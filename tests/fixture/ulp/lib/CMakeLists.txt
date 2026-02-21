# Subdirectory library — proves add_subdirectory() works with PlatformIO ULP builds
add_library(ulp_helpers STATIC ulp_helpers.c)
target_include_directories(ulp_helpers PUBLIC "${CMAKE_CURRENT_LIST_DIR}")
