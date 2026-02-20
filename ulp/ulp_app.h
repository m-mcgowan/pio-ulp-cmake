// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Shared ULP variable — accessible from both ULP and main MCU
extern volatile uint32_t app_state;

// Initialize the ULP application (sets up I2C, reads BMX160 chip ID)
int ulp_app_init(void);

#ifdef __cplusplus
}
#endif
