# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-02-20

### Added

- Initial release of `pio_ulp_cmake.py`
- Standalone mode via `extra_scripts = pre:scripts/pio_ulp_cmake.py`
- Integrated mode API for platform package maintainers (`integrated_main()`)
- Multiple ULP binary support via `board_build.ulp_projects`
- Custom symbol prefix per ULP project to avoid collisions
- Full CMakeLists.txt support: `add_library()`, `add_subdirectory()`,
  `target_compile_definitions()`, `target_include_directories()`
- SCons dependency tracking via `compile_commands.json`
- Component include resolution from CMake API reply with fallback
- Test project with two ULP programs (ESP32-S3 RISC-V)
- Integration test suite (`tests/test_ulp_cmake.sh`)
