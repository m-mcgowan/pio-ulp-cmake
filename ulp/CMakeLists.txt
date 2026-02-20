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

# ---- Project sources ----
target_sources(${ULP_APP_NAME} PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/main.c
    ${CMAKE_CURRENT_LIST_DIR}/ulp_app.c
)

# ---- External library: elert_c_bmx160 ----
# Linked directly from the shared collar library — no symlinks needed
set(BMX160_DIR "${CMAKE_CURRENT_LIST_DIR}/../../collar/lib/elert_c_bmx160/src")
add_library(elert_bmx160 STATIC
    "${BMX160_DIR}/bmx160.c"
)
target_include_directories(elert_bmx160 PUBLIC "${BMX160_DIR}")
target_compile_definitions(elert_bmx160 PRIVATE ${ULP_PLATFORM_DEFINES} BMX160_FLOAT_OPS=0)
target_include_directories(elert_bmx160 PRIVATE ${ULP_INCLUDE_DIRS})

# ---- External library: elert_c_i2c ----
set(I2C_DIR "${CMAKE_CURRENT_LIST_DIR}/../../collar/lib/elert_c_i2c/src")
add_library(elert_i2c STATIC
    "${I2C_DIR}/elert_i2c_simple.c"
    "${I2C_DIR}/elert_i2c_lock.c"
    "${I2C_DIR}/soft_i2c_simple.c"
    "${I2C_DIR}/soft_i2c_ulp.c"
)
target_include_directories(elert_i2c PUBLIC "${I2C_DIR}")
target_compile_definitions(elert_i2c PRIVATE ${ULP_PLATFORM_DEFINES})
target_include_directories(elert_i2c PRIVATE ${ULP_INCLUDE_DIRS})

# bmx160 depends on i2c headers (bmx160.h includes elert_i2c.h)
target_link_libraries(elert_bmx160 PRIVATE elert_i2c)

# Link libraries to the ULP executable
target_link_libraries(${ULP_APP_NAME} PRIVATE elert_bmx160 elert_i2c)

# ---- Subdirectory library (proves add_subdirectory works) ----
add_subdirectory(lib)
target_link_libraries(${ULP_APP_NAME} PRIVATE ulp_helpers)

# ---- Custom defines ----
target_compile_definitions(${ULP_APP_NAME} PRIVATE USE_RTC_I2C=0)

# Generate binary, header, and linker script for embedding into main app
ulp_add_build_binary_targets(${ULP_APP_NAME} PREFIX ${ULP_VAR_PREFIX})
