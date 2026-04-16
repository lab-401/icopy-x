#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Build an IPK package for iCopy-X.

The IPK is a ZIP archive with a specific directory layout that the iCopy-X
device can install.  This script:

  1. Copies our Python UI modules (src/lib/*.py) into lib/
  2. Copies JSON screen definitions (src/screens/*.json) into screens/
  3. Copies middleware .so files from orig_so/lib/ — but EXCLUDES any .so
     whose module has been replaced by a .py file (Python .so wins over .py
     when both exist, so we must NOT ship the replaced .so)
  4. Copies the main-level .so files from orig_so/main/
  5. Includes build/ artifacts (PM3 client, lua.zip, install.so)
  6. Bundles everything into a .ipk (ZIP)

Usage:
    python tools/build_ipk.py [--sn SERIAL] [--output FILE] [--dry-run]
"""

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_LIB = os.path.join(REPO_ROOT, "src", "lib")
SRC_MIDDLEWARE = os.path.join(REPO_ROOT, "src", "middleware")
SRC_SCREENS = os.path.join(REPO_ROOT, "src", "screens")
ORIG_SO_LIB = os.path.join(REPO_ROOT, "orig_so", "lib")
ORIG_SO_MAIN = os.path.join(REPO_ROOT, "orig_so", "main")
BUILD_DIR = os.path.join(REPO_ROOT, "build")
RES_DIR = os.path.join(REPO_ROOT, "res")
DATA_DIR = os.path.join(REPO_ROOT, "data")
PLUGINS_DIR = os.path.join(REPO_ROOT, "plugins")

# ---------------------------------------------------------------------------
# Modules replaced by .py — their .so counterparts MUST be excluded
# ---------------------------------------------------------------------------
REPLACED_SO_MODULES = frozenset({
    # UI layer (.py in src/lib/)
    "actbase",
    "actmain",
    "actstack",
    "activity_main",
    "activity_tools",
    "activity_update",
    "application",
    "batteryui",
    "hmi_driver",
    "images",
    "keymap",
    "resources",
    "widget",
    # Removed entirely — not imported by any code
    "aesutils",
    "debug",
    "games",
    # Middleware (.py in src/middleware/) — OSS reimplementations of .so modules
    "appfiles",
    "audio",
    "audio_copy",
    "bytestr",
    "commons",
    "config",
    "container",
    "erase",
    "executor",
    "felicaread",
    "gadget_linux",
    "hf14ainfo",
    "hf14aread",
    "hf15read",
    "hf15write",
    "hffelica",
    "hficlass",
    "hfmfkeys",
    "hfmfread",
    "hfmfuinfo",
    "hfmfuread",
    "hfmfuwrite",
    "hfmfwrite",
    "hfsearch",
    "iclassread",
    "iclasswrite",
    "legicread",
    "lfem4x05",
    "lfread",
    "lfsearch",
    "lft55xx",
    "lfverify",
    "lfwrite",
    "mifare",
    "read",
    "scan",
    "settings",
    "sniff",
    "tagtypes",
    "template",
    "update",
    "version",
    "write",
    "ymodem",
})

# Main-level .so modules replaced by .py (in src/main/)
REPLACED_MAIN_MODULES = frozenset({
    "install",
    "main",
    "rftask",
})

SRC_MAIN = os.path.join(REPO_ROOT, "src", "main")

DEFAULT_OUTPUT = "icopy-x-oss.ipk"


def collect_py_modules(src_lib_dir):
    """Return list of (src_path, ipk_path) for all .py files in src/lib/."""
    pairs = []
    for fname in sorted(os.listdir(src_lib_dir)):
        if fname.endswith(".py"):
            pairs.append((
                os.path.join(src_lib_dir, fname),
                f"lib/{fname}",
            ))
    return pairs


def collect_middleware_modules(src_mw_dir):
    """Return list of (src_path, ipk_path) for all .py files in src/middleware/.

    These are OSS Python reimplementations of original .so middleware modules.
    They go into lib/ alongside the UI modules — the device's Python path
    finds them there.
    """
    pairs = []
    if not os.path.isdir(src_mw_dir):
        return pairs
    for fname in sorted(os.listdir(src_mw_dir)):
        if fname.endswith(".py") and fname != "__init__.py":
            pairs.append((
                os.path.join(src_mw_dir, fname),
                f"lib/{fname}",
            ))
    return pairs


def collect_screen_jsons(src_screens_dir):
    """Return list of (src_path, ipk_path) for all .json screen definitions."""
    pairs = []
    if not os.path.isdir(src_screens_dir):
        return pairs
    for fname in sorted(os.listdir(src_screens_dir)):
        if fname.endswith(".json"):
            pairs.append((
                os.path.join(src_screens_dir, fname),
                f"screens/{fname}",
            ))
    return pairs


def collect_kept_so(orig_lib_dir):
    """Return list of (src_path, ipk_path) for .so files NOT replaced."""
    pairs = []
    if not os.path.isdir(orig_lib_dir):
        print(f"WARNING: {orig_lib_dir} not found — no .so files will be included")
        return pairs
    for fname in sorted(os.listdir(orig_lib_dir)):
        if not fname.endswith(".so"):
            continue
        module_name = fname[:-3]  # strip .so
        if module_name in REPLACED_SO_MODULES:
            continue
        pairs.append((
            os.path.join(orig_lib_dir, fname),
            f"lib/{fname}",
        ))
    return pairs


def collect_main_py(src_main_dir):
    """Return list of (src_path, ipk_path) for Python files in src/main/."""
    pairs = []
    if not os.path.isdir(src_main_dir):
        return pairs
    for fname in sorted(os.listdir(src_main_dir)):
        if fname.endswith(".py"):
            pairs.append((
                os.path.join(src_main_dir, fname),
                f"main/{fname}",
            ))
    return pairs


def collect_main_so(orig_main_dir):
    """Return list of (src_path, ipk_path) for main-level .so files NOT replaced."""
    pairs = []
    if not os.path.isdir(orig_main_dir):
        return pairs
    for fname in sorted(os.listdir(orig_main_dir)):
        if not fname.endswith(".so"):
            continue
        module_name = fname[:-3]  # strip .so
        if module_name in REPLACED_MAIN_MODULES:
            continue
        pairs.append((
            os.path.join(orig_main_dir, fname),
            f"main/{fname}",
        ))
    return pairs


def collect_resources(res_dir):
    """Return list of (src_path, ipk_path) for res/ resources.

    Collects audio (.wav), fonts (.ttf, .txt), and images (.png)
    that the device needs at runtime.
    """
    pairs = []
    if not os.path.isdir(res_dir):
        print(f"WARNING: {res_dir} not found — no resources will be included")
        return pairs

    for dirpath, dirnames, filenames in os.walk(res_dir):
        for fname in sorted(filenames):
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(src, res_dir)
            pairs.append((src, f"res/{rel}"))

    return pairs


def collect_data(data_dir):
    """Return list of (src_path, ipk_path) for data/ files (conf.ini etc)."""
    pairs = []
    if not os.path.isdir(data_dir):
        return pairs

    for fname in sorted(os.listdir(data_dir)):
        src = os.path.join(data_dir, fname)
        if os.path.isfile(src):
            pairs.append((src, f"data/{fname}"))

    return pairs


def collect_plugins(plugins_dir):
    """Return list of (src_path, ipk_path) for all plugin files.

    Walks plugins/ directory and includes all files from valid plugin
    subdirectories (those containing a manifest.json).  Skips directories
    starting with '.' or '_', and skips __pycache__ directories.

    The IPK paths preserve the plugins/ prefix so files land at
    <ipk_root>/plugins/<name>/... on the device.
    """
    pairs = []
    if not os.path.isdir(plugins_dir):
        return pairs

    for entry in sorted(os.listdir(plugins_dir)):
        # Skip hidden and private directories
        if entry.startswith('.') or entry.startswith('_'):
            continue

        subdir = os.path.join(plugins_dir, entry)
        if not os.path.isdir(subdir):
            continue

        # Only include directories that have a manifest.json
        manifest = os.path.join(subdir, "manifest.json")
        if not os.path.isfile(manifest):
            print(f"  WARNING: plugins/{entry}/ has no manifest.json — skipped")
            continue

        # Walk the entire plugin subdirectory
        for dirpath, dirnames, filenames in os.walk(subdir):
            # Prune __pycache__ and hidden/private dirs from walk
            dirnames[:] = [
                d for d in dirnames
                if d != '__pycache__' and not d.startswith('.') and not d.startswith('_')
            ]

            for fname in sorted(filenames):
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, plugins_dir)
                pairs.append((src, f"plugins/{rel}"))

    return pairs


def collect_build_binaries(serial_number, include_flash=True):
    """Return list of (src_path, ipk_path) for device binaries.

    Looks for PM3 client binary and lua.zip in build/ (Docker pipeline output).

    Ships proxmark3 binary and lua.zip (PM3 LUA scripts).

    Lua version matching:
      - Flash IPK (include_flash=True):  build/lua.zip (iceman Lua 5.4)
      - No-flash IPK (include_flash=False): build/factory_lua.zip (factory Lua 5.1)
      Both are shipped as pm3/lua.zip inside the IPK — the installer
      extracts whatever is bundled.
    """
    pairs = []

    # proxmark3 binary -> pm3/proxmark3
    # Flash IPK: iceman client (build/proxmark3 from Docker)
    # No-flash IPK: factory client (build/factory_proxmark3, checked into repo)
    if include_flash:
        pm3_build = os.path.join(BUILD_DIR, "proxmark3")
        if os.path.exists(pm3_build):
            pairs.append((pm3_build, "pm3/proxmark3"))
            print(f"  PM3 client: {pm3_build} (iceman)")
        else:
            print("WARNING: build/proxmark3 not found — run Docker build first")
    else:
        pm3_factory = os.path.join(BUILD_DIR, "factory_proxmark3")
        if os.path.exists(pm3_factory):
            pairs.append((pm3_factory, "pm3/proxmark3"))
            print(f"  PM3 client: {pm3_factory} (factory)")
        else:
            print("WARNING: build/factory_proxmark3 not found")

    # lua.zip -> pm3/lua.zip (PM3 LUA scripts)
    # Flash IPK: iceman lua (build/lua.zip from Docker, Lua 5.4 compatible)
    # No-flash IPK: factory lua (build/factory_lua.zip, Lua 5.1)
    if include_flash:
        lua_build = os.path.join(BUILD_DIR, "lua.zip")
        if os.path.exists(lua_build):
            pairs.append((lua_build, "pm3/lua.zip"))
            print(f"  LUA scripts: {lua_build} (iceman, Lua 5.4)")
        else:
            print("WARNING: build/lua.zip not found — run Docker build first")
    else:
        lua_factory = os.path.join(BUILD_DIR, "factory_lua.zip")
        if os.path.exists(lua_factory):
            pairs.append((lua_factory, "pm3/lua.zip"))
            print(f"  LUA scripts: {lua_factory} (factory, Lua 5.1)")
        else:
            print("WARNING: build/factory_lua.zip not found — no-flash IPK will have no LUA scripts")

    return pairs


UNIVERSAL_VERSION_SO = os.path.join(
    REPO_ROOT, "tools", "universal_version", "version.so")


def _generate_build_version(version_override=None):
    """Generate a build version string.

    Priority:
        1. Explicit --version flag (e.g. "v0.6.1" from CI release)
        2. ICOPYX_VERSION env var (for CI/CD pipelines)
        3. Auto-generated: YYMMDD-H.M-Int (local dev build)

    Returns:
        str: version string
    """
    if version_override:
        return version_override
    env_ver = os.environ.get('ICOPYX_VERSION', '')
    if env_ver:
        return env_ver
    now = datetime.now(timezone.utc)
    return now.strftime("%y%m%d-%H.%M-Int")


def build_ipk(output_path, serial_number="UNIVERSAL", dry_run=False,
              trojan=False, include_flash=True, version_override=None):
    """Build the IPK archive.

    When trojan=True, the IPK includes two extra ARM binaries required by
    the original firmware's DRM check:
      - lib/version.so   — universal bypass (mirrors running device's SN)
      - main/install.so  — genuine file copier from build/
    This allows the IPK to be installed via USB on a device still running
    the original firmware.  See docs/HOWTO-JAILBREAK.md.

    When include_flash=True (default), the IPK includes PM3 firmware files:
      - res/firmware/pm3/fullimage.elf   — PM3 firmware image
      - res/firmware/pm3/manifest.json   — version/integrity manifest
    Set include_flash=False for a non-flash variant that works with the
    existing vanilla PM3 firmware.
    """
    # Use an ordered dict keyed by ipk_path so later entries override earlier
    # ones (e.g. build/install.so overrides orig_so/main/install.so).
    manifest_map = {}

    def _add(pairs):
        for src_path, ipk_path in pairs:
            manifest_map[ipk_path] = src_path

    # 0. app.py entry point (src/app.py -> app.py)
    app_py = os.path.join(REPO_ROOT, "src", "app.py")
    if os.path.exists(app_py):
        _add([(app_py, "app.py")])

    # 1. Python UI modules (src/lib/*.py -> lib/*.py)
    _add(collect_py_modules(SRC_LIB))

    # 1b. Python middleware modules (src/middleware/*.py -> lib/*.py)
    _add(collect_middleware_modules(SRC_MIDDLEWARE))

    # 2. JSON screen definitions (src/screens/*.json -> screens/*.json)
    _add(collect_screen_jsons(SRC_SCREENS))

    # 3. Kept middleware .so files (orig_so/lib/*.so, minus replaced ones)
    _add(collect_kept_so(ORIG_SO_LIB))

    # 4a. Python main-level modules (src/main/*.py -> main/*.py)
    _add(collect_main_py(SRC_MAIN))

    # 4b. Kept main-level .so files (orig_so/main/*.so, minus replaced ones)
    _add(collect_main_so(ORIG_SO_MAIN))

    # 5. Resources (res/audio, res/font, res/img, res/firmware if flash enabled)
    resources = collect_resources(RES_DIR)
    if not include_flash:
        # Strip firmware files from non-flash variant
        resources = [(s, p) for s, p in resources
                     if not p.startswith("res/firmware/")]
        print(f"  (--no-flash: excluded res/firmware/ from IPK)")
    _add(resources)

    # 6. Data files (data/conf.ini)
    _add(collect_data(DATA_DIR))

    # 6b. Plugins (plugins/*/ -> plugins/*/)
    _add(collect_plugins(PLUGINS_DIR))

    # 7. Device binaries (build/) — added LAST so they override orig_so
    _add(collect_build_binaries(serial_number, include_flash=include_flash))

    # 8. Trojan mode: inject ARM binaries to pass original firmware DRM
    if trojan:
        # Universal version.so — mirrors running device's SERIAL_NUMBER
        if not os.path.exists(UNIVERSAL_VERSION_SO):
            print(f"ERROR: {UNIVERSAL_VERSION_SO} not found.")
            print("  Build it first:  arm-linux-gnueabihf-gcc -shared -fPIC -O2 \\")
            print("    -I<rootfs>/usr/local/python-3.8.0/include/python3.8 \\")
            print("    -o tools/universal_version/version.so \\")
            print("    tools/universal_version/version_universal.c")
            return False
        _add([(UNIVERSAL_VERSION_SO, "lib/version.so")])

        # Genuine install.so — original ARM file copier
        genuine_install = os.path.join(BUILD_DIR, "install.so")
        if not os.path.exists(genuine_install):
            print(f"ERROR: {genuine_install} not found.")
            return False
        _add([(genuine_install, "main/install.so")])

    manifest = [(src, ipk) for ipk, src in manifest_map.items()]

    # Print manifest
    kept_so_count = 0
    py_count = 0
    json_count = 0
    res_count = 0
    plugin_count = 0
    other_count = 0

    print(f"IPK Build Manifest ({len(manifest)} files)")
    print(f"{'=' * 60}")

    for src_path, ipk_path in manifest:
        size = os.path.getsize(src_path)
        # Only print non-resource and non-plugin files individually
        if not ipk_path.startswith("res/") and not ipk_path.startswith("plugins/"):
            print(f"  {ipk_path:<45s} {size:>8,d} bytes")
        if ipk_path.startswith("plugins/"):
            plugin_count += 1
        elif ipk_path.endswith(".py"):
            py_count += 1
        elif ipk_path.endswith(".so"):
            kept_so_count += 1
        elif ipk_path.endswith(".json"):
            json_count += 1
        elif ipk_path.startswith("res/"):
            res_count += 1
        else:
            other_count += 1

    res_size = sum(os.path.getsize(s) for s, p in manifest if p.startswith("res/"))
    print(f"  res/* ({res_count} files){' ' * 28}{res_size:>8,d} bytes")

    plugin_size = sum(os.path.getsize(s) for s, p in manifest if p.startswith("plugins/"))
    if plugin_count:
        # Count distinct plugin directories
        plugin_dirs = set()
        for _, p in manifest:
            if p.startswith("plugins/"):
                parts = p.split("/")
                if len(parts) >= 2:
                    plugin_dirs.add(parts[1])
        print(f"  plugins/* ({plugin_count} files, {len(plugin_dirs)} plugins)"
              f"{' ' * (20 - len(str(plugin_count)) - len(str(len(plugin_dirs))))}"
              f"{plugin_size:>8,d} bytes")

    print(f"{'=' * 60}")
    print(f"  Python modules:  {py_count}")
    print(f"  JSON screens:    {json_count}")
    print(f"  Resources:       {res_count} (audio: wav, font: ttf, img: png)")
    print(f"  Plugins:         {plugin_count}")
    print(f"  Kept .so files:  {kept_so_count}")
    print(f"  Other:           {other_count}")
    print(f"  Excluded .so:    {len(REPLACED_SO_MODULES)} (replaced by .py)")
    print()

    # Verify excluded .so files
    print("Excluded .so modules (replaced by .py):")
    for mod in sorted(REPLACED_SO_MODULES):
        so_path = os.path.join(ORIG_SO_LIB, f"{mod}.so")
        exists = os.path.exists(so_path)
        print(f"  {mod}.so {'(found, excluded)' if exists else '(not present)'}")
    print()

    # Generate build version stamp
    build_version = _generate_build_version(version_override)
    print(f"  Build version:   {build_version}")
    print()

    if dry_run:
        print("DRY RUN — no IPK created.")
        return True

    # Create temporary _BUILD_VERSION file to include in the IPK
    _ver_tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                           delete=False, prefix='build_ver_')
    _ver_tmp.write(build_version)
    _ver_tmp.close()
    manifest.append((_ver_tmp.name, 'lib/_BUILD_VERSION'))

    # Build ZIP
    print(f"Writing {output_path} ...")
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src_path, ipk_path in manifest:
            zf.write(src_path, ipk_path)

    # Clean up temp file
    try:
        os.unlink(_ver_tmp.name)
    except OSError:
        pass

    total_size = os.path.getsize(output_path)
    print(f"IPK created: {output_path} ({total_size:,d} bytes)")

    # Verification: ensure no replaced .so leaked in
    # In trojan mode, lib/version.so and main/install.so are intentional.
    trojan_allowed = {"lib/version.so", "main/install.so"} if trojan else set()
    with zipfile.ZipFile(output_path, "r") as zf:
        names = set(zf.namelist())
        for mod in REPLACED_SO_MODULES:
            bad = f"lib/{mod}.so"
            if bad in names and bad not in trojan_allowed:
                print(f"ERROR: {bad} found in IPK — this .so is replaced by .py!")
                return False

    print("Verification passed: no replaced .so files in IPK.")

    # Trojan-specific verification
    if trojan:
        with zipfile.ZipFile(output_path, "r") as zf:
            names = set(zf.namelist())
            required = ["app.py", "lib/version.so", "main/install.so"]
            ok_trojan = True
            for r in required:
                if r not in names:
                    print(f"ERROR: trojan IPK missing {r}")
                    ok_trojan = False
            if ok_trojan:
                print("Trojan verification passed: checkPkg will accept this IPK.")
            else:
                return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Build iCopy-X IPK package")
    parser.add_argument(
        "--sn", default="UNIVERSAL",
        help="Serial number (default: UNIVERSAL)")
    parser.add_argument(
        "--output", "-o", default=DEFAULT_OUTPUT,
        help=f"Output IPK path (default: {DEFAULT_OUTPUT})")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print manifest without creating IPK")
    parser.add_argument(
        "--no-trojan", action="store_true",
        help="Omit the universal version.so and genuine install.so from "
             "the IPK. The resulting package cannot be installed on a "
             "device still running the original firmware.")
    parser.add_argument(
        "--no-flash", action="store_true",
        help="Omit PM3 firmware files (fullimage.elf, manifest.json) from "
             "the IPK. The resulting package works with the existing vanilla "
             "PM3 firmware and does not prompt for a firmware flash.")
    parser.add_argument(
        "--version", default=None,
        help="Override build version string (e.g. 'v0.6.1' for releases). "
             "Default: YYMMDD-H.M-Int (local dev build). "
             "Also reads ICOPYX_VERSION env var.")
    args = parser.parse_args()

    ok = build_ipk(args.output, serial_number=args.sn, dry_run=args.dry_run,
                   trojan=not args.no_trojan,
                   include_flash=not args.no_flash,
                   version_override=args.version)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
