# Read Flow UI Integration — Post-Mortem & Guide

## Branch: `feat/ui-integrating`
## Date: 2026-04-01
## Status: 99/99 read scenarios PASS, 45/45 scan regression PASS

---

## 1. Initial State — What Was Broken

### 1.1 Functionality: Reader API Was Invented

The initial `activity_read.py` used invented Python APIs that did not match the real `.so` module interfaces:

| Component | Invented (Wrong) | Ground Truth (Correct) |
|-----------|------------------|------------------------|
| Scanner constructor | `scan.scanForType(None, self)` | `scan.Scanner()` no-args, then `scanner.scan_all_asynchronous()` |
| Reader constructor | `read.Reader(tag_type, bundle)` | `read.Reader()` no-args, then `reader.start(tag_type, bundle)` — 2 positional args |
| Reader bundle | `{'tag_type': int, 'scan_data': dict}` | `{'infos': scan_cache, 'force': bool}` |
| Progress callback | `onReadProgress(phase, progress, total)` | `onReading(*args)` — receives dict with `{'seconds', 'action', 'keyIndex', 'keyCountMax'}` |
| Completion callback | `onReadComplete(result_code, data)` | No such API. Completion signals arrive via **4 different mechanisms** (see Section 5.3) |

**Ground Truth**: `trace_read_flow_20260401.txt` line 24 — `HFMFREAD.readAllSector((1024, {scan_cache}, <bound method ReadActivity.onReading>))`, `trace_autocopy_mf1k_standard.txt` line 16 — `READER_START args=(1, {'infos': {scan_cache}, 'force': False})`

### 1.2 Functionality: Scan Result Display Was Middleware

The old code had a `_FAMILY_MAP` dict and `_resolve_tag_display()` function that hardcoded tag family names, frequency values, UID formatting, and field layouts. This was 100% wrong — **`template.so` owns ALL card info rendering**. Our code must call `template.draw(tag_type, scan_cache, canvas)` and nothing else.

**Ground Truth**: `read_tag_reading_1.png` — shows MIFARE, M1 S50 1K (4B), Frequency: 13.56MHZ, UID, SAK, ATQA — all rendered by `template.so`

### 1.3 Functionality: Return Code Mapping Was Wrong

The old code used a simple `1=success, -1=fail` binary mapping. The real `.so` modules use a rich return code system with specific actions per code:

| Return Code | Old Behavior | Correct Behavior | Ground Truth |
|-------------|-------------|------------------|--------------|
| `-1` | "Read Failed" always | HF tags (uid in cache) → "Read Failed"; LF tags (no uid) → "Wrong type" | Test classification: 14 tests with `ret=-1` |
| `-2` | Unknown | "Read Failed" (all reader types) | 14 tests confirmed |
| `-3` | Unknown | Push WarningM1Activity (partial key recovery possible) | `trace_fail_read_flow_20260401.txt` |
| `-4` | Unknown | Push WarningM1Activity (method failed, e.g. darkside not vulnerable) | darkside_fail tests |
| `-7` | Unknown | Push WarningT5XActivity (T55xx check failed) | `trace_fail_read_flow_20260401.txt` line 96-98 |

**Ground Truth**: `trace_fail_read_flow_20260401.txt` lines 96-98 — `LFREAD.createRetObj(None, None, -7)` → `START(WarningT5XActivity, -7)` → `POLL stack=['dict', 'dict', 'dict']`

### 1.4 Functionality: Console Was a Separate Activity (Wrong)

The initial implementation pushed `ConsolePrinterActivity` as a separate activity onto the stack when the user pressed RIGHT. This was architecturally wrong.

**Ground Truth**: `trace_console_flow_20260401.txt` — Activity stack stays at `['dict', 'dict']` throughout console open/close cycles. Console is a **view mode** within ReadListActivity, NOT a separate activity. No `START()` or `FINISH()` appears in the trace during console toggles.

### 1.5 Functionality: PWR Key Never Reached Activities

The `_COMPAT_MAP` in `keymap.py` was missing the `'PWR_PRES!'` entry. The test launcher constructs key codes as `'%s_PRES!' % name`, so PWR produced `'PWR_PRES!'`. Every other key had a legacy `X_PRES!` entry, but PWR only had hardware-specific variants (`_PWR_CAN_PRES!`, `PWR_CAN_PRES!`). PWR was silently dropped by `_compat()` returning `None`.

Additionally, the old `keymap.py` had `if logical == POWER: self._run_shutdown(); return` which called `actstack.finish_activity()` directly, bypassing per-activity `onKeyEvent()`. Even if PWR had been mapped, ReadActivity couldn't have used it to hide the console — it would have popped the entire activity.

**Ground Truth**: `tools/launcher_current.py` line 614 — `keycode = '%s_PRES!' % name`, `src/lib/keymap.py` `_COMPAT_MAP` — no `'PWR_PRES!'` entry

### 1.6 UI: Toast Text Wrapping

Toast messages like "Read Successful!\nFile saved" were displayed as single-line overflows. The real device shows these as multi-line with `\n` as a semantic break point.

**Ground Truth**: `read_tag_no_tag_or_wrong_type_3.png` — toast shows two-line message with checkmark icon

### 1.7 UI: WarningM1Activity Page Model

The old WarningM1Activity had a 4-page model (one option per page). The real device uses a 2-page model with M1/M2 buttons per page:

| Page | M1 Action | M2 Action |
|------|-----------|-----------|
| 0 | Sniff | Enter Key |
| 1 | Force | PC-Mode |

**Ground Truth**: `activity_main_strings.txt` — WarningM1Activity symbols, `force-read` test Phase 2 expects `M1:Sniff`

---

## 2. Ground Truth Resources — What Was Vital

### 2.1 Real Device Traces (AUTHORITATIVE)

These traces are the **primary source of truth**. Every architectural decision derives from them.

| Trace | Path | Content | Key Findings |
|-------|------|---------|--------------|
| **Successful MFC Read** | `docs/Real_Hardware_Intel/trace_read_flow_20260401.txt` | 2 complete MFC 1K reads (UID: AA991523, 3AF73501) | Stack stays `['dict', 'dict']` — NO separate ReadActivity pushed. `hf 14a info` → `hf mf cgetblk 0` → `hf mf fchk` (108 keys, strategy 1) → `readAllSector` with `callListener(sector, 16, callback)` × 16 → `cacheFile(.eml, .bin)`. `readAllSector returned: 1`. Entire cycle: 7-10s. |
| **Failed LF Read** | `docs/Real_Hardware_Intel/trace_fail_read_flow_20260401.txt` | Failed Noralsy (type 23) read | `lf noralsy read` × 4 → `ret=-1` each → fallback: `lf gallagher read` × 2 → `lf t55xx detect` → `lf t55xx chk` → `createRetObj(None, None, -7)` → `START(WarningT5XActivity, -7)` → stack becomes `['dict', 'dict', 'dict']`. Shows **PUSH path** where read.so directly pushes Warning activities. |
| **Console Flow** | `docs/Real_Hardware_Intel/trace_console_flow_20260401.txt` | Console open/close during MFC read | **CRITICAL**: Stack stays `['dict', 'dict']` throughout — console is purely a view toggle within ReadListActivity. No activity push/pop on RIGHT or PWR. Read continues uninterrupted in background. Deferred result pattern: read completes while console showing, toast appears after PWR exit. |
| **iCLASS Elite Read** | `docs/Real_Hardware_Intel/trace_iclass_elite_read_20260401.txt` | iCLASS with elite key | `hf iclass rdbl b 01 k 2020666666668888 e` — note the `e` flag for elite key mode. Dump sequence follows. |

### 2.2 Real Device Screenshots

| Screenshot | Path | What It Proved |
|-----------|------|---------------|
| `read_tag_scanning_1-12.png` | `docs/Real_Hardware_Intel/Screenshots/` | Scan phase: tag detection progress, ProgressBar at correct position, "Scanning..." text |
| `read_tag_reading_1-7.png` | `docs/Real_Hardware_Intel/Screenshots/` | Read phase: template rendering by template.so (MIFARE, UID, SAK, ATQA), blue status text (`#1C6AEB`), countdown timer `"MM'SS''"` format, key progress `"ChkDIC...0/32keys"` |
| `read_tag_no_tag_or_wrong_type_1-3.png` | `docs/Real_Hardware_Intel/Screenshots/` | Error states: toast with error icon, M1/M2 buttons. `_3.png` is actually success (checkmark + "Read Successful! File saved") — **misnamed in original capture** |
| `read_tag_list_1_8.png`, `read_tag_list_8_8.png` | `docs/Real_Hardware_Intel/Screenshots/` | ReadListActivity: 40 tag types across 8 pages, 5 items per page, page indicator "1/8" |
| `lua_console_1-10.png` | `docs/Real_Hardware_Intel/Screenshots/` | Console appearance: **full-screen black background**, white monospace text (PM3 output), **NO title bar**, **NO button bar**. Shows zoom stages (different font sizes) and scrolled states |

### 2.3 Decompiled .so String Files

| File | Path | Key Symbols |
|------|------|-------------|
| `activity_main_strings.txt` | `docs/v1090_strings/` | `ReadActivity.onReading`, `ReadActivity.showReadToast`, `ReadActivity.hideReadToast`, `ReadActivity.onData`, `ReadActivity.canidle`, `ReadListActivity.initList`, `ConsolePrinterActivity.show/hidden/is_showing/textfontsizeup/textfontsizedown`, `WarningM1Activity` |
| `read_strings.txt` | `docs/v1090_strings/` | `Reader` class: `call_reading`, `call_exception`, `start`, `stop`, `is_reading`. PM3 commands: `hf mf fchk`, `hf mf rdsc`, `hf mfu dump`, `hf iclass dump` |
| `actstack_strings.txt` | `docs/v1090_strings/` | `finish_activity`, `get_activity_pck`, `register`, `unregister`, lifecycle: `onCreate`, `onResume`, `onPause`, `onDestroy` |
| `actbase_strings.txt` | `docs/v1090_strings/` | `setTitle`, `setLeftButton`, `setRightButton`, `dismissButton`, `callKeyEvent`, `onKeyEvent` |

### 2.4 Techniques That Were Vital

1. **Real device tracing with function patching**: Patching `hfmfread.readAllSector`, `hfmfread.callListener`, `hfmfkeys.fchks` etc. to log arguments and return values. This revealed the exact callback signatures, argument formats, and completion sequences.

2. **QEMU probing**: Running the real `.so` modules under QEMU to discover constructor signatures (`Reader()` no-args), method signatures (`start(tag_type, bundle)` 2 positional), and callback patterns.

3. **Test-driven state classification**: With 99 test scenarios covering every tag type and error path, the test results themselves became a classification system. When `ret=-2` consistently mapped to "Read Failed" across 14 different scenarios, that became the ground truth for that return code.

4. **Deferred execution logging**: Writing callback arguments to `/tmp/_onreading_args.log` during QEMU runs to discover the exact progress data format (`{'seconds': 66, 'action': 'ChkDIC', 'keyIndex': 0, 'keyCountMax': 32}`).

5. **Screenshot pixel-hash comparison**: The test framework computes MD5 hashes of screenshots (with battery icon masked) to detect visual changes. This enabled the 9-gate console test that verifies each key press produces a visible change.

---

## 3. Solutions Implemented

### 3.1 ReadActivity State Machine

**File**: `src/lib/activity_read.py`

Complete rewrite from invented APIs to ground-truth-only. The state machine has 7 states:

```
idle → scanning → reading → read_success / read_partial / read_failed / no_tag / warning_keys
```

Key architectural decision: **ReadActivity is a thin UI shell**. The `.so` modules (`read.so`, `scan.so`, `template.so`) handle ALL RFID logic. ReadActivity only:
1. Creates Scanner/Reader instances and binds callbacks
2. Routes completion signals to toast/button rendering
3. Handles key events for navigation

```python
# Ground truth: QEMU probe — Scanner() no-args, scan_all_asynchronous() no-args
self._scanner = _scan_mod.Scanner()
self._scanner.call_progress = self.onScanning
self._scanner.call_resulted = self.onScanFinish
self._scanner.call_exception = self.onScanFinish
self._scanner.scan_all_asynchronous()

# Ground truth: trace_autocopy_mf1k_standard.txt line 16
# READER_START args=(1, {'infos': {scan_cache}, 'force': False})
self._reader = _read_mod.Reader()
self._reader.call_reading = self.onReading
self._reader.call_exception = self._onReadException
self._reader.start(self._tag_type, bundle)
```

**Ground Truth**: `trace_read_flow_20260401.txt`, `trace_autocopy_mf1k_standard.txt`

### 3.2 Four Completion Mechanisms

The hardest architectural discovery: read.so signals completion via **4 different paths** depending on the reader type and outcome:

```python
# Mechanism 1: MFC completion dict through call_reading
# Ground truth: /tmp/_onreading_force.log
# {'success': False, 'tag_info': {...}, 'return': -3}
data = args[0]
if isinstance(data, dict) and 'success' in data:
    ret_code = data.get('return', 0)
    if success:
        self._showReadSuccess()
    elif ret_code in (-3, -4):
        self._launchWarningKeys()
    elif ret_code == -2:
        self._showReadFailed()
    # ...

# Mechanism 2: LF/T55xx Warning push (read.so calls actstack directly)
# Ground truth: trace_fail_read_flow_20260401.txt line 98
# START(WarningT5XActivity, -7) — stack becomes depth 3

# Mechanism 3: call_exception fires with traceback
# Ground truth: QEMU probe — only reliable callback for some readers

# Mechanism 4: is_reading() poll fallback (background thread)
# Waits for reader.is_reading() == False, then 2s grace period
# for mechanisms 1-3 to fire before falling back
```

### 3.3 Console as Inline View (Not Activity)

**File**: `src/lib/activity_read.py` — `_showConsole()` / `_hideConsole()`

```python
def _showConsole(self):
    """Show inline console view (NOT a separate activity).
    Ground truth: trace_console_flow_20260401.txt — stack stays ['dict', 'dict']"""
    self._console_showing = True
    if self._console is None:
        from lib.widget import ConsoleView
        self._console = ConsoleView(canvas, x=0, y=0,
                                    width=SCREEN_W, height=SCREEN_H)
    self._console.clear()
    # Load PM3 output from executor cache
    import executor
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if cache:
        self._console.addText(cache)
    self._console.autofit_font_size()
    self._console.show()
    # Start polling for live updates during read (0.3s interval)
    # ...daemon thread polls executor.CONTENT_OUT_IN__TXT_CACHE...
```

**Ground Truth**: `trace_console_flow_20260401.txt` — activity stack unchanged during console

### 3.4 Deferred Result Mechanism

When the console is showing and a read completes, the toast/buttons must NOT display over the console. Instead, the result is stored and replayed when the user exits the console via PWR.

```python
def _showReadSuccess(self, partial=False):
    self._state = 'read_partial' if partial else 'read_success'
    if self._console_showing:
        self._pending_result = ('success', partial)
        return
    # ... render toast and buttons normally ...

def _hideConsole(self):
    self._console_showing = False
    self._console.hide()
    # Replay deferred result
    if self._pending_result is not None:
        kind, data = self._pending_result
        self._pending_result = None
        if kind == 'success':
            self._showReadSuccess(partial=data)
        elif kind == 'failed':
            self._showReadFailed()
        elif kind == 'no_tag':
            self._showNoTag(data)
```

**Ground Truth**: `trace_console_flow_20260401.txt` — read completes during console, toast appears after PWR

### 3.5 PWR Key Fix

**File**: `src/lib/keymap.py`

Two changes:

1. Added `'PWR_PRES!'` to `_COMPAT_MAP`:
```python
# PWR variants (hardware uses _PWR_CAN_PRES!, launcher uses PWR_PRES!)
'PWR_PRES!':          POWER,
'_PWR_CAN_PRES!':     POWER,
'PWR_CAN_PRES!':      POWER,
```

2. Removed the global PWR→finish shortcut so each activity handles PWR in its own `onKeyEvent`:
```python
# REMOVED:
# if logical == POWER:
#     self._run_shutdown()  # called actstack.finish_activity()
#     return

# NOW: PWR goes through onKeyEvent like all other keys
target.callKeyEvent(logical)
```

This was critical because ReadActivity needs PWR to either:
- Hide the console (when `_console_showing == True`)
- Finish the activity (when in normal mode)

The old global shortcut always called `finish_activity()`, making console hide impossible.

**Ground Truth**: `tools/launcher_current.py` line 614 — `keycode = '%s_PRES!' % name`, original `keymap.so` `_run_shutdown` actually runs `sudo shutdown -t 0` (system shutdown), NOT activity pop

### 3.6 actstack Result Passing

**File**: `src/lib/actstack.py`

Added result forwarding from child to parent activity:

```python
def finish_activity():
    act = _ACTIVITY_STACK.pop()
    result = getattr(act, '_result', None)  # NEW
    # ... lifecycle teardown ...
    if _ACTIVITY_STACK:
        prev_act = _ACTIVITY_STACK[-1]
        prev_act.onResume()
        # Pass result from finished activity to parent
        if result is not None:
            prev_act.onActivity(result)  # NEW
```

This enables WarningM1Activity to communicate its chosen action (`force`, `sniff`, `enter_key`) back to ReadActivity.

**Ground Truth**: `force-read` test Phase 3 — WarningM1Activity finishes with `result={'action': 'force'}`, ReadActivity receives via `onActivity()` and calls `_startRead(force=True)`

### 3.7 Toast Auto-Wrap

**File**: `src/lib/widget.py` — `Toast.show()`

```python
def show(self, message, duration_ms=None, mode=None, icon=None, wrap='auto'):
    # 'auto': split on \n, wrap overflows, auto-reduce font if >3 lines
    # 'no-wrap': preserve \n exactly
    # 'no-resize': wrap naturally, never reduce font
```

**Ground Truth**: `read_tag_no_tag_or_wrong_type_3.png` — two-line toast with proper wrapping

### 3.8 ConsoleView Widget

**File**: `src/lib/widget.py` — `class ConsoleView`

Full-screen monospace text viewer with:
- **Zoom**: `textfontsizeup()` / `textfontsizedown()`, range 6-14, default 14
- **Horizontal scroll**: `scrollRight()` / `scrollLeft()`, 20px step
- **Autofit**: `autofit_font_size()` — largest font where longest line fits width
- **Scrollbar**: 4px on right edge, track #444444, thumb #AAAAAA, proportional
- **Live update**: `addText()` appends new PM3 output during read

Console key mapping (per `read_console_common.sh` lines 27-35):
```
UP / M2   → textfontsizeup()   (zoom in, max 14)
DOWN / M1 → textfontsizedown() (zoom out, min 6)
RIGHT     → scrollRight()      (horizontal scroll right)
LEFT      → scrollLeft()       (horizontal scroll left)
PWR       → exit console       (back to ReadActivity view)
```

**Ground Truth**: `lua_console_1-10.png` — full-screen black, white monospace, no title/button bar; `read_console_common.sh` — 9-gate test exercise sequence

---

## 4. JSON UI Requirements

### 4.1 ReadActivity Status Text (JsonRenderer)

Read progress is rendered via `JsonRenderer._render_text()`:

```python
self._jr._render_text({
    'y': 175,                  # Starting Y position
    'tag': '_read_status',     # Canvas tag for cleanup
    'lines': [
        {'text': "01'08''", 'align': 'center', 'color': '#1C6AEB'},
        {'text': "ChkDIC...0/32keys", 'align': 'center', 'color': '#1C6AEB'},
    ],
})
```

**Ground Truth**: `read_tag_reading_2.png` — centered blue text below template

### 4.2 Toast Schema

```python
Toast.show(
    message="Read Successful!\nFile saved",
    mode=Toast.MASK_CENTER,     # Full-screen semi-transparent overlay
    icon='check',               # 'check' → right.png, 'error' → wrong.png
    duration_ms=0,              # 0 = persistent until dismissed
    wrap='auto',                # 'auto' | 'no-wrap' | 'no-resize'
)
```

### 4.3 Button Bar Schema

```python
# Success: M1=Reread, M2=Write
self.setLeftButton(resources.get_str('reread'))
self.setRightButton(resources.get_str('write'))

# Failed: M1=Reread, M2=empty
self.setLeftButton(resources.get_str('reread'))
self.setRightButton('')

# No tag: M1=Rescan, M2=Rescan
self.setLeftButton(resources.get_str('rescan'))
self.setRightButton(resources.get_str('rescan'))

# Reading: M1=Rescan, M2=empty (console_during_read test gate)
self.setLeftButton(resources.get_str('rescan'))
self.setRightButton('')
```

### 4.4 Template Rendering

Card info is **exclusively** rendered by `template.so` — never by Python:

```python
import template
template.draw(tag_type, scan_cache, canvas)  # renders ALL card info
template.dedraw(canvas)                       # cleanup
```

---

## 5. NO MIDDLEWARE — Violations Found and Removed

### 5.1 Rule Definition

**NO MIDDLEWARE** means: Our Python code NEVER reimplements logic that belongs to the `.so` modules. We are a **thin UI shell** that:
- Creates instances of `.so` classes
- Binds callbacks
- Routes completion signals to toast/button rendering
- Handles key events for navigation

We do NOT:
- Parse PM3 command output
- Make RFID decisions (which key to try, what scan command to send)
- Format tag display data (that's template.so)
- Classify tag types (that's scan.so)
- Decide which reader to use (that's read.so)

### 5.2 Middleware Violations Found and Removed

#### Violation 1: `_FAMILY_MAP` / `_resolve_tag_display()`

**What it was**: A Python dict mapping tag type IDs to display strings (family name, frequency, icon), plus a function that formatted scan results into display lines.

**Why it was wrong**: `template.so` owns ALL card info rendering. It reads the scan cache and renders to the canvas directly.

**Fix**: Replaced with a single `template.draw(tag_type, scan_cache, canvas)` call.

**Ground Truth**: `read_tag_reading_1.png` — template.so renders the card info display

#### Violation 2: Invented `onReadComplete(result_code, data)` Callback

**What it was**: A Python callback signature that didn't exist in the real `.so` module.

**Why it was wrong**: read.so doesn't have a `call_complete` property. Completion arrives via `call_reading` (mechanism 1), direct activity push (mechanism 2), `call_exception` (mechanism 3), or `is_reading()` poll (mechanism 4).

**Fix**: Replaced with the 4-mechanism completion model discovered from traces.

**Ground Truth**: `trace_read_flow_20260401.txt` — no `onReadComplete` call in trace

#### Violation 3: Hardcoded Reader Bundle Format

**What it was**: `{'tag_type': int, 'scan_data': dict}` — invented key names.

**Why it was wrong**: Real device trace shows `{'infos': scan_cache, 'force': bool}`.

**Fix**: Changed bundle to match trace: `bundle = {'infos': scan_cache, 'force': force}`

**Ground Truth**: `trace_autocopy_mf1k_standard.txt` line 16 — `READER_START args=(1, {'infos': {scan_cache}, 'force': False})`

#### Violation 4: ConsolePrinterActivity as Separate Activity

**What it was**: Pushing `ConsolePrinterActivity` onto the activity stack when RIGHT was pressed.

**Why it was wrong**: Real device trace shows stack unchanged during console. Console is a view overlay within the same activity.

**Fix**: Implemented console as `ConsoleView` canvas overlay within ReadActivity.

**Ground Truth**: `trace_console_flow_20260401.txt` — stack stays `['dict', 'dict']`

#### Violation 5: PWR as Global finish_activity()

**What it was**: `keymap.py` intercepting PWR globally and calling `actstack.finish_activity()`.

**Why it was wrong**: The original `keymap.so` `_run_shutdown` runs `sudo shutdown -t 0` (system shutdown, not activity pop). Activity pop is per-activity logic in each activity's `onKeyEvent`.

**Fix**: Removed the global shortcut. PWR now goes through `onKeyEvent()` like all other keys.

**Ground Truth**: `activity_main_strings.txt` — `ReadActivity.onKeyEvent` handles PWR

### 5.3 Fixture Corrections (With Trace Evidence)

Only 2 fixture corrections were made, both with real device trace evidence:

#### iCLASS Elite Key Flag

**Before**: `hf iclass rdbl b 01 k 2020666666668888`
**After**: `hf iclass rdbl b 01 k 2020666666668888 e`

**Ground Truth**: `trace_iclass_elite_read_20260401.txt` — the `e` flag is present in the real command

#### EM4305 Chipset Detection Line

**Before**: `lf sea` response missing chipset line
**After**: Added `[+] Chipset detection: EM4x05 / EM4x69` to `lf sea` response

**Ground Truth**: PM3 source `cmdlf.c` — `lfsearch_strings.txt` shows this line is output by `lf sea` when an EM4x05 is detected. Cross-referenced with `https://github.com/iCopy-X-Community/icopyx-community-pm3` cmdlf.c lf_search function.

---

## 6. Test Architecture

### 6.1 Test Suite Structure

99 scenarios organized by tag type and behavior:

| Category | Count | Examples |
|----------|-------|---------|
| MIFARE Classic 1K | 30 | `all_default_keys`, `darkside_fail`, `nested_retry`, `force_from_nested_fail`, `gen1a_csave_success`, `console_during_read`, `console_on_success` |
| MIFARE Classic 4K | 7 | `all_keys`, `7b_all_keys`, `darkside_fail`, `gen1a_csave_success` |
| MIFARE Ultralight | 8 | `success`, `empty`, `partial`, `ev1_success`, `c_success`, `card_select_fail`, `console_during_read`, `console_on_success` |
| NTAG | 3 | `ntag213_success`, `ntag215_success`, `ntag216_success` |
| iCLASS | 5 | `elite`, `legacy`, `no_key`, `dump_fail`, `console_during_read` |
| LF card formats | 20+ | `em410x`, `awid`, `fdxb`, `hid`, `indala`, `gallagher`, `keri`, `nedap`, `nexwatch`, etc. |
| LF T5577 | 5 | `t55xx`, `with_password`, `block_read`, `detect_fail`, `console_during_read` |
| LF EM4305 | 3 | `success`, `block_read`, `fail` |
| Other HF | 9 | `iso15693`, `felica_success`, `legic`, etc. |
| Error/Edge | 5 | `no_tag`, `wrong_type`, `lf_fail` |
| Console tests | 14 | 5 `console_during_read`, 4 `console_on_result`, 5 negative/partial |

### 6.2 Console Test Framework

**File**: `tests/flows/read/includes/read_console_common.sh`

The console test uses a **9-gate exercise sequence**. Each key press is a separate gate verified by comparing screenshot pixel hashes (battery icon masked):

```
Gate 1: RIGHT — horizontal scroll right (text overflows at font 14)
Gate 2: LEFT  — horizontal scroll back to origin
Gate 3: DOWN  — zoom out (14→13)
Gate 4: DOWN  — zoom out more (13→12)
Gate 5: M1    — confirms M1 = fontsize down (12→11)
Gate 6: UP    — zoom in (11→12)
Gate 7: M2    — confirms M2 = fontsize up (12→13)
Gate 8: UP    — zoom back to max (13→14)
Gate 9: DOWN  — final zoom out round-trip (14→13)
```

The `during_read` variant:
1. Waits for `M1:Rescan` trigger (proves scan completed, read started)
2. Sends RIGHT to open console mid-read
3. Runs 9-gate exercise
4. Sends PWR to exit console
5. Verifies return to ReadActivity (state dump check)
6. Waits for result trigger (e.g., `toast:File saved`) — **this is where the 5 tests were failing**
7. Deduplicates screenshots, reports pass/fail

### 6.3 Running Tests

```bash
# Single test locally
TEST_TARGET=current SCENARIO=read_ultralight_console_during_read FLOW=read \
  bash tests/flows/read/scenarios/read_ultralight_console_during_read/read_ultralight_console_during_read.sh

# Full parallel suite on remote (48-core server)
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/read/test_reads_parallel.sh 16'

# Results
cat tests/flows/_results/current/read/scenario_summary.txt
```

---

## 7. High-Level Summary

### 7.1 Problems and Solutions

| # | Problem | Root Cause | Solution | Commits |
|---|---------|-----------|----------|---------|
| 1 | Scanner/Reader not calling back | Wrong API signatures — `scan.scanForType(None, self)` instead of `Scanner()` + `scan_all_asynchronous()` | QEMU probing revealed correct signatures. Complete rewrite to ground-truth APIs | `7c3d0cf` |
| 2 | Card info not rendering | Python middleware (`_FAMILY_MAP`) instead of `template.draw()` | Replaced with single `template.draw(tag_type, scan_cache, canvas)` call | `7c3d0cf` |
| 3 | Read completion unreliable | Assumed single callback path. Real `.so` uses 4 different completion mechanisms depending on reader type | Implemented all 4 mechanisms: completion dict, direct Warning push, exception callback, polling fallback | `7c3d0cf` |
| 4 | Console opens but breaks activity stack | Pushed ConsolePrinterActivity as separate activity | Changed to inline ConsoleView overlay within ReadActivity | `ae860cf` |
| 5 | Console keys not working (zoom, scroll) | ConsoleView was basic — no zoom range, no horizontal scroll | Added textfontsizeup/down (6-14), scrollRight/Left, autofit_font_size, scrollbar | `88436ad`, `ca6a7ad` |
| 6 | Read completes during console — toast never shown | No deferred result mechanism | Added `_pending_result` storage in console mode, replay on `_hideConsole()` | `ca6a7ad` |
| 7 | PWR in console doesn't exit | `'PWR_PRES!'` not in keymap `_COMPAT_MAP` | Added `'PWR_PRES!': POWER` to compat map | `c85c1c6` |
| 8 | PWR would pop activity instead of hiding console | `keymap.py` global PWR→finish_activity() shortcut | Removed shortcut, let each activity handle PWR in onKeyEvent | `c85c1c6` |
| 9 | WarningM1Activity wrong page model | 4-page (1 option each) instead of 2-page (2 options each) | Rewrote to 2-page model with M1/M2 per page | `7c3d0cf` |
| 10 | Toast wrapping broken | Single-line overflow for multi-line messages | Auto-wrap with `\n` as semantic breaks, font auto-reduction | `ca6a7ad` |

### 7.2 Test Progression

```
Commit 7c3d0cf: 89/99 PASS (10 console remaining)
Commit 88436ad: Console wiring (zoom, scroll, keys)
Commit ae860cf: Console as inline view → all 8 console tests pass structure-wise
Commit ca6a7ad: 96/99 PASS (deferred results, autofit, 3 timing edge cases)
Commit c85c1c6: 99/99 PASS (PWR_PRES! keymap fix)
```

### 7.3 Steps Taken

1. **Captured 3 real device traces** (successful read, failed LF read, console flow)
2. **Analyzed trace data** to discover: Scanner/Reader API signatures, callback formats, completion mechanisms, activity stack behavior during console
3. **Complete rewrite** of activity_read.py from invented APIs to ground-truth-only
4. **QEMU probing** to verify constructor signatures and callback patterns
5. **Test-driven iteration**: Run 99 tests, classify failures, fix one class at a time
6. **Console architectural change**: separate activity → inline view (trace-driven)
7. **Deferred result mechanism**: for console-during-read timing
8. **Final keymap fix**: 1-line `_COMPAT_MAP` entry unblocked all 5 remaining tests

---

## 8. What Would Have Made This Faster

### 8.1 Information Missing at Start

1. **The 4 completion mechanisms**: If documented upfront that read.so signals completion via call_reading dict, direct Warning push, call_exception, AND is_reading() poll, the first commit would have been much cleaner. This was discovered incrementally through test failures.

2. **Console is a view, not an activity**: This should have been the FIRST thing verified via trace. Instead, an entire ConsolePrinterActivity was built as a separate activity, then had to be rewritten as inline ConsoleView. The trace (`trace_console_flow_20260401.txt`) was captured AFTER the first failed approach.

3. **PWR_PRES! keymap gap**: This single missing compat map entry blocked 5 tests through the entire session. If the key injection pipeline had been audited first (launcher constructs `'%s_PRES!' % name`, keymap only has `_PWR_CAN_PRES!`), this would have been a 30-second fix.

4. **Return code classification table**: The mapping of return codes (-1 through -7) to UI actions was discovered test-by-test. A pre-built table from binary analysis would have saved hours.

5. **Reader bundle format**: The exact format `{'infos': scan_cache, 'force': bool}` was discovered from a real trace. If the autocopy trace had been captured earlier, this would have been known from the start.

### 8.2 Pre-Work Checklist for Future Flows

Before starting ANY new flow integration, capture:

1. **Real device traces** for EVERY distinct path (success, failure, each error variant)
2. **Activity stack behavior** during all interactions (is it a push or a view toggle?)
3. **Constructor signatures** from QEMU probing (`Class()` no-args vs `Class(arg)`)
4. **Callback signatures** from QEMU with logging patches
5. **Return code → UI action mapping** from exhaustive test classification
6. **Key injection audit**: verify ALL keys in the flow have `_COMPAT_MAP` entries matching the launcher's format

---

## 9. Commit History

| Hash | Message | Files | Tests |
|------|---------|-------|-------|
| `7c3d0cf` | feat: read flow UI integration — 89/99 PASS | 13 files (+913 -590) | 89/99 |
| `88436ad` | feat: ConsolePrinterActivity + console tests wiring | 4 files (+213 -137) | — |
| `ae860cf` | fix: console as inline view mode (not separate activity) | 1 file (+99 -15) | 96/99 (structure) |
| `ca6a7ad` | fix: UI polish — toast wrapping, console deferred results, scrollbar, autofit | 5 files (+209 -32) | 96/99 |
| `c85c1c6` | fix: add PWR_PRES! to keymap compat map — 99/99 read tests PASS | 1 file (+9 -11) | **99/99** |

---

## 10. Ground Truth Enforcement Rules

These rules governed every line of code written during this integration:

1. **Only `.so` binaries are truth** — decompiled string tables at `docs/v1090_strings/`
2. **Real device traces are authoritative** — `docs/Real_Hardware_Intel/trace_*.txt`
3. **Real device screenshots define UI** — `docs/Real_Hardware_Intel/Screenshots/`
4. **NEVER invent APIs** — every constructor call, callback name, and argument format must come from a trace or QEMU probe
5. **NEVER write middleware** — our Python is a thin UI shell, not RFID logic
6. **Fixtures are immutable data** — no logic, no branching, no function calls
7. **Tests are immutable** — the 99 test scripts define correct behavior
8. **Every code line must cite ground truth** — if you can't cite it, don't write it
9. **After writing code, audit it** — "Does this come directly from ground truth?"
10. **If no ground truth exists, STOP and ask** — capture a new trace or probe QEMU

For the PM3 source code for this exact hardware version, use:
`https://github.com/iCopy-X-Community/icopyx-community-pm3`

This is used when trace results are truncated (e.g., `lf sea` output cut off) and you need to verify the full PM3 command output format. Example: the `[+] Chipset detection: EM4x05 / EM4x69` line was verified via `cmdlf.c` in this repo.
