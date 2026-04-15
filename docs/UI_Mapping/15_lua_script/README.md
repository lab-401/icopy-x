# LUAScriptCMDActivity + ConsolePrinterActivity UI Mapping

Source: `decompiled/activity_main_ghidra_raw.txt`, `docs/v1090_strings/activity_main_strings.txt`,
`src/lib/resources.py` StringEN,
`docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Lua.png`,
`docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Lua-Resullts.png`,
`docs/reference_screenshots/sub_13_lua_script.png`

---

## 1. LUAScriptCMDActivity Overview

LUAScriptCMDActivity is a file-list browser that enumerates `.lua` scripts from the device
script directory, displays them in a paginated ListView, and launches ConsolePrinterActivity
to execute the selected script.

### 1.1 Exported Method Inventory

Methods extracted from `docs/v1090_strings/activity_main_strings.txt` lines 20883-21091:

| # | Method Name | String Table Line | Ghidra Symbol |
|---|-------------|-------------------|---------------|
| 1 | `getManifest` | 20963 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_1getManifest` (line 23902) |
| 2 | `__init__` | 21091 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_3__init__` (line 24161) |
| 3 | `onMultiPIUpdate` | 20961 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_5onMultiPIUpdate` (line 23860) |
| 4 | `listLUAFiles` | 20883 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_7listLUAFiles` (line 23984) |
| 5 | `onResume` | 21041 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_9onResume` (line 23947) |
| 6 | `onDestroy` | 21022 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_11onDestroy` (line 24118) |
| 7 | `runScriptTask` | 20960 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_13runScriptTask` (line 23929) |
| 8 | `onKeyEvent` | 21009 | `__pyx_pw_13activity_main_20LUAScriptCMDActivity_15onKeyEvent` (line 24141) |

Internal helper (lambda):
- `listLUAFiles.<locals>.is_lua` (line 20962, symbol line 23845)

### 1.2 mdef Table (from activity_main_strings.txt:31204-31223)

```
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_1getManifest
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_3__init__
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_5onMultiPIUpdate
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_7listLUAFiles
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_9onResume
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_11onDestroy
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_13runScriptTask
__pyx_mdef_13activity_main_20LUAScriptCMDActivity_15onKeyEvent
```

---

## 2. State Machine

LUAScriptCMDActivity has a single state: FILE_LIST. It launches ConsolePrinterActivity
as a child activity when a script is selected.

```
   +------------+     M2/OK      +-----------------------+
   | FILE_LIST  | ------------> | ConsolePrinterActivity |
   | (ListView) |  runScriptTask | (child activity)      |
   +-----+------+               +-----------+-----------+
         |                                   |
         | PWR                               | M1/PWR (in child)
         v                                   v
     finish()                          returns to FILE_LIST
```

### 2.1 STATE: FILE_LIST

**Screen layout** (verified: `docs/reference_screenshots/sub_13_lua_script.png` and
`docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Lua.png`):

- Title: `"LUA Script X/Y"` where X = current page, Y = total pages
  - Source: `resources.get_str('lua_script')` = `"LUA Script"` (resources.py:97)
  - Page indicator appended: format `"%s %d/%d"`
- Content: ListView with 5 items per page, paginated
- M1: not visible (no button label shown)
- M2: not visible (no button label shown)

**Screenshot citation**: `lua_script_1_10.png` and `lua_script_10_10.png` both show NO button bar at all — the list occupies the full content area with no footer buttons visible. The full screen shows only the title bar and list items.

**Screenshot confirmation** (sub_13_lua_script.png):
Title: "LUA Script 1/10" with battery icon
List items:
```
legic
test_t55x7_bi
mifareplus
mfu_magic
dumptoemul
```

**Screenshot confirmation** (v1090_captures/090-Lua.png):
Title: "LUA Script 1/18"
List items:
```
data_dumptohtml
data_emulatortodump
data_emulatortohtml
data_example_cmdline
data_example_parameter
```

Note: the 090-Lua.png shows 18 pages, indicating the real device has many more scripts than
the QEMU screenshot (10 pages). The number of scripts is dynamic based on `/mnt/upan/luascripts/`.

**Key behavior**:
- UP: scroll up in list, update title page indicator
- DOWN: scroll down in list, update title page indicator
- LEFT: previous page (if > page 1)
- RIGHT: next page (if < last page)
- M2/OK: execute selected script via `runScriptTask()`
- PWR: `finish()` (exit to Main Menu)

---

## 3. Script Directory

From string table (activity_main_strings.txt):
- `path_lua_scripts` (line 21433)
- `luascripts` (line 21930/25575)

The script directory on the real device is `/mnt/upan/luascripts/`.

### 3.1 listLUAFiles (string table line 20883)

1. Enumerates all files in `/mnt/upan/luascripts/`
2. Filters using `is_lua` lambda: keeps only files ending in `.lua`
3. Strips `.lua` extension for display
4. Sorts alphabetically
5. Returns list of script base names

---

## 4. Script Execution

### 4.1 runScriptTask (string table line 20960)

From binary analysis:
1. Gets selected filename from ListView
2. Builds PM3 command: `"script run <scriptname>"` (string literal at line 21910: `"script run "`)
3. Creates bundle with `{'cmd': cmd, 'title': 'LUA Script'}`
4. Launches `ConsolePrinterActivity` with this bundle

The PM3 command `script run` is the proxmark3 command that executes a Lua script.

### 4.2 onMultiPIUpdate (string table line 20961)

Page indicator update callback. Called when the ListView changes pages to update
the title with the current page number.

---

## 5. ConsolePrinterActivity Overview

ConsolePrinterActivity is a general-purpose PM3 output display. It is used by:
- LUAScriptCMDActivity (script execution output)
- ReadActivity (key recovery progress output)
- DiagnosisActivity (diagnostic command output)

### 5.1 Exported Method Inventory

Methods extracted from `docs/v1090_strings/activity_main_strings.txt` lines 20884-21095:

| # | Method Name | String Table Line | Ghidra Symbol |
|---|-------------|-------------------|---------------|
| 1 | `onActivity` | 20975 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_1onActivity` (STR@0x000c9898) |
| 2 | `__init__` | 21044 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_3__init__` (STR@0x000cbf5c) |
| 3 | `textfontsizeup` | 20971 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_5textfontsizeup` (STR@0x000ca6bc) |
| 4 | `textfontsizedown` | 20884 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_7textfontsizedown` (STR@0x000ca678) |
| 5 | `updatefontinfo` | 20969 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_9updatefontinfo` (STR@0x000cd690) |
| 6 | `updatetextfont` | 20968 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_11updatetextfont` (STR@0x000ca634) |
| 7 | `update_progress` | 20970 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_13update_progress` (STR@0x000ca7a0) |
| 8 | `add_text` | 21010 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_15add_text` (STR@0x000ccf90) |
| 9 | `on_exec_print` | 20972 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_17on_exec_print` (line 23889) |
| 10 | `onDestroy` | 20974 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_19onDestroy` (STR@0x000ca5b4) |
| 11 | `onKeyEvent` | 20973 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_21onKeyEvent` (STR@0x000cbf1c) |
| 12 | `hidden` | 21043 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_23hidden` (STR@0x000cbea4) |
| 13 | `show` | 21095 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_25show` (STR@0x000cbe2c) |
| 14 | `is_showing` | 20976 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_27is_showing` (STR@0x000cbdac) |
| 15 | `clear` | 21067 | `__pyx_pw_13activity_main_22ConsolePrinterActivity_29clear` (line 24040) |

### 5.2 mdef Table (from activity_main_strings.txt:30924-30938)

```
__pyx_mdef_13activity_main_22ConsolePrinterActivity_1onActivity
__pyx_mdef_13activity_main_22ConsolePrinterActivity_3__init__
__pyx_mdef_13activity_main_22ConsolePrinterActivity_5textfontsizeup
__pyx_mdef_13activity_main_22ConsolePrinterActivity_7textfontsizedown
__pyx_mdef_13activity_main_22ConsolePrinterActivity_9updatefontinfo
__pyx_mdef_13activity_main_22ConsolePrinterActivity_11updatetextfont
__pyx_mdef_13activity_main_22ConsolePrinterActivity_13update_progress
__pyx_mdef_13activity_main_22ConsolePrinterActivity_15add_text
__pyx_mdef_13activity_main_22ConsolePrinterActivity_17on_exec_print
__pyx_mdef_13activity_main_22ConsolePrinterActivity_19onDestroy
__pyx_mdef_13activity_main_22ConsolePrinterActivity_21onKeyEvent
__pyx_mdef_13activity_main_22ConsolePrinterActivity_23hidden
__pyx_mdef_13activity_main_22ConsolePrinterActivity_25show
__pyx_mdef_13activity_main_22ConsolePrinterActivity_27is_showing
__pyx_mdef_13activity_main_22ConsolePrinterActivity_29clear
```

---

## 6. ConsolePrinterActivity State Machine

Two states: RUNNING (task executing) and COMPLETE (task finished).

```
   +----------+     task done    +-----------+
   | RUNNING  | --------------> | COMPLETE  |
   | (output) |                 | (output)  |
   +----+-----+                 +-----+-----+
        |                             |
        | M1/PWR                      | M2/OK
        | (cancel)                    v
        v                        finish()
    cancel + finish()
```

### 6.1 Screen Layout

**Title**: Set from bundle `'title'` parameter, or default `"Console"`

**Content**: Monospace scrolling text area (ConsoleView widget) — full screen, NO title bar visible
- Cyan/green text on black background
- No title bar — the console output fills the entire screen from top to bottom
- No button bar visible during execution
- Scrolls vertically as new output arrives

**Screenshot citations**:
- `lua_console_1.png` through `lua_console_10.png`: All show full-screen console with NO title bar, NO buttons. Cyan/green monospace text on black background. Output includes PM3 command prefix `[usb|script] pm3 -->`, status lines with `[+]`/`[=]` prefixes, error messages, and final `Nikola.D: 0` result code.
- `lua_console_10.png` (final state): Shows UID/ATQA/SAK data and `[+] finished hf_read` with `Nikola.D: 0`.

**Screenshot confirmation** (090-Lua-Resullts.png):
Shows monospace output:
```
[usb|script] pm3 --> script run
[+] executing lua /mnt/upan/luas
[=] args
ERROR:
Could not read file dumpdata.bin
ERROR:
Could not read file dumpdata.bin
[+] finished data_dumptohtml
Nikola.D: 0
```

The output shows PM3 command execution with `[+]`, `[=]`, `ERROR:` prefixed lines
and a final `Nikola.D: 0` result code.

**Button labels**:
- While RUNNING:
  - M1: `"Cancel"` (resources.py:50, button key `'cancel'`)
  - M2: `""` (empty, no right button)
- When COMPLETE:
  - M1: (unchanged)
  - M2: `"OK"` (set via setRightButton)

### 6.2 Key Behavior

From binary onKeyEvent (decompiled at ghidra_raw.txt:53311-54279):

- M1/PWR: cancel running task (if any), finish()
- UP: scroll up in ConsoleView
- DOWN: scroll down in ConsoleView
- M2/OK: if COMPLETE, finish(); otherwise no action

---

## 7. ConsolePrinterActivity __init__ (decompiled at ghidra_raw.txt:54281-56002)

The `__init__` accepts up to 3 positional parameters plus keyword arguments.
From the decompiled switch at ghidra_raw.txt:54323 (switch on param_2+8 = arg count):
- case 0: no positional args beyond self
- case 1: 1 positional arg (bundle/parent)
- case 2: 2 positional args
- case 3: 3 positional args

The `__init__` calls the parent class `__init__` (via `__Pyx_PyObject_Call`)
and initializes internal state:
- `_running = False`
- `_complete = False`
- `_console = None`
- `fontsize` (string at activity_main_strings.txt:22239)
- `textfontsizeup` / `textfontsizedown` methods for resizing

---

## 8. Font Size Management

The binary has dedicated methods for font size adjustment:

- `textfontsizeup` (decompiled at ghidra_raw.txt:16511-16840): Increases font size
- `textfontsizedown` (decompiled at ghidra_raw.txt:16179-16509): Decreases font size
- `updatetextfont` (decompiled at ghidra_raw.txt:15845-16177): Applies current font size to text widget
- `updatefontinfo` (decompiled at ghidra_raw.txt, symbol at STR@0x000cd690): Updates font metadata display

Internal attribute: `fontsize` (activity_main_strings.txt:22239)

These methods are NOT accessible via any key in the standard onKeyEvent handler based on the
decompiled onKeyEvent function. They may be invoked programmatically or via a non-standard path.

---

## 9. Output Methods

### 9.1 add_text (decompiled at ghidra_raw.txt, symbol STR@0x000ccf90)

Appends text to the ConsoleView. Called by PM3 task output callback.

### 9.2 on_exec_print (decompiled at ghidra_raw.txt, symbol at line 23889)

Callback from executor print events. Receives PM3 output and routes to add_text.

### 9.3 update_progress (decompiled at ghidra_raw.txt:17233-18191)

Updates progress display. Large function (~950 lines decompiled). Handles progress bar
rendering and percentage/remaining time display for long-running operations like key cracking.

### 9.4 show / hidden / is_showing

Visibility management:
- `show` (decompiled at ghidra_raw.txt:52721-53014): Makes console visible
- `hidden` (decompiled at ghidra_raw.txt:53016-53309): Hides console
- `is_showing` (decompiled at ghidra_raw.txt:52431-52719): Returns visibility state

### 9.5 clear (string table line 21067/24040)

Clears all text from the ConsoleView.

---

## 10. ConsolePrinterActivity Decompiled Function Cross-Reference

| Function | Start Line | End Line | Address |
|----------|-----------|----------|---------|
| `onActivity` | 6322 | 6400 | 0x00031d30 |
| `onDestroy` | 15586 | 15843 | 0x0003c2ec |
| `updatetextfont` | 15845 | 16177 | 0x0003c778 |
| `textfontsizedown` | 16179 | 16509 | 0x0003cd40 |
| `textfontsizeup` | 16511 | 16840 | 0x0003d384 |
| `update_progress` | 17233 | 18191 | 0x0003e0a4 |
| `is_showing` | 52431 | 52719 | 0x000659d0 |
| `show` | 52721 | 53014 | 0x00065ed0 |
| `hidden` | 53016 | 53309 | 0x000663cc |
| `onKeyEvent` | 53311 | 54279 | 0x000668c8 |
| `__init__` | 54281 | 56002 | 0x00067958 |

---

## 11. String Resources Summary

### Title strings (resources.py StringEN.title):
- `'lua_script'` -> `"LUA Script"` (line 97)

### Button strings (resources.py StringEN.button):
- `'cancel'` -> `"Cancel"` (line 50)

### Internal string table (activity_main_strings.txt):
- `path_lua_scripts` (line 21433) -- path to scripts directory
- `luascripts` (line 21930) -- directory name `"luascripts"`
- `lua_script` (line 21931) -- resource key
- `"script run "` (line 21910) -- PM3 command prefix
- `".lua"` (line 22613) -- file extension filter
- `fontsize` (line 22239) -- internal font size attribute
- `ConsolePrinterActivity` (line 21230)
- `LUAScriptCMDActivity` (line 21280)

---

## Corrections Applied

1. **Script list buttons**: Fixed from M1="", M2="OK" to NO buttons visible. Citations: `lua_script_1_10.png` and `lua_script_10_10.png` both show no button bar.
2. **Console view description**: Updated to document that the console is full-screen with NO title bar and NO buttons visible during execution. Text is cyan/green monospace on black background. Citations: `lua_console_1.png` through `lua_console_10.png`.

---

## Key Bindings

### LUAScriptCMDActivity.onKeyEvent (activity_main_ghidra_raw.txt line 53311)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| FILE_LIST | prev() | next() | prevPage() | nextPage() | runScript() | no-op | runScript() | finish() |

**Notes:**
- UP/DOWN scroll within page. LEFT/RIGHT navigate between pages (paginated list of .lua files).
- M2/OK launch ConsolePrinterActivity with `"script run <filename>"` PM3 command.
- PWR exits to main menu.
- Title updates with page indicator: "LUA Script X/Y".

### ConsolePrinterActivity.onKeyEvent (activity_main_ghidra_raw.txt line 53311)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| RUNNING | scrollUp() | scrollDown() | no-op | no-op | no-op | cancel + finish() | no-op | cancel + finish() |
| COMPLETE | scrollUp() | scrollDown() | no-op | no-op | finish() | finish() | finish() | finish() |

**Notes:**
- UP/DOWN scroll through console output in both states.
- While RUNNING: M1/PWR cancel the PM3 task and exit.
- When COMPLETE: M2/OK dismiss the console and finish.

**Source:** `src/lib/activity_main.py` lines 2019-2053 (LUAScript), lines 769-789 (ConsolePrinter).
