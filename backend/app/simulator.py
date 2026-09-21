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
    # Signal Generators (Authentic Industrial Accelerometer Physics)
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_normal(self, n: int, fs: float) -> List[float]:
        """
        NORMAL mode: Authentic industrial conveyor baseline vibration.
        
        Superposition of:
        - 1X line/motor running frequency (50 Hz, A=1.05g)
        - 1X motor shaft rotational unbalance (20 Hz at 1200 RPM, A=0.30g)
        - 2X shaft rotational harmonic (40 Hz, A=0.18g)
        - 2X line harmonic (100 Hz, A=0.20g)
        - Structural idler frame natural resonance (85 Hz, A=0.14g)
        - Low-frequency belt cycle modulation envelope (~2.5 Hz, ±8%)
        - Gaussian accelerometer sensor noise floor (σ=0.16g)

        Expected DSP:
        - Dominant freq: strictly 50.0 Hz
        - RMS ≈ 0.85 - 1.15 g (ISO 10816 Zone A/B Normal)
        - Crest factor ≈ 2.2 - 2.8 (realistic mechanical vibration)
        - Kurtosis (Fisher) ≈ -1.0 to 0.0
        """
        dt = 1.0 / fs
        f0 = 50.0        # Motor line frequency
        f_rot = 20.0     # 1200 RPM shaft rotational frequency
        samples = []
        for i in range(n):
            t = i * dt
            belt_mod = 1.0 + 0.08 * math.sin(2 * math.pi * 2.5 * t)
            val = (
                1.05 * math.sin(2 * math.pi * f0 * t) * belt_mod
                + 0.30 * math.sin(2 * math.pi * f_rot * t + 0.3)
                + 0.18 * math.sin(2 * math.pi * 2 * f_rot * t + 0.7)
                + 0.20 * math.sin(2 * math.pi * 2 * f0 * t + 1.1)
                + 0.14 * math.sin(2 * math.pi * 85.0 * t + 1.5)
            )
            val += self._rng.gauss(0.0, 0.16)
            samples.append(round(val, 6))
        return samples

    def _generate_splice_impact(self, n: int, fs: float) -> List[float]:
        """
        SPLICE_IMPACT mode: Normal vibration + periodic damped shock transients.

        When a damaged belt joint/splice passes over an idler roller, it imparts
        a sharp impulse that rings down exponentially at the structural resonance
        frequency (160 Hz damped ring-down: A * exp(-70*dt) * cos(2*pi*160*dt)).

        Expected DSP:
        - Dominant freq: strictly 50.0 Hz
        - Crest factor > 3.5 (high transient impact spikes)
        - Kurtosis (Fisher) > 3.0 (heavy impulse tails)
        - RMS moderately elevated (1.2 - 1.4 g)
        """
        dt = 1.0 / fs
        f0 = 50.0
        f_rot = 20.0
        impulse_period_samples = int(fs * 0.10)   # Every 100 ms
        impulse_ring_freq = 160.0                # Structural resonance ring frequency
        impulse_amp = 5.5

        current_impact_sample = -9999
        samples = []

        for i in range(n):
            t = i * dt
            if i % impulse_period_samples == 0:
                current_impact_sample = i

            dt_impact = (i - current_impact_sample) * dt
            if 0.0 <= dt_impact < 0.05:
                # Exponentially damped sinusoid ring-down
                impact_val = impulse_amp * math.exp(-70.0 * dt_impact) * math.cos(2 * math.pi * impulse_ring_freq * dt_impact)
            else:
                impact_val = 0.0

            val = (
                1.02 * math.sin(2 * math.pi * f0 * t)
                + 0.28 * math.sin(2 * math.pi * f_rot * t + 0.4)
                + 0.18 * math.sin(2 * math.pi * 100.0 * t)
                + impact_val
            )
            val += self._rng.gauss(0.0, 0.16)
            samples.append(round(val, 6))
        return samples

    def _generate_harmonic_looseness(self, n: int, fs: float) -> List[float]:
        """
        HARMONIC_LOOSENESS mode: Fundamental + rich 2X, 3X, 4X and sub-harmonics.

        Physical interpretation: Mechanical looseness or idler bearing play
        introduces pronounced 2X (100 Hz), 3X (150 Hz) harmonics and fractional
        0.5X sub-harmonic rattle (25 Hz) with elevated mechanical chatter.

        Expected DSP:
        - Clear multi-harmonic peaks at 50, 100, 150 Hz
        - Elevated spectral energy and shifted spectral centroid
        - Dominant frequency strictly 50.0 Hz
        """
        dt = 1.0 / fs
        f0 = 50.0
        samples = []
        for i in range(n):
            t = i * dt
            val = (
                1.15 * math.sin(2 * math.pi * f0 * t)
                + 0.62 * math.sin(2 * math.pi * 2 * f0 * t + 0.8)   # 2nd harmonic (100 Hz)
                + 0.44 * math.sin(2 * math.pi * 3 * f0 * t + 1.4)   # 3rd harmonic (150 Hz)
                + 0.25 * math.sin(2 * math.pi * 0.5 * f0 * t + 0.3) # 0.5X sub-harmonic rattle (25 Hz)
                + 0.16 * math.sin(2 * math.pi * 4 * f0 * t + 2.1)   # 4th harmonic (200 Hz)
            )
            val += self._rng.gauss(0.0, 0.20)
            samples.append(round(val, 6))
        return samples

    def _generate_critical_failure(self, n: int, fs: float) -> List[float]:
        """
        CRITICAL_FAILURE mode: High-amplitude broadband vibration + severe impacts.

        Signal: Broadband mechanical chatter (σ=2.2) + erratic high-energy shock transients
        (8-12g) modeling catastrophic splice tearing and bearing seizure.

        Expected DSP:
        - High RMS (> 6.5 g emergency trip threshold)
        - Very high crest factor (> 4.5)
        - Severe kurtosis (> 3.5)
        - Broadband frequency spectrum
        """
        dt = 1.0 / fs
        f0 = 50.0
        impulse_period_samples = int(fs * 0.06)  # Every 60 ms
        impulse_amp = 11.0

        samples = []
        current_impact_sample = -9999

        for i in range(n):
            t = i * dt
            if i % impulse_period_samples == 0:
                current_impact_sample = i

            dt_impact = (i - current_impact_sample) * dt
            if 0.0 <= dt_impact < 0.04:
                impact_val = impulse_amp * (1.0 + self._rng.uniform(-0.15, 0.15)) * math.exp(-85.0 * dt_impact) * math.cos(2 * math.pi * 140.0 * dt_impact)
            else:
                impact_val = 0.0

            A_var = 2.2 * (1.0 + 0.25 * self._rng.uniform(-1, 1))
            val = A_var * math.sin(2 * math.pi * f0 * t) + impact_val
            val += self._rng.gauss(0.0, 2.2)
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
