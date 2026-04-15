# TimeSyncActivity UI Mapping

**Source module:** `activity_main.so` (in combined activity module)
**Decompiled reference:** `decompiled/activity_main_ghidra_raw.txt`
**Class:** `TimeSyncActivity`
**Menu position:** 12 (page 3, position 2 on page)
**String table references:** `activity_main_strings.txt` lines 20561-20860

---

## 1. Screen Layout -- Display Mode

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Time Settings"                     |
|  Font: Consolas 18, white on #788098 |
+--------------------------------------+
|  Content Area (0,40)-(240,200)       |
|  InputMethodList widget              |
|                                      |
|  ┌────┐   ┌────┐   ┌────┐           |
|  │1970│ - │ 02 │ - │ 12 │   (date)  |
|  └────┘   └────┘   └────┘           |
|                                      |
|  ┌────┐   ┌────┐   ┌────┐           |
|  │ 03 │ : │ 38 │ : │ 42 │   (time)  |
|  └────┘   └────┘   └────┘           |
|                                      |
+--------------------------------------+
|  Button Bar (0,200)-(240,240)        |
|  M1 = "Edit"    M2 = "Edit"         |
|  Font: mononoki 16                   |
+--------------------------------------+
```

**Title citation:** `resources.py` StringEN.title line 92: `'time_sync': 'Time Settings'`

**Citation:** Screenshot `v1090_captures/090-Time.png` shows: title "Time Settings" with battery icon, six numeric fields arranged in 2 rows (YYYY-MM-DD / HH:MM:SS), and button labels "Edit" on both M1 and M2.

---

## 2. Screen Layout -- Edit Mode

```
+--------------------------------------+
|  Title Bar (0,0)-(240,40)            |
|  "Time Settings"                     |
|  Font: Consolas 18, white on #788098 |
+--------------------------------------+
|  Content Area (0,40)-(240,200)       |
|  InputMethodList widget              |
|                                      |
|  ┌────┐   ┌────┐   ┌────┐           |
|  │1970│ - │ 02 │ - │ 12 │   (date)  |
|  └────┘   └────┘   └────┘           |
|          ^                           |
|  ┌────┐   ┌────┐   ┌────┐           |
|  │ 03 │ : │ 38 │ : │ 42 │   (time)  |
|  └────┘   └────┘   └────┘           |
|                                      |
|  ^ = up/down arrows on focused field |
+--------------------------------------+
|  Button Bar (0,200)-(240,240)        |
|  M1 = "Cancel"  M2 = "Save"         |
|  Font: mononoki 16                   |
+--------------------------------------+
```

**Citation:** Screenshot `v1090_captures/090-Time-Select.png` shows: same title, six fields with up/down arrows visible on the focused field (the "^" caret arrow), and button labels "Cancel" (M1) and "Save" (M2).

**Second edit screenshot:** `v1090_captures/090-Time-Select-2.png` shows the same edit mode layout, confirming "Cancel"/"Save" button labels.

---

## 3. Two Modes

The TimeSyncActivity operates in two distinct modes:

### Display Mode (initial state on entry)
- Shows current system time in 6 fields
- No field is focused/editable
- Buttons: M1 = "Edit", M2 = "Edit"
- UP/DOWN/LEFT/RIGHT: no action (fields not editable)
- M1 or M2: transition to Edit Mode
- PWR: exit back to Main Menu

### Edit Mode (after pressing Edit)
- One field has focus (shown with up/down arrows)
- Buttons: M1 = "Cancel", M2 = "Save"
- UP/DOWN: increment/decrement focused field value
- LEFT/RIGHT: move focus between fields
- M1 (Cancel): discard changes, return to Display Mode
- M2 (Save): sync time to system, return to Display Mode
- PWR: cancel and exit back to Main Menu

**Button label strings:**
- `resources.py` StringEN.button line 61: `'edit': 'Edit'`
- `resources.py` StringEN.button line 48: `'cancel': 'Cancel'`
- `resources.py` StringEN.button line 45: `'save': 'Save'`

---

## 4. Input Fields (InputMethodList widget)

| Index | Field  | Range        | Format | Position |
|-------|--------|--------------|--------|----------|
| 0     | Year   | 1970 - 2099  | 4-digit| Row 1, Col 1 |
| 1     | Month  | 01 - 12      | 2-digit| Row 1, Col 2 |
| 2     | Day    | 01 - 28/29/30/31 | 2-digit| Row 1, Col 3 |
| 3     | Hour   | 00 - 23      | 2-digit| Row 2, Col 1 |
| 4     | Minute | 00 - 59      | 2-digit| Row 2, Col 2 |
| 5     | Second | 00 - 59      | 2-digit| Row 2, Col 3 |

**Day range is dynamic** -- depends on the currently selected month and year (leap year handling). The `get_max_min()` method (activity_main_strings.txt line 21058) computes valid ranges.

**Widget:** `InputMethodList` (widget_ghidra_raw.txt strings lines 308-309, 327-329). This is a list of `InputMethods` widgets, each representing one numeric field. The `InputMethodList` manages focus across all fields.

**Separators:** Dash "-" between date fields, colon ":" between time fields (visible in screenshots).

---

## 5. Key Bindings

### onKeyEvent (activity_main_strings.txt line 21082, decompiled reference at line 20638)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| DISPLAY | no-op | no-op | no-op | no-op | no-op | enterEdit() | enterEdit() | finish() |
| EDIT | increment field | decrement field | prev field (wrap) | next field (wrap) | no-op | no-op | saveTime() -> DISPLAY | exitEdit() -> DISPLAY |

Expanded per-key detail:

| Key   | Display Mode                | Edit Mode                           |
|-------|-----------------------------|-------------------------------------|
| UP    | No action                   | `_incrementField()` -- increment focused field value (wraps max->min) |
| DOWN  | No action                   | `_decrementField()` -- decrement focused field value (wraps min->max) |
| LEFT  | No action                   | `_moveCursorLeft()` -- move cursor to previous field (wraps around) |
| RIGHT | No action                   | `_moveCursorRight()` -- move cursor to next field (wraps around) |
| OK    | No action                   | No action                           |
| M1    | Enter Edit Mode             | No action (pass in binary)          |
| M2    | Enter Edit Mode             | Save: `_saveTime()`, return to Display Mode |
| PWR   | Exit to Main Menu           | Discard changes, return to Display Mode |

**CORRECTION (2026-03-31):** Previous version stated OK enters edit mode. Binary re-analysis confirms OK has no action in either mode. M1 enters edit mode from DISPLAY but has no action in EDIT mode. PWR in EDIT mode returns to DISPLAY (does NOT exit activity).

**Citation for M1/M2 labels:**
- Display Mode: screenshot `090-Time.png` shows "Edit" / "Edit"
- Edit Mode: screenshot `090-Time-Select.png` shows "Cancel" / "Save"

---

## 6. Methods

### __init__ (activity_main_strings.txt line 21187)

```
def __init__(self, bundle):
    super().__init__(bundle)
    # Initialize time fields from system clock
    # Set _is_editing = False (display mode)
```

### onCreate (activity_main_strings.txt line 21134)

```
def onCreate(self, bundle):
    super().onCreate(bundle)
    # 1. setTitle("Time Settings")
    # 2. Create InputMethodList with 6 fields (YYYY, MM, DD, HH, MM, SS)
    # 3. init_views() -- populate fields with current system time
    # 4. setLeftButton("Edit")
    # 5. setRightButton("Edit")
    # 6. edit_arrow_enable(False) -- disable arrows in display mode
```

### init_views (activity_main_strings.txt line 21083)

```
def init_views(self):
    # Reads current system time
    # Populates all 6 InputMethods fields with current values
    # Called from onCreate and on mode transitions
```

**Citation:** Decompiled reference at `activity_main_ghidra_raw.txt` line 20693 (`TimeSyncActivity_6init_views`).

### up_down_word_if_focus (activity_main_strings.txt line 20903)

```
def up_down_word_if_focus(self, direction):
    # Called on UP/DOWN in edit mode
    # Gets currently focused InputMethods widget
    # Calls upword() or downword() to change value
    # Validates against get_max_min() range
    # Wraps at boundaries (e.g., 12 -> 01 for month)
```

**Citation:** String reference at activity_main_strings.txt line 20903 and decompiled at line 20561.

### im_selection_left_right (activity_main_strings.txt line 20908)

```
def im_selection_left_right(self, direction):
    # Called on LEFT/RIGHT in edit mode
    # Moves focus to previous/next InputMethods field
    # Wraps: field 0 LEFT -> field 5, field 5 RIGHT -> field 0
```

**Citation:** String reference at activity_main_strings.txt line 20908 and decompiled at line 20708.

### im_selection_up_down (activity_main_strings.txt line 20907)

```
def im_selection_up_down(self, direction):
    # Alternative UP/DOWN handler for row-based navigation
    # Moves focus between row 1 (date) and row 2 (time)
```

**Citation:** String reference at activity_main_strings.txt line 20907 and decompiled at line 20734.

### edit_arrow_enable (activity_main_strings.txt line 20909)

```
def edit_arrow_enable(self, enabled):
    # Shows/hides the up/down arrows on the focused field
    # Called with True when entering edit mode
    # Called with False when leaving edit mode
```

**Citation:** String reference at activity_main_strings.txt line 20909 and decompiled at line 20811.

### arrow_im_selection (activity_main_strings.txt line 20910)

```
def arrow_im_selection(self):
    # Handles arrow key-driven field selection
    # Manages visual state of selection arrows
```

### get_max_min (activity_main_strings.txt line 21058)

```
def get_max_min(self, field_index):
    # Returns (min_value, max_value) for the specified field
    # Field 0 (Year): (1970, 2099)
    # Field 1 (Month): (1, 12)
    # Field 2 (Day): (1, days_in_month)  -- respects leap years
    # Field 3 (Hour): (0, 23)
    # Field 4 (Minute): (0, 59)
    # Field 5 (Second): (0, 59)
```

**Citation:** Decompiled at line 20770 (`TimeSyncActivity_17get_max_min`).

### sync_time_to_system (activity_main_strings.txt line 20904)

```
def sync_time_to_system(self):
    # Reads all 6 field values from InputMethodList
    # Constructs datetime string
    # Sets system time via OS command
    # Shows toast: "Synchronization successful!" or "Synchronizing system time"
```

**Toast strings citation:**
- `resources.py` StringEN.toastmsg line 134: `'time_syncing': 'Synchronizing system time'`
- `resources.py` StringEN.toastmsg line 135: `'time_syncok': 'Synchronization successful!'`

**Citation:** Decompiled at line 20769 and string reference at line 20904.

### run_sync_time_self (activity_main_strings.txt line 20905)

```
def run_sync_time_self(self):
    # Background task wrapper for sync_time_to_system
    # Shows progress toast during sync
```

**Citation:** Decompiled at line 20601.

### same_chk (activity_main_strings.txt line 21132)

```
def same_chk(self):
    # Checks if edited values differ from original
    # Returns True if no changes were made
    # Used to optimize: skip sync if nothing changed
```

### get_im_focus (activity_main_strings.txt line 21030)

```
def get_im_focus(self):
    # Returns the currently focused InputMethods widget index
    # Returns -1 if no field has focus (display mode)
```

### run_serial_listener (activity_main_strings.txt line 20906)

```
def run_serial_listener(self):
    # Serial listener for USB time sync from PC
    # Listens for time data sent over USB serial
```

**Citation:** String reference at activity_main_strings.txt line 20906 and decompiled at line 20860.

### onResume (activity_main_strings.txt line 21133)

```
def onResume(self):
    super().onResume()
    # Refresh time display with current system time
```

**Citation:** Decompiled at line 20832.

### onDestroy (activity_main_strings.txt line 21107)

```
def onDestroy(self):
    # Stop serial listener if running
    super().onDestroy()
```

**Citation:** Decompiled at line 20711.

---

## 7. InputMethodList Widget Architecture

The `InputMethodList` widget (from `widget.so`) manages a collection of `InputMethods` widgets:

### InputMethodList Methods (from widget_ghidra_raw.txt)

| Method                    | Purpose                                    | Citation |
|---------------------------|--------------------------------------------|----------|
| `add_method()`            | Add an InputMethods field to the list      | widget strings line 428 |
| `add_method_if_new()`     | Add field only if not already present      | widget strings line 328 |
| `set_input_method_max()`  | Set maximum value for a field              | widget strings line 308 |
| `set_input_method_height()`| Set field display height                  | widget strings line 309 |
| `get_input_method_count()`| Get number of fields                       | widget strings line 327 |
| `update_focus()`          | Update visual focus indicator              | widget strings line 385 |
| `has_focus()`             | Check if any field has focus               | widget strings line 411 |
| `focus_exit()`            | Remove focus from all fields               | widget strings line 384 |
| `left()`                  | Move focus left                            | widget strings line 382 |
| `right()`                 | Move focus right                           | widget strings line 383 |
| `up()`                    | Navigate up in field list                  | widget strings line 423 |
| `down()`                  | Navigate down in field list                | widget strings line 422 |
| `get_all_input_text()`    | Get all field values as text               | widget strings line 412 |
| `_get_focus_method()`     | Get currently focused InputMethods widget  | widget strings line 410 |
| `_set_focus_state()`      | Set focus state for a field                | widget strings line 416 |
| `_show_current_page()`    | Render current page of fields              | widget strings line 478 |
| `_hidden_all_group()`     | Hide all field groups                      | widget strings line 480 |
| `_goto_create_mode()`     | Enter creation/edit mode                   | widget strings line 438 |
| `_act_item_and_selection()`| Activate item and update selection         | widget strings line 455 |

### InputMethods Widget Methods (from widget_ghidra_raw.txt)

| Method             | Purpose                                    | Citation |
|--------------------|--------------------------------------------|----------|
| `upword()`         | Increment digit value                      | widget strings line 398 |
| `downword()`       | Decrement digit value                      | widget strings line 397 |
| `nextitem()`       | Move to next digit position                | widget strings line 396 |
| `lastitem()`       | Move to previous digit position            | widget strings line 395 |
| `setdata()`        | Set field value                            | widget strings line 473 |
| `getdata()`        | Get field value                            | widget strings line 329 |
| `show()`           | Show the widget                            | widget strings line 392 |
| `hide()`           | Hide the widget                            | widget strings line 391 |
| `setfocus()`       | Give focus to this widget                  | widget strings line 389 |
| `unsetfocus()`     | Remove focus from this widget              | widget strings line 388 |
| `rollfocus()`      | Toggle focus state                         | widget strings line 390 |
| `rollshowhide()`   | Toggle visibility                          | widget strings line 393 |
| `resetselection()` | Reset digit selection                      | widget strings line 394 |
| `isshowing()`      | Check if visible                           | widget strings line 312 |
| `isfocuing()`      | Check if has focus                         | widget strings line 311 |
| `_setstate()`      | Set internal state                         | widget strings line 435 |
| `_intdraw_word()`  | Internal draw for digit display            | widget strings line 440 |
| `_findnextword()`  | Find next valid digit value                | widget strings line 331 |
| `_findlastword()`  | Find previous valid digit value            | widget strings line 330 |

### Visual Constants

| Property              | Value                | Citation |
|-----------------------|----------------------|----------|
| `_InputMethod_BG1`    | Background color 1   | activity_main_strings.txt line 20911 |
| `_InputMethod_BG2`    | Background color 2   | activity_main_strings.txt line 20879 |

---

## 8. State Transitions

```
                     ┌─────────────────────────────┐
  Main Menu          │   TimeSyncActivity           │
  pos 12 ── OK ────▶ │   title: "Time Settings"     │
                     │   DISPLAY MODE               │
                     │   M1="Edit"  M2="Edit"       │
                     │   6 fields (read-only)        │
                     └──────┬───────────┬────────────┘
                            │           │
                       M1 or M2      PWR key
                       (enter edit)  (exit)
                            │           │
                            ▼           ▼
                     ┌────────────┐   Main Menu
                     │ EDIT MODE  │
                     │ M1="Cancel"│
                     │ M2="Save"  │
                     │ UP/DOWN:   │
                     │  inc/dec   │
                     │ LEFT/RIGHT:│
                     │  prev/next │
                     │  field     │
                     └───┬────┬───┘
                         │    │
                    M1   │    │ M2
                 (cancel)│    │(save)
                         │    │
                         ▼    ▼
             ┌───────────┐  ┌───────────────────┐
             │ Discard   │  │ sync_time_to_     │
             │ changes   │  │ system()          │
             │ Return to │  │ Toast: "Synchro-  │
             │ DISPLAY   │  │ nization          │
             │ MODE      │  │ successful!"      │
             └───────────┘  │ Return to DISPLAY │
                            │ MODE              │
                            └───────────────────┘

  PWR from EDIT MODE:
    → Cancel changes
    → Exit directly to Main Menu (finish())
```

---

## 9. Toast Messages

| Event           | Toast Text                        | Duration | Citation |
|-----------------|-----------------------------------|----------|----------|
| Syncing         | "Synchronizing system time"       | Shown during sync | resources.py toastmsg line 134 |
| Sync complete   | "Synchronization successful!"     | Brief    | resources.py toastmsg line 135 |

---

## 10. Ground Truth Checklist

| Property              | Value (Display Mode)       | Value (Edit Mode)          | Source |
|-----------------------|----------------------------|----------------------------|--------|
| Title                 | "Time Settings"            | "Time Settings"            | resources.py line 92 |
| M1 label              | "Edit"                     | "Cancel"                   | 090-Time.png, 090-Time-Select.png |
| M2 label              | "Edit"                     | "Save"                     | 090-Time.png, 090-Time-Select.png |
| Widget type           | InputMethodList            | InputMethodList            | activity_main_strings.txt line 21515 |
| Field count           | 6                          | 6                          | Screenshots show 6 fields |
| Field 0 (Year)        | Read-only display          | Editable, range 1970-2099  | Screenshot + get_max_min |
| Field 1 (Month)       | Read-only display          | Editable, range 01-12      | Screenshot + get_max_min |
| Field 2 (Day)         | Read-only display          | Editable, range 01-31*     | Screenshot + get_max_min |
| Field 3 (Hour)        | Read-only display          | Editable, range 00-23      | Screenshot + get_max_min |
| Field 4 (Minute)      | Read-only display          | Editable, range 00-59      | Screenshot + get_max_min |
| Field 5 (Second)      | Read-only display          | Editable, range 00-59      | Screenshot + get_max_min |
| UP/DOWN               | No action                  | Inc/dec focused field      | Decompiled onKeyEvent |
| LEFT/RIGHT            | No action                  | Prev/next field focus      | Decompiled onKeyEvent |
| OK                    | Enter edit mode            | No action                  | Screenshots confirm mode change |
| PWR                   | Exit to Main Menu          | Cancel + exit to Main Menu | Universal PWR behavior |

*Day range is dynamic based on month/year (leap year aware).

---

## Corrections Applied

1. **No button label errors found**: All button labels verified against screenshots:
   - Display mode: M1="Edit", M2="Edit" confirmed by `time_settings_1.png`, `time_settings_2.png`, `time_settings_10.png`
   - Edit mode: M1="Cancel", M2="Save" confirmed by `time_settings_3.png` through `time_settings_9.png`
   - After sync: Returns to display mode with M1="Edit", M2="Edit" confirmed by `time_settings_sync_1.png` through `time_settings_sync_4.png`
2. **Arrow visibility**: Up arrow (^) confirmed visible on focused field in edit mode across `time_settings_3.png` through `time_settings_9.png`. Arrow position changes as focus moves between fields (Year, Month, Day, Hour, Minute, Second). Only ONE arrow direction visible at a time in screenshots, but both UP and DOWN directions exist conditionally per decompiled code — the single-arrow appearance is a state snapshot, not a limitation.
3. **Sync toast sequence**: Confirmed from screenshots: "Synchronizing system time" (`time_settings_sync_1.png`) followed by "Synchronization successful!" (`time_settings_sync_2.png` through `time_settings_sync_4.png`).
