# SimulationActivity + SimulationTraceActivity UI Mapping

Source: `decompiled/activity_main_ghidra_raw.txt`, `docs/v1090_strings/activity_main_strings.txt`,
`src/lib/resources.py` StringEN, `docs/reference_screenshots/sub_05_simulation.png`

---

## 1. SimulationActivity Overview

SimulationActivity is the LARGEST activity class in activity_main.so with 52+ exported methods
(activity_main_strings.txt:20880-21173). It manages tag simulation for 16 tag types with per-type
custom draw functions, input validation, and PM3 command generation.

### 1.1 Exported Method Inventory (from string table)

Methods extracted from `docs/v1090_strings/activity_main_strings.txt` lines 20880-21173:

| # | Method Name | String Table Line | Ghidra Symbol |
|---|-------------|-------------------|---------------|
| 1 | `getManifest` | 21017 | `__pyx_pw_13activity_main_18SimulationActivity_1getManifest` (STR@0x000caf1c) |
| 2 | `__init__` | 21138 | `__pyx_pw_13activity_main_18SimulationActivity_3__init__` (STR@0x000ccd24) |
| 3 | `getSimMap` | 21064 | `__pyx_pw_13activity_main_18SimulationActivity_5getSimMap` (STR@0x000ccc28) |
| 4 | `filter_space` | 21003 | `__pyx_pw_13activity_main_18SimulationActivity_7filter_space` (STR@0x000cd350) |
| 5 | `parserUID` | 21062 | `__pyx_pw_13activity_main_18SimulationActivity_9parserUID` (STR@0x000caee0) |
| 6 | `parserJabDat` | 20999 | `__pyx_pw_13activity_main_18SimulationActivity_13parserJabDat` (STR@0x000cae60) |
| 7 | `parserIoPorx` | 21000 | `__pyx_pw_13activity_main_18SimulationActivity_15parserIoPorx` (STR@0x000cca34) |
| 8 | `parserFCCN` | 21036 | `__pyx_pw_13activity_main_18SimulationActivity_17parserFCCN` (STR@0x000cae24) |
| 9 | `parserPyramid` | 20927 | `__pyx_pw_13activity_main_18SimulationActivity_19parserPyramid` (STR@0x000cade4) |
| 10 | `parserFdx` | 21063 | `__pyx_pw_13activity_main_18SimulationActivity_21parserFdx` (STR@0x000cad84) |
| 11 | `parserNedap` | 21016 | `__pyx_pw_13activity_main_18SimulationActivity_23parserNedap` (STR@0x000ccb74) |
| 12 | `chk_max_comm` | 21005 | `__pyx_pw_13activity_main_18SimulationActivity_25chk_max_comm` (STR@0x000cdc64) |
| 13 | `chk_ioid_input` | 20947 | `__pyx_pw_13activity_main_18SimulationActivity_27chk_ioid_input` (STR@0x000cd7cc) |
| 14 | `chk_gproxid_input` | 20948 | `__pyx_pw_13activity_main_18SimulationActivity_29chk_gproxid_input` (STR@0x000ccaec) |
| 15 | `chk_pyramid_input` | 20945 | `__pyx_pw_13activity_main_18SimulationActivity_31chk_pyramid_input` (STR@0x000ca038) |
| 16 | `chk_fdx_data` | n/a | `__pyx_pw_13activity_main_18SimulationActivity_33chk_fdx_data` (STR@0x000ca0c0) |
| 17 | `chk_nedap_input` | 20946 | `__pyx_pw_13activity_main_18SimulationActivity_35chk_nedap_input` (STR@0x000ca140) |
| 18 | `draw_top_title` | 20931 | `__pyx_pw_13activity_main_18SimulationActivity_37draw_top_title` (STR@0x000ca1c0) |
| 19 | `draw_hf_sim_4b` | 20943 | `__pyx_pw_13activity_main_18SimulationActivity_41draw_hf_sim_4b` (STR@0x000c9d7c) |
| 20 | `draw_hf_sim_7b` | 20942 | `__pyx_pw_13activity_main_18SimulationActivity_43draw_hf_sim_7b` (STR@0x000c9e7c) |
| 21 | `draw_lf_sim_4b` | 20935 | `__pyx_pw_13activity_main_18SimulationActivity_45draw_lf_sim_4b` (STR@0x000c9dfc) |
| 22 | `draw_lf_sim_5b` | 20934 | `__pyx_pw_13activity_main_18SimulationActivity_47draw_lf_sim_5b` (STR@0x000c9efc) |
| 23 | `draw_lf_jablotron` | 20938 | `__pyx_pw_13activity_main_18SimulationActivity_49draw_lf_jablotron` (STR@0x000c9f7c) |
| 24 | `draw_pos_arrow` | 20933 | `__pyx_pw_13activity_main_18SimulationActivity_51draw_pos_arrow` (STR@0x000cde74) |
| 25 | `create_tags_for_inputmethod` | 20944 | `__pyx_pw_13activity_main_18SimulationActivity_53create_tags_for_inputmethod` (STR@0x000ca950) |
| 26 | `draw_lf_awid` | 21004 | `__pyx_pw_13activity_main_18SimulationActivity_59draw_lf_awid` (STR@0x000cad04) |
| 27 | `draw_lf_io` | 21039 | `__pyx_pw_13activity_main_18SimulationActivity_61draw_lf_io` (STR@0x000cac8c) |
| 28 | `draw_lf_gporx` | 20939 | `__pyx_pw_13activity_main_18SimulationActivity_63draw_lf_gporx` (STR@0x000cac0c) |
| 29 | `draw_lf_pyramid` | 20936 | `__pyx_pw_13activity_main_18SimulationActivity_65draw_lf_pyramid` (STR@0x000cd0d8) |
| 30 | `draw_lf_fdx_animal` | 20941 | `__pyx_pw_13activity_main_18SimulationActivity_67draw_lf_fdx_animal` (STR@0x000cd050) |
| 31 | `draw_lf_fdx_data` | 20940 | `__pyx_pw_13activity_main_18SimulationActivity_69draw_lf_fdx_data` (STR@0x000cce30) |
| 32 | `draw_lf_nedap` | 20937 | `__pyx_pw_13activity_main_18SimulationActivity_71draw_lf_nedap` (STR@0x000cab8c) |
| 33 | `get_focus_im` | 21002 | `__pyx_pw_13activity_main_18SimulationActivity_73get_focus_im` (STR@0x000cd5a0) |
| 34 | `switch_or_input` | 20924 | `__pyx_pw_13activity_main_18SimulationActivity_75switch_or_input` (STR@0x000cd010) |
| 35 | `focus_or_unfocus` | 20930 | `__pyx_pw_13activity_main_18SimulationActivity_77focus_or_unfocus` (STR@0x000ca2bc) |
| 36 | `switch_word_iffocus` | 20923 | `__pyx_pw_13activity_main_18SimulationActivity_79switch_word_iffocus` (STR@0x000ca99c) |
| 37 | `get_all_input` | 20929 | `__pyx_pw_13activity_main_18SimulationActivity_81get_all_input` (STR@0x000ca200) |
| 38 | `onCreate` | 21088 | `__pyx_pw_13activity_main_18SimulationActivity_83onCreate` (STR@0x000cab14) |
| 39 | `showSniffingToast` | 20926 | `__pyx_pw_13activity_main_18SimulationActivity_85showSniffingToast` (STR@0x000caad0) |
| 40 | `startSimForData` | 20925 | `__pyx_pw_13activity_main_18SimulationActivity_87startSimForData` (STR@0x000cc5a4) |
| 41 | `onData` | 21137 | `__pyx_pw_13activity_main_18SimulationActivity_89onData` (STR@0x000ca828) |
| 42 | `onSim` | 21173 | `__pyx_pw_13activity_main_18SimulationActivity_91onSim` (STR@0x000c9918) |
| 43 | `on14ASimStop` | 21001 | `__pyx_pw_13activity_main_18SimulationActivity_93on14ASimStop` (STR@0x000cc6c4) |
| 44 | `startSim` | 21087 | `__pyx_pw_13activity_main_18SimulationActivity_95startSim` (STR@0x000cc218) |
| 45 | `stopSim` | 21110 | `__pyx_pw_13activity_main_18SimulationActivity_97stopSim` (STR@0x000cc338) |
| 46 | `showListUI` | 21035 | `__pyx_pw_13activity_main_18SimulationActivity_101showListUI` (STR@0x000ca280) |
| 47 | `onKeyEvent` | 21038 | `__pyx_pw_13activity_main_18SimulationActivity_103onKeyEvent` (STR@0x000caa94) |
| 48 | `draw_pos_arrow_for_selection` | 20880 | (inferred from string table) |
| 49 | `create_tags_for_inputmethods` | 20881 | (inferred from string table) |
| 50 | `draw_single_sim` | 20932 | (inferred from string table) |
| 51 | `showSimUi` | 21061 | (inferred from string table) |
| 52 | `parserData` | 21037 | (inferred from string table) |

**Note**: `startSim` (method #95) caused a decompiler exception:
`DECOMP_ERROR __pyx_pw_13activity_main_18SimulationActivity_95startSim: Exception while decompiling 0006cc94: Decompiler process died`
(activity_main_ghidra_raw.txt:58774)

---

## 2. State Machine

SimulationActivity has three states:

```
   +-------------+     OK        +----------+     M2/OK      +-----------+
   | TYPE_SELECT  |  ----------> | SIM_UI   |  ----------->  | SIMULATING|
   | (list_view)  |              | (sim_ui) |                | (running) |
   | M1="" M2=""  |              | M1=Stop  |                | M1=Stop   |
   +------+------+              | M2=Start |                | M2=Start  |
          |                      +-----+----+                +------+----+
          | PWR                       | PWR                         | M1/PWR
          v                           v                             | (stopSim)
      finish()                   TYPE_SELECT                        v
                                                               SIM_UI
                                                            (on HF: on14ASimStop)
```

### 2.1 STATE: TYPE_SELECT (list_view)

**Screen layout** (verified: `docs/reference_screenshots/sub_05_simulation.png`):
- Title: `"Simulation X/Y"` where X = current page, Y = total pages
  - Source: `resources.get_str('simulation')` = `"Simulation"` (resources.py:89)
  - Page indicator appended in title: `"{} {}/{}".format(title, cur, pages)`
- Content: ListView with 5 items per page, 4 pages total (16 types / 5 per page = 4 pages, last page has 1 item)
- M1: `""` (empty -- no button label)
- M2: `""` (empty -- no button label)

**Screenshot confirmation** (`simulation_list_1_4.png`):
Title shows "Simulation 1/4" with battery icon. No button labels visible in bottom bar. List shows numbered items:
```
1. M1 S50 1k
2. M1 S70 4k
3. Ultralight
4. Ntag215
5. FM11RF005SH
```

**Key behavior**:
- UP: scroll up in list, update title page indicator
- DOWN: scroll down in list, update title page indicator
- M2/OK: select type, transition to SIM_UI
- PWR: finish() (exit to caller)

### 2.2 STATE: SIM_UI (sim_ui)

**Screen layout**:
- Title: `"Simulation"` (fixed, no page indicator)
  - Source: `resources.get_str('simulation')` (resources.py:89)
- Content: Per-type draw function renders input fields (see Section 4)
- M1: `"Stop"` (resources.py:36, button key `'stop'`)
- M2: `"Start"` (resources.py:37, button key `'start'`)

**Button citation:** `simulation_detail_1.png` shows M1="Stop" on bottom-left and M2="Start" on bottom-right.

**Key behavior** (from onKeyEvent decompiled at ghidra_raw.txt:20226-22203):
- M1: toggle editing mode (self._editing = not self._editing)
- M2/OK: call startSimForData() -> validate inputs -> startSim(cmd)
- PWR: return to TYPE_SELECT (showListUI)
- UP: if editing, roll current input field character up; else move focus to previous field
- DOWN: if editing, roll current input field character down; else move focus to next field
- LEFT: if editing, move cursor left within current input field
- RIGHT: if editing, move cursor right within current input field

### 2.3 STATE: SIMULATING

**Screen layout**:
- Title: `"Simulation"`
- Content: simulation in progress (toast shown)
- M1: `"Stop"` (resources.py:36, button key `'stop'`)
- M2: `"Start"` (resources.py:37, button key `'start'`)

**Button citation:** `simulation_in_progress.png` shows M1="Stop" on bottom-left and M2="Start" on bottom-right (buttons do NOT change from SIM_UI state).

**Toast**: `"Simulation in progress..."` (resources.py:126, toastmsg key `'simulating'`)

**Key behavior**:
- M2/PWR: call stopSim() which calls executor.stopPM3Task()
  - On HF types: triggers on14ASimStop() for trace data capture
  - On LF types: returns directly to SIM_UI

---

## 3. SIM_MAP: 16 Simulation Types

The global `SIM_MAP` is referenced via `__pyx_n_s_SIM_MAP` (activity_main_strings.txt:22346/27355).
Each entry is a tuple: `(display_name, type_id, freq, draw_key, parser_key, pm3_cmd_template)`.

Source: activity_main_strings.txt lines 21338-22057 (PM3 commands), confirmed by binary string literals:

| # | Display Name | ID | Freq | Draw Function | Parser | PM3 Command Template |
|---|-------------|----|------|---------------|--------|---------------------|
| 0 | M1 S50 1k | 1 | HF | `draw_hf_sim_4b` | `parserUID` | `hf 14a sim t 1 u {}` (STR line 21446) |
| 1 | M1 S70 4k | 0 | HF | `draw_hf_sim_4b` | `parserUID` | `hf 14a sim t 2 u {}` (STR line 21445) |
| 2 | Ultralight | 2 | HF | `draw_hf_sim_7b` | `parserUID` | `hf 14a sim t 7 u {}` (STR line 21444) |
| 3 | Ntag215 | 6 | HF | `draw_hf_sim_7b` | `parserUID` | `hf 14a sim t 8 u {}` (STR line 21443) |
| 4 | FM11RF005SH | 40 | HF | `draw_hf_sim_4b` | `parserUID` | `hf 14a sim t 9 u {}` (STR line 21442) |
| 5 | Em410x ID | 8 | LF | `draw_lf_sim_4b` | `parserUID` | `lf em 410x_sim {}` (STR line 21571) |
| 6 | HID Prox ID | 9 | LF | `draw_lf_sim_5b` | `parserData` | `lf hid sim {}` (STR line 21932) |
| 7 | AWID ID | 11 | LF | `draw_lf_awid` | `parserFCCN` | `lf awid sim {} {} {}` (STR line 21829) |
| 8 | IO Prox ID | 12 | LF | `draw_lf_io` | `parserIoPorx` | `lf io sim {} {} {}` (STR line 22057) |
| 9 | G-Prox II ID | 13 | LF | `draw_lf_gporx` | `parserFCCN` | `lf gproxii sim {} {} {}` (STR line 21570) |
| 10 | Viking ID | 15 | LF | `draw_lf_sim_4b` | `parserUID` | `lf Viking sim {}` (STR line 21650) |
| 11 | Pyramid ID | 16 | LF | `draw_lf_pyramid` | `parserPyramid` | `lf Pyramid sim {} {}` (STR line 21572) |
| 12 | Jablotron ID | 30 | LF | `draw_lf_jablotron` | `parserJabDat` | `lf Jablotron sim {}` (STR line 21437) |
| 13 | Nedap ID | 32 | LF | `draw_lf_nedap` | `parserNedap` | `lf nedap sim s {} c {} i {}` (STR line 21338) |
| 14 | FDX-B Animal | 28 | LF | `draw_lf_fdx_animal` | `parserFdx` | `lf FDX sim c {} n {} s` (STR line 21438) |
| 15 | FDX-B Data | 28 | LF | `draw_lf_fdx_data` | `parserFdx` | `lf FDX sim c {} n {} e {}` (STR line 21439) |

### 3.1 Page Layout for TYPE_SELECT

5 items per page, no "OK" buttons visible. Page indicator is in the title, not as a separate widget.

```
Page 1/4: 1. M1 S50 1k, 2. M1 S70 4k, 3. Ultralight, 4. Ntag215, 5. FM11RF005SH
Page 2/4: 6. Em410x ID, 7. HID Prox ID, 8. AWID ID, 9. IO Prox ID, 10. G-Prox II ID
Page 3/4: 11. Viking ID, 12. Pyramid ID, 13. Jablotron ID, 14. Nedap ID, 15. FDX-B Animal
Page 4/4: 16. FDX-B Data
```

**Numeric prefixes citation:** `simulation_list_1_4.png` shows items with "1. ", "2. ", etc. prefixes. The numeric prefix is part of the display string, not a separate column.

---

## 4. Per-Type Draw Functions and Input Fields

### 4.1 HF Types: `draw_hf_sim_4b` (decompiled at ghidra_raw.txt:9532-9736)

Used by: M1 S50 1k, M1 S70 4k, FM11RF005SH

Input fields:
```
UID: [12345678]    (hex, 8 chars = 4 bytes)
```

Draw function creates one input field for UID, max 8 hex characters.

### 4.2 HF Types: `draw_hf_sim_7b` (decompiled at ghidra_raw.txt:9944-10148)

Used by: Ultralight, Ntag215

Input fields:
```
UID: [123456789ABCDE]    (hex, 14 chars = 7 bytes)
```

### 4.3 LF Types: `draw_lf_sim_4b` (decompiled at ghidra_raw.txt:9738-9942)

Used by: Em410x ID, Viking ID

Input fields:
```
UID: [1234567890]    (hex, 10 chars = 5 bytes for EM, 8 chars for Viking)
```

Note: Em410x uses 10-char hex, Viking uses 8-char hex. The draw function is `draw_lf_sim_4b`
but the field length varies based on the specific SIM_MAP entry.

### 4.4 LF Types: `draw_lf_sim_5b` (decompiled at ghidra_raw.txt:10150-10354)

Used by: HID Prox ID

Input fields:
```
ID: [112233445566]    (hex, 12 chars = 6 bytes)
```

### 4.5 `draw_lf_awid` (decompiled at ghidra_raw.txt:26773-28050)

Used by: AWID ID

Input fields:
```
FC:      [222222]    (decimal, max 65535)
CN:      [444444]    (decimal, max 65535)
Format:  [26]        (decimal, max 255)
```

Validation: `chk_max_comm` checks each field <= max value.
On validation failure: toast `"Input invalid:\n{} greater than {}"` (resources.py:127, toastmsg `'sim_valid_input'`)

### 4.6 `draw_lf_io` (decompiled at ghidra_raw.txt:25482-26771)

Used by: IO Prox ID

Input fields:
```
Version: [0x01]    (hex, 2 chars)
FC:      [1]       (decimal, max 255)
CN:      [1]       (decimal, max 999)
```

Validation: `chk_ioid_input` (decompiled at ghidra_raw.txt line 610, symbol at STR@0x000cd7cc)

### 4.7 `draw_lf_gporx` (decompiled at ghidra_raw.txt:24175-25480)

Used by: G-Prox II ID

Input fields:
```
FC:      [1]      (decimal, max 255)
CN:      [1]      (decimal, max 65535)
Format:  [26]     (decimal, max 255)
```

Validation: `chk_gproxid_input` (decompiled at ghidra_raw.txt:555, STR@0x000ccaec)

### 4.8 `draw_lf_pyramid` (decompiled at ghidra_raw.txt:580-581)

Used by: Pyramid ID

Input fields:
```
FC:      [1]      (decimal, max 255)
CN:      [1]      (decimal, max 99999)
```

Validation: `chk_pyramid_input` (decompiled at ghidra_raw.txt:10906-11274)

### 4.9 `draw_lf_jablotron` (decompiled at ghidra_raw.txt:10356-10583)

Used by: Jablotron ID

Input fields:
```
ID: [1C6AEB]    (hex, 6 chars)
```

### 4.10 `draw_lf_nedap` (decompiled at ghidra_raw.txt:22868-24173)

Used by: Nedap ID

Input fields:
```
Subtype: [0x01]   (hex, 2 chars)
CN:      [1]      (decimal, max 65535)
ID:      [1]      (decimal, max 65535)
```

Validation: `chk_nedap_input` (decompiled at ghidra_raw.txt:11565-11853)

### 4.11 `draw_lf_fdx_animal` (decompiled at ghidra_raw.txt:578-579)

Used by: FDX-B Animal

Input fields:
```
Country: [1]      (decimal, max 2001)
ID:      [1]      (decimal, max 4294967295)
Animal:  [1]      (selector, 0 or 1)
```

Validation: `chk_fdx_data` (decompiled at ghidra_raw.txt:11276-11563)

### 4.12 `draw_lf_fdx_data` (decompiled at ghidra_raw.txt:569-570)

Used by: FDX-B Data

Input fields:
```
Country: [1]      (decimal, max 2001)
ID:      [1]      (decimal, max 4294967295)
Ext:     [0]      (decimal, max 255)
```

---

## 5. Input Method System

### 5.1 Focus Management

- `focus_or_unfocus` (decompiled at ghidra_raw.txt:13098-13280): Sets visual focus on one input field
- `get_focus_im` (decompiled at ghidra_raw.txt:601-602): Returns currently focused InputMethod
- `switch_word_iffocus` (decompiled at ghidra_raw.txt:19379-19885): Cycles character at cursor position
- `switch_or_input` (decompiled at ghidra_raw.txt:577): Toggles between browsing and editing mode
- `draw_pos_arrow` (decompiled at ghidra_raw.txt:639-640): Draws cursor arrow at current position

### 5.2 Editing Flow

1. User presses M1 ("Edit") to enter editing mode
2. Cursor appears on the first character of the focused input field
3. UP/DOWN cycles the character value (hex: 0-F, dec: 0-9)
4. LEFT/RIGHT moves cursor position within the field
5. Pressing M1 again toggles back to field-selection mode (UP/DOWN change field focus)
6. M2/OK triggers startSimForData() with all current input values

---

## 6. Simulation Execution

### 6.1 startSimForData (decompiled at ghidra_raw.txt:535-536)

Flow:
1. `get_all_input()` collects values from all input fields (ghidra_raw.txt:12100-12738)
2. Type-specific validation: calls the appropriate `chk_*_input` function
3. On validation failure: shows toast with `sim_valid_input` or `sim_valid_param` message
4. Builds PM3 command from template: `cmd_template.format(*values)`
5. Calls `startSim(cmd)`

### 6.2 startSim (decompiled FAILED -- decompiler died at 0x0006cc94)

From string table and cross-reference analysis:
1. Sets state to SIMULATING
2. Calls `executor.startPM3Task(cmd, callback=self.onSim)`
3. Shows toast: `"Simulation in progress..."` (resources.py:126)
4. Buttons remain M1="Stop", M2="Start" (unchanged from SIM_UI state)
5. Audio: `playSimulating` (activity_main_strings.txt:21563)

### 6.3 stopSim (STR@0x000cc338)

1. Calls `executor.stopPM3Task()`
2. For HF types (M1/S70/Ultralight/Ntag215/FM11): calls `on14ASimStop()`
3. For LF types: returns directly to SIM_UI

### 6.4 on14ASimStop (STR@0x000cc6c4)

After HF simulation stops, captures trace data and returns to SIM_UI.
May optionally launch `SimulationTraceActivity` to display captured data.

### 6.5 onSim (decompiled at ghidra_raw.txt:6447-6614)

Callback from PM3 task completion. Routes to on14ASimStop for HF, or back to SIM_UI for LF.

### 6.6 onData (decompiled at ghidra_raw.txt:18193-18431)

Data callback from executor during simulation. Contains a lambda2 for processing
(activity_main_strings.txt:20928, STR@0x000c9a3c).

---

## 7. Toast Messages

| Key | Value | Source |
|-----|-------|--------|
| `simulating` | `"Simulation in progress..."` | resources.py:126 |
| `sim_valid_input` | `"Input invalid:\n{} greater than {}"` | resources.py:127 |
| `sim_valid_param` | `"Invalid parameter"` | resources.py:128 |

---

## 8. SimulationTraceActivity

Separate activity for displaying simulation trace/capture data after HF simulation stops.

### 8.1 Exported Methods (from string table activity_main_strings.txt:20919-21015)

| # | Method Name | Symbol |
|---|-------------|--------|
| 1 | `__init__` | `__pyx_pw_13activity_main_23SimulationTraceActivity_1__init__` (STR@0x000caf94) |
| 2 | `showResult` | `__pyx_pw_13activity_main_23SimulationTraceActivity_3showResult` (STR@0x000cd4e4) |
| 3 | `saveSniffData` | `__pyx_pw_13activity_main_23SimulationTraceActivity_5saveSniffData` (line 23977) |
| 4 | `onCreate` | `__pyx_pw_13activity_main_23SimulationTraceActivity_7onCreate` (line 23982) |
| 5 | `onKeyEvent` | `__pyx_pw_13activity_main_23SimulationTraceActivity_9onKeyEvent` (STR@0x000cc704) |

### 8.2 Screen Layout

- Title: `"Trace"` (resources.py:88, title key `'trace'`)
- Content: BigTextListView showing trace data (from `showResult`)
- M1: `"Back"`
- M2: `"Save"` (resources.py:46, button key `'save'`)

### 8.3 Key Behavior

- M2/OK: `saveSniffData()` -- saves trace, shows toast `"Trace file\nsaved"` (resources.py:112, toastmsg `'trace_saved'`)
- M1/PWR: `finish()` -- exit back to caller

### 8.4 State Flow

```
   +----------+    M2/OK     +-------+
   | DISPLAY  | ----------> | SAVED  |
   | (trace)  |             | (same) |
   +----+-----+             +--------+
        |
        | M1/PWR
        v
    finish()
```

---

## 9. String Resources Summary

### Title strings (resources.py StringEN.title):
- `'simulation'` -> `"Simulation"` (line 89)
- `'trace'` -> `"Trace"` (line 88)

### Button strings (resources.py StringEN.button):
- `'simulate'` -> `"Simulate"` (line 43)
- `'stop'` -> `"Stop"` (line 36)
- `'start'` -> `"Start"` (line 37)
- `'edit'` -> `"Edit"` (line 62)
- `'save'` -> `"Save"` (line 46)
- `'finish'` -> `"Finish"` (line 44)

### Toast strings (resources.py StringEN.toastmsg):
- `'simulating'` -> `"Simulation in progress..."` (line 126)
- `'sim_valid_input'` -> `"Input invalid:\n{} greater than {}"` (line 127)
- `'sim_valid_param'` -> `"Invalid parameter"` (line 128)
- `'trace_saved'` -> `"Trace file\nsaved"` (line 112)
- `'trace_loading'` -> `"Trace\nLoading..."` (line 124)

### Item strings (resources.py StringEN.itemmsg):
- `'sniff_trace'` -> `"TraceLen: {}"` (line 238)

### Internal string table (activity_main_strings.txt):
- `SIM_MAP` (line 22346)
- `playSimulating` (line 21563)
- `text_simulation` (line 21476)
- `text_simulating` (line 21477)
- `text_sim_valid_param` (line 21261)
- `text_sim_valid_input` (line 21262)
- `showListUI` (line 21903)
- `showSimUi` (line 21061)

---

## 10. Decompiled Function Cross-Reference

### Key decompiled functions with line ranges in ghidra_raw.txt:

| Function | Start Line | End Line | Address |
|----------|-----------|----------|---------|
| `onSim` | 6447 | 6614 | 0x00031fa4 |
| `onData_lambda2` | 7364 | 7532 | 0x00032fc8 |
| `draw_hf_sim_4b` | 9532 | 9736 | 0x00035750 |
| `draw_lf_sim_4b` | 9738 | 9942 | 0x00035b34 |
| `draw_hf_sim_7b` | 9944 | 10148 | 0x00035f18 |
| `draw_lf_sim_5b` | 10150 | 10354 | 0x000362fc |
| `draw_lf_jablotron` | 10356 | 10583 | 0x000366e0 |
| `chk_pyramid_input` | 10906 | 11274 | 0x00037100 |
| `chk_fdx_data` | 11276 | 11563 | 0x00037790 |
| `chk_nedap_input` | 11565 | 11853 | 0x00037cdc |
| `draw_top_title` | 11855 | 12098 | 0x00038228 |
| `get_all_input` | 12100 | 12738 | 0x00038654 |
| `showListUI` | 12877 | 13096 | 0x000393dc |
| `focus_or_unfocus` | 13098 | 13280 | 0x00039788 |
| `onData` | 18193 | 18431 | 0x0003f0d8 |
| `create_tags_for_inputmethod` | 19127 | 19377 | 0x000401a4 |
| `switch_word_iffocus` | 19379 | 19885 | 0x00040608 |
| `onKeyEvent` | 20226 | 22203 | 0x00041560 |
| `showSniffingToast` | 22205 | 22515 | 0x00043a30 |
| `onCreate` | 22517 | 22866 | 0x00043f8c |
| `draw_lf_nedap` | 22868 | 24173 | 0x000445d0 |
| `draw_lf_gporx` | 24175 | 25480 | 0x00045d90 |
| `draw_lf_io` | 25482 | 26771 | 0x00047550 |
| `draw_lf_awid` | 26773 | 28050 | 0x00048cd8 |
| `parserFdx` | 28052 | 28694 | 0x0004a4b4 |
| `parserPyramid` | 28696 | 28949 | 0x0004b018 |
| `parserFCCN` | 28951 | 29271 | 0x0004b48c |
| `parserJabDat` | 29273 | 29563 | 0x0004ba0c |
| `parserUID` | 29565 | 29783 | 0x0004bf38 |
| `getManifest` | 29785 | 30103 | 0x0004c2e8 |
| `startSim` | DECOMP_ERROR | -- | 0x0006cc94 |

---

## 11. getManifest (decompiled at ghidra_raw.txt:29785-30103)

Returns a dict containing:
- Key from `resources.get_str` for title/button resolution
- Tuple of (class_reference, draw_parameters)

The manifest is used by the activity stack to register SimulationActivity with proper
title and button configuration.

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | TYPE_SELECT: Corrected M2 from `"Simulate"` to `""` (empty). No button labels shown in this state. | `simulation_list_1_4.png` |
| 2026-03-31 | SIM_UI: Corrected M1 from `"Edit"` to `"Stop"`, M2 from `"Simulate"` to `"Start"`. | `simulation_detail_1.png` |
| 2026-03-31 | SIMULATING: Corrected M2 from `"Stop"` to `"Start"`. Buttons stay M1="Stop", M2="Start" (unchanged from SIM_UI). | `simulation_in_progress.png` |
| 2026-03-31 | Added numeric prefixes to list items: "1. M1 S50 1k", "2. M1 S70 4k", etc. | `simulation_list_1_4.png` |

---

## Key Bindings

### SimulationActivity.onKeyEvent (activity_main_ghidra_raw.txt line 20226)

Three states: LIST (type selection), SIM_UI (parameter entry), SIMULATING (running sim).

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LIST | prev() | next() | no-op | no-op | selectType() -> SIM_UI | no-op | selectType() -> SIM_UI | finish() |
| SIM_UI (not editing) | prevField() | nextField() | no-op | no-op | startSim() | toggle edit mode | startSim() | back to LIST |
| SIM_UI (editing) | rollUp() | rollDown() | prevChar() | nextChar() | startSim() | toggle edit mode | startSim() | back to LIST |
| SIMULATING | no-op | no-op | no-op | no-op | no-op | no-op | stopSim() | stopSim() |

**Notes:**
- LIST: Standard list navigation. M2/OK select sim type and show parameter entry UI.
- SIM_UI: M1 toggles between edit and navigate modes. In edit mode, UP/DOWN roll hex digit values and LEFT/RIGHT move cursor between characters. In navigate mode, UP/DOWN move between input fields.
- SIMULATING: Only M2 and PWR can stop the simulation.

**Sub-activity:** SimulationTraceActivity shows captured trace data after HF simulation stop:

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TRACE | no-op | no-op | no-op | no-op | saveSniffData() | finish() | saveSniffData() | finish() |

**Source:** `src/lib/activity_main.py` lines 4566-4616, `activity_main_ghidra_raw.txt` lines 20226-22203.
