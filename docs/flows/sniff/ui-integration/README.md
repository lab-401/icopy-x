# Sniff Flow — UI Integration Post-Mortem & Handover

## 1. Initial State & Problems Found

### 1.1 Functional Problems

The SniffActivity started with 23 scenarios (from a prior session) but had critical parity gaps with the original firmware:

1. **Missing parser results**: `parserKeyForM1()` and `parserUidForData()` never called successfully. The original `.so` extracts UID and keys from trace data — our Python showed only `TraceLen: N`.
2. **Wrong function name**: `onData` called `parserTraceLen()` — this function does NOT exist in `sniff.so`. The correct name is `parserHfTraceLen()` (verified via QEMU attribute probe: `[a for a in dir(sniff) if 'parser' in a.lower()]`).
3. **Wrong marker string**: `onData` checked for `125k_sniff_finished` — doesn't exist in any `.so` binary. The correct signal is `t5577_sniff_finished` (a resource string, not a PM3 marker). T5577 auto-finishes based on `selected_type_id == '125k'`.
4. **T5577 manual finish was not a real flow**: QEMU trace (`trace_sniff_t5577_enhanced_20260404.txt`) proved `lf t55xx sniff` blocks with `timeout=-1` until PM3 completes. T5577 ALWAYS auto-finishes. The `sniff_t5577_manual_finish` scenario was removed.
5. **Save not implemented**: `_saveSniffData` called `sniff_mod.saveSniffData()` — but `saveSniffData` is NOT in `sniff.so`. It's in `activity_main.so`, which we replaced with Python. The save logic (write executor cache to `/mnt/upan/trace/{type}_{N}.txt`) had to be implemented.
6. **Empty trace showed Decoding screen**: The original `.so` skips Decoding entirely for empty/failed traces. Our code showed "Decoding... 0/0" with ProgressBar.
7. **Button suppression**: Dimmed buttons (M2=Save inactive for empty traces) still responded to key presses. Fixed via `callKeyEvent` guards in `BaseActivity`.

### 1.2 UI Problems

1. **Result text alignment wrong**: Rendered via `BigTextListView` (left-aligned at x=19, anchor='nw'). QEMU canvas trace proved: empty traces render centered at `(120, 120)`, data traces render with TraceLen centered at `(120, 68)` and data left-aligned at `(19, 100+)`.
2. **Decoding text position wrong**: Initially at `y=168`, QEMU canvas trace proved it's at `y=186`.
3. **No page arrows on instruction screens**: Real device FB captures show ▼/▲ arrows between Start/Finish buttons for multi-page instructions. Implemented using `res/img/down.png`, `up.png`, `down_up.png` image assets.
4. **Button bar visible during Decoding**: Used `setLeftButton('')` which hides text but leaves dark background. Changed to `dismissButton()` — confirmed by FB captures showing no button bar during Decoding.
5. **Title incorrectly reset**: `_finishHfResult` set title to "Sniff TRF 1/1". FB captures prove title persists from instruction phase (e.g., "1/4" for HF).
6. **Missing "Processing..." toast**: FB captures show "Processing..." toast before "Trace file saved". Our code only showed the latter.

---

## 2. Critical Resources & Techniques

### 2.1 QEMU Canvas State Tracing

The single most important technique. Added a 100ms polling loop to `launcher_original.py` that dumps all canvas text items containing "TraceLen", "Decoding", "UID", "Key":

```python
# Canvas state polling — periodically dump all text items
_prev_canvas_texts = [set()]
def _poll_canvas_state():
    for item in canvas.find_all():
        if canvas.type(item) == 'text':
            txt = canvas.itemcget(item, 'text')
            if 'Decoding' in txt or 'TraceLen' in txt:
                texts.add('id=%s %r xy=(%.0f,%.0f) fill=%s' % (
                    item, txt[:40], coords[0], coords[1], fill))
    if texts != _prev_canvas_texts[0]:
        _tlog('CANVAS+ %s' % (texts - _prev_canvas_texts[0]))
        _tlog('CANVAS- %s' % (_prev_canvas_texts[0] - texts))
    self.after(100, _poll_canvas_state)
```

This revealed:
- Exact pixel positions: `'TraceLen: 2298' xy=(120,68)`, `'Decoding...\n0/2298' xy=(120,186)`
- Empty trace creates ONLY `'TraceLen: 0' xy=(120,120)` — NO Decoding items
- Data trace result items at `(19,60)`, `(19,100)`, `(19,140)` — 40px spacing
- Original `.so` doesn't delete canvas items — Decoding text persists as stale items under result
- Items flicker every ~100ms (`.so` internal redraw loop)

### 2.2 QEMU Thread Tracing

Added `threading.current_thread().name` to the PM3 mock:

```python
print('[PM3-THREAD] %s' % threading.current_thread().name, flush=True)
```

Revealed:
- `hf 14a sniff` runs on Thread-9 (sniff BG task)
- `hf list mf` runs on Thread-10 (parse BG task)
- Two SEPARATE `startBGTask` calls, not one
- Key events dispatched via serial buffer (hmi_driver thread), not tkinter main thread

### 2.3 QEMU Parser Probing

Direct probing of sniff.so function signatures under QEMU:

```python
# List all exported parser functions
print([a for a in dir(sniff_mod) if 'parser' in a.lower()])
# → ['parserHfTraceLen', 'parserKeyForM1', 'parserLfTraceLen', ...]
# Note: NO 'parserTraceLen' — the MODULE_AUDIT was wrong

# Probe calling conventions
try:
    result = sniff_mod.parserKeyForM1()
except TypeError as e:
    print(e)  # "takes no arguments" or "takes exactly one argument"
```

Found:
- `parserKeyForM1()` — 0 args, returns `{'8D2D6F67': ['FFFFFFFFFFFF']}` (dict: UID→keys)
- `parserUidForData(cache)` — 1 arg (cache string), returns UID string
- `parserHfTraceLen()` — 0 args, returns int trace length
- `parserKeysForT5577(parser_fn)` — 1 arg (parser function), returns list of hex strings

### 2.4 Real Device Framebuffer Captures

458 raw frames at 500ms intervals → 61 unique states in `docs/Real_Hardware_Intel/framebuffer_captures/sniff_20260403/`. Key states:
- state_006: INSTRUCTION page 1/4 with ▼▲ arrows
- state_014: Decoding screen with TraceLen + blue progress
- state_030: Result with data (TraceLen: 9945)
- state_059: Empty result (TraceLen: 0, Save dimmed)

### 2.5 Pixel-Level Measurement

Used PIL to measure exact positions from FB captures:

```python
from PIL import Image
img = Image.open('state_059.png')
px = img.load()
# Scan for dark pixels (text), blue pixels (Decoding), grey pixels (ProgressBar)
for y in range(40, 240):
    for x in range(0, 240):
        r, g, b = px[x, y][:3]
        if r < 80: dark_pixels.append((x, y))
```

---

## 3. Key Solutions

### 3.1 Parser Integration (No Middleware)

The `.so` parsers run under QEMU (ARM Cython binaries). Our Python `_finishHfResult` calls them directly — no reimplementation:

```python
# parserKeyForM1() — 0 args, reads executor cache internally
# Returns dict: {uid_hex: [key_hex, ...]}
key_data = sniff_mod.parserKeyForM1()
if key_data and isinstance(key_data, dict):
    for uid, keys in key_data.items():
        display_lines.append('UID: %s' % uid)
        for i, k in enumerate(keys):
            display_lines.append('  Key%d: %s' % (i + 1, k))
```

### 3.2 Empty Trace Detection

The original `.so` skips Decoding when `trace len = 0` appears in the sniff response. Detected via raw cache string match in `onData`:

```python
cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
if 'trace len' in cache:
    trace_len = sniff_mod.parserHfTraceLen()
    self._trace_len = int(trace_len) if trace_len else 0
    self._trace_len_known = True
```

Then in `_showResult`:
```python
if self._trace_len_known and self._trace_len == 0:
    self._finishHfResult()  # Skip Decoding, go straight to result
    return
```

### 3.3 Decoding Display — Lazy Init on Trace Data Lines

Decoding items created only when actual trace data lines arrive (lines containing `|` column separators), not on header lines. Zero data lines = no Decoding:

```python
def _on_decode_line(line):
    if '|' not in str(line):
        return  # Skip headers like "[=] downloading..."
    self._decode_count += 1
    if not _decode_created[0]:
        _decode_created[0] = True
        # Create ProgressBar and Decoding text
```

### 3.4 T5577 Auto-Finish

T5577 always auto-finishes because `lf t55xx sniff` blocks with `timeout=-1`:

```python
if data and self._selected_type_id == '125k':
    self._t5577_cache = str(data)
    self._stopSniff()
    self._showResult()
    return
```

Test framework supports this via `auto_finish` parameter:
```bash
run_sniff_scenario 4 5 "toast:Sniffing in progress" "M2:Save" "save" "" "auto_finish"
```

### 3.5 Trace File Save

The original `activity_main.so`'s `saveSniffData` writes the executor cache to `/mnt/upan/trace/{type}_{N}.txt`. Our Python reimplements this:

```python
trace_dir = '/mnt/upan/trace'
os.makedirs(trace_dir, exist_ok=True)
type_prefix = {'14a': '14a', '14b': '14b', 'iclass': 'iclass',
               'topaz': 'topaz', '125k': 't5577'}[self._selected_type_id]
existing = [f for f in os.listdir(trace_dir)
            if f.startswith(type_prefix + '_') and f.endswith('.txt')]
seq = len(existing) + 1
with open(os.path.join(trace_dir, '%s_%d.txt' % (type_prefix, seq)), 'w') as f:
    f.write(cache)
```

Test verification:
```bash
pre_save_count=$(ls "${trace_dir}/${trace_prefix}_"*.txt 2>/dev/null | wc -l)
send_key "M2"
# ... wait for toast ...
post_save_count=$(ls "${trace_dir}/${trace_prefix}_"*.txt 2>/dev/null | wc -l)
if [ "${post_save_count}" -le "${pre_save_count}" ]; then
    report_fail "Trace file not created"
fi
```

---

## 4. Multiple PM3 Command Paths

### 4.1 HF Sniff Commands (14A, 14B, iClass, Topaz)

| Type | Sniff Function | Sniff Command | Parse Command | Listener |
|------|---------------|---------------|---------------|----------|
| 14A | `sniff14AStart()` | `hf 14a sniff` (t=8000) | `hf list mf` (t=-1) | YES |
| 14B | `sniff14BStart()` | `hf 14b sniff` (t=8000) | `hf list 14b` (t=-1) | YES |
| iClass | `sniffIClassAStart()` | `hf iclass sniff` (t=8000) | `hf list iclass` (t=-1) | YES |
| Topaz | `sniffTopazStart()` | `hf topaz sniff` (t=8000) | `hf list topaz` (t=-1) | YES |

**IMPORTANT**: 14A parse is `hf list mf`, NOT `hf 14a list`. Confirmed by real device trace.

### 4.2 T5577 / LF Commands

`sniffT5577Start()` sends TWO commands:
1. `lf config a 0 t 20 s 10000` (timeout=5000) — configure LF sampling
2. `lf t55xx sniff` (timeout=-1) — start sniff, BLOCKS until PM3 completes

There is a SEPARATE function `sniff125KStart()` which sends `lf sniff` (generic LF). The original `activity_main.so` calls `sniffT5577Start()`, NOT `sniff125KStart()`. This was confirmed by:
- `activity_main_strings.txt` line 21264: `t5577_sniff_finished`
- Real device trace: `lf config` + `lf t55xx sniff`, not `lf sniff`

**NOTE FOR FUTURE**: If a generic LF sniff is needed, `sniff125KStart()` exists but uses different commands. Do not confuse the two.

---

## 5. Test Methodology

### 5.1 Content Validation at Every Critical Stage

NEVER rely on state counts alone. The `run_sniff_scenario` function validates at each phase:

```bash
# PHASE 1: Activity entered
wait_for_ui_trigger "title:Sniff TRF" 15

# PHASE 2: Instruction screen
wait_for_ui_trigger "M1:Start" 10
wait_for_ui_trigger "M1_active:true" 5
wait_for_ui_trigger "M2_active:false" 5

# PHASE 3: Sniffing
wait_for_ui_trigger "${sniff_trigger}" "${SNIFF_WAIT}"
wait_for_ui_trigger "M1_active:false" 5
wait_for_ui_trigger "M2_active:true" 5

# PHASE 4: Result
wait_for_ui_trigger "${result_trigger}" "${SNIFF_WAIT}"
wait_for_ui_trigger "content:TraceLen" 10
wait_for_ui_trigger "M1_active:true" 5
# M2_active verified based on save/no_save intent

# PHASE 5: Save (if applicable)
wait_for_ui_trigger "toast:Trace file" 15
# File creation verified in /mnt/upan/trace/
```

### 5.2 Negative Assertions for Empty Traces

Empty/failed trace scenarios verify the RESULT state has NO Decoding artifacts:

```python
for s in data['states']:
    if s.get('M2') != 'Save':
        continue  # Only check RESULT state, not TYPE_SELECT
    for item in s.get('content_text', []):
        if 'Decoding' in item.get('text', ''):
            sys.exit(1)  # FAIL
    for ci in s.get('canvas_items', []):
        if 'sniff_decode' in ' '.join(ci.get('tags', [])):
            sys.exit(1)  # FAIL
```

### 5.3 Active Polling, Not Blind Sleeps

`wait_for_ui_trigger` polls every 500ms with state dump capture — no blind sleeps for commands. State dumps are the reliable validation source, not screenshots.

### 5.4 Cross-Target Validation

Every change validated against `TEST_TARGET=original` to confirm behavioral parity:

```bash
# Compare result content between targets
for target in original current; do
    python3 -c "
    for s in data['states']:
        if s.get('M2') == 'Save':
            for c in s['content_text']:
                if 'TraceLen' in c['text'] or 'UID' in c['text']:
                    print(f'{target}: {c[\"text\"]} xy=({c[\"x\"]},{c[\"y\"]})')
    "
done
```

### 5.5 Remote QEMU Server Test Runs

All final validation on remote QEMU server (`qx@178.62.84.144`):
- Use `sshpass` for non-interactive auth
- Sync with `rsync --exclude='_results' --exclude='.git'`
- Clean stale scenarios before run: `rm -rf sniff_t5577_manual_finish sniff_14a_multi_key`
- Limit workers when server is shared: `3` workers, not `9`

---

## 6. JSON UI Requirements

### 6.1 Result Display Rules

1. **TraceLen always horizontally centered** — `anchor='center'` at `x=SCREEN_W//2`
2. **TraceLen-only (no UID/Keys): vertically + horizontally centered** — at `(SCREEN_W//2, CONTENT_Y0+CONTENT_H//2)`. This is an acknowledged deviation from the original (which renders at `(19, 60)` for all cases), chosen for better UX.
3. **Data result with UID/Keys**: TraceLen centered at `(120, 68)`, data items left-aligned at `(19, y)` with 40px spacing starting at `y=100`.

### 6.2 Decoding Display Positions

From QEMU canvas trace ground truth:
- `TraceLen: N` — centered at `(120, 68)`, fill=`NORMAL_TEXT_COLOR` (black)
- `Decoding...\nX/Y` — centered at `(120, 186)`, fill=`COLOR_ACCENT` (#1C6AEB blue)
- ProgressBar — `x=20, y=188, width=200, height=20`

### 6.3 Button Bar

- No button bar during Decoding: `dismissButton()`, not `setLeftButton('')`
- Page arrows for multi-page instructions: `res/img/down.png`, `up.png`, `down_up.png`
  - First page: `down.png`
  - Last page: `up.png`
  - Middle: `down_up.png`
  - Single page (T5577): no arrows

### 6.4 Color Constants

All colors from `_constants.py` — never hardcoded:
- `NORMAL_TEXT_COLOR` for result text
- `COLOR_ACCENT` (#1C6AEB) for Decoding text
- `BTN_TEXT_COLOR` for button labels
- `BTN_TEXT_COLOR_DISABLED` (#808080) for dimmed buttons

---

## 7. No Middleware — Rules & Exceptions

### 7.1 The Rule

The `.so` modules ARE the logic. Our Python is a thin UI shell. We:
- Call `.so` functions directly (they run under QEMU ARM emulation)
- Display whatever the parsers return
- Never reimplement parser logic in Python
- Never add `if/else` decision logic that should come from the `.so`

### 7.2 Middleware Instances Found & Removed

1. **`sniff.py` Python shim** — Created a Python module reimplementing all sniff.so parser functions with regex. IMMEDIATELY deleted when identified as middleware. The real `sniff.so` loads fine under QEMU.

2. **`125k_sniff_finished` string check** — `onData` checked for a non-existent PM3 response marker. Replaced with `self._selected_type_id == '125k'` type check (the `.so` handles T5577 auto-finish internally).

3. **`startBGTask` for parse** — Initially called the parse directly (not via `startBGTask`). The original `.so` uses `startBGTask` (confirmed via QEMU thread trace: Thread-9 for sniff, Thread-10 for parse). Reverted to match.

4. **Result text formatting** — Attempted to format UID/Key display in Python (`'UID: %s' % uid`). The `.so`'s `parserKeyForM1()` returns a dict; formatting is the activity's UI responsibility, not middleware.

### 7.3 Exception: Erase Flow

The Erase flow (`WipeTagActivity`) is the ONLY flow where middleware was justified. The original `erase.so` modules contain tag-specific PM3 command sequences that are tightly coupled to the real PM3 hardware. Under QEMU with mocked PM3, these sequences can't execute correctly.

The Erase middleware (`src/middleware/`) reimplements the PM3 command dispatch for erase operations while keeping the UI shell (activity) in pure Python. This is structured as a separate layer with clear boundaries:
- `src/middleware/` — RFID command logic (replaces `.so` command dispatch)
- `src/lib/` — UI shell (calls middleware instead of `.so` for Erase only)

This exception was justified because:
1. Erase commands are destructive — wrong commands brick tags
2. The `.so` erase logic is deeply intertwined with PM3 protocol state
3. The middleware was verified against real device traces via strace

### 7.4 The `saveSniffData` Case

`saveSniffData` was in `activity_main.so` (not `sniff.so`). Since we REPLACED `activity_main.so` with Python, implementing the save logic in Python is NOT middleware — it's implementing our own activity's method. The save writes `executor.CONTENT_OUT_IN__TXT_CACHE` to `/mnt/upan/trace/{type}_{N}.txt`.

---

## 8. QEMU Validation Methodology

### 8.1 The Process

1. **Run `TEST_TARGET=original`** — the real `.so` modules under QEMU with fixture data
2. **Run `TEST_TARGET=current`** — our Python UI with the same fixtures
3. **Compare `scenario_states.json`** — content_text, positions, colors, button states
4. **If different**: trace the original with QEMU canvas polling to find exact positions
5. **Fix**: adjust our Python to match the traced positions
6. **Verify**: re-run both targets, compare again

### 8.2 What QEMU Tracing Reveals That Screenshots Don't

- **Canvas item IDs**: track creation/deletion timing
- **Exact coordinates**: `xy=(120,68)` vs `xy=(19,60)` — not guessable from screenshots
- **Thread identity**: which thread creates which canvas items
- **Stale items**: items that persist on canvas but are visually hidden
- **Color values**: `fill=black` vs `fill=#1C6AEB` — exact hex codes

### 8.3 strace for Real Device Traces

Used on the real iCopy-X device to capture PM3 command sequences, file I/O, and timing:
- `trace_sniff_flow_20260403.txt` — complete 4-protocol sniff trace
- `trace_sniff_enhanced_20260404.txt` — enhanced trace with listener callback logging
- `trace_sniff_t5577_enhanced_20260404.txt` — T5577 with listener=None confirmation

---

## 9. Summary

### 9.1 Problems & Solutions

| Problem | Root Cause | Solution | Validation |
|---------|-----------|----------|------------|
| No UID/Key in results | `parserTraceLen` doesn't exist; `parserKeyForM1` never called | Use `parserHfTraceLen`, call `parserKeyForM1()` (0 args) | Cross-target content comparison |
| Empty trace shows Decoding | Decoding created unconditionally | Check `_trace_len_known` from sniff response; lazy-init on trace data lines | QEMU canvas trace: empty creates NO Decoding items |
| Decoding not captured in tests | `startBGTask` creates+destroys atomically | Use `startBGTask` (matching original); lazy-init Decoding on first trace data line | Passes on original, reliable on current for large fixtures |
| Save doesn't create file | Called `sniff.saveSniffData()` which doesn't exist | Implement file write in Python `_saveSniffData` (we own this method) | File count verification gate |
| T5577 manual finish fails | Not a real device flow | Removed scenario; added `auto_finish` parameter | QEMU trace: `timeout=-1` always blocks |
| Stale Decoding bleeds through | Original doesn't delete items; our canvas is transparent | Clean up Decoding items in `_finishHfResult` | Visual comparison of result + post-PWR screens |
| Wrong Decoding positions | Guessed from screenshots | QEMU canvas trace: exact `(x, y)` coordinates | Pixel measurement comparison |

### 9.2 What Would Have Made This Faster

1. **QEMU canvas tracing from the start**. Every pixel position dispute was resolved in seconds once canvas polling was added. Hours were spent guessing from screenshots before this technique was discovered.

2. **A ground-truth function signature table for ALL `.so` parser functions**. The MODULE_AUDIT had errors (`parserTraceLen` listed as existing; `parserUidForData` listed as 0 args but takes 1). A QEMU probe script that calls every function with 0, 1, 2 args and records results would save significant time.

3. **Understanding that `sniff.so` loads under QEMU from the start**. Time was wasted creating a Python `sniff.py` shim — the real `.so` loads fine because everything runs under `qemu-arm-static`.

4. **The key dispatch mechanism difference**: original uses serial buffer → hmi_driver thread (50ms poll); current uses `_tk_root.after(0, ...)` (main thread). This affects threading behavior of everything downstream.

5. **The `data save` command flow**: knowing upfront that `saveSniffData` is in `activity_main.so` (not `sniff.so`) and writes to `/mnt/upan/trace/` would have avoided the dead-end of calling `sniff.saveSniffData()`.

6. **A clear statement: "the original .so never deletes canvas items"**. This single fact explains why Decoding text persists in original state dumps, why the `"decoding"` gate works on original, and why our cleanup causes visual parity.

---

## 10. Final Test Results

**28 scenarios, 28 PASS on remote QEMU server (qx@178.62.84.144)**

| Category | Scenarios | Status |
|----------|-----------|--------|
| 14A data traces | 5 (trace_result, real_key_found, real_double_uid, real_mfsniff, trace_no_keys) | PASS |
| 14A empty/abort | 3 (empty_trace, pwr_abort, pwr_from_result) | PASS |
| 14B | 3 (trace_result, real_reqb, empty_trace) | PASS |
| iClass | 5 (trace_result, real_csn, trace_with_csn, empty_trace, sniff_failure) | PASS |
| Topaz | 3 (trace_result, trace_ndef, empty_trace) | PASS |
| T5577 | 7 (auto_finish, password_found, no_password, real_password, real_block_data, empty, pwr_abort) | PASS |
| Navigation | 2 (list_navigation, pwr_back) | PASS |

Save file verification: confirmed on all `save` scenarios — files created in `/mnt/upan/trace/` with correct naming and content.
