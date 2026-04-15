# MainActivity UI Mapping

**Source module:** `actmain.so` (252KB, 129 functions, 4 Activity classes)
**Decompiled reference:** `decompiled/actmain_ghidra_raw.txt`
**Class:** `MainActivity`

---

## 1. Screen Layout

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Main Page N/M"                     |
|  Font: Consolas 18, white on #788098 |
+--------------------------------------+
|  Content Area (0,40)-(240,200)       |
|  ListView: 5 items/page, ~32px each  |
|  Selection: dark rectangle highlight |
|  Items have icon + text              |
+--------------------------------------+
|  Button Bar: EMPTY (no labels)       |
|  (0,200)-(240,240), 40px             |
|  M1 = "", M2 = ""                    |
+--------------------------------------+
```

**Citation:** Framebuffer captures `read_mf1k_4b/0000.png` and `v1090_captures/090-Home-Dump.png` both show no button labels in the bottom bar. The bar area exists (#222222 background per `actbase.so` SUMMARY.md line 86) but `setLeftButton`/`setRightButton` are NOT called (confirmed by string search in `actmain_ghidra_raw.txt` lines 451-460 -- these strings exist as references but are not invoked in `MainActivity.onCreate`).

---

## 2. Title Format

The title is **"Main Page N/M"** where N is the current page and M is total pages. The page indicator is embedded IN the title string, not a separate widget.

**Citation:** Screenshots `v1090_captures/090-Home-Dump.png` shows "Main Page 1/3" and `v1090_captures/090-Home-Page3.png` shows "Main Page 3/3". The title key in `resources.py` StringEN.title (line 67): `'main_page': 'Main Page'`. The N/M suffix is formatted by the caller using `setTitle()`.

---

## 3. Menu Items (14 total, 3 pages)

### Discovery Mechanism

`check_all_activity()` (actmain_ghidra_raw.txt line 23966) dynamically discovers activity classes:
1. Uses `importlib.import_module()` to load `.so` modules from `lib/` directory
2. Uses `inspect.getmembers()` and `inspect.isclass()` to find Activity subclasses
3. Calls `getManifest()` on each discovered class to get metadata (title, icon, order)
4. Builds sorted activity list

**Citation:** SUMMARY.md lines 337-345 document `check_all_activity` behavior. String references at actmain_ghidra_raw.txt lines 436, 550 confirm `check_all_activity` and `getManifest` strings.

### Complete Item List (verified from real-device screenshots)

| Position | Item Name      | Source Activity Class       | Page |
|----------|----------------|-----------------------------|------|
| 0        | Auto Copy      | AutoCopyActivity            | 1    |
| 1        | Dump Files     | CardWalletActivity          | 1    |
| 2        | Scan Tag       | ScanActivity                | 1    |
| 3        | Read Tag       | ReadActivity                | 1    |
| 4        | Sniff TRF      | SniffActivity               | 1    |
| 5        | Simulation     | SimulationActivity          | 2    |
| 6        | PC-Mode        | PCModeActivity              | 2    |
| 7        | Diagnosis      | DiagnosisActivity           | 2    |
| 8        | Backlight      | BacklightActivity           | 2    |
| 9        | Volume         | VolumeActivity              | 2    |
| 10       | About          | AboutActivity               | 3    |
| 11       | Erase Tag      | WipeTagActivity             | 3    |
| 12       | Time Settings  | TimeSyncActivity            | 3    |
| 13       | LUA Script     | LUAScriptCMDActivity        | 3    |

**Page 1 citation:** `main_page_1_3_1.png` shows items 0-4: "Auto Copy", "Dump Files", "Scan Tag", "Read Tag", "Sniff TRF". Also confirmed by `v1090_captures/090-Home-Dump.png` and `read_mf1k_4b/0000.png`.

**Page 2 citation:** `main_page_2_3_1.png` shows items 5-9: "Simulation", "PC-Mode", "Diagnosis", "Backlight", "Volume". Note: NO "Write Tag" item exists in the menu. Backlight position 8 and Volume position 9 confirmed by test infrastructure: `backlight_common.sh` line 42 (`BACKLIGHT_MENU_POS=8`) and `volume_common.sh` line 49 (`VOLUME_MENU_POS=9`).

**Page 3 citation:** `main_page_3_3_1.png` shows items 10-13: "About", "Erase Tag", "Time Settings", "LUA Script". Note: Page 3 shows only 4 items (partially filled page). Also confirmed by `v1090_captures/090-Home-Page3.png`.

**Items per page:** 5 items/page. 14 items / 5 = 3 pages (5+5+4).

**Citation:** All three pages verified from `main_page_1_3_1.png`, `main_page_2_3_1.png`, `main_page_3_3_1.png` real-device screenshots.

### Title Strings (from resources.py StringEN.title)

| Key             | Value           | Line |
|-----------------|-----------------|------|
| `main_page`     | "Main Page"     | 67   |
| `auto_copy`     | "Auto Copy"     | 68   |
| `card_wallet`   | "Dump Files"    | 95   |
| `scan_tag`      | "Scan Tag"      | 76   |
| `read_tag`      | "Read Tag"      | 75   |
| `sniff_tag`     | "Sniff TRF"     | 77   |
| `simulation`    | "Simulation"    | 89   |
| `pc-mode`       | "PC-Mode"       | 74   |
| `backlight`     | "Backlight"     | 70   |
| `volume`        | "Volume"        | 79   |
| `about`         | "About"         | 69   |
| `wipe_tag`      | "Erase Tag"     | 91   |
| `time_sync`     | "Time Settings" | 92   |
| `lua_script`    | "LUA Script"    | 97   |
| `diagnosis`     | "Diagnosis"     | 90   |

---

## 4. Key Bindings

### onKeyEvent (actmain_ghidra_raw.txt line 12783)

The function signature takes `(self, event)` with 2 positional args. The key handling follows this pattern (reconstructed from decompiled comparisons):

### State matrix (single state: IDLE):

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev() | next() | no-op | no-op | launch activity | no-op | launch activity | sleep/shutdown |

### Per-key detail:

| Key       | Action                                        | Citation |
|-----------|-----------------------------------------------|----------|
| UP        | `self.lv_main_page.prev()` -- move selection up | actmain_ghidra_raw.txt line ~12900: first comparison branch calls `prevItem()` |
| DOWN      | `self.lv_main_page.next()` -- move selection down | actmain_ghidra_raw.txt line ~13020: second comparison branch calls `nextItem()` |
| OK        | `self._launchActivity(pos)` -- launch selected activity | actmain_ghidra_raw.txt line ~13214: calls `gotoActByPos` |
| M1        | No action (no button label, no handler)       | No M1-specific branch found in decompiled |
| M2        | Same as OK -- launch selected activity        | Reimplementation `actmain.py` line 184: `elif key in (KEY_OK, KEY_M2)` |
| PWR       | Shutdown/sleep flow (SleepModeActivity)        | Memory: feedback_pwr_universal_back.md. On root activity, PWR triggers shutdown sequence, not finish() |
| LEFT      | No action (reimplementation has no LEFT/RIGHT handler) | SUMMARY.md mentioned page nav but reimplementation omits it since ListView handles scroll internally |
| RIGHT     | No action (same as LEFT)                      | ListView wrapping handles multi-page navigation via UP/DOWN |

**CORRECTION (2026-03-31):** Previous version stated M2 has no action. Binary re-analysis and reimplementation confirm M2 acts as OK (launches selected activity). LEFT/RIGHT page navigation removed -- ListView handles pagination via UP/DOWN scroll wrapping.

**Citation:** `src/lib/actmain.py` lines 162-196. SUMMARY.md lines 329-334 document original `onKeyEvent` behavior.

---

## 5. Activity Dispatch

### gotoActByPos (actmain_ghidra_raw.txt line 2463)

```
def gotoActByPos(self, pos):
    # Gets activity class from self._activity_list[pos]
    # Calls actstack.start_activity(clz, bundle)
    # bundle contains: {'ret': True}  (for "return to main" flag)
```

### gotoActByName (actmain_ghidra_raw.txt line 2465)

```
def gotoActByName(self, name):
    # Looks up activity by name string
    # Calls actstack.start_activity(clz, bundle)
```

**Citation:** String references at actmain_ghidra_raw.txt lines 2463-2466 confirm both `gotoActByPos` and `gotoActByName` exist. SUMMARY.md line 335: "`gotoAct(self, index)` - Launches activity by index, Uses `actstack.start_activity(clz, bundle)` pattern".

---

## 6. onCreate (actmain_ghidra_raw.txt line 15184)

The `onCreate` method performs these steps (reconstructed from decompiled code):

1. **Call super().onCreate(bundle)** -- base class initialization
2. **Create ListView widget** -- for scrollable menu items
3. **Call check_all_activity()** -- discover and populate activity list
4. **Set title** -- calls `setTitle("Main Page 1/M")` where M = total pages
5. **Buttons: NOT set** -- `setLeftButton`/`setRightButton` are NOT called (no button labels)

**Citation:** The decompiled function at line 15184 shows the argument parsing then calls to several global module lookups (widget creation, check_all_activity). The string references at lines 451, 456, 460 confirm `setRightButton`, `setLeftButton`, `dismissButton` strings exist in the module but are used by other activities (OTAActivity, WarningDiskFullActivity), NOT by `MainActivity.onCreate`.

---

## 7. Additional Activities in actmain.so

The `actmain.so` module also contains these activities (NOT part of main menu):

| Class                    | Purpose                  | Citation |
|--------------------------|--------------------------|----------|
| `OTAActivity`            | Over-The-Air firmware update | SUMMARY.md lines 366-393 |
| `SleepModeActivity`      | Sleep/hibernation screen | SUMMARY.md lines 395-404 |
| `WarningDiskFullActivity` | Disk full warning dialog | SUMMARY.md lines 406-417 |

---

## 8. Utility Functions in actmain.so

| Function              | Purpose                                    | Citation |
|-----------------------|--------------------------------------------|----------|
| `fromLevelGetBacklight` | Convert backlight level to hardware value | actmain_strings.txt line 2530 |
| `fromLevelGetVolume`    | Convert volume level to hardware value    | actmain_strings.txt line 2548 |
| `getBacklight`          | Get current backlight setting             | actmain_strings.txt line 2613 |
| `setVolume`             | Set volume setting                        | actmain_strings.txt line 2666 |
| `getVolume`             | Get current volume setting                | actmain_strings.txt line 2674 |

**Note:** These are module-level functions in `actmain.so`, not methods of `MainActivity`. They delegate to `settings.so` functions (`settings.getBacklight`, `settings.setBacklight`, etc.) as confirmed by `settings_ghidra_raw.txt` lines 239-252.

---

## 9. State Transitions

```
         ┌─────────────────────────┐
         │      MainActivity       │
         │    "Main Page N/M"      │
         │    ListView (5/page)    │
         │    No button labels     │
         └────────┬────────────────┘
                  │ OK key on selected item
                  ▼
    ┌──────────────────────────┐
    │  gotoActByPos(position)  │
    │  actstack.start_activity │
    │  (selected Activity)     │
    └──────────────────────────┘
                  │ Child finishes
                  ▼
         ┌─────────────────────────┐
         │  MainActivity.onResume  │
         │  (refreshes display)    │
         └─────────────────────────┘
```

**PWR key:** From any child activity, PWR triggers `finish()` which returns to `MainActivity` via `actstack.finish_activity()` -> `prev_act.onResume()` (SUMMARY.md lines 156-165).

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | Removed "Write Tag" from menu item list (was erroneously at position 5). Added "Diagnosis" (DiagnosisActivity) at position 7. Correct page 2 order: Simulation, PC-Mode, Diagnosis, Backlight, Volume. Total remains 14 items (5+5+4). | `main_page_1_3_1.png`, `main_page_2_3_1.png`, `main_page_3_3_1.png` |
| 2026-03-31 | Removed `write_tag` from Title Strings table (item not present in menu). | `main_page_2_3_1.png` |
