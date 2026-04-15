# How to Jailbreak an iCopy-X Device

## Overview

The iCopy-X ships with closed-source firmware protected by a serial-number
DRM lock. Each firmware update package (`.ipk`) must contain a `version.so`
compiled for the specific target device — if the serial number inside the
`.so` doesn't match the device's own serial, the update is rejected.

This document describes how to install the open-source firmware on any
iCopy-X device, bypassing the DRM entirely, using only the USB drive the
device already supports.

**No network, no SSH, no soldering. One USB stick.**

---

## Prerequisites

| Item | Notes |
|------|-------|
| iCopy-X device | Any model, any serial number |
| USB drive | FAT32, the device reads from `/mnt/upan/` |
| This repo checked out | With `tools/universal_version/version.so` built |
| ARM cross-compiler | Only if rebuilding `version.so` (pre-built binary included) |

---

## How the DRM Works

The original firmware's update handler (`activity_update.so`) performs three
checks when the user triggers an update from the About screen:

```
1. checkPkg — ZIP must contain:
     app.py
     lib/version.so     ← compiled ARM .so, NOT a .py file
     main/install.so    ← compiled ARM .so

2. checkVer — loads lib/version.so from the IPK via ExtensionFileLoader,
   reads its SERIAL_NUMBER attribute, compares against the running device's
   version.SERIAL_NUMBER. Mismatch → error 0x04, install rejected.

3. install — loads main/install.so from the IPK, calls install.install()
   to copy files to /home/pi/ipk_app_new. On next reboot, ipk_starter.py
   swaps ipk_app_new → ipk_app_main.
```

Key facts established by QEMU tracing:

- `ExtensionFileLoader` **cannot** load `.py` files — it requires ELF
  binaries with a matching `PyInit_<name>` export.
- `install.so` contains **no DRM** — it is purely a file copier.
- `version.so` is the only DRM-relevant component. The serial number is
  a string attribute read at import time.

## How the Bypass Works

We ship a **universal `version.so`** — a 9KB ARM binary that, when loaded
by `checkVer`, reads the device's own serial number from `sys.modules` and
mirrors it back.

The device boots and loads its genuine `version.so` into `sys.modules["version"]`
with the real `SERIAL_NUMBER`. Later, when the update UI loads our IPK's
`lib/version.so` as a separate module instance via `ExtensionFileLoader`,
our code runs:

```c
sys_modules = PySys_GetObject("modules");          // get sys.modules dict
running_ver = PyDict_GetItemString(sys_modules, "version");  // already-loaded module
val = PyObject_GetAttrString(running_ver, "SERIAL_NUMBER");  // device's real SN
PyModule_AddObject(module, "SERIAL_NUMBER", val);   // set it on ourselves
```

The comparison that `checkVer` performs — `ipk_version.SERIAL_NUMBER ==
running_version.SERIAL_NUMBER` — passes, because the two values are
identical by construction.

```
Device boots:       version.SERIAL_NUMBER = "02150004"   (from device's own .so)
checkVer loads IPK: version.SERIAL_NUMBER = "02150004"   (mirrored from sys.modules)
Comparison:         "02150004" == "02150004" → PASS
```

This works on **any** device, regardless of serial number, without
knowing the serial in advance.

---

## Building the Jailbreak IPK

The jailbreak IPK must satisfy the original firmware's `checkPkg` by
including `lib/version.so` and `main/install.so` as compiled ARM binaries.
It also includes all the open-source Python files that will replace the
closed-source firmware after installation.

### Step 1: Build the universal version.so (if not already built)

```bash
arm-linux-gnueabihf-gcc -shared -fPIC -O2 \
  -I/mnt/sdcard/root2/root/usr/local/python-3.8.0/include/python3.8 \
  -o tools/universal_version/version.so \
  tools/universal_version/version_universal.c
```

Verify:

```bash
file tools/universal_version/version.so
# → ELF 32-bit LSB shared object, ARM, EABI5 ...

strings tools/universal_version/version.so | grep PyInit_version
# → PyInit_version
```

A pre-built binary is committed at `tools/universal_version/version.so`.

### Step 2: Build the IPK

The jailbreak IPK needs the standard build output **plus** two ARM binaries
that the original firmware requires:

| IPK path | Source | Purpose |
|----------|--------|---------|
| `lib/version.so` | `tools/universal_version/version.so` | Passes `checkVer` DRM |
| `main/install.so` | `device_so/install.so` | Passes `checkPkg`, copies files |
| `lib/version.py` | `device_so/version_universal.py` | Runtime version module (after boot) |
| `main/install.py` | `src/main/install.py` | Runtime installer (for future updates) |
| everything else | `src/lib/`, `src/middleware/`, `src/screens/` | The OSS firmware |

Build with:

```bash
python3 tools/build_ipk.py --output icopy-x-jailbreak.ipk
```

Then inject the two ARM binaries the original firmware requires:

```bash
python3 -c "
import zipfile
with zipfile.ZipFile('icopy-x-jailbreak.ipk', 'a') as zf:
    zf.write('tools/universal_version/version.so', 'lib/version.so')
    zf.write('device_so/install.so', 'main/install.so')
"
```

Verify the IPK contains all three required files:

```bash
python3 -c "
import zipfile
with zipfile.ZipFile('icopy-x-jailbreak.ipk') as zf:
    for req in ['app.py', 'lib/version.so', 'main/install.so']:
        info = zf.getinfo(req)
        print(f'  {req:30s} {info.file_size:>10,d} bytes')
"
```

### Step 3: Install on device

1. Copy `icopy-x-jailbreak.ipk` to a FAT32 USB drive (root directory).
2. Insert the USB drive into the iCopy-X device.
3. On the device, navigate: **Main Menu** → **About** → press **DOWN** → press **OK** ("Update").
4. The update screen appears. Press **M2** ("Start").
5. The device extracts the IPK, runs `checkPkg` (pass), runs `checkVer` (pass — universal bypass), then calls `install.so` to copy files.
6. The device reboots automatically.
7. On boot, `ipk_starter.py` detects `/home/pi/ipk_app_new` and swaps it into `/home/pi/ipk_app_main`.
8. The open-source firmware is now running.

### Step 4: Verify

After reboot, the device should show:
- OS version: `2.0.0` (from our `version.py`)
- All menu items functional
- No `.so` modules in the execution path (except the PM3 binary)

---

## After the Jailbreak

Once the OSS firmware is running, the DRM is permanently gone:

- Our `update.py` replaces the original `activity_update.so`.
- It has **no `checkVer`** — no serial number check at all.
- It accepts `.py` installers, not just `.so`.
- Future updates are delivered as standard IPKs via USB, with no DRM
  binaries required.

The universal `version.so` and the genuine `install.so` are only needed
for the **first** install onto a device still running the original firmware.

---

## Reverting to Original Firmware

The original firmware is preserved. The device's `ipk_starter.py` renames
the old firmware directory before swapping:

```
/home/pi/ipk_app_main  →  /home/pi/ipk_app_old    (original firmware)
/home/pi/ipk_app_new   →  /home/pi/ipk_app_main   (OSS firmware)
```

To revert: build an IPK containing the original firmware files and install
it via the same USB update process. The OSS firmware's update handler has
no DRM, so any valid IPK will be accepted.

If a backup was made before jailbreaking (`/home/pi/ipk_app_main.bak`),
restoring it to `/home/pi/ipk_app_new` and rebooting will restore the
original firmware.

---

## Technical Reference

### Files

| File | Description |
|------|-------------|
| `tools/universal_version/version_universal.c` | C source for the universal bypass module |
| `tools/universal_version/version.so` | Pre-built ARM binary (9KB) |
| `device_so/install.so` | Genuine ARM installer from original firmware (98KB) |
| `src/main/install.py` | OSS transliteration of install.so (used by future updates) |
| `docs/DRM-Install-Analysis.md` | Full DRM analysis with QEMU trace results |

### Build environment

| Component | Location |
|-----------|----------|
| ARM cross-compiler | `/home/qx/.local/bin/arm-linux-gnueabihf-gcc` (13.3.1) |
| Python 3.8 headers | `/mnt/sdcard/root2/root/usr/local/python-3.8.0/include/python3.8` |
| QEMU ARM user-mode | `/home/qx/.local/bin/qemu-arm-static` |

### Original firmware DRM flow (activity_update.so)

```
UpdateActivity.checkPkg(ipk_path)
  → zipfile.ZipFile(ipk).namelist() must include:
      app.py, lib/version.so, main/install.so

UpdateActivity.checkVer(unpkg_path)
  → path_import(os.path.join(unpkg, 'lib', 'version.so'))
      → importlib.machinery.ExtensionFileLoader('version', path)
      → spec.loader.exec_module(mod)
  → ipk_sn = mod.SERIAL_NUMBER
  → running_sn = version.SERIAL_NUMBER  (from sys.modules)
  → if ipk_sn != running_sn: error 0x04

UpdateActivity.install(unpkg_path)
  → path_import(os.path.join(unpkg, 'main', 'install.so'))
  → mod.install(unpkg_path, callback)
      → install_font()  — copy fonts from res/font/
      → install_lua_dep() — extract lua.zip from /mnt/upan/
      → install_app() — move unpkg → /home/pi/ipk_app_new
      → update_permission() — chmod 777 -R
      → restart_app() — sudo service icopy restart &
```

### Why other approaches don't work

| Approach | Problem |
|----------|---------|
| Ship `lib/version.py` instead of `.so` | `ExtensionFileLoader` rejects `.py` — "invalid ELF header" |
| Skip `lib/version.so` from IPK | `checkPkg` fails — file is in the required list |
| Patch the serial in a binary `version.so` | Device-specific — need a separate build per device |
| Python import order tricks | `checkVer` uses explicit `ExtensionFileLoader`, not `import` |
| LD_PRELOAD / fake cpuinfo | QEMU user-mode doesn't propagate `LD_PRELOAD` |
