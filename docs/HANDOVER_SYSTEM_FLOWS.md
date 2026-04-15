# System Flows — Handover Document

## Project Status

We are creating a 100% Open Source version of the iCopy-X closed-source device.

### Completed Phases
- [done] Create extensive functional + UI testing for the original firmware
- [done] Create a new open-source UI layer that works with the original firmware
- [done] Test the new UI layer works 100% with the old firmware, via QEMU
- [done] Build a new IPK that we can install on a REAL device
- [done] Replace ALL closed-source RFID middleware .so modules (scan, read, write, sniff, erase, simulate, dump files)
- [done] Replace ALL closed-source UI-flow .so modules (volume, backlight, time settings, LUA scripts, PC-mode, about)
- [done] **402/402 test scenarios passing** across ALL 14 functional flows

### Current Phase: System .so Module Elimination

**Goal: 100% open source. Zero closed-source .so binaries in the final IPK.**

We have eliminated 53 of 64 original .so modules. The remaining 11 are system-level
modules that are NOT tested by functional flow tests — they are infrastructure that
the application depends on to boot, run, and self-update.

---

## Remaining .so Modules (11 total)

### Priority 1: Core Runtime (must work for app to boot)

| # | Module | Size | What It Does | Difficulty |
|---|--------|------|-------------|------------|
| 1 | `application.so` | 60KB | App lifecycle bootstrap — sets up Python paths, imports main modules | Easy |
| 2 | `main.so` | 58KB | Entry point — called by app.py, delegates to application.so | Easy |
| 3 | `rftask.so` | 160KB | RF task manager — spawns/manages PM3 subprocess (RemoteTaskManager) | Medium |

### Priority 2: Utility Libraries (used by middleware)

| # | Module | Size | What It Does | Difficulty |
|---|--------|------|-------------|------------|
| 4 | `bytestr.so` | 34KB | `bytesToHexString()`, `to_bytes()`, `to_str()` — byte/string conversion | Trivial |
| 5 | `audio_copy.so` | 45KB | `playReadyForCopy()` — plays a sound during AutoCopy | Trivial |

### Priority 3: Firmware Update (needed for self-update mechanism)

| # | Module | Size | What It Does | Difficulty |
|---|--------|------|-------------|------------|
| 6 | `ymodem.so` | 287KB | YMODEM serial protocol — used for STM32/GD32 firmware flashing | Medium |
| 7 | `install.so` *** | 86KB | Genuine ARM installer — extracts and installs IPK packages | Hard |
| 8 | `version_orig.so` *** | 83KB | SN-locked version info — contains device serial number | Special |

### Priority 4: Can Be Removed Entirely

| # | Module | Size | What It Does | Why Remove |
|---|--------|------|-------------|-----------|
| 9 | `debug.so` | 39KB | `ViewMsgASCII()`, `ViewMsgHEX()` — debug print helpers | Not imported by any code |
| 10 | `aesutils.so` ** | 61KB | AES-128 crypto for DRM license checks | DRM bypassed — zero imports |
| 11 | `games.so` ** | 112KB | DOOM + GreedySnake easter egg | Entertainment only — zero imports |

**Legend:**
- `**` = Can be removed entirely (no code imports them)
- `***` = Needed for FIRST install onto device, then replaceable by our own universal installer

---

## Implementation Order

```
Phase A: Core Runtime (app must boot)
  1. application.so  → application.py   (app lifecycle bootstrap)
  2. main.so          → main.py          (entry point)
  3. rftask.so        → rftask.py        (PM3 subprocess manager)

Phase B: Trivial Utilities
  4. bytestr.so       → bytestr.py       (byte/string helpers)
  5. audio_copy.so    → audio_copy.py    (sound effect stub)

Phase C: Firmware Update System
  6. ymodem.so        → ymodem.py        (YMODEM serial protocol)
  7. install.so ***   → install.py       (IPK installer — trojan horse strategy)
  8. version_orig.so  → (already have version.py, remove .so fallback)

Phase D: Cleanup (remove, don't replace)
  9. debug.so         → REMOVE (not imported)
  10. aesutils.so     → REMOVE (DRM bypassed)
  11. games.so        → REMOVE (entertainment only)
```

---

## Critical Context: install.so and the Serial Number Lock

The original firmware's IPK installation mechanism has a serial number lock:
1. Each `version.so` inside an IPK contains a hardcoded `SERIAL_NUMBER`
2. During install, `install.so` compares the IPK's SN against the device's CPU ID
3. If they don't match, installation is rejected

**Our strategy for the FIRST install:**
- Our IPK ships with the original `install.so` (ARM binary) — this is the genuine installer
- We also ship `version_orig.so` — which contains the device's real SN
- `install.so` will verify the SN matches and proceed with installation
- Once our firmware is running, we own the system — we can replace `install.so` with our own universal Python installer that has no SN checks

**Trojan horse approach (alternative):**
- Since we have root access on the device, we could temporarily override the CPU ID check:
  - The device reads CPU serial from `/proc/cpuinfo` (field: `Serial`)
  - We could create a wrapper script that mounts a fake cpuinfo before install runs
  - Or patch the check in install.so at runtime via LD_PRELOAD
  - Or simply use `version_universal.py` which returns `SERIAL_NUMBER = "UNIVERSAL"` and modify install.so's check to accept that

**Post-first-install:**
- Replace `install.so` with a Python `install.py` that:
  1. Extracts the IPK (ZIP)
  2. Validates package structure (app.py, lib/, main/ present)
  3. Copies files to `/home/pi/ipk_app_new/`
  4. Sets permissions (`chmod -R 777`)
  5. The device's `ipk_starter.py` handles the swap on next boot
  6. No SN check — universal installer

---

## Ground Truth Resources

### Decompiled modules:
- `decompiled/activity_main_ghidra_raw.txt` — 1.9MB
- `decompiled/hmi_driver_ghidra_raw.txt` — 638KB
- `decompiled/gadget_linux_ghidra_raw.txt` — 10K+ lines
- `decompiled/audio_ghidra_raw.txt` — 837KB
- `decompiled/settings_ghidra_raw.txt` — 198KB

### Module audit:
- `docs/V1090_MODULE_AUDIT.txt` — Complete method signatures for ALL 64 .so modules
- `docs/V1090_SO_STRINGS_RAW.txt` — Extracted string constants from ALL .so modules

### Real device traces:
- `docs/Real_Hardware_Intel/trace_misc_flows_20260330.txt`
- `docs/Real_Hardware_Intel/trace_misc_flows_session2_20260330.txt`

### Archive prototype (working reference, NOT to be trusted for UI):
- `/home/qx/archive/lib_transliterated/` — working transliterations of many modules
- `/home/qx/archive/ui/activities/update.py` — working IPK installer
- `/home/qx/archive/worktrees/agent-af81b37b/tools/build_ipk.py` — IPK builder

### Test infrastructure:
- `tests/flows/` — 402 scenarios across 14 flows (ALL PASSING on current)
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`)

---

## Approach for Each System Module

Unlike functional flows (which have extensive test scenarios), system modules are
verified differently:

1. **Decompile analysis** — Read the Ghidra output, understand every function
2. **String extraction** — Map all strings from V1090_SO_STRINGS_RAW.txt
3. **QEMU tracing** — Run the original system under QEMU with strace/tracing
4. **Archive reference** — Check if /home/qx/archive/ has a working transliteration
5. **Implement** — Write the Python replacement
6. **QEMU boot test** — Boot with TEST_TARGET=current, verify app starts
7. **Flow regression** — Run ALL 402 test scenarios to verify no regressions
8. **Real device test** — Install IPK on real device, verify functionality

---

## Laws (same as functional flows, plus system-specific additions)

1. **Tests are immutable.** NEVER edit test files.
2. **The `.so` IS the logic.** Decompile, trace, understand — never guess.
3. **DEBUG and TRACE** — we have a fully emulated original system.
4. **Never guess.** Every function, every string must trace to ground truth.
5. **Never put logic in the UI.**
6. **NEVER flash PM3 bootrom.** No JTAG = bricked device.
7. **Request the REAL DEVICE if required.**
8. **ALL .so modules must be replaced** — the goal is ZERO .so in final IPK.
9. **Remote QEMU server** for >3 tests.
10. **Never use blind sleeps.**

### System-specific additions:
11. **Boot stability is paramount.** If application.so/main.so/rftask.so replacement
    breaks the boot, the device is bricked until USB recovery. Test THOROUGHLY under
    QEMU before touching real hardware.
12. **rftask.so manages the PM3 subprocess.** This is the bridge between our Python
    code and the Proxmark3 hardware. Getting this wrong means no RFID functionality.
    Trace the original's TCP socket protocol exhaustively before reimplementing.
13. **install.so is a trust boundary.** The first install onto a device uses the
    genuine install.so. Only AFTER our firmware is running can we replace it.
    Plan the trojan horse carefully.
14. **Preserve backward compatibility.** Our install.py must still accept IPKs
    built by the original toolchain, in case we need to roll back.

---

## Environment

- Branch: `feat/ui-integrating`
- Remote QEMU: `qx@178.62.84.144` (password: `proxmark`)
- Build tool: `python3 tools/build_ipk.py --sn UNIVERSAL --output icopy-x-oss.ipk`
- Current IPK: `icopy-x-oss-current.ipk` (88 files, 1.7MB, 58 Python + 11 .so + 18 JSON + 1 binary)
- Target: 88 files → 77+ Python + 0 .so (except pm3/proxmark3 binary)

---

## Test Status (402/402 passing)

| Flow | Scenarios | Status |
|------|-----------|--------|
| Scan Tag | 45/45 | DONE |
| Read Tag | 99/99 | DONE |
| Write Tag | 61/61 | DONE |
| Auto Copy | 51/51 | DONE |
| Simulate | 28/28 | DONE |
| Sniff TRF | 16/16 | DONE |
| Erase Tag | 10/10 | DONE |
| Dump Files | 35/35 | DONE |
| LUA Script | 11/11 | DONE |
| Time Settings | 13/13 | DONE |
| Volume | 7/7 | DONE |
| Backlight | 7/7 | DONE |
| PC-Mode | 8/8 | DONE |
| About | 11/11 | DONE |
| **TOTAL** | **402/402** | **ALL PASS** |

---

## New OSS Modules Created During Functional Flows Phase

| Module | Purpose |
|--------|---------|
| `config.py` | conf.ini persistence (configparser wrapper) |
| `settings.py` | Typed getters/setters for backlight/volume/sleep |
| `audio.py` | Audio playback stubs (30+ sound effect functions) |
| `gadget_linux.py` | USB gadget kernel module control |
| `version.py` | Device info (getTYP/getHW/getHMI/getOS/getPM/getSN) |
| `update.py` | IPK firmware update pipeline (search/checkPkg/unpkg/install) |

These join the 35 middleware modules already created during RFID flow work:
executor, scan, read, write, sniff, erase, hf14ainfo, hf14aread, hf15read, hf15write,
hffelica, hficlass, hfmfkeys, hfmfread, hfmfuinfo, hfmfuread, hfmfuwrite, hfmfwrite,
hfsearch, iclassread, iclasswrite, legicread, lfem4x05, lfread, lfsearch, lft55xx,
lfverify, lfwrite, mifare, template, tagtypes, appfiles, commons, container, felicaread
