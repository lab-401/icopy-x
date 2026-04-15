# Write Flow UI Integration — Post-Mortem & Guide

## Branch: `feat/ui-integrating`
## Date: 2026-04-02
## Status: 61/61 write scenarios PASS, 99/99 read PASS, 45/45 scan PASS

---

## 1. Initial State — What Was Broken

### 1.1 Functionality: WriteActivity Never Launched

`ReadActivity.onActivity()` handled `action='force'`, `action='sniff'`, `action='enter_key'` from WarningM1Activity — but had **no handler for `action='write'`** from WarningWriteActivity. When the user pressed M2 "Write" on the read result screen → WarningWriteActivity appeared → user pressed M2 "Write" → WarningWriteActivity finished with result `{'action': 'write'}` → ReadActivity.onActivity() received it → **ignored it**. WriteActivity was never pushed.

The 63/63 "passing" write tests were **all false positives** — they passed on screenshot state count alone. WriteActivity was never launched in any of them.

**Ground Truth**: `full_read_write_trace_20260327.txt` lines 49-52:
```
START(WarningWriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_7.bin')
FINISH(WarningWriteActivity)
START(WriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_7.bin')
```

### 1.2 Functionality: write.so Call Signature Unknown

The previous code called `write.write(self._infos, self)` (2 args). write.so requires **3 positional arguments**. The signature was unknown — no documentation existed.

### 1.3 Functionality: DRM Blocking All Writes (THE BIGGEST BLOCKER)

`launcher_current.py` had the **wrong cpuinfo serial**: `02150004f4584d53` instead of the correct `02c000814dfb3aeb`. This caused `hfmfwrite.tagChk1()` to silently return `False`, making `write_common()` return `-9` immediately — zero PM3 write commands, "Write failed!" toast.

**This was completely silent** — no error message, no exception, no log. The args to write.so were byte-for-byte identical between the working original and the broken current target. We spent hours investigating attribute names, callback signatures, and activity lifecycle before finding the root cause.

**Ground Truth**: `docs/DRM-KB.md` — correct serial is `02c000814dfb3aeb`. `docs/DRM-Issue.md` — `hfmfwrite.tagChk1()` DRM check #3.

### 1.4 Functionality: write.so Callback Pattern Unknown

The previous code treated write.so as synchronous (waiting for return value). write.so actually:
1. Returns `-9999` immediately (spawns background thread)
2. Calls `on_write` callback with **progress dicts** `{'max': 64, 'progress': N}` during write
3. Calls `on_write` callback with **completion dict** `{'success': True/False}` at the end

### 1.5 Functionality: WriteActivity Attribute Names Wrong

The original Cython WriteActivity had specific public attribute names that write.so accessed:
- `.infos` (not `._infos`)
- `.can_verify` (not `._can_verify`)
- `._write_progressbar` (not `._progressbar`)
- `._write_toast` (not `._toast`)
- `.text_rewrite`, `.text_verify`, `.text_writing`, etc. (resource string attributes)
- `.playWriting()`, `.playVerifying()` (not `._playWriting()`)

### 1.6 UI: Action Bar Visible During Write/Verify Progress

The dark button bar remained visible during "Writing..." and "Verifying..." states. Ground truth (`write_tag_writing_1.png`) shows NO button bar during these states.

### 1.7 UI: Toast Text Overflow

Write/verify toast messages ("Write successful!", "Verification failed!") overflowed the toast box boundaries, overlapping the icon. No margins enforced.

### 1.8 UI: Action Bar Visible During Read Phase

The Rescan button bar was visible during the reading phase (between scan completion and read result). Ground truth (`read_tag_reading_2.png`) shows NO action bar during active read.

### 1.9 UI: "Data ready!" Screen Incorrect

The WarningWriteActivity "Data ready!" screen showed raw type IDs (e.g., "TYPE: 8") instead of the display names from `container.get_public_id()` (e.g., "ID1"). Layout, font sizes, and colors didn't match the real device.

### 1.10 UI: Button Labels Positioned Too High

Button text labels in the dark bar were 5px too high compared to the real device.

### 1.11 Fixture: MF Plus 2K Wrong Response

The `hf 14a info` response had bare `"MIFARE Classic"` instead of `"MIFARE Classic 1K / Classic 1K CL2"` (from upstream PM3 source). This caused scan.so to return type 43 (MF_POSSIBLE) instead of type 1 (MFC 1K).

### 1.12 Fixture: EM4305 Missing Scan Phase

The EM4305 write fixtures were missing scan phase responses (`hf 14a info`, `hf sea`, `lf sea`). Without these, scan.so couldn't identify the tag.

---

## 2. Ground Truth Resources — What Was Vital

### 2.1 Real Device Traces (AUTHORITATIVE)

| Trace | Path | Key Findings |
|-------|------|-------------|
| **LF+HF Write + AutoCopy** | `docs/Real_Hardware_Intel/trace_lf_hf_write_autocopy_20260402.txt` | **THE KEY TRACE.** 10 write cycles captured with patched write.so. Revealed: `write.write(on_write_callback, scan_cache, read_bundle)` signature. Returns -9999 immediately. callback.__self__ is the activity. Bundle is dump path (MFC) or read result dict (LF). |
| **WriteActivity Attributes** | `docs/Real_Hardware_Intel/trace_write_activity_attrs_20260402.txt` | Complete attribute dump of original Cython WriteActivity. Revealed: `.infos`, `.can_verify`, `._write_progressbar`, `._write_toast`, `.text_*` resource strings, `.playWriting()`, `.playVerifying()`. |
| **Write Internal Functions** | `docs/Real_Hardware_Intel/trace_write_internal_funcs_20260402.txt` | write.so internal dispatch: `run_action(run_closure, True)` → `call_on_state('verifying', callback)` → `call_on_finish(1, callback)` → `callReadSuccess(callback)`. |
| **MFC Read+Write** | `docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt` | Activity stack transitions, block write order (reverse: 60→0), verify phase. |
| **AWID Write** | `docs/Real_Hardware_Intel/awid_write_trace_20260328.txt` | LF write bundle: `{'return': 1, 'data': 'FC,CN: X,X', 'raw': '01deb4ddede7e8b7edbdb7e1'}`. DRM password pattern. |
| **FDX-B Write** | `docs/Real_Hardware_Intel/fdxb_t55_write_trace_20260328.txt` | LF clone pipeline: wipe → clone → DRM(b7+b0) → detect+verify. |
| **T55XX Restore** | `docs/Real_Hardware_Intel/t55_to_t55_write_trace_20260328.txt` | T55xx bundle: `{'return': 1, 'data': None, 'raw': None, 'file': '/mnt/upan/dump/t55xx/...'}`. |

### 2.2 Real Device Screenshots

| Screenshot | What It Proved |
|-----------|---------------|
| `write_tag_writing_1.png` | NO button bar during "Writing..." state |
| `write_tag_write_failed.png` | Write failure toast layout |
| `data_ready.png` | "Data ready!" screen: blue text, "TYPE:" centered, "M1-4b" in xlarge bold, message at top |
| `read_tag_reading_2.png` | NO action bar during read phase |

### 2.3 Decompiled Binaries and String Tables

| Resource | Key Findings |
|----------|-------------|
| `decompiled/write_ghidra_raw.txt` | `__pyx_pw_5write_11write` takes 3 params. Keywords: `target`, `infos`, `bundle`. `__pyx_int_neg_9999` return constant. |
| `docs/v1090_strings/write_strings.txt` | `call_on_state`, `call_on_finish`, `callReadSuccess`, `callReadFailed` — module-level callback functions. |
| `docs/v1090_strings/activity_main_strings.txt` | `WriteActivity.on_write`, `WriteActivity.on_verify`, `WriteActivity.playWriting`, `WriteActivity.playVerifying`, `WriteActivity.setBtnEnable` — method symbols confirming public names. |
| `docs/v1090_strings/hf14ainfo_strings.txt` | Keyword matching: `"MIFARE Classic 1K"` → type 1, `"MIFARE Classic"` → type 43 (POSSIBLE), `"MIFARE Plus"` → type 26. |
| `docs/v1090_strings/container_strings.txt` | `get_public_id` function, `M1-4b`, `ID1`, `ID2` display names, `TYP0`-`TYP14` categories. |

### 2.4 PM3 Source Code

`https://github.com/iCopy-X-Community/icopyx-community-pm3`

Used to resolve the Plus 2K detection issue:
- `client/src/cmdhf14a.c` line 1468: SAK 0x08 bitmask check outputs `"MIFARE Classic 1K / Classic 1K CL2"` + `"MIFARE Plus 2K / Plus EV1 2K"` + `"MIFARE Plus CL2 2K / Plus CL2 EV1 2K"`
- `client/luascripts/hf_mf_format.lua` line 112: SAK 0x08 = 16 sectors (Classic 1K / Plus 2K SL1), SAK 0x10 = 32 sectors (Plus 2K SL3)

### 2.5 Techniques That Were Vital

1. **Comparing TEST_TARGET=original vs TEST_TARGET=current**: The original .so WriteActivity worked under QEMU. Comparing PM3 command sequences, callback arguments, and attribute dumps between original and current targets isolated the differences.

2. **Real device live tracing with sitecustomize.py**: Deployed to `/usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py`. Patched `write.write`, `write.verify`, `write.run_action`, `write.call_on_state`, `write.call_on_finish` to log arguments and return values.

3. **Activity attribute dump**: Logged ALL attributes of the original Cython WriteActivity object to compare with our Python version. Revealed the public attribute naming differences.

4. **DRM smoke test**: Check `[OK] tagtypes DRM passed natively` vs `[WARN] tagtypes DRM failed` in launcher log. If DRM fails, ALL writes are silently blocked.

---

## 3. The DRM Problem and Solution

### 3.1 The Problem

`launcher_current.py` had cpuinfo serial `02150004f4584d53` (wrong). `launcher_original.py` had `02c000814dfb3aeb` (correct). The DRM in `hfmfwrite.tagChk1()` uses AES-128 key derivation from the cpuinfo serial. Wrong serial → wrong AES result → DRM check fails → `write_common()` returns -9 → no PM3 commands.

### 3.2 Why It Was Hard to Find

- **Completely silent**: No error message, no exception, no log
- **Args were identical**: The 3 arguments to `write.write()` were byte-for-byte the same between original (passes) and current (fails -9)
- **No attribute differences**: The WriteActivity had all the correct attributes
- **Red herrings**: We investigated callback signatures, attribute names, Python vs Cython class types, threading models — all before finding the serial

### 3.3 The Fix

One line in `launcher_current.py`:
```python
Serial\t\t: 02c000814dfb3aeb   # was: 02150004f4584d53
```

### 3.4 The Rule

**When ANY .so module fails silently — ALWAYS smoke-test DRM first:**
```bash
grep 'tagtypes DRM' scenario_log.txt
# Must see: [OK] tagtypes DRM passed natively: 40 readable types
# If you see: [WARN] tagtypes DRM failed — STOP. Fix the serial.
```

Reference: `docs/DRM-KB.md`, `docs/DRM-Issue.md`

---

## 4. Solutions Implemented

### 4.1 write.so Call Signature (from live trace)

```python
# Ground truth: trace_lf_hf_write_autocopy_20260402.txt
# write.write(on_write_callback, scan_cache, read_bundle)
# write.verify(on_verify_callback, scan_cache, read_bundle)
# Returns -9999 immediately. Result via callback.
write_mod.write(self.on_write, self.infos, self._read_bundle)
write_mod.verify(self.on_verify, self.infos, self._read_bundle)
```

### 4.2 on_write/on_verify Callback (progress + completion)

```python
def on_write(self, *args):
    data = args[0] if args else {}
    if not isinstance(data, dict):
        return
    # Completion: has 'success' key
    if 'success' in data:
        result = 'write_success' if data.get('success') else 'write_failed'
        self._onWriteComplete(result)
        return
    # Progress: has 'max' and 'progress' keys
    if 'max' in data and 'progress' in data:
        pct = int(data['progress'] * 100 / max(data['max'], 1))
        if self._write_progressbar:
            self._write_progressbar.setProgress(pct)
```

### 4.3 Activity Chain: Read → WarningWrite → Write

```python
# ReadActivity._launchWrite() — pass raw read bundle
actstack.start_activity(WarningWriteActivity, self._read_bundle)

# ReadActivity.onActivity() — handle write result from WarningWrite
elif action == 'write':
    actstack.start_activity(WriteActivity, result.get('read_bundle'))

# WarningWriteActivity._confirm_write() — pass bundle through
self._result = {'action': 'write', 'read_bundle': self._read_bundle}
self.finish()
```

### 4.4 WriteActivity Public Attributes (from attribute dump)

```python
# Ground truth: trace_write_activity_attrs_20260402.txt
self.infos = {}                  # NOT _infos — write.so reads activity.infos
self.can_verify = False          # NOT _can_verify
self._write_progressbar = None   # NOT _progressbar
self._write_toast = None         # NOT _toast
self.text_rewrite = resources.get_str('rewrite')
self.text_verify = resources.get_str('verify')
# ... etc for all text_* resource strings
```

### 4.5 State-Dependent Key Mapping

```python
# IDLE: M1=Write, M2=Verify (initial buttons)
# After completion: M1=Verify, M2=Rewrite (swapped!)
if self._state == self.STATE_IDLE:
    if key in (KEY_M1, KEY_OK): self.startWrite()
    elif key == KEY_M2: self.startVerify()
else:
    if key in (KEY_M1, KEY_OK): self.startVerify()
    elif key == KEY_M2: self.startWrite()
```

### 4.6 Button Bar Hidden During Write/Verify

```python
def setBtnEnable(self, enabled):
    if enabled:
        self.disableButton(left=False, right=False)
    else:
        self.dismissButton()  # Hide entire bar, not just grey out

def playWriting(self):
    self.dismissButton()     # Ground truth: write_tag_writing_1.png
    # ... show progress bar
```

### 4.7 "Data ready!" Screen via JSON UI

`src/screens/warning_write.json`:
```json
{
    "content": {
        "type": "text",
        "lines": [
            {"text": "{place_empty_tag}", "size": "large", "align": "left", "color": "#1C6AEB"},
            {"text": "", "size": "normal"},
            {"text": "TYPE:", "size": "large", "align": "center", "color": "#1C6AEB"},
            {"text": "{tag_type_display}", "size": "xlarge", "align": "center", "color": "#1C6AEB"}
        ]
    }
}
```

Type display name from `container.get_public_id(self._infos)` — NOT hardcoded.

### 4.8 Activity State Trigger (replaces M1:Rescan)

```python
# launcher_current.py state dump:
state['activity_state'] = str(getattr(top, 'state', ''))

# Test trigger (read_console_common.sh):
wait_for_ui_trigger "activity_state:reading"  # lifecycle-based, tag-agnostic
```

### 4.9 Toast Margins and State Dump

Widget.py Toast: `_MG=5` (icon gap), `_MR=5` (right margin).
State dump: toast text joined with space (not `\n`) so test triggers match wrapped content.

---

## 5. JSON UI Requirements

### 5.1 Content Type: text (extended)

```json
{
    "type": "text",
    "lines": [
        {"text": "...", "size": "normal|large|xlarge", "align": "left|center", "color": "#hex"}
    ]
}
```

Font sizes: `normal`=10pt, `large`=13pt, `xlarge`=28pt.
Embedded `\n` in resolved text splits into sub-lines.

### 5.2 Variable Resolution

JsonRenderer resolves `{variable}` from `set_state()` dict:
```python
jr.set_state({
    'place_empty_tag': resources.get_str('place_empty_tag'),
    'tag_type_display': container.get_public_id(infos),
})
```

---

## 6. NO MIDDLEWARE — Violations Found

### 6.1 Hardcoded Type Display Names (REMOVED)

Initial attempt used a hardcoded `_TYPE_DISPLAY` dict mapping type IDs to names. This was 100% wrong — `container.get_public_id()` returns the correct names. The dict was invented, not from ground truth.

### 6.2 Invented write.so Call Signature (FIXED)

Initial attempts: `write.write(self._infos, self)` (2 args), then `write.write(tag_type, self._infos, self)` (wrong order), then keyword args. All wrong. The correct signature came ONLY from the live trace.

### 6.3 Wrong WriteActivity Attribute Names (FIXED)

Using Python-conventional `_private` names instead of the Cython public names that write.so accesses. Fixed via the attribute dump trace.

### 6.4 Fixture Corrections (With Ground Truth)

| Fixture | Issue | Fix | Evidence |
|---------|-------|-----|----------|
| EM4305 write (2 scenarios) | Missing scan phase responses | Added `hf 14a info`, `hf sea`, `lf sea` | `read_lf_em4305_success/fixture.py` (99/99 read pass) |
| MF Plus 2K (read + write) | Bare "MIFARE Classic" → type 43 | Changed to "MIFARE Classic 1K / Classic 1K CL2" | PM3 source `cmdhf14a.c` SAK 0x08 |
| Plus 2K type validation | Script expected type 26, scan.so returns 1 or 43 | Accept both 1 and 43 | Read flow state dumps |

---

## 7. High-Level Summary

### 7.1 Problems and Solutions

| # | Problem | Root Cause | Solution | Hours |
|---|---------|-----------|----------|-------|
| 1 | WriteActivity never launched | Missing `action='write'` in `onActivity()` | Added handler to push WriteActivity | 0.5 |
| 2 | write.so returns -9 | **DRM: wrong cpuinfo serial** | Fixed serial in `launcher_current.py` | **6+** |
| 3 | write.so call signature unknown | No documentation | Live trace on real device | 2 |
| 4 | Callback treated as sync return | write.so returns -9999 (async) | Handle progress + completion in `on_write` | 1 |
| 5 | Wrong attribute names | Python conventions vs Cython public | Attribute dump from real device | 1 |
| 6 | Write toast not appearing | Background thread + tkinter | Toast `wrap='auto'`, state dump space-join | 1 |
| 7 | Key mapping wrong after completion | M1/M2 swap: IDLE vs completion | State-dependent dispatch | 0.5 |
| 8 | Action bar during write/verify | `disableButton` vs `dismissButton` | Call `dismissButton()` in setBtnEnable(False) | 0.5 |
| 9 | Data ready screen wrong | Hardcoded type names | `container.get_public_id()` + JSON UI | 1 |
| 10 | Action bar during read | M1:Rescan shown during read | `activity_state:reading` trigger, dismissButton | 1 |
| 11 | Plus 2K detection | Wrong PM3 response | PM3 source cmdhf14a.c | 1 |
| 12 | EM4305 read phase fails | Missing scan fixtures | Copy from read fixtures | 0.5 |
| 13 | Button labels too high | Y=228 vs real device | Y=233 (global constant) | 0.1 |
| 14 | Font sizes wrong | 10pt vs real device 13pt | Updated JSON schema sizes | 0.1 |

### 7.2 Test Progression

```
Start:      0/61 (WriteActivity never launched, all false positives)
DRM fix:   20/61 (write works, verify broken — key mapping wrong)
Key swap:  46/61 (verify works, toast timing issues)
Toast fix: 58/61 (3 fixture issues remaining)
Fixtures:  61/61 PASS
```

### 7.3 What Would Have Made This Faster

1. **DRM documentation in the launcher**: A comment in `launcher_current.py` saying "this serial must match `docs/DRM-KB.md`" would have saved 6+ hours. The DRM issue was solved months ago for `launcher_original.py` but the fix was never applied to `launcher_current.py`.

2. **write.so call signature**: If the live trace had been captured earlier (before investigating attributes, threading, etc.), we would have had the signature in minutes instead of hours.

3. **WriteActivity attribute names**: If the attribute dump trace had been the FIRST investigation step (not the last), we would have found `.infos` vs `._infos` immediately.

4. **The golden rule "smoke-test DRM first"**: This should be the FIRST check for any .so module failure, before any other investigation.

5. **Understanding the test framework**: The write_common.sh 5-phase pipeline sends M1 after M2 confirm. Without auto-start in WriteActivity, M1 triggers write correctly. WITH auto-start, M1 hits verify instead (timing race). Understanding this interaction upfront would have prevented the toast timing investigation.

---

## 8. Commit History

| Hash | Message | Tests |
|------|---------|-------|
| `45929ec` | feat: write flow wiring — ground-truth write.so call signature + live trace | Write broken (DRM) |
| `bb01c59` | fix: DRM cpuinfo serial — write flow unblocked | 20/61 |
| `bf25eb8` | fix: write flow 58/61 — callback dispatch, key mapping | 58/61 |
| `1cb3257` | fix: write flow 61/61 — fixture + type validation | 61/61 |
| `3e90b0c` | fix: UI polish — button bar, toast margins, state dump | 61/61 |
| `0451fd1` | fix: Data ready screen, activity_state trigger, Plus 2K | 61/61 |
| `ae8e9d3` | fix: UI pixel-matching — font sizes, button Y position | 61/61 |

---

## 9. Ground Truth Enforcement

Same rules as Read flow, with one critical addition:

**RULE 11: When .so modules fail silently, ALWAYS smoke-test DRM first.**
Check the launcher log for `[OK] tagtypes DRM passed natively`. If it says `[WARN] tagtypes DRM failed`, fix the cpuinfo serial before investigating anything else. Correct serial: `02c000814dfb3aeb`. Reference: `docs/DRM-KB.md`.

---

## 10. Known Limitations

### MIFARE Plus 2K Detection (SAK 0x08)

Plus 2K in SL1 mode has SAK=0x08 — identical to Classic 1K. PM3 lists both as "Possible types". `hf14ainfo.so` matches "MIFARE Classic 1K" first → type 1. Cannot distinguish without SL3 card (SAK=0x10). Documented in `docs/flows/write/README.md`.

### container.get_public_id() Signature

Takes 1 argument: the scan cache dict (infos). Returns the display name string (e.g., "ID1", "M1-4b"). Discovered empirically — the decompiled binary shows it accepts 1 positional arg but the exact type was confirmed by comparing original .so output with our Python call.
