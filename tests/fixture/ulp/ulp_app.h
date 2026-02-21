// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Shared variable accessible from main MCU via generated header
extern volatile uint32_t app_state;

// Initialize the ULP application (sets up I2C, reads sensor)
int ulp_app_init(void);

#ifdef __cplusplus
}
#endif
