# UI Audit Handover — 2026-04-10

## Commits This Session

1. `d069154` — ProgressBar two-line status, countdown timer, card_info_with_progress renderer
2. `78ab15e` — Main menu icons, battery polling, backlight/volume real-time preview
3. `8828af8` — Diagnosis/Volume icon swap, sniff.json gaps, about.json page 2

## Bugs Fixed

### 1. Main Menu Icons (Page 3/3)
**Status: FIXED**
- About → `"list"` icon (document with lines)
- Erase Tag → `"erase"` icon (E letter in box)
- Time Settings → `"time"` icon (T letter in box)
- LUA Script → `"script"` icon (S letter in box)
- Diagnosis → `"diagnosis"` icon (wrench) — was `"9"` (speaker, wrong)
- Volume → `"9"` icon (speaker) — was `"10"` (document, wrong)
- Ground truth: main_page_2_3_*.png, main_page_3_3_*.png

### 2. Battery Indicator
**Status: FIXED**
- New `src/lib/batteryui.py` — replaces batteryui.so
- Polls hmi_driver every 10s, pushes to BatteryBar widgets
- Register/unregister wired in actbase.py onResume/onPause
- Start called in application.py on boot
- Charger events (CHARGING!/DISCHARGIN!) trigger immediate update
- Fill colors: green >50%, yellow 20-50%, red <20%

### 3. Backlight Real-Time Preview
**Status: FIXED**
- `on_selection_change` callback wired to `hmi_driver.setbaklight()`
- Preview fires on each UP/DOWN navigation
- `_cancel()` fixed: reverts hardware only, does NOT persist to settings
- `_save()` already correct: persists + applies

### 4. Volume Real-Time Preview
**Status: FIXED**
- `on_selection_change` callback wired to `audio.setVolume()` + `audio.playVolumeExam()`
- Audio preview plays on each UP/DOWN navigation
- Save/exit behavior unchanged (correct per ground truth)

### 5. ProgressBar Two-Line Status
**Status: FIXED**
- `setTimer(text)` added for timer line above message line
- Timer renders at (x+width/2, y-18), message at (x+width/2, y-2)
- `hfmfkeys.py`: countdown timer thread fires callProgress every second
- `onReading()` in both ReadActivity and AutoCopyActivity formats MM'SS''

### 6. card_info_with_progress Renderer
**Status: FIXED**
- Added to both `_renderer.py` and `json_renderer.py` dispatch tables
- Delegates to `_render_progress` with mapped keys

## JSON Schema Gaps (Audit Findings)

These are documentation-level gaps in the JSON screen files. The **activity Python code is generally correct** — it renders properly regardless of JSON. These should be fixed for spec completeness but are LOW priority for manual testing.

### Scan Tag (scan_tag.json)
- JSON template variables (`{right_button}`) not fully resolved in found state
- Dead `_setupIdleState` code exists but is unreachable from normal launch

### Erase Tag (erase_tag.json)
- JSON shows button bar for type list but real device hides it
- Missing "Unknown error" state (only has "failed")

### Write Tag (write_tag.json)
- Post-completion button swap (Verify/Rewrite) not modeled in JSON
- Tag info persistence during writing not modeled (activity handles correctly)
- Buttons shown as "disabled" in JSON but actually "hidden" on real device

### AutoCopy (autocopy.json)
- `place_card` state implies inline toast but implementation pushes WarningWriteActivity
- `scan_wrong_type` not distinguished from `scan_not_found`

### Simulation (simulation.json)
- Missing M1 key definition in list_view state
- Otherwise correct

### Sniff (sniff.json) — FIXED
- Instruction state added
- PM3 commands corrected
- Result M1 label corrected

### Diagnosis (diagnosis.json)
- Factory diagnosis sub-activities (ScreenTest, ButtonTest, etc.) defined in JSON but never wired in DiagnosisActivity
- JSON color spec for pass/fail doesn't match activity rendering

### PC Mode (pc_mode.json)
- OK — no gaps found

### Time Settings (time_settings.json)
- OK — minor: toast icon naming ("right" vs "check")

### LUA Script (lua_script.json)
- Console is a pushed activity vs JSON's inline console view

### Dump Files (dump_files.json)
- Delete confirm overlay shows original buttons underneath
- Missing UP/DOWN key definitions in type_list

### About (about.json) — FIXED
- Page 2 (update instructions) added

### Warning M1 (warning_m1.json)
- JSON has 4 pages but activity has 2
- Button labels between JSON and activity are inverted

### Warning Write (warning_write.json)
- M1="Watch" on real device vs "Cancel" in reimplementation (intentional — wearable feature removed)

## Testing Recommendations

For manual testing, focus on these areas IN ORDER:

1. **Main Menu Navigation** — all 3 pages, all icons visible, correct names
2. **Battery** — title bar shows battery, fill changes over time
3. **Backlight** — navigate levels, see brightness change, OK saves, PWR reverts
4. **Volume** — navigate levels, hear preview sound, OK saves, PWR exits without save
5. **Read Tag** — scan → read → progress bar with timer text → success/fail
6. **AutoCopy** — full scan → read → swap card → write pipeline
7. **Write Tag** — write progress, verify, button swap after completion
8. **Erase Tag** — type selection, scanning, erase progress, success/fail toasts
9. **Simulation** — list pagination, field editing, start/stop simulation
10. **Sniff** — type selection, instruction pages, sniffing, result display
11. **Diagnosis** — run all 5 tests, view results
12. **Settings** — Time Settings, About (both pages), LUA Scripts

## Files Modified This Session

| File | Changes |
|------|---------|
| src/lib/widget.py | ProgressBar: setTimer(), _tag_timer, two-line message |
| src/lib/_renderer.py | card_info_with_progress dispatch + function |
| src/lib/json_renderer.py | card_info_with_progress dispatch + method |
| src/lib/activity_read.py | Timer formatting in onReading() |
| src/lib/activity_main.py | Timer in AutoCopy onReading(), backlight/volume preview |
| src/middleware/hfmfkeys.py | Countdown timer thread in keys() |
| src/lib/actmain.py | Menu icons for all 14 items, icon swaps |
| src/lib/batteryui.py | NEW — battery polling module |
| src/lib/actbase.py | Battery register/unregister, title bar optimizations |
| src/lib/application.py | batteryui.start() on boot |
| src/lib/hmi_driver.py | notifyCharging() on serial events |
| src/screens/sniff.json | Instruction state, PM3 fixes, label fixes |
| src/screens/about.json | Two-page state machine |
