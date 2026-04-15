# BacklightActivity UI Mapping

**Source module:** `activity_main.so` (in combined activity module)
**Decompiled reference:** `decompiled/activity_main_ghidra_raw.txt`
**Class:** `BacklightActivity`
**Menu position:** 8 (page 2, position 3 on page)
**Settings persistence:** `settings.so` via `settings.setBacklight(level)` / `settings.getBacklight()`
**Hardware control:** `hmi_driver.setbaklight(level)` for instant preview

---

## 1. Screen Layout

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Backlight"                         |
|  Font: Consolas 18, white on #788098 |
+--------------------------------------+
|  Content Area (0,40)-(240,200)       |
|  CheckedListView: 3 items, ~32px ea  |
|  Selection: dark rectangle highlight |
|  Check indicator: RIGHT side         |
|    Unchecked: grey-stroked square    |
|      outline                         |
|    Checked: blue-stroked square      |
|      outline + inner blue fill       |
|                                      |
|  Low                     [ ]        |
|  Middle                  [ ]        |
|  High                    [X]        |
+--------------------------------------+
|  Button Bar: HIDDEN / NOT SET        |
|  (dismissed or never created)        |
|  M1 = (none), M2 = (none)           |
+--------------------------------------+
```

**Title citation:** `resources.py` StringEN.title line 70: `'backlight': 'Backlight'`

**Widget type:** `CheckedListView` (NOT regular `ListView`). Confirmed by string reference in `activity_main_strings.txt` line 25173: `__pyx_k_CheckedListView`.

**Check indicator:** Two-part rendering on the RIGHT side of each item row:
- **Unchecked items:** grey-stroked square outline (border only, no fill)
- **Checked/selected item:** blue-stroked square outline with inner blue-filled square
This is NOT a green checkmark on the left. The `CheckedListView` widget (widget_ghidra_raw.txt) has methods `check()` (line 32672), `auto_show_chk()` (line 20025), and `getCheckPosition()` (line 4898). The two-part rendering is likely two `fillsquare` HMI calls: one for the border stroke, one for the inner fill.

**Check indicator citation:** `backlight_1.png` through `backlight_5.png` show the grey square outlines for unchecked items and blue square with inner fill for the checked item.

**Button labels:** The `BacklightActivity` does NOT set M1 or M2 button labels. The OK key saves (confirmed by memory note `feedback_settings_ok_key.md`: "Settings save key is OK, not M2. M1/M2 have no action on CheckedListView settings screens (Backlight, Volume)").

---

## 2. Item List

| Index | Label    | Backlight Level | HMI Value | Citation |
|-------|----------|-----------------|-----------|----------|
| 0     | "Low"    | 0               | 10        | resources.py StringEN.itemmsg line 224: `'blline1': 'Low'` |
| 1     | "Middle" | 1               | 50        | resources.py StringEN.itemmsg line 225: `'blline2': 'Middle'` |
| 2     | "High"   | 2               | 100       | resources.py StringEN.itemmsg line 226: `'blline3': 'High'` |

**HMI values citation:** `backlight_common.sh` lines 10-12: "item 0: Low (setbaklight 10), item 1: Middle (setbaklight 50), item 2: High (setbaklight 100)".

**Note:** Backlight uses distinct item keys (`blline1`/`blline2`/`blline3`) separate from volume's `valueline1`-`valueline4`. Backlight has NO "Off" option (3 items vs volume's 4 items).

---

## 3. Key Bindings

### onKeyEvent (activity_main_ghidra_raw.txt line 33990)

The function takes `(self, event)` with 2 positional args. Decompiled at line 33990, the comparison cascade reveals:

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev() + preview | next() + preview | no-op | no-op | save (stay) | no-op | save (stay) | recovery + finish() |

Expanded per-key detail:

| Key   | Action                                           | Citation |
|-------|--------------------------------------------------|----------|
| UP    | Move CheckedListView selection up. Instant preview: calls `hmi_driver.setbaklight()` with the newly selected level's hardware value. | Decompiled line ~34173: first true branch calls `self.isbusy()` check, then moves selection |
| DOWN  | Move CheckedListView selection down. Instant preview: calls `hmi_driver.setbaklight()` with the newly selected level's hardware value. | Decompiled line ~34411: second true branch (UP/DOWN are symmetric) |
| OK    | **Save (stay on screen).** Calls `self.updateBacklight()`. Does NOT call `self.finish()`. | Decompiled `updateBacklight` at binary, reimplementation line 194: `_save()` docstring says "Does NOT finish -- stays on screen." |
| M2    | **Same as OK.** Calls `self.updateBacklight()`. Does NOT finish. | Reimplementation `activity_main.py` line 189: `elif key in (KEY_M2, KEY_OK): self._save()` |
| M1    | No action (no handler branch)                    | No M1-specific branch in decompiled onKeyEvent |
| PWR   | **Cancel and exit.** Calls `self.recovery_backlight()` then `self.finish()`. Restores original backlight level. | Decompiled line ~34430: final branch calls `recovery_backlight` then `finish` |

**Instant preview:** When UP/DOWN changes selection, `hmi_driver.setbaklight()` is called immediately so the user can see the brightness change BEFORE saving.

**CORRECTION (2026-03-31):** Previous version stated OK saves AND exits. Binary re-analysis confirms OK/M2 call `updateBacklight()` only (save, no finish). Only PWR exits (with recovery). The `_save()` method updates check marks, persists to settings, and applies to hardware but does NOT call `finish()`.

**Citation:** `src/lib/activity_main.py` lines 173-240 (verified against `activity_main_ghidra_raw.txt` line 33990).

---

## 4. Methods

### __init__ (activity_main_ghidra_raw.txt line 8033)

```
def __init__(self, bundle):
    super().__init__(bundle)
    # Initialize _original_level from settings.getBacklight()
    # Store for recovery on cancel
```

### onCreate (referenced at activity_main_strings.txt line 20831)

```
def onCreate(self, bundle):
    super().onCreate(bundle)
    # 1. setTitle("Backlight")  -- from resources.title['backlight']
    # 2. Create CheckedListView with 3 items: ["Low", "Middle", "High"]
    # 3. Set initial check position from settings.getBacklight()
    # 4. Buttons: NOT set (no setLeftButton/setRightButton calls)
    # 5. dismissButton() may be called to hide button bar
```

### updateBacklight (activity_main_strings.txt line 20887)

```
def updateBacklight(self):
    # 1. Get current CheckedListView position
    # 2. Call settings.setBacklight(level) to persist to conf.ini
    # 3. Call hmi_driver.setbaklight(hardware_value) to apply
```

**Citation:** String references at `activity_main_strings.txt` line 20887: `BacklightActivity.updateBacklight`. Lambda reference at line 35137 (`updateBacklight_lambda`) confirms async/deferred execution pattern.

### recovery_backlight (activity_main_strings.txt line 20888)

```
def recovery_backlight(self):
    # 1. Retrieve self._original_level (saved in __init__)
    # 2. Call hmi_driver.setbaklight(original_hardware_value)
    # Does NOT call settings.setBacklight -- only reverts hardware
```

**Citation:** String reference at `activity_main_strings.txt` line 20888: `BacklightActivity.recovery_backlight`. Lambda reference at line 34946 (`recovery_backlight_lambda1`).

### getManifest (activity_main_ghidra_raw.txt line 35328)

```
def getManifest(self):
    return {
        'title': resources.getString('backlight'),  # "Backlight"
        'icon': (icon_image, icon_label)             # icon tuple
    }
```

**Citation:** Decompiled function at line 35328. Creates a `PyDict_New()`, sets item with title key (line 35373), retrieves icon via module global lookups (lines 35391-35406), creates a 2-tuple for (icon, label) (lines 35516-35530), and sets it in the dict (line 35531).

---

## 5. Settings Persistence

**File:** `/mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini`
**Section:** `[DEFAULT]`
**Key:** `backlight`
**Values:** `0` (Low), `1` (Middle), `2` (High)

**Citation:** `backlight_common.sh` lines 38-39: "conf.ini at /mnt/sdcard/root2/root/home/pi/ipk_app_main/data/conf.ini, Section [DEFAULT], key 'backlight', values 0/1/2". Settings module strings at `settings_ghidra_raw.txt` lines 239-241, 259-261, 266.

### Settings Flow

```
settings.getBacklight()  →  reads conf.ini [DEFAULT] backlight  →  returns 0/1/2
settings.setBacklight(n) →  writes conf.ini [DEFAULT] backlight = n
fromLevelGetBacklight(n) →  converts level to HMI value (0→10, 1→50, 2→100)
```

**Citation:** `settings_ghidra_raw.txt` lines 239-250 list all settings functions. `actmain_strings.txt` line 2530 confirms `fromLevelGetBacklight` exists as a module-level function.

---

## 6. State Transitions

```
                    ┌──────────────────────────┐
 Main Menu          │    BacklightActivity     │
 pos 8 ─── OK ───▶ │    title: "Backlight"    │
                    │    CheckedListView (3)   │
                    │    No button labels      │
                    └────┬───────────┬─────────┘
                         │           │
                    UP/DOWN       OK key
                  (instant       (save)
                   preview)        │
                         │         ▼
                         │    updateBacklight()
                         │    settings.setBacklight()
                         │    hmi_driver.setbaklight()
                         │    finish() → Main Menu
                         │
                    PWR key
                    (cancel)
                         │
                         ▼
                    recovery_backlight()
                    hmi_driver.setbaklight(original)
                    finish() → Main Menu
```

---

## 7. Ground Truth Checklist

| Property            | Value                        | Source |
|---------------------|------------------------------|--------|
| Title               | "Backlight"                  | resources.py line 70 |
| M1 label            | (none/empty)                 | feedback_settings_ok_key.md |
| M2 label            | (none/empty)                 | feedback_settings_ok_key.md |
| Item count           | 3                            | resources.py lines 224-226 |
| Item 0              | "Low"                        | resources.py itemmsg blline1 |
| Item 1              | "Middle"                     | resources.py itemmsg blline2 |
| Item 2              | "High"                       | resources.py itemmsg blline3 |
| Widget type         | CheckedListView              | activity_main_strings.txt line 25173 |
| Check indicator     | Unchecked: grey-stroked square outline, RIGHT side. Checked: blue-stroked square outline + inner blue fill, RIGHT side. | `backlight_1.png` - `backlight_5.png` |
| Save key            | OK                           | feedback_settings_ok_key.md |
| Cancel key          | PWR                          | backlight_common.sh line 16 |
| Instant preview     | Yes (UP/DOWN triggers HMI)   | backlight_common.sh line 14 |
| Settings key        | conf.ini [DEFAULT] backlight | backlight_common.sh line 19 |
| Settings values     | 0, 1, 2                      | backlight_common.sh line 19 |

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | Corrected check indicator description from generic "filled square" to two-part rendering: unchecked = grey-stroked square outline on RIGHT; checked = blue-stroked square outline + inner blue-filled square on RIGHT. | `backlight_1.png` through `backlight_5.png` |
