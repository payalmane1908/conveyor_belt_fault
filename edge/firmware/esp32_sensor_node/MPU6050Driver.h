/**
 * @file MPU6050Driver.h
 * @brief Hardware driver implementation for InvenSense MPU6050 6-axis IMU (accelerometer mode).
 * 
 * Supports I2C interface on ESP32 (Wire).
 * Configures ±16g full-scale range and 1 kHz sample rate.
 */

#ifndef MPU6050_DRIVER_H
#define MPU6050_DRIVER_H

#include "SensorInterface.h"
#include <Wire.h>

#define MPU6050_I2C_ADDR           0x68
#define MPU6050_REG_SMPLRT_DIV     0x19
#define MPU6050_REG_CONFIG         0x1A
#define MPU6050_REG_ACCEL_CONFIG   0x1C
#define MPU6050_REG_ACCEL_XOUT_H   0x3B
#define MPU6050_REG_PWR_MGMT_1     0x6B
#define MPU6050_REG_WHO_AM_I       0x75

#define MPU6050_EXPECTED_ID        0x68
#define MPU6050_SCALE_FACTOR_16G   (1.0f / 2048.0f) // 2048 LSB/g in ±16g mode

class MPU6050Driver : public SensorInterface {
private:
    uint8_t _i2cAddr;
    SensorQuality _quality;

    void writeRegister(uint8_t reg, uint8_t val) {
        Wire.beginTransmission(_i2cAddr);
        Wire.write(reg);
        Wire.write(val);
        Wire.endTransmission();
    }

public:
    MPU6050Driver(uint8_t i2cAddr = MPU6050_I2C_ADDR) : _i2cAddr(i2cAddr), _quality(QUALITY_OK) {}

    bool init() override {
        Wire.begin(21, 22, 400000); // Fast mode I2C (400 kHz)

        // Wake up sensor (clear SLEEP bit in PWR_MGMT_1)
        writeRegister(MPU6050_REG_PWR_MGMT_1, 0x00);
        delay(10);

        // Verify WHO_AM_I
        Wire.beginTransmission(_i2cAddr);
        Wire.write(MPU6050_REG_WHO_AM_I);
        Wire.endTransmission(false);
        Wire.requestFrom(_i2cAddr, (uint8_t)1);
        if (!Wire.available() || Wire.read() != MPU6050_EXPECTED_ID) {
            _quality = QUALITY_DISCONNECTED;
            return false;
        }

        // Configure Sample Rate Divider for 1 kHz (SMPLRT_DIV = 0 when DLPF disabled)
        writeRegister(MPU6050_REG_SMPLRT_DIV, 0x00);

        // Configure DLPF: 260 Hz Accel bandwidth, 1 kHz internal sampling (CONFIG = 0x00)
        writeRegister(MPU6050_REG_CONFIG, 0x00);

        // Configure Full Scale Range: ±16g (ACCEL_CONFIG = 0x18)
        writeRegister(MPU6050_REG_ACCEL_CONFIG, 0x18);

        _quality = QUALITY_OK;
        return true;
    }

    bool readAcceleration(float &ax, float &ay, float &az) override {
        Wire.beginTransmission(_i2cAddr);
        Wire.write(MPU6050_REG_ACCEL_XOUT_H);
        if (Wire.endTransmission(false) != 0) {
            _quality = QUALITY_DISCONNECTED;
            return false;
        }

        Wire.requestFrom(_i2cAddr, (uint8_t)6);
        if (Wire.available() < 6) {
            _quality = QUALITY_DISCONNECTED;
            return false;
        }

        int16_t rawX = (int16_t)((Wire.read() << 8) | Wire.read());
        int16_t rawY = (int16_t)((Wire.read() << 8) | Wire.read());
        int16_t rawZ = (int16_t)((Wire.read() << 8) | Wire.read());

        ax = rawX * MPU6050_SCALE_FACTOR_16G;
        ay = rawY * MPU6050_SCALE_FACTOR_16G;
        az = rawZ * MPU6050_SCALE_FACTOR_16G;

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
        return "MPU6050 (±16g 1kHz)";
    }
};

#endif // MPU6050_DRIVER_H
