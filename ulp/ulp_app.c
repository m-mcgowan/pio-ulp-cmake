// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#include "ulp_app.h"
#include "ulp_helpers.h"
#include "bmx160.h"
#include "elert_i2c.h"
#include "elert_i2c_simple.h"
#include "soft_i2c_simple.h"

// Shared variable visible to main MCU via generated ulp_main.h
volatile uint32_t app_state = 0;

// I2C and BMX160 state
static elert_i2c_interface_t i2c_iface;
static simple_i2c_config_t i2c_config;

int ulp_app_init(void) {
    app_state = 1;  // Starting init

    // Initialize software I2C (proves elert_i2c library is linked)
    i2c_config.sda_pin = 2;
    i2c_config.scl_pin = 3;
    elert_create_simple_i2c(&i2c_iface, &i2c_config);

    // Set up bmx160 device with the I2C interface (proves bmx160 library is linked)
    // Note: We use bmx160_read_reg directly rather than bmx160_init() because the
    // full init pulls in power management, FIFO config, and magnetometer init which
    // reference esp_log and elert_i2c_delay_us — not available on ULP.
    // This matches how simple_publish uses the library on ULP.
    bmx160_dev_t dev = {0};
    dev.i2c = &i2c_iface;
    uint8_t chip_id = 0;
    i2c_error_t err = bmx160_read_reg(&dev, BMX160_REG_CHIP_ID, &chip_id);

    // Call helper from subdirectory library (proves add_subdirectory works)
    uint32_t magic = ulp_helpers_get_magic();

    if (err == I2C_ERROR_OK && chip_id == BMX160_CHIP_ID) {
        app_state = 2;  // Init success
    } else {
        app_state = 0xFF;  // Init failed
    }

    app_state += magic;  // Use magic to prevent dead-code elimination

    return (int)err;
}
