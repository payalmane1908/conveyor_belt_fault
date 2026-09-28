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

from main import app
from app.database import SessionLocal, init_db, engine
from app import models, schemas

class TestPhase2WebSocketAndSCADA(unittest.TestCase):
    def setUp(self):
        """Clean database and seed devices/sensors before tests."""
        init_db()
        db = SessionLocal()
        db.query(models.RawVibrationBurst).delete()
        db.query(models.StreamTracker).delete()
        db.query(models.SensorAttachment).delete()
        db.query(models.Joint).delete()
        db.query(models.Belt).delete()
        db.query(models.Sensor).delete()
        db.query(models.Conveyor).delete()
        db.query(models.Device).delete()
        db.commit()

        # Seed trusted device
        dev = models.Device(
            id="esp32-node-01",
            name="ESP32 Live Node",
            device_type="ESP32",
            serial_number="ESP32-LIVE-001",
            is_trusted_hardware=1,
            status="ACTIVE"
        )
        sim_dev = models.Device(
            id="test-rig-simulator-01",
            name="Simulator Rig",
            device_type="TEST_RIG_EMULATOR",
            is_trusted_hardware=0,
            status="ACTIVE"
        )
        sensor = models.Sensor(
            id="SENS-ACCEL-01",
            sensor_type="ACCELEROMETER",
            model_number="ADXL345-IND",
            sampling_rate_hz=1000.0,
            output_protocol="SPI",
            status="ACTIVE"
        )
        db.add_all([dev, sim_dev, sensor])
        db.commit()
        db.close()

    # ----------------------------------------------------------------------
    # 1. Honest Snapshot Endpoint Test (No Fake Numbers)
    # ----------------------------------------------------------------------
    def test_snapshot_empty_state(self):
        """When no telemetry has arrived, snapshot must return NO ACTIVE STREAM and null burst."""
        with TestClient(app) as client:
            res = client.get("/api/v1/telemetry/snapshot")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["hardware_stream_state"], "NO ACTIVE STREAM")
            self.assertIsNone(data["latest_burst"])
            self.assertEqual(len(data["active_streams"]), 0)

    # ----------------------------------------------------------------------
    # 2. WebSocket Handshake & Ping Test
    # ----------------------------------------------------------------------
    def test_websocket_handshake_and_ping(self):
        """WebSocket connection must succeed, receive initial message, and respond to ping."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/v1/live-telemetry") as ws:
                init_msg = ws.receive_json()
                self.assertEqual(init_msg["type"], "CONNECTION_ESTABLISHED")

                # Test text ping/pong heartbeat
                ws.send_text("ping")
                resp = ws.receive_text()
                self.assertEqual(resp, "pong")

                # Test JSON ping
                ws.send_json({"action": "ping", "timestamp": 123456})
                pong_msg = ws.receive_json()
                self.assertEqual(pong_msg["type"], "PONG")
                self.assertEqual(pong_msg["client_time"], 123456)

    # ----------------------------------------------------------------------
    # 3. WebSocket Real-Time Telemetry Broadcast Test (LIVE)
    # ----------------------------------------------------------------------
    def test_websocket_broadcast_live_burst(self):
        """Live telemetry ingestion must broadcast exact payload over WebSocket."""
        test_samples = [0.15, -0.32, 0.48, -0.05]
        canonical_bytes = struct.pack("<4d", *test_samples)
        expected_hash = hashlib.sha256(canonical_bytes).hexdigest()

        with TestClient(app) as client:
            with client.websocket_connect("/ws/v1/live-telemetry") as ws:
                ws.receive_json() # consume connection message

                # Ingest live burst
                payload = {
                    "device_id": "esp32-node-01",
                    "stream_id": "accel-z",
                    "sensor_id": "SENS-ACCEL-01",
                    "sequence_number": 1,
                    "hardware_timestamp_us": 1000000,
                    "sampling_rate_hz": 1000.0,
                    "samples": test_samples,
                    "quality_flags": "OK",
                    "data_provenance": "LIVE"
                }
                res = client.post("/api/v1/telemetry/ingest", json=payload)
                self.assertEqual(res.status_code, 201)

                # Receive WebSocket broadcast
                msg = ws.receive_json()
                self.assertEqual(msg["type"], "TELEMETRY_BURST")
                self.assertEqual(msg["device_id"], "esp32-node-01")
                self.assertEqual(msg["stream_id"], "accel-z")
                self.assertEqual(msg["sequence_number"], 1)
                self.assertEqual(msg["data_provenance"], "LIVE")
                self.assertEqual(msg["sha256_hash"], expected_hash)
                self.assertEqual(msg["sampling_rate_hz"], 1000.0)
                self.assertEqual(len(msg["samples"]), 4)
                for orig, rec in zip(test_samples, msg["samples"]):
                    self.assertAlmostEqual(orig, rec, places=6)

    # ----------------------------------------------------------------------
    # 4. Simulation Broadcast & Provenance Preservation
    # ----------------------------------------------------------------------
    def test_websocket_broadcast_sim_burst(self):
        """Simulation generator must emit SIMULATION burst with 50 Hz test frequency at 1000 Hz sample rate."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/v1/live-telemetry") as ws:
                ws.receive_json() # connection msg

                # Trigger simulation burst
                res = client.post(
                    "/api/v1/telemetry/simulate/generate-burst?sensor_id=SENS-ACCEL-01&sampling_rate_hz=1000.0&fundamental_freq_hz=50.0"
                )
                self.assertEqual(res.status_code, 201)

                msg = ws.receive_json()
                self.assertEqual(msg["type"], "TELEMETRY_BURST")
                self.assertEqual(msg["data_provenance"], "SIMULATION")
                self.assertEqual(msg["sampling_rate_hz"], 1000.0)
                self.assertEqual(len(msg["samples"]), 500)

    # ----------------------------------------------------------------------
    # 5. Static File Root Routing Order Test
    # ----------------------------------------------------------------------
    def test_static_and_api_route_ordering(self):
        """Root GET / must serve index.html without intercepting /api or /ws."""
        with TestClient(app) as client:
            root_res = client.get("/")
            self.assertEqual(root_res.status_code, 200)
            # Accept either the React SPA title (production build) or the legacy
            # static HMI title, whichever is currently mounted.
            self.assertTrue(
                "CONVEYOR SCADA" in root_res.text or
                "Conveyor Belt Joint Telemetry SCADA" in root_res.text,
                "Root / must serve a SCADA index.html (React build or legacy static HMI)"
            )

            # API still reachable
            api_res = client.get("/api/v1/system/status")
            self.assertEqual(api_res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
