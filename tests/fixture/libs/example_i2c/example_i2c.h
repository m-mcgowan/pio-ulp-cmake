// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT
//
// Minimal I2C abstraction for ULP — demonstrates add_library() with
// target_link_libraries() in a ULP CMake project.

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    I2C_OK = 0,
    I2C_ERR_NACK = 1,
    I2C_ERR_TIMEOUT = 2,
} i2c_status_t;

typedef struct {
    uint8_t sda_pin;
    uint8_t scl_pin;
    uint32_t clock_hz;
} i2c_config_t;

typedef struct {
    i2c_config_t config;
    uint8_t initialized;
} i2c_bus_t;

// Initialize an I2C bus
i2c_status_t i2c_init(i2c_bus_t *bus, const i2c_config_t *config);

// Read a register from a device
i2c_status_t i2c_read_reg(i2c_bus_t *bus, uint8_t addr, uint8_t reg,
                           uint8_t *data, uint8_t len);

// Write a register to a device
i2c_status_t i2c_write_reg(i2c_bus_t *bus, uint8_t addr, uint8_t reg,
                            const uint8_t *data, uint8_t len);

#ifdef __cplusplus
}
#endif
