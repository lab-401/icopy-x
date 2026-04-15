# Erase Flow -- UI Integration Post-Mortem

Branch: `feat/ui-integrating`
Date: 2026-04-03 to 2026-04-04
Status: **10/10 PASS, 5/5 gates per scenario, 210/210 full regression PASS**

---

## 1. Initial State

### What existed

`WipeTagActivity` existed in `src/lib/activity_main.py` with 5 states (TYPE_SELECT, ERASING, SUCCESS, FAILED, NO_KEYS) and 10 test scenarios with fixtures. The activity had a 2-item list, a "Processing..." toast during erase, and result toasts. All 10 tests reported PASS based on state count alone.

### What was broken -- Functionality

**Finding 1: Wrong .so module calls crashed the erase flow.**
The activity called `hfmfkeys.hasAllKeys()` (wrong arity -- `.so` requires 1 argument), `write.write({'action': 'erase'})` (wrong signature -- write.so takes 3 positional args), and `lft55xx.wipe(self)` (wrong argument). None of these were the correct API.
```
TypeError: hasAllKeys() takes exactly one argument (0 given)
```
**Root cause**: The erase logic lives in `activity_main.so` (WipeTagActivity class methods), NOT in separate middleware `.so` modules. The original code incorrectly delegated to write.so and lft55xx.so. Ground truth: `docs/UI_Mapping/13_erase_tag/README.md` lines 24-37 list 40+ WipeTagActivity symbols in the binary string table -- `wipe_m1`, `wipe_magic_m1`, `wipe_std_m1`, `wipe_t5577`, `call_on_write_magic_m1`, etc.

**Finding 2: No tag detection / scanning phase.**
The activity went directly from TYPE_SELECT to "Processing..." with no scanning phase. The real device shows a "Scanning..." progress bar during `hf 14a info` tag detection (screenshot `erase_tag_menu_2.png`).

**Finding 3: Result screens had no buttons and wrong key behavior.**
After erase completed, M1/M2 buttons remained hidden (empty strings from `_startErase`). All keys called `finish()` (exit activity). Ground truth (state table `docs/flows/erase/README.md` lines 130-137 and screenshots `erase_tag_menu_6.png`, `erase_tag_unknown_error.png`): M1="Erase", M2="Erase" visible; M1/M2/OK re-trigger erase; PWR exits.

**Finding 4: Toast auto-cancel timer leak.**
When `_startErase()` showed "Processing..." toast (default 2000ms auto-cancel timer), then the background thread showed the result toast via `toast.show()`, the result toast was killed 2 seconds later by the leaked timer from the Processing toast. Root cause: `Toast._clear()` deleted canvas items but did NOT cancel the pending `after()` timer. Only `Toast.cancel()` did. Fix: added timer cancellation to `Toast._clear()` in `widget.py`.

**Finding 5: No progress display during erasing.**
The real device shows "ChkDIC" during key check (`erase_tag_menu_3.png`) and "Erasing 0%" during block writes (`erase_tag_menu_4.png`). The implementation showed only a static "Processing..." toast.

### What was broken -- UI

**Finding 6: List items missing number prefix.**
Real device (screenshot `erase_tag_menu_1.png`): "1. Erase MF1/L1/L2/L3", "2. Erase T5577". Implementation: "Erase MF1/L1/L2/L3", "Erase T5577" (no numbering). Spec: `docs/UI_Mapping/13_erase_tag/README.md` line 50-55 confirms numbered display format.

**Finding 7: Button bar visible in TYPE_SELECT but not in spec screenshots.**
The TYPE_SELECT screenshot (`erase_tag_menu_1.png`) shows no dark button bar at bottom, but the spec says M1="Back", M2="Erase". This is likely a screenshot timing issue -- buttons are set in `onCreate()` but may not render before the capture. Implementation keeps buttons as specified.

---

## 2. Ground Truth Resources

| Resource | What it provided |
|----------|-----------------|
| `docs/UI_Mapping/13_erase_tag/README.md` | Exhaustive UI spec: 5 states, key bindings, PM3 commands, 40+ binary symbols |
| `docs/flows/erase/README.md` | State table (lines 130-137): M1/M2 on result = re-erase, PWR = exit |
| `docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt` | Complete PM3 command trace: cwipe timeout=28888, fchk timeout=600000, wrbl timeout=5888 |
| `docs/Real_Hardware_Intel/trace_erase_gen1a_and_standard.txt` | Gen1a vs standard comparison: `wupC1 error` = not Gen1a, `isOk:01` = Gen1a |
| `docs/Real_Hardware_Intel/Screenshots/erase_tag_*.png` | 8 screenshots: TYPE_SELECT, Scanning, ChkDIC, Erasing 0%, result, error |
| `docs/v1090_strings/activity_main_strings.txt` | Binary symbol table: WipeTagActivity methods (lines 20574-23169) |
| `decompiled/hfmfkeys_v1090_ghidra_raw.txt` | `hasAllKeys` signature: 1 required arg (line 28517) |
| `https://github.com/iCopy-X-Community/icopyx-community-pm3` | PM3 source code for this exact hardware version -- use when trace results are truncated |

### Vital techniques

1. **Read the error first.** The `TypeError: hasAllKeys() takes exactly one argument` immediately identified the API mismatch. The fix was not to call hasAllKeys at all -- the erase logic belongs in our Python code, not delegated to .so modules.

2. **State dump JSON inspection.** Checking `scenario_states.json` after each run revealed toast timing issues (toast appeared in state 4, disappeared in state 5 -- leaked timer).

3. **Real device screenshot comparison.** Every UI state was verified against the 8 real device screenshots. The "ChkDIC" and "Erasing 0%" phases were only discovered from screenshots -- not from code analysis.

4. **Per-gate test validation.** The sniff suite's multi-gate approach (check button labels, active state, toast text at EACH phase) was adopted for erase tests. This caught the missing result buttons immediately.

---

## 3. Solutions Implemented

### 3.1 Middleware architecture (`src/middleware/erase.py`)

The erase flow was our **first middleware module**. This was justified because:
- There is no `erase.so` in the original firmware -- the erase logic is embedded in `activity_main.so`
- Since we reimplement `activity_main.so` in Python, the erase PM3 command sequences belong in our code
- The .so modules (`write.so`, `hfmfkeys.so`, `lft55xx.so`) had wrong APIs for erase operations
- This is NOT middleware wrapping .so modules -- it IS the reimplementation of the binary logic

**Structure:** `src/middleware/` directory with sys.path priority above rootfs .so modules:
```python
# src/middleware/erase.py -- three-phase API
def detect_mf1_tag():
    """Phase 1: hf 14a info + hf mf cgetblk 0.
    Returns {'info_cache': str, 'is_gen1a': bool} or 'no_tag'."""

def erase_mf1_detected(info_cache, is_gen1a, on_progress=None):
    """Phase 2: cwipe (Gen1a) or fchk+wrbl (standard).
    on_progress('chkdic'|'erasing', current, total) for UI updates."""

def erase_t5577():
    """Fallback chain: wipe → detect → wipe+password → detect → chk."""
```

The split into `detect_mf1_tag()` and `erase_mf1_detected()` enables the activity to show the SCANNING state (with ProgressBar) during detection, then transition to ERASING during the actual erase.

### 3.2 ProgressBar integration

```python
# In WipeTagActivity._startErase():
if sel == self.ERASE_MF1:
    self._state = self.STATE_SCANNING
    self._progress.setMessage(resources.get_str('scanning'))  # "Scanning..."
    self._progress.show()

# In _do_mf1_erase() background thread:
def _on_progress(phase, current, total):
    if phase == 'chkdic':
        self._progress.setMessage('ChkDIC')
    elif phase == 'erasing':
        pct = (current * 100) // total if total else 0
        self._progress.setMessage('%s %d%%' % (resources.get_str('wipe_block'), pct))
        self._progress.setProgress(pct)
```

### 3.3 Result screen buttons and re-erase

```python
# In _onEraseResult() -- after showing toast:
self.setLeftButton(resources.get_str('wipe'))   # "Erase"
self.setRightButton(resources.get_str('wipe'))  # "Erase"

# In onKeyEvent() -- result states:
elif self._state in (self.STATE_SUCCESS, self.STATE_FAILED, self.STATE_NO_KEYS):
    if key in (KEY_M1, KEY_M2, KEY_OK):
        self._startErase()  # re-erase with saved _selected_type
    elif key == KEY_PWR:
        self.finish()
```

### 3.4 Button state management (`src/lib/actbase.py`)

During this integration, we built the button active/visible state system:

```python
# Three-state model per button: hidden, shown+active, shown+inactive
def setLeftButton(self, text, color=None, active=True):
    self._m1_active = active
    self._m1_visible = bool(text)
    ...

def callKeyEvent(self, key):
    """M1/M2 suppressed when button is hidden or inactive."""
    if key == KEY_M1 and (not self._m1_visible or not self._m1_active):
        return
    if key == KEY_M2 and (not self._m2_visible or not self._m2_active):
        return
    self.onKeyEvent(key)

def dismissButton(self, left=False, right=False, keep_bindings=False):
    """keep_bindings=True: visually hidden but keys still dispatch
    (e.g. ConsolePrinterActivity zoom)."""
```

State dump exports `M1_active`, `M2_active`, `M1_visible`, `M2_visible` for test assertions. For `--target=original`, button active state is derived from canvas fill color (dimmed = `#808080`); visibility from whether text items exist.

### 3.5 Toast timer leak fix (`src/lib/widget.py`)

```python
# Before (bug): _clear() didn't cancel timers
def _clear(self):
    self._canvas.delete(self._tag_mask)
    self._canvas.delete(self._tag_text)

# After (fix): _clear() cancels any pending auto-dismiss timer
def _clear(self):
    if self._timer_id is not None:
        self._canvas.after_cancel(self._timer_id)
        self._timer_id = None
    self._canvas.delete(self._tag_mask)
    self._canvas.delete(self._tag_text)
```

---

## 4. DRM

No DRM issues encountered in the erase flow. The DRM check passes at launcher startup:
```
[OK] tagtypes DRM passed natively: 40 readable types
```
Correct serial `02c000814dfb3aeb` is set in `launcher_current.py` cpuinfo mock. The erase flow does not use `tagtypes.so` -- it calls `executor.startPM3Task()` directly for PM3 commands. If DRM were to fail, the erase middleware would still work because it doesn't go through scan.so/write.so.

**The Rule**: Before debugging ANY silent .so failure, ALWAYS check `tagtypes DRM passed natively` in the launcher log. See `docs/DRM-KB.md`, `docs/DRM-Issue.md`.

---

## 5. Multiple Paths Found

The T5577 erase uses `lf t55xx wipe` and `lf t55xx detect` commands. Note that there are MULTIPLE T5577/LF command paths in the PM3 firmware:

- `lf t55xx wipe` — block-level wipe (used by erase)
- `lf t55xx wipe p <password>` — wipe with password (DRM password 20206666)
- `lf t55xx detect` — post-wipe verification
- `lf t55xx chk` — password brute force
- `lf sniff` — LF sniff (used by sniff flow, different code path)

The fixture pattern matching in the PM3 mock (`launcher_current.py`) matches by substring: `'lf t55xx wipe'` matches BOTH `lf t55xx wipe` and `lf t55xx wipe p 20206666`. This works for erase but could cause fixture collisions if a test needs different responses for password vs no-password wipe. If this becomes a problem, use longer patterns or list-based multi-call responses.

---

## 6. Test Validation: Per-Gate Assertions

### The problem with state-count validation

The original erase tests validated only:
1. Whether a final toast appeared (e.g., `toast:Erase successful`)
2. Whether `DEDUP_COUNT >= min_unique` (typically 3)

This passed tests that had **wrong button labels, missing button states, wrong key behavior, and missing UI phases**. A test could PASS with 3 unique frames even if the buttons never showed, the progress bar never rendered, or the re-erase behavior was completely broken.

### The solution: 5-gate validation (modelled on sniff suite)

```bash
# Gate 1: Activity reached
wait_for_ui_trigger "title:Erase Tag" 15 "${raw_dir}" frame_idx

# Gate 2: TYPE_SELECT buttons correct
wait_for_ui_trigger "M2:Erase" 5 "${raw_dir}" frame_idx

# Gate 3: Transition past TYPE_SELECT (buttons hidden OR result already visible)
if ! wait_for_ui_trigger "M1_active:false" 5 "${raw_dir}" frame_idx; then
    # Fast path: check if result toast already appeared
    wait_for_ui_trigger "${final_trigger}" 3 "${raw_dir}" frame_idx
fi

# Gate 4: Result toast
wait_for_ui_trigger "${final_trigger}" "${ERASE_TRIGGER_WAIT}" "${raw_dir}" frame_idx

# Gate 5: Result buttons restored
wait_for_ui_trigger "M1:Erase" 5 "${raw_dir}" frame_idx
wait_for_ui_trigger "M2:Erase" 5 "${raw_dir}" frame_idx
```

Gate 3 handles fast operations (no_tag, T5577) where the buttons-hidden state is too brief to catch: if the result toast already appeared, that proves the transition happened.

### The rule

**NEVER rely on state count as the primary validation.** State count is a final sanity check only. ALWAYS validate content, toast, and button values at EACH critical stage with specific `wait_for_ui_trigger` gates. Failure messages must be diagnostic:
```
"M2 not 'Erase' on result screen (4 states)"   # tells you WHAT failed
```
Not:
```
"4 unique states (expected >= 3)"               # tells you nothing
```

---

## 7. Test Execution

### Running tests on the QEMU server

```bash
# Sync to remote
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' \
  --exclude='__pycache__' --exclude='*.pyc' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/

# Start background run
sshpass -p proxmark ssh qx@178.62.84.144 'cd ~/icopy-x-reimpl && \
  rm -rf tests/flows/_results/current/ && \
  nohup bash -c "for suite in scan simulate erase read write auto-copy; do \
    TEST_TARGET=current bash tests/flows/$suite/test_*_parallel.sh 9 2>&1 | \
    grep -E \"SUMMARY|Total:|PASS:|FAIL:|COMPLETE\"; done" \
  > /tmp/regression.log 2>&1 & echo "PID=$!"'

# Poll every 60s (DO NOT blind sleep)
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cat /tmp/regression.log && ps -p $PID -o pid= && echo "RUNNING" || echo "DONE"'
```

**Do NOT use blind sleeps.** Poll `ps -p $PID` every 60 seconds. Catch failures in seconds, not minutes.

### PM3_DELAY

Erase tests use `PM3_DELAY=0.5` (set unconditionally in `erase_common.sh`). The original `PM3_DELAY="${PM3_DELAY:-0.5}"` was overridden by `common.sh`'s `PM3_DELAY="${PM3_DELAY:-3.0}"` default. At 3.0s per command, the 4K erase (256 wrbl calls = 768s) exceeded the 400s trigger wait. Fix: unconditional `PM3_DELAY=0.5`.

### Final test results

| Suite | Result |
|-------|--------|
| Scan | 45/45 PASS |
| Simulate | 28/28 PASS |
| **Erase** | **10/10 PASS (5/5 gates each)** |
| Read | 14/14 PASS |
| Write | 61/61 PASS |
| Auto-Copy | 52/52 PASS |
| **Total** | **210/210 PASS** |

---

## 8. JSON UI Requirements

`src/screens/erase_tag.json` defines 6 states:

| State | Content | Buttons | Keys |
|-------|---------|---------|------|
| `type_select` | 2-item list | Back / Erase | M1=finish, M2/OK=startErase, UP/DOWN=scroll |
| `scanning` | progress "Scanning..." | hidden | PWR=finish |
| `erasing` | progress "Processing..." | hidden | PWR=finish |
| `success` | toast "Erase successful" | Erase / Erase | M1/M2/OK=startErase, PWR=finish |
| `failed` | toast "Erase failed" | Erase / Erase | M1/M2/OK=startErase, PWR=finish |
| `no_keys` | toast "No valid keys..." | Erase / Erase | M1/M2/OK=startErase, PWR=finish |

Result states use `"buttons": {"left": "Erase", "right": "Erase"}` with key bindings for re-erase (not finish).

---

## 9. No-Middleware Rules

### The rule

Our Python is a thin UI shell. The .so modules handle ALL RFID logic. Activities call .so module functions; they do NOT reimplement RFID protocols, parse PM3 responses, or make tag-specific decisions in Python.

### Middleware violations found in other flows

- **Simulate**: `_isLFTag()` hardcoded tag type set (removed -- scan.so provides this via `isTagLF()`)
- **Simulate**: `showReadToast()` keyword matching on PM3 output (removed -- template.so handles display)
- **Simulate**: `_saveSniffData()` no-op that faked file saving (removed)
- **Scan**: Incorrect scan UI return data from hardcoded predicates (fixed to use scan.so predicates)

### Erase: the exception

The erase flow is our **first middleware module** (`src/middleware/erase.py`). This was justified because:

1. **No `erase.so` exists.** The erase logic is embedded in `activity_main.so` (the WipeTagActivity class), not in a separate middleware module.
2. **We are reimplementing `activity_main.so`.** Since our Python `activity_main.py` replaces the binary, the erase PM3 command sequences naturally belong in our code.
3. **The .so modules had wrong APIs.** `write.write()` takes `(callback, scan_cache, bundle)`, not `({'action': 'erase'})`. `hfmfkeys.hasAllKeys()` requires a sector count argument. These weren't designed for the erase call pattern.
4. **Ground truth confirms it.** `docs/UI_Mapping/13_erase_tag/README.md` lines 24-37: the binary string table shows `wipe_m1`, `wipe_magic_m1`, `wipe_std_m1` as methods OF WipeTagActivity, not of a separate module.

### Structure for future middleware

```
src/middleware/
    __init__.py     # Convention docs
    erase.py        # Erase: detect_mf1_tag(), erase_mf1_detected(), erase_t5577()
```

Convention:
- Module name matches original .so name when shadowing (future: `write.py` → `import write`)
- New modules (no .so counterpart) use descriptive names (`erase.py`)
- Modules call `executor.startPM3Task()` for PM3 commands
- Modules do NOT touch UI (no canvas, no toast, no activity state)
- Modules return results; activities handle UI updates
- `src/middleware/` added to sys.path in launcher and common.sh

---

## 10. Summary

### Problems and solutions

| Problem | Solution | Steps |
|---------|----------|-------|
| Wrong .so module calls (hasAllKeys, write.write, lft55xx.wipe) | Created `src/middleware/erase.py` calling `executor.startPM3Task()` directly | Identified correct PM3 commands from trace, implemented detect+erase functions |
| No scanning/erasing progress UI | Added `STATE_SCANNING` + ProgressBar widget with `on_progress` callback | Split middleware into detect/erase phases, callback updates ProgressBar message |
| Result buttons missing and wrong key behavior | Restored M1/M2="Erase" in `_onEraseResult()`, M1/M2/OK=re-erase | Read state table from spec, matched real device screenshots |
| Toast auto-cancel timer leak | Fixed `Toast._clear()` to cancel pending timers | Diagnosed via state dump: toast appeared then vanished |
| PM3_DELAY override failure (4K test timeout) | Changed `PM3_DELAY="${PM3_DELAY:-0.5}"` to `PM3_DELAY=0.5` | common.sh set it to 3.0 first; `:-` syntax didn't override |
| Tests validated only state count | Implemented 5-gate per-scenario validation (title, buttons, active state, toast) | Modelled on sniff suite's per-gate approach |
| Button state not observable in tests | Added `_m1_active`/`_m2_active`/`_m1_visible`/`_m2_visible` to state dump | For original target: derived from canvas fill color |
| No guard on M1/M2 when buttons hidden | Added guard in `callKeyEvent()`: hidden or inactive buttons suppress M1/M2 | New `keep_bindings=True` option for ConsolePrinterActivity zoom |

### What would have made this faster

1. **Knowing the erase logic is in `activity_main.so`, not in separate .so modules.** The initial implementation wasted time trying to call write.so, hfmfkeys.so, and lft55xx.so with wrong APIs. The binary string table (`docs/UI_Mapping/13_erase_tag/README.md` lines 24-37) proved this immediately -- should have been read first.

2. **Having the state table (`docs/flows/erase/README.md` lines 130-137) highlighted as THE ground truth for key bindings.** The UI Mapping key binding table (lines 241-247) was derived from our (incorrect) implementation, not from the binary. The state table from the erase README was the actual ground truth.

3. **Knowing that `Toast._clear()` doesn't cancel timers.** This cost debugging time. The fix was 3 lines. A rule should exist: "Toast.show() replaces previous toast cleanly, including cancelling any pending auto-dismiss timer."

4. **Having per-gate test validation from the start.** The state-count-only validation gave false confidence. If the sniff suite's multi-gate pattern had been applied from the beginning, the missing buttons and wrong key behavior would have been caught immediately.

5. **Understanding PM3_DELAY inheritance.** The `common.sh` default (3.0) vs `erase_common.sh` default (0.5) conflict was caused by bash `:-` syntax. A note in the test infrastructure docs about this precedence would save time.

6. **PM3 source code availability.** When PM3 trace results are truncated or ambiguous, the source code at `https://github.com/iCopy-X-Community/icopyx-community-pm3` provides definitive command formats, timeout defaults, and response formats.
