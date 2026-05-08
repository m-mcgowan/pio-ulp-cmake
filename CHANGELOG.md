# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Bootloader-link race when ULP linker scripts leaked into the
  bootloader's environment via `env.Clone()` in pioarduino's
  `build_bootloader`. The leak was a direct hard-fail
  ("cannot open linker script file") on clean `arduino, espidf` builds
  and an incremental-rebuild race on `espidf`-only builds, the latter
  surviving an obvious strip workaround because SCons `MergeFlags`
  deduplicates equal LINKFLAGS strings and orphans one ULP path. The
  fix moves `-T <ulp_*.ld>` flags off the parent env entirely and
  applies them via a PreAction on `${PROGNAME}.elf`, so cloned envs
  never inherit them. Added Test 9 (espidf-only) alongside the
  pre-existing Test 8 (arduino+espidf) to regression-check the
  bootloader link command.

## [0.1.0] - 2026-03-17

### Added

- `pio_ulp_cmake.py` build script for ULP RISC-V binaries with PlatformIO
- Standalone mode via `extra_scripts = pre:scripts/pio_ulp_cmake.py`
- Integrated mode API for platform package maintainers (`integrated_main()`)
- Installable as a PlatformIO library via `lib_deps`
- Multiple ULP binary support via `board_build.ulp_projects`
- Custom symbol prefix per ULP project to avoid collisions
- Full CMakeLists.txt support: `add_library()`, `add_subdirectory()`,
  `target_compile_definitions()`, `target_include_directories()`
- SCons dependency tracking via `compile_commands.json`
- Component include resolution from CMake API reply with fallback
- Fallback to system cmake/ninja when PIO packages unavailable
- Support for both stock espressif32 and pioarduino platforms
- ESP-IDF example compatibility — all IDF ULP examples build unmodified
- On-device test suite with ULP load, run, and deep sleep verification
- CI across multiple platform versions (pioarduino 55.03.37, 54.03.21-2, stock 6.13.0)
- Release script (`scripts/release.sh`)
