# pio_ulp_cmake — Custom ULP CMake Build Support for PlatformIO

## Why this exists

PlatformIO's built-in ULP builder (`ulp.py` in the pioarduino platform
package) has significant limitations:

- **No CMakeLists.txt support.** It ignores any `CMakeLists.txt` in the ULP
  directory. Instead, it flat-globs all `*.c` and `*.S` files and passes them
  to CMake via `-DULP_S_SOURCES`. You can't use `add_library()`,
  `add_subdirectory()`, or `target_compile_definitions()`.

- **No external libraries.** Linking a shared library (e.g. an I2C driver
  used by both the MCU and the ULP) requires symlinking sources into the ULP
  directory. There's no way to use `target_link_libraries()`.

- **Single binary only.** The binary name is hardcoded to `ulp_main`. There's
  no way to build multiple ULP programs in one project, which is needed when
  different coprocessor tasks need separate binaries.

- **No symbol prefixes.** All exported ULP variables use the `ulp_` prefix.
  If two ULP binaries export a variable with the same name (e.g. `count`),
  they collide.

ESP-IDF's native build system (`idf.py`) supports all of this through
`ulp_add_project()` and standard CMake. `pio_ulp_cmake.py` brings that
capability to PlatformIO.

## What it does

`pio_ulp_cmake.py` is a hybrid SCons/CMake build tool. It lets you write
standard IDF-compatible `CMakeLists.txt` files for your ULP projects while
PlatformIO's SCons build system handles dependency tracking, assembly
embedding, and firmware linking.

For each registered ULP project, it:

1. Runs `cmake -S <your_ulp_dir>` using your CMakeLists.txt as the source
2. Runs `cmake --build` to compile the ULP binary via Ninja
3. Generates an assembly file (`.bin.S`) that embeds the binary into firmware
4. Adds the generated header (`.h`) and linker script (`.ld`) to the main
   build so firmware code can reference ULP variables

### What this enables

- **`add_library()` + `target_link_libraries()`** — link external C libraries
  into ULP code without symlinks
- **`add_subdirectory()`** — organize ULP code into subdirectories
- **`target_compile_definitions()`** — per-target compile flags
- **`target_include_directories()`** — per-target include paths
- **Multiple ULP binaries** — each with its own prefix to avoid symbol
  collisions
- **SCons dependency tracking** — changes to ULP sources trigger incremental
  rebuilds via `compile_commands.json`

## Usage (standalone mode)

This is the current way to use the tool with the stock pioarduino platform.
No platform patches required.

### 1. Add the script to your project

Copy `scripts/pio_ulp_cmake.py` into your project (e.g. under `scripts/`).

### 2. Configure `platformio.ini`

```ini
[env:esp32s3-idf]
platform = espressif32
board = esp32-s3-devkitc-1
framework = espidf

extra_scripts = pre:scripts/pio_ulp_cmake.py

board_build.ulp_projects =
    ulp_main:ulp
    ulp_sensor:ulp_sensor:sensor_
```

Each line under `board_build.ulp_projects` has the format:

```
name:dir[:prefix]
```

| Field    | Description                                          | Example        |
|----------|------------------------------------------------------|----------------|
| `name`   | ULP binary name (used for `.bin`, `.h`, `.ld` files) | `ulp_main`     |
| `dir`    | Directory containing `CMakeLists.txt`, relative to project root | `ulp` |
| `prefix` | Symbol prefix for the generated header (default: `ulp_`) | `sensor_`  |

### 3. Write your ULP CMakeLists.txt

Each ULP directory needs a standard IDF-compatible `CMakeLists.txt`. Minimal
example:

```cmake
cmake_minimum_required(VERSION 3.16)

include(${IDF_PATH}/tools/cmake/idf.cmake)
project(${ULP_APP_NAME})
add_executable(${ULP_APP_NAME})

include(IDFULPProject)
ulp_apply_default_options(${ULP_APP_NAME})
ulp_apply_default_sources(${ULP_APP_NAME})

target_sources(${ULP_APP_NAME} PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/main.c
)

ulp_add_build_binary_targets(${ULP_APP_NAME} PREFIX ${ULP_VAR_PREFIX})
```

The variables `${ULP_APP_NAME}` and `${ULP_VAR_PREFIX}` are passed by the
tool based on your `platformio.ini` configuration.

For projects that link external libraries, you need to propagate ULP platform
defines and includes to library targets (IDF only applies them to the
executable):

```cmake
# Defines needed by libraries that use #ifdef IS_ULP_COCPU guards
set(ULP_PLATFORM_DEFINES IS_ULP_COCPU ULP_RISCV_REGISTER_OPS)

# Include paths needed by libraries that use ULP SDK headers
set(ULP_INCLUDE_DIRS
    "${IDF_PATH}/components/ulp/ulp_riscv/ulp_core/include"
    "${IDF_PATH}/components/ulp/ulp_riscv/shared/include"
    "${IDF_PATH}/components/ulp/ulp_riscv/include"
    "${IDF_PATH}/components/riscv/include"
    ${COMPONENT_INCLUDES}
)

add_library(my_lib STATIC path/to/source.c)
target_compile_definitions(my_lib PRIVATE ${ULP_PLATFORM_DEFINES})
target_include_directories(my_lib PRIVATE ${ULP_INCLUDE_DIRS})
target_link_libraries(${ULP_APP_NAME} PRIVATE my_lib)
```

### 4. Do NOT call `ulp_add_project()` in `src/CMakeLists.txt`

When using `pio_ulp_cmake.py`, the tool handles all ULP building, assembly
embedding, and linker script addition. If your `src/CMakeLists.txt` also
calls `ulp_add_project()`, you'll get duplicate symbol errors.

```cmake
# src/CMakeLists.txt
FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.*)
idf_component_register(SRCS ${app_sources})

# Do NOT uncomment when using pio_ulp_cmake.py:
# ulp_add_project("ulp_main" "${CMAKE_SOURCE_DIR}/ulp")
```

### 5. Reference ULP symbols in firmware code

```cpp
#include "ulp_main.h"    // Generated header with ulp_ prefixed symbols
#include "ulp_sensor.h"  // Generated header with sensor_ prefixed symbols

// Binary data for loading
extern const uint8_t ulp_main_bin_start[] asm("_binary_ulp_main_bin_start");
extern const uint8_t ulp_main_bin_end[]   asm("_binary_ulp_main_bin_end");

void app_main(void) {
    ulp_riscv_load_binary(ulp_main_bin_start,
        ulp_main_bin_end - ulp_main_bin_start);
    ulp_riscv_run();

    // Read shared variables
    printf("app_state: %lu\n", (unsigned long)ulp_app_state);
    printf("sensor: %lu\n", (unsigned long)sensor_sensor_value);
}
```

### 6. Enable ULP in `sdkconfig.defaults`

```
CONFIG_ULP_COPROC_ENABLED=y
CONFIG_ULP_COPROC_TYPE_RISCV=y
CONFIG_ULP_COPROC_RESERVE_MEM=7500
```

## How it works internally

The tool operates as a `pre:` extra_scripts, which means it executes before
PlatformIO's framework builder (`espidf.py`). It:

1. **Intercepts the stock ULP builder.** The stock `espidf.py` calls
   `env.SConscript("ulp.py")` when it finds a `ulp/` directory. The tool
   monkey-patches `env.SConscript` to skip that call, preventing the stock
   builder from running.

2. **Resolves component includes at build time.** ULP code needs IDF
   component headers (`soc/*.h`, `hal/*.h`, etc.). The full resolved include
   list is only available from the CMake API reply, which doesn't exist until
   after the main cmake runs. The tool defers include resolution to the SCons
   build action (not parse time), where it reads the API reply from
   `.cmake/api/v1/reply/`. On the very first clean build, it falls back to
   scanning the IDF `components/` directory.

3. **Registers SCons dependencies from `compile_commands.json`.** After cmake
   configure, the tool parses `compile_commands.json` to discover all source
   files involved in the ULP build. These are registered as SCons
   dependencies so that touching any ULP source triggers an incremental
   rebuild.

4. **Compiles and links assembly.** Each ULP binary gets converted to a
   `.bin.S` assembly file (via IDF's `data_file_embed_asm.cmake`), compiled
   to a `.o`, and added to the firmware link. Linker scripts are added via
   `-T` flags.

## Integrated mode (for platform package maintainers)

If this tool is merged into the pioarduino platform package, it can be called
directly from `ulp.py` instead of running as an extra_script. This avoids
the SConscript interception and gets component includes from the framework
context directly.

In `ulp.py`, replace the existing ULP build logic with:

```python
from pio_ulp_cmake import integrated_main

# ... existing ulp.py setup that resolves sdk_config, project_config,
#     app_includes, idf_variant ...

integrated_main(env, sdk_config, project_config, app_includes, idf_variant)
```

The `integrated_main()` function accepts the framework context that `ulp.py`
already has:

| Parameter        | Description |
|------------------|-------------|
| `env`            | SCons environment |
| `sdk_config`     | Dict of sdkconfig values (keys without `CONFIG_` prefix) |
| `project_config` | CMake API reply target config for the main app |
| `app_includes`   | Dict with `plain_includes` list from the framework |
| `idf_variant`    | MCU variant string (e.g. `"esp32s3"`) |

In integrated mode:

- If `board_build.ulp_projects` is set, those projects are built
- Otherwise, it falls back to the legacy single-project behavior using
  `board_build.ulp_dir` (default `"ulp"`) with binary name `ulp_main`
- Component includes come from the framework context rather than parsing
  the CMake API reply

Users would configure their `platformio.ini` identically but without the
`extra_scripts` line:

```ini
[env:esp32s3-idf]
platform = espressif32
board = esp32-s3-devkitc-1
framework = espidf

board_build.ulp_projects =
    ulp_main:ulp
    ulp_sensor:ulp_sensor:sensor_
```

## Project structure

```
project/
├── platformio.ini              # Platform config + ULP project registration
├── sdkconfig.defaults          # ULP coprocessor enabled
├── CMakeLists.txt              # Top-level IDF cmake (standard)
├── scripts/
│   └── pio_ulp_cmake.py        # This tool
├── src/
│   ├── CMakeLists.txt          # idf_component_register (no ulp_add_project)
│   └── main.cpp                # Firmware code referencing ULP symbols
├── ulp/                        # First ULP project
│   ├── CMakeLists.txt          # Full cmake with add_library, etc.
│   ├── main.c
│   └── lib/                    # Subdirectory library
│       ├── CMakeLists.txt
│       └── helpers.c
├── ulp_sensor/                 # Second ULP project
│   ├── CMakeLists.txt
│   └── sensor_main.c
└── tests/
    └── test_ulp_cmake.sh       # Integration tests
```

## Running tests

```bash
./tests/test_ulp_cmake.sh       # run all tests
./tests/test_ulp_cmake.sh -v    # verbose — show build output on failure
```

The test suite does real PlatformIO builds (clean + incremental) and verifies
artifacts, symbols, prefix namespacing, external library linking, dependency
tracking, and single vs multi-project modes. See the test file header for
detailed descriptions of each test.

Requires PlatformIO with the `espressif32` platform and RISC-V/Xtensa
toolchains installed.
