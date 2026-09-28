/**
 * @file esp32_sensor_node.ino
 * @brief Industrial Edge DAQ Node Firmware for Conveyor Belt Monitoring.
 * 
 * Target: ESP32 DevKit V1 (Dual-Core Xtensa LX6 @ 240 MHz).
 * Features:
 * - 1000 Hz hardware-timed vibration acquisition (ADXL345 SPI / MPU6050 I2C).
 * - Batched transport: 100 samples per window (10 Hz transmission) to prevent serial saturation.
 * - Hardware interrupt tachometer for real-time rotational speed (speed_rpm).
 * - Digital trigger interrupt for physical joint passage latching (joint_id).
 * - Monotonic 64-bit microsecond hardware timestamps (esp_timer_get_time).
 * - Strict JSON framing matching backend RawTelemetryPacketIn schema (data_provenance="LIVE").
 */

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include "SensorInterface.h"
#include "ADXL345Driver.h"
#include "MPU6050Driver.h"

// ── Hardware Pin Configuration ─────────────────────────────────────────────
// VSPI Bus: GPIO 18=SCK, GPIO 19=MISO, GPIO 23=MOSI, GPIO 5=CS (ADXL345)
// Tachometer and Joint Trigger use SEPARATE pins to avoid SPI bus sharing conflicts.
#define PIN_ADXL_CS          5       // ADXL345 Chip Select (VSPI CS)
#define PIN_TACHO_INTERRUPT   4      // Hall-effect Tachometer Pulse (GPIO 4, falling edge, pull-up)
#define PIN_JOINT_TRIGGER    15      // Joint Passage Trigger (GPIO 15, falling edge, pull-up)
#define PIN_LED_HEARTBEAT    2       // Onboard status LED

// ── Acquisition Constants ──────────────────────────────────────────────────
#define SAMPLING_RATE_HZ     1000.0f
#define SAMPLE_INTERVAL_US   1000    // 1000 µs = 1.0 ms
#define SAMPLES_PER_BURST    100     // 100 samples = 0.1 sec window (10 bursts/sec)

// ── Identity & Provenance (Strictly Preserved) ──────────────────────────────
const char* DEVICE_ID       = "esp32-node-01";
const char* STREAM_ID       = "accel-z";
const char* SENSOR_ID       = "sens-vibe-01";
const char* PROVENANCE_TAG  = "LIVE";

// ── Active Transducer Instance ─────────────────────────────────────────────
// Default to ADXL345 on SPI (CS=5). To use MPU6050 on I2C, instantiate MPU6050Driver.
ADXL345Driver sensor(PIN_ADXL_CS);
// MPU6050Driver sensor(0x68);

// ── Global Acquisition State ───────────────────────────────────────────────
volatile uint32_t sequenceNumber = 0;
volatile uint32_t droppedPacketsCount = 0;

// Double buffering for thread-safe 1000 Hz sampling and serial transmission
float sampleBufferA[SAMPLES_PER_BURST];
float sampleBufferB[SAMPLES_PER_BURST];
volatile float* activeWriteBuffer = sampleBufferA;
volatile float* readySendBuffer   = nullptr;
volatile int sampleIndex = 0;
volatile bool burstReady = false;
volatile int64_t burstStartTimestampUs = 0;

// ── Tachometer RPM State ───────────────────────────────────────────────────
volatile uint32_t tachoPulseCount = 0;
volatile uint64_t lastTachoPulseUs = 0;
volatile float instantaneousRPM = 0.0f;
volatile bool tachoHardwareActive = false;

// ── Joint Trigger State ────────────────────────────────────────────────────
volatile bool jointTriggerLatched = false;
char currentJointCode[16] = "";

// ── Hardware Timer Handle ──────────────────────────────────────────────────
hw_timer_t* sampleTimer = NULL;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

// ── ISR: Tachometer Pulse Interrupt ────────────────────────────────────────
void IRAM_ATTR onTachoPulse() {
    uint64_t now = esp_timer_get_time();
    uint64_t dt = now - lastTachoPulseUs;
    if (dt > 2000) { // 2ms debounce (max 30,000 RPM)
        if (lastTachoPulseUs > 0 && dt > 0) {
            // Instantaneous RPM: (60,000,000 µs/min) / dt_µs
            instantaneousRPM = 60000000.0f / (float)dt;
            tachoHardwareActive = true;
        }
        lastTachoPulseUs = now;
        tachoPulseCount++;
    }
}

// ── ISR: Joint Passage Trigger Interrupt ───────────────────────────────────
void IRAM_ATTR onJointTrigger() {
    jointTriggerLatched = true;
}

// ── ISR: 1000 Hz Hardware Sample Timer ─────────────────────────────────────
void IRAM_ATTR onSampleTimer() {
    portENTER_CRITICAL_ISR(&timerMux);

    float ax = 0.0f, ay = 0.0f, az = 0.0f;
    sensor.readAcceleration(ax, ay, az);

    if (sampleIndex == 0) {
        burstStartTimestampUs = esp_timer_get_time();
    }

    activeWriteBuffer[sampleIndex] = az; // Z-axis vertical vibration
    sampleIndex++;

    if (sampleIndex >= SAMPLES_PER_BURST) {
        if (!burstReady) {
            readySendBuffer = activeWriteBuffer;
            activeWriteBuffer = (activeWriteBuffer == sampleBufferA) ? sampleBufferB : sampleBufferA;
            sampleIndex = 0;
            burstReady = true;
        } else {
            // Previous burst not yet transmitted over UART; buffer overrun
            sampleIndex = 0;
            droppedPacketsCount++;
        }
    }

    portEXIT_CRITICAL_ISR(&timerMux);
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000); // Allow USB-Serial enumerating

    pinMode(PIN_LED_HEARTBEAT, OUTPUT);
    digitalWrite(PIN_LED_HEARTBEAT, LOW);

    pinMode(PIN_TACHO_INTERRUPT, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_TACHO_INTERRUPT), onTachoPulse, FALLING);

    pinMode(PIN_JOINT_TRIGGER, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_JOINT_TRIGGER), onJointTrigger, FALLING);

    // Initialize physical accelerometer
    if (!sensor.init()) {
        Serial.println("{\"error\":\"TRANSDUCER_INIT_FAILED\",\"message\":\"Failed to initialize accelerometer on SPI/I2C\"}");
    }

    // Configure 1000 Hz Hardware Timer (Timer 0, prescaler 80 -> 1 MHz clock, alarm 1000 -> 1 kHz)
    sampleTimer = timerBegin(0, 80, true);
    timerAttachInterrupt(sampleTimer, &onSampleTimer, true);
    timerAlarmWrite(sampleTimer, SAMPLE_INTERVAL_US, true);
    timerAlarmEnable(sampleTimer);

    digitalWrite(PIN_LED_HEARTBEAT, HIGH);
}

// ── Main Loop (Serial Framing & Packet Emission) ───────────────────────────
void loop() {
    if (burstReady && readySendBuffer != nullptr) {
        int64_t packetTimestampUs;
        float burstSamples[SAMPLES_PER_BURST];
        bool jointDetected;
        SensorQuality quality;
        float currentRPM;
        bool hasTacho;

        // Atomic copy from ready buffer
        portENTER_CRITICAL(&timerMux);
        packetTimestampUs = burstStartTimestampUs;
        for (int i = 0; i < SAMPLES_PER_BURST; i++) {
            burstSamples[i] = readySendBuffer[i];
        }
        quality = sensor.getQuality();
        jointDetected = jointTriggerLatched;
        jointTriggerLatched = false;
        currentRPM = instantaneousRPM;
        hasTacho = tachoHardwareActive;
        burstReady = false;
        readySendBuffer = nullptr;
        uint32_t currentSeq = sequenceNumber++;
        portEXIT_CRITICAL(&timerMux);

        // Evaluate Quality Flag
        const char* qualityFlagStr = "OK";
        if (quality == QUALITY_CLIPPED) {
            qualityFlagStr = "CLIPPED";
        } else if (droppedPacketsCount > 0) {
            qualityFlagStr = "DROPPED_FRAMES";
        }

        // Evaluate Joint ID
        const char* jointIdStr = nullptr;
        if (jointDetected) {
            jointIdStr = "J-01"; // Detected physical splice
        }

        // Format single-line JSON packet strictly conforming to RawTelemetryPacketIn
        Serial.print("{\"device_id\":\"");
        Serial.print(DEVICE_ID);
        Serial.print("\",\"stream_id\":\"");
        Serial.print(STREAM_ID);
        Serial.print("\",\"sensor_id\":\"");
        Serial.print(SENSOR_ID);
        Serial.print("\",\"joint_id\":");
        if (jointIdStr) {
            Serial.print("\"");
            Serial.print(jointIdStr);
            Serial.print("\"");
        } else {
            Serial.print("null");
        }
        Serial.print(",\"sequence_number\":");
        Serial.print(currentSeq);
        Serial.print(",\"hardware_timestamp_us\":");
        Serial.print(packetTimestampUs);
        Serial.print(",\"sampling_rate_hz\":1000.0");
        Serial.print(",\"quality_flags\":\"");
        Serial.print(qualityFlagStr);
        Serial.print("\",\"data_provenance\":\"LIVE\"");
        
        // Optional telemetry context when physically measured
        if (hasTacho && (esp_timer_get_time() - lastTachoPulseUs < 2000000)) { // Valid if pulse within 2s
            Serial.print(",\"speed_rpm\":");
            Serial.print(currentRPM, 1);
        }

        Serial.print(",\"samples\":[");
        for (int i = 0; i < SAMPLES_PER_BURST; i++) {
            Serial.print(burstSamples[i], 4);
            if (i < SAMPLES_PER_BURST - 1) {
                Serial.print(",");
            }
        }
        Serial.println("]}");
    }

    // Yield to FreeRTOS watchdog
    vTaskDelay(pdMS_TO_TICKS(1));
}
