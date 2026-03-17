# pio-ulp-cmake

[![CI](https://github.com/m-mcgowan/pio-ulp-cmake/actions/workflows/ci.yml/badge.svg)](https://github.com/m-mcgowan/pio-ulp-cmake/actions/workflows/ci.yml)

Standard ESP-IDF CMake ULP builds in PlatformIO — multiple binaries,
libraries, subdirectories, custom prefixes, incremental rebuilds. Works with
both `espressif32` and `pioarduino` platforms.

## Features

- **IDF Native CMakeLists.txt** — `add_library()`, `add_subdirectory()`,
  `target_link_libraries()`, `target_compile_definitions()`, and
  `target_include_directories()` all work
- **Multiple ULP binaries** — build several ULP programs in one firmware,
  each with its own name and symbol prefix
- **External library linking** — link static C libraries into ULP code, or
  organize with `add_subdirectory()`
- **All coprocessor types** — ULP RISC-V, LP Core, and FSM via IDF's own
  `IDFULPProject.cmake`
- **Incremental rebuilds** — SCons dependency tracking via
  `compile_commands.json`
- **IDF examples build unmodified** — CI compiles 7 official ESP-IDF ULP
  examples with no source changes, only a PlatformIO directory layout
- **espressif32 and pioarduino** — tested in CI against both

**Requires ESP-IDF >= 5.4** (stock espressif32 >= 6.10.0, pioarduino >= 54.x).
ESP-IDF 5.4 introduced `IDFULPProject.cmake`, the standard CMake API for ULP builds.

## Quick start

**1. Add to your project**

```ini
; platformio.ini
[env:my-ulp-project]
platform = espressif32          ; or pioarduino release URL
board = ...;
framework = arduino, espidf     ; or just espidf

lib_deps =
    https://github.com/m-mcgowan/pio-ulp-cmake.git

extra_scripts =
    pre:${PROJECT_LIBDEPS_DIR}/${PIOENV}/pio-ulp-cmake/scripts/pio_ulp_cmake.py

board_build.ulp_projects =
    ulp_main:ulp   ; name:dir[:prefix]
```

Each entry under `board_build.ulp_projects` is `name:dir[:prefix]` — the
binary name, the directory containing your CMakeLists.txt, and an optional
symbol prefix (defaults to `ulp_`).

**2. Write a CMakeLists.txt** in `ulp/`

```cmake
cmake_minimum_required(VERSION 3.16)

include(${IDF_PATH}/tools/cmake/idf.cmake)
project(${ULP_APP_NAME})
add_executable(${ULP_APP_NAME})

include(IDFULPProject)
ulp_apply_default_options(${ULP_APP_NAME})
ulp_apply_default_sources(${ULP_APP_NAME})

target_sources(${ULP_APP_NAME} PRIVATE main.c)

ulp_add_build_binary_targets(${ULP_APP_NAME} PREFIX ${ULP_VAR_PREFIX})
```

This is the same CMakeLists.txt you'd write in a plain ESP-IDF project.

**3. Use ULP symbols in firmware**

```cpp
#include "ulp_main.h"

extern const uint8_t ulp_main_bin_start[] asm("_binary_ulp_main_bin_start");
extern const uint8_t ulp_main_bin_end[]   asm("_binary_ulp_main_bin_end");

void app_main(void) {
    ulp_riscv_load_binary(ulp_main_bin_start,
        ulp_main_bin_end - ulp_main_bin_start);
    ulp_riscv_run();
    printf("state: %lu\n", (unsigned long)ulp_app_state);
}
```

**4. Enable ULP in sdkconfig.defaults**

```
CONFIG_ULP_COPROC_ENABLED=y
CONFIG_ULP_COPROC_TYPE_RISCV=y
CONFIG_ULP_COPROC_RESERVE_MEM=4096
```

## Configuration reference

### ULP project entries

```
name:dir[:prefix]
```

| Field    | Description                                          | Example        |
|----------|------------------------------------------------------|----------------|
| `name`   | ULP binary name (used for `.bin`, `.h`, `.ld` files) | `ulp_main`     |
| `dir`    | Directory containing `CMakeLists.txt`, relative to project root | `ulp` |
| `prefix` | Symbol prefix for the generated header (default: `ulp_`). The trailing underscore optional, but advised. | `sensor_`  |

Multiple binaries:

```ini
board_build.ulp_projects =
    ulp_main:ulp
    ulp_sensor:ulp_sensor:sensor_
```

### Linking external libraries

Same pattern as IDF's own
[build_system example](https://github.com/espressif/esp-idf/tree/master/examples/system/ulp/lp_core/build_system):

```cmake
add_library(my_lib STATIC path/to/source.c)
target_include_directories(my_lib PUBLIC path/to/include)
target_link_libraries(${ULP_APP_NAME} PRIVATE my_lib)
```

### Installation alternatives

If you prefer not to use `lib_deps`, copy `scripts/pio_ulp_cmake.py` into
your project and reference it directly:

```ini
extra_scripts = pre:scripts/pio_ulp_cmake.py
```

## Background

PlatformIO's built-in ULP builder (`ulp.py` in the
[pioarduino platform](https://github.com/pioarduino/platform-espressif32))
collects `.c` and `.S` files with a flat glob and passes them directly to
CMake's generic ULP entry point. Your project's CMakeLists.txt is not used.
This means `add_library()`, `add_subdirectory()`, `target_link_libraries()`,
multiple binaries, and custom symbol prefixes are not available. This was
[reported upstream](https://github.com/platformio/platform-espressif32/issues/940) but not addressed.

ESP-IDF's own build system supports all of these through `ulp_add_project()`
and standard CMake — see the
[lp_core/build_system](https://github.com/espressif/esp-idf/tree/master/examples/system/ulp/lp_core/build_system)
example. This tool brings that same capability to PlatformIO.

## How it works

The tool is a hybrid SCons/CMake bridge. For each registered ULP project, it:

1. Runs `cmake -S <your_ulp_dir>` using your CMakeLists.txt
2. Builds the ULP binary via Ninja
3. Generates a `.bin.S` assembly file that embeds the binary into firmware
4. Adds the generated header and linker script to the main build

It delegates all coprocessor-specific behavior to IDF's own
`IDFULPProject.cmake` — no ULP logic is replicated. The same CMakeLists.txt
works for RISC-V, LP Core, and FSM.

<details>
<summary>Internals</summary>

The tool runs as a `pre:` extra_scripts, before PlatformIO's framework
builder (`espidf.py`):

1. **Intercepts the stock ULP builder.** Monkey-patches `env.SConscript` to
   skip the stock `ulp.py` call.

2. **Resolves component includes at build time.** ULP code needs IDF
   component headers (`soc/*.h`, `hal/*.h`, etc.). The tool reads the CMake
   API reply from `.cmake/api/v1/reply/` at build time; on the first clean
   build it falls back to scanning the IDF `components/` directory.

3. **Registers SCons dependencies.** Parses `compile_commands.json` so that
   touching any ULP source triggers an incremental rebuild.

4. **Compiles and links assembly.** Each ULP binary is converted to `.bin.S`,
   compiled to `.o`, and linked into firmware with `-T` linker scripts.

</details>

## Compatibility

### Tested platforms

Backward compatible across ESP-IDF 5.4–5.5 (requires `IDFULPProject.cmake`,
introduced in ESP-IDF 5.4). CI tests every push against stock and pioarduino
platforms, each in an isolated `PLATFORMIO_CORE_DIR`.

| Platform | Version | ESP-IDF | Status |
|----------|---------|---------|--------|
| pioarduino | `55.03.37` | 5.5.2 | Tested in CI |
| pioarduino | `54.03.21-2` | 5.4.2 | Tested in CI |
| stock espressif32 | `6.13.0` | 5.5.3 | Tested in CI |
| stock espressif32 | `6.12.0` | 5.5.0 | Tested in CI |
| stock espressif32 | `6.10.0` | 5.4.0 | Tested in CI |

### IDF example coverage

CI builds 7 official ESP-IDF ULP examples on every push. The examples are
copied verbatim from `framework-espidf` by `scripts/sync_examples.sh` — no
`.c`, `.S`, or `.h` files are modified. The only adaptation is the directory
layout (IDF's `main/` becomes PIO's `src/`) and a generated `platformio.ini`.

| Example | Coprocessor | Board | What it validates |
|---------|------------|-------|-------------------|
| `ulp_fsm` | FSM assembly | ESP32 | Multi-file `.S` without CMakeLists.txt |
| `ulp_riscv_gpio` | RISC-V | ESP32-S3 | Basic RISC-V ULP build |
| `ulp_riscv_i2c` | RISC-V | ESP32-S3 | Shared header between HP and ULP code |
| `lp_core_gpio` | LP Core | ESP32-C6 | Standard LP Core build |
| `lp_core_build_system` | LP Core | ESP32-C6 | Custom CMakeLists.txt + static library |
| `lp_core_interrupt` | LP Core | ESP32-C6 | Alternative app name (`lp_core_main`) |
| `lp_core_uart_print` | LP Core | ESP32-C6 | LP UART with different source nesting |

The only layout changes (no source modifications):

- `main/*.c` -> `src/*.c`
- `main/ulp/` or `main/lp_core/` -> `ulp/`
- Shared headers referenced as `../header.h` -> project root

## Test fixture

The integration test fixture at `tests/fixture/` exercises the features that
IDF examples don't cover: multiple binaries, symbol prefixes, external
libraries, and subdirectory organization.

```
tests/fixture/
├── platformio.ini          # Two ULP projects: ulp_main + ulp_sensor
├── src/main.cpp            # Firmware that loads both ULP binaries
├── ulp/                    # First ULP project (default ulp_ prefix)
│   ├── CMakeLists.txt      #   Links external libs + subdirectory lib
│   ├── main.c
│   └── lib/                #   Subdirectory library (add_subdirectory)
├── ulp_sensor/             # Second ULP project (sensor_ prefix)
│   └── sensor_main.c
└── libs/                   # External libraries (add_library)
    ├── example_i2c/
    └── example_sensor/
```

The test suite (`tests/test_ulp_cmake.sh`) runs 7 build-only tests: clean
build, artifact verification, symbol prefix namespacing, external library
linking, firmware symbol linkage, incremental dependency tracking, and single
vs multi-project mode. On-device tests verify ULP binary loading, shared
variable updates, and deep sleep survival on real hardware.

## Running tests

```bash
# Integration tests — specify the platform to test against
PLATFORMIO_CORE_DIR=/tmp/pio-test \
  ./tests/test_ulp_cmake.sh -v -p 'espressif32@6.13.0'

# Local CI — sync examples from framework and build all of them
./scripts/ci.sh                           # all examples, latest platform
./scripts/ci.sh 55.03.37 ulp_riscv_gpio  # one example, specific version
./scripts/ci.sh --list                    # list available examples
```

## Project structure

```
pio-ulp-cmake/
├── scripts/
│   ├── pio_ulp_cmake.py           # The build tool
│   ├── sync_examples.sh           # Generates examples/ from framework-espidf
│   └── ci.sh                      # Local CI runner (builds all examples)
├── examples/                      # Generated on demand (gitignored)
└── tests/
    ├── test_ulp_cmake.sh          # Integration tests (7 tests)
    └── fixture/                   # Multi-project test harness
```

## Integrated mode (for platform maintainers)

If merged into the pioarduino platform, the tool can be called directly from
`ulp.py` instead of running as an extra_script:

```python
from pio_ulp_cmake import integrated_main
integrated_main(env, sdk_config, project_config, app_includes, idf_variant)
```

| Parameter        | Description |
|------------------|-------------|
| `env`            | SCons environment |
| `sdk_config`     | Dict of sdkconfig values (keys without `CONFIG_` prefix) |
| `project_config` | CMake API reply target config for the main app |
| `app_includes`   | Dict with `plain_includes` list from the framework |
| `idf_variant`    | MCU variant string (e.g. `"esp32s3"`) |

In integrated mode, `board_build.ulp_projects` defines the builds. Without
it, the tool falls back to legacy single-project behavior using
`board_build.ulp_dir` (default `"ulp"`) with binary name `ulp_main`.

Users configure `platformio.ini` the same way, minus the `extra_scripts`
line.
