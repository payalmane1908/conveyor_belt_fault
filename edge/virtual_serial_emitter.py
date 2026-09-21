"""
Virtual Telemetry Emitter (Development, Test Rig & Hardware DAQ Testing Utility)
================================================================================
Simulates synthetic telemetry packets for pipeline validation.

Supported Modes:
1. Serial Mode (--mode serial):
   Transmits JSON packets over a virtual or physical COM port.
2. HTTP Mode (--mode http):
   Sends validated telemetry directly to the backend ingestion endpoint:
   POST /api/v1/telemetry/simulate
   with strict data_provenance="SIMULATION".
   Automatically synchronizes sequence counter with the backend StreamTracker
   to prevent HTTP 409 sequence conflicts.
"""

import sys
import json
import time
import math
import urllib.request
import urllib.error
import argparse
from typing import List, Optional

def generate_burst_samples(sample_count: int, sampling_rate_hz: float, freq_hz: float = 50.0) -> List[float]:
    """Generates synthetic sinusoidal vibration samples (50 Hz fundamental + harmonics)."""
    samples = []
    dt = 1.0 / sampling_rate_hz
    for i in range(sample_count):
        t = i * dt
        val = 1.2 * math.sin(2 * math.pi * freq_hz * t) + 0.3 * math.sin(2 * math.pi * 120.0 * t)
        samples.append(round(val, 6))
    return samples

def get_backend_sequence(target_url: str, device_id: str, stream_id: str) -> int:
    """Queries backend StreamTracker via /api/v1/system/status to avoid sequence conflicts (HTTP 409)."""
    status_url = f"{target_url.rstrip('/')}/api/v1/system/status"
    try:
        req = urllib.request.Request(status_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                for s in data.get("active_streams", []):
                    if s.get("device_id") == device_id and s.get("stream_id") == stream_id:
                        return s.get("last_sequence_number", 0) + 1
    except Exception:
        pass
    return 1

def run_http_emitter(
    target_url: str,
    device_id: str = "test-rig-simulator-01",
    stream_id: str = "sim-accel-z",
    sensor_id: str = "sim-accel-p3-01",
    joint_id: str = "joint-001",
    delay_s: float = 1.0,
    burst_count: Optional[int] = None
):
    """Transmits synthetic bursts over HTTP to /api/v1/telemetry/simulate with SIMULATION provenance."""
    endpoint = f"{target_url.rstrip('/')}/api/v1/telemetry/simulate"
    print(f"[*] Starting Virtual HTTP Telemitter targeting: {endpoint}")
    print(f"[*] Identity: device='{device_id}', stream='{stream_id}', sensor='{sensor_id}'")
    print(f"[*] Provenance: SIMULATION (Strictly isolated from physical hardware)")

    seq = get_backend_sequence(target_url, device_id, stream_id)
    print(f"[*] Initial synchronized sequence number: {seq}")

    sent = 0
    try:
        while burst_count is None or sent < burst_count:
            samples = generate_burst_samples(sample_count=200, sampling_rate_hz=1000.0)
            hw_ts = int(time.time() * 1_000_000) % 4_294_967_296

            packet = {
                "device_id": device_id,
                "stream_id": stream_id,
                "sensor_id": sensor_id,
                "joint_id": joint_id,
                "sequence_number": seq,
                "hardware_timestamp_us": hw_ts,
                "sampling_rate_hz": 1000.0,
                "samples": samples,
                "quality_flags": "OK",
                "data_provenance": "SIMULATION"
            }

            payload_bytes = json.dumps(packet).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=payload_bytes,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    resp_body = json.loads(resp.read().decode("utf-8"))
                    sha256 = resp_body.get("sha256_hash", "N/A")[:12]
                    print(f"[HTTP 201] Sent burst seq={seq} (200 samples) -> SHA-256={sha256}...")
                    seq += 1
                    sent += 1
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8", errors="replace")
                print(f"[ERROR] HTTP {e.code}: {err_text}")
                if e.code == 409:
                    print("[*] Resynchronizing sequence counter with backend...")
                    seq = get_backend_sequence(target_url, device_id, stream_id)
                time.sleep(2.0)
            except urllib.error.URLError as e:
                print(f"[ERROR] Connection failed: {e.reason}. Ensure backend is running.")
                time.sleep(3.0)

            time.sleep(delay_s)

    except KeyboardInterrupt:
        print("\n[*] Virtual HTTP emitter stopped by user.")

def run_serial_emitter(port: str, baudrate: int = 115200, delay_s: float = 1.0):
    """Transmits simulated telemetry frames over a serial COM port."""
    try:
        import serial
    except ImportError:
        print("[ERROR] pyserial is not installed. Install with 'pip install pyserial' to run serial emitter.")
        return

    print(f"[*] Opening serial port {port} at {baudrate} baud...")
    try:
        ser = serial.Serial(port, baudrate, timeout=1.0)
    except serial.SerialException as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        return

    seq = 1
    try:
        while True:
            samples = generate_burst_samples(sample_count=200, sampling_rate_hz=1000.0)
            packet = {
                "device_id": "test-rig-simulator-01",
                "stream_id": "sim-accel-z",
                "sensor_id": "sim-accel-p3-01",
                "joint_id": "joint-001",
                "sequence_number": seq,
                "hardware_timestamp_us": int(time.time() * 1_000_000) % 4_294_967_296,
                "sampling_rate_hz": 1000.0,
                "samples": samples,
                "quality_flags": "OK",
                "data_provenance": "SIMULATION"
            }
            line = (json.dumps(packet) + "\n").encode("utf-8")
            ser.write(line)
            ser.flush()
            print(f"[TX] Sent serial burst seq={seq} ({len(samples)} samples) to {port}")
            seq += 1
            time.sleep(delay_s)
    except KeyboardInterrupt:
        print("\n[*] Serial emitter stopped by user.")
    finally:
        ser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Virtual Telemetry Emitter (Serial & HTTP Modes)")
    parser.add_argument("--mode", choices=["serial", "http"], default="serial", help="Emission transport mode")
    parser.add_argument("--port", default="COM4", help="Serial COM port (for serial mode)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (for serial mode)")
    parser.add_argument("--target", default="http://127.0.0.1:8001", help="Target backend URL (for http mode)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between bursts")
    parser.add_argument("--count", type=int, default=None, help="Number of bursts to send (None = continuous)")
    args = parser.parse_args()

    if args.mode == "http":
        run_http_emitter(args.target, delay_s=args.delay, burst_count=args.count)
    else:
        run_serial_emitter(args.port, args.baud, args.delay)
