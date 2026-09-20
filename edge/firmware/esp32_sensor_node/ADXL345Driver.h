/**
 * @file ADXL345Driver.h
 * @brief Hardware driver implementation for Analog Devices ADXL345 3-axis digital accelerometer.
 * 
 * Supports SPI and I2C hardware buses on ESP32.
 * Configures full-resolution mode (±16g, 3.9 mg/LSB) and 1600 Hz output data rate (ODR).
 */

#ifndef ADXL345_DRIVER_H
#define ADXL345_DRIVER_H

#include "SensorInterface.h"
#include <SPI.h>
#include <Wire.h>

// ADXL345 Register Addresses
#define ADXL345_REG_DEVID          0x00
#define ADXL345_REG_BW_RATE        0x2C
#define ADXL345_REG_POWER_CTL      0x2D
#define ADXL345_REG_DATA_FORMAT    0x31
#define ADXL345_REG_DATAX0         0x32

#define ADXL345_EXPECTED_DEVID     0xE5
#define ADXL345_SCALE_FACTOR_G     0.00390625f  // 1/256 g/LSB (3.9 mg/LSB full resolution)

class ADXL345Driver : public SensorInterface {
private:
    int _csPin;
    bool _useSPI;
    uint8_t _i2cAddr;
    SensorQuality _quality;

    void writeRegister(uint8_t reg, uint8_t val) {
        if (_useSPI) {
            digitalWrite(_csPin, LOW);
            SPI.transfer(reg);
            SPI.transfer(val);
            digitalWrite(_csPin, HIGH);
        } else {
            Wire.beginTransmission(_i2cAddr);
            Wire.write(reg);
            Wire.write(val);
            Wire.endTransmission();
        }
    }

    uint8_t readRegister(uint8_t reg) {
        uint8_t val = 0;
        if (_useSPI) {
            digitalWrite(_csPin, LOW);
            SPI.transfer(reg | 0x80); // Read bit set
            val = SPI.transfer(0x00);
            digitalWrite(_csPin, HIGH);
        } else {
            Wire.beginTransmission(_i2cAddr);
            Wire.write(reg);
            Wire.endTransmission(false);
            Wire.requestFrom(_i2cAddr, (uint8_t)1);
            if (Wire.available()) val = Wire.read();
        }
        return val;
    }

public:
    // SPI Constructor
    ADXL345Driver(int csPin) : _csPin(csPin), _useSPI(true), _i2cAddr(0x53), _quality(QUALITY_OK) {}

    // I2C Constructor
    ADXL345Driver(uint8_t i2cAddr = 0x53) : _csPin(-1), _useSPI(false), _i2cAddr(i2cAddr), _quality(QUALITY_OK) {}

    bool init() override {
        if (_useSPI) {
            pinMode(_csPin, OUTPUT);
            digitalWrite(_csPin, HIGH);
            SPI.begin();
            SPI.setClockDivider(SPI_CLOCK_DIV4); // 5 MHz clock
        } else {
            Wire.begin(21, 22, 400000); // Fast mode I2C
        }

        // Verify Device ID
        uint8_t devId = readRegister(ADXL345_REG_DEVID);
        if (devId != ADXL345_EXPECTED_DEVID) {
            _quality = QUALITY_DISCONNECTED;
            return false;
        }

        // Configure BW_RATE: 1600 Hz ODR / 800 Hz Bandwidth (code 0x0E)
        writeRegister(ADXL345_REG_BW_RATE, 0x0E);

        // Configure DATA_FORMAT: Full resolution, ±16g range (0x0B)
        writeRegister(ADXL345_REG_DATA_FORMAT, 0x0B);

        // Configure POWER_CTL: Measurement mode (0x08)
        writeRegister(ADXL345_REG_POWER_CTL, 0x08);

        _quality = QUALITY_OK;
        return true;
    }

    bool readAcceleration(float &ax, float &ay, float &az) override {
        int16_t rawX, rawY, rawZ;

        if (_useSPI) {
            digitalWrite(_csPin, LOW);
            SPI.transfer(ADXL345_REG_DATAX0 | 0xC0); // Read + Multiple bytes
            uint8_t x0 = SPI.transfer(0x00);
            uint8_t x1 = SPI.transfer(0x00);
            uint8_t y0 = SPI.transfer(0x00);
            uint8_t y1 = SPI.transfer(0x00);
            uint8_t z0 = SPI.transfer(0x00);
            uint8_t z1 = SPI.transfer(0x00);
            digitalWrite(_csPin, HIGH);

            rawX = (int16_t)((x1 << 8) | x0);
            rawY = (int16_t)((y1 << 8) | y0);
            rawZ = (int16_t)((z1 << 8) | z0);
        } else {
            Wire.beginTransmission(_i2cAddr);
            Wire.write(ADXL345_REG_DATAX0);
            if (Wire.endTransmission(false) != 0) {
                _quality = QUALITY_DISCONNECTED;
                return false;
            }
            Wire.requestFrom(_i2cAddr, (uint8_t)6);
            if (Wire.available() < 6) {
                _quality = QUALITY_DISCONNECTED;
                return false;
            }
            rawX = (int16_t)(Wire.read() | (Wire.read() << 8));
            rawY = (int16_t)(Wire.read() | (Wire.read() << 8));
            rawZ = (int16_t)(Wire.read() | (Wire.read() << 8));
        }

        ax = rawX * ADXL345_SCALE_FACTOR_G;
        ay = rawY * ADXL345_SCALE_FACTOR_G;
        az = rawZ * ADXL345_SCALE_FACTOR_G;

        // Check for full-scale clipping (±15.8g saturation)
        if (fabs(ax) > 15.8f || fabs(ay) > 15.8f || fabs(az) > 15.8f) {
            _quality = QUALITY_CLIPPED;
        } else {
            _quality = QUALITY_OK;
        }

        return true;
    }

    SensorQuality getQuality() override {
        return _quality;
    }

    const char* getSensorName() const override {
        return "ADXL345 (±16g Full-Res)";
    }
};

#endif // ADXL345_DRIVER_H
