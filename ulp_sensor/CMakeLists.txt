cmake_minimum_required(VERSION 3.16)

include(${IDF_PATH}/tools/cmake/idf.cmake)
project(${ULP_APP_NAME})
add_executable(${ULP_APP_NAME})

include(IDFULPProject)
ulp_apply_default_options(${ULP_APP_NAME})
ulp_apply_default_sources(${ULP_APP_NAME})

target_sources(${ULP_APP_NAME} PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/sensor_main.c
)

target_compile_definitions(${ULP_APP_NAME} PRIVATE SENSOR_POLL_INTERVAL=100)

ulp_add_build_binary_targets(${ULP_APP_NAME} PREFIX ${ULP_VAR_PREFIX})
