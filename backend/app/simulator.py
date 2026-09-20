"""
Simulation Harness — Phase 3 Fault Preset Generator
=====================================================
Generates physically interpretable synthetic fault signals for pipeline
validation and SCADA demonstration.

STRICT INTEGRITY RULES:
1. Gated by settings.ALLOW_SIMULATION_INGESTION.
2. All packets carry DataProvenance.SIMULATION — never masquerades as LIVE.
3. Every simulated observation remains identifiable as SIMULATION in all
   downstream models, alerts, and UI panels.
4. All generated signals are physically interpretable — each preset alters
   the signal in a different, DSP-detectable way.

Simulation Modes
----------------
NORMAL
    Controlled 50 Hz sinusoidal vibration + low-level Gaussian noise.
    Expected DSP: low crest factor, kurtosis ≈ 0, stable dominant freq.

SPLICE_IMPACT
    Normal signal + periodic high-amplitude impulsive strikes every ~100 samples.
    Expected DSP: elevated crest factor (>4), elevated kurtosis (>3 Fisher),
    moderate RMS increase.

HARMONIC_LOOSENESS
    Fundamental 50 Hz + 2nd harmonic (100 Hz) + 3rd harmonic (150 Hz).
    Expected DSP: multiple spectral peaks, elevated spectral energy,
    shifted spectral centroid, dominant freq may shift.

CRITICAL_FAILURE
    Substantially elevated broadband noise + large-amplitude periodic impacts
    + reduced fundamental coherence. Multiple metrics simultaneously elevated.
    Expected DSP: high RMS, high crest factor, high kurtosis, broadband spectrum.
"""

import math
import random
import time
from typing import List, Optional
from fastapi import HTTPException, status

from .config import settings
from .schemas import SimulationPacketIn, DataProvenance, RawTelemetryPacketIn


# Fault mode labels — used in API and UI
FAULT_NORMAL = "NORMAL"
FAULT_SPLICE_IMPACT = "SPLICE_IMPACT"
FAULT_HARMONIC_LOOSENESS = "HARMONIC_LOOSENESS"
FAULT_CRITICAL_FAILURE = "CRITICAL_FAILURE"

VALID_FAULT_MODES = [FAULT_NORMAL, FAULT_SPLICE_IMPACT, FAULT_HARMONIC_LOOSENESS, FAULT_CRITICAL_FAILURE]


class SimulationHarnessDriver:
    """
    Isolated development test harness for validating pipeline ingestion,
    throughput, sequence continuity, and SQLite WAL persistence.

    STRICT INTEGRITY RULES:
    1. Gated by settings.ALLOW_SIMULATION_INGESTION.
    2. Enforces DataProvenance.SIMULATION on all generated packets.
    3. Never masquerades as LIVE hardware.
    """
    def __init__(self):
        self.device_id = "test-rig-simulator-01"
        self.stream_id = "sim-accel-z"
        self.sequence_counter = 0
        self.last_timestamp_us = 0
        self._rng = random.Random(42)  # Seeded for reproducibility in tests

    def generate_test_packet(
        self,
        sensor_id: str,
        joint_id: Optional[str] = None,
        sample_count: int = 500,
        sampling_rate_hz: float = 1000.0,
        fundamental_freq_hz: float = 50.0,  # 50 Hz physical vibration frequency (well below 500 Hz Nyquist)
        amplitude: float = 1.5,
        sequence_override: Optional[int] = None,
        timestamp_override_us: Optional[int] = None,
    ) -> RawTelemetryPacketIn:
        """Original Phase 1/2 compatible test packet generator (NORMAL mode)."""
        if not settings.ALLOW_SIMULATION_INGESTION:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Simulation ingestion is disabled in this environment."
            )

        seq, hw_ts = self._next_seq_ts(sequence_override, timestamp_override_us)

        # Generate deterministic synthetic waveform for pipeline verification
        # 50 Hz fundamental + 120 Hz harmonic (both well below 500 Hz Nyquist limit at 1000 Hz sample rate)
        samples: List[float] = []
        dt = 1.0 / sampling_rate_hz
        for i in range(sample_count):
            t = i * dt
            val = amplitude * math.sin(2 * math.pi * fundamental_freq_hz * t) + 0.3 * math.sin(2 * math.pi * 120.0 * t)
            samples.append(round(val, 6))

        return RawTelemetryPacketIn(
            device_id=self.device_id,
            stream_id=self.stream_id,
            sensor_id=sensor_id,
            joint_id=joint_id,
            sequence_number=seq,
            hardware_timestamp_us=hw_ts,
            sampling_rate_hz=sampling_rate_hz,
            samples=samples,
            quality_flags="OK",
            data_provenance=DataProvenance.SIMULATION
        )

    def generate_fault_packet(
        self,
        sensor_id: str,
        fault_mode: str = FAULT_NORMAL,
        joint_id: Optional[str] = None,
        sample_count: int = 1000,
        sampling_rate_hz: float = 1000.0,
        sequence_override: Optional[int] = None,
        timestamp_override_us: Optional[int] = None,
    ) -> RawTelemetryPacketIn:
        """
        Generate a fault-mode simulation packet with physically interpretable signal.

        Parameters
        ----------
        fault_mode : str
            One of: NORMAL, SPLICE_IMPACT, HARMONIC_LOOSENESS, CRITICAL_FAILURE
        sample_count : int
            Number of samples. 1000 recommended for good FFT resolution at 1000 Hz.
        """
        if not settings.ALLOW_SIMULATION_INGESTION:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Simulation ingestion is disabled in this environment."
            )

        if fault_mode not in VALID_FAULT_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid fault_mode '{fault_mode}'. Valid: {VALID_FAULT_MODES}"
            )

        seq, hw_ts = self._next_seq_ts(sequence_override, timestamp_override_us)

        if fault_mode == FAULT_NORMAL:
            samples = self._generate_normal(sample_count, sampling_rate_hz)
        elif fault_mode == FAULT_SPLICE_IMPACT:
            samples = self._generate_splice_impact(sample_count, sampling_rate_hz)
        elif fault_mode == FAULT_HARMONIC_LOOSENESS:
            samples = self._generate_harmonic_looseness(sample_count, sampling_rate_hz)
        elif fault_mode == FAULT_CRITICAL_FAILURE:
            samples = self._generate_critical_failure(sample_count, sampling_rate_hz)
        else:
            samples = self._generate_normal(sample_count, sampling_rate_hz)

        return RawTelemetryPacketIn(
            device_id=self.device_id,
            stream_id=self.stream_id,
            sensor_id=sensor_id,
            joint_id=joint_id,
            sequence_number=seq,
            hardware_timestamp_us=hw_ts,
            sampling_rate_hz=sampling_rate_hz,
            samples=samples,
            quality_flags="OK",
            data_provenance=DataProvenance.SIMULATION
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Signal Generators
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_normal(self, n: int, fs: float) -> List[float]:
        """
        NORMAL mode: controlled 50 Hz sinusoidal vibration + low Gaussian noise.

        Signal: x(t) = 1.5*sin(2π*50*t) + noise(σ=0.05)

        Expected DSP:
        - RMS ≈ 1.5/√2 ≈ 1.06
        - Dominant freq ≈ 50 Hz
        - Crest factor ≈ √2 ≈ 1.41 (pure sine)
        - Kurtosis (Fisher) ≈ -1.5 (sine wave) to ≈ 0 (with noise)
        """
        dt = 1.0 / fs
        A = 1.5
        f0 = 50.0
        noise_sigma = 0.05
        samples = []
        for i in range(n):
            t = i * dt
            val = A * math.sin(2 * math.pi * f0 * t)
            val += self._rng.gauss(0.0, noise_sigma)
            samples.append(round(val, 6))
        return samples

    def _generate_splice_impact(self, n: int, fs: float) -> List[float]:
        """
        SPLICE_IMPACT mode: normal vibration + periodic impulsive strikes.

        Signal: normal(t) + periodic_impulse(t, period=100ms, amplitude=6.0)

        The impulse decays exponentially to model a real mechanical impact.
        Physical interpretation: a splice/joint striking a stationary component
        produces a brief high-amplitude transient every belt revolution fraction.

        Expected DSP:
        - Crest factor > 4 (high peak relative to RMS)
        - Kurtosis (Fisher) > 3 (heavy tails from impulses)
        - Dominant freq still ≈ 50 Hz (periodic fundamental unchanged)
        - RMS moderately elevated
        """
        dt = 1.0 / fs
        A = 1.5
        f0 = 50.0
        noise_sigma = 0.05

        # Impulse parameters
        impulse_amplitude = 6.0
        impulse_period_samples = int(fs * 0.10)   # Every 100 ms
        impulse_decay = 0.95                        # Exponential decay factor per sample

        samples = []
        impulse_state = 0.0  # Current impulse amplitude
        for i in range(n):
            t = i * dt
            # Trigger impulse at regular intervals
            if i % impulse_period_samples == 0:
                impulse_state = impulse_amplitude

            val = A * math.sin(2 * math.pi * f0 * t)
            val += self._rng.gauss(0.0, noise_sigma)
            val += impulse_state
            # Decay impulse
            impulse_state *= impulse_decay

            samples.append(round(val, 6))
        return samples

    def _generate_harmonic_looseness(self, n: int, fs: float) -> List[float]:
        """
        HARMONIC_LOOSENESS mode: fundamental + 2nd + 3rd harmonics.

        Signal: 1.2*sin(2π*50*t) + 0.5*sin(2π*100*t) + 0.3*sin(2π*150*t) + noise

        Physical interpretation: mechanical looseness or resonance introduces
        sub-harmonic or super-harmonic content. Belt tension variation or
        idler looseness produces 2x and 3x running frequency components.

        Expected DSP:
        - Three clear FFT peaks at 50, 100, 150 Hz
        - Elevated spectral energy relative to NORMAL
        - Spectral centroid shifted higher than NORMAL
        - Dominant freq may be 50 Hz (fundamental still strongest)
        """
        dt = 1.0 / fs
        f0 = 50.0
        noise_sigma = 0.07
        samples = []
        for i in range(n):
            t = i * dt
            val = (
                1.2 * math.sin(2 * math.pi * f0 * t)       # Fundamental
                + 0.5 * math.sin(2 * math.pi * 2*f0 * t)   # 2nd harmonic
                + 0.3 * math.sin(2 * math.pi * 3*f0 * t)   # 3rd harmonic
            )
            val += self._rng.gauss(0.0, noise_sigma)
            samples.append(round(val, 6))
        return samples

    def _generate_critical_failure(self, n: int, fs: float) -> List[float]:
        """
        CRITICAL_FAILURE mode: high-amplitude broadband noise + large impacts.

        Signal: broadband_noise(σ=2.5) + large_impulses(A=12, period=50ms)
                + degraded fundamental (reduced coherence)

        Physical interpretation: severely deteriorated splice producing large
        mechanical impacts at every passage, combined with broadband vibration
        from belt damage or structural looseness.

        Expected DSP:
        - High RMS (> engineering threshold)
        - Very high crest factor (>>4)
        - Very high kurtosis (>>3 Fisher)
        - Broadband spectrum (high spectral energy)
        - Dominant freq may shift or become ambiguous
        """
        dt = 1.0 / fs
        f0 = 50.0
        noise_sigma = 2.5     # Much higher than NORMAL (0.05)
        impulse_amp = 12.0    # Much larger than SPLICE_IMPACT (6.0)
        impulse_period_samples = int(fs * 0.05)  # Every 50 ms (double frequency)
        impulse_decay = 0.85  # Faster decay (more abrupt impacts)

        samples = []
        impulse_state = 0.0
        for i in range(n):
            t = i * dt
            if i % impulse_period_samples == 0:
                impulse_state = impulse_amp * (1.0 + self._rng.uniform(-0.2, 0.2))  # Variable amplitude

            # Reduced fundamental coherence (amplitude variation)
            A_var = 1.5 * (1.0 + 0.3 * self._rng.uniform(-1, 1))
            val = A_var * math.sin(2 * math.pi * f0 * t)
            val += self._rng.gauss(0.0, noise_sigma)
            val += impulse_state
            impulse_state *= impulse_decay

            samples.append(round(val, 6))
        return samples

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _next_seq_ts(
        self,
        sequence_override: Optional[int],
        timestamp_override_us: Optional[int],
    ):
        if sequence_override is not None:
            seq = sequence_override
        else:
            self.sequence_counter += 1
            seq = self.sequence_counter

        if timestamp_override_us is not None:
            hw_ts = timestamp_override_us
        else:
            hw_ts = int(time.time() * 1_000_000) % 4_294_967_296  # 32-bit microsecond counter

        return seq, hw_ts


sim_driver = SimulationHarnessDriver()
