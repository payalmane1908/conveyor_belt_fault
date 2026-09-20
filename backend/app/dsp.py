"""
DSP Engine — Digital Signal Processing for Raw Vibration Bursts
================================================================
Provides deterministic, mathematically documented feature extraction
for use in joint health scoring and anomaly detection.

All features are labeled as DSP measurements. No ISO compliance is
claimed unless the measurement setup and machine classification are
explicitly verified by a qualified engineer.

Kurtosis convention: Fisher/Excess kurtosis throughout.
  - Gaussian white noise baseline ≈ 0
  - Impulsive signals yield positive excess kurtosis
  - scipy.stats.kurtosis(fisher=True) is used exclusively
  - Do NOT mix with Pearson kurtosis (Gaussian baseline = 3)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from scipy import stats as sp_stats

logger = logging.getLogger("dsp")

# ---------------------------------------------------------------------------
# Minimum sample requirements
# ---------------------------------------------------------------------------
MIN_SAMPLES_FOR_FFT = 4          # Absolute minimum for a meaningful FFT
MIN_SAMPLES_FOR_STATISTICS = 2   # Minimum for variance-based metrics


@dataclass
class TimeDomainFeatures:
    """
    Time-domain vibration features extracted from a raw sample burst.

    All acceleration units match the input (typically g or m/s²).
    The caller is responsible for unit consistency.

    Kurtosis: Fisher/excess convention.  Gaussian signal → ~0.
    """
    rms: float
    """RMS = sqrt(mean(x²)).  Represents energy content."""

    peak: float
    """Peak = max(|x|).  Maximum absolute amplitude."""

    peak_to_peak: float
    """Peak-to-peak = max(x) - min(x).  Full signal excursion."""

    crest_factor: float
    """Crest Factor = peak / RMS.  Impulsive content indicator.
    Returns 0.0 when RMS is zero (DC or flat signal)."""

    kurtosis: float
    """Fisher/excess kurtosis.  Gaussian ≈ 0.  Elevated values indicate
    impulsive behavior (e.g., impact, splice strike).  This is NOT a
    direct indicator of physical damage — it is an impulsive vibration
    anomaly indicator requiring engineering interpretation."""

    skewness: float
    """Statistical skewness of the amplitude distribution."""

    sample_count: int
    """Number of samples used in the calculation."""


@dataclass
class FFTFeatures:
    """
    Single-sided FFT features for a real-valued vibration signal.

    The amplitude spectrum uses the standard single-sided normalization:
        A[k] = 2 * |FFT[k]| / N    for k > 0
        A[0] = |FFT[0]| / N         (DC component)

    This normalization ensures that for x(t) = A*sin(2πft) sampled at fs:
        dominant_amplitude ≈ A
    """
    frequency_bins_hz: List[float]
    """Frequency axis in Hz for each FFT bin."""

    amplitude_spectrum: List[float]
    """Normalized single-sided amplitude spectrum (same unit as input)."""

    dominant_frequency_hz: float
    """Frequency of the highest-amplitude spectral component (Hz)."""

    dominant_amplitude: float
    """Amplitude at the dominant frequency."""

    spectral_centroid_hz: float
    """Spectral centroid = sum(f * A) / sum(A).  Weighted centre of mass
    of the spectrum.  Shifts higher when high-frequency content increases."""

    spectral_energy: float
    """Total spectral energy = sum(A²).  Proportional to signal power."""

    sample_count: int
    """Number of time-domain samples used."""

    sampling_rate_hz: float
    """Sampling rate used for frequency bin calculation."""


@dataclass
class DSPResult:
    """Combined DSP analysis result for one burst."""
    time_domain: Optional[TimeDomainFeatures] = None
    fft: Optional[FFTFeatures] = None
    valid: bool = False
    rejection_reason: Optional[str] = None


class DSPAnalyzer:
    """
    DSP feature extraction engine for raw vibration acceleration bursts.

    Usage:
        analyzer = DSPAnalyzer()
        result = analyzer.analyze(samples, sampling_rate_hz=1000.0)

    The analyzer never raises exceptions on malformed input — it returns
    DSPResult(valid=False, rejection_reason=...) so that malformed bursts
    do not crash the ingestion pipeline.
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze(
        self,
        samples: List[float],
        sampling_rate_hz: float,
    ) -> DSPResult:
        """
        Full DSP analysis: time-domain + FFT.

        Parameters
        ----------
        samples : list of float
            Raw vibration acceleration samples.
        sampling_rate_hz : float
            Acquisition sampling rate in Hz.

        Returns
        -------
        DSPResult
            Contains time_domain and fft features if valid, otherwise
            valid=False with rejection_reason explaining what was wrong.
        """
        # Input validation
        ok, reason = self._validate_input(samples, sampling_rate_hz)
        if not ok:
            logger.warning("DSP analysis rejected: %s", reason)
            return DSPResult(valid=False, rejection_reason=reason)

        arr = np.asarray(samples, dtype=np.float64)

        # Sanitise NaN / Inf before any computation
        n_bad = int(np.sum(~np.isfinite(arr)))
        if n_bad > 0:
            logger.warning("DSP: %d non-finite samples detected; replacing with 0.", n_bad)
            arr = np.where(np.isfinite(arr), arr, 0.0)

        td_features = self.compute_time_domain_features(arr)
        fft_features = self.compute_fft_spectrum(arr, sampling_rate_hz)

        return DSPResult(
            time_domain=td_features,
            fft=fft_features,
            valid=True,
        )

    # ------------------------------------------------------------------
    # Time-Domain Features
    # ------------------------------------------------------------------

    def compute_time_domain_features(self, samples: np.ndarray) -> TimeDomainFeatures:
        """
        Compute time-domain statistical features from a 1-D numpy array.

        Mathematical definitions
        ------------------------
        RMS           = sqrt(mean(x²))
        Peak          = max(|x|)
        Peak-to-peak  = max(x) - min(x)
        Crest Factor  = peak / RMS   (0.0 when RMS = 0)
        Kurtosis      = Fisher/excess kurtosis  (scipy.stats.kurtosis, fisher=True)
                        Gaussian signal → ~0; impulsive signal → positive
        Skewness      = scipy.stats.skew(x)
        """
        n = len(samples)

        # RMS
        rms = float(np.sqrt(np.mean(samples ** 2)))

        # Peak (maximum absolute amplitude)
        peak = float(np.max(np.abs(samples)))

        # Peak-to-peak
        p2p = float(np.max(samples) - np.min(samples))

        # Crest Factor — guarded against RMS = 0
        if rms > 0.0:
            crest_factor = peak / rms
        else:
            crest_factor = 0.0
        crest_factor = float(crest_factor)

        # Kurtosis — Fisher/excess convention (Gaussian baseline ≈ 0)
        if n >= MIN_SAMPLES_FOR_STATISTICS:
            kurtosis = float(sp_stats.kurtosis(samples, fisher=True, bias=True))
        else:
            kurtosis = 0.0

        # Skewness
        if n >= MIN_SAMPLES_FOR_STATISTICS:
            skewness = float(sp_stats.skew(samples, bias=True))
        else:
            skewness = 0.0

        return TimeDomainFeatures(
            rms=rms,
            peak=peak,
            peak_to_peak=p2p,
            crest_factor=crest_factor,
            kurtosis=kurtosis,
            skewness=skewness,
            sample_count=n,
        )

    # ------------------------------------------------------------------
    # FFT / Frequency-Domain Features
    # ------------------------------------------------------------------

    def compute_fft_spectrum(
        self,
        samples: np.ndarray,
        sampling_rate_hz: float,
    ) -> Optional[FFTFeatures]:
        """
        Single-sided FFT spectrum for real-valued vibration signal.

        Normalization
        -------------
        Single-sided amplitude spectrum:
            A[k] = 2 * |FFT[k]| / N    for k in {1 ... N//2}
            A[0] = |FFT[0]| / N         (DC component)

        For x(t) = A * sin(2π f t) with N samples:
            |FFT[k_dominant]| ≈ N * A / 2
            A[k_dominant] = 2 * (N * A / 2) / N = A   ✓

        Dominant frequency is identified by argmax of the amplitude
        spectrum (excluding DC bin 0 to avoid DC bias artefacts).

        Returns None if the signal is too short for FFT.
        """
        n = len(samples)
        if n < MIN_SAMPLES_FOR_FFT:
            logger.warning("DSP FFT: too few samples (%d < %d).", n, MIN_SAMPLES_FOR_FFT)
            return None

        # rfft operates on real signals — output length is (N//2 + 1)
        fft_complex = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(n, d=1.0 / sampling_rate_hz)

        # Single-sided amplitude normalization
        amplitude = np.abs(fft_complex) / n
        amplitude[1:] *= 2.0  # double for single-sided (DC stays as-is)

        # Dominant frequency: argmax excluding DC (bin 0)
        if len(amplitude) > 1:
            search_amp = amplitude[1:]   # exclude DC
            dom_idx_offset = int(np.argmax(search_amp))
            dom_idx = dom_idx_offset + 1
        else:
            dom_idx = 0

        dominant_frequency_hz = float(freqs[dom_idx])
        dominant_amplitude = float(amplitude[dom_idx])

        # Spectral centroid (weighted mean frequency by amplitude)
        amp_sum = float(np.sum(amplitude))
        if amp_sum > 0.0:
            centroid = float(np.sum(freqs * amplitude) / amp_sum)
        else:
            centroid = 0.0

        # Total spectral energy
        spectral_energy = float(np.sum(amplitude ** 2))

        return FFTFeatures(
            frequency_bins_hz=freqs.tolist(),
            amplitude_spectrum=amplitude.tolist(),
            dominant_frequency_hz=dominant_frequency_hz,
            dominant_amplitude=dominant_amplitude,
            spectral_centroid_hz=centroid,
            spectral_energy=spectral_energy,
            sample_count=n,
            sampling_rate_hz=sampling_rate_hz,
        )

    # ------------------------------------------------------------------
    # Input Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_input(
        samples: List[float],
        sampling_rate_hz: float,
    ) -> Tuple[bool, str]:
        """
        Returns (is_valid, rejection_reason).
        Empty string reason means valid.
        """
        if samples is None or len(samples) == 0:
            return False, "Sample array is empty"
        if sampling_rate_hz <= 0.0 or not math.isfinite(sampling_rate_hz):
            return False, f"Invalid sampling rate: {sampling_rate_hz}"
        if len(samples) < MIN_SAMPLES_FOR_STATISTICS:
            return False, f"Too few samples: {len(samples)} < {MIN_SAMPLES_FOR_STATISTICS}"
        return True, ""


# Module-level singleton — import and reuse across the service layer
dsp_analyzer = DSPAnalyzer()
