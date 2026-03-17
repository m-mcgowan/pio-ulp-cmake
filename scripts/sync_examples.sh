#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mat McGowan
# SPDX-License-Identifier: MIT
#
# sync_examples.sh — Create self-contained PIO projects from ESP-IDF ULP examples
#
# Each example becomes its own PlatformIO project under examples/ with:
#   platformio.ini    — references shared pio_ulp_cmake.py
#   sdkconfig.defaults — ULP coprocessor settings from the IDF example (verbatim)
#   src/<main>.c      — verbatim HP main from IDF example
#   ulp/              — verbatim ULP coprocessor sources from IDF example
#
# No source file contents are modified. The only adaptation is the directory
# layout (PIO project structure) and the platformio.ini configuration.
#
# Usage:
#   ./scripts/sync_examples.sh [--framework-dir PATH] [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Parse arguments ---
FRAMEWORK_DIR=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --framework-dir) FRAMEWORK_DIR="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# --- Auto-detect framework path ---
if [[ -z "$FRAMEWORK_DIR" ]]; then
    FRAMEWORK_DIR="${PLATFORMIO_CORE_DIR:-$HOME/.platformio}/packages/framework-espidf"
fi

if [[ ! -d "$FRAMEWORK_DIR/examples/system/ulp" ]]; then
    echo "Error: framework-espidf not found at $FRAMEWORK_DIR" >&2
    echo "Install it with: pio pkg install -g -p espressif32" >&2
    exit 1
fi

IDF_ULP="$FRAMEWORK_DIR/examples/system/ulp"
EXAMPLES_DIR="$PROJECT_DIR/examples"

# --- Helpers ---
copy_file() {
    local src="$1" dst="$2"
    if $DRY_RUN; then
        echo "  [dry-run] $(basename "$dst")"
        return
    fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
}

copy_tree() {
    local src="$1" dst="$2"
    if $DRY_RUN; then
        echo "  [dry-run] $(basename "$dst")/"
        return
    fi
    mkdir -p "$dst"
    cp -R "$src/." "$dst/"
}

write_file() {
    local dst="$1"
    shift
    if $DRY_RUN; then
        echo "  [dry-run] $(basename "$dst")"
        return
    fi
    mkdir -p "$(dirname "$dst")"
    printf '%s\n' "$@" > "$dst"
}

# Create a PIO project for one example.
#
# Usage: create_project <slug> <board> <env_name> <idf_example_path> \
#            <ulp_src_subdir> <app_name> [extra_ini_lines...]
create_project() {
    local slug="$1"
    local board="$2"
    local env_name="$3"
    local idf_example="$4"
    local ulp_subdir="$5"     # "ulp" or "lp_core" in the IDF example's main/
    local app_name="$6"
    shift 6
    local extra_ini_lines=("$@")

    local dest="$EXAMPLES_DIR/$slug"
    local idf_main="$IDF_ULP/$idf_example/main"

    echo "--- $slug ($env_name) ---"

    # ULP sources -> ulp/ (always named "ulp" to trigger platform toolchain detection)
    copy_tree "$idf_main/$ulp_subdir" "$dest/ulp"

    # HP main source -> src/
    # Find the main .c file (exclude subdirs and headers)
    for f in "$idf_main"/*.c; do
        [ -f "$f" ] && copy_file "$f" "$dest/src/$(basename "$f")"
    done

    # Support headers (e.g., bmp180_defs.h) -> src/ AND project root
    # ULP sources use "../header.h" (relative to ulp/), so headers must also
    # exist at project root to match the IDF layout (main/ -> main/ulp/).
    for f in "$idf_main"/*.h; do
        [ -f "$f" ] && copy_file "$f" "$dest/src/$(basename "$f")"
        [ -f "$f" ] && copy_file "$f" "$dest/$(basename "$f")"
    done

    # sdkconfig.defaults — copy verbatim from IDF example
    local idf_sdkconfig="$IDF_ULP/$idf_example/sdkconfig.defaults"
    if [[ -f "$idf_sdkconfig" ]]; then
        copy_file "$idf_sdkconfig" "$dest/sdkconfig.defaults"
    fi

    # platformio.ini
    local script_rel
    script_rel=$(python3 -c "import os.path; print(os.path.relpath('$PROJECT_DIR/scripts/pio_ulp_cmake.py', '$dest'))")

    local ini_content
    ini_content="[env:$env_name]
platform = espressif32@55.3.36
framework = espidf
board = $board
extra_scripts = pre:$script_rel
board_build.ulp_projects =
    $app_name:ulp"

    for line in "${extra_ini_lines[@]+"${extra_ini_lines[@]}"}"; do
        ini_content="$ini_content
$line"
    done

    write_file "$dest/platformio.ini" "$ini_content"

    echo ""
}

echo "Syncing ESP-IDF ULP examples from: $FRAMEWORK_DIR"
echo "Each example becomes a self-contained PlatformIO project."
echo ""

# ==========================================================================
# FSM ULP — ESP32 (IDF example: ulp_fsm/ulp)
# Multi-file assembly: pulse_cnt.S + wake_up.S, no CMakeLists.txt
# ==========================================================================
create_project "ulp_fsm" "esp32dev" "esp32-fsm-ulp" \
    "ulp_fsm/ulp" "ulp" "ulp_main"

# ==========================================================================
# RISC-V ULP — ESP32-S3 (IDF example: ulp_riscv/gpio)
# Simplest RISC-V ULP example — GPIO state change wakeup
# ==========================================================================
create_project "ulp_riscv_gpio" "esp32-s3-devkitc-1" "esp32s3-riscv-gpio" \
    "ulp_riscv/gpio" "ulp" "ulp_main"

# ==========================================================================
# RISC-V ULP — ESP32-S3 (IDF example: ulp_riscv/i2c)
# Has support header bmp180_defs.h — tests include path handling
# ==========================================================================
create_project "ulp_riscv_i2c" "esp32-s3-devkitc-1" "esp32s3-riscv-i2c" \
    "ulp_riscv/i2c" "ulp" "ulp_main"

# ==========================================================================
# LP Core — ESP32-C6 (IDF example: lp_core/gpio)
# Standard LP Core GPIO wakeup
# ==========================================================================
create_project "lp_core_gpio" "esp32-c6-devkitc-1" "esp32c6-lp-gpio" \
    "lp_core/gpio" "ulp" "ulp_main"

# ==========================================================================
# LP Core — ESP32-C6 (IDF example: lp_core/build_system)
# Custom CMakeLists.txt + static library — THE pio_ulp_cmake.py showcase
# ==========================================================================
create_project "lp_core_build_system" "esp32-c6-devkitc-1" "esp32c6-lp-build-system" \
    "lp_core/build_system" "ulp" "ulp_build_system_example"

# ==========================================================================
# LP Core — ESP32-C6 (IDF example: lp_core/interrupt)
# Uses lp_core/ subdir in IDF, but we copy to ulp/ for PIO toolchain detection.
# App name is lp_core_main (not ulp_main).
# ==========================================================================
create_project "lp_core_interrupt" "esp32-c6-devkitc-1" "esp32c6-lp-interrupt" \
    "lp_core/interrupt" "lp_core" "lp_core_main"

# ==========================================================================
# LP Core — ESP32-C6 (IDF example: lp_core/lp_uart/lp_uart_print)
# LP UART periodic print — tests deeper nesting in IDF example path
# ==========================================================================
create_project "lp_core_uart_print" "esp32-c6-devkitc-1" "esp32c6-lp-uart-print" \
    "lp_core/lp_uart/lp_uart_print" "lp_core" "lp_core_main"

# --- Summary ---
echo "=== Sync complete ==="
echo "Projects created in: $EXAMPLES_DIR/"
echo ""
echo "To build an example:"
echo "  cd examples/ulp_riscv_gpio && pio run"
echo ""
if $DRY_RUN; then
    echo "(dry run — no files were written)"
fi
