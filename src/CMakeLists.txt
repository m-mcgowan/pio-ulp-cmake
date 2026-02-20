FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.*)

idf_component_register(SRCS ${app_sources})

# NOTE: When using pio_ulp_cmake.py (via extra_scripts), do NOT call
# ulp_add_project() here — the tool handles ULP building, embedding,
# and linking. For native IDF builds (idf.py), uncomment these:
#
# ulp_add_project("ulp_main" "${CMAKE_SOURCE_DIR}/ulp")
