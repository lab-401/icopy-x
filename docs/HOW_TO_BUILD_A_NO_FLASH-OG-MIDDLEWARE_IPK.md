# HOW TO BUILD A "No Flash, Original Middleware" IPK

**Verified**: Both the original IPK and our No-Flash OG-Middleware IPK install
successfully through the real original firmware install flow in QEMU (2026-04-06).

## What This IPK Is

A **No Flash, Original Middleware** IPK replaces ONLY the UI layer with our
open-source Python implementation. It does NOT:
- Flash the Proxmark3 module (no `fullimage.elf` flashing)
- Replace any RFID middleware `.so` files (scan.so, read.so, write.so, etc.)
- Modify the device's bootloader or firmware

It DOES:
- Replace the UI activity modules (activity_main.so → activity_main.py, etc.)
- Install JSON screen definitions (`screens/*.json`)
- Include the erase middleware (`lib/erase.py` — split from monolithic activity_main.so)
- Keep ALL original middleware `.so` files intact
- Ship `version.so` (SN-locked) for install validation + `version.py` for runtime

---

## ABSOLUTE LAWS

### Ground Truth Sources (ONLY these)
1. **Original decompiled .so files**: `decompiled/*.txt`
2. **Real device traces**: `docs/Real_Hardware_Intel/trace_*.txt`
3. **Real device screenshots**: `docs/Real_Hardware_Intel/Screenshots/*.png`
4. **Original IPK**: `/home/qx/02150004_1.0.90.ipk` (canonical reference, 205 files)

### Rules
1. **Tests are immutable.** NEVER edit test files.
2. **The `.so` middleware IS the logic.** Our Python activities call `.so` modules. They do NOT reimplement RFID operations.
3. **Never guess.** Every file, every path, every parameter must trace to a ground truth.
4. **Never put logic in the UI.** PM3 commands come from `.so` modules only.
5. **Never deviate from ground-truth resources** to make tests pass or shortcut tasks.
6. **NEVER flash PM3 bootrom.** No JTAG = bricked device.
7. **After writing code, audit it.** Does every line trace to ground truth? If not, undo it.

---

## IPK FORMAT (verified from original IPK + successful install trace)

An IPK is a **ZIP archive** with `.ipk` extension. The install flow finds it via
`os.listdir('/mnt/upan/')` filtering for `.ipk` files.

### Required Structure
```
.ipk (ZIP archive)
├── app.py                    # Entry point (checkPkg VALIDATES this exists)
├── nikola                    # Empty marker file
├── manifest.json             # Metadata with CRC32 checksums
├── main/
│   ├── __init__.py
│   ├── install.so            # Installer module (checkPkg VALIDATES this exists)
│   ├── main.so               # Main entry point
│   └── rftask.so             # RF task handler
├── lib/
│   ├── __init__.py
│   ├── version.so            # Version module (checkPkg VALIDATES this exists)
│   ├── version.py            # Universal version replacement (runtime)
│   ├── *.py                  # Our Python UI modules
│   ├── erase.py              # Erase middleware (split from activity_main.so)
│   ├── *.so                  # Original v1.0.90 middleware .so files
│   └── ...
├── screens/
│   └── *.json                # JSON UI screen definitions
├── pm3/
│   ├── proxmark3             # PM3 client binary
│   └── lua.zip               # PM3 Lua scripts
└── res/
    ├── audio/*.wav           # Audio files (41 files)
    ├── firmware/
    │   ├── app/GD32_APP_v1.4.nib
    │   └── pm3/fullimage.elf
    ├── font/
    │   ├── font_install.txt  # MUST exist (install_font() requires it)
    │   ├── mononoki-Regular.ttf
    │   └── monozhwqy.ttf
    └── img/*.png             # UI icons (28 files)
```

### Three Files checkPkg Validates
Ground truth: `strings activity_update.so` → `app.py`, `main/install.so`, `lib/version.so`

| File | Path in ZIP | Source |
|------|------------|--------|
| `app.py` | `app.py` (root) | From original IPK (863 bytes) |
| `install.so` | `main/install.so` | `device_so/install.so` (98,188 bytes) |
| `version.so` | `lib/version.so` | `device_so/version.so` (82,856 bytes, SN 02150004) |

---

## INSTALL FLOW (traced and verified in QEMU 2026-04-06)

The install is driven by the original `activity_update.so` and `update.so` modules.
The complete flow, verified via `tools/launcher_install_test.py` tracing:

```
1. AboutActivity.checkUpdate()
   → os.listdir('/mnt/upan/') finds .ipk file
   → shutil.move() moves IPK to /mnt/upan/ipk_old/ (backup)
   → Launches UpdateActivity with moved file path

2. UpdateActivity.search()
   → os.system('sudo mount -o rw /dev/mmcblk0p4 /mnt/upan/')
   → Opens ZIP, reads namelist (225 files for our IPK)

3. UpdateActivity.unpkg()
   → shutil.rmtree('/tmp/.ipk/unpkg')
   → Extracts ALL files to /tmp/.ipk/unpkg/ via zipfile.read() + file write
   → Creates subdirectories: lib/, main/, pm3/, res/, screens/

4. install_font()
   → os.listdir('/tmp/.ipk/unpkg/res/font') finds font files
   → Copies fonts to /usr/share/fonts/

5. update_permission()
   → os.system('chmod 777 -R /tmp/.ipk/unpkg')

6. install_app()
   → shutil.rmtree('/home/pi/unpkg')
   → shutil.rmtree('/home/pi/ipk_app_new')
   → shutil.move('/tmp/.ipk/unpkg', '/home/pi/')
   → os.system('sudo service icopy restart &')
```

### Install Error Codes (from archive transliteration + tracing)
| Code | Stage | Meaning |
|------|-------|---------|
| 0x01 | search() | No .ipk files found in /mnt/upan/ |
| 0x02 | search()/move | File found but can't be moved/opened (path error) |
| 0x03 | install() | Crash during font install or file copy |
| 0x04 | checkVer | SERIAL_NUMBER mismatch or version.so import failure |
| 0x05 | checkPkg | Missing app.py, lib/version.so, or main/install.so |

---

## DRM BYPASS: The version.so Problem

### The Problem
`checkVer()` loads `lib/version.so` from the extracted IPK via `ExtensionFileLoader`,
reads `SERIAL_NUMBER`, and compares against the running device's serial. Mismatch → error 0x04.

### The Solution
Ship BOTH files:
- `lib/version.so` — Original binary (SN 02150004). Satisfies `checkPkg` existence check
  AND `checkVer` serial validation.
- `lib/version.py` — Universal replacement (`device_so/version_universal.py`). At runtime,
  Python imports `.py` over `.so` in the same directory for standard imports. This provides
  auto-detected serial number for DRM checks.

**For device SN 02150004**: The `device_so/version.so` has matching SN. Install passes.

**For other devices**: Would need device-specific `version.so` with matching SN compiled in.

---

## SOURCE FILES

### v1.0.90 .so Files (Middleware)
**Source**: Original IPK `/home/qx/02150004_1.0.90.ipk`

**NOT from `orig_so/`** — those are v1.0.3 from the SD card image (WRONG version,
different file sizes, different Cython version).

### Python UI Modules
**Source**: `src/lib/*.py` (17 files)

### Erase Middleware
**Source**: `src/middleware/erase.py` → shipped as `lib/erase.py`

The original firmware has NO `erase.so`. Erase logic was embedded in the monolithic
`activity_main.so`. Our reimplementation splits it into a clean module imported by
`activity_main.py` at lines 2577, 2619 (`import erase as _erase`).

### JSON Screen Definitions
**Source**: `src/screens/*.json` (18 files)

### Device Binaries
**Source**: `device_so/`

| File | Size | Purpose |
|------|------|---------|
| `install.so` | 98,188 | ARM ELF installer (v1.0.90) |
| `version.so` | 82,856 | ARM ELF version module (SN 02150004) |
| `version_universal.py` | 1,626 | Universal version replacement |
| `proxmark3` | 1,942,640 | ARM ELF PM3 client |

### Resources, app.py, nikola, __init__.py
**Source**: Original IPK (byte-identical copies via the build script baseline)

---

## MODULES REPLACED BY PYTHON

These `.so` files are EXCLUDED from the IPK — our `.py` files replace them:

| Module | Excluded .so | Our .py | Purpose |
|--------|-------------|---------|---------|
| actbase | actbase.so | actbase.py | Base activity class |
| actmain | actmain.so | actmain.py | Activity registry |
| actstack | actstack.so | actstack.py | Activity stack manager |
| activity_main | activity_main.so | activity_main.py | All UI activities |
| activity_tools | activity_tools.so | activity_tools.py | Tool activities |
| hmi_driver | hmi_driver.so | hmi_driver.py | HMI serial driver |
| images | images.so | images.py | Image loader |
| keymap | keymap.so | keymap.py | Key event mapper |
| resources | resources.so | resources.py | String/font resources |
| widget | widget.so | widget.py | UI widgets |

**CRITICAL**: Python 3.8 imports `.so` before `.py` in the same directory. The build
script MUST exclude these `.so` files so our `.py` replacements are used.

---

## BUILD PROCEDURE

### Build Tool
```bash
python3 tools/build_noflash_ipk.py --output test-install.ipk
```

The build script (`tools/build_noflash_ipk.py`):
1. Loads ALL 205 files from the original IPK as a baseline
2. Adds our Python UI modules from `src/lib/` (overrides original .so counterparts)
3. Adds erase middleware from `src/middleware/erase.py` → `lib/erase.py`
4. Removes replaced `.so` files (the 10 modules listed above)
5. Adds JSON screen definitions from `src/screens/`
6. Overrides `main/install.so` and `lib/version.so` from `device_so/`
7. Adds `lib/version.py` (universal version replacement)
8. Verifies: checkPkg files present, no replaced .so leaked, font dir exists
9. Outputs ZIP with 225 files

### Verification
```bash
python3 -c "
import zipfile
with zipfile.ZipFile('test-install.ipk') as zf:
    names = set(zf.namelist())
    assert 'app.py' in names, 'MISSING: app.py'
    assert 'lib/version.so' in names, 'MISSING: lib/version.so'
    assert 'main/install.so' in names, 'MISSING: main/install.so'
    assert 'lib/activity_main.py' in names, 'MISSING: activity_main.py'
    assert 'lib/erase.py' in names, 'MISSING: erase.py'
    assert 'lib/activity_main.so' not in names, 'LEAKED: activity_main.so'
    print(f'OK: {len(names)} files')
"
```

---

## TESTING IN QEMU

### QEMU Path Duality (CRITICAL)

QEMU user-mode with `QEMU_LD_PREFIX=/mnt/sdcard/root2/root` translates ALL ARM
syscalls (open, stat, readdir) by prepending the prefix. BUT Python's `shutil`
module operates on host paths directly. This creates a path duality:

- `os.listdir('/mnt/upan/')` → QEMU translates → reads `/mnt/sdcard/root2/root/mnt/upan/`
- `shutil.move('/mnt/upan/file.ipk', ...)` → operates on HOST `/mnt/upan/`

**Solution**: Symlink the QEMU rootfs path to the host path:

```bash
# REQUIRED before ANY install testing
rm -rf /mnt/sdcard/root2/root/mnt/upan      # Remove directory
ln -sf /mnt/upan /mnt/sdcard/root2/root/mnt/upan  # Symlink to host

# Also symlink /tmp/.ipk for extraction (but NOT /tmp itself — breaks Python)
mkdir -p /tmp/.ipk
ln -sf /tmp/.ipk /mnt/sdcard/root2/root/tmp/.ipk
```

**WARNING**: Do NOT symlink `/tmp` or `/home/pi` entirely — this breaks the QEMU
Python environment (site-packages, pygame, etc. live in the rootfs under those paths).

### Automated Test Script
```bash
bash tools/test_ipk_install.sh /path/to/file.ipk
```

This script:
1. Restores QEMU rootfs from backup
2. Places IPK at both host and QEMU paths
3. Boots QEMU with `tools/launcher_install_test.py` (traced launcher)
4. Navigates: GOTO:10 → DOWN → OK (triggers install)
5. Polls state dumps for install result toast
6. Verifies installed files
7. Reports PASS/FAIL

### Smoke Test (Always Run First)
```bash
# Verify the ORIGINAL IPK installs correctly
bash tools/test_ipk_install.sh /home/qx/02150004_1.0.90.ipk
```

If this fails → the QEMU environment is broken, not the IPK.

### Install Test Launcher

`tools/launcher_install_test.py` is a dedicated launcher for install testing.
It is based on `launcher_original.py` but adds:
- `os.system` tracing (logs all commands, stubs mount/service/reboot)
- `os.listdir` tracing for upan/ipk/tmp paths
- `os.path.exists` tracing for install-related paths
- `shutil.*` tracing (move, copy, rmtree)
- `zipfile.ZipFile` tracing (open, read, extract, namelist)
- `os.makedirs` tracing
- Global exception hook for silent failures

**This launcher is SEPARATE from `launcher_original.py`** — never edit the test launcher.

### Post-Install Verification
```bash
# Files installed to /home/pi/unpkg/ (on host, via shutil.move)
ls /home/pi/unpkg/lib/activity_main.py     # Our Python UI
ls /home/pi/unpkg/lib/erase.py             # Erase middleware
ls /home/pi/unpkg/lib/scan.so              # Original middleware
ls /home/pi/unpkg/screens/about.json       # JSON screens
```

On the real device, the next boot swaps `ipk_app_new` → `ipk_app_main`.

---

## KNOWN ISSUES AND MITIGATIONS

### Issue 1: orig_so/ has v1.0.3, device runs v1.0.90
**Status**: RESOLVED. Build script reads from original IPK, not orig_so/.

### Issue 2: QEMU path duality for file operations
**Status**: RESOLVED. Symlink `/mnt/sdcard/root2/root/mnt/upan` → `/mnt/upan`.
Documented above. Do NOT symlink `/tmp` or `/home/pi` entirely.

### Issue 3: install_font() requires res/font/ directory
**Status**: RESOLVED. Build script includes `res/font/font_install.txt` from original IPK.

### Issue 4: Python .so import priority
**Status**: RESOLVED. Build script excludes replaced `.so` files from IPK.

### Issue 5: QEMU environment becomes dirty after install
**Status**: MITIGATED. Test script restores from backup before each attempt.
If site-packages are lost (e.g., from accidental `/home/pi` symlink), restore
from the local machine: `rsync -az /mnt/sdcard/root2/root/home/pi/.local/ remote:/mnt/sdcard/root2/root/home/pi/.local/`

---

## TOOLS

| Tool | Purpose |
|------|---------|
| `tools/build_noflash_ipk.py` | Build No-Flash OG-Middleware IPK from original IPK + our code |
| `tools/test_ipk_install.sh` | Automated QEMU install test with backup/restore |
| `tools/launcher_install_test.py` | Traced QEMU launcher for install debugging |
| `tools/compare_ui_states.py` | Pixel-level state dump comparison |

---

## CHECKLIST

- [x] v1.0.90 .so files sourced from original IPK (NOT orig_so/)
- [x] Python UI modules from src/lib/ (17 files)
- [x] Erase middleware from src/middleware/erase.py → lib/erase.py
- [x] JSON screens from src/screens/ (18 files)
- [x] app.py, nikola, manifest.json from original IPK
- [x] lib/__init__.py and main/__init__.py from original IPK
- [x] device_so/install.so → main/install.so (98,188 bytes)
- [x] device_so/version.so → lib/version.so (82,856 bytes, SN 02150004)
- [x] device_so/version_universal.py → lib/version.py
- [x] res/font/font_install.txt exists (557 bytes)
- [x] res/ directory complete (audio, fonts, images, firmware)
- [x] pm3/proxmark3 and pm3/lua.zip included
- [x] QEMU upan symlink set up
- [x] No replaced .so files in final IPK (verified by build script)
- [x] checkPkg files verified (app.py, lib/version.so, main/install.so)
- [x] Original IPK smoke test PASSES in QEMU
- [x] Our IPK installs successfully in QEMU (225 files extracted)
