// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#include "ulp_app.h"
#include "ulp_helpers.h"
#include "example_i2c.h"
#include "example_sensor.h"

// Shared variable visible to main MCU via generated ulp_main.h
volatile uint32_t app_state = 0;

// I2C and sensor state
static i2c_bus_t i2c_bus;
static sensor_dev_t sensor;

int ulp_app_init(void) {
    app_state = 1;  // Starting init

    // Initialize I2C bus (proves example_i2c library is linked)
    i2c_config_t cfg = {
        .sda_pin = 2,
        .scl_pin = 3,
        .clock_hz = 100000,
    };
    i2c_init(&i2c_bus, &cfg);

    // Initialize sensor over I2C (proves example_sensor + inter-lib dep works)
    i2c_status_t err = sensor_init(&sensor, &i2c_bus, 0x68);

    // Call helper from subdirectory library (proves add_subdirectory works)
    uint32_t magic = ulp_helpers_get_magic();

    if (err == I2C_OK) {
        app_state = 2;  // Init success
    } else {
        app_state = 0xFF;  // Init failed
    }

    app_state += magic;  // Use magic to prevent dead-code elimination

    return (int)err;
}
