# UI Mapping Audit -- Group 1

Auditor: Adversarial Audit Process
Date: 2026-03-31
Evidence: Real device screenshots from `/docs/Real_Hardware_Intel/Screenshots/`

---

## 1. Main Menu (`01_main_menu/README.md`)

### CONFIRMED

- **Title format**: "Main Page N/M" -- confirmed by all 6 screenshots (e.g., `main_page_1_3_1.png` shows "Main Page 1/3", `main_page_3_3_4.png` shows "Main Page 3/3").
- **Total pages**: 3 -- confirmed ("1/3", "2/3", "3/3" all visible).
- **Items per page**: 5 on pages 1 and 2, 4 on page 3 -- confirmed.
- **Total items**: 14 -- confirmed (5 + 5 + 4).
- **Button labels**: NONE -- confirmed. No text appears in the bottom bar area on any screenshot. All 6 screenshots show an empty bottom region.
- **Page 1 items (order)**: Auto Copy, Dump Files, Scan Tag, Read Tag, Sniff TRF -- confirmed by `main_page_1_3_1.png` and `main_page_1_3_5.png`.
- **Page 3 items (order)**: About, Erase Tag, Time Settings, LUA Script -- confirmed by `main_page_3_3_1.png` and `main_page_3_3_4.png`.
- **Selection highlight**: Dark rectangle highlight on the selected item -- confirmed. In `main_page_1_3_1.png` "Auto Copy" is highlighted (pos 1), in `main_page_1_3_5.png` "Sniff TRF" is highlighted (pos 5), etc.
- **"Write Tag" NOT in main menu**: Confirmed. No screenshot shows "Write Tag" anywhere. The doc lists it at position 5 on page 2, but the real device shows "Simulation" at position 1 on page 2 instead.
- **Page indicator**: Embedded in the title string (not a separate widget) -- confirmed by screenshots.
- **Battery icon**: Present in the title bar on the right side in all screenshots.

### ERRORS

1. **Page 2 items are WRONG -- "Write Tag" does NOT exist on the real device main menu.**

   Doc claims page 2 order: Write Tag, Simulation, PC-Mode, Backlight, Volume

   Real device (`main_page_2_3_1.png` and `main_page_2_3_5.png`) shows page 2 order: **Simulation, PC-Mode, Diagnosis, Backlight, Volume**

   Evidence: `main_page_2_3_1.png` -- position 1 on page 2 is "Simulation" (highlighted). `main_page_2_3_5.png` -- position 5 is "Volume" (highlighted). Between them: PC-Mode, Diagnosis, Backlight.

   Two errors here:
   - **"Write Tag" (position 5) does not appear at all.** It is not on any page of the main menu in these screenshots.
   - **"Diagnosis" appears at position 7 (page 2, slot 3)** but the doc does NOT list Diagnosis in the main menu item table at all. Diagnosis exists only in the title strings table (line 100 of the doc: `'diagnosis': 'Diagnosis'`) but is missing from the "Complete Item List" table.

2. **Total item count is WRONG (or at least the enumeration is wrong).**

   The doc claims 14 items. With "Write Tag" removed and "Diagnosis" added, the count stays at 14, but the item at position 5 is wrong. The actual positions are:

   | Position | Actual Item    | Doc Claims     | Status |
   |----------|---------------|----------------|--------|
   | 0        | Auto Copy     | Auto Copy      | OK     |
   | 1        | Dump Files    | Dump Files     | OK     |
   | 2        | Scan Tag      | Scan Tag       | OK     |
   | 3        | Read Tag      | Read Tag       | OK     |
   | 4        | Sniff TRF     | Sniff TRF      | OK     |
   | 5        | Simulation    | Write Tag      | WRONG  |
   | 6        | PC-Mode       | Simulation     | WRONG  |
   | 7        | Diagnosis     | PC-Mode        | WRONG  |
   | 8        | Backlight     | Backlight      | OK     |
   | 9        | Volume        | Volume         | OK     |
   | 10       | About         | About          | OK     |
   | 11       | Erase Tag     | Erase Tag      | OK     |
   | 12       | Time Settings | Time Settings  | OK     |
   | 13       | LUA Script    | LUA Script     | OK     |

   NOTE: This particular real device may be an iCopy-XS which lacks "Write Tag" (write is done via AutoCopy flows), and includes "Diagnosis" instead. However, the doc claims to map the real device and is wrong about what that device shows.

### CORRECTIONS NEEDED

1. Remove "Write Tag" (position 5) from the Complete Item List table, or note it is absent on iCopy-XS hardware.
2. Add "Diagnosis" at position 7 (page 2, slot 3) with source activity class `DiagnosisActivity`.
3. Correct page 2 item order to: Simulation, PC-Mode, Diagnosis, Backlight, Volume.
4. Update positions 5-7: Simulation=5, PC-Mode=6, Diagnosis=7.
5. Update the citations section for Page 2 -- it was listed as "(inferred)" and the inference was wrong.

---

## 2. Backlight (`10_backlight/README.md`)

### CONFIRMED

- **Title**: "Backlight" -- confirmed by all 5 screenshots (`backlight_1.png` through `backlight_5.png`).
- **Item count**: 3 items -- confirmed (Low, Middle, High visible in all screenshots).
- **Item order**: Low (index 0), Middle (index 1), High (index 2) -- confirmed.
- **Item text**: "Low", "Middle", "High" -- confirmed exactly.
- **Check indicator position**: RIGHT side of each item -- confirmed. All screenshots show square indicators on the right edge.
- **Button labels**: NONE -- confirmed. No M1/M2 text appears in the bottom bar area in any screenshot.
- **Widget type**: CheckedListView -- confirmed by visual presence of check squares.
- **Battery icon**: Present in title bar, right side.
- **Selection behavior**: The highlight (darker background row) moves independently of the check indicator. E.g., `backlight_2.png` shows Middle highlighted but High checked; `backlight_3.png` shows Middle highlighted AND checked.

### ERRORS

1. **Check indicator shape is WRONG.**

   Doc claims: "filled square" (Section 1 layout: "Check indicator: filled square", Ground Truth table: "Filled square, RIGHT side").

   Real device shows: The check indicator is a **square outline** (unfilled box) when unchecked, and a **blue square outline** (slightly larger/bolder blue border, still an outline -- NOT a filled/solid square) when checked.

   Evidence:
   - `backlight_1.png`: High is checked -- shows a blue-bordered square outline on the right. Low and Middle show gray square outlines (unchecked).
   - `backlight_5.png`: Low is checked -- same blue-bordered square outline pattern.
   - `backlight_3.png`: Middle is checked -- blue square outline.

   The checked indicator is NOT a "filled square." It is a square outline whose border turns blue when checked.

2. **Layout diagram shows wrong indicator style.**

   Doc diagram shows `[X]` for checked and `[  ]` for unchecked. The real device does NOT show an X or fill. It shows a blue border vs. gray border on the square outline.

### CORRECTIONS NEEDED

1. Change "Check indicator: filled square" to "Check indicator: square outline (gray when unchecked, blue border when checked)".
2. Update the layout diagram to reflect the outline style rather than `[X]`.
3. Update Ground Truth table row "Check indicator" from "Filled square, RIGHT side" to "Square outline (blue border when checked), RIGHT side".

---

## 3. Volume (`11_volume/README.md`)

### CONFIRMED

- **Title**: "Volume" -- confirmed by all 6 screenshots (`volume_1.png` through `volume_6.png`).
- **Item count**: 4 items -- confirmed (Off, Low, Middle, High).
- **Item order**: Off (index 0), Low (index 1), Middle (index 2), High (index 3) -- confirmed.
- **Item text**: "Off", "Low", "Middle", "High" -- confirmed exactly.
- **Check indicator position**: RIGHT side -- confirmed. All screenshots show square indicators on the right edge.
- **Button labels**: NONE -- confirmed. No button text visible in any screenshot.
- **Battery icon**: Present in title bar, right side.
- **Selection/check behavior**: Identical to Backlight -- highlight bar and check indicator are independent. E.g., `volume_3.png` shows Low highlighted but Middle checked.

### ERRORS

1. **Check indicator shape is WRONG (same error as Backlight).**

   Doc claims: "filled square" (Section 1 layout: "Check indicator: filled square", Ground Truth table: "Filled square, RIGHT side").

   Real device shows: Square outline, gray when unchecked, blue border when checked -- identical to Backlight.

   Evidence:
   - `volume_1.png`: High is checked -- blue-bordered square outline.
   - `volume_6.png`: Off is checked -- blue-bordered square outline.
   - `volume_4.png`: Low is checked -- blue-bordered square outline. Middle and High show gray outlines.

2. **Layout diagram shows wrong indicator style.**

   Doc diagram shows `[X]` for checked. Real device shows blue-bordered outline, not filled/X.

### CORRECTIONS NEEDED

1. Change "Check indicator: filled square" to "Check indicator: square outline (gray when unchecked, blue border when checked)".
2. Update the layout diagram to reflect the outline style rather than `[X]`.
3. Update Ground Truth table row "Check indicator" from "Filled square, RIGHT side" to "Square outline (blue border when checked), RIGHT side".

---

## 4. PC-Mode (`08_pcmode/README.md`)

### CONFIRMED

- **Title**: "PC-Mode" -- confirmed by `pc_mode.png`.
- **M1 button label**: "Start" -- confirmed. Left side of bottom bar shows "Start".
- **M2 button label**: "Start" -- confirmed. Right side of bottom bar shows "Start".
- **Both buttons say "Start"**: Confirmed. `pc_mode.png` clearly shows "Start" on both left and right.
- **Instruction text**: "Please connect to the computer.Then press start button" -- confirmed by `pc_mode.png`. The text is displayed as a multi-line block in the content area.
- **Battery icon**: Present in title bar, right side.
- **IDLE state layout**: Matches the doc's description of BigTextListView with connection instructions.

### ERRORS

None found. The PC-Mode document accurately matches the screenshot evidence.

### CORRECTIONS NEEDED

None.

---

## 5. About (`12_about/README.md`)

### CONFIRMED

- **Title**: "About" -- confirmed by `about_processing.png` (shows "About" with no page indicator while processing).
- **Page indicator format**: "About 1/2" and "About 2/2" -- confirmed by `about_1_2.png` and `about_2_2.png`. The superscript-style page numbers are visible.
- **Device name**: "iCopy-XS" -- confirmed by `about_1_2.png` (first content line reads "iCopy-XS").
- **Button labels**: NONE -- confirmed. No M1/M2 text appears in any of the 3 screenshots.
- **Processing state**: Shows "Processing..." toast -- confirmed by `about_processing.png`.
- **Battery icon**: Present in title bar.

### ERRORS

1. **Page count is NOT mentioned in the doc.**

   The doc describes a single-state "INFO_DISPLAY" with 6 items and says "UP/DOWN: No action (list is non-scrollable, fits on one page)." But the real device shows TWO pages: "About 1/2" and "About 2/2". The About screen is paginated.

   Evidence: `about_1_2.png` shows "About 1/2", `about_2_2.png` shows "About 2/2".

2. **The doc says 6 lines fit on one page and there is no scrolling. This is WRONG.**

   The doc states: "UP/DOWN have no effect since the display list fits within a single page (6 items, 5 items/page means it fits on 2 pages but typically no scrolling needed for info display)."

   The doc contradicts itself -- it says 6 items with 5/page means 2 pages, then claims no scrolling is needed. The real device DOES use 2 pages and UP/DOWN or LEFT/RIGHT presumably navigate between them.

   Evidence: `about_1_2.png` (page 1) and `about_2_2.png` (page 2) are clearly two separate pages.

3. **Page 1 content format differs from doc.**

   Doc claims format strings like `"    {}"` with `"    v1.0.90"` as example for line 0.

   Real device `about_1_2.png` shows:
   ```
   iCopy-XS

   HW  1.7
   HMI 1.4
   OS  1.0.90
   PM  3.1
   SN  02150004
   ```

   The first line is "iCopy-XS" (the device name), NOT a version string like "v1.0.90". The doc's aboutline1 example `"    v1.0.90"` does not match -- the real device shows "iCopy-XS" as the first line (which is the device model name, not a firmware version number). The version numbers appear on subsequent lines WITHOUT a "v" prefix (e.g., "HW  1.7" not "HW  v1.3"; "OS  1.0.90" not "OS  5.4.31").

4. **Page 2 content is the update instructions.**

   `about_2_2.png` shows:
   ```
   Firmware update

   1.Download firmware
    icopy-x.com/update
   2.Plug USB, Copy
   firmware to device.
   3.Press 'OK' start
   update.
   ```

   The doc treats this as a separate state ("UPDATE_AVAILABLE") that only appears after firmware update is detected. But the real device shows this as page 2/2 of the About screen -- it is ALWAYS present as the second page, not a conditional state triggered by update detection.

5. **HW version example is wrong.**

   Doc says example: `"   HW  v1.3"`. Real device shows: `"HW  1.7"`. No "v" prefix, different version number, less leading whitespace.

6. **PM version format is wrong.**

   Doc says example: `"   PM  v4.14831"`. Real device shows: `"PM  3.1"`. No "v" prefix, much shorter version string.

### CORRECTIONS NEEDED

1. Add page indicator to the About screen description: title format is "About N/M" with N/M showing current/total pages (2 pages total).
2. Correct the claim that UP/DOWN have no effect -- the screen has 2 pages so navigation keys work.
3. Fix line 0 (aboutline1): the first line shows the device model name (e.g., "iCopy-XS"), not a firmware version.
4. Remove the "v" prefix from all version string examples -- the real device does not show "v" before version numbers.
5. Correct the state machine: page 2 with firmware update instructions is NOT a conditional "UPDATE_AVAILABLE" state -- it is always present as the second page of the About view.
6. Update the example values to match real hardware: HW 1.7, HMI 1.4, OS 1.0.90, PM 3.1, SN 02150004.

---

## 6. Simulation (`07_simulation/README.md`)

### CONFIRMED

- **TYPE_SELECT title format**: "Simulation X/Y" -- confirmed by `simulation_list_1_4.png` which shows "Simulation 1/4".
- **Total pages**: 4 -- confirmed ("1/4" in screenshot).
- **Page 1 items**: M1 S50 1k, M1 S70 4k, Ultralight, Ntag215, FM11RF005SH -- confirmed by `simulation_list_1_4.png`. Items are numbered 1-5.
- **Items per page**: 5 -- confirmed (5 items visible on page 1).
- **SIM_UI title**: "Simulation" (no page indicator) -- confirmed by `simulation_detail_1.png` through `simulation_detail_4.png`.
- **Battery icon**: Present in title bar.
- **UID input field**: Shows "UID: 12345678" for M1 S50 1k type -- confirmed by `simulation_detail_1.png`.
- **Simulation in progress toast**: "Simulation in progress..." -- confirmed by `simulation_in_progress.png`.
- **Type name subtitle**: "M1 S50 1k" shown in blue text above the UID input -- confirmed by all detail screenshots.

### ERRORS

1. **SIM_UI button labels are WRONG.**

   Doc claims:
   - M1: "Edit" (resources.py:62, button key 'edit')
   - M2: "Simulate" (resources.py:43, button key 'simulate')

   Real device shows (all detail screenshots `simulation_detail_1.png` through `simulation_detail_4.png`):
   - M1: **"Stop"**
   - M2: **"Start"**

   Evidence: `simulation_detail_1.png` clearly shows "Stop" on the left and "Start" on the right. This is consistent across all 4 detail screenshots.

2. **SIMULATING state button labels are WRONG.**

   Doc claims:
   - M1: "Stop"
   - M2: "Stop" (both say "Stop")

   Real device (`simulation_in_progress.png`) shows:
   - M1: **"Stop"**
   - M2: **"Start"**

   Evidence: `simulation_in_progress.png` shows "Stop" on the left and "Start" on the right -- the buttons do NOT change to both "Stop" during simulation. They remain "Stop"/"Start".

3. **TYPE_SELECT button labels are WRONG.**

   Doc claims:
   - M1: "" (empty)
   - M2: "Simulate"

   Real device (`simulation_list_1_4.png`) shows: **NO button labels at all.** The bottom bar area is empty/not visible. There is no "Simulate" text on the list view.

4. **TYPE_SELECT list items are NUMBERED on the real device.**

   The doc does not mention item numbering. Real device (`simulation_list_1_4.png`) shows:
   ```
   1. M1 S50 1k
   2. M1 S70 4k
   3. Ultralight
   4. Ntag215
   5. FM11RF005SH
   ```

   Each item has a number prefix ("1.", "2.", etc.). The doc does not document this numbering.

### CORRECTIONS NEEDED

1. Fix SIM_UI button labels: M1="Stop", M2="Start" (not "Edit"/"Simulate").
2. Fix SIMULATING state button labels: M1="Stop", M2="Start" (not "Stop"/"Stop").
3. Fix TYPE_SELECT button labels: both M1 and M2 are empty/none (not M2="Simulate").
4. Document that TYPE_SELECT list items have numeric prefixes ("1.", "2.", etc.).
5. Re-evaluate the state machine: the button labels "Stop"/"Start" in SIM_UI suggest M1 triggers stopSim and M2 triggers startSim, NOT M1=Edit toggle.

---

## Summary of All Errors Found

| Document | Error Count | Severity |
|----------|-------------|----------|
| Main Menu | 2 major | HIGH -- Wrong items on page 2 (Write Tag absent, Diagnosis missing) |
| Backlight | 1 | MEDIUM -- Check indicator shape wrong (outline not filled) |
| Volume | 1 | MEDIUM -- Check indicator shape wrong (same as Backlight) |
| PC-Mode | 0 | CLEAN |
| About | 6 | HIGH -- Page count wrong, state model wrong, version format wrong |
| Simulation | 4 | HIGH -- All three states have wrong button labels |

Total errors found: **14**
