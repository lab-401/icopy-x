#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Build a "No Flash, Original Middleware" IPK for iCopy-X.

This IPK replaces ONLY the UI layer with our open-source Python code.
All middleware .so files come from the original v1.0.90 firmware IPK.

Source of truth: /home/qx/02150004_1.0.90.ipk (original device firmware)

Usage:
    python3 tools/build_noflash_ipk.py
    python3 tools/build_noflash_ipk.py --output test-install.ipk
    python3 tools/build_noflash_ipk.py --dry-run
"""

import argparse
import os
import sys
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Original IPK — canonical source of v1.0.90 .so files and resources
ORIGINAL_IPK = "/home/qx/02150004_1.0.90.ipk"

# Our Python UI modules
SRC_LIB = os.path.join(REPO_ROOT, "src", "lib")
SRC_MIDDLEWARE = os.path.join(REPO_ROOT, "src", "middleware")
SRC_SCREENS = os.path.join(REPO_ROOT, "src", "screens")

# Device binaries (install.so, version.so from real device)
DEVICE_SO = os.path.join(REPO_ROOT, "device_so")

# Modules replaced by our .py — their .so MUST be excluded
REPLACED_SO = frozenset({
    "actbase", "actmain", "actstack", "activity_main",
    "activity_tools", "activity_update", "batteryui",
    "hmi_driver", "images", "keymap", "resources", "widget",
})

DEFAULT_OUTPUT = "test-install.ipk"


def build(output_path, dry_run=False):
    """Build the No-Flash OG-Middleware IPK."""

    if not os.path.exists(ORIGINAL_IPK):
        print(f"ERROR: Original IPK not found: {ORIGINAL_IPK}")
        return False

    # ipk_path -> (source_type, source_detail)
    # source_type: 'original_ipk', 'src_file', 'device_so', 'empty'
    manifest = {}

    # ================================================================
    # Stage 1: Copy EVERYTHING from original IPK as baseline
    # ================================================================
    print("Stage 1: Loading original IPK as baseline...")
    with zipfile.ZipFile(ORIGINAL_IPK, 'r') as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            manifest[info.filename] = ('original_ipk', info.filename, info.file_size)

    print(f"  {len(manifest)} files from original IPK")

    # ================================================================
    # Stage 2: Replace UI modules with our Python versions
    # ================================================================
    print("Stage 2: Replacing UI modules with Python...")
    replaced_count = 0

    # Our Python UI modules → lib/*.py
    for fname in sorted(os.listdir(SRC_LIB)):
        if not fname.endswith('.py'):
            continue
        src = os.path.join(SRC_LIB, fname)
        ipk_path = f"lib/{fname}"
        manifest[ipk_path] = ('src_file', src, os.path.getsize(src))
        replaced_count += 1

    # Middleware erase.py → lib/erase.py
    erase_py = os.path.join(SRC_MIDDLEWARE, "erase.py")
    if os.path.exists(erase_py):
        manifest["lib/erase.py"] = ('src_file', erase_py, os.path.getsize(erase_py))
        replaced_count += 1
        print(f"  Added middleware: erase.py → lib/erase.py")

    print(f"  {replaced_count} Python modules added")

    # ================================================================
    # Stage 3: Remove replaced .so files (our .py replaces them)
    # ================================================================
    print("Stage 3: Removing replaced .so files...")
    removed = []
    for mod in sorted(REPLACED_SO):
        so_path = f"lib/{mod}.so"
        if so_path in manifest:
            del manifest[so_path]
            removed.append(mod)
    print(f"  Removed {len(removed)} .so files: {', '.join(removed)}")

    # ================================================================
    # Stage 4: Add JSON screen definitions
    # ================================================================
    print("Stage 4: Adding JSON screen definitions...")
    json_count = 0
    if os.path.isdir(SRC_SCREENS):
        for fname in sorted(os.listdir(SRC_SCREENS)):
            if fname.endswith('.json'):
                src = os.path.join(SRC_SCREENS, fname)
                manifest[f"screens/{fname}"] = ('src_file', src, os.path.getsize(src))
                json_count += 1
    print(f"  {json_count} JSON screens added")

    # ================================================================
    # Stage 5: Override with device_so binaries
    # ================================================================
    print("Stage 5: Device binary overrides...")

    # install.so from device_so (v1.0.90, matching device)
    install_so = os.path.join(DEVICE_SO, "install.so")
    if os.path.exists(install_so):
        manifest["main/install.so"] = ('device_so', install_so, os.path.getsize(install_so))
        print(f"  main/install.so → device_so ({os.path.getsize(install_so):,d} bytes)")

    # version.so from device_so (SN 02150004, required by checkPkg + checkVer)
    version_so = os.path.join(DEVICE_SO, "version.so")
    if os.path.exists(version_so):
        manifest["lib/version.so"] = ('device_so', version_so, os.path.getsize(version_so))
        print(f"  lib/version.so → device_so ({os.path.getsize(version_so):,d} bytes)")

    # version_universal.py → lib/version.py (runtime replacement)
    version_py = os.path.join(DEVICE_SO, "version_universal.py")
    if os.path.exists(version_py):
        manifest["lib/version.py"] = ('src_file', version_py, os.path.getsize(version_py))
        print(f"  lib/version.py → version_universal.py")

    # ================================================================
    # Verification
    # ================================================================
    print("\n=== Verification ===")

    # checkPkg requirements
    for required in ("app.py", "lib/version.so", "main/install.so"):
        if required in manifest:
            print(f"  ✓ {required} present")
        else:
            print(f"  ✗ {required} MISSING — install will fail with 0x05!")
            return False

    # install_font requirements
    font_files = [p for p in manifest if p.startswith("res/font/")]
    if font_files:
        print(f"  ✓ res/font/ has {len(font_files)} files")
    else:
        print(f"  ✗ res/font/ MISSING — install will fail with 0x03!")
        return False

    # No replaced .so leaked
    for mod in REPLACED_SO:
        bad = f"lib/{mod}.so"
        if bad in manifest:
            print(f"  ✗ {bad} still in IPK — .so will shadow our .py!")
            return False
    print(f"  ✓ No replaced .so files in IPK")

    # Summary
    so_count = sum(1 for p in manifest if p.startswith("lib/") and p.endswith(".so"))
    py_count = sum(1 for p in manifest if p.startswith("lib/") and p.endswith(".py"))
    print(f"\n  Total files: {len(manifest)}")
    print(f"  lib/*.so (middleware): {so_count}")
    print(f"  lib/*.py (our UI): {py_count}")
    print(f"  screens/*.json: {json_count}")

    if dry_run:
        print("\nDRY RUN — no IPK created.")
        return True

    # ================================================================
    # Build the ZIP
    # ================================================================
    print(f"\nWriting {output_path} ...")

    with zipfile.ZipFile(ORIGINAL_IPK, 'r') as orig_zf:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zf:
            for ipk_path, (source_type, source_detail, size) in sorted(manifest.items()):
                if source_type == 'original_ipk':
                    # Copy from original IPK
                    data = orig_zf.read(source_detail)
                    out_zf.writestr(ipk_path, data)
                elif source_type in ('src_file', 'device_so'):
                    # Copy from local file
                    out_zf.write(source_detail, ipk_path)
                elif source_type == 'empty':
                    out_zf.writestr(ipk_path, b'')

    total_size = os.path.getsize(output_path)
    print(f"IPK created: {output_path} ({total_size:,d} bytes)")

    # Final verification
    with zipfile.ZipFile(output_path, 'r') as zf:
        names = set(zf.namelist())
        for required in ("app.py", "lib/version.so", "main/install.so"):
            assert required in names, f"MISSING in final IPK: {required}"
        for mod in REPLACED_SO:
            assert f"lib/{mod}.so" not in names, f"LEAKED: lib/{mod}.so"

    print("Final verification passed.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Build No-Flash OG-Middleware IPK for iCopy-X")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT,
                        help=f"Output path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print manifest without creating IPK")
    args = parser.parse_args()

    ok = build(args.output, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
