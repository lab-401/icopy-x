# Time Settings Flow -- Specification & Integration Guide

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task

Build **Phase 1** (flow scenarios validated against original firmware) and **Phase 2** (open-source Python UI layer) for the **Time Settings** flow (`TimeSyncActivity`). This is a pure system UI flow -- **NO PM3 COMMANDS**.

---

## TWO ABSOLUTE LAWS

### LAW 1: NO MIDDLEWARE
TimeSyncActivity is a **date/time editor**. It reads the system clock, lets the user edit 6 fields (YYYY-MM-DD HH:MM:SS), and writes back via `date -s` and `hmi_driver._set_com('TIME:...')`. There are ZERO PM3 commands, ZERO RFID interactions, ZERO middleware modules.

If you find yourself importing `executor`, `scan`, `read`, `write`, or any RFID module -- **STOP. You are violating Law 1.**

Note: The Erase flow is the ONLY justified middleware exception in this project. See `docs/flows/dump_files/ui-integration/README.md` Section 6.3 for why Erase was an exception, and the structure put in place. Time Settings has NO such exception.

### LAW 2: NO CHANGING SCENARIOS (Phase 2)
Once Phase 1 scenarios are built and validated against the original firmware, they become **IMMUTABLE** acceptance criteria for Phase 2. If a scenario fails with `--target=current`, the bug is in YOUR implementation, not in the scenario.

---

## What Phase 1 IS and Phase 2 IS

**Phase 1**: Extract the complete logic tree from the original `.so` binary. Build a scenario for EACH leaf. Validate ALL scenarios pass against `--target=original`.

**Phase 2**: Craft an open-source Python UI that faithfully reproduces the original firmware's behavior. The tests pass as a CONSEQUENCE of correct implementation -- not by reverse-engineering test expectations.

---

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/HOW_TO_BUILD_FLOWS.md` -- **READ FIRST.** Flow scenario methodology, fixture system, trigger patterns.
2. `docs/HOW_TO_INTEGRATE_A_FLOW.md` -- Integration methodology, 4-layer architecture, JSON UI system.
3. `docs/flows/dump_files/README.md` -- **MODEL SPEC.** Shows the complete handover format with ground truth discoveries.
4. `docs/flows/dump_files/ui-integration/README.md` -- **POST-MORTEM.** Critical lessons: QEMU LD_PREFIX symlinks, scan cache native types, per-gate validation, no-middleware rules with Erase exception.
5. `docs/UI_Mapping/14_time_settings/README.md` -- UI specification for Time Settings.
6. Real device screenshots (14 files):
   - `docs/Real_Hardware_Intel/Screenshots/time_settings_1.png` through `time_settings_10.png`
   - `docs/Real_Hardware_Intel/Screenshots/time_settings_sync_1.png` through `time_settings_sync_4.png`

---

## Activity Overview

| Property | Value |
|----------|-------|
| Activity class | `TimeSyncActivity` |
| ACT_NAME | `'time_settings'` |
| Menu position | Index 12 (`GOTO:12`) |
| Binary source | `activity_main.so` (13 methods decompiled) |
| PM3 commands | **NONE** |
| External modules | `hmi_driver._set_com()` (RTC sync, best-effort) |

---

## State Machine (from decompiled binary + real device screenshots)

### State: DISPLAY (initial)
- **Title:** `"Time Settings"` (resources key: `time_sync`)
- **Content:** 6 boxed numeric fields arranged as:
  - Row 1: `YYYY -- MM -- DD` (date with em-dash separators)
  - Row 2: `HH : MM : SS` (time with colon separators)
- **Buttons:** M1="Edit", M2="Edit"
- **Keys:** M1/M2 = enter EDIT mode, PWR = finish()
- **Behavior:** Reads current system time on entry via `time.localtime()`
- **Screenshot:** `time_settings_1.png`, `time_settings_2.png`

### State: EDIT
- **Title:** `"Time Settings"` (unchanged)
- **Content:** Same 6 fields, with `^` cursor indicator below the focused field
- **Buttons:** M1="Cancel", M2="Save"
- **Keys:**
  - UP = increment focused field (wraps max -> min)
  - DOWN = decrement focused field (wraps min -> max)
  - LEFT = move cursor to previous field (wraps)
  - RIGHT = move cursor to next field (wraps)
  - M1/PWR = exit EDIT (discard, re-read system time, return to DISPLAY)
  - M2 = save time (write to system + RTC, show toast, return to DISPLAY)
- **Field order:** year(0), month(1), day(2), hour(3), minute(4), second(5)
- **Field ranges:**
  - year: 2000-2099
  - month: 1-12
  - day: 1-28/29/30/31 (context-dependent on month/year)
  - hour: 0-23
  - minute: 0-59
  - second: 0-59
- **Day clamping:** Changing month/year automatically clamps day to valid max (e.g., Feb 30 -> Feb 28/29)
- **Screenshots:** `time_settings_3.png` through `time_settings_9.png`

### State: SAVING (transient)
- **Toast:** `"Synchronizing system time"` (resources key: `time_syncing`), shown during save
- **Screenshot:** `time_settings_sync_1.png`

### State: SAVED (transient -> DISPLAY)
- **Toast:** `"Synchronization successful!"` (resources key: `time_syncok`)
- **Buttons:** M1="Edit", M2="Edit" (restored)
- **Returns to DISPLAY** after toast auto-dismiss
- **Screenshots:** `time_settings_sync_2.png` through `time_settings_sync_4.png`

---

## Logic Tree (EVERY leaf needs a scenario)

```
TimeSyncActivity
  |
  +-- DISPLAY mode
  |     |-- Shows current date/time fields (YYYY--MM--DD HH:MM:SS)
  |     |-- Title: "Time Settings"
  |     |-- M1="Edit", M2="Edit"
  |     |-- M1 or M2 -> enter EDIT
  |     +-- PWR -> finish()
  |
  +-- EDIT mode
  |     |-- Cursor starts on year (field 0)
  |     |-- M1="Cancel", M2="Save"
  |     |
  |     +-- Navigation
  |     |     |-- RIGHT moves cursor: year->month->day->hour->minute->second->year
  |     |     +-- LEFT moves cursor: year->second->minute->hour->day->month->year
  |     |
  |     +-- Value adjustment
  |     |     |-- UP increments field (wraps at max->min)
  |     |     +-- DOWN decrements field (wraps at min->max)
  |     |
  |     +-- Day clamping
  |     |     +-- Feb 30 -> Feb 28 (non-leap) or Feb 29 (leap)
  |     |
  |     +-- Cancel
  |     |     |-- M1 -> discard, re-read time, return to DISPLAY
  |     |     +-- PWR -> same as M1
  |     |
  |     +-- Save
  |           |-- M2 -> write time, show sync toast, return to DISPLAY
  |           +-- Toast: "Synchronizing system time" then "Synchronization successful!"
  |
  +-- Fixtures: NONE (no PM3 commands)
```

---

## Proposed Scenarios

| # | Scenario | Mode | Validates | Min Triggers |
|---|----------|------|-----------|-------------|
| 1 | `time_display` | Display | Title, buttons M1=Edit/M2=Edit, content has date/time | title:Time Settings, M1:Edit, M2:Edit |
| 2 | `time_pwr_exit` | Display | PWR exits to main menu | title:Time Settings then title:Main Page |
| 3 | `time_enter_edit` | Edit | M1 enters edit, buttons change to Cancel/Save | M1:Cancel, M2:Save |
| 4 | `time_cursor_right` | Edit | RIGHT moves cursor through 6 fields | content with cursor indicator |
| 5 | `time_cursor_left` | Edit | LEFT moves cursor backwards | content with cursor indicator |
| 6 | `time_increment_field` | Edit | UP increments year value | content value changed |
| 7 | `time_decrement_field` | Edit | DOWN decrements value | content value changed |
| 8 | `time_field_wrap_max` | Edit | UP at max wraps to min | content value at min |
| 9 | `time_field_wrap_min` | Edit | DOWN at min wraps to max | content value at max |
| 10 | `time_cancel_edit` | Edit | M1 cancels, returns to DISPLAY with Edit/Edit buttons | M1:Edit, M2:Edit |
| 11 | `time_pwr_cancel` | Edit | PWR cancels edit, returns to DISPLAY | M1:Edit, M2:Edit |
| 12 | `time_save` | Save | M2 saves, shows sync toasts, returns to DISPLAY | toast:Synchronizing, toast:Synchronization, M1:Edit |
| 13 | `time_day_clamp` | Edit | Change month from 31-day to 30-day, day clamps | content day value clamped |

---

## Validation Rules

Each scenario MUST validate at least 2 of these at EACH critical gate:
- **Title** (e.g., `title:Time Settings`)
- **Button text** (e.g., `M1:Edit`, `M2:Save`)
- **Button state** (e.g., `M1_active:true`, `M2_active:true`)
- **Content text** (e.g., date/time values visible)
- **Toast text** (e.g., `toast:Synchronizing system time`)

State count is a SMOKE TEST only, never the primary validation.

---

## Running tests

```bash
# Single scenario
TEST_TARGET=original SCENARIO=time_display FLOW=time_settings \
  bash tests/flows/time_settings/scenarios/time_display/time_display.sh

# Full suite
TEST_TARGET=original bash tests/flows/time_settings/test_time_settings_parallel.sh

# Phase 2: current target
TEST_TARGET=current bash tests/flows/time_settings/test_time_settings_parallel.sh
```

---

## Key files

| File | Purpose |
|------|---------|
| `src/lib/activity_main.py` | TimeSyncActivity (L1689-1997) |
| `src/screens/time_settings.json` | JSON UI state machine |
| `src/lib/resources.py` | String resources: `time_sync`, `time_syncing`, `time_syncok`, `edit`, `cancel`, `save` |

---

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores)
- GOTO index: `GOTO:12` (menu position for Time Settings)
- Fixtures: **NONE** required (no PM3 commands)
