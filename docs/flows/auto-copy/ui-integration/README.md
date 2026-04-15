# Auto-Copy Flow -- UI Integration Post-Mortem

## 1. Initial State

### What existed
`AutoCopyActivity` in `src/lib/activity_main.py` (~450 lines) with 18 states, 52 test scenarios reporting 51/51 PASS. The activity combined Scan -> Read -> Write -> Verify into a single automated pipeline.

### What was broken

**Scan API (blocking ALL tests):**
The scan call was `scan.scan_all_asynchronous(self)` -- a module-level function that doesn't exist. The correct API is `scan.Scanner()` instance with `call_progress`, `call_resulted`, `call_exception` callback attributes, then `scanner.scan_all_asynchronous()`. Every test was stuck at "Scanning..." with the error `module 'scan' has no attribute 'scan_all_asynchronous'`.

**Read API (wrong pattern):**
Used `Reader.find_reader(scan_result)` with synchronous `reader.start()` on a background thread. The correct API (from ReadListActivity) is `Reader()` no-args constructor, then `reader.call_reading = self.onReading`, `reader.call_exception = self._onReadException`, then `reader.start(tag_type, bundle)` with 2 positional args. Completion arrives through `onReading` as a dict with `'success'` key.

**Flow architecture (not matching real firmware):**
AutoCopyActivity handled write/verify internally with `_startWrite()` calling `write.write()` directly. The real firmware (confirmed by 3 traces) pushes `WarningWriteActivity` then `WriteActivity` as separate activities on the stack:
```
trace_autocopy_mf1k_standard.txt line 111-119:
  START(WarningWriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_9C750884_1.bin')
  FINISH(WarningWriteActivity)
  START(WriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_9C750884_1.bin')
```

**Middleware in read failure handling:**
`_showReadNoKeyHF()`, `_showReadNoKeyLF()`, `_showReadMissingKeys()`, `_showReadTimeout()` all rendered read-failure UI as toasts in Python. The real firmware pushes Warning activities (WarningM1Activity for HF key failures, WarningT5XActivity for LF key failures) that handle their own UI. Confirmed by `trace_fail_read_flow_20260401.txt` line 98: `START(WarningT5XActivity, -7)` and by all 6 read flow darkside/nested/hardnested tests using `M1:Sniff` trigger.

**Scan result handling:**
`onScanFinish` only handled dict results. scan.so returns three formats: string codes (`'CODE_TAG_MULT'`), integers (`-2`), and dicts. Also, multi-tag detection relied on `result.get('hasMulti')` which scan.so's Scanner never sets. The real binary calls `scan.isTagMulti(result)` and `scan.isTagFound(result)` -- module-level predicate functions (confirmed by activity_main.so string table lines 21937-21938).

**No ConsolePrinter during read:**
RIGHT key during READING state was blocked by `if not self._btn_enabled: return`. ReadListActivity handles RIGHT during reading to show an inline ConsoleView.

**MF4K race condition:**
The `_wait_for_completion` poll thread could detect `is_reading()==False` before `onReading`'s completion dict arrived, calling `_promptSwapCard()` with `_read_bundle=None`. WriteActivity then received None instead of the dump file path. MF1K (16 sectors) was fast enough that `onReading` always won the race; MF4K (40 sectors) lost it consistently.

**WarningWriteActivity button labels:**
Showed "Cancel"/"Write" in AutoCopy context. Real device shows "Watch"/"Write" (confirmed by `data_ready.png` screenshot and `docs/UI_Mapping/02_auto_copy/README.md`).

---

## 2. Resources and Techniques

### Critical traces
| Trace | What it provided |
|-------|-----------------|
| `trace_autocopy_mf1k_standard.txt` | Complete MFC 1K auto-copy: scan -> fchk -> rdsc -> WarningWriteActivity -> WriteActivity -> wrbl. Confirmed activity stack architecture. |
| `autocopy_mf4k_mf1k7b_t55_trace_20260329.txt` | 3 tag types (MF4K + MF1K-7B + T55XX) all pushing WarningWriteActivity -> WriteActivity. Confirmed architecture is universal. |
| `trace_autocopy_multitag_wrongtype_20260402.txt` | **Captured during this integration.** Multi-tag collision returns `found=True, type=-1, return=-3` with NO `hasMulti` key. ISO14443-B returns `found=True, type=22`. Proved `scan.isTagMulti()` predicate is needed. |
| `trace_fail_read_flow_20260401.txt` | T55xx key failure: `START(WarningT5XActivity, -7)`. Proved read.so pushes Warning activities for key failures. |

### Decompiled binary analysis
- `activity_main_strings.txt` lines 21937-21938: `isTagMulti`, `isTagFound` -- the ONLY scan predicates referenced by the binary. No `isTagTypeWrong`, `isTimeout`, `isTagLost`.
- `scan_ghidra_raw.txt` line 11874: `isTagTypeWrong` exists in scan.so but is NOT called by AutoCopyActivity.
- `container_strings.txt` line 954: `ISO15693 ST SA` -- English name for type 46 (runtime returns Chinese "特斯联" due to locale bug in container.so).

### Read flow as reference implementation
ReadListActivity in `activity_read.py` was the ground truth for:
- Scanner API pattern (lines 308-344)
- Reader API pattern with 4 completion mechanisms
- Console inline view (_showConsole/_hideConsole)
- WarningM1Activity push for key failures (_launchWarningKeys)
- WarningWriteActivity push for write transition (_launchWrite)

### Live device tracing
Deployed tracer via `sitecustomize.py` (docs/HOW_TO_RUN_LIVE_TRACES.md) to capture multi-tag and wrong-type scan results. The tracer patches module-level functions only (safe). Class method patches crash the Cython .so.

---

## 3. Solutions Implemented

### 3.1 Scanner API fix
```python
# BEFORE (broken):
_scan_mod.scan_all_asynchronous(self)

# AFTER (correct, same pattern as ScanActivity):
self._scanner = _scan_mod.Scanner()
self._scanner.call_progress = self.onScanning
self._scanner.call_resulted = self.onScanFinish
self._scanner.call_exception = self.onScanFinish
self._scanner.scan_all_asynchronous()
```

### 3.2 Scan result predicates
```python
# Use scan.so's own predicate functions, not dict keys.
# Ground truth: activity_main.so string table lines 21937-21938.
try:
    import scan as _scan_mod
    is_multi = _scan_mod.isTagMulti(result)
    is_found = _scan_mod.isTagFound(result)
except Exception:
    is_multi = result.get('hasMulti', False)
    is_found = result.get('found', False)

if is_multi:
    # show multi-tag toast
elif is_found:
    # proceed to read
else:
    # show no-tag-found toast
```
Note: `isTagMulti()` and `isTagFound()` take the result dict as argument (discovered via error: "takes exactly one argument (0 given)").

### 3.3 Reader API fix
```python
# Same pattern as ReadListActivity (activity_read.py:308-344)
import read as _read_mod
self._reader = _read_mod.Reader()
self._reader.call_reading = self.onReading
self._reader.call_exception = self._onReadException
self._reader.start(tag_type, {'infos': scan_cache, 'force': force})
```

### 3.4 Activity stack architecture
```python
# AutoCopyActivity pushes WarningWriteActivity, not internal _startWrite()
def _launchWrite(self):
    actstack.start_activity(WarningWriteActivity, self._read_bundle)

def onActivity(self, result):
    action = result.get('action')
    if action == 'write':
        actstack.start_activity(WriteActivity, result.get('read_bundle'))
    elif action == 'force':
        self._startRead(force=True)
    elif action == 'sniff':
        actstack.start_activity(SniffActivity)
```

### 3.5 WarningWriteActivity context-aware buttons
```python
# "Watch" in AutoCopy context, "Cancel" in manual Write flow
from_autocopy = any(isinstance(a, AutoCopyActivity) for a in actstack.get_stack())
if from_autocopy:
    self.setLeftButton(resources.get_str('write_wearable'))  # "Watch"
else:
    self.setLeftButton(resources.get_str('cancel'))
```

### 3.6 ConsoleMixin (shared, no duplication)
Extracted from ReadListActivity into `ConsoleMixin` class in `activity_read.py`. Both `ReadActivity` and `AutoCopyActivity` inherit from it:
```python
class ConsoleMixin:
    def _showConsole(self): ...   # ConsoleView on canvas, polls executor cache
    def _hideConsole(self): ...   # Hide overlay
    def _handleConsoleKey(self, key): ...  # UP/DOWN=zoom, RIGHT/LEFT=scroll, PWR=exit

class ReadActivity(ConsoleMixin, BaseActivity): ...
class AutoCopyActivity(ConsoleMixin, BaseActivity): ...
```
RIGHT key during READING state shows console (before the `_btn_enabled` gate).

### 3.7 MF4K race condition fix
```python
# Poll thread waits for onReading to handle completion before falling back
def _wait_for_completion():
    while self._reader is not None and self._state == self.STATE_READING:
        if not self._reader.is_reading():
            # Wait for onReading completion to fire first
            for _ in range(20):  # 10 seconds
                time.sleep(0.5)
                if self._state != self.STATE_READING:
                    return  # onReading handled it
            # onReading never fired -- fallback
            ...
```

### 3.8 Key failure handling (no middleware)
```python
# BEFORE (middleware -- Python rendering read-failure UI):
self._showReadNoKeyHF()  # toast with "No valid key"

# AFTER (push WarningM1Activity -- .so handles its own UI):
actstack.start_activity(WarningM1Activity, {'infos': infos})
```
WarningM1Activity renders `title='Missing keys'`, `M1='Sniff'`, `content='Option 1) Go to reader to sniff keys...'`. All 6 read flow tests confirm this with `M1:Sniff` trigger.

---

## 4. DRM

The DRM mechanism (`hfmfwrite.tagChk1()`) was already solved in the Write flow integration. The cpuinfo serial `02c000814dfb3aeb` is set in `launcher_current.py`. Auto-Copy reuses the same `write.so` pipeline through WriteActivity, so no additional DRM work was needed.

Key lesson carried forward: **ALWAYS check `[OK] tagtypes DRM passed natively: 40 readable types` in the launcher log before debugging write failures.**

---

## 5. Test Results

### Auto-Copy suite: 52/52 PASS
```
TOTAL: 52  PASS: 52  FAIL: 0
Duration: 1177s (9 workers)
```

| Category | Scenarios | States range |
|----------|-----------|-------------|
| LF happy (with verify) | 20 | 14-15 states |
| LF failure (write/verify fail) | 3 | 10-15 states |
| HF MFC happy | 6 | 8-65 states |
| HF MFC failure | 6 | 3-5 states |
| HF other (iCLASS, ISO15693, UL, NTAG) | 8 | 8-10 states |
| Scan failure (no_tag, multi_tag) | 2 | 3 states |
| Console tests | 3 | 1-11 states |
| MF4K happy | 1 | 65 states |

### Regression suites: 0 regressions
| Suite | Result |
|-------|--------|
| Scan | 45/45 PASS |
| Read | 99/99 PASS |
| Write | 61/61 PASS |
| Volume | 7/7 PASS |
| Backlight | 7/7 PASS |
| **Total** | **271/271 PASS** |

---

## 6. JSON UI Requirements

The AutoCopy JSON state machine (`src/screens/autocopy.json`) defines 17 states with:
- Screen layout: title, content type (progress/empty), toast, buttons
- Key bindings per state
- Transition predicates

Key states and their UI:
- `scanning`: progress bar "Scanning...", no buttons, only PWR works
- `scan_not_found`: toast "No tag found", Rescan/Rescan
- `scan_multi`: toast "Multiple tags detected!", Rescan/Rescan
- `reading`: progress bar "Reading...", no buttons
- `place_card`: toast "Data ready for copy!...", Reread/Write (then pushes WarningWriteActivity)
- `writing`/`verifying`: handled by WriteActivity (separate activity)
- `write_success`/`verify_success`: handled by WriteActivity

---

## 7. No-Middleware Rules

### Rule
Our Python is a thin UI shell. scan.so, read.so, write.so, template.so, container.so handle ALL RFID logic. If you're writing tag-specific logic in Python -- STOP.

### Middleware found and removed

**1. Multi-tag detection via executor cache (reverted)**
```python
# WRONG: Python reading PM3 response text behind scan.so's back
cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '')
if 'Multiple tags' in cache:
    has_multi = True
```
**Fix:** Call `scan.isTagMulti(result)` -- scan.so's own exported predicate.

**2. Writable type validation via tagtypes.getReadable() (reverted)**
```python
# WRONG: Python cross-checking scan.so's type against tagtypes list
readable = set(tagtypes.getReadable())
if tag_type not in readable:
    is_type_ok = False
```
**Fix:** Removed entirely. Real device proceeds to read for all found types. Non-writable types simply don't reach the write stage.

**3. Read failure toast rendering (removed)**
```python
# WRONG: Python rendering read-failure UI
def _showReadNoKeyHF(self):
    self._toast.show(resources.get_str('no_valid_key'), ...)
def _showReadNoKeyLF(self): ...
def _showReadMissingKeys(self): ...
def _showReadTimeout(self): ...
```
**Fix:** Push `WarningM1Activity` for ret_code -3/-4. The Warning activity handles its own UI. Confirmed by 6 read flow tests all using `M1:Sniff` trigger.

**4. Wrong-type scan detection (removed scenario)**
The `autocopy_scan_wrong_type` test assumed a "Wrong type found!" toast. Live trace confirmed: the real device has NO wrong-type error in AutoCopy. Tags are either found (proceed to read) or not found. The scenario was removed.

---

## 8. PM3 Source Reference

PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

Used for understanding PM3 response formats when traces were truncated:
- `cmdhf14a.c` -- `hf 14a info` collision detection output format
- `cmdhfmf.c` -- `hf mf fchk`, `hf mf wrbl` response patterns
- `cmdlf.c` -- `lf t55xx detect`, `lf sea` response patterns

---

## 9. Summary

### High-level problems and solutions

| Problem | Root cause | Solution | Time |
|---------|-----------|----------|------|
| All tests stuck at "Scanning..." | Wrong scan.so API call | Use Scanner() with callbacks | 30 min |
| Write never starts | Internal _startWrite() instead of pushing activities | Push WarningWriteActivity -> WriteActivity (from traces) | 2 hrs |
| Multi-tag not detected | scan.so doesn't set hasMulti in result dict | Call scan.isTagMulti(result) predicate (from binary strings) | 3 hrs (incl. live trace) |
| "No valid key" wrong UI | Python toast middleware | Push WarningM1Activity (from read flow tests) | 2 hrs |
| MF4K write silently fails | Race: poll thread beats onReading, _read_bundle=None | Poll waits for onReading completion before fallback | 1 hr |
| Console not showing during read | RIGHT key blocked by _btn_enabled gate | Handle RIGHT before gate, share via ConsoleMixin | 30 min |
| Duplicate console code | Copy-paste from ReadListActivity | Extract ConsoleMixin, both activities inherit | 20 min |

### What would have made this faster

1. **The scan.so Scanner API documented explicitly.** The broken `scan.scan_all_asynchronous(self)` call was the first blocker. Having `Scanner()` + `call_resulted` + `call_exception` + `scan_all_asynchronous()` documented would have saved the first 30 minutes.

2. **A trace showing scan FAILURE in AutoCopy.** All existing traces showed successful scans. The multi-tag and wrong-type behaviors required a live device trace session. A pre-captured trace of multi-tag collision + non-writable tag would have saved 3+ hours of middleware-then-revert.

3. **Explicit statement: "AutoCopy pushes WarningWriteActivity and WriteActivity, not internal write."** This architectural fact was discoverable from traces but wasn't stated in the handover docs. The handover described AutoCopy as a "single activity" handling scan+read+write+verify internally -- the opposite of reality.

4. **The `onActivity()` method name (not `onActivityResult`).** The actstack calls `prev_act.onActivity(result)` when a child finishes. Using the wrong name (`onActivityResult`) silently failed. A doc note on the actstack callback convention would have saved 30 minutes.

5. **The `scan.isTagMulti(result)` function signature.** It takes the result dict as argument. The zero-argument call fails silently via the except handler. Knowing the signature upfront would have saved a debug cycle.

6. **The `_wait_for_completion` race condition pattern.** ReadListActivity has the same poll thread but its fallback calls `_showReadSuccess()` which doesn't need `_read_bundle`. AutoCopy's fallback calls `_promptSwapCard()` which does. Documenting this coupling would have prevented the MF4K bug.
