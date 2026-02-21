# pio_ulp_cmake — Full CMake ULP Builds for PlatformIO

## Why this exists

PlatformIO's built-in ULP builder (`ulp.py` in the
[pioarduino platform](https://github.com/pioarduino/platform-espressif32))
does not use your project's CMakeLists.txt. It bypasses CMake's project model
entirely, which means several standard ESP-IDF build features don't work.

### What the stock builder does

The stock `ulp.py` collects all `.c` and `.S` files from the `ulp/` directory
with a flat glob and passes them as a semicolon-separated list to CMake's
generic ULP entry point:

```python
# ulp.py — collect_ulp_sources()
return [
    str(Path(ulp_env.subst("$PROJECT_DIR")) / "ulp" / f)
    for f in os.listdir(str(Path(ulp_env.subst("$PROJECT_DIR")) / "ulp"))
    if f.endswith((".c", ".S", ".s"))
]
```

```python
# ulp.py — generate_ulp_config()
"-DULP_S_SOURCES=%s" % ";".join([...]),
"-DULP_APP_NAME=ulp_main",
"-DCOMPONENT_DIR=" + str(Path(ulp_env.subst("$PROJECT_DIR")) / "ulp"),
```

Your CMakeLists.txt is never read. CMake is invoked with `-B <build_dir>
<idf_components>/ulp/cmake` — the IDF's generic cmake directory is the
source, not your project.

### What doesn't work

**No CMakeLists.txt support.** Any `CMakeLists.txt` in your ULP directory is
ignored. You can't use `add_library()`, `add_subdirectory()`,
`target_link_libraries()`, `target_compile_definitions()`, or
`target_include_directories()`. If your ULP code needs a static library or
has subdirectories, you're stuck.

**Hardcoded single binary.** The app name `ulp_main` and all output filenames
(`ulp_main.h`, `ulp_main.ld`, `ulp_main.bin`, `ulp_main.bin.S`) are
hardcoded. There is no way to build multiple ULP programs in one project.

**Hardcoded source directory.** The ULP source directory is hardcoded to
`ulp/`. LP Core examples that use `lp_core/` as their source directory
require renaming.

**No symbol prefix control.** All exported ULP variables get the `ulp_`
prefix. If you could build two ULP binaries (you can't, but hypothetically),
variables with the same name would collide.

### What ESP-IDF supports natively

ESP-IDF's own build system handles all of this through `ulp_add_project()`
and standard CMake. The
[lp_core/build_system](https://github.com/espressif/esp-idf/tree/master/examples/system/ulp/lp_core/build_system)
example demonstrates `add_library()`, `target_link_libraries()`, and custom
CMakeLists.txt — none of which work with PlatformIO's stock builder.

`pio_ulp_cmake.py` brings that capability to PlatformIO.

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

Linking external libraries follows the same pattern as IDF's own
[build_system example](https://github.com/espressif/esp-idf/tree/master/examples/system/ulp/lp_core/build_system) —
just `add_library()` and `target_link_libraries()`:

```cmake
add_library(my_lib STATIC path/to/source.c)
target_include_directories(my_lib PUBLIC path/to/include)
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

### 6. Enable ULP in sdkconfig

Create `sdkconfig.<env>` (where `<env>` matches your `[env:name]` in
platformio.ini):

```
CONFIG_ULP_COPROC_ENABLED=y
CONFIG_ULP_COPROC_TYPE_RISCV=y
CONFIG_ULP_COPROC_RESERVE_MEM=4096
```

## Design principle

This project does **not** replicate or copy any part of ESP-IDF's ULP build
logic. All coprocessor-specific behavior — include paths, platform defines,
startup files, linker scripts, toolchain selection — is inferred from IDF's
own CMake implementation (`IDFULPProject.cmake`). The same CMakeLists.txt
works for ULP RISC-V, LP Core, and FSM without any coprocessor-specific
hardcoding in the build tool or project templates.

Similarly, toolchain PATH setup is delegated to PlatformIO's
`LoadPioPlatform()`, which already adds all installed toolchain packages to
`os.environ['PATH']`.

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

## Compatibility validation

The `examples/` directory proves that `pio_ulp_cmake.py` compiles
**unmodified ESP-IDF ULP examples**. Every `.c`, `.S`, and `.h` file is
byte-for-byte identical to the original in the `framework-espidf` package.

`scripts/sync_examples.sh` copies sources from the installed framework into
PlatformIO's project layout. Each example becomes a self-contained PIO
project with its own `platformio.ini` and `sdkconfig.<env>`. No source files
are patched.

| Example | Coprocessor | Board | What it validates |
|---------|------------|-------|-------------------|
| `ulp_fsm` | FSM assembly | ESP32 | Multi-file `.S` without CMakeLists.txt |
| `ulp_riscv_gpio` | RISC-V | ESP32-S3 | Basic RISC-V ULP build |
| `ulp_riscv_i2c` | RISC-V | ESP32-S3 | Shared header between HP and ULP code |
| `lp_core_gpio` | LP Core | ESP32-C6 | Standard LP Core build |
| `lp_core_build_system` | LP Core | ESP32-C6 | Custom CMakeLists.txt + static library |
| `lp_core_interrupt` | LP Core | ESP32-C6 | Alternative app name (`lp_core_main`) |
| `lp_core_uart_print` | LP Core | ESP32-C6 | LP UART with different source nesting |

```bash
# Sync examples from installed framework-espidf
./scripts/sync_examples.sh

# Build all examples
for d in examples/*/; do (cd "$d" && pio run); done

# Or build one
cd examples/lp_core_build_system && pio run
```

The only layout adaptations (handled by the sync script, not by modifying
sources):

- IDF's `main/*.c` goes to PIO's `src/*.c`
- IDF's `main/ulp/` or `main/lp_core/` goes to `ulp/`
- Shared headers referenced as `../header.h` from ULP sources are placed at
  the project root

## Project structure

```
pio-ulp-cmake/
├── scripts/
│   ├── pio_ulp_cmake.py           # The build tool
│   └── sync_examples.sh           # Syncs ESP-IDF examples into examples/
├── examples/                      # Verbatim ESP-IDF examples as PIO projects
│   ├── ulp_fsm/                   # FSM assembly (ESP32)
│   ├── ulp_riscv_gpio/            # RISC-V GPIO (ESP32-S3)
│   ├── ulp_riscv_i2c/             # RISC-V I2C (ESP32-S3)
│   ├── lp_core_gpio/              # LP Core GPIO (ESP32-C6)
│   ├── lp_core_build_system/      # LP Core + custom CMake (ESP32-C6)
│   ├── lp_core_interrupt/         # LP Core interrupt (ESP32-C6)
│   └── lp_core_uart_print/        # LP Core UART (ESP32-C6)
└── tests/
    ├── test_ulp_cmake.sh          # Integration tests
    └── fixture/                   # Multi-project test harness
        ├── platformio.ini
        ├── src/main.cpp
        ├── ulp/                   # First ULP project (with subdirectory lib)
        ├── ulp_sensor/            # Second ULP project (sensor_ prefix)
        └── libs/                  # External libraries linked into ULP
```

Each example project follows standard PIO layout:

```
examples/ulp_riscv_gpio/
├── platformio.ini                 # References ../../scripts/pio_ulp_cmake.py
├── sdkconfig.esp32s3-riscv-gpio   # ULP coprocessor settings
├── src/
│   └── ulp_riscv_example_main.c   # Verbatim from ESP-IDF
└── ulp/
    └── main.c                     # Verbatim from ESP-IDF
```

## Running tests

```bash
# Integration tests (multi-project builds, symbol prefixes, external libs)
./tests/test_ulp_cmake.sh       # run all tests
./tests/test_ulp_cmake.sh -v    # verbose — show build output on failure
```

The test suite does real PlatformIO builds (clean + incremental) and verifies
artifacts, symbols, prefix namespacing, external library linking, dependency
tracking, and single vs multi-project modes. See the test file header for
detailed descriptions of each test.

Requires PlatformIO with the `espressif32` platform and RISC-V/Xtensa
toolchains installed.
