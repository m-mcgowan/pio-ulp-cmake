// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT
//
// Example sensor driver for ULP — demonstrates inter-library dependencies
// (this library depends on example_i2c) and add_library() in a ULP CMake
// project.

#pragma once

#include <stdint.h>
#include "example_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SENSOR_CHIP_ID     0xD1
#define SENSOR_REG_CHIP_ID 0x00
#define SENSOR_REG_DATA    0x10

typedef struct {
    i2c_bus_t *bus;
    uint8_t addr;
    uint8_t chip_id;
} sensor_dev_t;

// Initialize sensor and verify chip ID
i2c_status_t sensor_init(sensor_dev_t *dev, i2c_bus_t *bus, uint8_t addr);

// Read sensor data register
i2c_status_t sensor_read_data(sensor_dev_t *dev, uint16_t *value);

#ifdef __cplusplus
}
#endif
