# Install DRM Analysis & Jailbreak

## TL;DR

The iCopy-X update DRM has been **fully analyzed and bypassed**. The jailbreak
uses direct SSH file staging, completely skipping the DRM check.

**install.so** has been replaced with an open-source `install.py`.  
**The IPK now contains 1 .so file** (version_orig.so for SN extraction only).

---

## DRM Mechanism (activity_update.so)

The serial number check is NOT in `install.so` — it's in `activity_update.so`'s
`checkVer()` method (which we've already replaced with our DRM-free `update.py`).

### Original Update Flow

```
1. AboutActivity → finds .ipk on USB drive
2. activity_update.so.checkPkg(ipk)
   → Validates ZIP contains: app.py, lib/version.so, main/install.so
3. activity_update.so.checkVer(unpkg_path)
   → path_import: ExtensionFileLoader('version', 'lib/version.so')
   → Reads module.SERIAL_NUMBER
   → Compares against running device's version.SERIAL_NUMBER
   → MISMATCH → error 0x04, install blocked
4. activity_update.so.install(unpkg_path)
   → path_import: ExtensionFileLoader('install', 'main/install.so')
   → Calls install.install(unpkg_path, callback)
```

### Key Findings (from QEMU trace, 2026-04-09)

1. **ExtensionFileLoader CANNOT load .py files** — returns "invalid ELF header".
   The original firmware's `path_import` can ONLY load compiled ARM .so modules.

2. **version.so has transitive import dependencies** — loading it triggers:
   `version → executor → hmi_driver → batteryui → audio → pygame`.
   It cannot be loaded in isolation.

3. **install.so has NO import dependencies** — loads cleanly in isolation.
   It's a pure file copier with zero DRM.

4. **install.so function signatures confirmed under QEMU:**
   - `install_font(unpkg_path, callback)` — copies fonts from res/font/
   - `install_lua_dep(unpkg_path, callback)` — extracts lua.zip from /mnt/upan/
   - `update_permission(unpkg_path, callback)` — chmod 777 -R
   - `install_app(unpkg_path, callback)` — moves unpkg → /home/pi/ipk_app_new
   - `restart_app(callback)` — os.system('sudo service icopy restart &')
   - `install(unpkg_path, callback)` — orchestrator calling all of the above

5. **Callback signature:** `callback(name: str, progress: int)`
   Progress values: 30, 38, 60, 100.

---

## Why We Can't Use the Original Update UI

Our OSS IPK cannot be installed through the original firmware's update UI because:

| Check | Requirement | Our IPK | Result |
|-------|------------|---------|--------|
| checkPkg | `lib/version.so` exists | We ship `lib/version.py` | **FAIL** |
| checkPkg | `main/install.so` exists | We ship `main/install.py` | **FAIL** |
| checkVer | ExtensionFileLoader loads version.so | .py can't be loaded this way | **FAIL** |
| checkVer | SERIAL_NUMBER matches device | Our version.py is universal | N/A |

Even if we shipped both .py and .so versions, the original firmware's checkVer
would load the .so version, and it would need to match the specific device's
serial number — making the IPK device-specific.

---

## Jailbreak Approach

**Method: Direct SSH file staging** — the simplest and most reliable bypass.

Since we have root SSH access to the device (`root:fa`, port 2222), we skip
the update UI entirely:

```bash
# 1. Upload IPK to device
scp -P 2222 icopy-x-oss.ipk root@device:/tmp/

# 2. Extract and stage
ssh -p 2222 root@device "
  rm -rf /home/pi/ipk_app_new
  mkdir -p /tmp/ipk_extract
  cd /tmp/ipk_extract && unzip -q /tmp/icopy-x-oss.ipk
  mv /tmp/ipk_extract /home/pi/ipk_app_new
  chmod -R 777 /home/pi/ipk_app_new
  reboot
"
```

On reboot, the device's `ipk_starter.py` detects `/home/pi/ipk_app_new` and:
1. Renames `ipk_app_main` → `ipk_app_old`
2. Renames `ipk_app_new` → `ipk_app_main`
3. Boots the OSS firmware

**Automated script:** `tools/jailbreak.sh`

### Why This Is the Best Approach

| Approach | Complexity | Universal | Reliable |
|----------|-----------|-----------|----------|
| SSH direct staging | Simple | Yes | Yes |
| Fake cpuinfo mount | Medium | Yes | Fragile |
| LD_PRELOAD hook | Medium | Yes | QEMU can't |
| Cross-compile version.so | Hard | No (per-device) | Yes |
| Patch activity_update.so | Hard | Yes | Fragile |

---

## Post-Jailbreak: Future Updates

Once our firmware is running, future updates use our `update.py` (not the
original `activity_update.so`). Our update.py:
- Has **no serial number check** (no checkVer DRM)
- Accepts both `.py` and `.so` install modules
- Falls back to simple file copy if neither works
- Does **not** require `lib/version.so` in the IPK

So after the first jailbreak install, all future OTA updates work normally
through the device's update UI — no SSH needed.

---

## Module Status

| Module | Status | Notes |
|--------|--------|-------|
| `install.so` | **REPLACED** by `install.py` | 6 functions, 100% parity |
| `version.so` | **REPLACED** by `version.py` | Universal SN detection |
| `activity_update.so` | **REPLACED** by `update.py` | No DRM, accepts .py/.so |
| `version_orig.so` | **SHIPPED** (read-only) | SN extraction fallback |
| `debug.so` | **REMOVED** | Not imported by any code |
| `aesutils.so` | **REMOVED** | DRM bypassed, zero imports |
| `games.so` | **REMOVED** | Entertainment only, zero imports |

**Final .so count in IPK: 1** (version_orig.so, read-only data extraction)
