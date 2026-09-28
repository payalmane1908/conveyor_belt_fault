# SIH26008 — Conveyor Belt Joint Rupture & Failure Prevention System
## Technical Demonstration & Engineering Defense Script for SIH Judges

---

### Executive Overview & Architectural Truth

> **System Core Principle**:
> Real ESP32 hardware, virtual simulation, DSP feature extraction, ML condition monitoring, health scoring, tamper-evident maintenance ledger, and the React SCADA frontend communicate through a **single, backend-authoritative architecture**.
> No sensor data, health score, ML prediction, or alert state is fabricated or independently invented in the frontend.

```
+---------------------------------------------------------------------------------------+
|                                    DATA SOURCES                                       |
|  [Physical ESP32 Node (UART)]     [Virtual HTTP Emitter]    [Research Dataset / IF]   |
|   (Baud 115200, 1000 Hz)           (Preset Generator)       (Mendeley 10.17632)       |
+-----------------------------+-------------------+--------------------+----------------+
                              |                   |                    |
                              v                   v                    v
                      [EDGE_HARDWARE]        [SIMULATION]     [RESEARCH_BENCHMARK]
                              |                   |                    |
                              +---------+---------+                    |
                                        v                              |
                          +---------------------------+                |
                          |  Backend Ingestion API    |                |
                          |  (/telemetry/ingest &     |                |
                          |   /telemetry/simulate)    |                |
                          +-------------+-------------+                |
                                        |                              |
                                        v                              |
                          +---------------------------+                |
                          |  Canonical SHA-256        |                |
                          |  Integrity Hashing        |                |
                          +-------------+-------------+                |
                                        |                              |
                                        v                              |
                          +---------------------------+                |
                          |  DSP Feature Engine       |                |
                          |  (RMS, Crest, Kurtosis,   |                |
                          |   FFT Dominant Frequency) |                |
                          +-------------+-------------+                |
                                        |                              |
                                        v                              |
                          +---------------------------+                |
                          |  Isolation Forest Anomaly |<---------------+
                          |  Detection (Phase 4B)     |
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          |  Joint Health Engine &    |
                          |  Deterministic Interlock  |
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          |  Alert Dispatch &         |
                          |  WebSocket Broadcaster    |
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          |  React SCADA Dashboard    |
                          |  (Control Room / Passport)|
                          +---------------------------+
```

---

### Part 1: The Problem & Engineering Context

Conveyor belts in industrial mining and material handling facilities operate under continuous tension (e.g. 110 N on test rigs, tens of kilonewtons in mine sites) transporting hundreds of tons of bulk material per hour. 
- **The Critical Failure Mode**: Belt splices (vulcanized finger joints or mechanical fasteners) are critical failure points in conveyor systems. Unplanned belt failure can cause significant production downtime, maintenance cost and safety risk. A catastrophic splice separation results in sudden belt rupture, violent pull-back, severe structural damage to pulleys, extended unplanned plant downtime, and serious personnel safety risks.
- **Why Traditional Methods Fail**: Periodic manual visual inspections only detect damage *after* visible surface cracking or delamination has occurred. Point vibration sensors placed on distant bearing housings attenuate high-frequency splice impact transients.
- **Our Solution**: Continuous, high-rate (1000 Hz) time-domain and frequency-domain digital signal processing combined with condition-aware Machine Learning (Isolation Forest) and synchronized optical inspection. Every vibration burst is cryptographically hashed with SHA-256 for auditability and tamper evidence.

---

### Part 2: Step-by-Step Live Demonstration Flow

#### Step 1: System Baseline & Provenance Audit
1. Navigate to **Control Room** (`http://127.0.0.1:5173/control-room`).
2. Point out the **Provenance Badge** in the top-right SubNav bar:
   - When running against real ESP32 hardware: displays `LIVE • HARDWARE` (`EDGE_HARDWARE`).
   - When running demonstration scenarios: displays `SIMULATION • DEMO` (`SIMULATION`).
   - Explain: *"Our system enforces strict scientific data provenance. Simulation data never masquerades as physical sensor telemetry."*
3. Show the **Scenario Dropdown** in the SubNav bar:
   - Initial state: `Scenario A: Normal Baseline` (`NORMAL`).
   - In the **Vibration Waveform Card**, show the real sinusoidal acceleration waveform (~1.06 g RMS, Crest Factor ~1.52, Dominant Frequency 50.0 Hz).
   - In the **Health Status Widget**, note: `Belt Health: 100/100`, Status: `NORMAL`, Recommendation: `Nominal baseline condition. Belt splice operating within standard limits.`

#### Step 2: Scenario B — Splice Rupture Warning (`SPLICE_IMPACT`)
1. In the SubNav bar, select **Splice Rupture Warning** from the dropdown.
2. Trace the execution flow to the judges:
   ```
   Dropdown Click -> MonitoringContext.triggerScenario('SPLICE_IMPACT')
   -> POST /api/v1/telemetry/simulate/generate-fault?sensor_id=sim-accel-p3-01&fault_mode=SPLICE_IMPACT
   -> Backend Simulator synthesizes impulsive periodic transients (1000 Hz)
   -> Ingestion validates schema & computes SHA-256 hash
   -> DSP calculates RMS (2.32 g) and Crest Factor spike (2.81)
   -> WebSocket broadcasts TELEMETRY_BURST & HEALTH_UPDATE
   -> React UI updates waveform, raises amber WARNING status, and logs alert
   ```
3. Highlight to judges:
   - **Waveform**: Distinct sharp impulse spikes corresponding to damaged joint fingers traversing the detection station.
   - **DSP Metrics**: RMS jumps from ~1.06 g to 2.32 g; Crest Factor jumps from ~1.52 to 2.81.
   - **Alert**: A `WARNING` alert is automatically triggered in the system.

#### Step 3: Scenario C — Mechanical Harmonic Looseness (`HARMONIC_LOOSENESS`)
1. Select **Harmonic Looseness** from the dropdown.
2. Point out:
   - **Frequency Spectrum**: FFT reveals characteristic harmonic peaks (50 Hz fundamental + 100 Hz / 150 Hz structural harmonics).
   - **Health Diagnostic**: Condition monitoring detects multi-harmonic energy redistribution characteristic of loose take-up mechanical mounts or joint misalignment.

#### Step 4: Scenario D — Critical Failure & Simulated Interlock (`CRITICAL_FAILURE`)
1. Select **Critical Failure** from the dropdown.
2. Point out the system response:
   - **Waveform**: Extreme energy shock vibration (Peak > 16 g, RMS > 4.2 g, Crest Factor ~3.97).
   - **Simulated Interlock**: Status turns to `CRITICAL` / `[SIMULATED INTERLOCK]`.
   - **Engineering Honesty Note**: Point out the explicit UI label `[SIMULATED INTERLOCK] / [DEMO THRESHOLD]`. Explain: *"This software demonstrates an automated SCADA trip recommendation. In a production plant, an IEC 61508 / SIL-3 certified hardware relay would execute the emergency drive stop."*

#### Step 5: Digital Splice Joint Passport & Tamper-Evident Maintenance
1. Navigate to **Joint Passport** (`http://127.0.0.1:5173/joint-passport`).
2. Show **Joint J-01**:
   - Point out the **Multi-Evidence Synthesis**: Vibration DSP metrics, Optical Vision defect class, and Operating Context (RPM, tension) shown independently without arbitrary mathematical smearing.
3. Click **Log Maintenance Action**:
   - Fill in:
     - Technician ID: `TECH-MINE-42`
     - Action Type: `SPLICE_REPAIR`
     - Notes: `Re-cured outer vulcanized splice fingers. Tension reset to 110 N.`
     - Check `Reset Learned Vibration Baseline`.
   - Click **Commit Record**.
4. Show the updated **Maintenance Ledger**:
   - The record appears instantly with its deterministic **SHA-256 Audit Hash** (e.g. `65c0d993fa...47cb3e2e`).
   - Refresh the page to prove to the judges that the record was committed to the SQLite database and persisted across reloads.

#### Step 6: Evidence Vault & Cryptographic Verification
1. Navigate to **Evidence** (`http://127.0.0.1:5173/evidence`).
2. Show the **Binary SHA-256 Verifier**:
   - View the latest telemetry burst.
   - Click the verification trigger to compute the real-time SHA-256 checksum over the raw float-32 acceleration payload and demonstrate that it matches the stored cryptographic record: `CRYPTOGRAPHICALLY VALIDATED (PASS)`.
3. Point out the **Dataset Provenance**:
   - Cite the Mendeley Data benchmark (DOI: `10.17632/jf8v2ndydr.1`) used for baseline model evaluation.

---

### Part 3: Technical Defense & Question-and-Answer Guide

#### Q1: Why did you use an Isolation Forest rather than an end-to-end Deep Learning model (e.g. CNN / LSTM)?
**Answer**:
1. **Extreme Class Imbalance in Industrial Settings**: In operational mines and conveyor systems, normal running hours account for >99.9% of all data. Real-world catastrophic splice ruptures are exceedingly rare and destructive events. Deep learning classifiers trained on synthetic or heavily augmented failure data suffer from severe out-of-distribution hallucinations and false positives in unfamiliar operating regimes.
2. **Unsupervised Anomaly Boundary**: Isolation Forest isolates anomalies by recursively partitioning feature space without requiring labeled failure instances during initial baseline training.
3. **Condition-Aware Context**: Our Phase 4B pipeline feeds operational context (belt speed in RPM, pretension in N) alongside 8 time/frequency DSP metrics into the standardizer. This ensures a vibration increase caused merely by belt acceleration is not falsely flagged as mechanical splice damage.
4. **Edge Feasibility**: Isolation Forest tree traversal executes in microseconds on constrained industrial compute without GPU requirements.

#### Q2: Why is there no exact Remaining Useful Life (RUL = 17 days / 83 hours) displayed on your dashboard?
**Answer**:
*"To claim an exact numeric RUL countdown in days or hours without genuine longitudinal run-to-failure degradation data collected across dozens of identical belts under identical operating conditions is scientifically indefensible. In industrial engineering, fake RUL counters create a dangerous false sense of precision. Instead, our system provides defensible decision support: empirical degradation rate ($g/\text{revolution}$ slope calculated over observed revolutions), condition-aware anomaly scoring, and deterministic ISO-aligned alarm persistence."*

#### Q3: How do Computer Vision (YOLO) and Vibration DSP work together? Is it a fused neural network?
**Answer**:
*"We maintain strict architectural separation between optical vision and vibration DSP rather than claiming an unsupported multimodal tensor fusion:
- **Vibration Transducer (ADXL345 / ESP32)**: Measures subsurface internal splice strain, core cord delamination, and dynamic impulse impacts at 1000 Hz.
- **Optical Camera (YOLOv8n)**: Detects surface tears, longitudinal rips, splice seam separation, and surface foreign object gouges.
In the Joint Passport, both evidence streams are displayed side-by-side as independent corroborating evidence. If vibration crest factor spikes and computer vision simultaneously detects a tear, the deterministic health engine escalates the alert severity to CRITICAL_ACTION_REQUIRED. We do not invent an arbitrary 70/30 weighting equation."*

#### Q4: How does your cryptographic integrity and data provenance work? Is it a blockchain?
**Answer**:
*"No, it is not a blockchain. Conveyor monitoring at 1000 Hz generates high data velocity where distributed consensus would add immense latency without engineering benefit.
Instead, we implement deterministic canonical cryptographic provenance:
1. Every incoming raw sample array is serialized deterministically into IEEE-754 binary representation.
2. A SHA-256 digest is computed at the moment of ingestion.
3. The burst is stored alongside its hash, sequence number, and strict provenance tag (`EDGE_HARDWARE`, `SIMULATION`, or `RESEARCH_BENCHMARK`).
4. Any bit-level tampering with persisted vibration samples is detected immediately by the verifier."*

#### Q5: Are your alarm thresholds derived from ISO 10816?
**Answer**:
*"ISO 10816 provides general vibration severity guidelines for rotating industrial machinery (such as motors, gearboxes, and large bearings), but it does not specify direct surface thresholds for flexible elastomeric conveyor splice joints. Our thresholds (e.g. Crest Factor > 3.5, RMS > 6.5 g) are calibrated demonstration parameters designed to illustrate impulsive fault progression on our test-rig. We explicitly label them as `[DEMO THRESHOLD]` to preserve scientific and industrial honesty."*

#### Q6: How does the system handle real ESP32 hardware vs simulation?
**Answer**:
*"We built a dedicated hardware DAQ bridge (`edge/hardware_bridge.py`) that interfaces directly with our ESP32 DevKit running `edge/firmware/esp32_sensor_node/esp32_sensor_node.ino` at 115200 baud over UART. 
- When the ESP32 is physically plugged in, packets are ingested with `EDGE_HARDWARE` provenance.
- If the hardware is unplugged, the bridge explicitly halts with `[SENSOR NOT CONNECTED]` under our strict Zero Hardware Fabrication policy. It never silently manufactures fake numbers pretending to be real hardware.
- Simulation is handled through a separate, dedicated endpoint (`/telemetry/simulate`) and explicitly carries the `SIMULATION` provenance tag throughout the entire pipeline."*

---

### Part 4: Technical Verification Summary for SIH Evaluators

| Subsystem / Metric | Verification Status | Artifact / Command |
| :--- | :--- | :--- |
| **Backend Test Suite** | **84 passed, 1 skipped, 0 failed** (Phase 1 verified) | `python -m pytest backend/tests/ -v` |
| **Frontend Production Build** | Zero TypeScript / Vite errors | `npm run build` inside `frontend/` |
| **Hardware DAQ Bridge** | Validated against ESP32 firmware | `python edge/hardware_bridge.py --list-ports` |
| **Virtual HTTP Emitter** | Validated with backend seq-sync | `python edge/virtual_serial_emitter.py --mode http` |
| **E2E Scenario Execution** | All 4 scenarios verified via DSP/Health | Normal, Splice Impact, Harmonic, Critical |
| **Cryptographic Audit** | SHA-256 validated across all bursts | Evidence Vault + Joint Passport ledger |
| **Data Provenance Separation** | Strict 3-tier boundary enforced | `EDGE_HARDWARE`, `SIMULATION`, `RESEARCH_BENCHMARK` |
