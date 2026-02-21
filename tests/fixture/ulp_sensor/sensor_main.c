// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#include <stdint.h>
#include "ulp_riscv_utils.h"

/* Exported variables — prefixed with "sensor_" by ULP_VAR_PREFIX */
volatile uint32_t sensor_value = 0;
volatile uint32_t sensor_count = 0;

int main(void)
{
    sensor_count++;
    /* Simulate reading a sensor */
    sensor_value = 42 + sensor_count;
    ulp_riscv_delay_cycles(1000);
    return 0;
}
