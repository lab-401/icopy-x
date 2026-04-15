# About Flow -- Specification & Integration Guide

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task

Build **Phase 1** (flow scenarios validated against original firmware) and **Phase 2** (open-source Python UI layer) for the **About** flow (`AboutActivity` + `UpdateActivity`). This is a system UI flow -- **NO PM3 TAG COMMANDS**. AboutActivity shows device information across 2 pages. Page 2 allows launching UpdateActivity for firmware installation.

---

## TWO ABSOLUTE LAWS

### LAW 1: NO MIDDLEWARE
AboutActivity is a **device info display + update launcher**. It reads version information from the `version` module and displays it. UpdateActivity reads IPK files from `/mnt/upan/` and installs them. Neither sends PM3 RFID commands.

If you find yourself importing `scan`, `read`, `write`, or sending `hf`/`lf` commands -- **STOP. You are violating Law 1.**

Note: The Erase flow is the ONLY justified middleware exception in this project. See `docs/flows/dump_files/ui-integration/README.md` Section 6.3 for why. About has NO such exception.

### LAW 2: NO CHANGING SCENARIOS (Phase 2)
Once Phase 1 scenarios pass with `--target=original`, they are **IMMUTABLE** for Phase 2.

---

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/HOW_TO_BUILD_FLOWS.md` -- **READ FIRST.** Flow scenario methodology.
2. `docs/HOW_TO_INTEGRATE_A_FLOW.md` -- Integration methodology, JSON UI system.
3. `docs/flows/dump_files/README.md` -- **MODEL SPEC.** Complete handover format.
4. `docs/flows/dump_files/ui-integration/README.md` -- **POST-MORTEM.** QEMU LD_PREFIX, per-gate validation, no-middleware rules.
5. `docs/UI_Mapping/12_about/README.md` -- UI specification for About.
6. Real device screenshots:
   - `docs/Real_Hardware_Intel/Screenshots/about_1_2.png` -- Page 1 (device info)
   - `docs/Real_Hardware_Intel/Screenshots/about_2_2.png` -- Page 2 (update instructions)
   - `docs/Real_Hardware_Intel/Screenshots/about_processing.png` -- Update in progress
7. Decompiled binaries:
   - `decompiled/activity_main_ghidra_raw.txt` -- AboutActivity symbols
   - `decompiled/activity_update_ghidra_raw.txt` -- UpdateActivity symbols (639KB)
   - `decompiled/update_ghidra_raw.txt` -- update.so module (722KB)

---

## Activity Overview

### AboutActivity

| Property | Value |
|----------|-------|
| Activity class | `AboutActivity` |
| ACT_NAME | `'about'` |
| Menu position | Index 10 (`GOTO:10`) |
| Binary source | `activity_main.so` |
| PM3 commands | **NONE** |
| Pages | 2 (Info + Update instructions) |

### UpdateActivity

| Property | Value |
|----------|-------|
| Activity class | `UpdateActivity` |
| Binary source | `activity_update.so` (separate module) |
| PM3 commands | **NONE** |
| External modules | `update.so` (IPK search/verify/install) |

---

## State Machine -- AboutActivity

### Page 1: Device Info (initial)
- **Title:** `"About 1/2"` (resources key: `about`, with page indicator)
- **Content:** 6 lines of device information (BigTextListView):
  ```
      iCopy-XS              (from version.getTYP(), default 'iCopy-X')
  HW  1.7                   (from version.getHW())
  HMI 1.4                   (from version.getHMI())
  OS  1.0.90                (from version.getOS(), first 25 chars)
  PM  3.1                   (from version.getPM())
  SN  02150004              (from version.getSN())
  ```
- **Buttons:** NONE (M1="", M2="")
- **Keys:** DOWN = page 2, M2/OK = launch UpdateActivity, PWR = finish()
- **Screenshot:** `about_1_2.png`

### Page 2: Update Instructions
- **Title:** `"About 2/2"`
- **Content:** 5 lines of firmware update instructions:
  ```
  Firmware update
  1.Download firmware
   icopy-x.com/update
  2.Plug USB, Copy firmware to device.
  3.Press 'OK' start update.
  ```
- **Buttons:** NONE (M1="", M2="")
- **Keys:** UP/M1 = page 1, M2/OK = launch UpdateActivity, PWR = finish()
- **Screenshot:** `about_2_2.png`

### Version Module API

| Method | Returns | Used for |
|--------|---------|----------|
| `version.getTYP()` | Device type string (e.g., "iCopy-XS") | Line 1 |
| `version.getHW()` | Hardware version (e.g., "1.7") | Line 2 |
| `version.getHMI()` | HMI version (e.g., "1.4") | Line 3 |
| `version.getOS()` | OS version (e.g., "1.0.90"), truncated to 25 chars | Line 4 |
| `version.getPM()` | PM3 version (e.g., "3.1") | Line 5 |
| `version.getSN()` | Serial number (e.g., "02150004") | Line 6 |

All calls wrapped in try/except -- missing module returns `'?'` for each field.

---

## State Machine -- UpdateActivity

### State: READY (initial)
- **Title:** `"Update"` (resources key: `update`)
- **Content:** BigTextListView with install instructions (resources key: `start_install_tips`)
- **Buttons:** M1="" (hidden), M2="Start"
- **Keys:** M2/OK = start install, PWR = finish()

### State: INSTALLING
- **Content:** ProgressBar with `"Updating"` message
- **Buttons:** disabled
- **Keys:** ALL ignored
- **Background:** update.so performs: search() -> checkPkg() -> unpkg() -> checkVer() -> install()
- **Progress callback:** `onInstall(name, progress)` updates progressbar

### State: DONE (success)
- **Toast:** `"Update finish."` (resources key: `update_finish`)
- **Keys:** Any key = finish()

### State: DONE (failure)
- **Toast:** `"Install failed, code = {N}"` (resources key: `install_failed`)
- **Keys:** Any key = finish()

### State: NO UPDATE
- **Toast:** `"No update available"` (resources key: `update_unavailable`)
- **Returns to:** AboutActivity (finish())

---

## Logic Tree

```
AboutActivity
  |
  +-- Page 1 (Device Info)
  |     |-- Title: "About 1/2"
  |     |-- 6 version info lines
  |     |-- No buttons visible
  |     |-- DOWN -> Page 2
  |     |-- M2/OK -> UpdateActivity
  |     +-- PWR -> finish()
  |
  +-- Page 2 (Update Instructions)
  |     |-- Title: "About 2/2"
  |     |-- 5 instruction lines
  |     |-- No buttons visible
  |     |-- UP/M1 -> Page 1
  |     |-- M2/OK -> UpdateActivity
  |     +-- PWR -> finish()
  |
  +-- UpdateActivity (sub-activity)
        |
        +-- READY
        |     |-- Title: "Update", M2="Start"
        |     |-- M2/OK -> search for IPK -> INSTALLING
        |     +-- PWR -> finish() (back to About)
        |
        +-- No IPK found
        |     +-- Toast: "No update available" -> finish()
        |
        +-- INSTALLING
        |     |-- ProgressBar + "Updating"
        |     +-- On complete -> DONE
        |
        +-- DONE (success)
        |     +-- Toast: "Update finish." -> any key -> finish()
        |
        +-- DONE (failure)
              +-- Toast: "Install failed, code = {N}" -> any key -> finish()
```

---

## Proposed Scenarios

| # | Scenario | Tests | Min Triggers |
|---|----------|-------|-------------|
| 1 | `about_page1` | Page 1 display: title, version info content | title:About 1/2, content:HW, content:SN |
| 2 | `about_page2` | Page 2 display: title, update instructions | title:About 2/2, content:Firmware update |
| 3 | `about_page_nav` | DOWN goes to page 2, UP returns to page 1 | title:About 1/2 then title:About 2/2 then title:About 1/2 |
| 4 | `about_pwr_exit` | PWR from page 1 exits | title:About then title:Main Page |
| 5 | `about_pwr_exit_page2` | PWR from page 2 exits | title:About 2/2 then finish |
| 6 | `about_no_buttons` | Verify M1/M2 are empty (no button text) | M1:, M2: (empty check) |
| 7 | `about_launch_update` | M2/OK from page 2 launches UpdateActivity | title:Update, M2:Start |
| 8 | `about_update_no_ipk` | UpdateActivity with no IPK file -> "No update available" | toast:No update available |
| 9 | `about_update_pwr_cancel` | PWR from UpdateActivity returns to About | title:Update then title:About |

### IMPORTANT: Update Module Mocking

Under QEMU, `update.so` and `activity_update.so` need fixtures:
- Default: No IPK files found -> "No update available" toast
- For install scenarios: Mock IPK search to return a valid package path

---

## Validation Rules

Each scenario MUST validate at least 2 of:
- **Title** (`title:About 1/2`, `title:About 2/2`, `title:Update`)
- **Page content** (`content:HW`, `content:SN`, `content:Firmware update`, `content:icopy-x.com`)
- **Button text** (empty for About, `M2:Start` for Update)
- **Button state** (active/inactive)
- **Toast text** (`toast:No update available`, `toast:Update finish`)

State count is a SMOKE TEST only.

---

## Running tests

```bash
# Single scenario
TEST_TARGET=original SCENARIO=about_page1 FLOW=about \
  bash tests/flows/about/scenarios/about_page1/about_page1.sh

# Full suite
TEST_TARGET=original bash tests/flows/about/test_about_parallel.sh
```

---

## Key files

| File | Purpose |
|------|---------|
| `src/lib/activity_main.py` | AboutActivity (L469-651), UpdateActivity (L6218-6278) |
| `src/screens/about.json` | JSON UI state machine (to be created) |
| `src/lib/resources.py` | Strings: `about`, `update`, `aboutline1`-`aboutline6`, `aboutline1_update`-`aboutline5_update`, `update_finish`, `update_unavailable`, `install_failed` |

---

## Resource Strings Reference

### About Activity

| Key | Category | Value |
|-----|----------|-------|
| `about` | title | `"About"` |
| `aboutline1` | itemmsg | `"    {}"` (device type) |
| `aboutline2` | itemmsg | `"   HW  {}"` |
| `aboutline3` | itemmsg | `"   HMI {}"` |
| `aboutline4` | itemmsg | `"   OS  {}"` |
| `aboutline5` | itemmsg | `"   PM  {}"` |
| `aboutline6` | itemmsg | `"   SN  {}"` |
| `aboutline1_update` | itemmsg | `"Firmware update"` |
| `aboutline2_update` | itemmsg | `"1.Download firmware"` |
| `aboutline3_update` | itemmsg | `" icopy-x.com/update"` |
| `aboutline4_update` | itemmsg | `"2.Plug USB, Copy firmware to device."` |
| `aboutline5_update` | itemmsg | `"3.Press 'OK' start update."` |

### Update Activity

| Key | Category | Value |
|-----|----------|-------|
| `update` | title | `"Update"` |
| `start` | button | `"Start"` |
| `updating` | toastmsg | `"Updating"` |
| `update_finish` | toastmsg | `"Update finish."` |
| `update_unavailable` | toastmsg | `"No update available"` |
| `install_failed` | toastmsg | `"Install failed, code = {}"` |
| `start_install_tips` | tipsmsg | Install instructions text |

---

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores)
- GOTO index: `GOTO:10` (menu position for About)
- Fixtures: Mock version module for consistent values; mock update.so for install scenarios
