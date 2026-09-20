# ESP32 Edge Ingestion Firmware Specification
## Conveyor Belt Joint Health & Failure Prevention System

### 1. Serial Protocol Overview
- **Baud Rate**: `115200` (configurable up to `921600` for high-throughput multi-channel bursts)
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Framing**: Newline-delimited JSON (`\n`) or COBS-encoded binary frame

### 2. JSON Frame Format
Each raw vibration burst captured during joint passage (or continuous monitoring) is transmitted as a single line:

```json
{
  "device_id": "esp32-conveyor-node-01",
  "stream_id": "accel-z",
  "sensor_id": "SENS-ACCEL-01",
  "joint_id": "J-01",
  "sequence_number": 1042,
  "hardware_timestamp_us": 184523910,
  "sampling_rate_hz": 1000.0,
  "samples": [0.042, 0.081, -0.015, 0.120, -0.095],
  "quality_flags": "OK",
  "data_provenance": "LIVE"
}
```

### 3. Key Firmware Rules
1. **Monotonic Sequence Numbers**: The ESP32 must increment `sequence_number` by `1` for every transmitted burst on a given `stream_id`. Never reuse sequence numbers.
2. **Hardware Microsecond Timestamps**: Use `esp_timer_get_time()` (64-bit microseconds) or `micros()` (32-bit microseconds). The backend handles 32-bit rollover automatically.
3. **Trigger Synchronization**:
   - When the RFID reader (RC522) or magnetic Hall sensor trips, the ESP32 notes the passage event and populates `joint_id` with the detected joint code.
   - The burst window begins after the configured physical offset delay ($t_{\text{delay}} = \frac{d_{\text{offset}}}{v}$).
4. **Quality Flags**:
   - `OK`: Clean acquisition.
   - `CLIPPED`: Accelerometer exceeded full-scale range ($\pm 16g$).
   - `NOISY`: Excessive electrical interference detected on ADC.
5. **Data Provenance**:
   - Must be strictly set to `"LIVE"`. Packets from real firmware must never use `"SIMULATION"`.
