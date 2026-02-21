// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#include "example_sensor.h"

i2c_status_t sensor_init(sensor_dev_t *dev, i2c_bus_t *bus, uint8_t addr) {
    if (!dev || !bus) {
        return I2C_ERR_TIMEOUT;
    }
    dev->bus = bus;
    dev->addr = addr;

    // Read and verify chip ID
    i2c_status_t status = i2c_read_reg(bus, addr, SENSOR_REG_CHIP_ID,
                                        &dev->chip_id, 1);
    return status;
}

i2c_status_t sensor_read_data(sensor_dev_t *dev, uint16_t *value) {
    uint8_t raw[2] = {0};
    i2c_status_t status = i2c_read_reg(dev->bus, dev->addr,
                                        SENSOR_REG_DATA, raw, 2);
    if (status == I2C_OK) {
        *value = ((uint16_t)raw[0] << 8) | raw[1];
    }
    return status;
}
