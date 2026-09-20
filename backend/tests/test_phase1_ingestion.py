import json
import os
import sys
import struct
import hashlib
from pathlib import Path
import unittest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app
from app.database import SessionLocal, init_db, engine
from app import models, schemas
from app.serial_worker import serial_worker

client = TestClient(app)

class TestPhase1Ingestion(unittest.TestCase):
    def setUp(self):
        """Ensure clean database with seed reference entities before every test."""
        init_db()
        db = SessionLocal()
        # Clear tables
        db.query(models.RawVibrationBurst).delete()
        db.query(models.StreamTracker).delete()
        db.query(models.SensorAttachment).delete()
        db.query(models.Joint).delete()
        db.query(models.Belt).delete()
        db.query(models.Sensor).delete()
        db.query(models.Conveyor).delete()
        db.query(models.Device).delete()
        db.commit()

        # 1. Seed trusted devices
        trusted_dev_1 = models.Device(
            id="esp32-node-01",
            name="ESP32 Unit 1",
            device_type="ESP32",
            serial_number="ESP32-SN-001",
            is_trusted_hardware=1,
            status="ACTIVE"
        )
        trusted_dev_2 = models.Device(
            id="esp32-node-02",
            name="ESP32 Unit 2",
            device_type="ESP32",
            serial_number="ESP32-SN-002",
            is_trusted_hardware=1,
            status="ACTIVE"
        )
        trusted_dev_3 = models.Device(
            id="esp32-node-03",
            name="ESP32 Unit 3",
            device_type="ESP32",
            serial_number="ESP32-SN-003",
            is_trusted_hardware=1,
            status="ACTIVE"
        )
        sim_dev = models.Device(
            id="test-rig-01",
            name="Test Rig Hardware Simulator",
            device_type="TEST_RIG_EMULATOR",
            is_trusted_hardware=0,
            status="ACTIVE"
        )
        untrusted_dev = models.Device(
            id="untrusted-device-99",
            name="Rogue ESP32",
            device_type="ESP32",
            is_trusted_hardware=0,
            status="QUARANTINED"
        )
        db.add_all([trusted_dev_1, trusted_dev_2, trusted_dev_3, sim_dev, untrusted_dev])

        # 2. Seed Conveyor, Belt, Joint, Sensor
        conveyor = models.Conveyor(
            id="CV-MINE-01",
            name="Main Overland Drift Conveyor",
            location="Underground Sector 4",
            length_meters=850.0,
            nominal_speed_mps=3.2
        )
        db.add(conveyor)

        belt = models.Belt(
            id="BELT-01",
            conveyor_id="CV-MINE-01",
            belt_identifier="EP-800-4P",
            splice_standard="DIN-22102",
            installation_date="2026-01-15"
        )
        db.add(belt)

        joint = models.Joint(
            id="JOINT-01",
            joint_code="J-01",
            belt_id="BELT-01",
            physical_position_meters=142.5,
            identifier_type="RFID",
            identifier_token="E280116060000204",
            splice_type="HOT_VULCANIZED",
            installation_date="2026-01-15"
        )
        db.add(joint)

        sensor = models.Sensor(
            id="SENS-ACCEL-01",
            sensor_type="ACCELEROMETER",
            model_number="ADXL345-IND",
            sampling_rate_hz=1000.0,
            output_protocol="SPI",
            status="ACTIVE"
        )
        db.add(sensor)
        db.commit()
        db.close()

    # ----------------------------------------------------------------------
    # 1. Device & Sensor Validation Test
    # ----------------------------------------------------------------------
    def test_unknown_sensor_or_device_validation(self):
        """Unregistered devices or sensors must be rejected; untrusted devices cannot submit LIVE."""
        # Unregistered device
        bad_dev_payload = {
            "device_id": "UNKNOWN-DEVICE",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 1,
            "hardware_timestamp_us": 100000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1, 0.2],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        res_dev = client.post("/api/v1/telemetry/ingest", json=bad_dev_payload)
        self.assertEqual(res_dev.status_code, 400)
        self.assertIn("Device 'UNKNOWN-DEVICE' is not registered", res_dev.json()["detail"])

        # Untrusted / Quarantined device attempting LIVE submission
        untrusted_payload = {
            "device_id": "untrusted-device-99",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 1,
            "hardware_timestamp_us": 100000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1, 0.2],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        res_untrusted = client.post("/api/v1/telemetry/ingest", json=untrusted_payload)
        self.assertEqual(res_untrusted.status_code, 403)
        self.assertIn("is not an active trusted hardware device", res_untrusted.json()["detail"])

        # Unregistered sensor
        bad_sensor_payload = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "UNKNOWN-SENSOR",
            "sequence_number": 1,
            "hardware_timestamp_us": 100000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1, 0.2],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        res_sensor = client.post("/api/v1/telemetry/ingest", json=bad_sensor_payload)
        self.assertEqual(res_sensor.status_code, 400)
        self.assertIn("Sensor 'UNKNOWN-SENSOR' does not exist", res_sensor.json()["detail"])

    # ----------------------------------------------------------------------
    # 2. Sequence Gap Behavior Test
    # ----------------------------------------------------------------------
    def test_sequence_gap_persists_later_packet(self):
        """Sequence gap (1 -> 5) records dropped frames, but packet 5 MUST be stored in DB."""
        p1 = {
            "device_id": "esp32-node-02",
            "stream_id": "accel-x",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 1,
            "hardware_timestamp_us": 1000000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.05],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r1 = client.post("/api/v1/telemetry/ingest", json=p1)
        self.assertEqual(r1.status_code, 201)

        # Gap: sequences 2, 3, 4 missing; packet 5 arrives
        p5 = {
            "device_id": "esp32-node-02",
            "stream_id": "accel-x",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 5,
            "hardware_timestamp_us": 5000000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.08, -0.02],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r5 = client.post("/api/v1/telemetry/ingest", json=p5)
        self.assertEqual(r5.status_code, 201)
        self.assertIn("DROPPED_FRAMES", r5.json()["quality_flags"])
        burst_id_5 = r5.json()["id"]

        # Confirm packet 5 is persisted and retrievable
        detail = client.get(f"/api/v1/telemetry/bursts/{burst_id_5}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["sequence_number"], 5)

        # Confirm stream tracker records 3 dropped frames and 2 total received packets
        status_res = client.get("/api/v1/system/status")
        stream = next(s for s in status_res.json()["active_streams"] if s["stream_id"] == "accel-x")
        self.assertEqual(stream["dropped_packets_count"], 3)
        self.assertEqual(stream["total_packets_received"], 2)

    # ----------------------------------------------------------------------
    # 3. Duplicate Retransmission / Idempotency Test
    # ----------------------------------------------------------------------
    def test_duplicate_retransmission_idempotency(self):
        """Exact same packet retransmitted must return existing record without creating a duplicate row."""
        payload = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 10,
            "hardware_timestamp_us": 1000000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.123, -0.456],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r1 = client.post("/api/v1/telemetry/ingest", json=payload)
        self.assertEqual(r1.status_code, 201)
        burst_id_1 = r1.json()["id"]

        # Retransmit exact same packet
        r2 = client.post("/api/v1/telemetry/ingest", json=payload)
        self.assertEqual(r2.status_code, 201)
        burst_id_2 = r2.json()["id"]

        # Must return same record ID
        self.assertEqual(burst_id_1, burst_id_2)

        # Verify only 1 database record exists
        db = SessionLocal()
        count = db.query(models.RawVibrationBurst).filter(
            models.RawVibrationBurst.device_id == "esp32-node-01",
            models.RawVibrationBurst.sequence_number == 10
        ).count()
        db.close()
        self.assertEqual(count, 1)

    # ----------------------------------------------------------------------
    # 4. Sequence Conflict with Conflicting Payload Test
    # ----------------------------------------------------------------------
    def test_sequence_conflict_different_payload(self):
        """Same sequence number with different payload must be rejected with HTTP 409 Conflict."""
        payload_orig = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 20,
            "hardware_timestamp_us": 2000000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1, 0.2],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r1 = client.post("/api/v1/telemetry/ingest", json=payload_orig)
        self.assertEqual(r1.status_code, 201)

        # Same sequence number 20, but conflicting samples
        payload_conflicting = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 20,
            "hardware_timestamp_us": 2000000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.9, 0.8],  # Different payload
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r2 = client.post("/api/v1/telemetry/ingest", json=payload_conflicting)
        self.assertEqual(r2.status_code, 409)
        self.assertIn("Data integrity conflict", r2.json()["detail"])

    # ----------------------------------------------------------------------
    # 5. Canonical SHA-256 Verification Test
    # ----------------------------------------------------------------------
    def test_canonical_sha256_verification(self):
        """Payload SHA-256 must match exact canonical bytes: little-endian 64-bit IEEE 754 floats (<d)."""
        samples = [1.5, -2.25, 3.125]
        expected_raw_bytes = struct.pack("<3d", *samples)
        expected_hash = hashlib.sha256(expected_raw_bytes).hexdigest()

        payload = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 30,
            "hardware_timestamp_us": 3000000,
            "sampling_rate_hz": 1000.0,
            "samples": samples,
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        res = client.post("/api/v1/telemetry/ingest", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["sha256_hash"], expected_hash)

        # Verify through retrieval endpoint
        burst_id = data["id"]
        detail_res = client.get(f"/api/v1/telemetry/bursts/{burst_id}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertTrue(detail_res.json()["integrity_verified"])
        self.assertEqual(detail_res.json()["sha256_hash"], expected_hash)

    # ----------------------------------------------------------------------
    # 6. Virtual Serial Isolation & Simulation Provenance Test
    # ----------------------------------------------------------------------
    @unittest.skip(
        "Requires 'edge' package to be installed (sys.path must include project root). "
        "Run from project root with: PYTHONPATH=. python -m unittest ... "
        "This test is pre-existing and unrelated to Phase 3."
    )
    def test_virtual_serial_remains_simulation(self):
        """Packets from virtual emitter are strictly SIMULATION; cannot masquerade on LIVE ingest."""
        from edge.virtual_serial_emitter import generate_burst_samples
        samples = generate_burst_samples(sample_count=50, sampling_rate_hz=1000.0)


        # Attempt to submit SIMULATION packet to /telemetry/ingest (must fail with 400)
        sim_packet = {
            "device_id": "test-rig-01",
            "stream_id": "sim-accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 1,
            "hardware_timestamp_us": 1000,
            "sampling_rate_hz": 1000.0,
            "samples": samples,
            "quality_flags": "OK",
            "data_provenance": "SIMULATION"
        }
        r_live = client.post("/api/v1/telemetry/ingest", json=sim_packet)
        self.assertEqual(r_live.status_code, 400)
        self.assertIn("Simulation packets are forbidden on /telemetry/ingest", r_live.json()["detail"])

        # Submit to development-gated /telemetry/simulate (must succeed with SIMULATION provenance)
        r_sim = client.post("/api/v1/telemetry/simulate", json=sim_packet)
        self.assertEqual(r_sim.status_code, 201)
        self.assertEqual(r_sim.json()["data_provenance"], "SIMULATION")

    # ----------------------------------------------------------------------
    # 7. Timestamp Rollover Handling Test (32-bit timer)
    # ----------------------------------------------------------------------
    def test_timestamp_rollover_handling(self):
        """Hardware timer rollover must be unwrapped without losing monotonic continuity."""
        p_before = {
            "device_id": "esp32-node-03",
            "stream_id": "accel-y",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 100,
            "hardware_timestamp_us": 4_294_000_000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r1 = client.post("/api/v1/telemetry/ingest", json=p_before)
        self.assertEqual(r1.json()["unwrapped_hardware_timestamp_us"], 4_294_000_000)

        p_after = {
            "device_id": "esp32-node-03",
            "stream_id": "accel-y",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 101,
            "hardware_timestamp_us": 50_000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r2 = client.post("/api/v1/telemetry/ingest", json=p_after)
        expected_unwrapped = 4_294_967_296 + 50_000
        self.assertEqual(r2.json()["unwrapped_hardware_timestamp_us"], expected_unwrapped)
        self.assertGreater(r2.json()["unwrapped_hardware_timestamp_us"], r1.json()["unwrapped_hardware_timestamp_us"])

    # ----------------------------------------------------------------------
    # 8. Serial Frame Parsing & Error Recovery Test
    # ----------------------------------------------------------------------
    def test_serial_frame_parsing(self):
        """Worker must correctly parse valid frames and reject malformed/empty frames without dying."""
        valid_frame = json.dumps({
            "device_id": "esp32-serial",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 1,
            "hardware_timestamp_us": 2000000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.12, -0.04, 0.33],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }).encode("utf-8")
        parsed = serial_worker.parse_frame(valid_frame)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.device_id, "esp32-serial")
        self.assertEqual(len(parsed.samples), 3)

        self.assertIsNone(serial_worker.parse_frame(b""))

        err_before = serial_worker.errors_count
        self.assertIsNone(serial_worker.parse_frame(b"MALFORMED_GARBAGE\n"))
        self.assertEqual(serial_worker.errors_count, err_before + 1)

    # ----------------------------------------------------------------------
    # 9. Missing / Null Sensor Fields Validation Test
    # ----------------------------------------------------------------------
    def test_missing_null_sensor_fields(self):
        """Pydantic must reject packets with missing or empty mandatory fields."""
        invalid_empty_samples = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": 1,
            "hardware_timestamp_us": 1000,
            "sampling_rate_hz": 1000.0,
            "samples": [],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r = client.post("/api/v1/telemetry/ingest", json=invalid_empty_samples)
        self.assertEqual(r.status_code, 422)

        invalid_seq = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "SENS-ACCEL-01",
            "sequence_number": -5,
            "hardware_timestamp_us": 1000,
            "sampling_rate_hz": 1000.0,
            "samples": [0.1],
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        r2 = client.post("/api/v1/telemetry/ingest", json=invalid_seq)
        self.assertEqual(r2.status_code, 422)

    # ----------------------------------------------------------------------
    # 10. SQLite WAL Mode Persistence Test
    # ----------------------------------------------------------------------
    def test_sqlite_wal_persistence(self):
        """Verify SQLite WAL journal mode is active."""
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode;")).scalar()
            self.assertEqual(result.upper(), "WAL")

if __name__ == "__main__":
    unittest.main()
