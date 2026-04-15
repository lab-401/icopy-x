# HOW TO BUILD FLOW TESTS

This document is the complete reference for building flow tests for the iCopy-X v1.0.90 firmware reimplementation. It describes the methodology, architecture, and rules that govern every flow test.

Read this document **in full** before writing any test code.

---

## 1. PURPOSE

We run the **original v1.0.90 compiled .so modules** inside QEMU ARM user-mode emulation. We navigate the UI with real button presses. We provide **PM3 fixture responses** that match the patterns the .so modules look for. By varying the fixture responses, we navigate **100% of branches on the logic tree, down to every unique leaf**.

The purpose is **not** to reimplement the firmware logic. The purpose is to **prove** that we understand every path the original firmware can take, by exercising each path under controlled conditions and capturing the exact UI state at each step.

Every unique state — every title, button label, toast message, content line, scan cache value — is captured in a `scenario_states.json` file. This gives us a pixel-perfect, data-complete map of the firmware's behavior that can be used to build a 1:1 reimplementation.

---

## 2. GROUND TRUTH SOURCES

You may **ONLY** use these sources. Never guess. Never invent.

### 2.1 Original .so binaries
Location: `/mnt/sdcard/root2/root/home/pi/ipk_app_main/lib/*.so`
These are the Cython-compiled modules from the real v1.0.90 firmware. They run inside QEMU. They ARE the application logic. You never modify them.

### 2.2 Extracted strings from .so files
Location: `docs/v1090_strings/*.txt`
Every string embedded in every .so file, extracted with `strings`. These contain:
- **PM3 keywords**: The exact strings the .so uses in `hasKeyword()` and `getContentFromRegex()` calls
- **UI text**: Toast messages, button labels, screen titles
- **PM3 commands**: The exact commands the .so sends to the Proxmark3

Example from `hf14ainfo_strings.txt`:
```
MIFARE Classic 1K          ← hasKeyword match
MIFARE Classic 4K          ← hasKeyword match
MIFARE Ultralight          ← hasKeyword match
Magic capabilities : Gen 1a  ← hasKeyword match
BCC0 incorrect             ← hasKeyword match
Multiple tags detected     ← hasKeyword match
.*ATQA:(.*)\n              ← getContentFromRegex pattern
.*SAK:(.*)\[.*\n           ← getContentFromRegex pattern
hasKeyword                 ← confirms this module uses keyword matching
getContentFromRegexG       ← confirms this module uses regex extraction
```

Example from `lfsearch_strings.txt`:
```
Valid EM410x ID            ← hasKeyword match → type 8
Valid HID Prox ID          ← hasKeyword match → type 9
Valid Indala ID            ← hasKeyword match → type 10
Valid AWID ID              ← hasKeyword match → type 28(?)
Valid Viking ID            ← hasKeyword match
Valid GALLAGHER ID         ← hasKeyword match
No known 125/134 kHz tags found!  ← hasKeyword match → no LF tag
HID Prox - ([xX0-9a-fA-F]+)      ← getContentFromRegex pattern
```

### 2.3 Decompiled .so analysis
Location: `decompiled/`
Ghidra decompilation output. Contains function signatures, call graphs, and pseudocode. Use `decompiled/SUMMARY.md` for a high-level overview of every module's API.

Key information extractable:
- `actstack.get_activity_pck()` — returns the activity stack
- `actstack.Activity.getCanvas()` — returns the tkinter canvas
- `scan.getScanCache()` — returns scan results dict
- Canvas tag names: `tags_title`, `tags_btn_left`, `tags_btn_right`, `tags_btn_bg`

### 2.4 Real device traces
Location: `docs/traces/`
PM3 command logs and framebuffer captures from the real hardware. These are **calibration anchors** — they confirm that a path exists and show the exact PM3 command/response sequence. They do NOT replace the .so binary analysis.

### 2.5 UI Mapping
Location: `docs/UI_Mapping/`
Exhaustive per-activity documentation: screen layout, states, transitions, button labels, toast messages, key bindings. All derived from .so binary analysis.

---

## 3. HOW TO DERIVE THE LOGIC TREE

The logic tree for a flow is built in three steps.

### Step 1: Identify the PM3 commands

Read the string extraction file for the module (e.g., `docs/v1090_strings/scan_strings.txt`, `hf14ainfo_strings.txt`, `lfsearch_strings.txt`). Find all strings that look like PM3 commands:
```
hf 14a info
hf mf cgetblk
hf search
lf search
data save f
lf t55xx detect
```

Cross-reference with `decompiled/SUMMARY.md` to confirm which module calls which commands.

### Step 2: Identify the branch keywords

In the same string files, find all strings used with `hasKeyword` and `getContentFromRegex`. These are the decision points:

```python
# From hf14ainfo_strings.txt — the .so checks for these keywords:
"Multiple tags detected"      → return CODE_TAG_MULT
"MIFARE Classic 1K"          → type = M1_S50 (1 or 41)
"MIFARE Classic 4K"          → type = M1_S70 (0 or 25)
"MIFARE Mini"                → type = 26
"MIFARE Ultralight"          → redirect to hfmfuinfo
"MIFARE DESFire"             → type = 21
"Magic capabilities : Gen 1a" → gen1a = True
"Magic capabilities : Gen 2 / CUID" → gen2_cuid = True
"BCC0 incorrect"             → bbcErr = True
```

### Step 3: Build the tree

Each PM3 command is a node. Each keyword match is a branch. The tree looks like:

```
hf 14a info
├─ timeout (-1) → no HF tag, try hf search
├─ "Multiple tags detected" → CODE_TAG_MULT → toast "Multiple tags!"
├─ "MIFARE Classic 1K"
│  ├─ uid_len == 4 → type 1 (M1_S50_1K_4B)
│  │  ├─ "Magic capabilities : Gen 1a" → gen1a=True, type 43
│  │  └─ no Gen1a → type 1
│  └─ uid_len == 7 → type 42 (M1_S50_1K_7B)
├─ "MIFARE Classic 4K" → type 0 or 25
├─ "MIFARE Ultralight" → hf mfu info → sub-branches
├─ "MIFARE DESFire" → type 21
├─ "BCC0 incorrect" → bbcErr=True, type 40
├─ "Magic capabilities : Gen 2 / CUID" → type 39
├─ no keyword match → continue to hf search
│
hf search
├─ timeout (-1) → no HF tag, try lf search
├─ "Valid iCLASS" → type 17/18
├─ "Valid ISO15693" → type 19/46
├─ "Valid LEGIC" → type 20
├─ "Valid ISO14443-B" → type 22
├─ "No known/supported 13.56 MHz tags" → try lf search
│
lf search
├─ "Valid EM410x ID" → type 8
├─ "Valid HID Prox ID" → type 9
├─ ... (20+ LF types)
├─ "No known 125/134 kHz tags found!" → try T55XX detect
│  └─ lf_wav_filter → amplitude check → lf t55xx detect
│     ├─ "Valid T55xx" → type 23
│     └─ no match → CODE_TAG_NO
└─ no match → CODE_TAG_NO → toast "No tag found"
```

**Every leaf is a scenario.** Every branch that leads to a different UI state gets its own test.

---

## 4. HOW FIXTURES WORK

### 4.1 What a fixture IS

A fixture is a **data dictionary** that maps PM3 command substrings to response tuples:

```python
SCAN_MF_CLASSIC_1K_4B = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
    'hf mf cgetblk': (0, """[-] Can't set magic card block
[-] isOk:00
"""),
    '_default_return': 1,
}
```

Each value is `(return_code, response_text)`:
- `return_code = 0` → command executed, response is valid
- `return_code = -1` → command timed out (pipeline may stop)
- `response_text` → the exact text the .so will search with `hasKeyword()` / `getContentFromRegex()`

### 4.2 What a fixture is NOT

A fixture is **NEVER**:
- Logic or branching code
- Function calls or conditionals
- Commands that bypass the .so decision-making
- Modified versions of real PM3 responses

**ABSOLUTE RULE**: Fixtures are DATA ONLY. No decisions, no branching, no function calls, no bypass commands. The .so modules ARE the logic. The walker uses REAL button presses. Violating this produces false positives.

### 4.3 How the mock works

The PM3 mock in `minimal_launch_090.py` replaces `executor.startPM3Task`:

```python
def _pm3_mock(cmd, timeout=5000, listener=None, rework_max=2):
    time.sleep(_PM3_DELAY)
    for pat, val in _RESPONSES.items():
        if pat in cmd:  # substring match
            ret, resp = val
            executor.CONTENT_OUT_IN__TXT_CACHE = resp
            return ret if ret == -1 else 1
    return _DEFAULT_RET
```

When the .so calls `executor.startPM3Task('hf 14a info', timeout=5000)`, the mock:
1. Looks for a fixture key that is a substring of `'hf 14a info'`
2. Sets `CONTENT_OUT_IN__TXT_CACHE` to the response text
3. Returns `1` (success) or `-1` (timeout)
4. The .so then calls `executor.hasKeyword("MIFARE Classic 1K")` on that cached content
5. The keyword matches → the .so branches accordingly

### 4.4 The pipeline continuation rule

**CRITICAL**: The scan pipeline stops when `startPM3Task` returns `-1`. For tags detected in later stages (e.g., LF tags require `hf 14a info` → `hf search` → `lf search`), the earlier stages must return `0` with "no match" content, NOT `-1`.

```python
# WRONG — pipeline stops at hf 14a info:
SCAN_EM410X = {
    'lf sea': (0, "[+] Valid EM410x ID found!"),
    '_default_return': -1,  # hf 14a info returns -1 → STOP
}

# CORRECT — pipeline continues through all stages:
SCAN_EM410X = {
    'hf 14a info': HF14A_NO_TAG,  # (0, "no tags") — continues
    'hf sea': HFSEA_NO_TAG,       # (0, "no tags") — continues
    'lf sea': (0, "[+] Valid EM410x ID found!"),  # match!
    '_default_return': 1,
}
```

### 4.5 Where fixture response text comes from

The response text in a fixture must come from one of:
1. **Real PM3 output** from a real Proxmark3 device (captured via strace or direct)
2. **Real device traces** in `docs/traces/`
3. **PM3 documentation** (the exact format PM3 outputs)

The text must contain the **exact keywords** the .so searches for. These keywords are found in `docs/v1090_strings/*.txt`. If the .so searches for `"Valid EM410x ID"`, the fixture response MUST contain that exact string.

---

## 5. TEST ARCHITECTURE

### 5.1 Hierarchy

```
tests/
├── includes/
│   └── common.sh              # Shared: QEMU boot, capture, dedup, state dump
├── flows/
│   ├── scan/
│   │   ├── includes/
│   │   │   └── scan_common.sh # Scan-specific: GOTO:2, capture timing
│   │   ├── scenarios/
│   │   │   ├── scan_no_tag/
│   │   │   │   └── scan_no_tag.sh
│   │   │   ├── scan_mf_classic_1k_4b/
│   │   │   │   └── scan_mf_classic_1k_4b.sh
│   │   │   └── ... (one dir per scenario)
│   │   └── test_scans.sh      # Runs all scan scenarios
│   ├── read/
│   │   ├── includes/
│   │   │   └── read_common.sh
│   │   ├── scenarios/
│   │   └── test_reads.sh
│   ├── write/
│   └── auto-copy/
└── test_all_flows.sh          # Runs all flows
```

### 5.2 What is a "Flow"

A **flow** is a top-level firmware feature: Scan Tag, Read Tag, Write Tag, Auto Copy, Erase Tag, etc. Each flow maps to one or more activities in the firmware.

### 5.3 What is a "Scenario"

A **scenario** is one specific path through the logic tree. It has:
- **One fixture**: A specific set of PM3 responses
- **One expected outcome**: A specific UI state (title, buttons, toast, content)
- **One test script**: Boots QEMU, navigates to the flow, runs with the fixture, captures results

Examples of scenarios for the Scan flow:
- `scan_no_tag` — no tag present, all PM3 commands timeout
- `scan_mf_classic_1k_4b` — MIFARE Classic 1K detected via `hf 14a info`
- `scan_em410x` — EM410x detected via `lf search` (requires 3 prior stages to pass-through)
- `scan_bcc0_incorrect` — HF tag with BCC0 error flag
- `scan_gen2_cuid` — Magic Gen2 CUID card
- `scan_multi_tags` — Multiple tags detected simultaneously

### 5.4 Scenario script structure

Every scenario script is minimal:

```bash
#!/bin/bash
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_no_tag"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario "no_tag" 3
```

Arguments to `run_scan_scenario`:
1. Fixture key (maps to `ALL_SCAN_SCENARIOS['no_tag']` in `pm3_fixtures.py`)
2. Minimum unique states to PASS (default 3)

### 5.5 Output structure

Each scenario produces:
```
_results/scan/scenarios/scan_no_tag/
├── screenshots/
│   ├── state_001.png      # Deduplicated unique screen states
│   ├── state_002.png
│   └── ...
├── logs/
│   └── scenario_log.txt   # Full QEMU stdout (PM3 commands, state transitions)
├── scenario_states.json    # Complete UI state dump per unique screen
└── result.txt             # "PASS: 5 unique states" or "FAIL: ..."
```

### 5.6 scenario_states.json

This is the critical output. For each unique screen state, it records:

```json
{
  "scenario": "scan_mf_classic_1k_4b",
  "states": [
    {
      "state": 1,
      "screenshot": "state_001.png",
      "title": "Scan Tag",
      "M1": null,
      "M2": "Scanning...",
      "toast": null,
      "content_text": [],
      "scan_cache": null,
      "executor": {"pm3_running": false, "last_content": ""}
    },
    {
      "state": 5,
      "screenshot": "state_005.png",
      "title": "Scan Tag",
      "M1": "Rescan",
      "M2": "Simulate",
      "toast": "Tag Found",
      "content_text": [
        {"text": "ISO14443-A", "x": 18, "y": 48},
        {"text": "MIFARE Classic 1K", "x": 18, "y": 82},
        {"text": "UID: 2C AD C2 72", "x": 18, "y": 128}
      ],
      "scan_cache": {
        "found": "True",
        "uid": "'2CADC272'",
        "type": "1"
      },
      "executor": {"last_content": "[+] MIFARE Classic 1K..."}
    }
  ]
}
```

This is NOT OCR. These values are extracted directly from the live application's canvas, activity stack, and module variables.

---

## 6. QEMU NAVIGATION

### 6.1 Available commands

Commands are sent via `send_key`:

| Command | Effect |
|---------|--------|
| `GOTO:N` | Jump to menu item N (0=AutoCopy, 1=DumpFiles, 2=ScanTag, 3=ReadTag, ...) |
| `UP` / `DOWN` | Navigate lists |
| `OK` | Confirm / Enter |
| `M1` / `M2` | Left / Right button press |
| `PWR` | Back / Exit (universal) |
| `TOAST_CANCEL` | Dismiss toast overlay (deletes canvas mask items) |
| `STATE_DUMP` | Capture full app state to JSON |
| `FINISH` | Exit current activity |

### 6.2 Boot sequence

Every scenario follows this sequence:
1. `clean_scenario` — kill old QEMU, clear results
2. `generate_mock` — create fixture file from `pm3_fixtures.py`
3. `boot_qemu` — start QEMU with fixture loaded
4. `wait_for_hmi` — poll until Tk window renders and HMI key bindings are active
5. Navigation commands (e.g., `GOTO:2` for Scan Tag)
6. `capture_frames` — screenshot + STATE_DUMP at 100ms intervals
7. `TOAST_CANCEL` — dismiss any toast overlay
8. More `capture_frames` for clean result screen
9. `dedup_screenshots` — hash raw pixels (masking battery icon), keep unique states
10. `report_pass` / `report_fail`

### 6.3 The QEMU matches the real device

The QEMU emulation has been validated against real device traces. The .so modules run identically. The PM3 mock provides the same interface as the real PM3 executor. The HMI key injection matches the real serial protocol.

**If you think something is "broken in QEMU" or "broken at the C level" — you are wrong.** The QEMU has been tested and proven to match 100% of the real device's behavior. If a test fails, the problem is in your fixture, your navigation, or your understanding of the logic tree.

---

## 7. DYNAMIC FLOW CONTROL — UI TRIGGERS

### 7.1 The Problem with Fixed Timing

A multi-phase flow (e.g., Read = scan phase + read phase) cannot use fixed `sleep` delays between phases. The duration of each phase varies by scenario — a MIFARE Classic key cracking flow takes far longer than an EM410x ID read. Fixed delays either miss the transition (too short) or waste time (too long).

### 7.2 Trigger on UI Strings, Not PM3 Commands

**Do NOT poll PM3 command counts.** That is middleware — you are making assumptions about what the .so does internally.

**DO trigger on the EXACT strings the .so renders on screen.** When a phase completes, the .so calls `showButton()` to update button labels and/or `showScanToast()` / `showReadToast()` to display result messages. These strings are defined in `resources.so` and documented in the UI Mapping. They are the .so's own signal that a phase is complete.

### 7.3 The `field:value` Trigger Format

Every trigger must specify BOTH the UI field and the expected value, to avoid false positives:

```
field:value
```

Where `field` is one of:
- `M1` — Left button label
- `M2` — Right button label
- `toast` — Toast overlay text
- `content` — Any text in the content area

**Examples:**

| Trigger | Meaning | Source |
|---------|---------|--------|
| `M2:Read` | Scan complete (success), M2 button shows "Read" | `resources.button.read` via `showButton()` |
| `M2:Rescan` | Scan complete (fail), M2 shows "Rescan" | `resources.button.rescan` via `showButton()` |
| `M1:Rescan` | Scan complete (any outcome) | `resources.button.rescan` via `showButton()` |
| `M1:Reread` | Read complete (success or fail) | `resources.button.reread` via `showButton()` |
| `M1:Verify` | Write complete | `resources.button.verify` via `showButton()` |
| `toast:Tag Found` | Scan found a tag | `resources.toastmsg.tag_found` via `showScanToast()` |
| `toast:No tag found` | Scan found nothing | `resources.toastmsg.no_tag_found` via `showScanToast()` |
| `toast:File saved` | Read saved successfully | `resources.toastmsg.read_ok_1` via `showReadToast()` |
| `toast:Read Failed` | Read failed | `resources.toastmsg.read_failed` via `showReadToast()` |
| `toast:Write successful` | Write succeeded | `resources.toastmsg.write_success` via toast |
| `content:ChkDIC` | Key checking in progress | `resources.procbarmsg.ChkDIC` via progress bar |
| `content:Scanning...` | Scan in progress | `resources.procbarmsg.scanning` via progress bar |

**Why `field:value` matters:** Without the field qualifier, searching for `"Read"` would match the title "Read Tag", the list item "Read Tag", and the M2 button "Read" — causing false-positive triggers. With `M2:Read`, only the M2 button label is checked.

### 7.4 Where Trigger Strings Come From

Every trigger string MUST come from the original .so, not from guessing. The sources are:

1. **`tools/qemu_shims/resources.py`** — Contains all UI strings: `button`, `title`, `toastmsg`, `tipsmsg`, `procbarmsg`. These are the EXACT strings the .so renders.

2. **`docs/UI_Mapping/<activity>/README.md`** — Documents every state's button labels, toast messages, and content text. Each state transition shows what M1/M2/toast values appear.

3. **`docs/v1090_strings/<module>_strings.txt`** — Raw strings from the .so binaries. Search for `text_` prefixed attributes (e.g., `text_tag_found`, `text_read_ok_1`, `text_reread`) which are the .so's cached string references.

### 7.5 Triggers are Scenario-Specific

Different scenarios trigger different strings. Each scenario script MUST specify its own triggers:

```bash
# Happy path: scan finds tag → read succeeds
run_read_scenario "mf1k_all_default_keys" 3 "M2:Read" "M1:Reread"

# Fail path: scan finds nothing → no read phase
run_read_scenario "mf1k_no_tag" 3 "M1:Rescan" "M1:Rescan"

# Partial read: scan finds tag → read partial success
run_read_scenario "mf1k_partial_read" 3 "M2:Read" "M1:Reread"
```

The trigger strings change because the .so's `showButton()` renders different labels depending on the outcome. The scenario author must know what the .so will display for their specific fixture — this comes from the logic tree and UI mapping.

### 7.6 How `wait_for_ui_trigger` Works

The test infrastructure provides `wait_for_ui_trigger`:

```bash
wait_for_ui_trigger "M2:Read" 30 "${raw_dir}" frame_idx
```

This function:
1. Captures a screenshot + triggers STATE_DUMP every 0.5 seconds
2. Reads the STATE_DUMP JSON
3. Checks the specified field (`M2`) for the target value (`Read`)
4. Returns 0 when found, or 1 on timeout

The STATE_DUMP extracts M1, M2, toast, and content text directly from the live tkinter canvas — not OCR, not log parsing. These are the real values the .so set via `setLeftButton()`, `setRightButton()`, and canvas text items.

### 7.7 Multi-Phase Flow Pattern

A flow with multiple phases (e.g., Read = scan + read) follows this pattern:

```bash
# Phase 1: Start scan
send_key "OK"

# Wait for scan to complete — detected by button label change
wait_for_ui_trigger "${scan_trigger}" 30 "${raw_dir}" frame_idx

# Transition: dismiss toast, press button for next phase
send_key "TOAST_CANCEL"
sleep 2
send_key "M2"

# Phase 2: Wait for read to complete — detected by button label change
wait_for_ui_trigger "${read_trigger}" 60 "${raw_dir}" frame_idx

# Capture final result
send_key "TOAST_CANCEL"
```

Each `wait_for_ui_trigger` captures frames continuously until the .so signals completion by changing the UI. No fixed delays. No PM3 polling. The .so drives the timing.

---

## 8. RULES

### 8.1 NEVER guess or invent

You never need to guess. ALL information to navigate every logic tree branch is provided in the ground truth sources. If you don't know what keyword a module checks for, read `docs/v1090_strings/<module>_strings.txt`. If you don't know what PM3 command a module sends, read `decompiled/SUMMARY.md`.

### 8.2 NEVER put logic in fixtures

Fixtures are DATA ONLY. The .so modules ARE the logic. You provide data, the .so makes decisions. If you find yourself writing `if/else`, function calls, or conditional responses in a fixture — STOP. You are doing it wrong.

### 8.3 NEVER modify the mock's command matching

The mock uses simple substring matching: `if pat in cmd`. Do not change the matching order, add extra commands, or remove commands. The logic tree and fixtures are derived from ground truth. Modifying them will never fix a problem — it will create false positives.

### 8.4 Enumerate ALL paths

Every scenario must cover one unique leaf on the logic tree. This means:
- **Happy paths**: Tag found, read success, write success
- **Fail paths**: No tag, timeout, wrong type, card lost
- **Edge cases**: BCC0 error, Gen1a, Gen2 CUID, multiple tags, static nonce
- **Every tag type**: Each of the 44+ tag types that can be detected

If there are N leaf nodes on the logic tree, there must be N scenarios.

### 8.5 When you are stuck

If your fixture is written but the test won't pass:

**DO THIS (in this EXACT order):**
1. Check the QEMU log (`scenario_log.txt`) — it shows every PM3 command, response, and error
2. **MANDATORY: Check the real device traces FIRST.** Read ALL files in `docs/Real_Hardware_Intel/`:
   - `full_read_write_trace_20260327.txt` — **BEST TRACE**: complete Read+Write with every PM3 command, activity transition, scan cache update, and stack state. Shows that ReadListActivity handles scan+read internally (no ReadActivity push), WarningWriteActivity→WriteActivity push sequence, write block order, verify phase.
   - `V1090_REAL_DEVICE_TRACES.md` — activity transitions, PM3 command sequences, key facts
   - `write_flow_20260326/` — full app strace + PM3 trace + 271 framebuffer screenshots
   - `write_flow_trace_20260326/` — write-specific traces
   - `lf_read_trace_20260326.txt` — LF read strace
   - `Screenshots/` — real device framebuffer captures
   These traces show EXACTLY what the real device does. Every PM3 command, every activity transition, every response. If the answer exists anywhere, it is HERE.
3. Re-read the .so string extractions for the relevant module (`docs/v1090_strings/`)
4. Check the UI Mapping (`docs/UI_Mapping/`) for the activity in question
5. Assume you missed something in the logic tree — re-derive it from step 1
6. **Run a live trace on the real device.** See `docs/HOW_TO_RUN_LIVE_TRACES.md` for the complete procedure. This captures activity transitions, PM3 commands, scan cache, and stack state from the RUNNING app with zero guesswork. Ask the user to establish the SSH tunnel and perform the flow on the physical device while the tracer captures.

**NEVER DO THIS:**
1. Write middleware or logic in fixtures
2. Change the mock's command matching order
3. Add synthetic commands that the .so doesn't send
4. Remove commands from fixtures
5. Assume QEMU is broken

---

## 9. FLOW BOUNDARIES

When building a flow test, you must define where the test **starts** and where it **stops**. The user sets these boundaries.

### 9.1 Proposing boundaries

Before building scenarios, propose the boundary to the user. Example for Scan flow:

> "The Scan Tag flow starts when ScanActivity enters SCANNING state and ends when the scan result is displayed. After scan completion, the UI shows M1='Rescan' and M2='Simulate'. Should I:
> - Include 'Rescan' scenarios? (This re-enters the scan loop)
> - Include 'Simulate' button? (This transitions to SimulationActivity — a different flow)
> - Include the back-navigation via PWR?"

The user's answer for the Scan flow was:
- Do NOT iterate into Rescan (infinite loop)
- Do NOT follow Simulate (separate flow)
- The test ends at the result screen with M1/M2 visible

### 9.2 Cross-flow transitions

Many flows lead into other flows:
- **Scan** → Simulate (via M2 on result)
- **Read** → Write (via M2 on read success)
- **Read** → Dump Files (saves file)
- **Auto Copy** → Read → Write (automated pipeline)

Each transition point is a potential boundary. Always confirm with the user.

---

## 10. WORKED EXAMPLE: BUILDING THE SCAN FLOW

This section walks through exactly how the 44 scan scenarios were built.

### Step 1: Read the UI Mapping

`docs/UI_Mapping/03_scan_tag/README.md` documents:
- ScanActivity's 5 states: IDLE, SCANNING, SCAN_RESULT_FOUND, SCAN_RESULT_NOT_FOUND, SCAN_RESULT_MULTI
- Menu position: 2 (so `GOTO:2` enters it)
- Button labels per state
- Toast messages per outcome

### Step 2: Extract keywords from .so strings

From `hf14ainfo_strings.txt`:
```
MIFARE Classic 1K, MIFARE Classic 4K, MIFARE Mini, MIFARE Ultralight,
MIFARE DESFire, MIFARE Plus, Magic capabilities : Gen 1a,
Magic capabilities : Gen 2 / CUID, BCC0 incorrect, Multiple tags detected
```

From `lfsearch_strings.txt`:
```
Valid EM410x ID, Valid HID Prox ID, Valid Indala ID, Valid AWID ID,
Valid IO Prox ID, Valid Viking ID, Valid Pyramid ID, Valid FDX-B ID,
Valid GALLAGHER ID, Valid Jablotron ID, Valid KERI ID, Valid NEDAP ID,
Valid Noralsy ID, Valid PAC/Stanley ID, Valid Paradox ID, Valid Presco ID,
Valid Visa2000 ID, Valid Hitag, Valid NexWatch ID,
Valid Guardall G-Prox II ID, Valid Securakey ID,
No known 125/134 kHz tags found!
```

From `hfsearch_strings.txt`:
```
Valid iCLASS, Valid ISO15693, Valid LEGIC Prime, Valid ISO14443-B,
Valid Topaz, Valid ISO18092 / FeliCa,
No known/supported 13.56 MHz tags found
```

### Step 3: Build one fixture per keyword match

Each keyword match = one leaf = one scenario = one fixture:

```python
# Leaf: "MIFARE Classic 1K" + uid_len=4 + no Gen1a
SCAN_MF_CLASSIC_1K_4B = {
    'hf 14a info': (0, "...[+] MIFARE Classic 1K...UID: 2C AD C2 72..."),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
}

# Leaf: "Valid EM410x ID" (requires passing through HF stages)
SCAN_EM410X = {
    'hf 14a info': HF14A_NO_TAG,   # pass-through
    'hf sea': HFSEA_NO_TAG,        # pass-through
    'lf sea': (0, "...[+] Valid EM410x ID found!..."),
}

# Leaf: no tag (all stages timeout)
SCAN_NO_TAG = {
    '_default_return': -1,
}
```

### Step 4: Register in ALL_SCAN_SCENARIOS

```python
ALL_SCAN_SCENARIOS = {
    'no_tag': SCAN_NO_TAG,
    'mf_classic_1k_4b': SCAN_MF_CLASSIC_1K_4B,
    'em410x': SCAN_EM410X,
    # ... 44 total
}
```

### Step 5: Create scenario scripts

For each key in `ALL_SCAN_SCENARIOS`, create:
```
tests/flows/scan/scenarios/scan_<key>/scan_<key>.sh
```

### Step 6: Run and verify

```bash
bash tests/flows/scan/test_scans.sh
```

Result: 44/44 PASS, 13-16 unique states per scenario, full `scenario_states.json` with title, M1, M2, toast, content, scan_cache, executor state.

---

## 11. COMPLETE TYPE CODE TABLE

Every tag type has a numeric code used throughout the firmware. The `_tag_type` field in fixtures maps to these codes. The detection keyword and PM3 command chain that produces each type:

| Code | Name | Detection Module | Keyword in PM3 Response | PM3 Command Chain |
|------|------|-----------------|------------------------|-------------------|
| 0 | M1_S70_4K_4B | hf14ainfo | `MIFARE Classic 4K` + uid_len=4 | `hf 14a info` → `hf mf cgetblk` |
| 1 | M1_S50_1K_4B | hf14ainfo | `MIFARE Classic 1K` + uid_len=4 | `hf 14a info` → `hf mf cgetblk` |
| 2 | ULTRALIGHT | hfmfuinfo | `hf mfu info` TYPE contains "Ultralight" (not C/EV1) | `hf 14a info` → `hf mfu info` |
| 3 | ULTRALIGHT_C | hfmfuinfo | `hf mfu info` TYPE contains "Ultralight C" | `hf 14a info` → `hf mfu info` |
| 4 | ULTRALIGHT_EV1 | hfmfuinfo | `hf mfu info` TYPE contains "Ultralight EV1" | `hf 14a info` → `hf mfu info` |
| 5 | NTAG213_144B | hfmfuinfo | `hf mfu info` TYPE contains "NTAG 213" | `hf 14a info` → `hf mfu info` |
| 6 | NTAG215_504B | hfmfuinfo | `hf mfu info` TYPE contains "NTAG 215" | `hf 14a info` → `hf mfu info` |
| 7 | NTAG216_888B | hfmfuinfo | `hf mfu info` TYPE contains "NTAG 216" | `hf 14a info` → `hf mfu info` |
| 8 | EM410X_ID | lfsearch | `Valid EM410x ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 9 | HID_PROX_ID | lfsearch | `Valid HID Prox ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 10 | INDALA_ID | lfsearch | `Valid Indala ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 11 | IO_PROX_ID | lfsearch | `Valid IO Prox ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 12 | GPROX_II_ID | lfsearch | `Valid Guardall G-Prox II ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 13 | SECURAKEY_ID | lfsearch | `Valid Securakey ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 14 | VIKING_ID | lfsearch | `Valid Viking ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 15 | PYRAMID_ID | lfsearch | `Valid Pyramid ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 16 | PARADOX_ID | lfsearch | `Valid Paradox ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 17 | ICLASS_LEGACY | hfsearch | `Valid iCLASS tag` | `hf 14a info` → `hf sea` |
| 18 | ICLASS_ELITE | hfsearch | `Valid iCLASS tag` (+ key check cascade) | `hf 14a info` → `hf sea` |
| 19 | ISO15693_ICODE | hfsearch | `Valid ISO15693` | `hf 14a info` → `hf sea` |
| 20 | LEGIC_MIM256 | hfsearch | `Valid LEGIC Prime` | `hf 14a info` → `hf sea` |
| 21 | FELICA | hfsearch | `Valid ISO18092 / FeliCa` | `hf 14a info` → `hf sea` |
| 22 | ISO14443B | hfsearch | `Valid ISO14443-B` | `hf 14a info` → `hf sea` |
| 23 | T55X7_ID | lft55xx | `Valid T55xx` (via lf_wav_filter gatekeeper) | `hf 14a info` → `hf sea` → `lf sea` → `data save f` → `lf t55xx detect` |
| 24 | EM4305 | scan | `Chipset detection: EM4x05` or `lf em 4x05_info` | `hf 14a info` → `hf sea` → `lf sea` → special EM4305 path |
| 25 | M1_MINI | hf14ainfo | `MIFARE Mini` | `hf 14a info` → `hf mf cgetblk` |
| 26 | M1_S50_1K_4B (alt) | hf14ainfo | `MIFARE Classic 1K` variant | `hf 14a info` |
| 27 | TOPAZ | hfsearch | `Valid Topaz` | `hf 14a info` → `hf sea` |
| 28 | FDX_B_ID | lfsearch | `Valid FDX-B ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 29 | GALLAGHER_ID | lfsearch | `Valid GALLAGHER ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 30 | JABLOTRON_ID | lfsearch | `Valid Jablotron ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 31 | KERI_ID | lfsearch | `Valid KERI ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 32 | NEDAP_ID | lfsearch | `Valid NEDAP ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 33 | NORALSY_ID | lfsearch | `Valid Noralsy ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 34 | PAC_ID | lfsearch | `Valid PAC/Stanley ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 35 | PRESCO_ID | lfsearch | `Valid Presco ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 36 | VISA2000_ID | lfsearch | `Valid Visa2000 ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 37 | HITAG_ID | lfsearch | `Valid Hitag` | `hf 14a info` → `hf sea` → `lf sea` |
| 38 | AWID_ID | lfsearch | `Valid AWID ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 39 | GEN2_CUID | hf14ainfo | `Magic capabilities : Gen 2 / CUID` | `hf 14a info` |
| 40 | BCC0_INCORRECT | hf14ainfo | `BCC0 incorrect` (truncated response, no type classification) | `hf 14a info` |
| 41 | M1_S70_4K_7B | hf14ainfo | `MIFARE Classic 4K` + uid_len=7 | `hf 14a info` → `hf mf cgetblk` |
| 42 | M1_S50_1K_7B | hf14ainfo | `MIFARE Classic 1K` + uid_len=7 | `hf 14a info` → `hf mf cgetblk` |
| 43 | M1_POSSIBLE_4B | hf14ainfo | `MIFARE Classic` + `MIFARE Plus` (compound) | `hf 14a info` |
| 44 | M1_GEN1A | hf14ainfo | `Magic capabilities : Gen 1a` | `hf 14a info` → `hf mf cgetblk` |
| 45 | NEXWATCH_ID | lfsearch | `Valid NexWatch ID` | `hf 14a info` → `hf sea` → `lf sea` |
| 46 | ISO15693_ST | hfsearch | `Valid ISO15693` + manufacturer contains "ST" | `hf 14a info` → `hf sea` |
| 47 | ICLASS_SE | hfsearch | `Valid iCLASS tag` (SE requires hardware USB reader) | `hf 14a info` → `hf sea` |

---

## 12. ADVANCED DETECTION PATHS

### 12.1 Ultralight/NTAG sub-type routing (hfmfuinfo)

When `hf 14a info` returns `"MIFARE Ultralight"` or `"NTAG"`, the scan pipeline calls `hf mfu info`. The response contains a `TYPE:` field that determines the sub-type:

```
hf mfu info response → hasKeyword checks:
  TYPE: contains "NTAG 213"        → type 5 (NTAG213_144B)
  TYPE: contains "NTAG 215"        → type 6 (NTAG215_504B)
  TYPE: contains "NTAG 216"        → type 7 (NTAG216_888B)
  TYPE: contains "Ultralight C"    → type 3 (ULTRALIGHT_C)
  TYPE: contains "Ultralight EV1"  → type 4 (ULTRALIGHT_EV1)
  TYPE: contains "Ultralight" (plain) → type 2 (ULTRALIGHT)
  TYPE: "Unknown"                  → type 2 (fallback)
```

Keywords found in `hfmfuinfo_strings.txt`: `NTAG 213`, `NTAG 215`, `NTAG 216`, `NTAG213_144B`, `NTAG215_504B`, `NTAG216_888B`, `TYPE:`, `TYPE: Unknown`.

Fixture for NTAG215 requires two PM3 commands:
```python
SCAN_NTAG215 = {
    'hf 14a info': (0, "...[+] MIFARE Ultralight...[+] ATQA: 00 44...SAK: 00..."),
    'hf mfu info': (0, "...[=] TYPE: NTAG 215 (504 bytes)..."),
    'hf mf cgetblk': CGETBLK_NOT_GEN1A,
}
```

### 12.2 Route C: hf search → redirect to hf 14a info

For some types, `hf search` detects a tag before `hf 14a info` does. Specifically:
- `hf search` returns `"MIFARE"` → the scan pipeline redirects to `scan_14a()` which calls `hf 14a info`
- This happens for DESFire and HF14A_OTHER types

For **DESFire**: `hf search` → "MIFARE" → `hf 14a info` → "MIFARE DESFire" → type 21.
For **HF14A_OTHER**: `hf search` → "MIFARE" → `hf 14a info` → no specific MIFARE sub-type match → type 40.

This means the fixture needs BOTH `hf sea` (with "MIFARE") and `hf 14a info` (with specific type):
```python
SCAN_MF_DESFIRE = {
    'hf 14a info': (0, "...[+] MIFARE DESFire..."),
    'hf sea': (0, "...MIFARE..."),  # triggers redirect
}
```

### 12.3 T55XX multi-step detection pipeline

The T55XX detection follows a 5-step pipeline. ALL steps must be in the fixture:

```
Step 1: hf 14a info → HF14A_NO_TAG (ret=0, no match → continue)
Step 2: hf sea → HFSEA_NO_TAG (ret=0, "No known/supported" → continue to LF)
Step 3: lf sea → (ret=0, "No known 125/134 kHz tags found!" → check T55XX)
Step 4: data save f /tmp/lf_trace_tmp → (ret=0, mock auto-creates .pm3 file with amplitude > 90)
Step 5: lf t55xx detect → (ret=0, "[+] Valid T55xx tag" → type 23)
```

The `data save f` command is special: the PM3 mock automatically creates the `.pm3` waveform file with amplitude=240 (well above the lf_wav_filter threshold of 90). You do NOT need to add logic for this — the mock handles it.

### 12.4 EM4305 detection path

EM4305 has its own detection function `scan_em4x05()` in scan.so. It uses `lf em 4x05_info` directly, NOT the `lf search` → keyword pattern. The fixture needs:
```python
SCAN_EM4305 = {
    'hf 14a info': HF14A_NO_TAG,
    'hf sea': HFSEA_NO_TAG,
    'lf sea': LFSEA_NO_TAG,  # "No known 125/134 kHz tags found!" — not via lf search
    'lf em 4x05_info': (0, "...[+] Chipset detection: EM4x05..."),
}
```

### 12.5 iClass key cascade

iClass detection involves a 3-key check after `hf search` returns "Valid iCLASS tag":
1. Try key `AFA785A7DAB33378` (legacy key)
2. Try key `2020666666668888` (alternate)
3. Try key `6666202066668888` (alternate)
4. If none work → dictionary attack via `hf iclass chk`

The fixture needs `hf iclass rdbl` entries for each key attempt. iClass SE (type 47) requires a USB hardware reader and cannot be tested under QEMU — it is detected as ELITE (type 18) under emulation.

### 12.6 BCC0 incorrect — truncated response

When a card has BCC0 error, the `hf 14a info` response is TRUNCATED. It does NOT contain "Possible types:" or any MIFARE sub-type keyword. The .so sets `bbcErr=True` and classifies as type 40 (HF14A_OTHER) without further type classification:

```python
SCAN_BCC0_INCORRECT = {
    'hf 14a info': (0, """[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[!] BCC0 incorrect, expected 0x2C != 0xFF
"""),  # NOTE: NO "Possible types:" section, NO "MIFARE Classic"
    '_tag_type': 40,  # Goes to HF14A_OTHER due to BCC0 error
}
```

### 12.7 Compound keyword conditions

Some types require MULTIPLE keywords in one response:
- **M1_POSSIBLE_4B** (type 43): `"MIFARE Classic"` AND `"MIFARE Plus"` (ambiguous card)
- **M1_POSSIBLE_7B** (type 44): Same but uid_len=7
- These trigger when the card COULD be Classic or Plus — the .so cannot distinguish

---

## 13. FIXTURE METADATA FIELDS

Every fixture dict can include these metadata fields (prefixed with `_`):

| Field | Required | Description |
|-------|----------|-------------|
| `_description` | No | Human-readable description of the scenario |
| `_tag_type` | No | Expected numeric type code (for documentation) |
| `_default_return` | Yes | Return value for unmatched PM3 commands: `-1` (timeout/stop) or `1` (continue) |

The `_default_return` is critical:
- `-1`: Any PM3 command not in the fixture returns timeout. The pipeline STOPS at the first unmatched command. Use for `no_tag` (nothing responds) or HF-only tags (LF commands should not be reached).
- `1`: Unmatched commands return success with empty content. The pipeline CONTINUES. Use for LF tags that need to pass through HF stages, or for T55XX detection.

---

## 14. FIXTURE COUNT VS SCENARIO COUNT

The `ALL_SCAN_SCENARIOS` dict in `pm3_fixtures.py` contains more entries than the 44 test scripts:
- **44 scan-mode fixtures** with test scripts (the core scan flow suite)
- **11 additional scan-mode fixtures** without test scripts (Gen1a, UL subtypes, iClass variants, T55XX read variants — available for future expansion)
- **20 read-mode LF fixtures** (prefixed `read_*`) — these are for the Read Tag flow's LF scan phase, NOT part of the Scan flow tests

When building a new flow, only create test scripts for the scenarios within the user-defined boundary.

---

## 15. ADDING A NEW FLOW

To add a new flow (e.g., Read Tag):

1. **Read the UI Mapping**: `docs/UI_Mapping/04_read_tag/README.md`
2. **Extract keywords**: `docs/v1090_strings/hfmfread_strings.txt`, `read_strings.txt`, etc.
3. **Build the logic tree**: Every PM3 command → every keyword match → every leaf
4. **Propose boundaries to the user**: "Read starts at ReadActivity, ends at read success/fail. Do I follow the Write button? Do I include Reread?"
5. **Write fixtures**: One per leaf, in `pm3_fixtures.py` under `ALL_READ_SCENARIOS`
6. **Create `read_common.sh`**: Navigation to Read Tag (GOTO:3, select type, OK)
7. **Create scenario scripts**: One per fixture key
8. **Create `test_reads.sh`**: Flow-level runner
9. **Run and verify**: All scenarios PASS, `scenario_states.json` captures all state

---

## 16. READ FLOW — LESSONS LEARNED

These lessons were discovered while building and debugging the 82 Read Tag scenarios. They apply to ALL multi-phase flows (Read, Write, AutoCopy, Erase).

### 16.1 Navigation to the correct tag type

The Read Tag flow presents a **40-item scrollable list** (8 pages × 5 items). Each scenario MUST navigate to the correct tag type before pressing OK. The navigation is controlled by `_tag_type` in the fixture, which maps to page/position via `tools/read_list_map.json`.

**The bug that was found**: All 73 read scenarios were selecting the FIRST list item (M1 S50 1K 4B, type 1) because `read_common.sh` hardcoded `send_key "OK"` immediately after entering ReadListActivity. Every scenario ran with MFC 1K fixtures regardless of type.

**The fix**: `resolve_tag_nav()` reads `_tag_type` from the fixture, looks up the page/down values in `read_list_map.json`, and `navigate_to_tag()` sends the right number of DOWN presses before OK.

**Rule**: Every read fixture MUST have `_tag_type` set. Every flow with a type-selection list MUST navigate to the correct position.

### 16.2 Per-scenario variables

Scenario scripts can set these variables BEFORE sourcing the flow's common script:

```bash
#!/bin/bash
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_all_keys"
BOOT_TIMEOUT=600        # Override: QEMU process max lifetime (default 300s for read)
TRIGGER_WAIT=240        # Override: max seconds to poll for trigger (default 180s)
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario "mf4k_all_keys" 3
```

| Variable | Default | Description |
|----------|---------|-------------|
| `BOOT_TIMEOUT` | 300 (read) / 80 (common) | Total QEMU process lifetime via `timeout` |
| `TRIGGER_WAIT` | 180 | Seconds to poll for the result trigger |
| `PM3_DELAY` | 0.1 | Mock delay per PM3 command (seconds) |
| `TEST_DISPLAY` | :99 | X display for this worker (set by parallel runner) |

**WARNING**: The `:-` default syntax does NOT work for flow-level overrides of `common.sh` defaults. `common.sh` sets `BOOT_TIMEOUT=80`, so `read_common.sh`'s `${BOOT_TIMEOUT:-300}` is a no-op (already set to 80). The fix is to save the scenario value before sourcing, then apply: `BOOT_TIMEOUT="${_SCENARIO_BOOT_TIMEOUT:-300}"`.

### 16.3 Correct trigger selection

Every scenario MUST specify the correct trigger for its expected outcome. The default `M1:Reread` is ONLY correct for successful read scenarios.

**Success triggers**:
In order of preference.
1) `toast`: - Contents that match the EXACT string dictated by the original .so logic path, ie "Write failed!", "Read\nSuccessful!\nFile saved", etc.
2) `content_text.text` - Contents that match the EXACT string dictated by the original .so logic path, ie,  "Data ready for copy!\nPlease place new tag for copy."
3) `title` : - Contents that match the EXACT string dictated by the original .so logic path, ie,  "Data ready!"

Fixtures will use AT LEAST one of these triggers, depending on the UI dictated by the original UI.

These **extra validators** can and should be complemented with auxiliary data points for the button labels: 
- `M1:Reread` — Read completed (success or partial), M1 shows "Reread"
- `M2:Write` — Read succeeded with data, M2 shows "Write"

However, NEVER rely on just the button labels alone.
ALWAYS rely on the specific toast / content_text / title triggers.

**Failure triggers**:
- `toast:No tag found` — Scan phase found no tag (LF fail, EM4305 fail, T55XX detect fail)
- `content:No valid key` — Key recovery failed (darkside fail, hardnested fail, card lost, timeout)
- `toast:Read Failed` — Read phase failed after keys were found

**Golden Rules**:
- NEVER just rely on a state count
- ALWAYS have toast or content_text SPECIFIC to the logic state we are testing
- TRY to use **extra validators** to have the most specific matches as possible.


### 16.4 Fixture response format requirements

LF read fixtures MUST include all fields the `.so` parses. The `lfread.so` module has two parsers:
- `readCardIdAndRaw(uid_regex, raw_regex)` — needs an ID field AND a Raw field
- `readFCCNAndRaw(uid_regex, raw_regex)` — needs FC/CN fields AND a Raw field

**The bug**: GProx and Pyramid fixtures had FC/CN but no `Raw:` field. `readFCCNAndRaw()` couldn't extract the raw data → read failed silently → "No tag found" toast.

**Rule**: Every LF fixture response MUST contain a `Raw:` or equivalent hex data line. Check `docs/v1090_strings/lfread_strings.txt` for the exact regex patterns.

### 16.5 Multi-phase attack flow ordering

For MIFARE Classic key recovery, the .so follows a strict chain:
```
fchk → darkside → nested → staticnested/hardnested/loudong → rdsc
```

**Critical**: Each phase requires the PREVIOUS phase to succeed:
- `darkside` MUST find at least one key for `nested` to have a starting key
- `nested` failing with "Tag isn't vulnerable to Nested Attack" triggers `hardnested`
- If `darkside` fails (no key found), `nested`/`hardnested` are never called

**The bug**: Hardnested fixtures had darkside FAILING ("not vulnerable"). Without a starting key, nested never ran, hardnested never triggered. Fix: darkside returns `"found valid key: ffffffffffff"`, then nested returns "not vulnerable to Nested Attack" → triggers hardnested.

### 16.6 Gen1a detection via cgetblk override

Gen1a magic cards are detected when `hf mf cgetblk 0` SUCCEEDS (returns block data). The scan fixture for standard MFC (`mf_classic_1k_4b`) has cgetblk FAILING. For Gen1a scenarios, the READ fixture must include a successful `cgetblk` entry that overrides the scan fixture's failure response (fixtures merge: read overlays scan).

### 16.7 Variant types share read paths

Many tag types use identical read code. The `read.so` dispatcher groups types:
- `getM1Types()` → types 0, 1, 25, 26, 41, 42 → `hfmfread.so`
- `getULTypes()` → types 2, 3, 4, 5, 6, 7 → `hfmfuread.so`
- `getiClassTypes()` → types 17, 18 → `iclassread.so`
- ISO15693 types 19, 46 → `hf15read.so`

**Rule**: Create at least one happy-path read scenario per variant type (even if the read path is identical). The scenarios differ in:
1. Different `_tag_type` → different list position → different navigation
2. Different scan fixture → different detection keywords
3. Different sector/block counts (e.g., MF Mini=5, 1K=16, 2K=32, 4K=40 sectors)

### 16.8 QEMU timing and Xvfb limits

Under QEMU ARM emulation, each PM3 command takes ~2-3 seconds (mock delay + emulation overhead). A 4K card with 40 `hf mf rdsc` calls takes ~100-120 seconds just for sector reads.

**Xvfb resource exhaustion**: `wait_for_ui_trigger` captures a screenshot + state dump every ~0.7 seconds. With `TRIGGER_WAIT=360`, that's 720+ captures. Xvfb crashes with `XIO: fatal IO error 11` after ~1000 captures. Keep `TRIGGER_WAIT` ≤ 240 for long-running scenarios.

**Parallel I/O bottleneck**: 16 parallel QEMU workers sharing one SD card image and one /tmp filesystem causes I/O contention that slows individual tests. The practical limit is ~12 workers for read tests (vs ~16 for scan-only).

---

## 17. REFERENCE: EXISTING TOOLS

| File | Purpose |
|------|---------|
| `tools/minimal_launch_090.py` | QEMU launcher with PM3 mock, key injection, state dump |
| `tools/pm3_fixtures.py` | All fixture definitions (scan, read, write, erase) |
| `tools/read_list_map.json` | Read Tag list: 40 items with page/down navigation + scan fixture keys |
| `tests/includes/common.sh` | Shared test infrastructure (parallel-safe: per-scenario key files, parameterized display) |
| `tests/flows/scan/includes/scan_common.sh` | Scan-specific test logic |
| `tests/flows/scan/test_scans.sh` | Scan flow runner (44 scenarios) |
| `tests/flows/read/includes/read_common.sh` | Read-specific: tag navigation, merged fixtures, trigger validation |
| `tests/flows/read/test_reads_parallel.sh` | Parallel read runner (`--remote`, `--init-remote`, FIFO semaphore) |
| `tests/test_all_flows.sh` | Top-level runner |
| `docs/UI_Mapping/` | Per-activity UI documentation |
| `docs/v1090_strings/` | Per-module string extractions |
| `decompiled/SUMMARY.md` | Module API overview |
| `docs/HOW_TO_RUN_LIVE_TRACES.md` | How to instrument the real device for flow capture |
| `docs/Real_Hardware_Intel/` | All real device traces (PM3 commands, activity transitions, screenshots) |

The Scan flow (44/44) and Read flow (74/82) are proven. Use them as templates for every new flow.
