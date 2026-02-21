# SPDX-FileCopyrightText: 2026 Mat McGowan
# SPDX-License-Identifier: MIT
#
# pio_ulp_cmake.py — Custom ULP CMake build support for PlatformIO
#
# Enables ULP projects with full CMakeLists.txt support: add_library(),
# add_subdirectory(), target_compile_definitions(), custom prefixes, and
# multiple ULP binaries.
#
# Works in two modes:
#
# 1. STANDALONE (extra_scripts) — use with pioarduino platform as-is:
#
#      [env:myenv]
#      extra_scripts = pre:scripts/pio_ulp_cmake.py
#      board_build.ulp_projects =
#          ulp_main:ulp
#          ulp_sensor:ulp_sensor:sensor_
#
# 2. INTEGRATED (from platform ulp.py) — after PR is merged:
#
#      # In ulp.py:
#      from pio_ulp_cmake import build_ulp_project, parse_ulp_projects
#
# Format for board_build.ulp_projects:
#   name:dir[:prefix]
#   - name:   ULP binary name (e.g., "ulp_main")
#   - dir:    Directory with CMakeLists.txt, relative to project root
#   - prefix: Symbol prefix for generated header (default "ulp_")
#
# Each ULP project gets its own build directory, binary, header, linker
# script, and assembly embedding. Symbol prefixes prevent conflicts when
# multiple binaries export the same variable names.

__version__ = "0.1.0"

import json
import os
import re
import sys
from pathlib import Path


def parse_ulp_projects(env):
    """Parse board_build.ulp_projects from platformio.ini.

    Returns list of (name, abs_dir, prefix) tuples. Empty list if not set.
    """
    try:
        raw = env.GetProjectOption("board_build.ulp_projects", "")
    except Exception:
        return []

    if not raw.strip():
        return []

    project_dir = env.subst("$PROJECT_DIR")
    projects = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 2:
            sys.stderr.write(
                "Warning: Invalid ULP project entry '%s' "
                "(expected name:dir[:prefix])\n" % line
            )
            continue
        name = parts[0].strip()
        ulp_dir = str(Path(project_dir) / parts[1].strip())
        prefix = parts[2].strip() if len(parts) > 2 else "ulp_"
        projects.append((name, ulp_dir, prefix))

    return projects


def _parse_sdkconfig_defaults(project_dir):
    """Parse sdkconfig.defaults to extract ULP-related config.

    Returns a dict of CONFIG_* keys to values.
    """
    config = {}
    for name in ("sdkconfig.defaults", "sdkconfig"):
        path = Path(project_dir) / name
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CONFIG_") and "=" in line:
                        key, _, val = line.partition("=")
                        config[key.strip()] = val.strip().strip('"')
    return config


def _parse_sdkconfig_cmake(build_dir):
    """Parse sdkconfig.cmake (from a previous build) for config values."""
    config = {}
    path = Path(build_dir) / "config" / "sdkconfig.cmake"
    if path.exists():
        with open(path) as f:
            for line in f:
                m = re.match(r'set\((\w+)\s+"?([^"]*)"?\)', line.strip())
                if m:
                    config[m.group(1)] = m.group(2)
    return config


def _get_sdk_config(project_dir, build_dir):
    """Get ULP-relevant sdkconfig values from the best available source."""
    # Prefer cmake config (from previous build) as it's fully resolved
    config = _parse_sdkconfig_cmake(build_dir)
    if not config:
        # Fall back to sdkconfig.defaults
        config = _parse_sdkconfig_defaults(project_dir)
    return config


def _get_ulp_toolchain(framework_dir, idf_variant, sdk_config):
    """Determine the ULP CMake toolchain file."""
    riscv = sdk_config.get("CONFIG_ULP_COPROC_TYPE_RISCV", "") == "y"
    lp_core = sdk_config.get("CONFIG_ULP_COPROC_TYPE_LP_CORE", "") == "y"

    if lp_core:
        return str(
            Path(framework_dir)
            / "components"
            / "ulp"
            / "cmake"
            / "toolchain-lp-core-riscv.cmake"
        )

    if riscv:
        toolchain_name = "toolchain-ulp-riscv.cmake"
    else:
        toolchain_name = "toolchain-%s-ulp.cmake" % idf_variant

    return str(Path(framework_dir) / "components" / "ulp" / "cmake" / toolchain_name)


def _get_component_includes_from_cmake_reply(build_dir):
    """Extract component include paths from the CMake API reply.

    The main cmake build runs before our ULP build (during PlatformIO's
    "Reading CMake configuration..." phase), so the API reply is available.
    Collects includes from all __idf_* component targets to get the full
    resolved set (individual targets only expose their own includes, not
    transitive dependencies).
    """
    reply_dir = Path(build_dir) / ".cmake" / "api" / "v1" / "reply"
    if not reply_dir.is_dir():
        return None

    # Find codemodel file
    codemodel = None
    for f in reply_dir.iterdir():
        if f.name.startswith("codemodel-v2"):
            with open(f) as fp:
                codemodel = json.load(fp)
            break

    if not codemodel:
        return None

    configs = codemodel.get("configurations", [{}])
    if not configs:
        return None

    # Collect includes from all __idf_* component targets
    all_includes = []
    seen = set()
    for project in configs[0].get("projects", []):
        for target_index in project.get("targetIndexes", []):
            target_ref = configs[0]["targets"][target_index]
            name = target_ref.get("name", "")
            if not name.startswith("__idf_"):
                continue
            target_file = reply_dir / target_ref["jsonFile"]
            if not target_file.exists():
                continue
            with open(target_file) as fp:
                target_config = json.load(fp)
            for cg in target_config.get("compileGroups", []):
                for inc in cg.get("includes", []):
                    p = inc["path"]
                    if p not in seen:
                        seen.add(p)
                        all_includes.append(p)
                break  # First compile group is sufficient per target

    return all_includes if all_includes else None


def _get_component_includes_fallback(framework_dir, build_dir, idf_variant=None):
    """Fallback: construct minimal component include paths from IDF.

    Only used when the CMake API reply is not yet available (first run).
    """
    includes = [str(Path(build_dir) / "config")]

    components_dir = Path(framework_dir) / "components"
    if not components_dir.is_dir():
        return includes

    # Exclude host-only components
    _EXCLUDE = {"linux"}

    for comp in sorted(components_dir.iterdir()):
        if not comp.is_dir() or comp.name in _EXCLUDE:
            continue
        inc = comp / "include"
        if inc.is_dir():
            includes.append(str(inc))
        # Target-specific includes and register dirs
        if idf_variant:
            for subdir in ("include", "register"):
                target_inc = comp / idf_variant / subdir
                if target_inc.is_dir():
                    includes.append(str(target_inc))

    return includes


def _get_source_dependencies(build_dir):
    """Parse compile_commands.json for SCons dependency tracking."""
    cc_json = Path(build_dir) / "compile_commands.json"
    if cc_json.exists():
        try:
            with open(cc_json) as f:
                commands = json.load(f)
            return [entry["file"] for entry in commands if "file" in entry]
        except (json.JSONDecodeError, KeyError):
            pass
    return []


def build_ulp_project(
    ulp_env,
    app_name,
    ulp_dir,
    prefix="ulp_",
    framework_dir=None,
    build_dir=None,
    idf_variant=None,
    sdk_config=None,
    component_includes=None,
):
    """Build a single ULP project and embed it into the main firmware.

    This is the core function used by both standalone and integrated modes.

    Args:
        ulp_env: SCons environment (cloned for ULP builds).
        app_name: Name of the ULP binary (e.g., "ulp_main").
        ulp_dir: Absolute path to the ULP source directory.
        prefix: Symbol prefix for generated header (default "ulp_").
        framework_dir: Path to framework-espidf package.
        build_dir: PlatformIO build directory.
        idf_variant: MCU variant (e.g., "esp32s3").
        sdk_config: Dict of sdkconfig values.
        component_includes: List of include paths, or None to auto-detect.
    """
    from platformio import fs
    from platformio.proc import exec_command

    platform = ulp_env.PioPlatform()

    if framework_dir is None:
        framework_dir = platform.get_package_dir("framework-espidf")
    if build_dir is None:
        build_dir = ulp_env.subst("$BUILD_DIR")
    if idf_variant is None:
        idf_variant = ulp_env.BoardConfig().get("build.mcu", "esp32s3")
    if sdk_config is None:
        sdk_config = _get_sdk_config(
            ulp_env.subst("$PROJECT_DIR"), build_dir
        )
    ulp_build_dir = str(Path(build_dir) / "ulp" / app_name)

    has_custom_cmake = (Path(ulp_dir) / "CMakeLists.txt").exists()
    toolchain_file = _get_ulp_toolchain(framework_dir, idf_variant, sdk_config)

    # --- Configure step ---

    def _generate_config_action(env, target, source):
        # Resolve component includes at build time — the main cmake has
        # already run by now, so the API reply is available.
        resolved_includes = component_includes
        if resolved_includes is None:
            resolved_includes = _get_component_includes_from_cmake_reply(
                build_dir
            )
        if resolved_includes is None:
            resolved_includes = _get_component_includes_fallback(
                framework_dir, build_dir, idf_variant
            )
        comp_includes_str = ";".join(resolved_includes)

        cmd = [
            str(Path(platform.get_package_dir("tool-cmake")) / "bin" / "cmake"),
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DCMAKE_GENERATOR=Ninja",
            "-DCMAKE_TOOLCHAIN_FILE=" + toolchain_file,
            "-DULP_APP_NAME=%s" % app_name,
            "-DULP_VAR_PREFIX=%s" % prefix,
            "-DCOMPONENT_DIR=" + fs.to_unix_path(ulp_dir),
            "-DCOMPONENT_INCLUDES=%s" % comp_includes_str,
            "-DIDF_TARGET=%s" % idf_variant,
            "-DIDF_PATH=" + fs.to_unix_path(framework_dir),
            "-DSDKCONFIG_HEADER="
            + str(Path(build_dir) / "config" / "sdkconfig.h"),
            "-DPYTHON=" + env.subst("$PYTHONEXE"),
            "-DSDKCONFIG_CMAKE="
            + str(Path(build_dir) / "config" / "sdkconfig.cmake"),
            "-DCMAKE_MODULE_PATH="
            + fs.to_unix_path(
                str(Path(framework_dir) / "components" / "ulp" / "cmake")
            ),
            "-GNinja",
            "-B",
            ulp_build_dir,
        ]

        if has_custom_cmake:
            cmd.append(fs.to_unix_path(ulp_dir))
        else:
            cmd.insert(
                5,
                "-DULP_S_SOURCES=%s"
                % ";".join(
                    [fs.to_unix_path(s.get_abspath()) for s in source]
                ),
            )
            cmd.append(
                str(Path(framework_dir) / "components" / "ulp" / "cmake")
            )

        result = exec_command(cmd)
        if result["returncode"] != 0:
            sys.stderr.write(result["err"] + "\n")
            env.Exit(1)

    if has_custom_cmake:
        ulp_sources = [str(Path(ulp_dir) / "CMakeLists.txt")]
        ulp_sources.extend(_get_source_dependencies(ulp_build_dir))
    else:
        ulp_sources = [
            str(Path(ulp_dir) / f)
            for f in os.listdir(ulp_dir)
            if f.endswith((".c", ".S", ".s"))
        ]
        ulp_sources.sort()

    config_target = ulp_env.Command(
        str(Path(ulp_build_dir) / "build.ninja"),
        ulp_sources,
        ulp_env.VerboseAction(
            _generate_config_action,
            "Generating ULP configuration for %s" % app_name,
        ),
    )

    # --- Build step ---

    build_cmd = (
        str(Path(platform.get_package_dir("tool-cmake")) / "bin" / "cmake"),
        "--build",
        ulp_build_dir,
        "--target",
        "build",
    )

    ulp_binary_env = ulp_env.Clone()
    ulp_binary_env.Decider("timestamp-newer")

    build_target = ulp_binary_env.Command(
        [
            str(Path(ulp_build_dir) / ("%s.h" % app_name)),
            str(Path(ulp_build_dir) / ("%s.ld" % app_name)),
            str(Path(ulp_build_dir) / ("%s.bin" % app_name)),
        ],
        None,
        ulp_binary_env.VerboseAction(
            " ".join(build_cmd),
            "Generating ULP project files for %s" % app_name,
        ),
    )

    # --- Assembly embedding step ---

    asm_cmd = (
        str(Path(platform.get_package_dir("tool-cmake")) / "bin" / "cmake"),
        "-DDATA_FILE=$SOURCE",
        "-DSOURCE_FILE=$TARGET",
        "-DFILE_TYPE=BINARY",
        "-P",
        str(
            Path(framework_dir)
            / "tools"
            / "cmake"
            / "scripts"
            / "data_file_embed_asm.cmake"
        ),
    )

    ulp_assembly = ulp_env.Command(
        str(Path(build_dir) / ("%s.bin.S" % app_name)),
        str(Path(ulp_build_dir) / ("%s.bin" % app_name)),
        ulp_env.VerboseAction(
            " ".join(asm_cmd),
            "Generating ULP assembly file for %s" % app_name,
        ),
    )

    # --- Wire up dependencies ---

    ulp_env.Depends(build_target, config_target)
    ulp_env.Depends(
        str(Path("$BUILD_DIR") / "${PROGNAME}.elf"), ulp_assembly
    )
    ulp_env.Requires(
        str(Path("$BUILD_DIR") / "${PROGNAME}.elf"), ulp_assembly
    )

    orig_env = ulp_env["__PIO_ULP_ORIG_ENV"]

    # Add to the ORIGINAL env so main firmware compilation can find
    # the generated ULP header and linker script.
    orig_env.AppendUnique(CPPPATH=[ulp_build_dir], LIBPATH=[ulp_build_dir])

    # Track linker scripts for later addition (avoiding duplicates with cmake)
    if "__PIO_ULP_LD_SCRIPTS" not in orig_env:
        orig_env["__PIO_ULP_LD_SCRIPTS"] = []
    ld_script = str(Path(ulp_build_dir) / ("%s.ld" % app_name))
    orig_env["__PIO_ULP_LD_SCRIPTS"].append((app_name, ld_script))

    # Track ULP build targets for dependency wiring in standalone mode.
    # Source compilation must wait for ULP headers to be generated.
    if "__PIO_ULP_BUILD_TARGETS" not in orig_env:
        orig_env["__PIO_ULP_BUILD_TARGETS"] = []
    orig_env["__PIO_ULP_BUILD_TARGETS"].append(build_target)

    # Track assembly files for compilation in standalone mode.
    if "__PIO_ULP_ASM_FILES" not in orig_env:
        orig_env["__PIO_ULP_ASM_FILES"] = []
    asm_file = str(Path(build_dir) / ("%s.bin.S" % app_name))
    orig_env["__PIO_ULP_ASM_FILES"].append((asm_file, ulp_assembly))


# ---------------------------------------------------------------------------
# Standalone mode: runs as pre: extra_scripts
# ---------------------------------------------------------------------------

def _standalone_main(env):
    """Entry point when used as extra_scripts = pre:pio_ulp_cmake.py"""
    projects = parse_ulp_projects(env)
    if not projects:
        return

    # Prevent stock ulp.py from running.
    # The stock espidf.py calls env.SConscript("ulp.py", ...) when it finds
    # a ulp/ directory. We intercept that call since pre: extra_scripts
    # execute before the framework builder.
    _original_sconscript = env.SConscript

    def _intercept_sconscript(script, *args, **kwargs):
        if isinstance(script, str) and os.path.basename(script) == "ulp.py":
            return  # Skip stock ULP handler — we handle it
        return _original_sconscript(script, *args, **kwargs)

    env.SConscript = _intercept_sconscript

    # Set up toolchain environment
    platform = env.PioPlatform()
    framework_dir = platform.get_package_dir("framework-espidf")
    is_xtensa = env.BoardConfig().get("build.mcu", "") in (
        "esp32", "esp32s2", "esp32s3"
    )

    ulp_env = env.Clone()
    ulp_env["__PIO_ULP_ORIG_ENV"] = env
    ulp_env.PrependENVPath("IDF_PATH", framework_dir)

    toolchain_path = platform.get_package_dir(
        "toolchain-xtensa-esp-elf" if is_xtensa else "toolchain-riscv32-esp"
    )

    sdk_config = _get_sdk_config(env.subst("$PROJECT_DIR"), env.subst("$BUILD_DIR"))

    toolchain_path_ulp = platform.get_package_dir(
        "toolchain-esp32ulp"
        if sdk_config.get("CONFIG_ULP_COPROC_TYPE_FSM", "") == "y"
        else None
    )

    for package in [
        toolchain_path,
        toolchain_path_ulp,
        platform.get_package_dir("tool-ninja"),
        str(Path(platform.get_package_dir("tool-cmake")) / "bin"),
    ]:
        if package and os.path.isdir(package):
            ulp_env.PrependENVPath("PATH", package)

    # Build each registered project
    for app_name, ulp_dir, prefix in projects:
        build_ulp_project(
            ulp_env,
            app_name,
            ulp_dir,
            prefix=prefix,
            framework_dir=framework_dir,
            sdk_config=sdk_config,
        )

    # In standalone mode, we need to compile ULP assembly files and add
    # them to the firmware link. However, projects that are also declared
    # in the main cmake via ulp_add_project() are already handled by
    # espidf.py through the cmake API reply. We detect these by checking
    # if the .bin.S file appears in the cmake API reply sources.
    # Compile and link ULP assembly files that aren't handled by the
    # main cmake (via ulp_add_project / target_add_binary_data).
    # Detection of cmake-handled projects is deferred to build time because
    # the cmake API reply may not exist yet at parse time (clean builds).
    asm_files = env.get("__PIO_ULP_ASM_FILES", [])
    ld_scripts = env.get("__PIO_ULP_LD_SCRIPTS", [])

    for asm_file, asm_dep in asm_files:
        obj = env.StaticObject(
            target=asm_file + ".o",
            source=asm_file,
        )
        env.Depends(obj, asm_dep)
        env.Append(PIOBUILDFILES=[obj])

    for app_name, ld_script in ld_scripts:
        env.Append(LINKFLAGS=["-T", ld_script])


# ---------------------------------------------------------------------------
# Integrated mode: called from platform ulp.py
# ---------------------------------------------------------------------------

def integrated_main(env, sdk_config, project_config, app_includes, idf_variant):
    """Entry point when called from platform ulp.py.

    Receives framework context directly — no need to derive it.
    """
    platform = env.PioPlatform()
    framework_dir = platform.get_package_dir("framework-espidf")
    build_dir = env.subst("$BUILD_DIR")
    # Get component includes from the framework context
    def _get_comp_includes(target_config, app_name):
        for source in target_config.get("sources", []):
            if source["path"].endswith("%s.bin.S" % app_name):
                return [
                    inc["path"]
                    for inc in target_config["compileGroups"][
                        source["compileGroupIndex"]
                    ]["includes"]
                ]
        return [str(Path(build_dir) / "config")]

    # Translate sdk_config format (stock ulp.py uses .get() without CONFIG_ prefix)
    sdk_cfg = {}
    for key in ("ULP_COPROC_TYPE_RISCV", "ULP_COPROC_TYPE_FSM", "ULP_COPROC_TYPE_LP_CORE"):
        if sdk_config.get(key, False):
            sdk_cfg["CONFIG_" + key] = "y"

    ulp_env = env.Clone()
    ulp_env["__PIO_ULP_ORIG_ENV"] = env
    ulp_env.PrependENVPath("IDF_PATH", framework_dir)

    is_xtensa = idf_variant in ("esp32", "esp32s2", "esp32s3")
    toolchain_path = platform.get_package_dir(
        "toolchain-xtensa-esp-elf" if is_xtensa else "toolchain-riscv32-esp"
    )
    toolchain_path_ulp = platform.get_package_dir(
        "toolchain-esp32ulp"
        if sdk_config.get("ULP_COPROC_TYPE_FSM", False)
        else None
    )

    for package in [
        toolchain_path,
        toolchain_path_ulp,
        platform.get_package_dir("tool-ninja"),
        str(Path(platform.get_package_dir("tool-cmake")) / "bin"),
    ]:
        if package and os.path.isdir(package):
            ulp_env.PrependENVPath("PATH", package)

    # Get includes with framework context
    comp_includes_list = _get_comp_includes(project_config, "ulp_main")
    plain_includes_list = app_includes.get("plain_includes", [])
    component_includes = comp_includes_list + plain_includes_list

    projects = parse_ulp_projects(env)

    if projects:
        for app_name, ulp_dir, prefix in projects:
            build_ulp_project(
                ulp_env, app_name, ulp_dir,
                prefix=prefix,
                framework_dir=framework_dir,
                sdk_config=sdk_cfg,
                component_includes=component_includes,
            )
    else:
        # Legacy: single project from board_build.ulp_dir
        ulp_dir_name = env.GetProjectOption("board_build.ulp_dir", "ulp")
        ulp_dir = str(Path(env.subst("$PROJECT_DIR")) / ulp_dir_name)
        build_ulp_project(
            ulp_env, "ulp_main", ulp_dir,
            framework_dir=framework_dir,
            sdk_config=sdk_cfg,
            component_includes=component_includes,
        )


# ---------------------------------------------------------------------------
# Auto-detect mode on import
# ---------------------------------------------------------------------------

try:
    from SCons.Script import Import

    Import("env")

    # Check if we're in ulp.py context (integrated) or extra_scripts (standalone)
    try:
        Import("sdk_config project_config app_includes idf_variant")
        # Integrated mode — called from ulp.py via SConscript
        integrated_main(env, sdk_config, project_config, app_includes, idf_variant)
    except Exception:
        # Standalone mode — called as pre: extra_scripts
        _standalone_main(env)

except ImportError:
    # Not running in SCons context (e.g., imported for testing)
    pass
