# How to Integrate a Flow: Methodology Guide

## Context

The iCopy-X is an RFID copier running 62 Cython-compiled `.so` modules on ARM Linux (240x240 display). We are replacing the **UI layer** with open-source Python while keeping the **middleware `.so` modules** (scan.so, read.so, write.so, executor.so, etc.) unchanged.

The firmware runs under QEMU ARM for testing. Flow tests capture screenshots and state dumps at each step, comparing against expected behavior.

### Architecture

```
┌─────────────────────────────────────────────────┐
│  OUR PYTHON (src/lib/)                          │
│  actmain.py, activity_main.py, activity_tools.py│
│  actbase.py, actstack.py, widget.py, keymap.py  │
│  resources.py, images.py, hmi_driver.py         │
│                                                  │
│  These are THIN UI SHELLS.                       │
│  They render widgets and forward callbacks.      │
│  They do NOT contain RFID logic.                 │
├─────────────────────────────────────────────────┤
│  ORIGINAL .so MIDDLEWARE (rootfs)               │
│  scan.so, read.so, write.so, executor.so        │
│  tagtypes.so, hfmfkeys.so, hfmfread.so, etc.   │
│                                                  │
│  These contain ALL RFID logic.                   │
│  They call executor.startPM3Task() for PM3 cmds.│
│  They call back into the activity via methods.   │
├─────────────────────────────────────────────────┤
│  LAUNCHER (tools/launcher_current.py)           │
│  Boots QEMU, mocks serial/subprocess/pygame,    │
│  creates Tk root, pushes MainActivity,          │
│  wires keymap, PM3 fixture system.              │
└─────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `tools/launcher_current.py` | Boots OSS Python UI under QEMU |
| `tools/launcher_original.py` | Boots original .so UI (reference baseline) |
| `tests/includes/common.sh` | Test infrastructure: boot, keys, screenshots, state dumps |
| `tests/flows/{flow}/` | Per-flow test scenarios |
| `src/lib/activity_main.py` | All activity classes (ScanActivity, ReadActivity, etc.) |
| `src/lib/activity_tools.py` | DiagnosisActivity + sub-test activities |
| `src/lib/actmain.py` | MainActivity (main menu, navigation dispatch) |
| `src/lib/actbase.py` | BaseActivity (title bar, button bar, canvas) |
| `src/lib/widget.py` | ListView, CheckedListView, ProgressBar, Toast, etc. |
| `src/lib/_constants.py` | Colors, dimensions, layout constants |

## Ground Truth Rules

**Only use ground-truth resources:**

1. The original decompiled `.so` files: `decompiled/*.txt` (widget_ghidra_raw.txt, activity_main_ghidra_raw.txt, scan_ghidra_raw.txt, actbase_strings.txt, etc.)
2. Real activity traces from real actions on the real device: `docs/Real_Hardware_Intel/trace_*.txt`
3. Real screenshots from the real device: `docs/Real_Hardware_Intel/Screenshots/*.png` (140 files + MANIFEST.txt)
4. **NEVER deviate** from these resources. Never invent. Never guess. Never "try something".
5. **ALL your work must derive from these ground truths.**
6. **EVERY action that you perform**, you will provide the reference to the ground-truth upon which you justify your action.
7. **Before you write ANY code**, ask yourself: Does this come directly from a ground-truth? If not, don't do it.
8. **AFTER you have written code**, audit it and ask yourself: Does this come directly from a ground-truth? If not, undo it.

If there is NO way around this, or if you're given a task that requires deviating, ask explicit confirmation from the User.

## Immutable Laws

1. **Tests are immutable.** NEVER edit test files. They define correct behavior.
2. **The `.so` middleware IS the logic.** Our Python activities do NOT reimplement scanning, reading, writing, or any RFID logic. They call into `.so` modules and render whatever comes back.
3. **The real device screenshots are the ONLY visual ground truth.** Located at `docs/Real_Hardware_Intel/Screenshots/` (140 files with `MANIFEST.txt`).
4. **The decompiled `.so` source is the ONLY behavioral ground truth.** Located at `decompiled/*.txt`. The `docs/UI_Mapping/` docs are reference material derived from these — they may contain errors.
5. **Never guess.** Every method call, every string, every widget parameter must be traceable to a ground truth source.
6. **Never put logic in the UI.** If a PM3 command needs to be sent, the `.so` middleware sends it. If a result needs to be parsed, the `.so` parses it. The activity just renders.
7. **NEVER flash PM3 bootrom.** No JTAG = bricked device.

## JSON UI System

Activities define their UI declaratively as JSON screen definitions. The `JsonRenderer` (`src/lib/json_renderer.py`) translates these into canvas draw calls. Activities handle logic (key events, .so callbacks, state transitions) and tell the renderer what screen to draw.

### JSON Screen Schema

```json
{
    "title": "Screen Title",
    "content": {
        "type": "template|progress|list|text|empty",
        ...type-specific fields...
    },
    "buttons": {
        "left": "Button Text" | null,
        "right": "Button Text" | null
    },
    "toast": {
        "text": "Message",
        "icon": "check|error",
        "timeout": 3000
    }
}
```

### Content Types

| Type | Use Case | Key Fields |
|------|----------|------------|
| `template` | Scan/read result display | `header`, `subheader`, `fields[]` (with `row[]` for inline) |
| `progress` | Scanning/reading/writing | `message`, `value`, `max` |
| `list` | Main menu, tag lists | `style` (menu/plain/radio), `items[]`, `selected` |
| `text` | About, warnings | `lines[]` |
| `empty` | Toast-only screens | (none) |

### Multi-State Activities (JSON files in `src/screens/`)

```json
{
    "id": "scan_tag",
    "initial_state": "scanning",
    "states": {
        "scanning": { "screen": { ... } },
        "found": { "screen": { ... } },
        "not_found": { "screen": { ... } }
    }
}
```

### Activity Integration Pattern

```python
class ScanActivity(BaseActivity):
    def onCreate(self, bundle):
        self.setTitle("Scan Tag")
        self._jr = JsonRenderer(self.getCanvas())
        self._startScan()

    def _startScan(self):
        # Render scanning UI via JSON
        self._jr.render({
            'content': {'type': 'progress', 'message': 'Scanning...', 'value': 0, 'max': 100},
            'buttons': {'left': None, 'right': None},
        })
        # Start .so middleware
        scanner = scan.Scanner()
        scanner.call_progress = self.onScanning
        scanner.call_resulted = self.onScanFinish
        scanner.scan_all_asynchronous()

    def onScanFinish(self, result):
        # Render result via JSON template
        self._jr.render({
            'content': {'type': 'template', 'header': 'MIFARE', ...},
            'buttons': {'left': 'Rescan', 'right': 'Simulate'},
        })
```

### Visual Constants Source

All pixel positions, colors, and fonts in `_constants.py` and `json_renderer.py` are sourced from:
- `decompiled/actbase_strings.txt`: button bar `#222222`, text `white`
- `docs/Real_Hardware_Intel/Screenshots/scan_tag_scanning_2.png`: progress bar y=210
- `docs/Real_Hardware_Intel/Screenshots/scan_tag_scanning_5.png`: template layout y=52,86,110,132,155
- `docs/Real_Hardware_Intel/Screenshots/main_page_1_3_1.png`: icon colors, no button bar on menu
8. **NEVER access ~/.ssh on any device.**

## The Integration Process (Per Flow)

### Step 1: Gather Ground Truth

For the flow you're integrating (e.g., Scan, Read, Write):

**A. Real device screenshots:**
```
docs/Real_Hardware_Intel/Screenshots/{flow}_*.png
```
Read every screenshot. Note: title text, button labels (M1/M2), content type (list, progress bar, text, toast), widget positions.

**B. Real device traces:**
```
docs/Real_Hardware_Intel/*.txt
```
Search for PM3 commands, activity stack transitions, callback methods, scan cache data. These show the ACTUAL call sequence on real hardware.

**C. Decompiled `.so` source:**
```
decompiled/activity_main_ghidra_raw.txt   # activity classes
decompiled/scan_ghidra_raw.txt            # scan middleware
decompiled/read_ghidra_raw.txt            # read middleware
docs/v1090_strings/activity_main_strings.txt  # string literals
docs/v1090_strings/scan_strings.txt           # scan.so API
```
Find the exact activity class. Map: `onCreate()`, `onKeyEvent()`, `onScanFinish()`, `onReading()`, etc. Note every `.so` method call.

**D. Test fixtures and flow scripts:**
```
tests/flows/{flow}/includes/{flow}_common.sh   # test flow logic
tests/flows/{flow}/scenarios/*/fixture.py       # PM3 mock responses
```
The test script defines: GOTO position, key sequence, expected state triggers, minimum unique states. The fixture defines PM3 command→response mappings.

**E. String tables:**
```
docs/v1090_strings/{module}_strings.txt
src/lib/resources.py  # StringEN class (verified string keys→values)
```

### Step 2: Map the State Machine

From the decompiled source + screenshots + traces, document:

```
State 1: [STATE_NAME]
  - Triggered by: [what action]
  - Widget: [ListView / ProgressBar / Toast / Canvas text]
  - Title: [exact string]
  - M1: [label or empty]
  - M2: [label or empty]
  - .so calls: [what middleware functions are called]
  - Callback: [what method the .so calls back on the activity]

State 2: ...
```

### Step 3: Identify the Middleware Integration Point

This is the CRITICAL step. For each flow, identify:

1. **Which `.so` module drives the flow?** (e.g., `scan.so` for scanning)
2. **What function starts the operation?** (e.g., `scan.scanForType(type, listener)`)
3. **What callback methods does the `.so` call on the activity?**
   - `onScanFinish(result)` — scan complete
   - `onScanning(progress)` — progress update
   - `onReading(progress, total, listener)` — read progress
   - etc.
4. **What data format does the callback receive?**
   - e.g., `{'found': True, 'uid': '9C750884', 'type': 1, 'sak': '08', ...}`
5. **What methods/attributes must the Python activity expose** for the `.so` to call back successfully?

#### Known Issue: `.so` Callback Compatibility

The Cython `.so` modules call methods on the activity object using Python attribute lookup. Our Python activity must expose methods with **exactly matching names and compatible signatures**. If the `.so` checks for specific attributes (e.g., `hasattr(listener, 'onScanFinish')`), those must exist.

**Current blocker for Scan flow:** `scan.scanForType(None, self)` silently does nothing — no PM3 commands are sent, no callbacks fire. Investigation needed:
- Does `scanForType(None, ...)` mean "no type, don't scan"? Try type `0` or `-1` for "all".
- Does `scan.so` check for specific attributes on the listener object?
- Try `scan.Scanner().scan_all_asynchronous(self)` (class method vs module function).
- Take a live trace with the ORIGINAL `.so` UI to capture the exact call signature.

### Step 4: Write the Python Activity

The activity class must:

1. **Match the original class name exactly** (e.g., `ScanActivity`, not `ScanTagActivity`)
2. **Expose all callback methods** the `.so` expects (exact names, compatible signatures)
3. **Call the `.so` middleware** using the exact function name and arguments from Step 3
4. **Render UI** using the same widgets, positions, and content as the real device screenshots
5. **Handle keys** per the decompiled `onKeyEvent()` logic
6. **NOT contain any RFID logic** — no PM3 command strings, no result parsing (except for activities like DiagnosisActivity where the `.so` itself embeds PM3 calls)

### Step 5: Run Flow Tests

```bash
# Single scenario
TEST_TARGET=current SCENARIO={name} FLOW={flow} \
  bash tests/flows/{flow}/scenarios/{name}/{name}.sh

# Full flow (sequential)
TEST_TARGET=current bash tests/flows/{flow}/test_{flow}.sh

# Full flow (parallel, for flows that support it)
TEST_TARGET=current bash tests/flows/{flow}/test_{flow}_parallel.sh 4
```

Check results:
```
tests/flows/_results/current/{flow}/scenario_summary.txt
tests/flows/_results/current/{flow}/scenarios/{name}/screenshots/
tests/flows/_results/current/{flow}/scenarios/{name}/logs/scenario_log.txt
```

### Step 6: Compare Screenshots

For each captured state, compare against the real device screenshot:

| Element | Real Device | Our Version | Match? |
|---------|-------------|-------------|--------|
| Title text | | | |
| M1 label | | | |
| M2 label | | | |
| Content type | | | |
| Widget position | | | |
| Colors | | | |
| Toast text | | | |

Fix discrepancies. Rerun tests. Iterate until screenshots match and tests pass.

### Step 7: Verify with Verification Agent

Launch a read-only verification agent:
- Reads the decompiled `.so` source
- Reads our Python activity
- Reads the test results and screenshots
- Reports any behavioral divergence

## Multi-Agent Approach

For complex flows, use this agent structure:

### Phase 1: Implementation (parallel agents)

**Agent A — Extract .so behavior:**
- Read decompiled source, string tables, traces
- Output: state machine spec with exact method calls
- READ-ONLY — does not modify files

**Agent B — Implement activity:**
- Uses Agent A's spec to write/rewrite the Python activity
- Verifies against screenshots after each change

### Phase 2: Verification (parallel agents)

**Agent C — Code verifier:**
- Reads the modified Python code
- Compares every method, label, key handler against the decompiled source
- Reports discrepancies — READ-ONLY

**Agent D — Screenshot verifier:**
- Reads test result screenshots
- Compares against real device screenshots
- Reports visual discrepancies — READ-ONLY

### Phase 3: Iteration

Discrepancies from Phase 2 agents feed back to Phase 1 Agent B for fixes. Repeat until both verifiers report zero issues.

### Phase 4: Orchestrator Audit

The orchestrating agent (you) independently:
- Picks specific states and traces the full rendering path
- Runs a few test scenarios manually
- Challenges any assumptions in the agent reports

## Common Pitfalls

### 1. Import Path Shadowing
`src/lib/` is prepended to `sys.path`. If a `.py` file in `src/lib/` has the same name as a middleware `.so` (e.g., `scan.py`), it shadows the real `.so`. **Only UI modules should exist in `src/lib/`.**

The `_ACTIVITY_REGISTRY` in `actmain.py` uses **bare imports** (`'activity_main'`, not `'lib.activity_main'`) so that `src/lib/` is found first on `sys.path`.

### 2. `.so` Callback Compatibility
Cython `.so` modules use Python attribute lookup to call methods on listener objects. If the `.so` does `listener.onScanFinish(result)`, our Python class MUST have a method named exactly `onScanFinish` with a compatible signature. Missing or misspelled methods cause silent failures.

### 3. Stale Test Results
The test infrastructure sometimes doesn't clean old results. Always `rm -rf` the results directory AND verify timestamps of output files after a run. If the timestamp predates your code change, the results are stale.

### 4. Doc-to-Code vs Screenshot-to-Code
Previous agents read docs and implemented from specs. The docs had errors. **Always compare against real device screenshots**, not docs. The docs are reference material, not ground truth.

### 5. ProgressBar Rendering
The real device's ProgressBar:
- No "%" counter text
- Progress bar fill is blue (#1C6AEB) on grey background
- Position: near bottom of content area
- Message text ("Scanning...") above the bar
Our `widget.py` ProgressBar may not match — verify against screenshots.

### 6. Toast Rendering
The real device's Toast:
- Dark semi-transparent overlay with icon + text
- Icon is on the left (circle-X for error, checkmark for success)
- Text is white
- Overlay appears in the center of the content area
- `TOAST_CANCEL` command in the key file dismisses it

## Flow Status

| Flow | Scenarios | Status | Notes |
|------|-----------|--------|-------|
| Backlight | 7 | 7/7 PASS locally (settings.so timing issue) | CheckedListView, save/cancel |
| Volume | 7 | 7/7 PASS | CheckedListView, no PWR recovery |
| Diagnosis | 4 | 4/4 PASS | ListView menu, canvas text testing/results |
| Scan | 45 | 32/45 PASS (but ALL stuck at scanning) | **BLOCKED: scan.so callback not firing** |
| Read | 99 | Not started | Depends on scan |
| Write | 61 | Not started | Depends on read |
| Auto-Copy | 53 | Not started | Full pipeline scan→read→write |
| Erase | 10 | Not started | |
| Simulate | 30 | Not started | Independent |
| Sniff | 16 | Not started | Independent |
| LUA Script | 4 | Not started | |
| About | - | Not tested as flow | |
| Time Settings | - | Not tested as flow | |
| PC-Mode | - | Not tested as flow | |

## The Scan Flow Blocker

### Problem
`scan.scanForType(None, self)` is called but:
- Zero PM3 commands are sent
- `onScanFinish()` is never called
- The UI stays stuck at "Scanning... 0%"

### What we know from traces
The real device's AutoCopy trace shows:
1. Activity starts
2. `hf 14a info` PM3 command fires (sent by scan.so internally)
3. Result: `{'found': True, 'uid': '9C750884', 'type': 1, ...}`
4. `onScanFinish(result)` called on the activity

The misc flow trace shows scan sends: `hf 14a reader` (timeout=5888) + `lf sea` (timeout=8888).

### Real device trace (2026-03-31)
File: `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt`

The trace captured 6 complete scan operations on real hardware. Key findings:

**PM3 command sequence (scan.so drives this internally):**
```
1. hf 14a info (timeout=5000)          — always first, check HF
2a. IF HF found (UID in response):
    → hf mf cgetblk 0 (timeout=5888)  — check Gen1a magic
    → hf mfu info (timeout=8888)       — if Ultralight type
    → setScanCache({type: N, uid: '...'})
    → onScanFinish called → show result
2b. IF HF not found (empty response):
    → lf sea (timeout=10000)           — search LF tags
    → hf sea (timeout=10000)           — broader HF search
    → hf felica reader (timeout=10000) — FeliCa check
    → IF still nothing: REPEAT from step 1 (up to 2 cycles)
    → IF found: setScanCache → onScanFinish
    → IF not found after retries: onScanFinish(no tag)
```

**Scan cache dict format** (from POLL lines):
- MFC 1K: `type=1 uid=3AF73501`
- Ultralight: `type=2 uid=00000000000000`
- Indala: `type=10 uid=` (no UID for LF)
- ISO15693: `type=19 uid=E0530110CCA96A11`
- FDX-B: `type=28 uid=`

**Bundle:** Always `None` — `START(ScanActivity, None)`

### Investigation needed
1. **Why `scan.scanForType(None, self)` silently fails under QEMU:**
   - The real device trace shows PM3 commands fire immediately after `START(ScanActivity, None)`
   - Under QEMU with our Python ScanActivity, zero PM3 commands fire
   - `scan.so` IS loaded (no import error), but `scanForType` does nothing
   - Hypothesis: `scan.so` checks for specific attributes/methods on the listener object that our Python class doesn't have, OR `scanForType(None, ...)` skips scanning when type is None
2. **Try different call patterns:**
   - `scan.scanForType(0, self)` — type 0 might mean "scan all"
   - `scan.Scanner().scan_all_asynchronous(self)` — class method
   - `scan.scanForType(self)` — maybe it takes only one arg (the listener)
3. **Check what methods scan.so expects on the listener:**
   - Read `decompiled/scan_ghidra_raw.txt` for `_call_progress_method`, `_call_resulted_method`
   - These internal Scanner methods look up callback names on the listener object
   - Our Python class must expose those exact method names
4. **Add debug instrumentation** to `scan.so` entry points in the launcher:
   ```python
   # In launcher_current.py, after all imports:
   import scan as _scan_mod
   _orig_scanForType = _scan_mod.scanForType
   def _traced_scanForType(*a, **kw):
       print('[TRACE] scanForType args=%s kwargs=%s' % (
           [type(x).__name__ for x in a], kw), flush=True)
       result = _orig_scanForType(*a, **kw)
       print('[TRACE] scanForType returned: %s' % result, flush=True)
       return result
   _scan_mod.scanForType = _traced_scanForType
   ```

## Environment Details

- **Local VM**: sudo password `proxmark`, QEMU rootfs at `/mnt/sdcard/root2/root/`
- **Remote QEMU server**: `qx@178.62.84.144`, password `proxmark`
- **Original IPK**: `/home/qx/02150004_1.0.90.ipk`
- **Real device**: SSH port 2222 reverse tunnel, `root:fa`
- **Xvfb**: Display `:99`, 240x240x24
- **QEMU binary**: `/home/qx/.local/bin/qemu-arm-static`
- **Python 3.8**: `/mnt/sdcard/root2/root/usr/local/python-3.8.0/bin/python3.8`

## Git State

Branch: `feat/ui-framework-replacement`
Key commits:
- `f141885` — TEST_TARGET isolation + visual canary (previous agent)
- `7fecc04` — Initial 37+ activity classes (previous agent — contains errors)
- `8bc0181` — Launcher, widgets, buttons, keys, colors fixes
- `12e16af` — White background + visible selection highlight
- `dd86d10` — ScanActivity calls scan.so directly, bare imports, diagnosis rewrite
