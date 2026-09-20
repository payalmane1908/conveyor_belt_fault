"""
Virtual Serial Telemetry Emitter (Development & Hardware Testing Utility)
Simulates an ESP32 sending real JSON telemetry frames over a serial COM port.
"""
import json
import time
import math
import argparse
from typing import List

def generate_burst_samples(sample_count: int, sampling_rate_hz: float, freq_hz: float = 28.0) -> List[float]:
    samples = []
    dt = 1.0 / sampling_rate_hz
    for i in range(sample_count):
        t = i * dt
        val = 1.2 * math.sin(2 * math.pi * freq_hz * t) + 0.3 * math.sin(2 * math.pi * 120.0 * t)
        samples.append(round(val, 6))
    return samples

def run_emitter(port: str, baudrate: int = 115200, delay_s: float = 1.0):
    try:
        import serial
    except ImportError:
        print("[ERROR] pyserial is not installed. Install with 'pip install pyserial' to run virtual serial emitter.")
        return

    print(f"[*] Opening serial port {port} at {baudrate} baud...")
    ser = serial.Serial(port, baudrate, timeout=1.0)
    seq = 1

    try:
        while True:
            samples = generate_burst_samples(sample_count=200, sampling_rate_hz=1000.0)
            packet = {
                "device_id": "esp32-node-01",
                "stream_id": "accel-z",
                "sensor_id": "SENS-ACCEL-01",
                "joint_id": "J-01",
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
            print(f"[TX] Sent burst seq={seq} ({len(samples)} samples) to {port}")
            seq += 1
            time.sleep(delay_s)
    except KeyboardInterrupt:
        print("[*] Emitter stopped by user.")
    finally:
        ser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Virtual Serial Telemetry Emitter")
    parser.add_argument("--port", default="COM4", help="Serial port to transmit to")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between bursts")
    args = parser.parse_args()
    run_emitter(args.port, args.baud, args.delay)
