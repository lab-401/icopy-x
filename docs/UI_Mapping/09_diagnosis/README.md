# DiagnosisActivity + 6 Sub-Test Activities — Exhaustive UI Mapping

Source: `activity_tools.so` decompiled via Ghidra (`activity_tools_ghidra_raw.txt`)
String table: `resources.py` StringEN

---

## 1. DiagnosisActivity (activity_tools.so)

### Module Location

Binary: `orig_so/lib/activity_tools.so`
Decompiled: `decompiled/activity_tools_ghidra_raw.txt`

### Class Methods (from binary string table, activity_tools_ghidra_raw.txt lines 340-371)

```
DiagnosisActivity.__init__          @0x00036054  (line 33197)
DiagnosisActivity.getManifest       @0x00032378  (line 29708)
DiagnosisActivity.onCreate          @0x0003a21c  (line 37324)
DiagnosisActivity.onKeyEvent        @0x0003491c  (line 31863)
DiagnosisActivity.onData            @0x0001bc04  (line 8668)
DiagnosisActivity.startTest         @0x0002c4f4  (line 24236)
DiagnosisActivity.updateTitle       @0x0002ba1c  (line 23598)
DiagnosisActivity.setTipsEnable     @0x00032920  (line 30041)
DiagnosisActivity._test_hfvoltage   @0x0001cf48  (line 9776)
DiagnosisActivity._test_lfvoltage   @0x0001ccb8  (line 9624)
DiagnosisActivity._test_hfreader    @0x0001ca28  (line 9472)
DiagnosisActivity._test_lfreader    @0x0001c798  (line 9319)
DiagnosisActivity._test_hf_reader_factory  @0x0002e2bc  (line 25967)
DiagnosisActivity._test_lf_reader_factory  @0x0002e034  (line 25812)
DiagnosisActivity._test_voltage     @0x000305dc  (line 28009)
DiagnosisActivity._test_reader      @0x0002fd80  (line 27549)
DiagnosisActivity._flash_memtest    @0x0002efa0  (line 26743)
DiagnosisActivity._manual_check     @0x0002e7cc  (line 26276)
DiagnosisActivity._button_test      @0x0002e544  (line 26122)
DiagnosisActivity._screen_test      @0x000391c0  (line 36362)
DiagnosisActivity._usb_test         @0x000395ac  (line 36595)
DiagnosisActivity._sound_test       @0x00039e30  (line 37091)
```

### getManifest (line 29708)

Returns a dict with two entries corresponding to module name and class reference.
This follows the standard activity manifest pattern used by `actstack.so`.

```python
# Reconstructed from decompiled (line 29758-30036):
def getManifest():
    return {
        'module': 'activity_tools',
        'class': DiagnosisActivity
    }
```

### State Machine

#### STATE: MAIN (Initial)
- **Title**: "Diagnosis" (resources.py StringEN.title.diagnosis, line 7)
- **View type**: ListView (standard list, NOT CheckedListView)
- **Items**: 2 items, single page
  - Item 0: "User diagnosis" (resources.py StringEN.itemmsg.diagnosis_item1, line 11)
  - Item 1: "Factory diagnosis" (resources.py StringEN.itemmsg.diagnosis_item2, line 11)
- **Footer**: None
- **Navigation**:
  - UP/DOWN: Navigate list cursor
  - OK: Select item, transitions to TEST_LIST state
  - PWR: Exit activity (universal back)

#### STATE: TEST_LIST (After selecting User or Factory)
- **Title**: "Diagnosis" with mode indicator via `updateTitle()` (line 23598)
- **View type**: CheckedListView
  - 9 items across 2 pages (5 items/page, page indicator in title)
  - Each item shows test name on LEFT, pass/fail indicator (filled square) on RIGHT
- **Items** (resources.py StringEN.itemmsg, line 11):

| Index | Resource Key | Display Text |
|-------|-------------|--------------|
| 0 | diagnosis_subitem1 | "HF Voltage  " |
| 1 | diagnosis_subitem2 | "LF Voltage  " |
| 2 | diagnosis_subitem3 | "HF reader   " |
| 3 | diagnosis_subitem4 | "LF reader   " |
| 4 | diagnosis_subitem5 | "Flash Memory" |
| 5 | diagnosis_subitem6 | "USB port    " |
| 6 | diagnosis_subitem7 | "Buttons     " |
| 7 | diagnosis_subitem8 | "Screen      " |
| 8 | diagnosis_subitem9 | "Sound       " |

Note: Items have trailing spaces to right-align in fixed-width display.

- **Footer buttons**:
  - M1: "Cancel" (resources.py StringEN.button.cancel, line 6) -- returns to MAIN state
  - M2: "Start" (resources.py StringEN.button.start, line 6) -- starts selected test

  **Screenshot citation**: `diagnosis_menu_2.png` shows the tips/start screen with M1="Cancel" on left, M2="Start" on right, and text "Press start button to start diagnosis."

- **Navigation**:
  - UP/DOWN: Navigate list cursor, page wraps at 5 items
  - OK: Start test for highlighted item (same as M2)
  - PWR: Return to MAIN state

#### STATE: RESULTS (After tests complete)

- **Title**: "Diagnosis 1/1" (with page indicator, single page if all results fit)
- **View type**: CheckedListView showing test results
- **Content**: Each test result displays as:
  - Test name followed by colon and checkmark with measured value, e.g.:
    - `HF Voltage  : √ (37V)`
    - `LF Voltage  : √ (43V)`
    - `HF reader   : √`
    - `LF reader   : √`
    - `Flash Memory: √`
  - The `√` character indicates a passing result
  - Voltage tests include the measured value in parentheses after the checkmark
  - Non-voltage tests show only the checkmark without a value

**Screenshot citation**: `diagnosis_results_1_1.png` shows title "Diagnosis 1/1" with 5 test results (HF Voltage through Flash Memory), all showing `√` pass indicators. HF Voltage shows `(37V)` and LF Voltage shows `(43V)`.

- **Navigation**:
  - UP/DOWN: Scroll through results
  - PWR: Return to MAIN state

### __init__ (line 33197)

Takes `(self, parent)` as arguments (decompiled line 33240: expects 2 positional args).

Initialization sequence (reconstructed from lines 33314-33796):
1. Calls super().__init__(parent) via `__Pyx_PyObject_Call` on base class
2. Sets up a test list using CheckedListView constructor
3. Initializes test result tracking (9 items, all initially unchecked)
4. Sets up auto_fill callback for populating the checklist
5. Stores reference to resources module for string lookups

### onCreate (line 37324)

Takes `(self)` as single argument (decompiled line 37354: expects 1 positional arg).

Sequence (reconstructed from lines 37407-37697):
1. Calls `self.__init__()` or super().onCreate() (attribute lookup at line 37409)
2. Gets `self.items_act` (attribute at line 37443) -- the test list config
3. Calls `self.items_act.setItems(...)` with the 9 diagnosis subitems
4. Sets up `initList()` with parameters:
   - `title`: "Diagnosis"
   - `tips`: "Press start button to start diagnosis." (start_diagnosis_tips)
   - `items_act`: the CheckedListView
   - `onData`: self.onData callback
5. Returns None on success

### onKeyEvent (line 31863)

Takes `(self, key)` as arguments (decompiled line 31898: expects 2 positional args).

Key handling (reconstructed from lines 31966-32462, multiple RichCompare blocks):

```
Key comparison chain (KEY_OK first, then KEY_PWR, then KEY_UP, then KEY_DOWN):

if key == KEY_OK:           (line 32004, RichCompare at 0x5a4ee)
    if self.is_testing():   (line 32050, attribute check)
        return True         (already testing, ignore)
    else:
        self.startTest()    (line 32077, start test on current item)
        return True

elif key == KEY_PWR:        (line 32150, second RichCompare)
    if self.is_testing():   (line 32198, check running state)
        return True         (block exit during test)
    else:
        self.goBack()       (line 32236-32253, navigate back)
        # If in TEST_LIST -> go to MAIN
        # If in MAIN -> exit activity
        return True

elif key == KEY_UP:         (line 32313, third RichCompare)
    self.list_prev()        (line 32345, move cursor up)
    return True

elif key == KEY_DOWN:       (line 32444, fourth RichCompare)
    self.list_next()        (line 32384, move cursor down)
    return True
```

### startTest (line 24236)

Takes `(self)` as single argument (line 24284: expects 1 positional arg).

This is the central dispatch method. It:
1. Gets the current list selection via `self.items_act.getSelected()` (line 24337-24377)
2. Checks if the selected test is already running (boolean check at line 24396-24411)
3. If not running, gets the test handler:
   - Gets `self.items_act` (line 24472)
   - Gets the test method reference based on selected index
4. Iterates through the test list (lines 24514-24835):
   - For each test item, extracts: [test_name, test_method, status]
   - Item[0] = test display name
   - Item[1] = test callback function
   - Item[2] = status (pass/fail indicator)
5. Calls the appropriate test method
6. Updates the CheckedListView with pass/fail results

### setTipsEnable (line 30041)

Takes `(self, text, enable)` as arguments (line 30083: switch on nargs, up to 3).

Controls the tips text area visibility and content:
1. Gets the `enable` boolean parameter
2. If enable is True, shows the tips text
3. If enable is False, hides the tips text
4. Gets the tips display method and calls it with the text content
5. Sets up button visibility based on enable state

### Test Dispatch Map

Based on the method names in the binary (lines 345-371):

| Test Index | Method | Delegates To |
|-----------|--------|-------------|
| 0: HF Voltage | `_test_hfvoltage` | PM3: `hw tune` (HF voltage measurement) |
| 1: LF Voltage | `_test_lfvoltage` | PM3: `hw tune` (LF voltage measurement) |
| 2: HF reader | `_test_hfreader` | Launches HFReaderTestActivity |
| 3: LF reader | `_test_lfreader` | Launches LfReaderTestActivity |
| 4: Flash Memory | `_flash_memtest` | PM3: `mem info` or similar |
| 5: USB port | `_usb_test` | Launches UsbPortTestActivity |
| 6: Buttons | `_button_test` | Launches ButtonTestActivity |
| 7: Screen | `_screen_test` | Launches ScreenTestActivity |
| 8: Sound | `_sound_test` | Launches SoundTestActivity |

#### User vs Factory Diagnosis

- **User diagnosis** (item 0): Runs tests 0-8, results shown as pass/fail
- **Factory diagnosis** (item 1): Same 9 tests but with factory-specific methods:
  - `_test_hf_reader_factory` @0x0002e2bc (line 25967)
  - `_test_lf_reader_factory` @0x0002e034 (line 25812)
  - Factory methods may use different PM3 commands or pass/fail thresholds

### _test_voltage (line 28009)

Generic voltage test method used by both HF and LF voltage tests.

Inner function `newlines` (line 28785) -- formats multiline voltage output.

Flow:
1. Runs PM3 voltage measurement command
2. Parses voltage value from response
3. Compares against threshold
4. Returns pass/fail result
5. Updates CheckedListView indicator

### _manual_check (line 26276)

Used for tests that require manual user confirmation (Screen, Sound).

Flow:
1. Shows test-specific UI
2. Waits for user to press Pass or Fail button
3. Records result in CheckedListView

---

## 2. ScreenTestActivity (activity_tools.so)

### Class Methods (lines 303-304, 313, 333-335, 364, 373-374)

```
ScreenTestActivity.__init__      @0x0001d350  (line 10081)
ScreenTestActivity.onCreate      @0x00028c68  (line 20930)
ScreenTestActivity.onKeyEvent    @0x0003336c  (line 30661)
ScreenTestActivity.showTips      @0x00029108  (line 21205)
ScreenTestActivity.showBtns      @0x000299e4  (line 21747)
ScreenTestActivity.showBigBg     @0x0003b314  (line 38307)
ScreenTestActivity.resetColorPos @0x0001f154  (line 11719)
```

### UI States

#### STATE: TIPS
- **Title**: "Diagnosis" (inherited)
- **Content**: Tips text area showing:
  "Press 'OK' to start test.\nPress 'OK' again to stop test.\n\n'UP' and 'DOWN' change screen color."
  (resources.py StringEN.tipsmsg.test_screen_tips, line 9)
- **Navigation**:
  - OK: Start screen color test, transition to COLOR_TEST
  - PWR: Exit back to DiagnosisActivity

#### STATE: COLOR_TEST
- **Content**: Full-screen solid color background via `showBigBg()` (line 38307)
- **Color cycling**: `resetColorPos()` (line 11719) resets the color index
- **Navigation**:
  - UP: Previous color
  - DOWN: Next color
  - OK: Stop test, transition to CONFIRMATION
  - PWR: Stop test, transition to CONFIRMATION

#### STATE: CONFIRMATION
- **Content**: Tips text showing:
  "Is the screen OK?"
  (resources.py StringEN.tipsmsg.test_screen_isok_tips, line 9)
- **Footer buttons**:
  - M1: "Pass" (resources.py StringEN.button.pass, line 6)
  - M2: "Fail" (resources.py StringEN.button.fail, line 6)
- **Navigation**:
  - M1: Record Pass, return to DiagnosisActivity with result
  - M2: Record Fail, return to DiagnosisActivity with result
  - PWR: Cancel, return without result

---

## 3. ButtonTestActivity (activity_tools.so)

### Class Methods (lines 314-315, 317-318, 329-332, 388-389)

```
ButtonTestActivity.__init__         @0x0001f734  (line 12063)
ButtonTestActivity.onCreate         @0x000266cc  (line 18509)
ButtonTestActivity.onKeyEvent       @0x000256e8  (line 17555)
ButtonTestActivity.update_btn_state @0x0002026c  (line 12701)
ButtonTestActivity.auto_stop_run    @0x00028418  (line 20454)
```

### UI States

#### STATE: BUTTON_TEST
- **Title**: "Diagnosis" (inherited)
- **Content**: Visual representation of all device buttons
  - Shows button layout on screen
  - Each button has an indicator (unchecked/checked)
  - As user presses each physical button, the corresponding on-screen indicator lights up
- **Required buttons to press**: UP, DOWN, OK, PWR, M1, M2
- **Method**: `update_btn_state()` (line 12701) -- updates the visual state of each button indicator when pressed
- **Auto-stop**: `auto_stop_run()` (line 20454) -- timer-based auto-completion
  - Once all buttons have been pressed, auto-transitions to result
- **Navigation**:
  - Any key: Marks that key as tested via `update_btn_state()`
  - All keys pressed: Auto-pass, returns to DiagnosisActivity
  - Timeout: Auto-fail after period

---

## 4. SoundTestActivity (activity_tools.so)

### Class Methods (lines 336-339)

```
SoundTestActivity.onCreate     @0x0002ad88  (line 22862)
SoundTestActivity.onKeyEvent   @0x0002a0e0  (line 22146)
SoundTestActivity.finish       @0x0002a6dc  (line 22483)
```

### UI States

#### STATE: PLAYING
- **Title**: "Diagnosis" (inherited)
- **Content**: Tips text showing:
  "Do you hear the music?"
  (resources.py StringEN.tipsmsg.test_music_tips, line 9)
- **Audio**: Plays a test tone/music through the device speaker
- **Footer buttons**:
  - M1: "Pass" (resources.py StringEN.button.pass, line 6)
  - M2: "Fail" (resources.py StringEN.button.fail, line 6)
- **Navigation**:
  - M1: Record Pass, call `finish()` (line 22483), return to DiagnosisActivity
  - M2: Record Fail, call `finish()`, return to DiagnosisActivity
  - PWR: Cancel, call `finish()`, return without result

### finish (line 22483)

Stops audio playback and cleans up resources before returning to parent.

---

## 5. HFReaderTestActivity (activity_tools.so)

### Class Methods (lines 293, 297-298, 307-308, 324-325)

```
HFReaderTestActivity.__init__    @0x0001df20  (line 10704)
HFReaderTestActivity.onCreate    @0x00022004  (line 14388)
HFReaderTestActivity.onKeyEvent  @0x0001ba10  (line 8572)
HFReaderTestActivity.showTips    @0x0001c30c  (line 9060)
HFReaderTestActivity.run_check   @0x000227c8  (line 14850)
```

### UI States

#### STATE: TIPS
- **Title**: "Diagnosis" (inherited)
- **Content**: Tips text showing:
  "Please place Tag with 'IC Test'"
  (resources.py StringEN.tipsmsg.test_hf_reader_tips, line 9)
- **Footer buttons**:
  - M1: "Start" (resources.py StringEN.button.start, line 6)
- **Navigation**:
  - M1/OK: Start HF reader test via `run_check()`, transition to TESTING
  - PWR: Exit back to DiagnosisActivity

#### STATE: TESTING
- **Content**: Progress/status display showing test progress
- **Operation**: `run_check()` (line 14850) runs the PM3 HF reader test
  - Sends PM3 command to detect HF tag
  - Parses response for tag detection
  - Reports pass (tag found) or fail (no tag)
- **Navigation**:
  - PWR: Cancel test (if supported)
  - Auto-transition to result on completion

#### STATE: RESULT
- **Content**: Pass/Fail result with `showTips()` (line 9060) updating the display
- **Footer buttons**:
  - M1: "Pass" / M2: "Fail" (manual override if needed)
- **Navigation**:
  - Any key: Return to DiagnosisActivity with result

---

## 6. LfReaderTestActivity (activity_tools.so)

### Class Methods (lines 292, 295-296, 309-310, 320-323, 372, 378, 380)

```
LfReaderTestActivity.__init__    @0x0001e4ec  (line 11011)
LfReaderTestActivity.onCreate    @0x00020af8  (line 13189)
LfReaderTestActivity.onKeyEvent  @0x0001b820  (line 8476)
LfReaderTestActivity.showTips    @0x0001be80  (line 8801)
LfReaderTestActivity.run_check   @0x0003a868  (line 37703)
LfReaderTestActivity.run_watch   @0x00021380  (line 13699)
LfReaderTestActivity.run_watch.onWatchLine  @0x00021ccc  (line 14199)
```

### UI States

#### STATE: TIPS
- **Title**: "Diagnosis" (inherited)
- **Content**: Tips text showing:
  "Please place Tag with 'ID Test'"
  (resources.py StringEN.tipsmsg.test_lf_reader_tips, line 9)
- **Footer buttons**:
  - M1: "Start" (resources.py StringEN.button.start, line 6)
- **Navigation**:
  - M1/OK: Start LF reader test via `run_check()`, transition to TESTING
  - PWR: Exit back to DiagnosisActivity

#### STATE: TESTING
- **Content**: Status display showing LF reader detection progress
- **Operation**: `run_check()` (line 37703) plus `run_watch()` (line 13699)
  - `run_watch()` sets up a line-by-line watcher via `onWatchLine` callback (line 14199)
  - Monitors PM3 output for LF tag detection
  - Reports pass (tag found) or fail (no tag)
- **Navigation**:
  - PWR: Cancel test
  - Auto-transition to result on completion

---

## 7. UsbPortTestActivity (activity_tools.so)

### Class Methods (lines 305-306, 311-312, 316-317, 326-328, 376)

```
UsbPortTestActivity.__init__       @0x0001d918  (line 10386)
UsbPortTestActivity.onCreate       @0x00024008  (line 16236)
UsbPortTestActivity.onKeyEvent     @0x0002351c  (line 15610)
UsbPortTestActivity.showTips       @0x0001eaf8  (line 11330)
UsbPortTestActivity.run_check      @0x000247cc  (line 16698)
UsbPortTestActivity.finishOnResult @0x0001fd94  (line 12403)
```

### UI States

#### STATE: CHARGER_TEST
- **Title**: "Diagnosis" (inherited)
- **Content**: Tips text showing:
  "Please connect to charger."
  (resources.py StringEN.tipsmsg.test_usb_connect_tips, line 9)
- **Operation**: `run_check()` (line 16698) monitors USB port status
- **Footer buttons**:
  - M1: "Pass" (resources.py StringEN.button.pass)
  - M2: "Fail" (resources.py StringEN.button.fail)
- **Navigation**:
  - M1: Record Pass
  - M2: Record Fail
  - PWR: Cancel

#### STATE: USB_SERIAL_TEST
- **Content**: Tips text showing:
  "Does the computer have a USBSerial(Gadget Serial) found?"
  (resources.py StringEN.tipsmsg.test_usb_found_tips, line 9)
- **Footer buttons**:
  - M1: "Pass" (resources.py StringEN.button.pass)
  - M2: "Fail" (resources.py StringEN.button.fail)

#### STATE: OTG_TEST
- **Content**: Tips text showing:
  "1. Connect to OTG tester.\n2. Judge whether the power supply of OTG is normal?"
  (resources.py StringEN.tipsmsg.test_usb_otg_tips, line 9)
- **Footer buttons**:
  - M1: "Pass"
  - M2: "Fail"

### finishOnResult (line 12403)

Called to package the test result and return to DiagnosisActivity.
Passes result code back through the activity stack.

---

## 8. Factory-Only Test Methods

### _test_hf_reader_factory (line 25967)

Factory-specific HF reader test. Launches HFReaderTestActivity with factory
configuration parameters. May use different PM3 commands or pass/fail thresholds.

### _test_lf_reader_factory (line 25812)

Factory-specific LF reader test. Launches LfReaderTestActivity with factory
configuration parameters.

### _flash_memtest (line 26743)

Flash memory test. Runs directly (no sub-activity launch).
- Sends PM3 command for memory diagnostics
- Parses response for pass/fail
- Updates CheckedListView directly

---

## 9. Overall Key Flow Summary

```
Main Menu -> "Diagnosis" (position 8)
  +-- DiagnosisActivity [MAIN]
        |-- "User diagnosis"  -> [TEST_LIST] -> 9 tests with CheckedListView
        +-- "Factory diagnosis" -> [TEST_LIST] -> 9 tests (factory thresholds)

TEST_LIST item selection:
  |-- HF Voltage   -> inline PM3 test (hw tune), result in checklist
  |-- LF Voltage   -> inline PM3 test (hw tune), result in checklist
  |-- HF reader    -> HFReaderTestActivity (place IC tag, run_check)
  |-- LF reader    -> LfReaderTestActivity (place ID tag, run_watch + run_check)
  |-- Flash Memory -> inline PM3 test (mem info), result in checklist
  |-- USB port     -> UsbPortTestActivity (charger/serial/OTG steps)
  |-- Buttons      -> ButtonTestActivity (press all 6 buttons)
  |-- Screen       -> ScreenTestActivity (color cycle + confirmation)
  +-- Sound        -> SoundTestActivity (play music + pass/fail)
```

---

## 10. String Resource Cross-Reference

All strings sourced from `resources.py` StringEN (line references to `tools/qemu_shims/resources.py`):

| Category | Key | Value | resources.py line |
|----------|-----|-------|-------------------|
| title | diagnosis | "Diagnosis" | 7 |
| itemmsg | diagnosis_item1 | "User diagnosis" | 11 |
| itemmsg | diagnosis_item2 | "Factory diagnosis" | 11 |
| itemmsg | diagnosis_subitem1 | "HF Voltage  " | 11 |
| itemmsg | diagnosis_subitem2 | "LF Voltage  " | 11 |
| itemmsg | diagnosis_subitem3 | "HF reader   " | 11 |
| itemmsg | diagnosis_subitem4 | "LF reader   " | 11 |
| itemmsg | diagnosis_subitem5 | "Flash Memory" | 11 |
| itemmsg | diagnosis_subitem6 | "USB port    " | 11 |
| itemmsg | diagnosis_subitem7 | "Buttons     " | 11 |
| itemmsg | diagnosis_subitem8 | "Screen      " | 11 |
| itemmsg | diagnosis_subitem9 | "Sound       " | 11 |
| tipsmsg | start_diagnosis_tips | "Press start button to start diagnosis." | 9 |
| tipsmsg | test_screen_tips | "Press 'OK' to start test.\nPress 'OK' again to stop test.\n\n'UP' and 'DOWN' change screen color." | 9 |
| tipsmsg | test_screen_isok_tips | "Is the screen OK?" | 9 |
| tipsmsg | test_music_tips | "Do you hear the music?" | 9 |
| tipsmsg | test_usb_connect_tips | "Please connect to charger." | 9 |
| tipsmsg | test_usb_found_tips | "Does the computer have a USBSerial(Gadget Serial) found?" | 9 |
| tipsmsg | test_usb_otg_tips | "1. Connect to OTG tester.\n2. Judge whether the power supply of OTG is normal?" | 9 |
| tipsmsg | test_hf_reader_tips | "Please place Tag with 'IC Test'" | 9 |
| tipsmsg | test_lf_reader_tips | "Please place Tag with 'ID Test'" | 9 |
| tipsmsg | testing_with | "Testing with: \n{}" | 9 |
| button | pass | "Pass" | 6 |
| button | fail | "Fail" | 6 |
| button | start | "Start" | 6 |
| button | cancel | "Cancel" | 6 |

---

## Corrections Applied

1. **TEST_LIST footer buttons**: Fixed from M1="Start", M2=(none) to M1="Cancel", M2="Start". Citation: `diagnosis_menu_2.png` clearly shows "Cancel" on left and "Start" on right.
2. **Results display format**: Added RESULTS state documentation showing checkmark characters with measured values (e.g., "HF Voltage : √ (37V)"). Citation: `diagnosis_results_1_1.png`.
3. **Testing state screens**: Screenshots `diagnosis_menu_3.png` through `diagnosis_menu_6.png` confirm "Testing with:" display format for HF Voltage, LF Voltage, LF reader, and Flash Memory tests — no buttons visible during testing.

---

## Key Bindings

### DiagnosisActivity.onKeyEvent (activity_tools_ghidra_raw.txt line 31863)

Three states: ITEMS_MAIN (top-level), ITEMS_TEST (sub-test list), TESTING (running).

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| ITEMS_MAIN | no-op | no-op | no-op | no-op | show TEST_LIST | no-op | show TEST_LIST | finish() |
| ITEMS_TEST | prev() | next() | no-op | no-op | startTest() | no-op | startTest() | back to MAIN |
| RESULTS | prev() | next() | no-op | no-op | startTest() | no-op | startTest() | back to MAIN |
| TESTING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | cancel test |

### Sub-Activity Key Bindings

#### ScreenTestActivity (activity_tools_ghidra_raw.txt line 30661)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TIPS | no-op | no-op | no-op | no-op | start color cycle | Fail | Pass | Fail + exit |
| COLOR_CYCLE | prevColor() | nextColor() | no-op | no-op | nextColor (or end) | Fail | Pass | Fail + exit |

#### ButtonTestActivity (activity_tools_ghidra_raw.txt line 17555)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TESTING | record UP | record DOWN | record LEFT | record RIGHT | record OK | record M1 | record M2 | record PWR |

All 8 buttons must be pressed within 30s timeout. When all pressed: auto-Pass. Timeout: auto-Fail. Note: PWR IS recorded (unlike other activities where PWR exits).

#### SoundTestActivity (activity_tools_ghidra_raw.txt line 22146)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LISTEN | no-op | no-op | no-op | no-op | no-op | Fail | Pass | Fail + exit |

#### HFReaderTestActivity / LfReaderTestActivity (activity_tools_ghidra_raw.txt lines 8572, 8476)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TIPS | no-op | no-op | no-op | no-op | run_check() | no-op | run_check() | Fail + exit |

#### UsbPortTestActivity (activity_tools_ghidra_raw.txt line 15610)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TIPS | no-op | no-op | no-op | no-op | run_check() | no-op | run_check() | Fail + exit |

**Source:** `src/lib/activity_tools.py` lines 189-236 (DiagnosisActivity), 511-547 (ScreenTest), 644-656 (ButtonTest), 766-773 (SoundTest), 825-830 (HF/LF Reader), 1022-1027 (USB).
