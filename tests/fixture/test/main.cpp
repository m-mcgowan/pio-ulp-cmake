// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT

#define DOCTEST_CONFIG_IMPLEMENT
#include <doctest.h>
#include <Arduino.h>

static bool board_init(Print& log) {
    log.println("[ulp-test] board_init OK");
    return true;
}

#define PTR_BOARD_INIT board_init
#include <pio_test_runner/doctest_runner.h>

void setup() { DOCTEST_SETUP(); }
void loop()  { DOCTEST_LOOP(); }
