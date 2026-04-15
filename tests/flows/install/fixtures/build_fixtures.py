#!/usr/bin/env python3
"""Build all IPK fixture files for the INSTALL flow test suite.

Each fixture is a ZIP file (.ipk) crafted to provoke a specific branch
in the activity_update.so → install.so pipeline.

Ground truth sources:
  - decompiled/activity_update_ghidra_raw.txt (checkPkg, checkVer, install)
  - decompiled/install_ghidra_raw.txt (install.so functions)
  - docs/UI_Mapping/19_install/README.md (full logic tree)
  - docs/v1090_strings/install_so_analysis.md (callback messages)

Required inputs:
  - orig_so/lib/version.so  (real device version module, contains SERIAL_NUMBER)
  - decompiled/install.so   (real device install module from IPK)

Usage:
  python3 tests/flows/install/fixtures/build_fixtures.py
"""

import os
import sys
import shutil
import struct
import zipfile

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
FIXTURE_DIR = os.path.dirname(__file__)

VERSION_SO = os.path.join(PROJECT, 'orig_so', 'lib', 'version_v1090.so')
INSTALL_SO = os.path.join(PROJECT, 'decompiled', 'install.so')

# The serial number in v1.0.90 version.so: "02150004" at 3 offsets
SERIAL_BYTES = b'02150004'
WRONG_SERIAL = b'99999999'


def check_inputs():
    for path, name in [(VERSION_SO, 'version_v1090.so'), (INSTALL_SO, 'install.so')]:
        if not os.path.isfile(path):
            print(f"ERROR: {name} not found at {path}")
            sys.exit(1)
    # Verify serial is present
    with open(VERSION_SO, 'rb') as f:
        data = f.read()
    count = data.count(SERIAL_BYTES)
    if count == 0:
        print(f"ERROR: Serial {SERIAL_BYTES!r} not found in {VERSION_SO}")
        sys.exit(1)
    print(f"version.so serial verified: {SERIAL_BYTES.decode()} ({count} occurrences)")


def make_app_py():
    """Minimal app.py stub — required by checkPkg."""
    return b'# app.py stub for test fixture\n'


def make_wrong_serial_version_so():
    """Binary-patch ALL occurrences of the serial in version.so."""
    with open(VERSION_SO, 'rb') as f:
        data = f.read()
    patched = data.replace(SERIAL_BYTES, WRONG_SERIAL)
    count = data.count(SERIAL_BYTES)
    print(f"    Patched {count} serial occurrences: {SERIAL_BYTES.decode()} → {WRONG_SERIAL.decode()}")
    return patched


def make_corrupt_install_so():
    """A file named install.so that is not a valid ELF — triggers load failure."""
    return b'NOT_AN_ELF_THIS_IS_CORRUPT_DATA_FOR_TESTING\x00' * 10


def make_dummy_font():
    """Minimal .ttf stub to trigger the font install path."""
    # A minimal TrueType header (not a real font, but enough for
    # install_font() to find *.ttf files and attempt to copy them)
    return b'\x00\x01\x00\x00' + b'\x00' * 100


def build_ipk(name, contents):
    """Create a ZIP file at FIXTURE_DIR/name with the given contents dict.

    contents: {archive_path: bytes_data, ...}
    """
    path = os.path.join(FIXTURE_DIR, name)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for arcname, data in contents.items():
            zf.writestr(arcname, data)
    size = os.path.getsize(path)
    print(f"  {name} ({size:,} bytes, {len(contents)} files)")
    return path


def build_corrupt_ipk(name):
    """Create a file that is NOT a valid ZIP."""
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, 'wb') as f:
        f.write(b'THIS IS NOT A ZIP FILE\x00' * 20)
    size = os.path.getsize(path)
    print(f"  {name} ({size:,} bytes, corrupt)")
    return path


def read_binary(path):
    with open(path, 'rb') as f:
        return f.read()


def main():
    print("=== Building INSTALL flow IPK fixtures ===\n")
    check_inputs()

    version_so_data = read_binary(VERSION_SO)
    install_so_data = read_binary(INSTALL_SO)
    app_py_data = make_app_py()

    print("\nGenerating fixtures:\n")

    # --- Fixture 1: valid_minimal.ipk ---
    # Complete valid IPK with real binaries. No fonts, no lua.
    # Triggers: full install pipeline success path
    # Expected: "No Font can install." → "Permission Updating..." →
    #           "lua.zip no found..." or "LUA dep exists..." →
    #           "App installed!" → "App restarting..."
    build_ipk('valid_minimal.ipk', {
        'app.py': app_py_data,
        'lib/version.so': version_so_data,
        'main/install.so': install_so_data,
    })

    # --- Fixture 2: valid_with_fonts.ipk ---
    # Valid IPK with a font file in res/font/
    # Triggers: " Font will install..." → " Font installed." path
    build_ipk('valid_with_fonts.ipk', {
        'app.py': app_py_data,
        'lib/version.so': version_so_data,
        'main/install.so': install_so_data,
        'res/font/test_fixture.ttf': make_dummy_font(),
    })

    # --- Fixture 3: invalid_zip.ipk ---
    # Not a valid ZIP file
    # Triggers: checkPkg() → not a valid ZIP → error 0x05
    build_corrupt_ipk('invalid_zip.ipk')

    # --- Fixture 4: no_app.ipk ---
    # Valid ZIP but missing app.py
    # Triggers: checkPkg() → missing required file → error 0x05
    build_ipk('no_app.ipk', {
        'lib/version.so': version_so_data,
        'main/install.so': install_so_data,
    })

    # --- Fixture 5: no_version.ipk ---
    # Valid ZIP with app.py but no lib/version.so
    # Triggers: checkPkg() → missing version.so → error 0x05
    build_ipk('no_version.ipk', {
        'app.py': app_py_data,
        'main/install.so': install_so_data,
    })

    # --- Fixture 6: no_install.ipk ---
    # Valid ZIP with app.py + version.so but no main/install.so
    # Triggers: checkPkg() → missing install module → error 0x05
    build_ipk('no_install.ipk', {
        'app.py': app_py_data,
        'lib/version.so': version_so_data,
    })

    # --- Fixture 7: wrong_serial.ipk ---
    # Valid ZIP but version.so has mismatched SERIAL_NUMBER
    # Triggers: checkVer() → serial mismatch → error 0x04
    build_ipk('wrong_serial.ipk', {
        'app.py': app_py_data,
        'lib/version.so': make_wrong_serial_version_so(),
        'main/install.so': install_so_data,
    })

    # --- Fixture 8: corrupt_install.ipk ---
    # Valid ZIP, correct version.so, but install.so is unloadable
    # Triggers: path_import('install') fails → error 0x03
    build_ipk('corrupt_install.ipk', {
        'app.py': app_py_data,
        'lib/version.so': version_so_data,
        'main/install.so': make_corrupt_install_so(),
    })

    print(f"\nDone. {len(os.listdir(FIXTURE_DIR))} files in {FIXTURE_DIR}")


if __name__ == '__main__':
    main()
