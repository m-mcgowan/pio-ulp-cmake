// SPDX-FileCopyrightText: 2026 Mat McGowan
// SPDX-License-Identifier: MIT
//
// On-device test: ULP continues running across main CPU deep sleep.
//
// Two-phase test using pio-test-runner's deep sleep protocol:
//   Phase 1 (first boot): load + start ULP sensor, verify it runs, then sleep
//   Phase 2 (after wake): verify wakeup cause and that sensor_count increased

#include <doctest.h>
#include <Arduino.h>
#include <esp_sleep.h>
#include <ulp_riscv.h>
#include <pio_test_runner/test_runner.h>

extern const uint8_t ulp_sensor_bin_start[] asm("_binary_ulp_sensor_bin_start");
extern const uint8_t ulp_sensor_bin_end[] asm("_binary_ulp_sensor_bin_end");

extern "C" {
#include "ulp_sensor.h"
}

TEST_SUITE("ULP DeepSleep") {

TEST_CASE("ULP sensor survives deep sleep" * doctest::timeout(30)) {
    auto cause = esp_sleep_get_wakeup_cause();

    if (cause == ESP_SLEEP_WAKEUP_UNDEFINED) {
        // Phase 1: first boot — load ULP, verify it runs, then sleep
        esp_err_t err = ulp_riscv_load_binary(ulp_sensor_bin_start,
            ulp_sensor_bin_end - ulp_sensor_bin_start);
        REQUIRE(err == ESP_OK);

        sensor_sensor_count = 0;
        err = ulp_riscv_run();
        REQUIRE(err == ESP_OK);

        delay(100);
        Serial.printf("Phase 1: sensor_count=%lu before sleep\n",
            (unsigned long)sensor_sensor_count);
        CHECK(sensor_sensor_count > 0);

        // Configure ULP timer wakeup so ULP keeps running during sleep
        ulp_set_wakeup_period(0, 100000);  // 100ms period

        // Signal the test runner we're about to sleep
        pio_test_runner::signal_sleep(3000);
        Serial.flush();
        delay(100);

        esp_sleep_enable_timer_wakeup(3 * 1000000ULL);
        esp_deep_sleep_start();
        // never reached — device resets
    }

    // Phase 2: woke from timer — ULP should have kept running
    Serial.printf("Phase 2: woke with cause=%d, sensor_count=%lu\n",
        (int)cause, (unsigned long)sensor_sensor_count);
    CHECK(cause == ESP_SLEEP_WAKEUP_TIMER);
    // ULP ran during 3s sleep with 100ms period → ~30 iterations
    CHECK(sensor_sensor_count > 1);
}

}
