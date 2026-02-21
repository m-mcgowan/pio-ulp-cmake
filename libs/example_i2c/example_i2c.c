// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#include "example_i2c.h"

i2c_status_t i2c_init(i2c_bus_t *bus, const i2c_config_t *config) {
    if (!bus || !config) {
        return I2C_ERR_TIMEOUT;
    }
    bus->config = *config;
    bus->initialized = 1;
    return I2C_OK;
}

i2c_status_t i2c_read_reg(i2c_bus_t *bus, uint8_t addr, uint8_t reg,
                           uint8_t *data, uint8_t len) {
    if (!bus || !bus->initialized) {
        return I2C_ERR_TIMEOUT;
    }
    // Stub: in real code this would perform I2C transactions
    for (uint8_t i = 0; i < len; i++) {
        data[i] = reg + i;  // deterministic test pattern
    }
    return I2C_OK;
}

i2c_status_t i2c_write_reg(i2c_bus_t *bus, uint8_t addr, uint8_t reg,
                            const uint8_t *data, uint8_t len) {
    if (!bus || !bus->initialized) {
        return I2C_ERR_TIMEOUT;
    }
    // Stub: no-op write
    (void)addr;
    (void)reg;
    (void)data;
    (void)len;
    return I2C_OK;
}
