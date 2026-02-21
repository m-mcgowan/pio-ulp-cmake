#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mat McGowan
# SPDX-License-Identifier: MIT
#
# Patch a pioarduino platform-espressif32 installation to use pio_ulp_cmake.
#
# This emulates what a merged PR would look like: ulp.py detects custom
# CMakeLists.txt or board_build.ulp_projects and delegates to pio_ulp_cmake's
# integrated_main(), falling back to stock behavior otherwise.
#
# Usage:
#   ./scripts/patch_pioarduino.sh <platform_dir> <pio_ulp_cmake_path>
#
# Example:
#   ./scripts/patch_pioarduino.sh \
#     ~/.platformio/platforms/espressif32 \
#     scripts/pio_ulp_cmake.py

set -euo pipefail

PLATFORM_DIR="${1:?Usage: $0 <platform_dir> <pio_ulp_cmake_path>}"
PIO_ULP_CMAKE="${2:?Usage: $0 <platform_dir> <pio_ulp_cmake_path>}"

ULP_PY="$PLATFORM_DIR/builder/frameworks/ulp.py"
TARGET_DIR="$PLATFORM_DIR/builder/frameworks"

if [[ ! -f "$ULP_PY" ]]; then
    echo "Error: ulp.py not found at $ULP_PY" >&2
    exit 1
fi

if [[ ! -f "$PIO_ULP_CMAKE" ]]; then
    echo "Error: pio_ulp_cmake.py not found at $PIO_ULP_CMAKE" >&2
    exit 1
fi

# 1. Copy pio_ulp_cmake.py next to ulp.py so it can be imported
cp "$PIO_ULP_CMAKE" "$TARGET_DIR/pio_ulp_cmake.py"
echo "Copied pio_ulp_cmake.py to $TARGET_DIR/"

# 2. Patch ulp.py to detect and delegate to pio_ulp_cmake
# Insert integration code right after the Import() line (line 25)
# The patch adds a check: if board_build.ulp_projects is set or a
# CMakeLists.txt exists in the ULP dir, delegate to integrated_main()
# and skip the rest of the stock ulp.py.

PATCH_MARKER="# --- pio_ulp_cmake integration ---"

if grep -q "$PATCH_MARKER" "$ULP_PY"; then
    echo "ulp.py already patched, skipping"
    exit 0
fi

# Create the patched version
python3 - "$ULP_PY" "$PATCH_MARKER" << 'PYEOF'
import sys

ulp_py = sys.argv[1]
marker = sys.argv[2]

with open(ulp_py) as f:
    lines = f.readlines()

# Find the line: Import("env sdk_config project_config app_includes idf_variant")
insert_after = None
for i, line in enumerate(lines):
    if line.strip().startswith('Import("env sdk_config'):
        insert_after = i
        break

if insert_after is None:
    print("Error: Could not find Import() line in ulp.py", file=sys.stderr)
    sys.exit(1)

patch = f"""
{marker}
# Check if pio_ulp_cmake should handle this build
import os as _os
from pathlib import Path as _Path
try:
    from pio_ulp_cmake import integrated_main, parse_ulp_projects
    _ulp_projects = parse_ulp_projects(env)
    _ulp_dir = str(_Path(env.subst("$PROJECT_DIR")) / env.GetProjectOption("board_build.ulp_dir", "ulp"))
    _has_custom_cmake = (_Path(_ulp_dir) / "CMakeLists.txt").exists()
    if _ulp_projects or _has_custom_cmake:
        integrated_main(env, sdk_config, project_config, app_includes, idf_variant)
        Return()  # Skip the rest of stock ulp.py
except ImportError:
    pass
{marker.replace('---', '--- end')}

"""

lines.insert(insert_after + 1, patch)

with open(ulp_py, 'w') as f:
    f.writelines(lines)

print(f"Patched ulp.py (inserted after line {insert_after + 1})")
PYEOF

echo "Done. pioarduino platform is now patched for pio_ulp_cmake integration."
