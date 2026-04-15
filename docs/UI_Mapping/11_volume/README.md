# VolumeActivity UI Mapping

**Source module:** `activity_main.so` (in combined activity module)
**Decompiled reference:** `decompiled/activity_main_ghidra_raw.txt`
**Class:** `VolumeActivity`
**Menu position:** 9 (page 2, position 4 on page)
**Settings persistence:** `settings.so` via `settings.setVolume(level)` / `settings.getVolume()`
**Audio control:** `audio.setKeyAudioEnable()` for enabling/disabling key sounds

---

## 1. Screen Layout

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Volume"                            |
|  Font: Consolas 18, white on #788098 |
+--------------------------------------+
|  Content Area (0,40)-(240,200)       |
|  CheckedListView: 4 items, ~32px ea  |
|  Selection: dark rectangle highlight |
|  Check indicator: RIGHT side         |
|    Unchecked: grey-stroked square    |
|      outline                         |
|    Checked: blue-stroked square      |
|      outline + inner blue fill       |
|                                      |
|  Off                     [ ]        |
|  Low                     [X]        |
|  Middle                  [ ]        |
|  High                    [ ]        |
+--------------------------------------+
|  Button Bar: HIDDEN / NOT SET        |
|  (dismissed or never created)        |
|  M1 = (none), M2 = (none)           |
+--------------------------------------+
```

**Title citation:** `resources.py` StringEN.title line 79: `'volume': 'Volume'`

**Widget type:** `CheckedListView` (same as BacklightActivity). Confirmed by parallel structure to BacklightActivity and by string reference `__pyx_k_CheckedListView` in `activity_main_strings.txt` line 25173.

**Button labels:** The `VolumeActivity` does NOT set M1 or M2 button labels. The OK key saves (confirmed by memory note `feedback_settings_ok_key.md`: "Settings save key is OK, not M2. M1/M2 have no action on CheckedListView settings screens (Backlight, Volume)").

---

## 2. Item List

| Index | Label    | Volume Level | Citation |
|-------|----------|--------------|----------|
| 0     | "Off"    | 0            | resources.py StringEN.itemmsg line 220: `'valueline1': 'Off'` |
| 1     | "Low"    | 1            | resources.py StringEN.itemmsg line 221: `'valueline2': 'Low'` |
| 2     | "Middle" | 2            | resources.py StringEN.itemmsg line 222: `'valueline3': 'Middle'` |
| 3     | "High"   | 3            | resources.py StringEN.itemmsg line 223: `'valueline4': 'High'` |

**Note:** Volume has 4 items (including "Off") vs Backlight's 3 items (no "Off" option). Volume uses `valueline1`-`valueline4` keys while Backlight uses `blline1`-`blline3` keys.

---

## 3. Key Bindings

### onKeyEvent (activity_main_ghidra_raw.txt line 35648)

The function takes `(self, event)` with 2 positional args. Decompiled at line 35648, the comparison cascade reveals a structure parallel to `BacklightActivity.onKeyEvent`:

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev() + preview | next() + preview | no-op | no-op | save (stay) | no-op | save (stay) | finish() (no recovery) |

Expanded per-key detail:

| Key   | Action                                           | Citation |
|-------|--------------------------------------------------|----------|
| UP    | Move CheckedListView selection up. Instant audio preview: plays preview sound at new level. | Decompiled line ~35829: first true branch after key comparison |
| DOWN  | Move CheckedListView selection down. Instant audio preview. | Decompiled line ~36035: second true branch (symmetric with UP) |
| OK    | **Save (stay on screen).** Calls `self.saveSetting()`. Does NOT call `self.finish()`. Plays volume preview via `audio.playVolumeExam()`. | Reimplementation `activity_main.py` line 330: `_save()` does NOT finish. |
| M2    | **Same as OK.** Calls `self.saveSetting()`. Does NOT finish. | Reimplementation `activity_main.py` line 325: `elif key in (KEY_M2, KEY_OK): self._save()` |
| M1    | No action (no handler branch)                    | No M1-specific branch in decompiled onKeyEvent |
| PWR   | **Exit without recovery.** Calls `self.finish()` directly. Unlike Backlight, Volume does NOT restore the original level on PWR. | Reimplementation line 369-375: `_cancel()` just calls `self.finish()` |

**KEY DIFFERENCE vs BacklightActivity:** Volume does NOT revert on PWR exit. Once saved via OK/M2, the level persists. BacklightActivity reverts on PWR (recovery_backlight). Volume simply exits on PWR.

**CORRECTION (2026-03-31):** Previous version stated OK saves AND exits, and PWR restores original. Binary re-analysis confirms: OK/M2 save but do NOT exit. PWR exits WITHOUT recovery.

**Citation:** `src/lib/activity_main.py` lines 309-375 (verified against `activity_main_ghidra_raw.txt` line 35648).

---

## 4. Methods

### __init__ (activity_main_ghidra_raw.txt line 7790)

```
def __init__(self, bundle):
    super().__init__(bundle)
    # Initialize _original_level from settings.getVolume()
    # Store for recovery on cancel
```

**Citation:** Decompiled function at line 7790. Parallel structure to `BacklightActivity.__init__` at line 8033.

### onCreate (referenced at activity_main_strings.txt line 20857)

```
def onCreate(self, bundle):
    super().onCreate(bundle)
    # 1. setTitle("Volume")  -- from resources.title['volume']
    # 2. Create CheckedListView with 4 items: ["Off", "Low", "Middle", "High"]
    # 3. Set initial check position from settings.getVolume()
    # 4. Buttons: NOT set (no setLeftButton/setRightButton calls)
```

**Citation:** String reference `VolumeActivity.onCreate` at activity_main_strings.txt line 21186. The decompiled function address from string `__pyx_pw_13activity_main_14VolumeActivity_5onCreate` at activity_main_strings.txt line 589.

### saveSetting (activity_main_ghidra_raw.txt line 36881)

```
def saveSetting(self):
    # 1. Get current CheckedListView position (0-3)
    # 2. Call settings.setVolume(level) to persist to conf.ini
    # 3. If level == 0 (Off): audio.setKeyAudioEnable(False)
    #    If level > 0: audio.setKeyAudioEnable(True)
    # 4. Apply volume via audio module
```

**Citation:** Decompiled function at line 36881 (`VolumeActivity_7saveSetting`). The function calls `settings.setVolume` (confirmed by settings_ghidra_raw.txt line 246) and manages audio enable state.

**Volume test citation:** `volume_save_low_to_mid.sh` line 3: "Tests non-Off to non-Off save (setKeyAudioEnable stays true)" -- confirms the Off/non-Off logic.

### getManifest (activity_main_ghidra_raw.txt line 37328)

```
def getManifest(self):
    return {
        'title': resources.getString('volume'),  # "Volume"
        'icon': (icon_image, icon_label)          # icon tuple
    }
```

**Citation:** Decompiled function at line 37328. Same pattern as BacklightActivity.getManifest (line 35328).

---

## 5. Settings Persistence

**File:** `/mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini`
**Section:** `[DEFAULT]`
**Key:** `volume`
**Values:** `0` (Off), `1` (Low), `2` (Middle), `3` (High)

**Citation:** `settings_ghidra_raw.txt` lines 245-247, 264-265: `getVolume`, `setVolume`, string `volume`. The conf.ini path and section confirmed by `backlight_common.sh` lines 38-39 (same file, same section, different key).

### Settings Flow

```
settings.getVolume()       →  reads conf.ini [DEFAULT] volume  →  returns 0/1/2/3
settings.setVolume(n)      →  writes conf.ini [DEFAULT] volume = n
fromLevelGetVolume(n)      →  converts level to audio parameter
```

**Citation:** `settings_ghidra_raw.txt` lines 245-247 for get/set. `actmain_strings.txt` line 2548 confirms `fromLevelGetVolume` module-level function.

---

## 6. Differences from BacklightActivity

| Aspect               | BacklightActivity          | VolumeActivity              |
|-----------------------|----------------------------|-----------------------------|
| Item count            | 3                          | 4                           |
| Has "Off" option      | No                         | Yes (index 0)               |
| Item key prefix       | `blline1`-`blline3`        | `valueline1`-`valueline4`   |
| Save method           | `updateBacklight()`        | `saveSetting()`             |
| Cancel method         | `recovery_backlight()`     | (inline restore in onKeyEvent) |
| Hardware control      | `hmi_driver.setbaklight()` | `audio` module              |
| Settings key          | `backlight`                | `volume`                    |
| Instant preview       | Yes (brightness change)    | Yes (audio preview)         |
| Audio enable toggle   | N/A                        | Yes (`setKeyAudioEnable`)   |

---

## 7. State Transitions

```
                    ┌──────────────────────────┐
 Main Menu          │    VolumeActivity        │
 pos 9 ─── OK ───▶ │    title: "Volume"       │
                    │    CheckedListView (4)   │
                    │    No button labels      │
                    └────┬───────────┬─────────┘
                         │           │
                    UP/DOWN       OK key
                  (instant       (save)
                   preview)        │
                         │         ▼
                         │    saveSetting()
                         │    settings.setVolume()
                         │    audio.setKeyAudioEnable()
                         │    finish() → Main Menu
                         │
                    PWR key
                    (cancel)
                         │
                         ▼
                    Restore original volume
                    finish() → Main Menu
```

---

## 8. Ground Truth Checklist

| Property            | Value                        | Source |
|---------------------|------------------------------|--------|
| Title               | "Volume"                     | resources.py line 79 |
| M1 label            | (none/empty)                 | feedback_settings_ok_key.md |
| M2 label            | (none/empty)                 | feedback_settings_ok_key.md |
| Item count           | 4                            | resources.py lines 220-223 |
| Item 0              | "Off"                        | resources.py itemmsg valueline1 |
| Item 1              | "Low"                        | resources.py itemmsg valueline2 |
| Item 2              | "Middle"                     | resources.py itemmsg valueline3 |
| Item 3              | "High"                       | resources.py itemmsg valueline4 |
| Widget type         | CheckedListView              | activity_main_strings.txt line 25173 |
| Check indicator     | Unchecked: grey-stroked square outline, RIGHT side. Checked: blue-stroked square outline + inner blue fill, RIGHT side. | `volume_1.png` through `volume_6.png` |
| Save key            | OK                           | feedback_settings_ok_key.md |
| Cancel key          | PWR                          | backlight_common.sh + parallel structure |
| Instant preview     | Yes (UP/DOWN triggers audio) | Parallel to backlight instant preview |
| Settings key        | conf.ini [DEFAULT] volume    | settings_ghidra_raw.txt lines 264-265 |
| Settings values     | 0, 1, 2, 3                   | resources.py itemmsg valueline1-4 |

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | Corrected check indicator description from generic "filled square" to two-part rendering: unchecked = grey-stroked square outline on RIGHT; checked = blue-stroked square outline + inner blue-filled square on RIGHT. | `volume_1.png` through `volume_6.png` |
