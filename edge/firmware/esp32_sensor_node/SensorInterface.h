/**
 * @file SensorInterface.h
 * @brief Abstract accelerometer hardware abstraction layer for ESP32 Edge DAQ.
 * 
 * Defines the contract for physical vibration sensors (e.g., ADXL345, MPU6050).
 * Decouples hardware driver specifics from sampling and serial framing.
 */

#ifndef SENSOR_INTERFACE_H
#define SENSOR_INTERFACE_H

#include <Arduino.h>

enum SensorQuality {
    QUALITY_OK = 0,
    QUALITY_CLIPPED = 1,
    QUALITY_NOISY = 2,
    QUALITY_DISCONNECTED = 3
};

class SensorInterface {
public:
    virtual ~SensorInterface() {}

    /**
     * @brief Initializes the physical transducer and sets target sample rate / full-scale range.
     * @return true if communication succeeded and device ID is verified.
     */
    virtual bool init() = 0;

    /**
     * @brief Reads a single calibrated acceleration sample (in units of g).
     * @param[out] ax Acceleration on X axis (g)
     * @param[out] ay Acceleration on Y axis (g)
     * @param[out] az Acceleration on Z axis (g)
     * @return true if read was successful.
     */
    virtual bool readAcceleration(float &ax, float &ay, float &az) = 0;

    /**
     * @brief Gets current sensor quality status (e.g. checks saturation/clipping).
     */
    virtual SensorQuality getQuality() = 0;

    /**
     * @brief Returns sensor identifier string (e.g. "ADXL345", "MPU6050").
     */
    virtual const char* getSensorName() const = 0;
};

#endif // SENSOR_INTERFACE_H
