# Tools Reference

All tools for the iCopy-X Open reimplementation project.
Last updated: 2026-03-24

## Environment Setup

### `tools/setup_qemu_env.sh`
Self-healing QEMU environment setup. Run after any reboot/reset.
- Decompresses SD card image from RAR if needed
- Mounts 4 partitions (boot, root1, root2, data) via separate loop devices
- Creates /mnt/upan symlink
- Sets up QEMU shims (resources.py, Crypto/)
- Starts Xvfb if not running
- Creates image overlay directory

**Usage:** `bash tools/setup_qemu_env.sh`

**Prerequisites:** sudo password `proxmark`, QEMU binary at `~/.local/bin/qemu-arm-static`

## QEMU Launchers

### `tools/minimal_launch_090.py`
**PRIMARY v1.0.90 launcher.** Minimal patches, closest to real device behavior.

**Architecture:**
1. Import REAL pygame BEFORE `lib/` goes on sys.path (lib/audio.so shadows pygame internals)
2. Mock only: serial, subprocess, psutil (with subscript support), pygame.mixer
3. Resources shim from `tools/qemu_shims/` — `get_fws()` returns `[]` not font metrics
4. Safe `os.listdir` fallback for missing directories
5. Image overlay for missing `/res/img/` PNGs
6. PM3 scenario mock via `PM3_SCENARIO_FILE` env var (3s delay per command)
7. Key injection via `/tmp/icopy_keys_090.txt`
8. HMI key callback binding at 3s after Tk init
9. `TOAST_CANCEL` command for dismissing toast overlays
10. Executor helper mocking: `hasKeyword()`, `getContentFromRegexG/A()`, `getPrintContent()` — Python-level overrides that Cython .so modules access via attribute lookup
11. `scan.lf_wav_filter()` override — returns True when T55XX fixture active (no real antenna data under QEMU)
12. `data save f` handler — creates actual `.pm3` file with dummy LF trace data
13. `startPM3Plat` mocking — catches platform-level PM3 commands

**Key injection commands:**
| Command | Effect |
|---------|--------|
| `UP`, `DOWN`, `LEFT`, `RIGHT`, `OK`, `M1`, `M2` | Button press via serial buffer |
| `_PWR_CAN` | Power/cancel key (works for menu nav, NOT toast dismiss) |
| `GOTO:<N>` | Push activity at menu position N (0-13) |
| `FINISH` | Pop current activity (PWR back) |
| `TOAST_CANCEL` | Delete toast mask rectangles from canvas |

**CRITICAL: Toast Dismiss Under QEMU**

On real hardware, PWR short press dismisses toasts. Under QEMU, PWR goes through
`keymap.key.onKey('PWR')` → `BaseActivity.callKeyEvent('PWR')` at Cython C level,
but the toast's internal key handler doesn't fire because Cython bypasses Python dispatch.

The `TOAST_CANCEL` command works by directly deleting tkinter canvas items:
- Large rectangles with stipple/dark fill (the toast mask overlay)
- Text items containing toast messages ("Tag Found", "No tag found", etc.)
This reveals the clean screen underneath (e.g., card details with Rescan/Simulate buttons).

**Boot sequence:**
1. ~2s: Tk window created
2. ~3s: HMI key callbacks bound
3. ~6s: Processing toast appears (check_all_activity runs)
4. ~8s: Processing toast self-dismisses (check_fw_update completes — requires get_fws fix)
5. ~8s+: Menu interactive, GOTO works, keys work

**resources.get_fws() fix:**
The real `resources.so` returns `[]` for `get_fws('stm32')` etc. (no firmware files).
Our shim originally returned `(8, 17, 14, 28)` (font metrics) which crashed
`update.check_stm32`'s lambda filter: `'stm32' in 8` → TypeError.
This crash left the Processing toast stuck forever, blocking all key dispatch.
Fix: return `[]` to match real behavior. Confirmed via Ghidra decompilation of update.so.

**Usage:**
```bash
SITE1="/mnt/sdcard/root1/home/pi/.local/lib/python3.8/site-packages"
SITE2="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages"

QEMU_LD_PREFIX=/mnt/sdcard/root2/root \
QEMU_SET_ENV="LD_LIBRARY_PATH=<root2+root1 lib paths>" \
DISPLAY=:99 PYTHONPATH="$SITE1:$SITE2" PYTHONUNBUFFERED=1 \
PM3_SCENARIO_FILE="/path/to/mock.py" \
timeout 80 qemu-arm-static python3.8 -u tools/minimal_launch_090.py
```

### `tools/launch_090_arm.py`
Older full-featured launcher. More patches, canvas logging, auto-capture hooks.
Use `minimal_launch_090.py` instead — it's simpler and produces better captures.

### `tools/patched_launch.py`
v1.0.3 launcher. Proven working with 446 screenshots across 36 scenarios.

## Capture Scripts

### `tools/run_scan_scenarios.sh`
**PRIMARY scan capture batch.** Runs all 44 scan tag types, one QEMU boot each.
- Polls for toast dismiss + HMI binding before GOTO
- Captures 20s of scanning progress at 0.1s intervals
- Sends TOAST_CANCEL to dismiss result toast
- Captures 5s of clean result screen
- Deduplicates by md5, validates minimum unique count

**Output:** `docs/screenshots/v1090_scenarios/scan_<type>/state_*.png`

### `tools/capture_090_scenario_v2.sh`
Generic per-scenario capture. Boots fresh QEMU, loads PM3 fixture, injects keys.

### `tools/capture_090_each.sh`
Captures each of 14 activities via GOTO in separate QEMU sessions.

## QEMU Shims

### `tools/qemu_shims/resources.py`
Replacement for v1.0.90 `resources.so`. Provides:
- `StringEN` class with all string tables (button, title, toastmsg, tipsmsg, procbarmsg, itemmsg)
- `get_str(keys)` — string lookup (tuple for list input)
- `get_font(size)` — font name string
- `get_fws(key)` — **MUST return `[]`** (firmware file specs, NOT font metrics)
- `get_xy(key)`, `get_int(key)`, `get_par(key, idx, default)` — resource lookups
- `get_text_size(key)`, `get_font_type(key, default)` — text metrics
- `DrawParEN`, `DrawParZH` — drawing parameter classes
- `force_check_str_res()`, `is_keys_same(keys)`, `getLanguage()`, `setLanguage(lang)`

Auto-generated from real .so data extracted under QEMU.

### `tools/qemu_shims/Crypto/`
Replacement for pycryptodome. Provides AES MODE_ECB/CBC/CFB stubs.

### `tools/qemu_img_overlay/`
Auto-generated placeholder PNGs for missing device images under QEMU.

### `tools/probe_wav_filter.py`
QEMU probe for `scan.lf_wav_filter()`. Tests the real function with different file contents
to determine the amplitude threshold. Creates `.pm3` files with test data and calls the real
scan.so function. **Result:** threshold = 90 (amplitude >= 90 → True).

### `tools/trace_4_failed.sh`
Quick trace script for 4 previously-failed scan scenarios (ntag215, ultralight, iclass, t55xx).

## PM3 Mock Data

### `tools/pm3_fixtures.py`
**133 PM3 response fixtures** covering all tag types and middleware decision branches.

| Category | Count | Coverage |
|----------|-------|----------|
| Scan | 44 | All 48 tag types + edge cases (BCC0, Gen2, POSSIBLE 7B) |
| Read | 35 | MF Classic (all keys/partial/darkside/nested/tag-lost/4K), UL, NTAG, iCLASS, 18 LF types, ISO15693, LEGIC |
| Write | 36 | Gen1a (cload/UID), standard (success/fail/partial/verify-fail), UL, iCLASS (incl key calc), 17 LF types, ISO15693 |
| Erase | 5 | MF1 (success/no-keys/gen1a), T5577 (success/fail) |
| Diagnosis | 3 | HW tune (both OK / LF fail / HF fail) |
| Sniff | 3 | 14A trace, T5577 keys, empty |
| AutoCopy | 7 | Happy/darkside/gen1a/darkside-fail/write-fail/no-tag/verify-fail |

Derived from ground truth regex patterns extracted from .so binaries (V1090_PM3_PATTERN_MAP.md).

## Test Infrastructure

### `tools/test_ipk_full_tree.py`
Full middleware tree test. PM3 mock TCP server. 101+ checks.
Supports both IPK (`<path>`) and source tree (`--source`) mode.

### `tools/build_ipk.py`
IPK package builder. Sources transliterated modules from `lib_transliterated/`.

### `tools/test_ipk_release.py`
8-gate release test suite. 33 checks.

## Ghidra

### `tools/ghidra_decompile.py`
Headless Ghidra post-script for decompiling .so functions.

**Usage:**
```bash
GHIDRA=~/.local/lib/ghidra_12.0.4_PUBLIC
$GHIDRA/support/analyzeHeadless /tmp/proj proj \
    -import /path/to/file.so \
    -processor ARM:LE:32:v7 \
    -postScript /tmp/ghidra_script.py
```

### Decompilation outputs
- `decompiled/scan_ghidra_raw.txt` — scan.so full decompilation (32K lines, 95 functions)
- `decompiled/scan_xref_analysis.txt` — scan.so symbol cross-references
- `decompiled/scan_resolved_t55xx.txt` — scan.so T55XX functions with resolved symbols
- `decompiled/scan_t55xx_analysis.txt` — Human-readable T55XX flow analysis
- `decompiled/actbase_ghidra_raw.txt` — actbase.so decompilation
- `decompiled/actmain_ghidra_raw.txt` — actmain.so decompilation
- `decompiled/actstack_ghidra_raw.txt` — actstack.so decompilation
- `decompiled/executor_ghidra_raw.txt` — executor.so decompilation
- `decompiled/hmi_driver_ghidra_raw.txt` — hmi_driver.so decompilation
- `decompiled/lfverify_ghidra_raw.txt` — lfverify.so decompilation (11.6K lines)

## Reference Documents

| File | Content |
|------|---------|
| `docs/V1090_PM3_PATTERN_MAP.md` | Every regex/keyword from every .so — ground truth |
| `docs/V1090_FIXTURE_REQUIREMENTS.md` | Fixture-to-branch mapping (133 fixtures → 256 paths) |
| `docs/V1090_VERIFIED_STRINGS.md` | Complete StringEN table from real .so |
| `docs/V1090_SO_STRINGS_RAW.txt` | Raw string extraction from all .so files |
| `docs/V1090_MODULE_AUDIT.txt` | All module APIs (functions, classes, constants) |
| `docs/V1090_UI_TESTING_NOTES.md` | QEMU capture notes and timing |
| `docs/UI_MAP_EXHAUSTIVE.md` | Complete UI state map (29 activities, all states/keys/strings) |
| `docs/V1090_SCAN_COMMAND_TRACES.md` | Real PM3 command sequences traced from .so under QEMU |
| `docs/V1090_LF_WAV_FILTER_RECONSTRUCTION.md` | Complete lf_wav_filter() reconstruction with Ghidra + QEMU probing |
| `docs/V1090_LFVERIFY_RECONSTRUCTION.md` | lfverify.so reconstruction — 7 critical transliteration bugs found |
| `docs/RE_CHRONICLE.md` | Full reverse engineering history (22 sections) |

## Key Paths

| Path | Purpose |
|------|---------|
| `/home/qx/02150004-1_0_90.img` | SD card image (15.8GB) |
| `/home/qx/icpyximg.rar` | Compressed SD card image |
| `/mnt/sdcard/root2/root/home/pi/ipk_app_main/` | v1.0.90 app (mounted read-only) |
| `/mnt/sdcard/root1/` | Base rootfs (pygame 2.0.1, system libs) |
| `/home/qx/icopy-x-reimpl/orig_so/` | Backup of all 62 .so modules |
| `/home/qx/.local/bin/qemu-arm-static` | QEMU ARM user-mode binary (9MB) |
| `/home/qx/.local/lib/ghidra_12.0.4_PUBLIC/` | Ghidra installation |
| `/tmp/icopy_keys_090.txt` | Key injection file (volatile — /tmp) |

## SD Card Image Partition Table

```
Partition  Offset (sectors)  Size    Type    Mount
P1         49152             40M     FAT32   /mnt/sdcard/boot
P2         131072            1.7G    ext4    /mnt/sdcard/root1
P3         4589568           1.5G    ext4    /mnt/sdcard/root2
P4         7802880           11G     ext4    /mnt/sdcard/data (/mnt/upan)
```

Mount with separate loop devices to avoid "overlapping loop device" errors.
