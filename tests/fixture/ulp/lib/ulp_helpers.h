// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Returns a magic value — exists to prove subdirectory library linking works
uint32_t ulp_helpers_get_magic(void);

#ifdef __cplusplus
}
#endif
