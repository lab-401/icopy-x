# Sniff Flow — UI Integration Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Sniff TRF** flow — `SniffActivity` and `sniff.so` must capture RF communication traces for 5 protocol types (14A, 14B, iClass, Topaz, T5577), displaying correct UI at every step: type selection, instruction screens, sniffing-in-progress toast, decoded trace results, and trace save.

**Current status:** `SniffActivity` exists in `src/lib/activity_main.py` (lines 2620-2995) with 3 states, 5 sniff types, and integration with `sniff.so` for PM3 command dispatch. The test suite has **16 scenarios** in `tests/flows/sniff/scenarios/`. Unit tests exist in `tests/ui/activities/test_sniff.py` (370 lines, 37 test cases). Your job is to run every test, visually audit screenshots against real device captures, and fix any failures or UI issues.

## CRITICAL — DRM SMOKE TEST

**Before debugging ANY silent .so failure, ALWAYS check DRM first:**

```bash
# Check launcher log for this line:
[OK] tagtypes DRM passed natively: 40 readable types    # MUST see this
[WARN] tagtypes DRM failed — falling back to bypass      # MODULES MAY FAIL
```

**Correct serial**: `02c000814dfb3aeb` (in `launcher_current.py` cpuinfo mock)

**Reference**: `docs/DRM-KB.md`, `docs/DRM-Issue.md`

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/write/ui-integration/README.md` — **READ THIS FIRST.** Write flow post-mortem. DRM blocker (6+ hours lost, 1-line fix), callback patterns, no-middleware rules, sequential fixture responses. The Sniff flow uses the same `executor.startPM3Task()` pattern for PM3 commands.

2. `docs/flows/auto-copy/ui-integration/README.md` — Auto-Copy post-mortem. Activity stack architecture, scan.so predicates, middleware removal.

3. `docs/flows/simulate/ui-integration/README.md` — Simulate post-mortem. SimFields widget, FB capture methodology, pixel measurement, content verification in tests. Sniff has similar list navigation and state machine patterns.

4. `docs/flows/read/ui-integration/README.md` — Read flow post-mortem. Scanner/Reader API, template.so rendering. SniffForMfReadActivity is launched from the Read flow when key recovery fails.

5. `docs/flows/scan/ui-integration/README.md` — Scan flow post-mortem. Ground truth rules.

6. `docs/UI_Mapping/06_sniff/README.md` — **Exhaustive UI specification** for SniffActivity: 4 states (TYPE_SELECT, INSTRUCTION, SNIFFING, RESULT), sniff.so API (11 functions), PM3 commands, key bindings, parse functions, 20+ method signatures.

7. Real device screenshots (7 files):
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_list_1_1.png` — TYPE_SELECT: 5 items, "Sniff TRF 1/1", no softkeys
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_1_4_1.png` — INSTRUCTION Step 1/4: "Prepare client's reader..."
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_2_4.png` — INSTRUCTION Step 2/4: "Remove antenna cover..."
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_3_4.png` — INSTRUCTION Step 3/4: "Swipe tag on iCopy..."
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_4_4.png` — INSTRUCTION Step 4/4: "Repeat 3-5 times..."
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_sniffing.png` — SNIFFING: toast overlay on Step 1, M1="Start" M2="Finish"
    - `docs/Real_Hardware_Intel/Screenshots/sniff_trf_1_4_2.png` — RESULT: "TraceLen: 0", M1="Start" M2="Save"

8. `docs/HOW_TO_BUILD_FLOWS.md` — Methodology, fixture structure, keyword matching.

9. Decompiled binaries:
    - `decompiled/sniff_ghidra_raw.txt` — sniff.so: 11 exported functions (sniff14AStart, sniff14BStart, sniffIClassAStart, sniffTopazStart, sniff125KStart, 6 parser functions)
    - `decompiled/activity_main_ghidra_raw.txt` — SniffActivity onKeyEvent (~2000 lines decompiled)

10. Extracted .so strings:
    - `docs/v1090_strings/sniff_strings.txt` — sniff.so symbols and PM3 command strings
    - `docs/v1090_strings/activity_main_strings.txt` — SniffActivity method symbols, resource keys

11. `src/lib/activity_main.py` — Current SniffActivity (lines 2620-2995), SniffForMfReadActivity (lines 5635-5656), SniffForT5XReadActivity (lines 5658-5679), SniffForSpecificTag (lines 5681-5702).

12. `src/screens/sniff.json` — JSON UI state machine (3 states: type_select, sniffing, result).

13. `tests/ui/activities/test_sniff.py` — 37 unit tests across 6 test classes.

14. `tools/launcher_current.py` — Launcher with PM3 mock, DRM fix, state dump.

## Critical lessons from completed flows (DO NOT REPEAT THESE MISTAKES)

### 1. sniff.so API Discovery
The .so module APIs are NOT what you expect. For sniff.so:
- Check `docs/v1090_strings/sniff_strings.txt` and `docs/UI_Mapping/06_sniff/README.md` Section sniff.so Module API
- 5 start functions: `sniff14AStart`, `sniff14BStart`, `sniffIClassAStart`, `sniffTopazStart`, `sniff125KStart`
- 6 parser functions: `parserTraceLen`, `parserKeyForLine`, `parserDataForSCA`, `parserUidForData`, `parserKeyForM1`, `parserUidForKeyIndex`
- **14A parse command is `hf list mf`** NOT `hf 14a list` — verified by QEMU .so behavior (sniff_common.sh line 20)
- **Do NOT assume the API. Verify against QEMU behavior.**

### 2. NEVER Invent Middleware
If you find yourself writing trace parsing logic, STOP — it belongs in `sniff.so`. Our Python is a thin UI shell that calls `sniff.so` functions and renders their results. The `.so` handles all PM3 command dispatch, trace parsing, and key extraction.

### 3. NEVER Mass-Modify Fixtures
**BEFORE MODIFYING ANY FIXTURES — REQUEST EXPLICIT CONFIRMATION FROM THE USER.** Verify each fix individually.

### 4. Sequential Fixture Responses Are Critical
Sniff flows call multiple PM3 commands in sequence: first the sniff command, then the parse/list command. These must be separate entries in the fixture:
```python
'hf 14a sniff': (0, 'trace len = 1234\n'),   # start sniff
'hf list mf': (0, 'Recorded activity...\n'),  # parse trace
```

### 5. T5577 Auto-Finish via `125k_sniff_finished` Marker
T5577 sniff does NOT require manual M2 press. The `lf t55xx sniff` response contains `125k_sniff_finished` marker which triggers `onData()` → auto-stop → show result. This is unique to T5577.

### 6. PWR Key Goes Through onKeyEvent
PWR dispatches to `onKeyEvent()`. SniffActivity must handle PWR in ALL states:
- TYPE_SELECT: finish()
- INSTRUCTION: back to TYPE_SELECT
- SNIFFING: stopSniff() + back to TYPE_SELECT
- RESULT: hideAll() + back to TYPE_SELECT

### 7. Canvas Cleanup Between States
When transitioning between INSTRUCTION→SNIFFING→RESULT→TYPE_SELECT, clear ALL canvas items from previous states. Toast.cancel(), ListView.hide(), console text cleanup.

### 8. Content Verification in Tests
After navigating to SniffActivity, verify expected content appears (e.g., sniff type name, instruction text). In Simulate, 7 scenarios silently went to wrong types because tests only checked state counts.

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/sniff_ghidra_raw.txt`, `decompiled/activity_main_ghidra_raw.txt`
2. Real screenshots: `docs/Real_Hardware_Intel/Screenshots/sniff_trf_*.png` (7 files)
3. UI Mapping: `docs/UI_Mapping/06_sniff/README.md`
4. String extractions: `docs/v1090_strings/sniff_strings.txt`, `docs/v1090_strings/activity_main_strings.txt`
5. Previous flow post-mortems: `docs/flows/write/ui-integration/README.md`, `docs/flows/auto-copy/ui-integration/README.md`, `docs/flows/simulate/ui-integration/README.md`
6. **NEVER deviate.** Never invent. Never guess. Never "try something".
7. **ALL work must derive from these ground truths.**
8. **EVERY action** must cite its ground-truth reference.
9. **Before writing code:** Does this come from ground truth? If not, don't.
10. **After writing code:** Audit — does this come from ground truth? If not, undo.
11. **Use existing launcher tools** — `tools/launcher_current.py` — Do not roll your own infrastructure.

If no ground truth exists, ask the user before proceeding.

### Supplementary ground truth
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` — `cmdhf14a.c` for `hf 14a sniff` output, `cmdlft55xx.c` for `lf t55xx sniff`
- QEMU API dump: `archive/root_old/qemu_api_dump_filtered.txt` — method signatures
- Live trace methodology: `docs/HOW_TO_RUN_LIVE_TRACES.md` — deploy tracer to real device (tunnel on port 2222, `root:fa`). Use `/trace-device` skill.

## Sniff flow architecture

### Activity stack transitions

```
MainActivity
    | (user selects "Sniff TRF" from main menu, position 4)
SniffActivity (stack depth 2)
    |-- TYPE_SELECT: 5-item list, title "Sniff TRF 1/1"
    |   1. 14A Sniff
    |   2. 14B Sniff
    |   3. iclass Sniff
    |   4. Topaz Sniff
    |   5. T5577 Sniff
    |   UP/DOWN: scroll, OK: select → INSTRUCTION, PWR: finish
    |
    |-- INSTRUCTION: 4-step guide (HF) or single instruction (T5577)
    |   Title: "Sniff TRF N/4"
    |   M1="Start": begin sniff → SNIFFING
    |   M2="Finish": (dimmed/disabled)
    |   UP/DOWN: navigate instruction pages
    |   PWR: back to TYPE_SELECT
    |
    |-- SNIFFING: "Sniffing in progress..." toast overlay
    |   PM3 command dispatched (hf 14a sniff / lf sniff / etc.)
    |   M1="Start": (unchanged label, inactive during sniff)
    |   M2="Finish": stop sniff → RESULT
    |   PWR: abort sniff → TYPE_SELECT
    |   T5577: auto-stops on 125k_sniff_finished marker
    |
    |-- RESULT: Decoded trace data / TraceLen display
    |   M1="Start": restart sniff
    |   M2="Save": save trace file
    |   UP/DOWN: scroll result list
    |   PWR: back to TYPE_SELECT
```

**Ground Truth**: `docs/UI_Mapping/06_sniff/README.md`, `sniff_trf_*.png` screenshots

### SniffActivity state machine

| State | UP/DOWN | OK | M1 | M2 | PWR |
|-------|---------|----|----|-------|-----|
| TYPE_SELECT | scroll list | select type | -- | -- | finish() |
| INSTRUCTION | navigate pages | -- | startSniff() | stopSniff()→RESULT | back to TYPE_SELECT |
| SNIFFING | -- | -- | (inactive) | stopSniff()→RESULT | abort→TYPE_SELECT |
| RESULT | scroll results | -- | restart sniff | saveSniffData() | back to TYPE_SELECT |

**Ground Truth**: `docs/UI_Mapping/06_sniff/README.md` Key Bindings section, `sniff_common.sh` QEMU-verified key sequence

### Sniff algorithms by protocol

**14A Sniff (HF MIFARE):**
1. Start: `sniff.sniff14AStart()` → `hf 14a sniff`
2. Parse: `hf list mf` (NOT `hf 14a list` — QEMU-verified, sniff_common.sh line 20)
3. Result: Decoded trace with UID, keys, data blocks
- Ground Truth: `sniff_14a_trace_result/fixture.py`, `docs/UI_Mapping/06_sniff/README.md`

**14B Sniff (HF ISO14443B):**
1. Start: `sniff.sniff14BStart()` → `hf 14b sniff`
2. Parse: `hf list 14b` (from sniff.json line items)
3. Result: Decoded ISO14443B trace

**iClass Sniff (HF iClass):**
1. Start: `sniff.sniffIClassAStart()` → `hf iclass sniff`
2. Parse: `hf list iclass` (from sniff.json)
3. Result: Decoded iClass trace with key data

**Topaz Sniff (HF Topaz/Jewel):**
1. Start: `sniff.sniffTopazStart()` → `hf topaz sniff`
2. Parse: `hf list topaz` (from sniff.json)
3. Result: Decoded Topaz trace

**T5577 Sniff (LF):**
1. Config: `lf config a 0 t 20 s 10000` (configure LF sampling)
2. Start: `sniff.sniff125KStart()` → `lf t55xx sniff`
3. **Auto-stop**: Response contains `125k_sniff_finished` → `onData()` triggers `showResult()`
4. Result: T5577 write commands with password/data decoded
- Ground Truth: `sniff_t5577_auto_finish/fixture.py`
- **NO manual M2 "Finish" press needed for T5577**

### sniff.so module API

| Function | Purpose |
|----------|---------|
| `sniff14AStart` | Start 14A sniff (PM3: `hf 14a sniff`) |
| `sniff14BStart` | Start 14B sniff (PM3: `hf 14b sniff`) |
| `sniffIClassAStart` | Start iClass sniff (PM3: `hf iclass sniff`) |
| `sniffTopazStart` | Start Topaz sniff (PM3: `hf topaz sniff`) |
| `sniff125KStart` | Start LF/T5577 sniff (PM3: `lf t55xx sniff`) |
| `parserTraceLen` | Parse trace length from PM3 output (regex: `trace len = (\d+)`) |
| `parserKeyForLine` | Extract key bytes from a sniff trace line |
| `parserDataForSCA` | Parse data for SCA analysis |
| `parserUidForData` | Extract UID from trace data |
| `parserKeyForM1` | Parse key for MIFARE 1K |
| `parserUidForKeyIndex` | Parse UID for key index |
| `saveSniffData` | Save trace data to file (also used by SimulationTraceActivity) |

**Ground Truth**: `docs/UI_Mapping/06_sniff/README.md` sniff.so Module API section, `decompiled/sniff_ghidra_raw.txt` lines 283-300

### PM3 command reference

| Command | Type | Purpose |
|---------|------|---------|
| `hf 14a sniff` | HF | Start ISO14443A sniff |
| `hf 14b sniff` | HF | Start ISO14443B sniff |
| `hf iclass sniff` | HF | Start iClass sniff |
| `hf topaz sniff` | HF | Start Topaz/Jewel sniff |
| `lf config a 0 t 20 s 10000` | LF | Configure LF sampling (before T5577 sniff) |
| `lf t55xx sniff` | LF | Start T5577 LF sniff |
| `hf list mf` | HF | Parse 14A trace (NOT `hf 14a list`) |
| `hf list 14b` | HF | Parse 14B trace |
| `hf list iclass` | HF | Parse iClass trace |
| `hf list topaz` | HF | Parse Topaz trace |

**Ground Truth**: `docs/UI_Mapping/06_sniff/README.md` String Constants section, `sniff_common.sh` line 20 (14A parse verified as `hf list mf`)

## Related activities

### SniffForMfReadActivity (activity_main.py:5635-5656)

**Purpose**: Launched from the Read flow when MIFARE key recovery fails. The WarningM1Activity presents "Sniff" as an option (M1 key). This pushes SniffForMfReadActivity to capture keys via sniffing.

**Stub status**: Minimal implementation — `onCreate` sets title, `onKeyEvent` handles M1/PWR.

**Ground Truth**: `docs/flows/read/ui-integration/README.md` — M1:Sniff trigger, `activity_read.py:219-223`

### SniffForT5XReadActivity (activity_main.py:5658-5679)

**Purpose**: Launched from the Read flow when T5577 password recovery fails. Captures T55xx write commands to extract passwords.

**Method**: `showT5577Result` (from binary string table, `docs/V1090_SO_STRINGS_RAW.txt` line 63)

**Stub status**: Minimal implementation.

### SimulationTraceActivity (activity_main.py:5168-5268)

**Purpose**: Displays captured HF simulation trace data. Calls `sniff.saveSniffData()` (line 5256) — shares the same save mechanism as SniffActivity.

**Ground Truth**: `docs/UI_Mapping/06_sniff/README.md` — SimulationTraceActivity cross-reference

## Test infrastructure

### 16 test scenarios

| Scenario | Type | What It Tests |
|----------|------|---------------|
| `sniff_14a_trace_result` | 14A | Happy path: select → start → finish → result with trace data → save |
| `sniff_14a_empty_trace` | 14A | Sniff with no trace data (TraceLen: 0) |
| `sniff_14a_pwr_abort` | 14A | PWR during sniffing aborts back to TYPE_SELECT |
| `sniff_14a_pwr_from_result` | 14A | PWR from result screen back to TYPE_SELECT |
| `sniff_14b_trace_result` | 14B | 14B happy path with trace data |
| `sniff_14b_empty_trace` | 14B | 14B with no trace data |
| `sniff_iclass_trace_result` | iClass | iClass happy path |
| `sniff_iclass_empty_trace` | iClass | iClass with no trace data |
| `sniff_topaz_trace_result` | Topaz | Topaz happy path |
| `sniff_topaz_empty_trace` | Topaz | Topaz with no trace data |
| `sniff_t5577_auto_finish` | T5577 | Auto-stop via `125k_sniff_finished` marker (NO manual M2) |
| `sniff_t5577_manual_finish` | T5577 | Manual M2 finish for T5577 |
| `sniff_t5577_empty` | T5577 | T5577 with no captured data |
| `sniff_t5577_pwr_abort` | T5577 | PWR during T5577 sniff |
| `sniff_pwr_back` | -- | PWR from TYPE_SELECT exits to main menu |
| `sniff_list_navigation` | -- | UP/DOWN through all 5 sniff types |

### Running tests

```bash
# Single test locally
TEST_TARGET=current SCENARIO=sniff_14a_trace_result FLOW=sniff \
  bash tests/flows/sniff/scenarios/sniff_14a_trace_result/sniff_14a_trace_result.sh

# Full parallel suite on remote
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/sniff/test_sniff_parallel.sh 9'

# Results
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cat ~/icopy-x-reimpl/tests/flows/_results/current/sniff/scenario_summary.txt'
```

### Framework constants

```
PM3_DELAY=0.5
BOOT_TIMEOUT=120
SNIFF_WAIT=30
```

### 5-phase sniff test pipeline (`sniff_common.sh`)

1. **Phase 1**: Navigate to Sniff TRF (GOTO:4) → select type (DOWN × N) → OK
2. **Phase 2**: Instruction screen displayed → M1 "Start" fires PM3 sniff command
3. **Phase 3**: Wait for "Sniffing in progress..." toast → capture sniffing state
4. **Phase 4**: M2 "Finish" stops sniff → wait for M2="Save" (result displayed)
5. **Phase 5**: (optional) M2 "Save" → wait for "Trace file saved" toast

**T5577 exception**: Phase 4 is automatic — `125k_sniff_finished` marker triggers auto-stop without M2 press.

## Environment

- Branch: `feat/ui-integrating` at latest commit
- QEMU rootfs: `/mnt/sdcard/root2/root/`
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`, sudo: `proxmark`, 48 cores)
- Real device SSH: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be established by user)
- Main menu position: Item #5 ("Sniff TRF") → GOTO:4
- Activity registry: `'sniff': ('activity_main', 'SniffActivity')` in `actmain.py:47`

## Working flows (don't break these)

- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 63/63 PASS
- Auto-Copy: 52/52 PASS
- Simulate: 32/32 PASS

## Known issues and observations

### 14A parse command mismatch
The UI mapping docs (`docs/UI_Mapping/06_sniff/README.md`) and `sniff.json` list `hf 14a list` as the parse command for 14A sniff. However, QEMU .so testing reveals the actual command issued is **`hf list mf`**. The test fixtures (`sniff_14a_trace_result/fixture.py`) use `hf list mf`. Trust the QEMU-verified behavior over the documentation.

**Ground Truth**: `sniff_common.sh` line 20: "14A: hf list mf (NOT hf 14a list as docs suggest)"

### 14B parse command — unverified
The sniff.json lists `hf list 14b` for 14B. This has NOT been QEMU-verified (sniff_common.sh line 21: "14B: TBD (verify)"). If 14B scenarios fail, this is the first thing to check.

### sniff.so `hf 14b sniff` command — not in binary strings
The `hf 14b sniff` PM3 command is NOT found in the sniff.so string dump (`docs/UI_Mapping/06_sniff/README.md` Section SNIFFING note). The `sniff14BStart` function exists but its PM3 command string is not visible. Likely uses `hf 14b sniff` but this is unconfirmed.

### Instruction screen page indicator
The title changes to "Sniff TRF N/4" during INSTRUCTION state. The 4-page instruction set (Steps 1-4) is navigated with UP/DOWN. T5577 has a single instruction page (no pagination).

**Ground Truth**: All 7 screenshots confirm page indicator format and instruction content.

### Button labels during SNIFFING
M1 label stays as "Start" even during active sniffing — it does NOT change to "Stop". M2 shows "Finish".

**Ground Truth**: `sniff_trf_sniffing.png` — M1="Start", M2="Finish"

## Definition of done

1. All 16 sniff test scenarios PASS with correct trigger validation
2. UI matches real device screenshots at every state (TYPE_SELECT, INSTRUCTION, SNIFFING, RESULT)
3. Correct sniff type items in list (5 items, numbered "1." through "5.")
4. Instruction screens match real device text (4 steps for HF, 1 for T5577)
5. "Sniffing in progress..." toast during active sniff
6. Trace results display correctly (TraceLen, decoded data)
7. Save functionality works ("Trace file saved" toast)
8. T5577 auto-finish works without manual M2 press
9. PWR navigation works in all states
10. No regressions: Scan, Read, Write, Auto-Copy, Simulate all still pass
11. Every change cites ground-truth source

## Approach

1. **Run the full sniff suite** on remote with 9 workers
2. **Bring results back locally** (rm -rf local _results/current/sniff first!)
3. **Visually audit** every scenario's screenshots against the 7 real device captures
4. **Check for UI issues**: type selection list, instruction text, sniffing toast, result display, button labels
5. **Verify content**: correct sniff type names, instruction text matches resources, trace data format
6. **Identify failures** — tests failing on trigger or state count
7. **Fix issues one at a time** with ground-truth citations
8. **Run all suites** to verify no regressions

**DO NOT batch-fix.** Fix one scenario, verify, then move to the next. Each fix must cite its ground-truth source.
