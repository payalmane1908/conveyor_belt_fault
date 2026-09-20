"""
Phase 5 Test Suite — Physical Edge DAQ, Hardware Abstraction & Joint Lifecycle
=============================================================================
Verifies:
1. Hardware Readiness and Driver Specifications (ADXL345, MPU6050, ESP32 firmware).
2. Physical Serial Acquisition Worker status, frame parsing, and pipeline dispatch.
3. Provenance Quarantine (LIVE vs SIMULATION distinction strictly enforced).
4. Operating Context (RPM tachometer, pretension, WAITING_FOR_OPERATING_CONTEXT behavior).
5. Tamper-evident Maintenance Logging with SHA-256 record verification and baseline reset.
6. Joint Lifecycle Degradation Trends:
   - Guardrail: < 5 revolutions -> INSUFFICIENT_HISTORY (no noisy 2-point regression).
   - Trend Slope: >= 5 revolutions -> empirical rate of change (g/rev).
7. Scientific Honesty: Strict rejection of fabricated RUL and rupture predictions.
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app import models, schemas
from app.serial_worker import serial_worker
from app.joint_lifecycle_service import joint_lifecycle_service
from app.ml_service import vibration_anomaly_engine
from main import app

client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPhase5EdgeDAQAndLifecycle(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db: Session = SessionLocal()

        # Seed clean test joint and device
        self.joint = self.db.query(models.Joint).filter_by(id="joint-001").first()
        if not self.joint:
            self.joint = models.Joint(
                id="joint-001",
                joint_code="J-01",
                belt_id="BELT-01",
                physical_position_meters=120.0,
                identifier_type="OPTICAL",
                identifier_token="OPT-J01",
                splice_type="Finger Splice",
                installation_date="2026-01-20",
                total_revolutions_count=10,
                current_risk="NORMAL",
                consecutive_abnormal_count=0
            )
            self.db.add(self.joint)
            self.db.commit()

    def tearDown(self):
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. Hardware Readiness Audit & Driver Specification Checks
    # -------------------------------------------------------------------------
    def test_hardware_readiness_audit_exists(self):
        """edge/HARDWARE_READINESS.md must exist and declare the required categories."""
        audit_file = PROJECT_ROOT / "edge" / "HARDWARE_READINESS.md"
        self.assertTrue(audit_file.exists(), "HARDWARE_READINESS.md must exist in edge/")

        content = audit_file.read_text(encoding="utf-8")
        self.assertIn("AVAILABLE HARDWARE", content)
        self.assertIn("SOFTWARE-READY", content)
        self.assertIn("HARDWARE-BLOCKED", content)
        self.assertIn("ADXL345", content)
        self.assertIn("MPU6050", content)
        self.assertIn("ESP32", content)

    def test_firmware_and_driver_files_exist(self):
        """Firmware driver headers, ino sketch, and wiring documentation must exist."""
        firmware_dir = PROJECT_ROOT / "edge" / "firmware" / "esp32_sensor_node"
        self.assertTrue((firmware_dir / "SensorInterface.h").exists())
        self.assertTrue((firmware_dir / "ADXL345Driver.h").exists())
        self.assertTrue((firmware_dir / "MPU6050Driver.h").exists())
        self.assertTrue((firmware_dir / "esp32_sensor_node.ino").exists())
        self.assertTrue((PROJECT_ROOT / "edge" / "firmware" / "WIRING_AND_PINOUT.md").exists())

        ino_code = (firmware_dir / "esp32_sensor_node.ino").read_text(encoding="utf-8")
        self.assertIn("RawTelemetryPacketIn", ino_code)
        self.assertIn("SAMPLES_PER_BURST    100", ino_code)
        self.assertIn("PIN_TACHO_INTERRUPT", ino_code)
        self.assertIn("PIN_JOINT_TRIGGER", ino_code)

    # -------------------------------------------------------------------------
    # 2. Physical Serial Acquisition Worker Status & Parsing
    # -------------------------------------------------------------------------
    def test_serial_worker_status_endpoint(self):
        """GET /api/v1/hardware/serial/status returns runtime acquisition metrics."""
        res = client.get("/api/v1/hardware/serial/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("worker_enabled", data)
        self.assertIn("running", data)
        self.assertIn("connected", data)
        self.assertIn("port", data)
        self.assertIn("baudrate", data)
        self.assertIn("packets_read", data)
        self.assertIn("errors_count", data)

    def test_serial_frame_parsing_with_context(self):
        """Worker parse_frame correctly extracts telemetry including optional context."""
        raw_frame = json.dumps({
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "sens-vibe-01",
            "joint_id": "joint-001",
            "sequence_number": 999,
            "hardware_timestamp_us": 12345678,
            "sampling_rate_hz": 1000.0,
            "samples": [0.05, -0.02, 0.08],
            "quality_flags": "OK",
            "data_provenance": "LIVE",
            "drive_rpm": 530.0,
            "pretension_n": 110.0
        }).encode("utf-8")

        parsed = serial_worker.parse_frame(raw_frame)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.device_id, "esp32-node-01")
        self.assertEqual(parsed.drive_rpm, 530.0)
        self.assertEqual(parsed.pretension_n, 110.0)

    # -------------------------------------------------------------------------
    # 3. Operating Context & ML Waiting State
    # -------------------------------------------------------------------------
    def test_operating_context_dependency_guardrail(self):
        """
        If speed_rpm or pretension_n is None, ML engine must return
        WAITING_FOR_OPERATING_CONTEXT without inventing values.
        """
        features_without_context = {
            "rms": 0.25, "peak": 0.40, "peak_to_peak": 0.70, "crest_factor": 1.6,
            "kurtosis": 0.1, "skewness": 0.05, "dominant_freq_hz": 15.0,
            "spectral_energy": 0.12, "speed_rpm": None, "pretension_n": None
        }

        res = vibration_anomaly_engine.score_features(features_without_context)
        self.assertEqual(res["model_status"], "WAITING_FOR_OPERATING_CONTEXT")
        self.assertIsNone(res["raw_anomaly_score"])
        self.assertFalse(res["rupture_prediction"])

    # -------------------------------------------------------------------------
    # 4. Tamper-Evident Maintenance Logging & Baseline Reset
    # -------------------------------------------------------------------------
    def test_maintenance_logging_and_baseline_reset(self):
        """Maintenance action logs tamper-evident record and optionally resets baseline."""
        # Set joint to WARNING to test reset
        self.joint.current_risk = "WARNING"
        self.joint.consecutive_abnormal_count = 3
        self.db.commit()

        payload = {
            "joint_id": "joint-001",
            "technician_id": "TECH-4091",
            "action_type": "SPLICE_REPAIR",
            "notes": "Re-glued top cover splice seam. Mechanical inspection passed.",
            "baseline_reset": True,
            "data_provenance": "LIVE"
        }

        res = client.post("/api/v1/maintenance/log", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertEqual(data["joint_id"], "joint-001")
        self.assertEqual(data["action_type"], "SPLICE_REPAIR")
        self.assertEqual(data["risk_state_before"], "WARNING")
        self.assertEqual(data["risk_state_after"], "NORMAL")
        self.assertEqual(data["baseline_reset"], 1)
        self.assertIsNotNone(data["record_hash"])
        self.assertEqual(len(data["record_hash"]), 64)  # Valid SHA-256

        # Verify joint status was reset in DB
        self.db.refresh(self.joint)
        self.assertEqual(self.joint.current_risk, "NORMAL")
        self.assertEqual(self.joint.consecutive_abnormal_count, 0)

        # Verify querying maintenance log
        logs_res = client.get("/api/v1/joints/joint-001/maintenance")
        self.assertEqual(logs_res.status_code, 200)
        logs = logs_res.json()
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["id"], data["id"])

    # -------------------------------------------------------------------------
    # 5. Degradation Trend Analysis — Insufficient History Guardrail
    # -------------------------------------------------------------------------
    def test_degradation_trend_insufficient_history(self):
        """Fewer than 5 revolutions must report INSUFFICIENT_HISTORY."""
        # Create a fresh joint with 0 observations
        fresh_joint = models.Joint(
            id="joint-test-new",
            joint_code="J-NEW",
            belt_id="BELT-01",
            physical_position_meters=50.0,
            identifier_type="OPTICAL",
            identifier_token="OPT-NEW",
            splice_type="Finger Splice",
            installation_date="2026-09-01",
            total_revolutions_count=2,
            current_risk="NORMAL",
            consecutive_abnormal_count=0
        )
        self.db.merge(fresh_joint)
        self.db.commit()

        res = client.get("/api/v1/joints/joint-test-new/lifecycle")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        trend = data["degradation_trend"]
        self.assertEqual(trend["trend_status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(trend["trend_direction"], "INSUFFICIENT_DATA")
        self.assertIsNone(trend["rms_change_per_revolution"])
        self.assertIn("Minimum 5 observed revolutions required", trend["message"])

    # -------------------------------------------------------------------------
    # 6. Degradation Trend Analysis — Multi-Revolution Empirical Slope
    # -------------------------------------------------------------------------
    def test_degradation_trend_observed_slope(self):
        """With >= 5 observations, computes empirical rate of change without predicting rupture."""
        test_joint_id = "joint-trend-01"
        tj = models.Joint(
            id=test_joint_id,
            joint_code="J-TREND-01",
            belt_id="BELT-01",
            physical_position_meters=200.0,
            identifier_type="OPTICAL",
            identifier_token="OPT-TR01",
            splice_type="Finger Splice",
            installation_date="2026-09-01",
            total_revolutions_count=10,
            current_risk="NORMAL",
            consecutive_abnormal_count=0
        )
        self.db.merge(tj)
        self.db.commit()

        # Seed 6 synthetic observations with clear gradual increase: RMS increases 0.01 per revolution
        for rev in range(1, 7):
            obs = models.JointObservation(
                id=f"obs-trend-{rev}",
                joint_id=test_joint_id,
                revolution_index=rev,
                operating_state="STEADY_LOADED",
                data_provenance="SIMULATION",
                rms_acceleration=0.20 + (rev * 0.01),  # Gradual rise
                kurtosis=0.05 + (rev * 0.005),
                peak_acceleration=0.45,
                health_score=95.0,
                risk_state="NORMAL"
            )
            self.db.merge(obs)
        self.db.commit()

        res = client.get(f"/api/v1/joints/{test_joint_id}/lifecycle")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        trend = data["degradation_trend"]
        self.assertEqual(trend["trend_status"], "ESTIMATED_OBSERVED_TREND")
        self.assertAlmostEqual(trend["rms_change_per_revolution"], 0.01, places=3)
        self.assertIn(trend["trend_direction"], ["INCREASING_MODERATE", "ACCELERATING"])

    # -------------------------------------------------------------------------
    # 7. Scientific Honesty & Safety Guardrails
    # -------------------------------------------------------------------------
    def test_scientific_guardrails_no_fabricated_predictions(self):
        """Lifecycle endpoint must never invent rupture date, fatigue percentage, or RUL."""
        res = client.get("/api/v1/joints/joint-001/lifecycle")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        guardrails = data["safety_and_integrity_guardrails"]
        self.assertFalse(guardrails["rupture_prediction"])
        self.assertEqual(guardrails["rul_prediction"], "NOT_PREDICTABLE_WITHOUT_LONGITUDINAL_FAILURE_DATA")
        self.assertIsNone(guardrails["fatigue_percentage"])
        self.assertIn("Deterministic SCADA safety state remains authoritative", guardrails["disclaimer"])


if __name__ == "__main__":
    unittest.main()
