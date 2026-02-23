#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mat McGowan
# SPDX-License-Identifier: MIT
#
# ci.sh — Run CI builds locally
#
# Emulates what the GitHub Actions workflow does: install a platform version,
# sync examples from the framework, and build.
#
# Usage:
#   ./scripts/ci.sh                           # build all examples, latest platform
#   ./scripts/ci.sh 54.03.21-2               # build all examples, IDF 5.4.2
#   ./scripts/ci.sh 55.03.37 ulp_riscv_gpio  # build one example, specific version
#   ./scripts/ci.sh --list                    # list available examples

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Use a project-local PlatformIO directory to isolate from global state.
# Override with PLATFORMIO_CORE_DIR env var if desired.
export PLATFORMIO_CORE_DIR="${PLATFORMIO_CORE_DIR:-$PROJECT_DIR/.pio-ci}"

EXAMPLES=(
    ulp_fsm
    ulp_riscv_gpio
    ulp_riscv_i2c
    lp_core_gpio
    lp_core_build_system
    lp_core_interrupt
    lp_core_uart_print
)

usage() {
    echo "Usage: $0 [PLATFORM_VERSION] [EXAMPLE...]"
    echo ""
    echo "  PLATFORM_VERSION  pioarduino release tag (default: 55.03.37)"
    echo "  EXAMPLE           one or more example names (default: all)"
    echo ""
    echo "  --list            list available examples"
    echo "  --help            show this help"
    echo ""
    echo "Examples:"
    echo "  $0                           # all examples, latest"
    echo "  $0 54.03.21-2               # all examples, IDF 5.4.2"
    echo "  $0 55.03.37 ulp_riscv_gpio  # one example"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

if [[ "${1:-}" == "--list" ]]; then
    printf '%s\n' "${EXAMPLES[@]}"
    exit 0
fi

# Parse args: first arg is version if it looks like a version string
PLATFORM_VERSION="55.03.37"
BUILD_EXAMPLES=()

if [[ $# -gt 0 && "$1" =~ ^[0-9] ]]; then
    PLATFORM_VERSION="$1"
    shift
fi

if [[ $# -gt 0 ]]; then
    BUILD_EXAMPLES=("$@")
else
    BUILD_EXAMPLES=("${EXAMPLES[@]}")
fi

PLATFORM_URL="https://github.com/pioarduino/platform-espressif32/releases/download/$PLATFORM_VERSION/platform-espressif32.zip"

echo "=== Platform: pioarduino $PLATFORM_VERSION ==="
echo "=== Examples: ${BUILD_EXAMPLES[*]} ==="
echo ""

# Install platform and framework via test fixture
echo "--- Installing platform and framework ---"
FIXTURE_INI="$PROJECT_DIR/tests/fixture/platformio.ini"
FIXTURE_INI_BAK="$FIXTURE_INI.bak"
cp "$FIXTURE_INI" "$FIXTURE_INI_BAK"
sed -i.tmp "s|platform = .*|platform = $PLATFORM_URL|" "$FIXTURE_INI"
rm -f "$FIXTURE_INI.tmp"
(cd "$PROJECT_DIR/tests/fixture" && pio pkg install)
mv "$FIXTURE_INI_BAK" "$FIXTURE_INI"
echo ""

# Sync examples from installed framework
echo "--- Syncing examples ---"
"$SCRIPT_DIR/sync_examples.sh"
echo ""

# Build each example
PASSED=()
FAILED=()

for example in "${BUILD_EXAMPLES[@]}"; do
    dir="$PROJECT_DIR/examples/$example"
    if [[ ! -d "$dir" ]]; then
        echo "ERROR: example '$example' not found at $dir"
        FAILED+=("$example")
        continue
    fi

    echo "--- Building: $example ---"

    # Override platform version in generated platformio.ini
    sed -i.bak "s|platform = .*|platform = $PLATFORM_URL|" "$dir/platformio.ini"

    # Clean and build
    rm -rf "$dir/.pio"
    if (cd "$dir" && pio run); then
        PASSED+=("$example")
    else
        FAILED+=("$example")
    fi

    # Restore platformio.ini
    mv "$dir/platformio.ini.bak" "$dir/platformio.ini"

    echo ""
done

# Summary
echo "=== Results (pioarduino $PLATFORM_VERSION) ==="
echo "Passed: ${#PASSED[@]}/${#BUILD_EXAMPLES[@]}"
for e in "${PASSED[@]}"; do echo "  ✓ $e"; done
if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "Failed: ${#FAILED[@]}/${#BUILD_EXAMPLES[@]}"
    for e in "${FAILED[@]}"; do echo "  ✗ $e"; done
    exit 1
fi
