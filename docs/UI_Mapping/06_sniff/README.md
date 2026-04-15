# SniffActivity, SniffForSpecificTag, SniffForMfReadActivity, SniffForT5XReadActivity UI Mapping

Source: `activity_main.so` (SniffActivity + subclasses), `sniff.so` (sniff functions)
Binary: `activity_main.so` MD5=809b40ad17ff8d6947e87452e974f41c
Binary: `sniff.so` MD5=80a77ffe53d5037cc7554c5ff82bf416

## Class Hierarchy

```
BaseActivity
  └── SniffActivity
        └── SniffForSpecificTag
              ├── SniffForMfReadActivity
              └── SniffForT5XReadActivity
```
(V1090_MODULE_AUDIT.txt:1988, 2038, 2090, 2142)

---

# 1. SniffActivity (Main Sniff)

## Activity Registration (getManifest)

`SniffActivity.getManifest()` builds a dict with:
- title key: `sniff_tag` -> "Sniff TRF" (resources.py:77, StringEN.title)
- Associated with `SniffActivity` class and a list view constructor

(decompiled/activity_main_ghidra_raw.txt:33670-33988, `__pyx_pw_13activity_main_13SniffActivity_1getManifest @0x00050830`)

## Methods (from V1090_MODULE_AUDIT.txt:1988-2037)

| Method | Purpose |
|--------|---------|
| `__init__(self, canvas)` | Initialize 14+ attributes to None/default |
| `getManifest()` | Return manifest dict (title, class, listview) |
| `onCreate(self)` | Setup UI: title bar, sniff type ListView |
| `onKeyEvent(self, event)` | Handle KEY_OK, KEY_PWR, M1, M2, UP, DOWN |
| `onData(self, bundle)` | Receive sniff data from PM3; update display |
| `setupOnTypeSelected(self)` | Configure UI for selected sniff type (instructions/buttons) |
| `startSniff(self)` | Begin sniffing via sniff.so function |
| `stopSniff(self)` | Stop current sniff |
| `showHfResult(self)` | Display HF sniff results (14A/14B/iClass/Topaz) |
| `showT5577Result(self)` | Display T5577 LF sniff results |
| `showTracelen4Text(self, tracelen, xy)` | Show "TraceLen: {}" text on screen |
| `dismissTracelenText(self)` | Remove tracelen text |
| `showItems(self, items)` | Display items in console/list view |
| `decode_Line(self, line)` | Decode a single trace line |
| `saveSniffData(self)` | Save trace data to file |
| `hideAll(self)` | Hide all UI elements |
| `play_select_tips(self)` | Play audio tip when selecting type |
| `onTopPIOnlyUpdate(self, page_max, page_new)` | Update page indicator (top only) |
| `onMultiPIUpdate(self, page_max, page_new)` | Update page indicator (multi-line) |
| `nextIfShowing(self, lv)` | Scroll ListView forward if showing |
| `prevIfShowing(self, lv)` | Scroll ListView backward if showing |

## SniffActivity __init__ Attributes

From decompiled/activity_main_ghidra_raw.txt:9092-9530 (`__pyx_pw_13activity_main_13SniffActivity_3__init__ @0x00034f8c`):

The __init__ calls parent `__init__`, then sets ~15 attributes to None via sequential `PyObject_SetAttr` calls (lines 9266-9456). These include:
- Sniff state flags (running, stopped)
- ListView reference
- Button references
- Trace data buffer
- Sniff type selection
- Result display widgets
- Console text view
- Tracelen text widget

The method also initializes a numeric attribute to a constant (line 9334, likely an integer `0` for sniff type index) and a string attribute (line 9432-9440, likely sniff type command).

## State Machine

### State: TYPE_SELECT (Sniff Type Selection)

**Title bar:** "Sniff TRF 1/1" (resources.py:77 `title.sniff_tag` with page indicator appended)

**Screenshot citation**: `sniff_trf_list_1_1.png` shows title "Sniff TRF 1/1" with 5 items, no buttons visible.

**Content:** ListView with 5 sniff types, exactly 1 page (no pagination needed):

| Index | Resource Key | Display Text |
|-------|-------------|--------------|
| 1 | `itemmsg.sniff_item1` | "1. 14A Sniff" |
| 2 | `itemmsg.sniff_item2` | "2. 14B Sniff" |
| 3 | `itemmsg.sniff_item3` | "3. iclass Sniff" |
| 4 | `itemmsg.sniff_item4` | "4. Topaz Sniff" |
| 5 | `itemmsg.sniff_item5` | "5. T5577 Sniff" |

(resources.py:232-236)

**Buttons:** Both buttons dismissed (hidden) in TYPE_SELECT.

**Key handling in TYPE_SELECT:**
- KEY_UP: Move selection up in list
- KEY_DOWN: Move selection down in list
- KEY_OK: Select highlighted sniff type -> transition to INSTRUCTION state via `setupOnTypeSelected()`
- KEY_PWR: Exit activity (finish)

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: ListView visual style, highlight color, font size]

### State: INSTRUCTION (Step-by-Step Instructions)

**Transition:** User presses OK on a sniff type -> `setupOnTypeSelected()` is called.

(decompiled/activity_main_ghidra_raw.txt:613, `__pyx_pw_13activity_main_13SniffActivity_25setupOnTypeSelected @0x000cd874`)

**Title bar:** "Sniff TRF N/4" — includes page indicator showing current step out of 4 total instruction pages.

**Screenshot citations**:
- `sniff_trf_1_4_1.png`: Title shows "Sniff TRF 1/4" with Step 1 instructions
- `sniff_trf_2_4.png`: Title shows "Sniff TRF 2/4" with Step 2 instructions
- `sniff_trf_3_4.png`: Title shows "Sniff TRF 3/4" with Step 3 instructions
- `sniff_trf_4_4.png`: Title shows "Sniff TRF 4/4" with Step 4 instructions

**Buttons in INSTRUCTION (all pages):**
- Left button (M1): `button.start` -> "Start" (resources.py:37)
- Right button (M2): `button.finish` -> "Finish" (resources.py:44)

**Content varies by sniff type:**

**For 14A / 14B / iClass / Topaz (items 1-4):**

4-step instruction sequence displayed across 4 pages (one step per page, navigated with UP/DOWN):

| Step | Resource Key | Text |
|------|-------------|------|
| Step 1 | `itemmsg.sniffline1` | "Step 1: \nPrepare client's \nreader and tag, \nclick start." |
| Step 2 | `itemmsg.sniffline2` | "Step 2: \nRemove antenna cover \non iCopy and place \niCopy on reader." |
| Step 3 | `itemmsg.sniffline3` | "Step 3: \nSwipe tag on iCopy \nto ensure reader \nable to identify tag." |
| Step 4 | `itemmsg.sniffline4` | "Step 4: \nRepeat 3-5 times \nand click finish." |

(resources.py:227-230)

**For T5577 (item 5):**

Single instruction block:

| Resource Key | Text |
|-------------|------|
| `itemmsg.sniffline_t5577` | "Click start, then\nswipe iCopy on reader.\nUntil you get keys." |

(resources.py:231)

**Key handling in INSTRUCTION:**
- M1 (Left button / Start): Begin sniffing -> transition to SNIFFING
- M2 (Right button / Finish): [NEEDS VERIFICATION] — may stop/complete or navigate
- KEY_PWR: Go back to TYPE_SELECT
- KEY_UP / KEY_DOWN: Navigate between instruction pages (1/4 through 4/4)

### State: SNIFFING (In Progress)

**Transition:** User presses Start (M1) in INSTRUCTION state.

**Mechanism:**
1. `startSniff(self)` is called (decompiled/activity_main_ghidra_raw.txt:625, `__pyx_pw_13activity_main_13SniffActivity_11startSniff @0x000cdb54`)
2. Invokes the appropriate `sniff.so` function based on selected type

**sniff.so PM3 commands per type:**

| Sniff Type | sniff.so Function | PM3 Command |
|-----------|------------------|-------------|
| 14A Sniff | `sniff14AStart` | `hf 14a sniff` |
| 14B Sniff | `sniff14BStart` | (implied `hf 14b sniff` -- not in string table) |
| iClass Sniff | `sniffIClassAStart` | `hf iclass sniff` |
| Topaz Sniff | `sniffTopazStart` | `hf topaz sniff` |
| T5577 Sniff | `sniff125KStart` | `lf sniff` |

(sniff_ghidra_raw.txt:283-289, 312-330)

**Note on 14B:** The sniff.so string table contains `hf 14a sniff` (STR@0x0001c340), `hf iclass sniff` (STR@0x0001c2a0), `hf topaz sniff` (STR@0x0001c2e0), and `lf sniff` (STR@0x0001c3c0), but `hf 14b sniff` is NOT found. The `sniff14BStart` function (STR@0x0001bf74) exists but its PM3 command string is not visible in the string dump. It likely uses `hf 14b sniff` but this is [UNRESOLVED -- command string not found in binary].

**Toast during sniffing:** `toastmsg.sniffing` -> "Sniffing in progress..." (resources.py:113)

**Trace length regex:** `trace len = (\d+)` (sniff_ghidra_raw.txt:324, STR@0x0001c370)
Referenced as `PATTERN_TRACE_LEN` (sniff_ghidra_raw.txt:307, STR@0x0001c228).

**Title bar:** "Sniff TRF N/4" (unchanged from INSTRUCTION state — retains current page indicator)

**Content:**
- Instruction text remains visible behind the toast overlay
- "Sniffing in progress..." toast appears overlaid on the instruction text
- For T5577: waiting for LF sniff to complete

**Screenshot citation**: `sniff_trf_sniffing.png` shows title "Sniff TRF 1/4" with Step 1 text visible behind the "Sniffing in progress..." toast.

**Buttons during SNIFFING (HF types 1-4):**
- Left button (M1): remains `button.start` -> "Start" (resources.py:37) — does NOT change to "Stop"
- Right button (M2): `button.finish` -> "Finish" (resources.py:44)

**Screenshot citation**: `sniff_trf_sniffing.png` shows M1="Start" on left, M2="Finish" on right, with "Sniffing in progress..." toast overlay on Step 1 instructions. Title shows "Sniff TRF 1/4".

**Buttons during SNIFFING (T5577, type 5):**
- Buttons vary based on sniff state

**Key handling in SNIFFING:**
- M1 (Left button / Start): [NEEDS VERIFICATION] — may restart or be inactive during sniff
- M2 (Right button / Finish): Stop sniffing -> transition to RESULT
- KEY_PWR: Abort sniff and go back to TYPE_SELECT

### State: RESULT (Trace Data / Console View)

**Transition:** Sniff completes or user presses Finish/Stop.

**onData callback:** `SniffActivity.onData(self, bundle)` (decompiled/activity_main_ghidra_raw.txt:13282-13722, `@0x00039ac0`)

The `onData` method:
1. Extracts data from bundle dict (keys at indices 0 and 1)
2. Calls attribute methods to update UI display
3. Checks a boolean flag to determine if data should trigger `showResult`

**HF Result display (`showHfResult`):**
- Trace data displayed in console/text view
- Shows decoded trace lines via `decode_Line(self, line)` (decompiled/activity_main_ghidra_raw.txt:603, `@0x000cd620`)
- TraceLenText shown via `showTracelen4Text(self, tracelen, xy=(120, 68))` (decompiled/activity_main_ghidra_raw.txt:33009-33668, `@0x0004fc20`)
- Sniff decode progress: `itemmsg.sniff_decode` -> "Decoding...\n{}/{}" (resources.py:237)
- Trace length display: `itemmsg.sniff_trace` -> "TraceLen: {}" (resources.py:238)

**T5577 Result display (`showT5577Result`):**
- Toast: `toastmsg.t5577_sniff_finished` -> "T5577 Sniff Finished" (resources.py:114)
- Key data extracted and displayed

**Buttons in RESULT:**
- Left button (M1): `button.start` -> "Start" (resources.py:37)
- Right button (M2): `button.save_log` -> "Save" (resources.py:59)

**Screenshot citation**: `sniff_trf_1_4_2.png` shows M1="Start" on left, M2="Save" on right, with "TraceLen: 0" display.

**Key handling in RESULT:**
- M1 (Left button / Start): Restart sniffing
- M2 (Right button / Save): Save trace data -> `saveSniffData()`
- KEY_PWR: Go back to TYPE_SELECT
- KEY_UP / KEY_DOWN: Scroll result list/console via `nextIfShowing`/`prevIfShowing`

**Toast after save:** `toastmsg.trace_saved` -> "Trace file\nsaved" (resources.py:112)
**Toast loading:** `toastmsg.trace_loading` -> "Trace\nLoading..." (resources.py:124)

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: console view layout, trace data formatting, scroll behavior]

## Key Event Flow (onKeyEvent)

`SniffActivity.onKeyEvent(self, event)` (decompiled/activity_main_ghidra_raw.txt:30949-33007, `__pyx_pw_13activity_main_13SniffActivity_37onKeyEvent @0x0004d810`)

This is a complex function (~2000 lines of decompiled code). The key event handler:

1. Receives `(self, event)` with 2 positional args (line 30986: `iVar7 != 2`)
2. Compares key code against multiple constants using `PyObject_RichCompare` (line 31091)
3. First comparison at line 31053: checks if key == KEY_PWR (the universal back key)
   - If KEY_PWR is pressed while sniffing is active (`isSniffing` check at line 31129-31161):
     - Calls `stopSniff()` to abort
   - If KEY_PWR pressed in non-sniffing state:
     - Checks if showing results (`isShowing` at line 31162-31170)
     - If showing results: calls `hideAll()` and returns to type list
     - Otherwise: calls `finish()` to exit activity
4. Second comparison at line 31304: checks if key == KEY_OK
   - In TYPE_SELECT: selects current item
   - In other states: context-dependent
5. Additional key comparisons for M1, M2, UP, DOWN following the chain

(decompiled/activity_main_ghidra_raw.txt:30949-33007)

## sniff.so Module API

### Exported Functions (sniff_ghidra_raw.txt:283-300)

| Function | Cython Name | Purpose |
|----------|-------------|---------|
| `sniff14AStart` | `__pyx_pw_5sniff_1sniff14AStart` | Start 14A sniff |
| `sniff14BStart` | `__pyx_pw_5sniff_3sniff14BStart` | Start 14B sniff |
| `sniffIClassAStart` | `__pyx_pw_5sniff_5sniffIClassAStart` | Start iClass sniff |
| `sniffTopazStart` | `__pyx_pw_5sniff_7sniffTopazStart` | Start Topaz sniff |
| `sniff125KStart` | `__pyx_pw_5sniff_9sniff125KStart` | Start 125K (T5577) sniff |
| `parserTraceLen` | `__pyx_pw_5sniff_11parserTraceLen` | Parse trace length from output |
| `parserKeyForLine` | `__pyx_pw_5sniff_13parserKeyForLine` | Parse key from trace line |
| `parserDataForSCA` | `__pyx_pw_5sniff_15parserDataForSCA` | Parse data for SCA |
| `parserUidForData` | `__pyx_pw_5sniff_17parserUidForData` | Parse UID from data |
| `parserUidForKeyIndex` | `__pyx_pw_5sniff_19parserUidForKeyIndex` | Parse UID for key index |
| `parserKeyForM1` | `__pyx_pw_5sniff_21parserKeyForM1` | Parse key for MIFARE 1K |

### Key String Constants in sniff.so

| String | Address | Purpose |
|--------|---------|---------|
| `hf 14a sniff` | STR@0x0001c340 | PM3 command for 14A sniff |
| `hf iclass sniff` | STR@0x0001c2a0 | PM3 command for iClass sniff |
| `hf topaz sniff` | STR@0x0001c2e0 | PM3 command for Topaz sniff |
| `lf sniff` | STR@0x0001c3c0 | PM3 command for LF/T5577 sniff |
| `trace len = (\d+)` | STR@0x0001c370 | Regex for trace length parsing |
| `PATTERN_TRACE_LEN` | STR@0x0001c228 | Constant name for regex |

### Parser Functions Detail

**`parserTraceLen`** (sniff_ghidra_raw.txt:285):
Uses regex `trace len = (\d+)` to extract numeric trace length from PM3 output.

**`parserKeyForLine`** (sniff_ghidra_raw.txt:290, function at @0x00016a1c):
Extracts key bytes from a sniff trace line. Used for HF sniff result decoding.

**`parserDataForSCA`** (sniff_ghidra_raw.txt:292, function at @0x0001704c):
Parses data specific to SCA (Side Channel Analysis) from trace.

**`parserUidForData`** (sniff_ghidra_raw.txt:294, function at @0x00017d50):
Extracts UID from raw sniff data.

**`parserKeyForM1`** (sniff_ghidra_raw.txt:296):
Specifically parses MIFARE Classic 1K keys from sniff data — used by SniffForMfReadActivity.

**`parserUidForKeyIndex`** (sniff_ghidra_raw.txt:299):
Maps UID to key index in the key table.

---

# 2. SniffForSpecificTag (Directed Sniff Base)

## Class Purpose

`SniffForSpecificTag` extends `SniffActivity` for directed/targeted sniffing — when the caller already knows which sniff type to use (e.g., coming from a Read flow's "missing keys" option).

(V1090_MODULE_AUDIT.txt:2090)

## Differences from SniffActivity

- **Skips TYPE_SELECT state:** Goes directly to INSTRUCTION for the pre-selected sniff type.
- **Additional methods:**
  - `onSniffFinish(self)` — callback when directed sniff completes
  - `onSniffOk(self)` — callback when sniff yields usable results

## getManifest

`SniffForSpecificTag` does NOT appear to have its own getManifest in the decompiled binary — no `__pyx_pw_13activity_main_*SniffForSpecificTag*getManifest` symbol found. It inherits from SniffActivity's manifest, or is only launched programmatically (not via main menu).

## Title

Uses `title.sniff_notag` -> "Sniff TRF" (resources.py:78) — same display as SniffActivity but with a distinct resource key, suggesting the firmware distinguishes the two contexts internally.

## State Flow

```
[Caller Activity] --start(bundle)--> INSTRUCTION --> SNIFFING --> RESULT --> [Return to caller]
```

The bundle passed by the caller specifies which sniff type (14A, iClass, T5577, etc.).

## Key Handling

Inherits `SniffActivity.onKeyEvent` — no separate onKeyEvent symbol in decompiled binary.

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: exact visual difference (if any) between standalone and directed sniff]

---

# 3. SniffForMfReadActivity (MIFARE Read-Directed Sniff)

## Class Purpose

`SniffForMfReadActivity` extends `SniffForSpecificTag` for the specific case where a MIFARE Classic read has missing keys, and the user selects "Option 1) Go to reader to sniff keys".

(V1090_MODULE_AUDIT.txt:2038)

## getManifest

`SniffForMfReadActivity.getManifest()` (decompiled/activity_main_ghidra_raw.txt:3580-3612, `@0x0002f4cc`)

This is a minimal function:
- Takes no positional arguments (`param_2 + 8 < 1` required, line 3596)
- Returns a pre-built constant from the module data table (line 3602: `piVar2 = *(int **)(iVar3 + DAT_0002f558)`)
- The manifest likely maps to title `sniff_tag` or `sniff_notag` -> "Sniff TRF"

## Unique Methods

### showResult (decompiled/activity_main_ghidra_raw.txt:30473-30947, `@0x0004cf50`)

`SniffForMfReadActivity.showResult(self, data)` — takes 1 positional arg (the sniff result data).

Flow:
1. Calls parent's `__init__` equivalent to set up UI scope (line 30557-30564)
2. Invokes the parent's result display method via `CallNoArg` (line 30682)
3. Gets the sniffed key data via `PyObject_GetAttr` (line 30698: attribute access on self)
4. Checks `PyObject_Size` of the key data (line 30710)
5. If keys found (size > 0): increments a "success" flag constant (line 30730)
6. If no keys found (size == 0): increments a "failure" flag constant (line 30726)
7. Gets attribute for display formatting (line 30733-30737)
8. Calls a display function with the formatted key tuple (line 30843-30846)

### onKeyEvent (decompiled/activity_main_ghidra_raw.txt:608, `@0x000cd74c`)

`SniffForMfReadActivity.onKeyEvent(self, event)` has its own override.

This suggests different key behavior compared to base SniffActivity — likely:
- KEY_OK returns to the caller (ReadActivity) with sniffed keys in the bundle
- KEY_PWR returns to caller without keys

## Integration with Read Flow

When Read flow encounters missing MIFARE keys:
1. `itemmsg.missing_keys_msg1` -> "Option 1) Go to reader to sniff keys" (resources.py:204)
2. User selects Option 1
3. ReadActivity starts SniffForMfReadActivity
4. SniffForMfReadActivity runs 14A sniff (hardcoded type)
5. `parserKeyForM1` (sniff.so) extracts MIFARE keys from trace
6. `showResult` displays found/not-found status
7. On finish, returns to ReadActivity with keys in bundle

## PM3 Command

Uses `hf 14a sniff` (sniff_ghidra_raw.txt:321, STR@0x0001c340) since MIFARE Classic operates on ISO 14443A.

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: result display format for key data]

---

# 4. SniffForT5XReadActivity (T5577 Read-Directed Sniff)

## Class Purpose

`SniffForT5XReadActivity` extends `SniffForSpecificTag` for the case where a T5577/EM4305 read has missing keys (password-protected tag), and the user selects "Option 1) Go to reader to sniff keys".

(V1090_MODULE_AUDIT.txt:2142)

## getManifest

No separate getManifest symbol found in the decompiled binary. Inherits from parent class or uses shared manifest.

## Unique Methods

### showT5577Result

`SniffForT5XReadActivity.showT5577Result` is referenced in the string table:
- docs/V1090_SO_STRINGS_RAW.txt:63 `SniffForT5XReadActivity.showT5577Result`
- docs/V1090_SO_STRINGS_RAW.txt:497 `activity_main.SniffForT5XReadActivity.showT5577Result`
- Symbol: `__pyx_pw_13activity_main_23SniffForT5XReadActivity_1showT5577Result` (docs/V1090_SO_STRINGS_RAW.txt:485)

This method overrides or specializes the base `showT5577Result` for the directed sniff context, likely:
1. Displays T5577 key/password found during sniff
2. Returns key data to the calling ReadActivity

## Integration with Read Flow

When Read flow encounters a password-protected T5577:
1. `itemmsg.missing_keys_t57` -> "Option 1) Go to reader to sniff keys.\n\nOption 2) Enter known keys manually." (resources.py:207)
2. User selects Option 1
3. ReadActivity starts SniffForT5XReadActivity
4. SniffForT5XReadActivity runs LF sniff (hardcoded type)
5. Result parsed for T5577 password
6. On finish, returns to ReadActivity with password in bundle

## PM3 Command

Uses `lf sniff` (sniff_ghidra_raw.txt:330, STR@0x0001c3c0) since T5577 operates on LF (125 kHz).

## Toast

`toastmsg.t5577_sniff_finished` -> "T5577 Sniff Finished" (resources.py:114)

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: T5577 result display format]

---

# 5. Common UI Elements

## Title Strings

| Resource Key | Value | Used By |
|-------------|-------|---------|
| `title.sniff_tag` | "Sniff TRF" | SniffActivity (standalone) |
| `title.sniff_notag` | "Sniff TRF" | SniffForSpecificTag (directed) |
| `title.trace` | "Trace" | Trace display sub-screen |

(resources.py:77-78, 88)

## Toast Strings

| Key | Value | Context |
|-----|-------|---------|
| `toastmsg.sniffing` | "Sniffing in progress..." | During active sniff |
| `toastmsg.trace_saved` | "Trace file\nsaved" | After saving trace |
| `toastmsg.t5577_sniff_finished` | "T5577 Sniff Finished" | T5577 sniff done |
| `toastmsg.trace_loading` | "Trace\nLoading..." | Loading saved trace |

(resources.py:113-114, 112, 124)

## Button Strings

| Key | Value | Context |
|-----|-------|---------|
| `button.start` | "Start" | Begin sniffing |
| `button.stop` | "Stop" | Stop active sniff |
| `button.finish` | "Finish" | Complete HF sniff cycle |
| `button.sniff` | "Sniff" | Sniff action button |
| `button.save_log` | "Save" | Save trace to file |

(resources.py:37, 36, 44, 41, 59)

## Item/Instruction Strings

| Key | Value |
|-----|-------|
| `itemmsg.sniff_item1` | "1. 14A Sniff" |
| `itemmsg.sniff_item2` | "2. 14B Sniff" |
| `itemmsg.sniff_item3` | "3. iclass Sniff" |
| `itemmsg.sniff_item4` | "4. Topaz Sniff" |
| `itemmsg.sniff_item5` | "5. T5577 Sniff" |
| `itemmsg.sniffline1` | "Step 1: \nPrepare client's \nreader and tag, \nclick start." |
| `itemmsg.sniffline2` | "Step 2: \nRemove antenna cover \non iCopy and place \niCopy on reader." |
| `itemmsg.sniffline3` | "Step 3: \nSwipe tag on iCopy \nto ensure reader \nable to identify tag." |
| `itemmsg.sniffline4` | "Step 4: \nRepeat 3-5 times \nand click finish." |
| `itemmsg.sniffline_t5577` | "Click start, then\nswipe iCopy on reader.\nUntil you get keys." |
| `itemmsg.sniff_decode` | "Decoding...\n{}/{}" |
| `itemmsg.sniff_trace` | "TraceLen: {}" |

(resources.py:227-238)

## Progress Bar Strings

None specific to sniff — sniffing does not use procbarmsg.

## SniffActivity hideAll

`SniffActivity.hideAll(self)` (decompiled/activity_main_ghidra_raw.txt:14060-14415, `@0x0003a87c`)

Takes `(self, data, is_xxx)` with 2 positional args. Hides all UI elements: ListView, instruction text, console view, tracelen text, buttons. Used when transitioning between states.

## SniffActivity dismissTracelenText

`SniffActivity.dismissTracelenText(self)` (decompiled/activity_main_ghidra_raw.txt:13724-14058, `@0x0003a2b0`)

Removes the tracelen display text from the canvas.

## SniffActivity onTopPIOnlyUpdate / onMultiPIUpdate

`onTopPIOnlyUpdate(self, page_max, page_new)` (decompiled/activity_main_ghidra_raw.txt:18433-18778, `@0x0003f504`)
`onMultiPIUpdate(self, page_max, page_new)` (decompiled/activity_main_ghidra_raw.txt:18780-19125, `@0x0003fb54`)

These update the page indicator in the title bar when scrolling through multi-page result data. Both take 2 positional args (page_max, page_new).

## SniffActivity play_select_tips

(decompiled/activity_main_ghidra_raw.txt:551, `__pyx_pw_13activity_main_13SniffActivity_35play_select_tips @0x000cc9f8`)

Plays an audio tip when user selects a sniff type from the list.

## SniffActivity saveSniffData

(decompiled/activity_main_ghidra_raw.txt:634, `__pyx_pw_13activity_main_13SniffActivity_27saveSniffData @0x000cdd54`)

Saves trace data to a file. After save: toast `trace_saved` -> "Trace file\nsaved".

## SniffActivity onCreate

(decompiled/activity_main_ghidra_raw.txt:538, `__pyx_pw_13activity_main_13SniffActivity_9onCreate @0x000cc65c`)

Sets up the initial UI:
1. Sets title to "Sniff TRF"
2. Creates ListView with 5 sniff type items
3. Registers list selection callback

---

# 6. Summary: Complete State Diagram

```
SniffActivity (standalone, from main menu):
  TYPE_SELECT --> [OK] --> INSTRUCTION --> [Start] --> SNIFFING --> [Finish/auto] --> RESULT
       |                       |                          |                           |
      [PWR]                  [PWR]                      [PWR]                       [PWR]
       |                       |                          |                           |
     EXIT               TYPE_SELECT                TYPE_SELECT                  TYPE_SELECT
                                                                                    |
                                                                                  [Save]
                                                                                    |
                                                                             trace_saved toast

SniffForSpecificTag / SniffForMfReadActivity / SniffForT5XReadActivity (directed, from Read flow):
  INSTRUCTION --> [Start] --> SNIFFING --> [Finish/auto] --> RESULT --> [OK/PWR] --> Return to caller
       |                          |                           |
      [PWR]                     [PWR]                       [PWR]
       |                          |                           |
  Return to caller         Return to caller            Return to caller
```

---

## Corrections Applied

1. **RESULT screen buttons**: Fixed from M1="Save" (wrong) to M1="Start", M2="Save" (correct). Citation: `sniff_trf_1_4_2.png`.
2. **SNIFFING state buttons**: Fixed from "Start changes to Stop" (wrong) to M1="Start" (unchanged), M2="Finish". Citation: `sniff_trf_sniffing.png`.
3. **INSTRUCTION screen titles**: Added page indicator documentation — titles show "Sniff TRF N/4" (e.g., "Sniff TRF 1/4" through "4/4"). Citations: `sniff_trf_1_4_1.png`, `sniff_trf_2_4.png`, `sniff_trf_3_4.png`, `sniff_trf_4_4.png`.
4. **TYPE_SELECT title**: Updated from "Sniff TRF" to "Sniff TRF 1/1" per `sniff_trf_list_1_1.png`.
5. **INSTRUCTION buttons**: Added M2="Finish" button documentation — both Start and Finish are visible on all instruction pages. Citations: all sniff_trf_*_4.png screenshots.
6. **Key handling updates**: Corrected M1/M2 role descriptions throughout to match actual button positions.

---

## Key Bindings

### SniffActivity.onKeyEvent (activity_main_ghidra_raw.txt line 30949)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TYPE_SELECT | prev() | next() | no-op | no-op | startSniff() | finish() | startSniff() | finish() |
| SNIFFING | no-op | no-op | no-op | no-op | no-op | stop + finish() | stop + showResult() | stop + TYPE_SELECT |
| RESULT | prevPage() | nextPage() | no-op | no-op | saveSniffData() | prevPage() | saveSniffData() | TYPE_SELECT |

**Notes:**
- TYPE_SELECT: UP/DOWN scroll 5-item sniff type list. M2/OK start sniff, M1/PWR exit.
- SNIFFING: M2 stops and shows decoded result. M1 stops and exits. PWR stops and returns to type selection.
- RESULT: UP/DOWN/M1 paginate through multi-page trace results. M2/OK save trace data to file. PWR returns to TYPE_SELECT.

**Source:** `src/lib/activity_main.py` lines 2671-2735, `activity_main_ghidra_raw.txt` lines 30949-33007.
