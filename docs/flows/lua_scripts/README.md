# LUA Scripts Flow — Phase 1 & Phase 2 Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task

Implement the **LUA Scripts** flow (`LUAScriptCMDActivity` + `ConsolePrinterActivity`) so that it matches the original firmware's behavior.

**Phase 1**: Build test scenarios from ground truth, validate against `--target=original`.
**Phase 2**: Implement open-source UI layer, validate against `--target=current`.

---

## TWO ABSOLUTE LAWS

### LAW 1: NO MIDDLEWARE
LUAScriptCMDActivity is a **file browser**. ConsolePrinterActivity is a **PM3 output display**. The `.so` modules handle script execution via `executor.startPM3Task('script run <name>', -1)`. Our Python activity code does NOT interpret script content, parse Lua output, or make RFID decisions.

If you find yourself writing Lua parsing logic, PM3 protocol code, or script-specific branching — **STOP. You are violating Law 1.**

### LAW 2: NO CHANGING SCENARIOS (Phase 2)
During Phase 2, test scenarios are **IMMUTABLE**. They are the acceptance criteria built from ground truth during Phase 1. If a scenario fails with `--target=current`, the bug is in YOUR implementation, not in the scenario.

---

## Architecture Overview

```
LUAScriptCMDActivity (file browser)
    │
    │ M2/OK → runScriptTask()
    │   Build: cmd = "script run <filename>"
    │   Bundle: {'cmd': cmd, 'title': 'LUA Script'}
    │   START(ConsolePrinterActivity, bundle)
    │
    ▼
ConsolePrinterActivity (PM3 output console)
    │
    │ Executes: executor.startPM3Task(bundle['cmd'], -1)
    │ Displays: executor.CONTENT_OUT_IN__TXT_CACHE (live polling)
    │ Full-screen: black bg, monospace text, NO title bar, NO button bar
    │
    │ PWR → cancel task + finish() → returns to FILE_LIST
    │ (or task completes → user presses any key → finish())
    │
    ▼
Returns to LUAScriptCMDActivity
```

---

## Essential Reading (READ ALL BEFORE ACTING)

1. `docs/HOW_TO_BUILD_FLOWS.md` — Phase 1 methodology
2. `docs/HOW_TO_INTEGRATE_A_FLOW.md` — Phase 2 integration guide
3. `docs/UI_Mapping/15_lua_script/README.md` — **PRIMARY UI SPEC** (404 lines). Complete method inventory, state machine, key bindings, console details.
4. `docs/Real_Hardware_Intel/trace_misc_flows_20260330.txt` lines 41-55 — Real device LUA flow trace (script run, cancel, retry, completion)
5. `docs/Real_Hardware_Intel/trace_misc_flows_session2_20260330.txt` lines 29-34 — Enhanced trace with full PM3 output
6. Post-mortems from completed flows (read for patterns):
   - `docs/flows/sniff/ui-integration/README.md` — QEMU canvas tracing, parser probing, threading model
   - `docs/flows/dump_files/README.md` — File browser pattern (CardWalletActivity — similar list UI)
   - `docs/flows/write/ui-integration/README.md` — DRM, cache patterns
   - `docs/flows/simulate/ui-integration/README.md` — Console-based output display

---

## Activities Involved

### LUAScriptCMDActivity (activity_main.so)

**Purpose**: File browser for `.lua` scripts in `/mnt/upan/luascripts/`.

**Methods** (from V1090_MODULE_AUDIT / activity_main_strings.txt):

| Method | Purpose |
|--------|---------|
| `getManifest` | Return activity metadata |
| `__init__` | Initialize activity |
| `onMultiPIUpdate` | Update title page indicator |
| `listLUAFiles` | Enumerate .lua files, filter, sort |
| `onResume` | Resume from pause |
| `onDestroy` | Clean up on exit |
| `runScriptTask` | Execute selected script via ConsolePrinterActivity |
| `onKeyEvent` | Handle button presses |

**Main Menu Position**: 13 (0-indexed). Use `GOTO:13` in test scripts.

### ConsolePrinterActivity (activity_main.so)

**Purpose**: Full-screen PM3 command output display. Shared by LUA, Read (key recovery), and Diagnosis flows.

**Methods** (15 total — see `docs/UI_Mapping/15_lua_script/README.md` Section 5.1):

| Method | Purpose |
|--------|---------|
| `onActivity` | Receive results from child activities |
| `__init__` | Initialize console |
| `textfontsizeup` / `textfontsizedown` | Zoom in/out |
| `add_text` | Append text to console |
| `on_exec_print` | Callback for executor print events |
| `onKeyEvent` | Handle key presses |
| `hidden` / `show` / `is_showing` | Visibility management |
| `clear` | Clear all console text |

---

## Ground Truth — Real Device Traces

### Trace 1: `trace_misc_flows_20260330.txt` lines 41-55

```
START(LUAScriptCMDActivity, None)
POLL stack=['dict', 'dict']                    ← ConsolePrinterActivity pushed immediately
PM3-TASK> script run hf_read                   ← PM3 command
PM3-CTRL> stop                                 ← User pressed PWR during execution
PM3-TASK< ret=-1                               ← Task cancelled
PM3-TASK> script run hf_read                   ← User re-ran the script
PM3-TASK< ret=1 \n[+] executing lua ...        ← Successful completion
FINISH(top=dict d=2)                           ← ConsolePrinterActivity finished
POLL stack=['dict']                            ← Back to LUAScriptCMDActivity
```

**Key observations**:
1. `START(LUAScriptCMDActivity, None)` — no bundle parameter
2. ConsolePrinterActivity is pushed (stack depth 2) after script selection
3. PM3 command: `script run hf_read` with `timeout=-1` (blocking)
4. PWR during execution: `stop` → `ret=-1` → user stays in console, can retry
5. Successful completion: `ret=1` with full script output in cache
6. Console finishes → returns to script list

### Trace 2: `trace_misc_flows_session2_20260330.txt` lines 29-34

```
START(LUAScriptCMDActivity, None)
POLL stack=['dict', 'dict']
PM3-TASK> script run hf_read timeout=-1
PM3-TASK< ret=1 \n[+] executing lua /mnt/upan/luascripts/hf_read.lua
    [+] args ''
    WORK IN PROGRESS - not expected to be functional yet
    Waiting for card... press Enter to quit
    Reading with 1
    Tag info
        ats : 00
        uid : 3AF73501
        ...
    [+] finished hf_read
FINISH(top=dict d=2)
POLL stack=['dict']
```

---

## PM3 Commands

| Command | Timeout | Purpose |
|---------|---------|---------|
| `script run <filename>` | -1 (blocking) | Execute Lua script on PM3 |

The filename is the script base name WITHOUT `.lua` extension.
Example: script file `hf_read.lua` → command `script run hf_read`

---

## Screen Specifications

### Screen 1: Script List (LUAScriptCMDActivity)

| Element | Value | Source |
|---------|-------|--------|
| Title | `"LUA Script X/Y"` (paginated) | resources.py: `'lua_script': 'LUA Script'` |
| Content | ListView, 5 items per page | FB: lua_script_1_10.png |
| Items | .lua filenames (extension stripped), sorted | listLUAFiles() |
| M1 | "" (invisible) | FB: no button bar visible |
| M2 | "" (invisible) | FB: no button bar visible |

**Key bindings**:

| Key | Action |
|-----|--------|
| UP | Scroll up in list |
| DOWN | Scroll down in list |
| LEFT | Previous page |
| RIGHT | Next page |
| M2/OK | `runScriptTask()` → launch ConsolePrinterActivity |
| PWR | `finish()` → exit to Main Menu |

**Script directory**: `/mnt/upan/luascripts/` — contains 47 `.lua` files on the device.

**Screenshot evidence**:
- `lua_script_1_10.png`: Title "LUA Script 1/10", 5 items, NO button bar
- `lua_script_10_10.png`: Title "LUA Script 10/10", 3 items (last page)
- `v1090_captures/090-Lua.png`: Title "LUA Script 1/18" (more scripts on real device)

### Screen 2: Console Output (ConsolePrinterActivity)

| Element | Value | Source |
|---------|-------|--------|
| Title | NONE (no title bar) | FB: lua_console_*.png |
| Content | Full-screen monospace, black background | ConsoleView(0,0,240,240) |
| Text color | Cyan/green on black | FB: lua_console_1.png |
| M1/M2 | Invisible but functional (zoom) | dismissButton(keep_bindings=True) |

**Key bindings**:

| Key | Action |
|-----|--------|
| UP / M2 | `textfontsizeup()` — zoom in (max 14) |
| DOWN / M1 | `textfontsizedown()` — zoom out (min 6) |
| RIGHT | Horizontal scroll right |
| LEFT | Horizontal scroll left |
| PWR | Cancel PM3 task + `finish()` → return to script list |

**Console output format** (from real device):
```
[usb|script] pm3 --> script run hf_read
[+] executing lua /mnt/upan/luascripts/hf_read.lua
[+] args ''
WORK IN PROGRESS - not expected to be functional yet
...
[+] finished hf_read

Nikola.D: 0
```

---

## Logic Tree — All Possible Paths

```
LUAScriptCMDActivity launched (GOTO:13)
├─ No scripts found
│   └─ LEAF: "No scripts found" toast, empty list
│
├─ Scripts found (FILE_LIST)
│   ├─ Navigation
│   │   ├─ LEAF: Scroll UP/DOWN within page
│   │   ├─ LEAF: Page LEFT/RIGHT between pages
│   │   └─ LEAF: Title updates "LUA Script X/Y"
│   │
│   ├─ PWR from FILE_LIST
│   │   └─ LEAF: finish() → Main Menu
│   │
│   └─ M2/OK → Execute script
│       └─ ConsolePrinterActivity launched
│           ├─ Script runs successfully (ret=1)
│           │   ├─ Output displayed in console
│           │   └─ LEAF: PWR → finish() → back to FILE_LIST
│           │
│           ├─ Script cancelled (ret=-1)
│           │   ├─ User presses PWR during execution
│           │   └─ LEAF: Task stopped → finish() → back to FILE_LIST
│           │
│           └─ Console navigation
│               ├─ LEAF: UP/M2 → zoom in
│               ├─ LEAF: DOWN/M1 → zoom out
│               └─ LEAF: LEFT/RIGHT → horizontal scroll
```

---

## Scenario Definitions

### Navigation Scenarios

| Scenario | Description | Validation Gates |
|----------|-------------|-----------------|
| `lua_list_display` | GOTO:13, verify script list shown | Title: "LUA Script", content: first script name, M1/M2 invisible |
| `lua_list_pagination` | Navigate pages with LEFT/RIGHT | Title changes: "1/Y" → "2/Y" → ... |
| `lua_list_scroll` | Scroll within page with UP/DOWN | Selection changes (highlight moves) |
| `lua_pwr_back` | PWR from script list | Activity finishes, returns to Main Menu |
| `lua_no_scripts` | Empty luascripts directory | Toast: "No scripts found" |

### Script Execution Scenarios

| Scenario | Description | Validation Gates |
|----------|-------------|-----------------|
| `lua_run_success` | Select script, run, completes | Console shows output, `[+] finished`, `Nikola.D: 0` |
| `lua_run_pwr_cancel` | Run script, PWR during execution | Task cancelled (ret=-1), returns to list |
| `lua_run_pwr_from_result` | Run script, wait for completion, PWR | Console closes, returns to list |

### Console Scenarios

| Scenario | Description | Validation Gates |
|----------|-------------|-----------------|
| `lua_console_no_title` | Verify console has no title bar | Title: None/empty, content: console text |
| `lua_console_output` | Verify PM3 output displayed | Content contains `script run`, `executing lua` |

---

## Fixture Design

Each scenario needs a `fixture.py` with PM3 mock responses:

```python
# Example: lua_run_success/fixture.py
SCENARIO_RESPONSES = {
    'script run hf_read': (1, '''[usb|script] pm3 --> script run hf_read
[+] executing lua /mnt/upan/luascripts/hf_read.lua
[+] args ''
WORK IN PROGRESS - not expected to be functional yet
Waiting for card... press Enter to quit
Reading with
1
Tag info
    ats : 00
    uid : 3AF73501
    data : :5
    manufacturer : Advanced Film Device Inc. Japan
    atqa : 0400
    sak : 8
    name : NXP MIFARE CLASSIC 1k | Plus 2k

[+] finished hf_read

Nikola.D: 0
'''),
}
DEFAULT_RETURN = 1
```

For navigation-only scenarios (no script execution), fixtures only need to exist as empty `SCENARIO_RESPONSES = {}`.

---

## Test Infrastructure

### Script seeding

Before each test, seed `/mnt/upan/luascripts/` with the appropriate `.lua` files:
- For list/pagination tests: seed multiple scripts (use the real 47 from the device)
- For empty test: ensure directory is empty
- For execution tests: seed the specific script being tested

The real device has 47 scripts. For pagination tests, use a subset that creates predictable page counts.

### Test common file

Create `tests/flows/lua_scripts/includes/lua_common.sh` following the pattern from `tests/flows/sniff/includes/sniff_common.sh`:
- `wait_for_ui_trigger` for polling content/title/button/toast
- Active polling every 500ms, NOT blind sleeps
- Content validation at EACH critical stage

### GOTO position

LUA Script is at main menu position **13** (0-indexed). Use `GOTO:13` in test scripts.

### Validation rules

For EACH scenario, validate at LEAST two of:
- Title (e.g., "LUA Script 1/10")
- Content text (e.g., script name, console output)
- Button state (M1/M2 visible/invisible/active/inactive)
- Toast content
- ProgressBar presence (if applicable)

State count is a SMOKE TEST only — never the primary validation.

---

## Running Tests

```bash
# Single scenario (Phase 1 — original)
TEST_TARGET=original bash tests/flows/lua_scripts/scenarios/lua_list_display/lua_list_display.sh

# Full suite (Phase 1 — original)
TEST_TARGET=original bash tests/flows/lua_scripts/test_lua_parallel.sh 1

# Full suite (Phase 2 — current)
TEST_TARGET=current bash tests/flows/lua_scripts/test_lua_parallel.sh 1

# Remote QEMU server
export SSHPASS=proxmark
sshpass -e rsync -az -e 'ssh -o StrictHostKeyChecking=no' \
  --exclude='_results' --exclude='.git' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:~/icopy-x-reimpl/
sshpass -e ssh -o StrictHostKeyChecking=no qx@178.62.84.144 \
  "cd ~/icopy-x-reimpl && TEST_TARGET=original bash tests/flows/lua_scripts/test_lua_parallel.sh 3"
```

Run test runs (>5 tests) on the QEMU server. Do NOT use blind sleeps — actively poll results every 60s.

---

## Implementation Notes for Phase 2

### ConsolePrinterActivity Gap

The current Python `ConsolePrinterActivity.onCreate()` reads the executor cache but does NOT execute the PM3 command from the bundle. The original `.so` calls `executor.startPM3Task(bundle['cmd'], -1)` to execute the script.

**Evidence**: Trace shows `PM3-TASK> script run hf_read timeout=-1` — the task is started by the activity, not by the launcher.

### Threading Model

From the Sniff flow post-mortem (`docs/flows/sniff/ui-integration/README.md`):
- Key events dispatch via `_tk_root.after(0, ...)` on the main tkinter thread
- `startBGTask` spawns daemon threads for PM3 operations
- State dumps run on the main thread — BG thread canvas operations may not be captured if too transient
- The original `.so` dispatches keys via serial buffer → hmi_driver thread (50ms poll)

### Key Files to Modify

| File | What to change |
|------|----------------|
| `src/lib/activity_main.py` | ConsolePrinterActivity (L733-828): add PM3 task execution from bundle |
| `tests/flows/lua_scripts/` | NEW: scenario scripts, fixtures, common.sh, parallel runner |

---

## Cross-References

- **Dump Files flow** (`docs/flows/dump_files/README.md`): Similar file browser pattern (CardWalletActivity). ListView pagination, UP/DOWN/OK/PWR navigation. Reference for how to build file-list test scenarios.
- **Sniff flow** (`docs/flows/sniff/ui-integration/README.md`): QEMU canvas tracing technique, parser probing, threading model. Critical for debugging UI parity issues.
- **Simulate flow** (`docs/flows/simulate/ui-integration/README.md`): SimulationTraceActivity shares `sniff.saveSniffData` — ConsolePrinterActivity is a similar "output display" activity.

---

## Definition of Done

### Phase 1
1. All scenario scripts built with fixtures
2. All scenarios pass with `--target=original`
3. Each scenario validates content, title, OR button state at every critical stage
4. Run >5 test runs on QEMU server to confirm stability

### Phase 2
1. All scenarios pass with `--target=current`
2. No middleware — LUAScriptCMDActivity/ConsolePrinterActivity only call `.so` functions
3. No scenario modifications
4. UI elements match original exactly (positions, colors, fonts from QEMU canvas trace)
5. No regressions on existing suites (Scan 45, Read 99, Write 63, Auto-Copy 52, Simulate 28, Erase 10, Sniff 28, Dump Files 35)

---

## Environment

- Branch: `feat/ui-integrating`
- Remote QEMU: `qx@178.62.84.144` (password: `proxmark`)
- Script directory: `/mnt/upan/luascripts/` (47 scripts on device)
- Main menu position: 13 (GOTO:13)
