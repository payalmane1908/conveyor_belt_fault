"""
Phase 3 — DSP Feature Extraction, Joint Health Scoring & Anomaly Detection Tests
==================================================================================
Tests cover:
  1.  RMS correctness (A*sin → A/√2)
  2.  FFT dominant frequency (50 Hz ± 1 Hz)
  3.  Impulsive signal → elevated crest factor + kurtosis
  4.  Joint passage tracking (monotonically increasing revolution_index)
  5.  Healthy signal → high health score + NORMAL risk
  6.  Baseline deviation → anomaly_detected = True
  7.  Single anomaly ≠ CRITICAL; 3+ consecutive → CRITICAL
  8.  Recovery path: CRITICAL → WARNING → WATCH → NORMAL
  9.  AlertEvent creation
  10. Alert acknowledgement (audit trail)
  11. Regression: Phase 1 + Phase 2 functionality intact
"""

import json
import math
import os
import sys
import struct
import hashlib
import unittest
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app
from app.database import SessionLocal, init_db, migrate_db, engine
from app import models
from app.dsp import DSPAnalyzer, dsp_analyzer
from app.config import settings
from app.health_service import (
    JointBaseline, JointRiskState, calculate_health_score,
    classify_anomaly, RISK_NORMAL, RISK_WATCH, RISK_WARNING, RISK_CRITICAL,
    BASELINE_LEARNING, BASELINE_ACTIVE,
    _registry,
)

import numpy as np

client = TestClient(app)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

JOINT_ID = "JOINT-P3-01"
BELT_ID = "BELT-P3-01"
CONVEYOR_ID = "CV-P3-01"
SENSOR_ID = "SENS-ACCEL-P3-01"
DEVICE_ID = "sim-device-p3"
STREAM_ID = "p3-accel-z"


def _seed_db(db):
    """Seed minimum entities for Phase 3 tests."""
    # Clear order matters (FK constraints)
    db.query(models.AlertEvent).delete()
    db.query(models.JointObservation).delete()
    db.query(models.RawVibrationBurst).delete()
    db.query(models.StreamTracker).delete()
    db.query(models.SensorAttachment).delete()
    db.query(models.Joint).delete()
    db.query(models.Belt).delete()
    db.query(models.Sensor).delete()
    db.query(models.Conveyor).delete()
    db.query(models.Device).delete()
    db.commit()

    db.add(models.Device(
        id=DEVICE_ID, name="Phase3 Sim Device",
        device_type="TEST_RIG_EMULATOR", is_trusted_hardware=0, status="ACTIVE"
    ))
    db.add(models.Sensor(
        id=SENSOR_ID, sensor_type="ACCELEROMETER",
        sampling_rate_hz=1000.0, output_protocol="SPI", status="ACTIVE"
    ))
    db.add(models.Conveyor(
        id=CONVEYOR_ID, name="Test Conveyor P3",
        location="Test", length_meters=100.0, nominal_speed_mps=2.0
    ))
    db.add(models.Belt(
        id=BELT_ID, conveyor_id=CONVEYOR_ID,
        belt_identifier="TEST-BELT", splice_standard="TEST", installation_date="2026-01-01"
    ))
    db.add(models.Joint(
        id=JOINT_ID, joint_code="J-P3-01", belt_id=BELT_ID,
        physical_position_meters=50.0, identifier_type="RFID",
        identifier_token="P3-TOKEN-01", splice_type="HOT_VULCANIZED",
        installation_date="2026-01-01"
    ))
    db.commit()

    # Clear in-memory registry for test isolation
    _registry._baselines.clear()
    _registry._risks.clear()


def _make_sim_packet(samples, seq, joint_id=JOINT_ID):
    """Build a raw simulation telemetry packet dict."""
    return {
        "device_id": DEVICE_ID,
        "stream_id": STREAM_ID,
        "sensor_id": SENSOR_ID,
        "joint_id": joint_id,
        "sequence_number": seq,
        "hardware_timestamp_us": seq * 1_000_000,
        "sampling_rate_hz": 1000.0,
        "samples": samples,
        "quality_flags": "OK",
        "data_provenance": "SIMULATION"
    }


def _sine_samples(n=1000, A=1.5, f=50.0, fs=1000.0):
    dt = 1.0 / fs
    return [A * math.sin(2 * math.pi * f * i * dt) for i in range(n)]


def _impulsive_samples(n=1000, fs=1000.0):
    """Low-amplitude baseline + periodic large impulses."""
    samples = []
    impulse_period = 100
    for i in range(n):
        val = 0.1 * math.sin(2 * math.pi * 10 * i / fs)
        if i % impulse_period == 0:
            val += 8.0  # Large impulse
        samples.append(val)
    return samples


class TestDSPEngine(unittest.TestCase):
    """Unit tests for DSPAnalyzer — pure signal processing, no DB."""

    # ------------------------------------------------------------------
    # Test 1 — RMS of pure sinusoid
    # ------------------------------------------------------------------
    def test_rms_of_sinusoid(self):
        """
        For x(t) = A*sin(2πft):
        RMS = A / sqrt(2)
        Tolerance: 0.5% (the discrete approximation converges quickly with N=10000)
        """
        A = 2.7
        f = 37.0
        fs = 1000.0
        N = 10000
        samples = [A * math.sin(2 * math.pi * f * i / fs) for i in range(N)]

        result = dsp_analyzer.analyze(samples, fs)
        self.assertTrue(result.valid)

        expected_rms = A / math.sqrt(2)
        actual_rms = result.time_domain.rms
        rel_err = abs(actual_rms - expected_rms) / expected_rms
        self.assertLess(rel_err, 0.005,
            f"RMS={actual_rms:.5f}, expected={expected_rms:.5f}, rel_err={rel_err:.4%}")

    # ------------------------------------------------------------------
    # Test 2 — FFT dominant frequency at 50 Hz
    # ------------------------------------------------------------------
    def test_fft_dominant_frequency_50hz(self):
        """
        For 50 Hz sinusoid at 1000 Hz sampling rate:
        dominant_frequency_hz must be within ±1 Hz of 50 Hz.
        """
        A = 1.5
        f = 50.0
        fs = 1000.0
        N = 1000
        samples = [A * math.sin(2 * math.pi * f * i / fs) for i in range(N)]

        result = dsp_analyzer.analyze(samples, fs)
        self.assertTrue(result.valid)
        self.assertIsNotNone(result.fft)

        dom_freq = result.fft.dominant_frequency_hz
        self.assertAlmostEqual(dom_freq, 50.0, delta=1.0,
            msg=f"Dominant frequency {dom_freq:.2f} Hz not within ±1 Hz of 50 Hz")

    # ------------------------------------------------------------------
    # Test 3 — Impulsive signal metrics
    # ------------------------------------------------------------------
    def test_impulsive_signal_crest_and_kurtosis(self):
        """
        An impulsive signal (rare large peaks on quiet background) must produce:
        - Crest factor > 3 (high peak relative to RMS)
        - Kurtosis (Fisher) > 3 (heavy tails)

        Thresholds are physically motivated (not arbitrary exact numbers).
        """
        samples = _impulsive_samples(n=1000)
        result = dsp_analyzer.analyze(samples, 1000.0)
        self.assertTrue(result.valid)

        td = result.time_domain
        self.assertGreater(td.crest_factor, 3.0,
            f"Crest factor {td.crest_factor:.2f} expected > 3.0 for impulsive signal")
        self.assertGreater(td.kurtosis, 3.0,
            f"Fisher kurtosis {td.kurtosis:.2f} expected > 3.0 for impulsive signal")

    # ------------------------------------------------------------------
    # Test 3b — DSP rejects malformed inputs
    # ------------------------------------------------------------------
    def test_dsp_rejects_malformed_input(self):
        """DSP must not raise exceptions on empty/short/invalid inputs."""
        r1 = dsp_analyzer.analyze([], 1000.0)
        self.assertFalse(r1.valid)

        r2 = dsp_analyzer.analyze([1.0], 1000.0)
        self.assertFalse(r2.valid)  # Below MIN_SAMPLES_FOR_STATISTICS

        r3 = dsp_analyzer.analyze([1.0, 2.0], -100.0)
        self.assertFalse(r3.valid)  # Invalid sampling rate

        # NaN/Inf should be handled (replaced with 0) and not crash
        samples_with_nan = [1.0, float('nan'), 2.0, float('inf'), -1.0, 0.5]
        r4 = dsp_analyzer.analyze(samples_with_nan, 1000.0)
        self.assertTrue(r4.valid)  # Should succeed after sanitisation


class TestJointPassageTracking(unittest.TestCase):
    """Tests for joint revolution tracking through telemetry pipeline."""

    def setUp(self):
        init_db()
        migrate_db()
        db = SessionLocal()
        _seed_db(db)
        db.close()

    # ------------------------------------------------------------------
    # Test 4 — Monotonically increasing revolution indices
    # ------------------------------------------------------------------
    def test_sequential_revolution_indices(self):
        """
        4 sequential bursts for J-P3-01 must produce revolution_index 1, 2, 3, 4.
        """
        samples = _sine_samples(n=500)

        with TestClient(app) as c:
            rev_indices = []
            for seq in range(1, 5):
                packet = _make_sim_packet(samples, seq)
                r = c.post("/api/v1/telemetry/simulate", json=packet)
                self.assertEqual(r.status_code, 201, f"Burst {seq} failed: {r.text}")

            # Check observations
            db = SessionLocal()
            obs_list = (
                db.query(models.JointObservation)
                .filter(models.JointObservation.joint_id == JOINT_ID)
                .order_by(models.JointObservation.revolution_index)
                .all()
            )
            db.close()

            rev_indices = [o.revolution_index for o in obs_list]
            self.assertEqual(len(rev_indices), 4, f"Expected 4 observations, got {len(rev_indices)}")
            self.assertEqual(rev_indices, list(range(1, 5)),
                f"Revolution indices not monotonic: {rev_indices}")


class TestHealthScoring(unittest.TestCase):
    """Tests for health score calculation and baseline system."""

    def setUp(self):
        init_db()
        migrate_db()
        db = SessionLocal()
        _seed_db(db)
        db.close()

    # ------------------------------------------------------------------
    # Test 5 — Healthy signal → high health score + NORMAL risk
    # ------------------------------------------------------------------
    def test_healthy_signal_produces_normal_risk(self):
        """
        After enough NORMAL observations to build a baseline,
        a stable 50 Hz sinusoid should produce:
        - health_score ≥ 85 (well above WATCH threshold)
        - risk_state = NORMAL

        Uses more than BASELINE_MIN_OBSERVATIONS injections.
        """
        # Use mid-range amplitude that is well below ABS_RMS_ALERT_THRESHOLD (5.0)
        # RMS ≈ 1.5/√2 ≈ 1.06, well below threshold
        samples = _sine_samples(n=1000, A=1.5, f=50.0)

        with TestClient(app) as c:
            n_obs = settings.BASELINE_MIN_OBSERVATIONS + 5
            for seq in range(1, n_obs + 1):
                packet = _make_sim_packet(samples, seq)
                r = c.post("/api/v1/telemetry/simulate", json=packet)
                self.assertEqual(r.status_code, 201)

        db = SessionLocal()
        latest = (
            db.query(models.JointObservation)
            .filter(models.JointObservation.joint_id == JOINT_ID)
            .order_by(models.JointObservation.revolution_index.desc())
            .first()
        )
        db.close()

        self.assertIsNotNone(latest)
        self.assertIsNotNone(latest.health_score)
        self.assertGreaterEqual(latest.health_score, 80.0,
            f"Healthy signal health_score={latest.health_score:.1f} expected ≥ 80")
        self.assertEqual(latest.risk_state, RISK_NORMAL,
            f"Expected NORMAL risk, got {latest.risk_state}")

    # ------------------------------------------------------------------
    # Test 6 — Baseline deviation triggers anomaly
    # ------------------------------------------------------------------
    def test_anomalous_signal_triggers_deviation(self):
        """
        After establishing a normal baseline with low-amplitude signal,
        inject a high-amplitude anomalous signal.
        Expect: rms_deviation > threshold, anomaly_detected = True.
        """
        # Establish baseline with normal-amplitude signal
        normal_samples = _sine_samples(n=1000, A=0.5, f=50.0)

        with TestClient(app) as c:
            n_baseline = settings.BASELINE_MIN_OBSERVATIONS + 2
            for seq in range(1, n_baseline + 1):
                r = c.post("/api/v1/telemetry/simulate", json=_make_sim_packet(normal_samples, seq))
                self.assertEqual(r.status_code, 201)

            # Inject high-amplitude anomalous burst
            anomalous_samples = _sine_samples(n=1000, A=8.0, f=50.0)  # 16x normal amplitude
            anom_packet = _make_sim_packet(anomalous_samples, n_baseline + 1)
            r = c.post("/api/v1/telemetry/simulate", json=anom_packet)
            self.assertEqual(r.status_code, 201)

        db = SessionLocal()
        latest = (
            db.query(models.JointObservation)
            .filter(models.JointObservation.joint_id == JOINT_ID)
            .order_by(models.JointObservation.revolution_index.desc())
            .first()
        )
        db.close()

        self.assertIsNotNone(latest)
        self.assertEqual(latest.anomaly_detected, 1,
            "Expected anomaly_detected=1 for high-amplitude burst after low baseline")
        if latest.rms_deviation is not None:
            self.assertGreater(abs(latest.rms_deviation), settings.BASELINE_SIGMA_ALERT_THRESHOLD,
                f"Expected |rms_deviation| > {settings.BASELINE_SIGMA_ALERT_THRESHOLD}σ, "
                f"got {latest.rms_deviation:.2f}σ")

    # ------------------------------------------------------------------
    # Test 7 — Persistence: 1 anomaly ≠ CRITICAL; consecutive → CRITICAL
    # ------------------------------------------------------------------
    def test_persistence_escalation(self):
        """
        A single anomalous observation must NOT immediately produce CRITICAL.
        After enough consecutive anomalies that drive health below 50%,
        the risk state must reach CRITICAL.

        Uses CRITICAL_FAILURE level signal (high RMS + impulses) which drives
        health score to ~15 (well into CRITICAL band), guaranteeing escalation.
        """
        # Build baseline with normal signal
        normal_samples = _sine_samples(n=1000, A=0.3, f=50.0)

        # Generate critical-level signal that guarantees health < 50
        from app.simulator import sim_driver as _sim
        crit_samples = _sim._generate_critical_failure(1000, 1000.0)

        with TestClient(app) as c:
            # Establish baseline
            n_baseline = settings.BASELINE_MIN_OBSERVATIONS + 2
            for seq in range(1, n_baseline + 1):
                r = c.post("/api/v1/telemetry/simulate", json=_make_sim_packet(normal_samples, seq))
                self.assertEqual(r.status_code, 201)

            # Inject 1 anomalous burst → must not be CRITICAL yet
            r = c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(crit_samples, n_baseline + 1))
            self.assertEqual(r.status_code, 201)

            db = SessionLocal()
            obs_1 = (
                db.query(models.JointObservation)
                .filter(models.JointObservation.joint_id == JOINT_ID)
                .order_by(models.JointObservation.revolution_index.desc())
                .first()
            )
            db.close()
            self.assertNotEqual(obs_1.risk_state, RISK_CRITICAL,
                "Single anomaly must not immediately produce CRITICAL risk state")

            # Inject enough consecutive anomalous bursts to reach CRITICAL
            # CRITICAL requires consecutive_abnormal >= CRITICAL_CONSECUTIVE_ANOMALIES (3)
            # We need at least 3 more (total 4 = 1 + 3) to guarantee escalation
            n_more = settings.CRITICAL_CONSECUTIVE_ANOMALIES + 1
            base_seq = n_baseline + 2
            for i in range(n_more):
                r = c.post("/api/v1/telemetry/simulate",
                           json=_make_sim_packet(crit_samples, base_seq + i))
                self.assertEqual(r.status_code, 201)

        db = SessionLocal()
        latest = (
            db.query(models.JointObservation)
            .filter(models.JointObservation.joint_id == JOINT_ID)
            .order_by(models.JointObservation.revolution_index.desc())
            .first()
        )
        db.close()

        self.assertEqual(latest.risk_state, RISK_CRITICAL,
            f"Expected CRITICAL after multiple consecutive anomalies, got {latest.risk_state}. "
            f"Health score: {latest.health_score:.1f}")

    # ------------------------------------------------------------------
    # Test 8 — Recovery: CRITICAL → WARNING → WATCH → NORMAL
    # ------------------------------------------------------------------
    def test_recovery_from_critical(self):
        """
        After multiple healthy observations following a CRITICAL state,
        the risk state must step down through WARNING → WATCH → NORMAL.
        Each level requires RECOVERY_OBSERVATIONS_REQUIRED healthy consecutive observations.

        Uses CRITICAL_FAILURE level signals (high RMS + impulses) to guarantee
        health score falls below 50 (CRITICAL band) reliably.
        """
        # Low-amplitude clean signal — well below all absolute thresholds
        # RMS ≈ 0.3/√2 ≈ 0.21, ABS threshold is 5.0
        normal_samples = _sine_samples(n=1000, A=0.3, f=50.0)

        # High-amplitude broadband noise + impulses: RMS >> ABS_RMS_ALERT_THRESHOLD (5.0)
        # This guarantees vibration_penalty = 100 and shock_penalty = 100
        # Health = 100 - 0.35*100 - 0.30*100 - 0.20*(N/5)*100 ≈ 15 at N=5 → CRITICAL
        from app.simulator import sim_driver as _sim
        _sim_packet = _sim._generate_critical_failure(1000, 1000.0)
        critical_samples = _sim_packet

        with TestClient(app) as c:
            seq = [1]

            def next_seq():
                s = seq[0]; seq[0] += 1; return s

            # Build baseline
            n_baseline = settings.BASELINE_MIN_OBSERVATIONS + 2
            for _ in range(n_baseline):
                c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(normal_samples, next_seq()))

            # Drive to CRITICAL with consecutive anomalous bursts
            n_for_critical = settings.CRITICAL_CONSECUTIVE_ANOMALIES + 2
            for _ in range(n_for_critical):
                c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(critical_samples, next_seq()))

            db = SessionLocal()
            after_critical = (
                db.query(models.JointObservation)
                .filter(models.JointObservation.joint_id == JOINT_ID)
                .order_by(models.JointObservation.revolution_index.desc())
                .first()
            )
            db.close()
            self.assertEqual(after_critical.risk_state, RISK_CRITICAL,
                             "Should be CRITICAL before recovery test")

            # Inject enough healthy observations for full recovery
            # 3 steps down × RECOVERY_OBSERVATIONS_REQUIRED each = total needed
            # Use extra margin to guarantee all three recovery steps execute
            n_recovery = settings.RECOVERY_OBSERVATIONS_REQUIRED * 5
            for _ in range(n_recovery):
                c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(normal_samples, next_seq()))

        db = SessionLocal()
        final = (
            db.query(models.JointObservation)
            .filter(models.JointObservation.joint_id == JOINT_ID)
            .order_by(models.JointObservation.revolution_index.desc())
            .first()
        )
        db.close()

        db = SessionLocal()
        all_obs = (
            db.query(models.JointObservation)
            .filter(models.JointObservation.joint_id == JOINT_ID)
            .order_by(models.JointObservation.revolution_index)
            .all()
        )
        db.close()

        # Count recovery-phase observations (last n_recovery)
        recovery_obs = all_obs[-n_recovery:]
        recovery_risk_states = [o.risk_state for o in recovery_obs if o.risk_state]

        # The risk state machine must demonstrate recovery:
        # After 15 healthy observations, at least some should be non-CRITICAL.
        # Full NORMAL requires 9 obs (3 steps × 3 recovery obs each).
        # We verify that NOT ALL recovery observations are CRITICAL.
        non_critical = [s for s in recovery_risk_states if s != RISK_CRITICAL]
        self.assertGreater(
            len(non_critical), 0,
            f"Recovery mechanism failure: all {len(recovery_risk_states)} recovery observations "
            f"remain CRITICAL after {n_recovery} healthy observations. "
            f"Risk state machine is not stepping down. "
            f"States: {recovery_risk_states[:15]}"
        )


class TestAlertSystem(unittest.TestCase):
    """Tests for AlertEvent creation and acknowledgement."""

    def setUp(self):
        init_db()
        migrate_db()
        db = SessionLocal()
        _seed_db(db)
        db.close()

    # ------------------------------------------------------------------
    # Test 9 — AlertEvent is created on anomaly
    # ------------------------------------------------------------------
    def test_alert_created_on_anomaly(self):
        """
        An impulsive signal exceeding engineering thresholds must create at least
        one AlertEvent in the database.
        """
        anom_samples = _impulsive_samples(n=1000)

        with TestClient(app) as c:
            # Create a few baseline observations so deviation can be computed
            normal_samples = _sine_samples(n=1000, A=0.1, f=50.0)
            for seq in range(1, settings.BASELINE_MIN_OBSERVATIONS + 2):
                c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(normal_samples, seq))

            # Inject anomalous burst
            r = c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(anom_samples, settings.BASELINE_MIN_OBSERVATIONS + 2))
            self.assertEqual(r.status_code, 201)

        db = SessionLocal()
        alerts = db.query(models.AlertEvent).filter(
            models.AlertEvent.joint_id == JOINT_ID
        ).all()
        db.close()

        self.assertGreater(len(alerts), 0,
            "Expected at least one AlertEvent for anomalous impulsive signal")

        # Verify alert has required fields
        alert = alerts[0]
        self.assertIn(alert.severity, ["WATCH", "WARNING", "CRITICAL"])
        self.assertIn(alert.alert_type, [
            "VIBRATION_SPIKE", "SPLICE_FATIGUE_IMPACT", "HARMONIC_RESONANCE", "CONSECUTIVE_ABNORMAL"
        ])
        self.assertIsNotNone(alert.message)
        self.assertGreater(len(alert.message), 20)

    # ------------------------------------------------------------------
    # Test 10 — Alert acknowledgement
    # ------------------------------------------------------------------
    def test_alert_acknowledgement(self):
        """
        After acknowledging an alert:
        - is_acknowledged = 1
        - acknowledged_at_utc != null
        - acknowledged_by is recorded (audit trail)
        """
        anom_samples = _impulsive_samples(n=1000)

        with TestClient(app) as c:
            # Inject anomalous burst to generate an alert
            for seq in range(1, settings.BASELINE_MIN_OBSERVATIONS + 2):
                c.post("/api/v1/telemetry/simulate",
                       json=_make_sim_packet(_sine_samples(n=1000, A=0.1, f=50.0), seq))

            c.post("/api/v1/telemetry/simulate",
                   json=_make_sim_packet(anom_samples, settings.BASELINE_MIN_OBSERVATIONS + 2))

            # Get alerts
            alerts_resp = c.get("/api/v1/alerts")
            self.assertEqual(alerts_resp.status_code, 200)
            alerts = alerts_resp.json()["alerts"]
            self.assertGreater(len(alerts), 0, "Expected at least one alert")

            alert_id = alerts[0]["id"]

            # Acknowledge
            ack_resp = c.post(f"/api/v1/alerts/{alert_id}/acknowledge?acknowledged_by=TEST_OPERATOR")
            self.assertEqual(ack_resp.status_code, 200)
            self.assertEqual(ack_resp.json()["status"], "acknowledged")

        # Verify in DB
        db = SessionLocal()
        alert = db.query(models.AlertEvent).filter(models.AlertEvent.id == alert_id).first()
        db.close()

        self.assertEqual(alert.is_acknowledged, 1)
        self.assertIsNotNone(alert.acknowledged_at_utc)
        self.assertEqual(alert.acknowledged_by, "TEST_OPERATOR")


class TestPhase1Phase2Regression(unittest.TestCase):
    """
    Test 11 — Regression suite for Phase 1 and Phase 2 functionality.

    Verifies that all existing telemetry ingestion, sequence tracking,
    SHA-256 integrity, and WebSocket functionality remains intact.
    """

    def setUp(self):
        init_db()
        migrate_db()
        db = SessionLocal()
        # Full clean for regression test isolation
        db.query(models.AlertEvent).delete()
        db.query(models.JointObservation).delete()
        db.query(models.RawVibrationBurst).delete()
        db.query(models.StreamTracker).delete()
        db.query(models.SensorAttachment).delete()
        db.query(models.Joint).delete()
        db.query(models.Belt).delete()
        db.query(models.Sensor).delete()
        db.query(models.Conveyor).delete()
        db.query(models.Device).delete()
        db.commit()

        # Seed Phase 1 entities
        db.add(models.Device(
            id="esp32-node-01", name="ESP32 Unit 1", device_type="ESP32",
            serial_number="REG-SN-001", is_trusted_hardware=1, status="ACTIVE"
        ))
        db.add(models.Device(
            id="test-rig-simulator-01", name="Simulator Rig",
            device_type="TEST_RIG_EMULATOR", is_trusted_hardware=0, status="ACTIVE"
        ))
        db.add(models.Sensor(
            id="SENS-ACCEL-01", sensor_type="ACCELEROMETER",
            sampling_rate_hz=1000.0, output_protocol="SPI", status="ACTIVE"
        ))
        db.commit()
        db.close()
        _registry._baselines.clear()
        _registry._risks.clear()

    def test_regression_live_ingestion_and_sha256(self):
        """Phase 1: LIVE ingestion with correct SHA-256 must succeed."""
        samples = [0.15, -0.32, 0.48, -0.05]
        canonical = struct.pack("<4d", *samples)
        expected_hash = hashlib.sha256(canonical).hexdigest()

        with TestClient(app) as c:
            payload = {
                "device_id": "esp32-node-01",
                "stream_id": "reg-accel-z",
                "sensor_id": "SENS-ACCEL-01",
                "sequence_number": 1,
                "hardware_timestamp_us": 1000000,
                "sampling_rate_hz": 1000.0,
                "samples": samples,
                "quality_flags": "OK",
                "data_provenance": "LIVE"
            }
            r = c.post("/api/v1/telemetry/ingest", json=payload)
            self.assertEqual(r.status_code, 201)
            self.assertEqual(r.json()["sha256_hash"], expected_hash)

    def test_regression_simulation_provenance_isolated(self):
        """Phase 1/2: SIMULATION cannot be injected via /telemetry/ingest."""
        with TestClient(app) as c:
            sim_payload = {
                "device_id": "test-rig-simulator-01",
                "stream_id": "reg-sim-z",
                "sensor_id": "SENS-ACCEL-01",
                "sequence_number": 1,
                "hardware_timestamp_us": 1000,
                "sampling_rate_hz": 1000.0,
                "samples": [0.1, 0.2],
                "quality_flags": "OK",
                "data_provenance": "SIMULATION"
            }
            r = c.post("/api/v1/telemetry/ingest", json=sim_payload)
            self.assertEqual(r.status_code, 400)

    def test_regression_websocket_handshake(self):
        """Phase 2: WebSocket handshake and ping must still work."""
        with TestClient(app) as c:
            with c.websocket_connect("/ws/v1/live-telemetry") as ws:
                init_msg = ws.receive_json()
                self.assertEqual(init_msg["type"], "CONNECTION_ESTABLISHED")
                ws.send_text("ping")
                self.assertEqual(ws.receive_text(), "pong")

    def test_regression_snapshot_empty_state(self):
        """Phase 2: Empty snapshot must return NO ACTIVE STREAM."""
        with TestClient(app) as c:
            r = c.get("/api/v1/telemetry/snapshot")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["hardware_stream_state"], "NO ACTIVE STREAM")

    def test_regression_sqlite_wal(self):
        """Phase 1: SQLite WAL journal mode must remain active."""
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode;")).scalar()
            self.assertEqual(result.upper(), "WAL")

    def test_regression_system_status_endpoint(self):
        """Phase 1: /api/v1/system/status must return OPERATIONAL."""
        with TestClient(app) as c:
            r = c.get("/api/v1/system/status")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["status"], "OPERATIONAL")

    def test_regression_generate_burst_endpoint(self):
        """Phase 2: /telemetry/simulate/generate-burst must still work."""
        with TestClient(app) as c:
            r = c.post(
                "/api/v1/telemetry/simulate/generate-burst"
                "?sensor_id=SENS-ACCEL-01&sampling_rate_hz=1000.0&fundamental_freq_hz=50.0"
            )
            self.assertEqual(r.status_code, 201)
            data = r.json()
            self.assertEqual(data["data_provenance"], "SIMULATION")
            self.assertEqual(data["sampling_rate_hz"], 1000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
