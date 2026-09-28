# ESP32 Edge DAQ Node Wiring & Pinout Guide
**Firmware Target:** `edge/firmware/esp32_sensor_node/esp32_sensor_node.ino`  
**Microcontroller:** ESP32 DevKit V1 (30-pin / 38-pin module)  

---

## 1. Pin Assignment Table

| ESP32 Pin | Function | Peripheral | Connected Signal | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **GPIO 5**  | VSPI CS    | ADXL345         | **CS** (Chip Select)       | Active LOW |
| **GPIO 18** | VSPI SCK   | ADXL345         | **SCL / SCK**              | Hardware SPI Clock |
| **GPIO 19** | VSPI MISO  | ADXL345         | **SDO / MISO**             | Hardware SPI Master In |
| **GPIO 23** | VSPI MOSI  | ADXL345         | **SDA / MOSI**             | Hardware SPI Master Out |
| **GPIO 4**  | Input (Pull-up) | Tachometer | **TACHO_PULSE**            | Falling edge ISR — **dedicated, no SPI conflict** |
| **GPIO 15** | Input (Pull-up) | Joint Trigger | **JOINT_TRIGGER**       | Falling edge ISR — Hall-effect / optical retro-reflector |
| **GPIO 21** | I2C SDA    | MPU6050 (alt)   | **SDA**                    | 400 kHz Fast-mode I2C (if using MPU6050) |
| **GPIO 22** | I2C SCL    | MPU6050 (alt)   | **SCL**                    | 400 kHz Fast-mode I2C (if using MPU6050) |
| **GPIO 2**  | Output     | Status LED      | **LED_HEARTBEAT**          | Onboard Blue LED (blinks on DAQ) |
| **3V3**     | Power      | Accelerometer   | **VCC / 3.3V**             | Do NOT connect to 5V! |
| **GND**     | Ground     | Common          | **GND**                    | Common system ground reference |

> **Pin Conflict Resolution (Phase 2):** GPIO 18 and 19 are reserved exclusively for the VSPI SPI bus (ADXL345). The tachometer interrupt is on **GPIO 4** and the joint trigger is on **GPIO 15** — both interrupt-capable pins with no SPI bus sharing.

---

## 2. SPI Accelerometer Wiring (ADXL345 — Recommended)

Connect the ADXL345 breakout module to the ESP32 VSPI bus:

```
ESP32 DevKit V1               ADXL345 Module
────────────────             ────────────────
3V3           ────────────►  VCC (3.3V)
GND           ────────────►  GND
GPIO 5        ────────────►  CS
GPIO 23       ────────────►  SDA / MOSI
GPIO 19       ────────────►  SDO / MISO
GPIO 18       ────────────►  SCL / SCK
```

*Note on Pin Selection:* If using dedicated VSPI bus pins (GPIO 18/19/23) for ADXL345, map `PIN_TACHO_INTERRUPT` to **GPIO 4** and `PIN_JOINT_TRIGGER` to **GPIO 15** to avoid SPI bus pin sharing.

---

## 3. I2C Accelerometer Wiring (MPU6050 Alternative)

If using the MPU6050 6-axis IMU over I2C:

```
ESP32 DevKit V1               MPU6050 Module
────────────────             ────────────────
3V3           ────────────►  VCC (3.3V)
GND           ────────────►  GND
GPIO 21       ────────────►  SDA
GPIO 22       ────────────►  SCL
GND           ────────────►  AD0 (Sets I2C address 0x68)
```

In `esp32_sensor_node.ino`, uncomment:
```cpp
MPU6050Driver sensor(0x68);
```

---

## 4. Tachometer (RPM) & Joint Trigger Wiring

### A. Hall-Effect / Optical Speed Sensor (Pulley RPM)
- **Signal Pin:** Connect output collector to **GPIO 4** (or configured `PIN_TACHO_INTERRUPT`).
- **Power:** 3.3V / 5V (use level shifter or voltage divider if sensor is 5V Open-Collector).
- **Triggering:** Falling edge interrupt on each magnet or reflective tooth passage.

### B. Joint Passage Marker Sensor
- **Signal Pin:** Connect optical diffuse/reflector sensor or magnetic splice marker to **GPIO 15** (or configured `PIN_JOINT_TRIGGER`).
- **Function:** Latches `joint_id = "J-01"` for the duration of the splice transit burst window.

---

## 5. Serial Connection & Backend Ingestion

1. Connect the ESP32 to the Host PC via micro-USB.
2. The onboard CP2102 / CH340 chip registers as a virtual COM port (e.g., `COM3` on Windows, `/dev/ttyUSB0` on Linux).
3. The backend [`backend/app/serial_worker.py`](file:///c:/Users/Nikhil/Documents/sih%20hardware%20prototype/backend/app/serial_worker.py) connects at `115200` baud.
4. Packets are line-buffered JSON strings terminated with `\n` and ingested into SQLite WAL with SHA-256 canonical hashing.
