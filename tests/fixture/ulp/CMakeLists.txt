cmake_minimum_required(VERSION 3.16)

# =============================================================================
# ULP RISC-V Project with External Libraries
#
# This CMakeLists.txt is compatible with both idf.py and PlatformIO builds.
# It uses the standard IDF ULP CMake API (IDFULPProject.cmake).
#
# Registered in platformio.ini with:
#   board_build.ulp_projects =
#       ulp_main:ulp
#
# See also: IDF examples/system/ulp/lp_core/build_system/
# =============================================================================

include(${IDF_PATH}/tools/cmake/idf.cmake)
project(${ULP_APP_NAME})
add_executable(${ULP_APP_NAME})

include(IDFULPProject)
ulp_apply_default_options(${ULP_APP_NAME})
ulp_apply_default_sources(${ULP_APP_NAME})

# ---------------------------------------------------------------------------
# Library support boilerplate
#
# ulp_apply_default_sources() sets IS_ULP_COCPU and ULP_RISCV_REGISTER_OPS on
# the executable target only. External libraries that use #ifdef guards for
# platform detection need these defines too. Similarly, libraries that include
# ULP SDK headers (ulp_riscv.h, ulp_riscv_gpio.h, etc.) need the ULP-specific
# include paths. COMPONENT_INCLUDES provides the full IDF SDK headers.
#
# This is identical to what you'd write in a native IDF ULP project that
# links external libraries — IDF's ulp_apply_default_sources() only applies
# to the executable target, not library targets.
# ---------------------------------------------------------------------------
set(ULP_PLATFORM_DEFINES IS_ULP_COCPU ULP_RISCV_REGISTER_OPS)

set(ULP_INCLUDE_DIRS
    "${IDF_PATH}/components/ulp/ulp_riscv/ulp_core/include"
    "${IDF_PATH}/components/ulp/ulp_riscv/shared/include"
    "${IDF_PATH}/components/ulp/ulp_riscv/include"
    "${IDF_PATH}/components/riscv/include"
    ${COMPONENT_INCLUDES}
)

# Base path for external libraries (relative to this file)
set(LIBS_DIR "${CMAKE_CURRENT_LIST_DIR}/../libs")

# ---- Project sources ----
target_sources(${ULP_APP_NAME} PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/main.c
    ${CMAKE_CURRENT_LIST_DIR}/ulp_app.c
)

# ---- External library: example_i2c ----
# Linked from the project's libs/ directory — no symlinks needed
add_library(example_i2c STATIC
    "${LIBS_DIR}/example_i2c/example_i2c.c"
)
target_include_directories(example_i2c PUBLIC "${LIBS_DIR}/example_i2c")
target_compile_definitions(example_i2c PRIVATE ${ULP_PLATFORM_DEFINES})
target_include_directories(example_i2c PRIVATE ${ULP_INCLUDE_DIRS})

# ---- External library: example_sensor ----
# Depends on example_i2c (demonstrates inter-library dependencies)
add_library(example_sensor STATIC
    "${LIBS_DIR}/example_sensor/example_sensor.c"
)
target_include_directories(example_sensor PUBLIC "${LIBS_DIR}/example_sensor")
target_compile_definitions(example_sensor PRIVATE ${ULP_PLATFORM_DEFINES})
target_include_directories(example_sensor PRIVATE ${ULP_INCLUDE_DIRS})
target_link_libraries(example_sensor PRIVATE example_i2c)

# Link libraries to the ULP executable
target_link_libraries(${ULP_APP_NAME} PRIVATE example_i2c example_sensor)

# ---- Subdirectory library (demonstrates add_subdirectory) ----
add_subdirectory(lib)
target_link_libraries(${ULP_APP_NAME} PRIVATE ulp_helpers)

# ---- Custom defines ----
target_compile_definitions(${ULP_APP_NAME} PRIVATE USE_RTC_I2C=0)

# Generate binary, header, and linker script for embedding into main app
ulp_add_build_binary_targets(${ULP_APP_NAME} PREFIX ${ULP_VAR_PREFIX})
