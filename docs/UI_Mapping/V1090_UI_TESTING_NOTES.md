# v1.0.90 UI Testing Notes

## Date: 2026-03-24

## Working QEMU Setup

### Boot Command
```bash
SITE1="/mnt/sdcard/root1/home/pi/.local/lib/python3.8/site-packages"
SITE2="/mnt/sdcard/root2/root/home/pi/.local/lib/python3.8/site-packages"

QEMU_LD_PREFIX=/mnt/sdcard/root2/root \
QEMU_SET_ENV="LD_LIBRARY_PATH=/mnt/sdcard/root2/root/usr/local/python-3.8.0/lib:/mnt/sdcard/root2/root/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root2/root/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/usr/lib/arm-linux-gnueabihf:/mnt/sdcard/root1/lib/arm-linux-gnueabihf" \
DISPLAY=:99 PYTHONPATH="$SITE1:$SITE2" PYTHONUNBUFFERED=1 \
PM3_SCENARIO_FILE="/tmp/scenario_090_mock.py" \
timeout 80 /home/qx/.local/bin/qemu-arm-static \
  /mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8 \
  -u /tmp/minimal_090.py
```

### Key Files
- `/tmp/minimal_090.py` — Working minimal v1.0.90 launcher (real pygame, minimal patches)
- `tools/launch_090_arm.py` — Full-featured launcher (more patches, GOTO support, canvas logging)
- `tools/capture_090_scenario_v2.sh` — Scenario capture script (per-scenario QEMU boot)
- `tools/run_all_090_scenarios.sh` — Master scenario batch runner
- `tools/pm3_fixtures.py` — PM3 mock fixtures for all 23 tag types

### Key Injection
- Write to `/tmp/icopy_keys_090.txt` (one command per line)
- Supported: `UP`, `DOWN`, `LEFT`, `RIGHT`, `OK`, `M1`, `M2`, `_PWR_CAN`
- GOTO: `GOTO:<position>` (0-13)
- FINISH: `FINISH` (PWR back)

## Critical Findings

### 1. "Processing..." Toast Blocker
**Root cause:** `check_all_activity()` runs on boot, shows "Processing..." toast, and calls:
- `check_disk_space()` — crashes if psutil mock doesn't support `[]` indexing
- `check_fw_update()` — may crash or hang

**Fix:** psutil mock must support subscript access:
```python
ps.disk_usage = lambda p: type('SD', (), {
    'total': 11e9, 'used': 2e9, 'free': 9e9, 'percent': 18.0,
    '__getitem__': lambda s,k: getattr(s,k) if isinstance(k,str) else [11e9,2e9,9e9,18.0][k]
})()
```

**Status:** Toast self-dismisses when check_disk_space succeeds. HOWEVER, check_fw_update may still block. Need to investigate further.

### 2. Real Pygame Required
**Problem:** v1.0.90 launcher originally mocked ALL of pygame. The mock pygame.font returns stub metrics (len*7), causing widget.so to render text at wrong positions. Scan result screens appear blank.

**Fix:** Import REAL pygame (from root1 site-packages) BEFORE adding `lib/` to sys.path. Only mock `pygame.mixer` (audio).

**Critical:** Must import pygame BEFORE lib/ goes on path. lib/ contains `audio.so` and `images.so` which shadow pygame's internal modules if on path during pygame import.

### 3. Key Callback Binding
**Problem:** `startSerialListener` patched to noop → `starthmi()` never runs → `SerialKeyCode[...]['meth']` is None → keys silently dropped.

**Fix:** Schedule key binding via `root.after(3000, _bind_keys)`:
```python
for ks in hmi_driver.SerialKeyCode:
    hmi_driver.SerialKeyCode[ks]['meth'] = keymap.key.onKey
```

### 4. Image Overlay Required
**Problem:** v1.0.90 `CardWalletActivity.getManifest()` loads `/res/img/list.png` which doesn't exist under QEMU. Crash kills `check_all_activity`, activity list never builds.

**Fix:** Patch `builtins.open` to redirect `/res/img/` requests to auto-generated placeholder PNGs.

### 5. Scan Result Screen Timing
**Problem:** Scan completes in <1s under QEMU (PM3 mock returns instantly). Result screen flashes too fast to capture.

**Partial fix:** Add `time.sleep(3.0)` in PM3 mock to simulate real command timing. This helps with progress bar rendering but result screen still elusive.

**Still investigating:** The scan result may auto-pop the activity. On real device, result stays with "Rescan/Rescan" buttons. Under QEMU, activity may be getting finished by the Processing toast's cleanup code.

## Captured Screenshots

### Location: `docs/screenshots/v1090_scenarios/`
- `backlight/` — 3 states (Low/Middle/High)
- `volume/` — 4 states (Off/Low/Middle/High)
- `about/` — 4 states (page 1)
- `erase_tag/` — 4 states (both items)
- `time_display/` — 11 states (clock ticking)
- `time_edit/` — 17 states (edit mode)
- `lua_script/` — 8 states (list scrolling)
- `diagnosis/` — 5 states (menu + items)
- `pcmode/` — 4 states (prompt)
- `simulation/` — 5 states (list page 1)
- `sniff/` — 3 states (list)
- `scan_*` — Multiple attempts at scan capture

### Location: `docs/screenshots/v1090_verified/`
- `each_activity/` — GOTO-based capture of all 14 activities
- `definitive_v2/` — 96 screenshots via GOTO + key navigation

### Location: `docs/screenshots/original_v1090_qemu/`
- 191 screenshots from earlier session (see RE_CHRONICLE.md section 19)

## Verified Menu Position Map
| Pos | Activity | Title |
|-----|----------|-------|
| 0 | Auto Copy | "Auto Copy" |
| 1 | Dump Files | "Dump Files 1/6" |
| 2 | Scan Tag | "Scan Tag" |
| 3 | Read Tag | (crashes under QEMU) |
| 4 | Sniff TRF | "Sniff TRF 1/1" |
| 5 | Simulation | "Simulation 1/4" |
| 6 | PC-Mode | "PC-Mode" |
| 7 | Diagnosis | "Diagnosis" |
| 8 | Backlight | "Backlight" |
| 9 | Volume | "Volume" |
| 10 | About | "About 1/2" |
| 11 | Erase Tag | "Erase Tag" |
| 12 | Time Settings | "Time Settings" |
| 13 | LUA Script | "LUA Script 1/10" |

## Verified String Table
Complete StringEN extraction from real .so under QEMU: `docs/V1090_VERIFIED_STRINGS.md`

## Next Steps
1. Fix `check_fw_update` to complete successfully (dismisses Processing toast)
2. With toast dismissed, verify key navigation works for entering activities
3. Capture scan result screens (may need longer PM3 delays or specific fixture tuning)
4. Run all 23 scan scenarios + autocopy + settings flows
5. Update UI_MAP_EXHAUSTIVE.md with verified data
