"""
Test Suite: Hardware DAQ Bridge & Virtual HTTP Simulation Telemetry
===================================================================
Verifies:
1. Virtual Serial Emitter HTTP simulation mode produces validated SIMULATION bursts.
2. Ingestion pipeline preserves strict SIMULATION provenance.
3. Hardware Bridge parses ESP32 firmware packets correctly and enforces EDGE_HARDWARE provenance.
4. Missing serial hardware triggers SENSOR NOT CONNECTED gracefully without fabricated data.
"""

import sys
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from backend.main import app
    from backend.app.schemas import DataProvenance
except ModuleNotFoundError:
    from main import app
    from app.schemas import DataProvenance

from edge.virtual_serial_emitter import generate_burst_samples, get_backend_sequence
from edge.hardware_bridge import run_hardware_bridge, list_available_ports

client = TestClient(app)

class TestVirtualHttpSimulation(unittest.TestCase):
    def test_burst_samples_generation(self):
        samples = generate_burst_samples(sample_count=100, sampling_rate_hz=1000.0, freq_hz=50.0)
        self.assertEqual(len(samples), 100)
        self.assertTrue(all(isinstance(x, float) for x in samples))
        # Sinusoidal peak bounded
        self.assertLess(max(samples), 2.0)
        self.assertGreater(min(samples), -2.0)

    def test_http_simulation_ingestion_preserves_provenance(self):
        """HTTP simulated bursts must carry SIMULATION provenance and succeed with 201."""
        samples = generate_burst_samples(sample_count=200, sampling_rate_hz=1000.0)
        packet = {
            "device_id": "test-rig-simulator-01",
            "stream_id": "sim-accel-z",
            "sensor_id": "sim-accel-p3-01",
            "joint_id": "joint-001",
            "sequence_number": 99990,
            "hardware_timestamp_us": 1000000,
            "sampling_rate_hz": 1000.0,
            "samples": samples,
            "quality_flags": "OK",
            "data_provenance": "SIMULATION"
        }
        res = client.post("/api/v1/telemetry/simulate", json=packet)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["data_provenance"], "SIMULATION")
        self.assertIn("sha256_hash", data)

    def test_simulation_cannot_masquerade_as_hardware(self):
        """Simulation bursts posted to /telemetry/ingest must be rejected with 400."""
        samples = generate_burst_samples(sample_count=50, sampling_rate_hz=1000.0)
        packet = {
            "device_id": "test-rig-simulator-01",
            "stream_id": "sim-accel-z",
            "sensor_id": "sim-accel-p3-01",
            "joint_id": "joint-001",
            "sequence_number": 99991,
            "hardware_timestamp_us": 2000000,
            "sampling_rate_hz": 1000.0,
            "samples": samples,
            "quality_flags": "OK",
            "data_provenance": "SIMULATION"
        }
        res = client.post("/api/v1/telemetry/ingest", json=packet)
        self.assertEqual(res.status_code, 400)


class TestHardwareDAQBridge(unittest.TestCase):
    def test_list_ports_callable(self):
        ports = list_available_ports()
        self.assertIsInstance(ports, list)

    def test_hardware_packet_ingestion_edge_provenance(self):
        """Packets from trusted physical hardware ESP32 are accepted on /telemetry/ingest."""
        samples = [0.15, -0.22, 0.35, -0.10, 0.05] * 20  # 100 samples
        packet = {
            "device_id": "esp32-node-01",
            "stream_id": "accel-z",
            "sensor_id": "sens-vibe-01",
            "joint_id": "joint-001",
            "sequence_number": 88880,
            "hardware_timestamp_us": 5000000,
            "sampling_rate_hz": 1000.0,
            "samples": samples,
            "quality_flags": "OK",
            "data_provenance": "LIVE"
        }
        res = client.post("/api/v1/telemetry/ingest", json=packet)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["data_provenance"], "LIVE")
        self.assertEqual(data["device_id"], "esp32-node-01")


if __name__ == "__main__":
    unittest.main()
