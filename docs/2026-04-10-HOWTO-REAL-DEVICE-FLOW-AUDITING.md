# Real-Device Flow Auditing — Methodology & Reference

**Created:** 2026-04-10
**Scope:** Generic procedure for auditing ANY flow on the real iCopy-X device
**Status:** Active — apply to every flow audit

---

## 1. PURPOSE

This document defines the procedure for auditing individual UI flows on the real iCopy-X device. Each audit verifies that our open-source Python reimplementation achieves **1:1 parity** with the original compiled firmware across four dimensions:

1. **Flow Functionality** — the flow works end-to-end with real RFID hardware
2. **System-level Functionality** — PM3 stack, USB, files, screen, audio all function correctly
3. **PM3-level Functionality** — every branch of the PM3 logic tree fires correctly
4. **UI Compliance** — pixel-perfect match with the approved JSON UI schema and reference screenshots. Our integrated  UI files were MANUALLY APPROVED - they are your REAL ground-truth. The screenshots act as a validation. (Depending on when the screenshot captured, it may be missing elements or have elements that are easily confused)

---

## 2. PROJECT LAWS

These are **absolute rules**. No exceptions without explicit User permission.

1. **Tests and fixtures are IMMUTABLE.** Never modify test files (`.sh`, `fixture.py`, `expected.json`, triggers, timeouts). If you believe a test is wrong, present your evidence and ASK.

2. **Do NOT touch the integrated UI look and feel.** The JSON screen definitions (`src/screens/*.json`), the `_constants.py` values, and the widget rendering code (`widget.py`, `_renderer.py`) are based on ground truths and have been manually tuned and approved.

3. **During an audit we are ONLY bugfixing.** Feature integration is finished. We are operating in a tightly tested and approved UI+UX framework. Every edit must be justified.

4. **Justify EVERY edit** against one of these criteria:
   - **(a)** This bugfix removes a deviance from ground-truth `.so` or UI behavior, and I can cite the ground-truth source.
   - **(b)** This modification fills a functionality/UI gap that was not properly integrated, and I can cite its presence in ground-truth elements.
   - **(c)** I asked the User SPECIFICALLY for this modification and they SPECIFICALLY gave permission.

5. **Never change activity flow architecture.** The activity push/pop sequences (e.g., AutoCopy → WarningWriteActivity → WriteActivity) are ground truth from original device traces. Fix bugs WITHIN activities, never reroute the flow.

6. **Never flash PM3 bootrom.** No JTAG = bricked device. Zero exceptions.

7. **Never access `~/.ssh` on any device.**

8. **Never modify the user's RFID cards** (cwipe, csetblk, etc.) without explicit permission.

9. **No hardcoded UI values.** All colors, coordinates, fonts, and dimensions must come from `_constants.py` or the JSON screen schema. Never use raw hex colors or pixel values in activity code.

10. **No guessing.** Every line of code must cite a ground-truth source: decompiled `.so`, real device trace, real screenshot, or approved test fixture.

---

## 3. AUDIT DIMENSIONS

### 3.1 Flow Functionality

Verify the flow works end-to-end on real hardware with real RFID tags:

- Activity transitions match the ground-truth trace sequence
- PM3 commands fire and receive real responses (not empty/offline)
- Scan cache is populated correctly
- File operations (save dump, load dump) succeed
- Result toasts appear with correct text
- Flow timing is within 2x of original (no instant completion, no excessive delays)

### 3.2 System-level Functionality

Verify system integrations within the flow:

| System | What to check |
|--------|--------------|
| PM3 subprocess | Connected (`fd 3 → /dev/ttyACM0`), responds to commands |
| RTM TCP server | Listening on port 8888, accepts Nikola protocol |
| USB storage | `/mnt/upan/` mounted, dump files readable/writable |
| DRM serial | `02c000814dfb3aeb` (must match for `.so` modules) |
| HMI serial | Key events dispatched to correct activity |
| Audio | Scan/read/write audio cues play at correct moments |
| Screen brightness | Backlight responds to settings |
| File I/O | Dump files created at correct paths with correct format |

### 3.3 PM3-level Functionality

Verify every branch of the PM3 command tree for the flow:

- **Command sequence**: Compare PM3 commands in trace against ground-truth trace line-by-line
- **Command arguments**: Verify keys, sector numbers, block numbers, timeouts match
- **Response parsing**: Verify `executor.hasKeyword()` / `executor.getContentFromRegex()` calls extract the correct data from PM3 output
- **Error handling**: Verify `-1`, `-10`, `-13` return codes trigger correct branches
- **Retry logic**: Verify `reworkPM3All()` fires only when appropriate (not spuriously)
- **Gen1a detection**: `hf mf cgetblk 0` → `data:` format properly detected
- **Key recovery pipeline**: fchk → darkside → nested → fchk sequence for each MFC variant

### 3.4 UI Compliance

Verify pixel-perfect UI match with approved ground truth:

#### Sources of UI truth (in priority order):
1. **Approved test screenshots** — `tests/flows/{flow}/_results/{scenario}/screenshots/`
2. **Real device framebuffer captures** — `docs/Real_Hardware_Intel/framebuffer_captures/`
3. **JSON screen definitions** — `src/screens/{flow}.json`
4. **UI Mapping documentation** — `docs/UI_Mapping/{NN}_{flow}/`
5. **Constants** — `src/lib/_constants.py`

#### Checklist:
- [ ] No hardcoded colors — all colors from `_constants.py` (`COLOR_ACCENT`, `PROGRESS_FG`, etc.)
- [ ] No hardcoded coordinates — all positions from `_constants.py` or JSON screen schema
- [ ] No hardcoded fonts — all fonts from `resources.get_font()` or `_constants.py`
- [ ] Progress bars wired to middleware callbacks and updating via `root.after()` (Tk thread safety)
- [ ] Status text matches ground-truth format exactly (check screenshots for line count, alignment, content)
- [ ] Toast messages match `resources.get_str()` values
- [ ] Button labels match ground-truth at each state (M1/M2 text, active/disabled)
- [ ] Title bar text correct for each activity state
- [ ] Template rendering (tag info cards) matches approved screenshots
- [ ] Content layout during operations (scanning/reading/writing) matches reference screenshots

---

## 4. AUDIT PROCEDURE

### Phase 0: Pre-flight

Before any testing, verify device health:

```bash
# SSH access
sshpass -p 'fa' ssh -p 2222 root@localhost

# Quick health check
sshpass -p 'fa' ssh -p 2222 root@localhost '
echo "=== App ===" && pgrep -fa "python.*app.py" | head -1
echo "=== PM3 ===" && pm3pid=$(pgrep -x proxmark3) && \
  ls -la /proc/$pm3pid/fd/3 2>/dev/null && echo "USB-CDC OK" || echo "PM3 NOT CONNECTED"
echo "=== RTM ===" && ss -tlnp 2>/dev/null | grep 8888 || echo "RTM not listening"
echo "=== DRM ===" && grep Serial /proc/cpuinfo
echo "=== Storage ===" && df -h /mnt/upan/ 2>/dev/null | tail -1
'
```

**All must pass before proceeding.**

### Phase 1: Deploy Telemetry

Deploy the application tracer. This patches `actstack`, `executor`, `scan`, and `keymap` to log all activity transitions, PM3 commands/responses, scan cache updates, and key events.

```bash
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat > /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py' << 'PYEOF'
import threading, time, json, sys

def _go():
    for _ in range(120):
        if "application" in sys.modules:
            break
        time.sleep(0.5)
    else:
        return

    time.sleep(5)

    LOG = "/mnt/upan/full_trace.log"
    t0 = time.time()
    with open(LOG, "w") as f:
        f.write("=== TRACE ===\n")

    def lg(m):
        try:
            with open(LOG, "a") as f:
                f.write("[%8.3f] %s\n" % (time.time() - t0, m))
        except: pass

    import actstack, executor, scan, keymap

    _orig_onKey = keymap.key.onKey
    def _traced_onKey(event):
        try: lg("KEY> %s" % event)
        except: pass
        return _orig_onKey(event)
    keymap.key.onKey = _traced_onKey

    o1 = actstack.start_activity
    def t1(*a, **kw):
        try:
            lg("START(%s)" % ", ".join(
                x.__name__ if hasattr(x, "__name__") else repr(x) for x in a))
        except: pass
        return o1(*a, **kw)
    actstack.start_activity = t1

    o2 = actstack.finish_activity
    def t2(*a, **kw):
        try:
            lg("FINISH(top=%s d=%d)" % (
                type(actstack._ACTIVITY_STACK[-1]).__name__,
                len(actstack._ACTIVITY_STACK)))
        except: pass
        return o2(*a, **kw)
    actstack.finish_activity = t2

    o3 = executor.startPM3Task
    def t3(*a, **kw):
        try: lg("PM3> %s (timeout=%s)" % (str(a[0])[:200], a[1] if len(a)>1 else kw.get("timeout","?")))
        except: pass
        r = o3(*a, **kw)
        try:
            lg("PM3< ret=%s %s" % (
                r, (executor.CONTENT_OUT_IN__TXT_CACHE or "").replace("\n", "\\n")[:500]))
        except: pass
        return r
    executor.startPM3Task = t3

    o4 = scan.setScanCache
    def t4(infos):
        try:
            if isinstance(infos, dict):
                lg("CACHE: %s" % json.dumps(
                    {k: repr(v)[:40] for k, v in infos.items()}))
        except: pass
        return o4(infos)
    scan.setScanCache = t4

    _orig_connect = executor.connect2PM3
    def _traced_connect(*a, **kw):
        lg("CONNECT> connect2PM3()")
        r = _orig_connect(*a, **kw)
        lg("CONNECT< socket=%s" % (executor._socket_instance is not None))
        return r
    executor.connect2PM3 = _traced_connect

    _orig_rework = executor.reworkPM3All
    def _traced_rework(*a, **kw):
        lg("REWORK> reworkPM3All()")
        r = _orig_rework(*a, **kw)
        lg("REWORK< socket=%s" % (executor._socket_instance is not None))
        return r
    executor.reworkPM3All = _traced_rework

    def _poll():
        prev = ""
        while True:
            try:
                names = [type(x).__name__ for x in actstack._ACTIVITY_STACK]
                cache = scan.getScanCache()
                cs = ""
                if isinstance(cache, dict):
                    cs = "type=%s uid=%s" % (
                        cache.get("type", "?"),
                        str(cache.get("uid", ""))[:16])
                line = "stack=%s %s" % (names, cs)
                if line != prev:
                    lg("POLL %s" % line)
                    prev = line
            except: pass
            time.sleep(0.5)
    threading.Thread(target=_poll, daemon=True).start()

    lg("=== ALL INSTALLED ===")

threading.Thread(target=_go, daemon=True).start()
PYEOF

# Clear old trace, restart app
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'rm -f /mnt/upan/full_trace.log; kill $(pgrep -f "python.*app.py" | head -1)'

# Wait for restart + tracer init
sleep 25

# Verify
sshpass -p 'fa' ssh -p 2222 root@localhost 'head -5 /mnt/upan/full_trace.log'
```

### Phase 2: User Performs Test

The User navigates the device through the target flow. The agent specifies what to do:

- Which menu item to select
- Which tags to place on the reader
- Which buttons to press at decision points
- When to press PWR to exit

The agent does NOT control the device — the User does.

### Phase 3: Pull and Analyze Trace

```bash
# Pull trace
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat /mnt/upan/full_trace.log' \
  > docs/Real_Hardware_Intel/trace_oss_{flow}_{date}.txt

# Quick summary
grep -c 'PM3>' trace_file          # PM3 command count
grep -c 'KEY>' trace_file          # Key event count  
grep 'START\|FINISH' trace_file    # Activity transitions
grep 'REWORK' trace_file           # Unexpected reconnects
```

### Phase 4: Compare Against Ground Truth

For each flow, compare the OSS trace against the original firmware trace:

| Dimension | OSS Trace | Original Trace | Verdict |
|-----------|-----------|---------------|---------|
| Activity sequence | `START/FINISH` lines | Same from original trace | MATCH / MISMATCH |
| PM3 command sequence | `PM3>` lines | Same from original trace | MATCH / MISMATCH |
| PM3 response codes | `ret=1` / `ret=-1` | Same from original trace | MATCH / MISMATCH |
| Scan cache | `CACHE:` lines | Same from original trace | MATCH / MISMATCH |
| Key events | `KEY>` lines | N/A (user-driven) | N/A |
| Timing | Timestamps | Timestamps from original | WITHIN 2x / TOO FAST / TOO SLOW |
| Spurious reworks | `REWORK>` count | 0 expected | COUNT |

### Phase 5: Fix Identified Issues

For each bug found:

1. **Cite the ground truth** — which trace line, screenshot, or test fixture shows the expected behavior
2. **Identify the code** — which file and line produces the wrong behavior
3. **Propose the fix** — minimum change to match ground truth
4. **Justify** — criterion (a), (b), or (c) from Section 2
5. **Apply and deploy** — hot-deploy via SCP, restart app
6. **Re-test** — pull new trace, verify fix

### Phase 6: Cleanup

**MANDATORY** after every session:

```bash
# Remove tracer (left-behind sitecustomize.py crashes the app on next boot)
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'rm -f /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py'
```

---

## 5. DEVICE ACCESS

```bash
# SSH
sshpass -p 'fa' ssh -p 2222 root@localhost

# Deploy a single file
sshpass -p 'fa' scp -P 2222 src/lib/somefile.py root@localhost:/home/pi/ipk_app_main/lib/somefile.py

# Deploy middleware (src/middleware/*.py → device lib/)
sshpass -p 'fa' scp -P 2222 src/middleware/somefile.py root@localhost:/home/pi/ipk_app_main/lib/somefile.py

# Deploy main modules
sshpass -p 'fa' scp -P 2222 src/main/somefile.py root@localhost:/home/pi/ipk_app_main/main/somefile.py

# Restart app (watchdog relaunches)
sshpass -p 'fa' ssh -p 2222 root@localhost 'kill $(pgrep -f "python.*app.py" | head -1)'

# One-liner: deploy + restart
sshpass -p 'fa' scp -P 2222 FILE root@localhost:DEST && \
sshpass -p 'fa' ssh -p 2222 root@localhost 'kill $(pgrep -f "python.*app.py" | head -1)'
```

**Path mapping (local → device):**

| Local | Device |
|-------|--------|
| `src/lib/*.py` | `/home/pi/ipk_app_main/lib/` |
| `src/middleware/*.py` | `/home/pi/ipk_app_main/lib/` (same dir as lib) |
| `src/main/*.py` | `/home/pi/ipk_app_main/main/` |
| `src/screens/*.json` | `/home/pi/ipk_app_main/screens/` |

---

## 6. GROUND-TRUTH RESOURCES

### 6.1 Original Firmware Traces (35 traces)

Located in `docs/Real_Hardware_Intel/`. Key traces per flow:

| Flow | Trace File | Content |
|------|-----------|---------|
| Scan (HF) | `trace_scan_flow_20260331.txt` | MFC1K, NTAG, ISO15693, Indala, FDX-B |
| Scan (LF) | `trace_lf_scan_flow_20260331.txt` | 15 LF badge types |
| Scan (iCLASS) | `trace_iclass_scan_20260331.txt` | iCLASS with key recovery |
| Read/Write (MFC) | `full_read_write_trace_20260327.txt` | MFC 1K full pipeline |
| Read (flow) | `trace_read_flow_20260401.txt` | Multiple tag types |
| Write (attrs) | `trace_write_activity_attrs_20260402.txt` | WriteActivity internals |
| Write (internal) | `trace_write_internal_funcs_20260402.txt` | hfmfwrite function calls |
| AutoCopy (MFC) | `trace_autocopy_mf1k_standard.txt` | MFC 1K standard auto-copy |
| AutoCopy (multi) | `autocopy_mf4k_mf1k7b_t55_trace_20260329.txt` | MFC4K, MFC1K-7B, T55XX |
| Erase | `trace_erase_flow_20260330.txt` | Multiple tag types |
| Sniff | `trace_sniff_flow_20260403.txt` | HF/LF sniff |
| Dump Files | `trace_dump_files_20260403.txt` | File listing + write from dump |
| Console/LUA | `trace_console_flow_20260401.txt` | Console view, LUA scripts |
| Misc | `trace_misc_flows_20260330.txt` | About, PC Mode, Time |

### 6.2 Real Device Screenshots (160 captures)

Located in `docs/Real_Hardware_Intel/framebuffer_captures/`. RGB565 format, 240x240px.

### 6.3 Approved Test Suites (394 fixtures, 433 scenarios)

Located in `tests/flows/`. Each flow has:
- `scenarios/{name}/fixture.py` — PM3 response fixtures
- `scenarios/{name}/expected.json` — approved UI state expectations
- `scenarios/{name}/{name}.sh` — test script
- `includes/` — shared test infrastructure

### 6.4 JSON Screen Definitions (18 screens)

Located in `src/screens/`. Define the UI layout for each activity state including content type, button labels, key bindings.

### 6.5 UI Mapping Documentation (19 flows)

Located in `docs/UI_Mapping/`. Pixel-level UI specifications with screenshot references.

### 6.6 Binary Ground Truth

| Resource | Path |
|----------|------|
| Original `.so` modules | `orig_so/lib/*.so`, `orig_so/main/*.so` |
| Decompiled analysis | `decompiled/SUMMARY.md` |
| String tables | `docs/v1090_strings/` |
| Module audit | `docs/V1090_MODULE_AUDIT.txt` |

---

## 7. FLOW AUDIT ORDER

Test from simple to complex, each building on the previous:

| # | Flow | PM3 Required | Key Tags Needed |
|---|------|-------------|-----------------|
| 1 | About | No | None |
| 2 | Backlight / Volume | No | None |
| 3 | PC Mode | No | None |
| 4 | Scan | Yes | MFC 1K, LF badge, NTAG |
| 5 | Read | Yes | MFC 1K (known keys) |
| 6 | Write | Yes | MFC 1K source + Gen1a target |
| 7 | Auto-Copy | Yes | MFC 1K source + Gen1a target |
| 8 | Erase | Yes | Gen1a or standard MFC |
| 9 | Simulate | Yes | MFC 1K (after scan) |
| 10 | Sniff | Yes | Two cards communicating |
| 11 | Dump Files | Partial | Existing dump files on `/mnt/upan/` |
| 12 | LUA Scripts | Yes | Depends on script |
| 13 | Time Settings | No | None |

---

## 8. PER-FLOW AUDIT CHECKLIST

Copy this for each flow audit:

```
Flow: _______________
Date: _______________
OSS Trace: docs/Real_Hardware_Intel/trace_oss_{flow}_{date}.txt
Ground Truth Trace: docs/Real_Hardware_Intel/{original_trace}.txt

PRE-FLIGHT
[ ] App running (python3 app.py)
[ ] PM3 connected (fd 3 → /dev/ttyACM0)
[ ] RTM listening (port 8888)
[ ] DRM serial correct (02c000814dfb3aeb)
[ ] Tracer active (full_trace.log updating)

FLOW FUNCTIONALITY
[ ] Activity transitions match ground truth
[ ] PM3 commands fire in correct sequence
[ ] PM3 responses parsed correctly
[ ] Scan cache populated correctly
[ ] Result callbacks fire correctly
[ ] Flow completes without crash

SYSTEM-LEVEL
[ ] File I/O works (dump save/load)
[ ] Audio cues play at correct moments
[ ] PWR exits correctly at every state
[ ] No spurious reworkPM3All()
[ ] No zombie processes after flow

PM3-LEVEL
[ ] Command sequence matches ground truth
[ ] Command arguments (keys, sectors, timeouts) correct
[ ] Response regex parsing correct
[ ] Error codes trigger correct branches
[ ] Gen1a detection works (if applicable)
[ ] Key recovery pipeline correct (if applicable)

UI COMPLIANCE
[ ] No hardcoded colors (all from _constants.py)
[ ] No hardcoded coordinates
[ ] Progress bar updates during operations
[ ] Status text matches ground-truth format
[ ] Toast text matches resources.get_str()
[ ] Button labels correct at each state
[ ] Title bar text correct
[ ] Template rendering matches screenshots
[ ] Content layout matches reference screenshots
[ ] Toasts dismissed on activity pause (PWR back)
```

---

## 9. CRITICAL IMPLEMENTATION NOTES

### 9.1 Tk Thread Safety

All middleware callbacks fire from background threads. Any callback that touches the UI (canvas operations, widget updates, activity transitions) MUST be scheduled on the Tk main thread:

```python
from lib import actstack
if actstack._root is not None:
    actstack._root.after(0, ui_function, *args)
```

This applies to: `onScanning`, `onReading`, `on_write`, `onScanFinish`, and any other callback from `scan.py`, `read.py`, `write.py`, or `hfmfkeys.py`.

### 9.2 PM3 Subprocess

The PM3 Popen call MUST use these exact parameters (ground truth from original `.so` process tree):

```python
subprocess.Popen(
    pm3_cmd_string,          # string, NOT list
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, # merged, NOT separate
    shell=True,
    close_fds=True,
    start_new_session=True,
)
```

The command string must include `sudo -s`. Process tree: `python3 → sh → sudo → proxmark3`.

### 9.3 Key Dictionary File

The key dictionary must be written with `.dic` extension: `/tmp/.keys/mf_tmp_keys.dic`. PM3's `hf mf fchk` auto-appends `.dic` to the filename.

### 9.4 Gen1a Detection

PM3 RRG v385d892 outputs `data: XX XX XX ...` for `hf mf cgetblk 0`, not `Block 0:`. The detection regex must match both formats.
