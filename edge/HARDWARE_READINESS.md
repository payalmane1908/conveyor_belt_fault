# Hardware Readiness Audit (Stage 5A)
**Project:** Conveyor Belt Joint Rupture & Damage Monitoring System (SIH Hardware Prototype)  
**Date:** September 2026  
**Status:** Audit Complete — Zero Hardware Fabrication Policy Enforced  

---

## 1. Executive Summary

This document establishes the empirical boundary between the **validated software/DSP/ML pipeline** and the **physical hardware edge interfaces**. It audits what physical hardware and software hooks exist today, what is blocked pending physical sensor wiring, and how operating context (rotational speed and belt tension) is legitimately acquired without data fabrication.

---

## 2. Hardware Readiness Classification Matrix

### A. AVAILABLE HARDWARE (Tested & Operable in Repo)
- **Host PC Serial COM Port Interface:** `pyserial` interface in `backend/app/serial_worker.py` capable of opening physical COM ports (`COM3`, `COM4`, `/dev/ttyUSB0`) at 115200 to 921600 baud.
- **Serial Parsing Pipeline:** Line-buffered JSON frame deserializer with SHA-256 binary canonical hashing and SQLite WAL persistence.
- **Database Seeded Edge Nodes:** Active trusted hardware device `esp32-node-01` (`is_trusted_hardware=1`, `status="ACTIVE"`) registered in SQLite.
- **Registered Sensor Entities:** `sens-vibe-01` (Accelerometer, 1000 Hz, SPI).

### B. SOFTWARE-READY (Pipeline Implemented, Awaiting Physical Flashing)
- **ESP32 Telemetry Packet Schema:** Strict contract in `backend/app/schemas.py` (`RawTelemetryPacketIn`):
  - `device_id`: String (e.g. `esp32-node-01`)
  - `stream_id`: String (e.g. `accel-z`)
  - `sensor_id`: String (e.g. `sens-vibe-01`)
  - `joint_id`: Nullable String (e.g. `J-01` or null)
  - `sequence_number`: Monotonic integer
  - `hardware_timestamp_us`: 64-bit / 32-bit hardware microsecond clock
  - `sampling_rate_hz`: Nominal 1000.0 Hz
  - `samples`: Float array (batched window, e.g. 100–200 samples)
  - `quality_flags`: `OK` | `CLIPPED` | `DROPPED_FRAMES` | `NOISY`
  - `data_provenance`: Strictly `"LIVE"` for hardware; `"SIMULATION"` rejected on `/telemetry/ingest`.
- **Phase 3 DSP Ingestion Bridge:** `HealthAssessmentService.process_burst()` extracts all 8 vibration features:
  - `rms`, `peak`, `crest_factor`, `kurtosis`, `skewness`, `dominant_freq_hz`, `spectral_centroid_hz`, `spectral_energy`.
- **Phase 4 ML Inference Bridge:** `VibrationAnomalyEngine.score_features()` and Joint Passport evidence generation.
- **Microsecond Timestamp Rollover Unwrapper:** 32-bit timer rollover handler in `backend/app/ingestion.py` tested for continuous long-run stability.

### C. NOT YET AVAILABLE (Hardware Not Yet Flashed or Physically Mounted)
- **Compiled ESP32 Binary / C++ Source:** Prior to Stage 5B, `edge/` only contained a specification (`esp32_firmware_spec.md`) and a Python test emitter (`virtual_serial_emitter.py`). No `.ino` or ESP-IDF `.cpp` code was committed.
- **Physical Accelerometer Wiring:** Physical ADXL345 (SPI) and MPU6050 (I2C) breadboard/harness wiring is documented, but physical device communication depends on deployment.
- **Physical Hall-Effect Tachometer:** Hardware pulse-counter interrupt driver on GPIO has not yet been committed to an active firmware build.
- **Physical Optical Encoder:** Not present in project hardware inventory.
- **Physical RFID Reader (RC522):** Documented in specification, but physical SPI reader is not wired to hardware nodes.

### D. HARDWARE-BLOCKED (Cannot Be Measured Without Additional Physical Transducers)
- **Continuous Dynamic Pretension (`pretension_n`):**
  - *Physical Reality:* The conveyor prototype currently lacks a continuous in-line strain-gauge load cell on the take-up carriage.
  - *Legitimate Acquisition:* Belt pretension is set mechanically via calibrated take-up bolts / spring balances (as in the Mendeley test bench at 70 N, 110 N, 150 N).
  - *Software Safety Rule:* If static calibrated pretension is not supplied through operational context, **the ML service will NOT invent a default value.** It will report `WAITING_FOR_OPERATING_CONTEXT` and refuse to score.

### E. FUTURE HARDWARE (Post-Hackathon Industrial Scale)
- **Multi-Point Distributed RS-485 Modbus Sensor Bus:** For 5 km overland conveyors with multiple idler stations.
- **High-Temperature Infrared Pyrometer Array:** For continuous rubber splice vulcanization monitoring.
- **Explosion-Proof (Ex-d / ATEX) Enclosure:** For underground coal/iron-ore explosive atmosphere compliance.

---

## 3. Specific Stage 5A Audit Answers

| Audit Item | Current Reality | Scientific & Architectural Decision |
| :--- | :--- | :--- |
| **Supported ESP32 Board** | ESP32-WROOM-32 (DevKit V1, 30-pin or 38-pin). Dual-core Xtensa LX6. | Core 0 dedicated to 1000 Hz hardware-timed ADC/SPI; Core 1 for JSON framing. |
| **Accelerometer Interface** | SPI (Hardware SPI bus) and I2C (Fast Mode 400 kHz). | Primary target: ADXL345 over SPI for clean $\pm 16g$ 1000 Hz sampling. Secondary: MPU6050 over I2C. |
| **ADXL345 vs MPU6050** | Both are software-ready in schema; neither has committed firmware drivers yet. | Create a modular C++ `SensorInterface` supporting both without backend changes. |
| **Tachometer Availability** | Physical sensor not yet connected; hardware interrupt pulse counting planned in Stage 5C. | If RPM is not physically measured, mark `speed_rpm = null`. Never invent fake RPM. |
| **RFID Hardware** | RC522 specified conceptually; no physical reader committed. | Allow graceful fallback to `joint_id = unavailable` until physical trigger is active. |
| **Pretension Measurement** | No dynamic load cell present. | Use static calibrated take-up setting. If absent, ML holds at `WAITING_FOR_OPERATING_CONTEXT`. |
| **Serial Packet Schema** | `schemas.RawTelemetryPacketIn` newline-delimited JSON. | Must preserve exact schema, monotonic sequence, and 64-bit microsecond counter. |
| **Ingestion Endpoints** | USB Serial (`serial_worker.py`) & HTTP (`POST /api/v1/telemetry/ingest`). | HTTP strictly rejects `SIMULATION` provenance; Serial worker will bridge to Phase 3 DSP. |
| **Phase 3 DSP Entry Point** | `HealthAssessmentService.process_burst(db, burst)`. | Calls `DSPAnalyzer.analyze()`, extracting 8 time/frequency features. |
| **Phase 4 ML Feature Vector** | 10 condition-aware features (`speed_rpm`, `pretension_n`, 8 DSP metrics). | Exact order preserved; Isolation Forest requires RPM & tension context. |

---

## 4. Stage 5A Conclusion & Next Step

The project architecture is completely verified and software-ready for edge telemetry. Because physical transducers must never be faked, Stage 5B will implement the production-grade ESP32 firmware with a clean C++ sensor abstraction (`ADXL345` / `MPU6050`) and framed serial output, preserving strict data provenance boundaries.
