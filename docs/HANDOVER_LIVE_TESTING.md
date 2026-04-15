# Live System Testing — Handover Document

## What This Is

The iCopy-X firmware has been fully reimplemented in open source. The next
phase is **live device testing** — installing the OSS IPK on the real
hardware and verifying every function works with real RFID tags.

This document is the single source of truth for any agent working on
live testing. Read it completely before doing anything.

---

## Project Status

### Completed
- 63 of 64 closed-source `.so` modules eliminated
- 402/402 QEMU test scenarios passing across 14 flows
- Universal DRM bypass compiled and verified under QEMU
- Standalone 36MB IPK built (256 files: 66 Python, 18 JSON, 166 resources, 3 .so, 2 PM3 binaries)
- Jailbreak documented (`docs/HOWTO-JAILBREAK.md`)

### Current Phase: Live Device Testing
**Goal:** Install the OSS IPK on a real iCopy-X device and verify all
functions work with real RFID hardware.

### What Remains After Testing
- Fix any regressions found during live testing
- Final IPK release

---

## The IPK

**Location:** Build with `python3 tools/build_ipk.py -o icopy-x-oss.ipk`

**Contents (256 files, 36MB compressed):**

| Category | Count | Description |
|----------|-------|-------------|
| Python (.py) | 66 | UI + middleware + main modules |
| JSON screens | 18 | Screen definitions |
| Resources | 166 | Audio (96 wav), fonts (3), images (66), font_install.txt |
| PM3 binaries | 2 | proxmark3 client + lua.zip |
| Data | 1 | conf.ini (default settings) |
| .so files | 3 | version.so (universal DRM bypass, 14KB, **ours**), version_orig.so (SN extraction, read-only), install.so (genuine file copier for first install) |

**No closed-source module is executed at runtime.** The 3 .so files serve bootstrap/data roles only.

### Build Commands
```bash
# Standard build (includes DRM bypass for USB install)
python3 tools/build_ipk.py -o icopy-x-oss.ipk

# Without DRM bypass binaries (OTA-only, post-jailbreak)
python3 tools/build_ipk.py --no-trojan -o icopy-x-oss-ota.ipk
```

---

## Device Access

The iCopy-X has **no LAN or WiFi**. Two interfaces exist:

| Interface | How | Used For |
|-----------|-----|----------|
| **USB mass storage** | USB cable to PC, device exposes `/dev/mmcblk0p4` as removable drive | IPK delivery, trace file retrieval |
| **USB serial** (reverse SSH tunnel) | Port 2222, `root:fa` | Instrumentation, trace deployment, diagnostics |

```bash
# SSH access (when tunnel is active)
sshpass -p 'fa' ssh -p 2222 root@localhost
```

**The user must establish the tunnel before any SSH operations.** Always verify connectivity first.

---

## Installation Procedure

### First Install (Jailbreak — Device Running Original Firmware)

1. Build the IPK: `python3 tools/build_ipk.py -o icopy-x-oss.ipk`
2. Copy `icopy-x-oss.ipk` to a FAT32 USB drive (root directory)
3. Insert USB drive into device
4. On device: **Main Menu → About → DOWN → OK** ("Update") **→ M2** ("Start")
5. Device reboots automatically
6. OSS firmware is now running

See `docs/HOWTO-JAILBREAK.md` for full details and DRM bypass explanation.

### Subsequent Updates (Device Running OSS Firmware)

Same USB procedure — our `update.py` has no DRM check. Any valid IPK is accepted.

---

## Live Tracing

**Full protocol:** `docs/HOW_TO_RUN_LIVE_TRACES.md`
**Slash command:** `/trace-device [app|fb] [flow-name]`

Two capture modes (NEVER run simultaneously):

| Mode | What It Captures | How |
|------|-----------------|-----|
| `app` | Activity transitions, PM3 commands, scan cache, stack state | `sitecustomize.py` patches module-level functions |
| `fb` | Framebuffer screenshots (240x240 RGB565) | `cp /dev/fb1` at 500ms intervals |

### Instrumentation Rules

**SAFE — module-level function patches:**
- `actstack.start_activity`, `actstack.finish_activity`
- `executor.startPM3Task`
- `scan.setScanCache`

**CRASHES THE APP — class method patches:**
- Any `ClassName.method = ...` on a `.so` class — Cython vtable corruption
- Heavy instrumentation + framebuffer capture simultaneously

**ALWAYS clean up** `sitecustomize.py` after capturing — leaving it causes crashes.

---

## Laws

These are absolute. No exceptions. No "just this once."

### Ground Truth
1. **Only ground-truth resources.** Never invent, guess, or "try". Every line of code must cite a decompiled `.so`, real trace, or real screenshot.
2. **The `.so` IS the logic.** Decompile, trace, understand — never guess.
3. **Captures are calibration anchors, NOT the complete map.** All branches for all cards come from binary analysis. Captures augment, not replace.
4. **Never iterate fixture responses without ground truth.** If no trace exists, STOP and request a real device trace.

### Testing
5. **Tests are IMMUTABLE.** NEVER modify test files without explicit user permission.
6. **ALL tests must RUN TO COMPLETION and ALL must PASS.** No timeouts, no crashes, no skips.
7. **Fixtures are DATA ONLY.** No decisions, no branching, no function calls. `.so` modules ARE the logic.
8. **Never blind-sleep.** Poll output every 60s or run foreground. Catch crashes in seconds, not minutes.
9. **Always test IPK under QEMU before declaring ready.** Never trust file-presence checks alone.
10. **>3 tests = remote QEMU server** (`qx@178.62.84.144`, pw `proxmark`). rsync before+after. Local for 1-3 only.
11. **ALWAYS `rm -rf` local `_results/current/` before rsyncing** test results back. rsync doesn't delete stale files.

### Hardware Safety
12. **NEVER flash PM3 bootrom.** No JTAG = bricked device. Zero exceptions.
13. **NEVER access `~/.ssh` on any device.**
14. **NEVER run framebuffer capture + Python instrumentation simultaneously.**
15. **ALWAYS clean up `sitecustomize.py` after trace capture.**

### Process
16. **Read docs first.** Before touching anything, read the relevant handover doc, the flow README, and the test fixtures.
17. **Never block the user.** If stuck, present findings and ASK.
18. **Follow instructions exactly.** The user's instructions override any default behavior.
19. **Prepare before touching real hardware.** Verify under QEMU first, then move to the device.

---

## QEMU Environment

### Local QEMU
- SD card image: `/home/qx/02150004-1_0_90.img`
- Setup: `bash tools/setup_qemu_env.sh`
- Rootfs: `/mnt/sdcard/root2/root/`
- App dir: `/mnt/sdcard/root2/root/home/pi/ipk_app_main/`
- Backup: `/mnt/sdcard/root2/root/home/pi/ipk_app_main.bak2/` (pristine original firmware, 62 .so)
- QEMU binary: `/home/qx/.local/bin/qemu-arm-static`
- Python 3.8: `/mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8`
- Xvfb display: `:99` (or `TEST_DISPLAY` override)

### Remote QEMU Server
- Host: `qx@178.62.84.144`, password: `proxmark`
- Use for >3 tests. rsync project before and after.
- **ALWAYS** `rm -rf _results/current/` locally before rsyncing back.

### Test Targets
| Target | What Runs | When |
|--------|-----------|------|
| `original` | All original `.so` modules from rootfs | Baseline verification |
| `current` | Python modules from `src/` shadow `.so` | OSS parity testing |
| `original_current_ui` | Python UI + original middleware `.so` | Integration testing |

### Running Tests
```bash
# Single scenario
TEST_TARGET=current bash tests/flows/scan/scenarios/scan_mf1k_4b/test.sh

# All scenarios for a flow
TEST_TARGET=current bash tests/flows/scan/run_all.sh

# Full regression (use remote QEMU for this)
TEST_TARGET=current bash tests/run_all_flows.sh
```

### Boot Process
```bash
source tests/includes/common.sh
boot_qemu "path/to/fixture.py"
wait_for_hmi 40  # polls for "Bound.*key callbacks"
```

---

## Key File Locations

### Source Code
| Path | Content |
|------|---------|
| `src/lib/` | Python UI modules (actbase, activity_main, widget, etc.) |
| `src/middleware/` | Python middleware (scan, read, write, executor, etc.) |
| `src/main/` | Python main-level modules (main, rftask, install) |
| `src/screens/` | JSON screen definitions |
| `src/app.py` | Entry point |

### Build & Tools
| Path | Content |
|------|---------|
| `tools/build_ipk.py` | IPK builder (`--no-trojan` for OTA-only) |
| `tools/universal_version/` | Universal version.so (C source + compiled ARM binary) |
| `tools/setup_qemu_env.sh` | QEMU environment setup |
| `tools/launcher_original.py` | QEMU launcher for original firmware |
| `tools/launcher_current.py` | QEMU launcher for OSS firmware |
| `tools/launcher_install_test.py` | QEMU launcher for IPK install testing |
| `tools/pm3_fixtures.py` | PM3 mock response database |

### Resources (shipped in IPK)
| Path | Content |
|------|---------|
| `res/audio/` | 96 wav files (UI sound effects, EN + CN) |
| `res/font/` | 3 font files (mononoki, monozhwqy CJK) |
| `res/img/` | 66 png images (menu icons, tag type images) |
| `data/conf.ini` | Default settings (backlight=1, volume=1) |
| `device_so/proxmark3` | PM3 client binary (ARM, from RRG upstream) |
| `device_so/lua.zip` | PM3 LUA scripts |

### Documentation
| Path | Content |
|------|---------|
| `docs/HOWTO-JAILBREAK.md` | DRM bypass and USB install procedure |
| `docs/HOW_TO_RUN_LIVE_TRACES.md` | Device instrumentation protocol |
| `docs/DRM-KB.md` | DRM knowledge base (all checks, all fixes) |
| `docs/DRM-Install-Analysis.md` | install.so/version.so analysis |
| `docs/V1090_MODULE_AUDIT.txt` | Complete method signatures for all 64 .so modules |
| `docs/V1090_SO_STRINGS_RAW.txt` | Extracted string constants from all .so modules |

### Test Infrastructure
| Path | Content |
|------|---------|
| `tests/flows/` | 402+ scenarios across 14+ flows |
| `tests/includes/common.sh` | Shared test harness (boot_qemu, send_key, etc.) |
| `tests/flows/_results/` | Test output (screenshots, logs, state dumps) |

### Device Binaries
| Path | Content |
|------|---------|
| `device_so/version.so` | Original device-specific version.so (SN 02150004) |
| `device_so/install.so` | Original install.so (genuine file copier) |
| `device_so/proxmark3` | PM3 client binary |
| `device_so/lua.zip` | PM3 LUA scripts |
| `device_so/version_universal.py` | Runtime version module template |
| `orig_so/` | All original v1.0.90 .so modules (reference) |
| `decompiled/` | Ghidra decompilation output for key .so modules |

---

## DRM Summary

The original firmware has a serial-number lock on firmware updates:

1. `activity_update.so` checkPkg requires `lib/version.so` and `main/install.so` (ARM .so, not .py)
2. `activity_update.so` checkVer loads `version.so` from IPK, compares `SERIAL_NUMBER` against device
3. `ExtensionFileLoader` cannot load `.py` files ("invalid ELF header")

**Our bypass:** `tools/universal_version/version.so` (14KB ARM C extension) reads `sys.modules["version"].SERIAL_NUMBER` at import time, mirroring the running device's SN. Falls back to scanning backup `version_orig.so` binaries if loaded at boot time (no prior module to mirror).

**After first install:** Our `update.py` replaces `activity_update.so`. No checkVer. No DRM. Future updates are universal.

---

## Device Hardware

| Component | Detail |
|-----------|--------|
| SoC | Allwinner H3 (sun8i), NanoPi NEO |
| CPU | ARM Cortex-A7, quad-core |
| Display | 240x240 TFT, `/dev/fb1`, RGB565 |
| Input | 5 buttons: M1, M2, OK, PWR (back/exit), UP/DOWN (rocker) |
| RFID | Proxmark3 (iCopy-X variant, XC3S100E FPGA) |
| USB | Gadget mode: mass storage (`g_mass_storage`), serial (`g_serial`), composite (`g_acm_ms`) |
| Storage | SD card, 4 partitions (boot, root1, root2, data) |
| Python | 3.8.0 (from `/usr/local/python-3.8.0/`) |
| CPU Serial | `02c000814dfb3aeb` (from `/proc/cpuinfo`) |
| Software SN | `02150004` (from `version.SERIAL_NUMBER`) |

---

## Live Testing Checklist

### Phase 1: Install
- [ ] Build IPK: `python3 tools/build_ipk.py -o icopy-x-oss.ipk`
- [ ] Copy to USB drive
- [ ] Install on device via About → Update
- [ ] Verify device boots to main menu
- [ ] Verify About screen shows OS version `2.0.0`

### Phase 2: Basic Functionality
- [ ] Navigate all main menu items (scroll through list)
- [ ] Enter and exit each sub-menu (Scan, Read, Write, etc.)
- [ ] PWR key exits from every screen
- [ ] Backlight settings work
- [ ] Volume settings work

### Phase 3: RFID Operations (requires real tags)
- [ ] Scan: detect a tag (any type)
- [ ] Read: read a tag successfully
- [ ] Write: write to a writable tag
- [ ] AutoCopy: full copy flow
- [ ] Simulate: simulate a read tag
- [ ] Sniff: capture RF traffic
- [ ] Erase: erase a writable tag
- [ ] Dump Files: browse saved dumps

### Phase 4: Edge Cases
- [ ] Scan with no tag present
- [ ] Read wrong tag type
- [ ] Write to read-only tag
- [ ] PC Mode: USB gadget activation
- [ ] LUA Scripts: list and run
- [ ] Time Settings: set date/time

### Regression Tracking
If a function fails, capture a trace:
1. Deploy tracer: `/trace-device app <flow-name>`
2. User performs the failing flow on device
3. Retrieve trace
4. Compare against QEMU test expectations
5. Fix, rebuild IPK, reinstall, retest

---

## Critical Reminders

- **The user operates the device physically.** You cannot remote-control the UI. Tell the user what to do, wait for their report.
- **Every fix must be verified under QEMU before reinstalling on hardware.** Never push untested code to the device.
- **The original firmware backup exists at `/home/pi/ipk_app_main.bak`** on the device and at `/mnt/sdcard/root2/root/home/pi/ipk_app_main.bak2` in QEMU. These are sacred — never overwrite them.
- **PM3 bootrom is NEVER flashed.** No JTAG recovery exists. A bad flash = bricked device.
