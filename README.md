# Conveyor Belt Joint Rupture & Failure Prevention System
### Smart India Hackathon (SIH26008) — Industrial Hardware & Software Prototype

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.2+-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-4.0+-38B2AC.svg?style=flat&logo=tailwind-css)](https://tailwindcss.com)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32--WROOM--32-E7352C.svg?style=flat&logo=espressif)](https://www.espressif.com)
[![YOLOv8](https://img.shields.io/badge/Vision-Ultralytics%20YOLOv8-00FFFF.svg?style=flat)](https://github.com/ultralytics/ultralytics)
[![Scikit-Learn](https://img.shields.io/badge/ML-Isolation%20Forest-F7931E.svg?style=flat&logo=scikit-learn)](https://scikit-learn.org)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20WAL-003B57.svg?style=flat&logo=sqlite)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat)](LICENSE)

---

## 📌 Table of Contents

1. [Executive Summary & Problem Statement](#-executive-summary--problem-statement)
2. [Architectural Truth & Core Principles](#-architectural-truth--core-principles)
3. [System Architecture Diagram](#-system-architecture-diagram)
4. [Subsystem Breakdown](#-subsystem-breakdown)
   - [A. Edge Hardware & DAQ Interface](#a-edge-hardware--daq-interface)
   - [B. High-Rate Digital Signal Processing (DSP) Engine](#b-high-rate-digital-signal-processing-dsp-engine)
   - [C. Condition-Aware Machine Learning Anomaly Detection](#c-condition-aware-machine-learning-anomaly-detection)
   - [D. Optical Computer Vision Defect Detection](#d-optical-computer-vision-defect-detection)
   - [E. Digital Splice Joint Passport & Tamper-Evident Ledger](#e-digital-splice-joint-passport--tamper-evident-ledger)
   - [F. Cryptographic Evidence Vault & Provenance Isolation](#f-cryptographic-evidence-vault--provenance-isolation)
   - [G. Industrial SCADA HMI & Control Room](#g-industrial-scada-hmi--control-room)
5. [Repository Structure](#-repository-structure)
6. [Hardware Bill of Materials (BOM) & Pinout](#-hardware-bill-of-materials-bom--pinout)
7. [Installation & Quickstart Guide](#-installation--quickstart-guide)
   - [Prerequisites](#prerequisites)
   - [1. Backend Setup](#1-backend-setup)
   - [2. Frontend SCADA Setup](#2-frontend-scada-setup)
   - [3. Edge Hardware & Simulation Setup](#3-edge-hardware--simulation-setup)
8. [Live Demonstration Flow (Judge's Guide)](#-live-demonstration-flow-judges-guide)
9. [REST API & WebSocket Specifications](#-rest-api--websocket-specifications)
10. [Scientific Datasets & Citations](#-scientific-datasets--citations)
11. [Engineering Defense & FAQ](#-engineering-defense--faq)

---

## 📖 Executive Summary & Problem Statement

Conveyor belts in industrial mining, mineral processing, cement manufacturing, and bulk cargo handling facilities operate under extreme continuous tension (tens of kilonewtons in mine sites) transporting thousands of tons of ore per hour.

- **The Critical Failure Mode**: Belt splices (vulcanized finger joints or cold-bonded mechanical fasteners) represent the single weakest structural link in any conveyor circuit. Dynamic cyclic fatigue, splice seam delamination, core steel cord pull-out, and localized impact shock inevitably lead to catastrophic joint ruptures.
- **The Financial & Safety Impact**: A high-tension belt rupture causes sudden, violent elastic pullback, destroying idlers, pulverizing pulley drums, ripping structural framework, and endangering human lives. Plant downtime routinely exceeds **$50,000 to $100,000 per hour** in large mining operations.
- **Why Traditional Methods Fail**:
  1. *Manual Visual Inspections*: Conducted intermittently while the belt is stopped or running slowly, detecting damage only after surface cracks or catastrophic tears have propagated.
  2. *Distant Bearing Vibration Sensors*: Placed on motor drive bearings hundreds of meters away, completely attenuating high-frequency, localized splice impact transients.
  3. *Uncalibrated Deep Learning*: End-to-end "black box" models hallucinate false positives when belt speed or motor load changes under normal operations.
- **The Solution**: An integrated, end-to-end cyber-physical predictive maintenance platform combining high-rate (1000 Hz) time-domain and frequency-domain Digital Signal Processing, condition-aware unsupervised anomaly detection (Isolation Forest), optical computer vision (YOLOv8), SHA-256 cryptographic provenance, and a real-time React SCADA dashboard with digital joint passports.

---

## 🏛 Architectural Truth & Core Principles

This system is built upon four uncompromised industrial engineering tenets:

1. **Backend-Authoritative Pipeline**:
   No sensor telemetry, health score, ML prediction, or alarm state is fabricated or independently invented in the frontend. The React SCADA interface is a pure projection of the backend state machine.
2. **Zero Hardware Fabrication Policy**:
   When physical ESP32 hardware is connected, data is ingested with `EDGE_HARDWARE` / `LIVE` provenance. If hardware is unplugged, the bridge explicitly halts with `[SENSOR NOT CONNECTED]`. The system strictly prohibits synthetic numbers from masquerading as physical hardware.
3. **Three-Tier Data Provenance Isolation**:
   Every telemetry burst, observation, and alert carries an immutable provenance tag:
   - `EDGE_HARDWARE` (or `LIVE`): Real physical DAQ readings from hardware sensors.
   - `SIMULATION`: Synthetic test-bench waveforms generated for scenario validation.
   - `RESEARCH_BENCHMARK`: Certified experimental runs from peer-reviewed datasets.
4. **Honest, Defensible Industrial Metrics**:
   We do not display arbitrary countdown timers (e.g. "RUL = 17 days, 4 hours") without longitudinal run-to-failure degradation curves across dozens of identical belts. Instead, we compute empirical degradation rates ($g/\text{revolution}$ slope), condition-aware anomaly scores, and deterministic ISO-aligned alarm persistence. All demonstration trip thresholds are explicitly labeled `[DEMO THRESHOLD] / [SIMULATED INTERLOCK]`.

---

## 📐 System Architecture Diagram

```
+---------------------------------------------------------------------------------------+
|                                    DATA SOURCES                                       |
|  [Physical ESP32 Node (UART)]     [Virtual HTTP Emitter]    [Research Dataset / IF]   |
|   (Baud 115200, 1000 Hz SPI)       (Fault Synthesizer)       (Mendeley 10.17632)      |
+-----------------------------+-------------------+--------------------+----------------+
                              |                   |                    |
                              v                   v                    v
                      [EDGE_HARDWARE]        [SIMULATION]     [RESEARCH_BENCHMARK]
                              |                   |                    |
                              +---------+---------+                    |
                                        v                              |
                          +---------------------------+                |
                          |   FastAPI Ingestion API   |                |
                          |  (/telemetry/ingest &     |                |
                          |   /telemetry/simulate)    |                |
                          +-------------+-------------+                |
                                        |                              |
                                        v                              |
                          +---------------------------+                |
                          |  Canonical SHA-256        |                |
                          |  IEEE-754 Integrity Hash  |                |
                          +-------------+-------------+                |
                                        |                              |
                                        v                              |
                          +---------------------------+                |
                          |  DSP Feature Engine       |                |
                          |  (RMS, Crest, Kurtosis,   |                |
                          |   FFT Spectral Energy)    |                |
                          +-------------+-------------+                |
                                        |                              |
                                        v                              |
                          +---------------------------+                |
                          | Condition-Aware Isolation |<---------------+
                          | Forest Anomaly Detector   | (Speed RPM + Pretension N)
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          | Joint Health Engine &     |
                          | Hysteresis State Machine  |
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          | SQLite WAL Persistence &  |
                          | WebSocket Broadcaster     |
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          | React 19 SCADA Dashboard  |
                          |  - Control Room           |
                          |  - Digital Joint Passport |
                          |  - AI Diagnosis (YOLO+ML) |
                          |  - Evidence Vault         |
                          +---------------------------+
```

---

## ⚙️ Subsystem Breakdown

### A. Edge Hardware & DAQ Interface
- **Microcontroller**: ESP32 DevKit V1 (Xtensa dual-core 32-bit LX6 microprocessor at 240 MHz).
- **Core 0**: Executes high-rate, hardware-timer-driven SPI/I2C burst acquisition at **1000.0 Hz**.
- **Core 1**: Manages JSON serialization, microsecond timestamping, line-buffered framing, and UART transmission at 115200 baud.
- **Sensors**:
  - Primary Accelerometer: **ADXL345** (Hardware VSPI, $\pm 16g$ range, 13-bit resolution).
  - Alternative Accelerometer: **MPU6050** (Fast-mode I2C @ 400 kHz, $\pm 16g$).
  - Speed Tachometer: Hall-effect / optical sensor triggered via falling-edge hardware interrupt (`PIN_TACHO_INTERRUPT`).
  - Joint Transit Sensor: Optical retro-reflector / Hall latch detecting splice passage (`PIN_JOINT_TRIGGER`).
- **Timestamp Rollover Protection**: Firmware handles 32-bit microsecond counter wraparound (~71.5 minutes) via a continuous 64-bit unwrapping algorithm in [`backend/app/ingestion.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/ingestion.py).

### B. High-Rate Digital Signal Processing (DSP) Engine
Implemented in [`backend/app/dsp.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/dsp.py), the DSP engine processes raw 1000 Hz vibration arrays and computes 8 fundamental time- and frequency-domain metrics:
1. **RMS Acceleration ($g$)**: Overall vibration power.
2. **Peak Acceleration ($g$)**: Maximum absolute dynamic acceleration in the burst window.
3. **Peak-to-Peak Acceleration ($g$)**: Full excursion between negative and positive extremes.
4. **Crest Factor ($ratio$)**: $\frac{\text{Peak}}{\text{RMS}}$ — sensitive indicator of sharp joint finger impacts and localized shock transients.
5. **Excess Kurtosis**: Fourth standardized moment assessing impulsiveness of vibration bursts.
6. **Skewness**: Third standardized moment assessing waveform asymmetry.
7. **Dominant Frequency (Hz)**: Peak spectral frequency derived from single-sided Fast Fourier Transform (FFT).
8. **Spectral Centroid & Energy**: Center-of-mass of the power spectrum and cumulative spectral power.
- **Rolling Baseline Calibration**: Computes baseline Median and Median Absolute Deviation (MAD), generating robust $\sigma$-equivalent z-scores ($z = \frac{x - \text{median}}{1.4826 \times \text{MAD}}$).

### C. Condition-Aware Machine Learning Anomaly Detection
Implemented in [`backend/app/ml_service.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/ml_service.py) and trained via [`ml/train_vibration_anomaly.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/ml/train_vibration_anomaly.py):
- **Algorithm**: `RobustScaler` + `IsolationForest` pipeline (150 estimators, 10% contamination factor).
- **Condition-Aware Context**: Evaluates a 10-dimensional feature vector:
  $$\mathbf{X} = [\text{speed\_rpm}, \text{pretension\_n}, \text{driver\_rms}, \text{driver\_peak}, \text{driver\_crest}, \text{driver\_kurtosis}, \text{driver\_freq}, \text{driven\_rms}, \text{driven\_crest}, \text{driven\_freq}]$$
- **Industrial Integrity**: If operational context (`speed_rpm` or `pretension_n`) is missing, the ML engine refuses to guess or hallucinate, remaining in `WAITING_FOR_OPERATING_CONTEXT`.
- **Training Provenance**: Trained exclusively on normal operating runs (Repetitions 1 & 2 across 17 speeds and 3 pretensions) from the peer-reviewed Mendeley Belt Drive dataset (DOI: `10.17632/jf8v2ndydr.1`), and evaluated on frozen test sets.

### D. Optical Computer Vision Defect Detection
Implemented in [`backend/app/vision_service.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/vision_service.py) and trained via [`vision/train.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/vision/train.py):
- **Architecture**: Ultralytics YOLOv8 nano (`yolov8n.pt`).
- **Defect Taxonomy**: Fine-tuned on an annotated industrial conveyor belt damage dataset (651 images, 1,708 bounding boxes):
  - `Belt Joint`: Optical splice seam tracking.
  - `Large Tear` / `Small Tear`: Longitudinal rips and edge fraying.
  - `Large Hole` / `Small Hole`: Punctures caused by trapped ore / foreign objects.
  - `damage`: Generalized surface gouges and rubber delamination.
- **Multi-Evidence Synthesis**: Vision and vibration operate as independent evidence streams. Both are presented side-by-side in the Joint Passport without arbitrary mathematical smearing.

### E. Digital Splice Joint Passport & Tamper-Evident Ledger
Implemented in [`backend/app/joint_lifecycle_service.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/joint_lifecycle_service.py):
- **Splice Identity**: Tracks individual joints (e.g. `J-01`, `J-02`) mapped to physical conveyor position, belt compound, installation date, and passage counts.
- **Degradation Slope**: Computes linear regression of RMS acceleration across recorded revolutions ($g/\text{revolution}$ degradation rate) to monitor physical joint wear over time.
- **Tamper-Evident Maintenance Ledger**:
  - Logs technician ID, action type (`SPLICE_REPAIR`, `RETENSIONING`, `RECALIBRATION`, `INSPECTION`), before/after risk states, notes, and baseline resets.
  - Commits each record with a deterministic **SHA-256 Audit Digest** to SQLite WAL.

### F. Cryptographic Evidence Vault & Provenance Isolation
- **IEEE-754 Canonical Serialization**: Raw float-32 acceleration sample arrays are packed into deterministic byte streams.
- **SHA-256 Digest**: Computed at the moment of ingestion before database persistence.
- **Live Verifier**: The Evidence page (`/evidence`) allows operators and auditors to re-hash persisted samples on the fly to verify that zero bit-level tampering has occurred.

### G. Industrial SCADA HMI & Control Room
Modern React 19 single-page application located in [`frontend/`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/frontend):
- **Typography & Theme**: Industrial Dark Mode styled with Google Fonts (`Rajdhani`, `JetBrains Mono`, `Inter`) and Tailwind CSS v4.
- **Real-Time Canvas Waveforms**: 1000 Hz continuous oscilloscope-style vibration waveform canvas with peak/trough indicators.
- **Dynamic Spectral FFT**: Real-time frequency spectrum display highlighting dominant harmonic frequencies.
- **Hysteresis Risk States**: Multi-observation state machine preventing alarm chattering:
  $$\text{NORMAL} \xrightarrow{2\text{ anomalies}} \text{WARNING} \xrightarrow{3\text{ anomalies}} \text{CRITICAL (TRIP)}$$
  $$\text{CRITICAL} \xrightarrow{3\text{ healthy passes}} \text{RECOVERY}$$

---

## 📁 Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api.py                    # FastAPI route controllers & WebSocket endpoints
│   │   ├── config.py                 # System thresholds, paths, & engineering parameters
│   │   ├── database.py               # SQLite WAL connection & schema migration
│   │   ├── dsp.py                    # Time & frequency domain DSP feature extraction
│   │   ├── health_service.py         # Joint health scoring, hysteresis state machine
│   │   ├── historical_replay_service.py # Research dataset replay engine
│   │   ├── ingestion.py              # Telemetry ingestion, timestamp unwrapper, SHA-256
│   │   ├── joint_lifecycle_service.py# Digital Joint Passport & degradation tracking
│   │   ├── ml_service.py             # Isolation Forest anomaly scoring engine
│   │   ├── models.py                 # SQLAlchemy database schema & ledger models
│   │   ├── provenance.py             # Scientific provenance & citation metadata
│   │   ├── schemas.py                # Pydantic validation schemas
│   │   ├── serial_worker.py          # Background USB UART acquisition worker
│   │   ├── simulator.py              # High-fidelity synthetic fault generator
│   │   ├── vision_service.py         # YOLOv8 optical damage inference service
│   │   └── websocket_manager.py      # Async WebSocket broadcasting pool
│   ├── tests/                        # 84+ Unit, DSP, Ingestion, & Integration tests
│   └── main.py                       # Application entrypoint & static mount
├── frontend/
│   ├── src/
│   │   ├── components/               # Gauges, Waveforms, FFT Spectrums, SubNav, Layout
│   │   ├── context/                  # MonitoringContext (WebSocket, scenario triggers)
│   │   ├── pages/
│   │   │   ├── ControlRoom.tsx       # Live SCADA view, waveforms, interlock display
│   │   │   ├── JointPassport.tsx     # Digital Splice Joint Passport & Maintenance Ledger
│   │   │   ├── SensorAnalytics.tsx   # DSP time/frequency analytical deep-dive
│   │   │   ├── AIDiagnosis.tsx       # Isolation Forest + YOLOv8 inspection breakdown
│   │   │   ├── Alerts.tsx            # Evidence-based alert stream & acknowledgement
│   │   │   ├── Evidence.tsx          # SHA-256 verifier & dataset provenance audit
│   │   │   ├── Settings.tsx          # Hardware COM port, baud rate, & plant configs
│   │   │   └── Login.tsx             # Operator / Engineer authentication
│   │   ├── services/                 # REST API client & WebSocket handler
│   │   └── types/                    # TypeScript interfaces & domain models
│   ├── package.json                  # React 19, Vite, Tailwind CSS v4, Recharts
│   └── vite.config.ts                # Vite dev server configuration
├── edge/
│   ├── firmware/
│   │   ├── WIRING_AND_PINOUT.md      # Pin connection tables & wiring diagrams
│   │   └── esp32_sensor_node/
│   │       ├── esp32_sensor_node.ino # Multi-core ESP32 DAQ firmware (1000 Hz SPI)
│   │       ├── ADXL345Driver.h       # Hardware SPI driver for ADXL345
│   │       ├── MPU6050Driver.h       # Fast-mode I2C driver for MPU6050
│   │       └── SensorInterface.h     # Clean C++ polymorphic sensor abstraction
│   ├── hardware_bridge.py            # Serial DAQ bridge script
│   ├── virtual_serial_emitter.py     # Standalone HTTP / Serial fault generator
│   └── HARDWARE_READINESS.md         # Stage 5A Hardware readiness audit
├── ml/
│   └── train_vibration_anomaly.py    # Condition-aware Isolation Forest training pipeline
├── vision/
│   └── train.py                      # YOLOv8 conveyor defect training & evaluation
├── models/
│   ├── ml/vibration_anomaly/         # Serialized Isolation Forest model & metadata
│   └── vision/conveyor_damage/       # Fine-tuned YOLOv8 weights (best.pt)
├── data/
│   ├── metadata/                     # Provenance JSONs & dataset manifest
│   ├── processed/research/           # Cleaned research features & YOLO labels
│   └── raw/                          # Raw research datasets & test samples
├── JUDGES_DEMO_SCRIPT.md             # Complete step-by-step SIH defense script
└── yolov8n.pt                        # Base YOLOv8 weights
```

---

## 🔌 Hardware Bill of Materials (BOM) & Pinout

### Component List
| Component | Specification | Purpose | Interface |
| :--- | :--- | :--- | :--- |
| **ESP32 DevKit V1** | Dual-Core 240 MHz, 4MB Flash | Edge DAQ & JSON Framing Node | USB / UART |
| **ADXL345** | $\pm 16g$, 13-bit, 3200 Hz ODR | High-frequency joint vibration sensing | Hardware VSPI |
| **MPU6050** *(Alternative)* | 6-Axis Accelerometer/Gyro | Secondary vibration transducer | I2C (400 kHz) |
| **Hall Effect / Optical Tach**| NPN Open-Collector / 3.3V | Pulley rotational speed (RPM) | GPIO Interrupt |
| **Joint Transit Marker** | Retro-reflective / Magnet | Splice arrival trigger window | GPIO Interrupt |
| **Power Supply** | 5V 2A Micro-USB / External 3.3V | Node & sensor supply rail | Power |

### ESP32 Pin Assignment
```
ESP32 DevKit V1 Pin            Connected Peripheral Signal
───────────────────            ───────────────────────────
3V3            ────────────►   VCC (ADXL345 / Sensors)  [3.3V ONLY]
GND            ────────────►   Common System GND
GPIO 5         ────────────►   ADXL345 CS (Chip Select, Active LOW)
GPIO 23        ────────────►   ADXL345 SDA / MOSI (Master Out)
GPIO 19        ────────────►   ADXL345 SDO / MISO (Master In)
GPIO 18        ────────────►   ADXL345 SCL / SCK  (SPI Clock)
GPIO 4         ────────────►   Tachometer Pulse Input (Pull-up interrupt)
GPIO 15        ────────────►   Joint Passage Marker Sensor (Pull-up)
GPIO 2         ────────────►   Onboard Blue LED (Blinks on active DAQ)
```

---

## 🚀 Installation & Quickstart Guide

### Prerequisites
- **Operating System**: Windows 10/11, Ubuntu 20.04+, or macOS.
- **Python**: Version `3.10` or higher (`3.11` recommended).
- **Node.js**: Version `18.x` or `20.x` (`npm` included).
- **Git**: Installed and on system `PATH`.

---

### 1. Backend Setup

Open a terminal in the project root:

```bash
# 1. Create and activate a Python virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
# source venv/bin/activate

# 2. Install Python dependencies
pip install fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy \
            numpy scipy pandas scikit-learn joblib opencv-python ultralytics pyserial pytest httpx

# 3. Start the FastAPI backend server
python backend/main.py
```

The backend server initializes SQLite tables and begins listening at:
- **API Server & Swagger UI**: `http://127.0.0.1:8001/docs`
- **WebSocket Endpoint**: `ws://127.0.0.1:8001/ws/v1/live-telemetry`
- **Classic HMI View**: `http://127.0.0.1:8001/classic`

---

### 2. Frontend SCADA Setup

Open a separate terminal window:

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install npm packages
npm install

# 3. Start the Vite development server
npm run dev
```

Open your browser at: **`http://127.0.0.1:5173`** (or `http://localhost:5173`).

To compile the production build served directly by FastAPI:
```bash
npm run build
```
Once built, navigating to `http://127.0.0.1:8001/` serves the production React SPA!

---

### 3. Edge Hardware & Simulation Setup

#### Option A: Running with Real ESP32 Hardware
1. Connect the ESP32 to your PC via USB.
2. In the frontend **Settings** page or [`backend/app/config.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/config.py), set:
   ```python
   SERIAL_PORT = "COM3"          # Adjust to your device port (e.g. /dev/ttyUSB0)
   SERIAL_WORKER_ENABLED = True
   ```
3. Or launch the hardware bridge directly:
   ```bash
   python edge/hardware_bridge.py --port COM3 --baud 115200
   ```

#### Option B: Running with the Virtual Fault Emitter
To validate all fault scenarios without physical hardware:
```bash
# Send continuous simulated telemetry over HTTP to the backend:
python edge/virtual_serial_emitter.py --mode http --url http://127.0.0.1:8001/api/v1/telemetry/simulate --speed 1.0
```

#### Option C: Built-in SCADA Replay
By default, when `SERIAL_WORKER_ENABLED = False`, the backend automatically runs a background historical replay loop in stable `NORMAL` condition, streaming live telemetry to the SCADA dashboard without requiring extra terminal commands.

---

## 🎯 Live Demonstration Flow (Judge's Guide)

Follow this verified sequence during technical evaluations:

### Step 1: System Baseline & Provenance Audit
1. Navigate to **Control Room** (`/control-room`).
2. Point out the **Provenance Badge** in the top-right header:
   - When running real hardware: displays `LIVE • HARDWARE`.
   - When running scenarios: displays `SIMULATION • DEMO`.
   - Explain: *"Our system enforces strict scientific data provenance. Simulation data never masquerades as physical sensor telemetry."*
3. Verify baseline metrics: RMS ~1.06 g, Crest Factor ~1.52, Dominant Frequency 50.0 Hz, Health Score `100/100 (NORMAL)`.

### Step 2: Splice Rupture Warning (`SPLICE_IMPACT`)
1. In the SubNav bar, switch the scenario dropdown to **Splice Rupture Warning**.
2. Observe the system response:
   - **Waveform Canvas**: Displays sharp periodic impulse spikes characteristic of cracked vulcanized joint fingers.
   - **DSP Metrics**: RMS jumps to ~2.32 g; Crest Factor spikes to 2.81+.
   - **Alert Stream**: Automatically triggers an amber `WARNING` alert with root-cause metric snapshots.

### Step 3: Mechanical Harmonic Looseness (`HARMONIC_LOOSENESS`)
1. Select **Harmonic Looseness** from the dropdown.
2. Point out:
   - **FFT Spectrum**: Displays structural harmonic peaks at 50 Hz, 100 Hz, and 150 Hz.
   - **Health Diagnostic**: Condition monitoring detects multi-harmonic energy redistribution characteristic of loose take-up mounts or pulley misalignment.

### Step 4: Critical Failure & Simulated Interlock (`CRITICAL_FAILURE`)
1. Select **Critical Failure** from the dropdown.
2. Observe:
   - **Waveform**: Extreme energy shock transients (Peak > 16 g, RMS > 4.2 g, Crest Factor ~3.97).
   - **Trip Status**: Status switches to `CRITICAL` / `[SIMULATED INTERLOCK]`.
   - **Engineering Honesty**: Note the explicit label `[SIMULATED INTERLOCK] / [DEMO THRESHOLD]`. Explain that production plants trigger an IEC 61508 / SIL-3 certified hardware relay to execute emergency drive stops.

### Step 5: Digital Splice Joint Passport & Tamper-Evident Ledger
1. Navigate to **Joint Passport** (`/joint-passport`) and select **Joint J-01**.
2. View the **Multi-Evidence Synthesis**: Vibration DSP metrics, Optical Vision defect class, and Operating Context (RPM, tension) shown independently.
3. Click **Log Maintenance Action**:
   - Technician ID: `TECH-MINE-42`
   - Action: `SPLICE_REPAIR`
   - Notes: `Re-cured vulcanized fingers. Reset take-up tension to 110 N.`
   - Check `Reset Learned Vibration Baseline`.
   - Click **Commit Record**.
4. Show the updated ledger with its deterministic **SHA-256 Audit Hash**. Refresh the page to prove persistence in SQLite WAL.

### Step 6: Evidence Vault & Cryptographic Verification
1. Navigate to **Evidence** (`/evidence`).
2. Show the **Binary SHA-256 Verifier**: Click verification to re-hash the raw IEEE-754 acceleration samples and verify that it matches the stored cryptographic record: `CRYPTOGRAPHICALLY VALIDATED (PASS)`.
3. Point out the peer-reviewed **Dataset Provenance** (DOI: `10.17632/jf8v2ndydr.1`).

---

## 📡 REST API & WebSocket Specifications

### Telemetry & Ingestion Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/telemetry/ingest` | Primary ingestion endpoint for real ESP32 hardware (`EDGE_HARDWARE`). Strictly rejects simulation packets. |
| `POST` | `/api/v1/telemetry/simulate` | Ingestion endpoint for synthetic simulation packets (`SIMULATION`). |
| `POST` | `/api/v1/telemetry/simulate/generate-fault` | Injects synthetic fault scenarios (`NORMAL`, `SPLICE_IMPACT`, `HARMONIC_LOOSENESS`, `CRITICAL_FAILURE`). |
| `GET` | `/api/v1/telemetry/latest` | Returns the latest persisted telemetry burst summary. |
| `GET` | `/api/v1/telemetry/bursts/{burst_id}` | Retrieves raw burst samples and verifies cryptographic SHA-256 integrity. |
| `GET` | `/api/v1/system/status` | Returns system health, active streams, and packet loss statistics. |

### Analytics, Health & AI Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/bursts/{burst_id}/dsp` | Executes full time- and frequency-domain DSP analysis on a stored burst. |
| `GET` | `/api/v1/joints/{joint_id}/health` | Returns current health score, risk state, baseline deviation, and trend. |
| `GET` | `/api/v1/joints/{joint_id}/passport` | Returns multi-evidence Joint Passport integrating vibration, vision, and operating context. |
| `GET` | `/api/v1/joints/{joint_id}/lifecycle` | Returns degradation rate slope ($g/\text{revolution}$) and revolution counts. |
| `GET` | `/api/v1/ml/status` | Returns Isolation Forest model version, training provenance, and feature list. |
| `POST` | `/api/v1/ml/score` | Scores a 10-dimensional condition-aware feature vector against the research model. |

### Vision & Maintenance Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/vision/analyze` | Uploads an optical frame for YOLOv8 conveyor defect detection and bounding-box inference. |
| `GET` | `/api/v1/vision/observations` | Lists optical inspection observations and defect classifications. |
| `POST` | `/api/v1/maintenance/log` | Commits a tamper-evident maintenance record with SHA-256 hash. |
| `GET` | `/api/v1/joints/{joint_id}/maintenance` | Lists maintenance history for a specific belt joint. |
| `GET` | `/api/v1/alerts` | Lists evidence-based alert events with severity filtering. |
| `POST` | `/api/v1/alerts/{alert_id}/acknowledge` | Acknowledges an active alert, preserving operator audit logs. |

### Real-Time WebSocket
- **URL**: `ws://127.0.0.1:8001/ws/v1/live-telemetry`
- **Events Emitted**:
  - `TELEMETRY_BURST`: Real-time raw waveform samples, sequence number, and timestamps.
  - `HEALTH_UPDATE`: Health score, risk state, and baseline deviations.
  - `ALERT_DISPATCH`: Real-time alarm notification with supporting evidence.
  - `REPLAY_STATUS`: Historical dataset replay status and progress.

---

## 📚 Scientific Datasets & Citations

1. **Belt Drive Vibration Benchmark Dataset**:
   - **Citation**: *Experimental vibration data collected for a belt drive system under different operating conditions.*
   - **Authors**: Data in Brief, 2023.
   - **DOI**: [10.17632/jf8v2ndydr.1](https://doi.org/10.17632/jf8v2ndydr.1)
   - **License**: Creative Commons Attribution 4.0 International (CC BY 4.0).
   - **Usage**: Used to train and evaluate the condition-aware Isolation Forest model across 17 rotational speeds and 3 pretension levels (70 N, 110 N, 150 N).
2. **Conveyor Belt Damage Computer Vision Dataset**:
   - **Format**: 651 high-resolution images, 1,708 COCO bounding box annotations.
   - **Classes**: `damage`, `Belt Joint`, `Large Hole`, `Large Tear`, `Small Hole`, `Small Tear`.
   - **Usage**: Fine-tuning Ultralytics YOLOv8 for automated surface inspection.

---

## 🛡 Engineering Defense & FAQ

#### Q1: Why use an Isolation Forest instead of an end-to-end Deep Learning model (e.g. CNN / LSTM)?
**Answer**:
1. **Severe Industrial Class Imbalance**: In industrial mining, normal running hours account for >99.9% of all data. Catastrophic splice ruptures are destructive, rare events. Supervised deep neural networks trained on heavily augmented failure data suffer from severe out-of-distribution hallucinations and high false positive rates in varying operating regimes.
2. **Unsupervised Anomaly Boundary**: Isolation Forest isolates anomalies by recursively partitioning feature space without requiring labeled failure instances during initial baseline training.
3. **Condition-Aware Context**: Our pipeline feeds operating context (belt speed in RPM and pretension in N) alongside 8 DSP metrics into the standardizer. This ensures a vibration increase caused merely by belt acceleration is not falsely flagged as structural splice damage.
4. **Deterministic Edge Execution**: Isolation Forest tree traversal executes in microseconds on constrained CPU compute without GPU requirements.

#### Q2: Why is there no exact Remaining Useful Life countdown (e.g. "RUL = 17 days, 4 hours")?
**Answer**:
To display an exact numeric RUL countdown in days or hours without genuine longitudinal run-to-failure degradation data collected across dozens of identical belts under identical operating conditions is scientifically indefensible. In industrial engineering, fake RUL counters create a dangerous false sense of precision. Instead, our system provides defensible decision support: empirical degradation rate ($g/\text{revolution}$ slope calculated over observed revolutions), condition-aware anomaly scoring, and deterministic ISO-aligned alarm persistence.

#### Q3: How do Computer Vision (YOLO) and Vibration DSP work together? Is it a fused neural network?
**Answer**:
We maintain strict architectural separation between optical vision and vibration DSP rather than claiming an unsupported multimodal tensor fusion:
- **Vibration Transducer (ADXL345 / ESP32)**: Measures subsurface internal splice strain, core cord delamination, and dynamic impulse impacts at 1000 Hz.
- **Optical Camera (YOLOv8n)**: Detects surface tears, longitudinal rips, splice seam separation, and surface gouges.
In the Joint Passport, both evidence streams are displayed side-by-side as independent corroborating evidence. If vibration crest factor spikes and computer vision simultaneously detects a tear, the deterministic health engine escalates the alert severity to `CRITICAL`. We do not invent an arbitrary weighting equation.

#### Q4: How does cryptographic integrity work? Is it a blockchain?
**Answer**:
No, it is not a blockchain. Conveyor monitoring at 1000 Hz generates high data velocity where distributed consensus would add immense latency without engineering benefit. Instead, we implement deterministic canonical cryptographic provenance:
1. Every incoming raw sample array is serialized into IEEE-754 binary representation.
2. A SHA-256 digest is computed at the moment of ingestion.
3. The burst is stored alongside its hash, sequence number, and strict provenance tag.
4. Any bit-level tampering with persisted vibration samples is detected immediately by the on-demand verifier.

#### Q5: Are your alarm thresholds derived from ISO 10816?
**Answer**:
ISO 10816 provides general vibration severity guidelines for rigid rotating industrial machinery (motors, gearboxes, bearings), but it does not specify direct surface thresholds for flexible elastomeric conveyor splice joints. Our thresholds (e.g. Crest Factor > 3.5, RMS > 5.0 g) are calibrated demonstration parameters designed to illustrate impulsive fault progression on our test-rig. We explicitly label them as `[DEMO THRESHOLD]` to preserve scientific and industrial honesty.

---

## 👥 Contributors & Acknowledgements
- **Team**: SIH26008 Hardware Prototype Engineering Team
- **Competition**: Smart India Hackathon (SIH) — Hardware Edition
- **Mentorship & Evaluation**: Dedicated to industrial plant operators and mining reliability engineers striving for zero unplanned downtime and safe conveyor operations.
