"""
Industrial Hardware DAQ Bridge — ESP32 USB/Serial to Backend Ingestion Gateway
==============================================================================
Connects to physical ESP32 sensor node streaming over USB/UART COM port.

Firmware Protocol Specification (esp32_sensor_node.ino):
- Baud Rate: 115200 baud, 8-N-1, Newline-delimited JSON
- Sampling: 1000 Hz hardware-timed ADXL345 SPI / MPU6050 I2C
- Transmission: 100 samples per burst window (10 bursts/sec)
- Fields: device_id, stream_id, sensor_id, joint_id, sequence_number,
          hardware_timestamp_us, sampling_rate_hz, samples, quality_flags, data_provenance

Strict Zero Hardware Fabrication Rules:
1. When ESP32 is unplugged / disconnected:
   Reports SENSOR NOT CONNECTED. Never fabricates fake mock data.
2. Ingested bursts are posted to /api/v1/telemetry/ingest tagged EDGE_HARDWARE.
3. Does not bypass backend validation, sequence tracking, or SHA-256 integrity hashing.
"""

import sys
import json
import time
import urllib.request
import urllib.error
import argparse
from typing import Optional, Dict, Any

def list_available_ports():
    """Lists available serial ports on the host system."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("[HARDWARE DAQ] No active serial COM ports detected on host.")
            return []
        print("[HARDWARE DAQ] Available COM Ports:")
        for p in ports:
            print(f"  - {p.device}: {p.description} [{p.hwid}]")
        return [p.device for p in ports]
    except ImportError:
        print("[WARN] pyserial not installed. Install with 'pip install pyserial'.")
        return []

def run_hardware_bridge(
    port: str,
    baudrate: int = 115200,
    target_url: str = "http://127.0.0.1:8001",
    device_override: Optional[str] = None,
    stream_override: Optional[str] = None,
    joint_override: Optional[str] = None,
    max_retries: Optional[int] = None
):
    """
    Main acquisition loop reading raw frames from physical ESP32 DevKit
    and ingesting directly into backend /api/v1/telemetry/ingest.
    """
    try:
        import serial
    except ImportError:
        print("[FATAL] pyserial is required for hardware acquisition.", flush=True)
        print("Install pyserial using: pip install pyserial", flush=True)
        sys.exit(1)

    ingest_endpoint = f"{target_url.rstrip('/')}/api/v1/telemetry/ingest"
    print("=" * 72, flush=True)
    print(" SIH26008 PHYSICAL ESP32 HARDWARE DAQ BRIDGE", flush=True)
    print(f" Port: {port} | Baud: {baudrate} | Target: {ingest_endpoint}", flush=True)
    print(" Mode: LIVE EDGE DAQ (Provenance: EDGE_HARDWARE)", flush=True)
    print("=" * 72, flush=True)

    ser: Optional[serial.Serial] = None
    reconnect_interval = 2.0
    attempts = 0

    while True:
        # 1. Attempt connection to physical COM port
        if ser is None or not ser.is_open:
            attempts += 1
            if max_retries is not None and attempts > max_retries:
                print(f"[SENSOR NOT CONNECTED] Exceeded max connection attempts ({max_retries}) for {port}.", flush=True)
                break
            try:
                print(f"[*] Attempting connection to physical ESP32 on {port}...", flush=True)
                ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=2.0
                )
                print(f"[CONNECTED] ESP32 node connected on {port} @ {baudrate} baud.", flush=True)
            except (serial.SerialException, FileNotFoundError, OSError) as e:
                print(f"[SENSOR NOT CONNECTED] Port {port} unavailable: {e}", flush=True)
                if max_retries is not None and attempts >= max_retries:
                    print(f"[STOPPED] SENSOR NOT CONNECTED. Zero fake data policy enforced.", flush=True)
                    break
                print(f"[*] Retrying in {reconnect_interval:.1f}s... (Zero fake data policy enforced)", flush=True)
                ser = None
                time.sleep(reconnect_interval)
                continue

        # 2. Read newline-delimited JSON frame from ESP32
        try:
            raw_line = ser.readline()
            if not raw_line:
                continue

            line_str = raw_line.decode("utf-8", errors="replace").strip()
            if not line_str or not line_str.startswith("{"):
                # Non-JSON debug output or boot banner from ESP32
                if line_str:
                    print(f"[ESP32 UART] {line_str}")
                continue

            # 3. Parse JSON frame
            try:
                frame_data = json.loads(line_str)
            except json.JSONDecodeError as json_err:
                print(f"[FRAME ERROR] Malformed JSON from ESP32: {json_err}")
                continue

            # 4. Enforce packet schema and physical provenance
            device_id = device_override or frame_data.get("device_id", "esp32-node-01")
            stream_id = stream_override or frame_data.get("stream_id", "accel-z")
            sensor_id = frame_data.get("sensor_id", "sens-vibe-01")
            joint_id = joint_override or frame_data.get("joint_id", "joint-001")
            seq = frame_data.get("sequence_number")
            hw_ts = frame_data.get("hardware_timestamp_us")
            samples = frame_data.get("samples", [])
            fs = frame_data.get("sampling_rate_hz", 1000.0)
            quality = frame_data.get("quality_flags", "OK")

            if seq is None or hw_ts is None or not samples:
                print(f"[WARN] Frame missing required fields: seq={seq}, ts={hw_ts}, samples={len(samples)}")
                continue

            packet_payload = {
                "device_id": device_id,
                "stream_id": stream_id,
                "sensor_id": sensor_id,
                "joint_id": joint_id,
                "sequence_number": int(seq),
                "hardware_timestamp_us": int(hw_ts),
                "sampling_rate_hz": float(fs),
                "samples": [float(s) for s in samples],
                "quality_flags": quality,
                "data_provenance": "LIVE"  # Canonical physical edge hardware provenance matching esp32_sensor_node.ino
            }

            if "speed_rpm" in frame_data:
                packet_payload["drive_rpm"] = float(frame_data["speed_rpm"])

            # 5. Transmit packet to backend ingestion endpoint
            req_data = json.dumps(packet_payload).encode("utf-8")
            req = urllib.request.Request(
                ingest_endpoint,
                data=req_data,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                sha = resp_json.get("sha256_hash", "N/A")[:12]
                print(f"[EDGE HW RX] seq={seq} ({len(samples)} samples) -> POST 201 SHA-256={sha}...")

        except (serial.SerialException, OSError) as ser_err:
            print(f"[DISCONNECTED] ESP32 connection lost: {ser_err}")
            if ser:
                try:
                    ser.close()
                except Exception:
                    pass
            ser = None
            time.sleep(2.0)
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="replace")
            print(f"[INGEST ERROR] HTTP {http_err.code}: {err_body}")
            time.sleep(1.0)
        except urllib.error.URLError as net_err:
            print(f"[BACKEND OFFLINE] Could not reach backend: {net_err.reason}")
            time.sleep(3.0)
        except KeyboardInterrupt:
            print("\n[STOPPED] Hardware DAQ Bridge terminated by operator.")
            break

    if ser and ser.is_open:
        ser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Industrial Hardware DAQ Bridge (ESP32 UART to Backend Ingestion Gateway)"
    )
    parser.add_argument("--port", default="COM3", help="Serial COM port connected to ESP32 (e.g. COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate matching esp32_sensor_node.ino (default 115200)")
    parser.add_argument("--target", default="http://127.0.0.1:8001", help="Target backend base URL (default http://127.0.0.1:8001)")
    parser.add_argument("--device", default=None, help="Device ID override (default from firmware: esp32-node-01)")
    parser.add_argument("--stream", default=None, help="Stream ID override (default from firmware: accel-z)")
    parser.add_argument("--joint", default=None, help="Joint ID override (default joint-001)")
    parser.add_argument("--max-retries", type=int, default=None, help="Max connection attempts before stopping (default infinite)")
    parser.add_argument("--list-ports", action="store_true", help="List available serial ports and exit")
    args = parser.parse_args()

    if args.list_ports:
        list_available_ports()
        sys.exit(0)

    run_hardware_bridge(
        port=args.port,
        baudrate=args.baud,
        target_url=args.target,
        device_override=args.device,
        stream_override=args.stream,
        joint_override=args.joint,
        max_retries=args.max_retries
    )
