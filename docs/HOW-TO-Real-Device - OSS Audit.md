# Real-Device OSS Firmware Audit Plan

**Date:** 2026-04-10
**Status:** PLANNING
**Goal:** Identify and fix all real-device functional failures in the open-source firmware

---

## 1. PROBLEM STATEMENT

The open-source firmware passes all QEMU-based test scenarios (402/402 flows), but
**real-device testing reveals that actual RFID functionality is broken across ALL flows**.

Symptoms observed:
- Scan does NOT detect badges (PM3 layer is broken, mocked, or uninitialized)
- ProgressBars are tied to artificial progress markers, not real PM3 command completion
- Toasts use fixed delays rather than reacting to real background events
- All flows exhibit "test-passing but not functional" behavior

**Root hypothesis:** The middleware was built to make test fixtures pass, not to actually
communicate with PM3 hardware. Tests mock `executor.startPM3Task`,
`executor.connect2PM3`, and all PM3 communication — so 100% test pass rate proves
nothing about real-device functionality.

---

## 2. PRELIMINARY CODE AUDIT FINDINGS

### 2.1 Critical Gap: TCP Socket Never Initialized

**File:** `src/middleware/executor.py`

`connect2PM3()` (line 114) creates the TCP socket to RemoteTaskManager on port 8888.
**It is NEVER called during normal application startup.**

- `main.py` starts `RemoteTaskManager` (TCP server on 8888) but never calls `connect2PM3()`
- `_socket_instance` starts as `None` (line 66)
- First PM3 command hits `_send_and_cache()` → `_socket_instance is None` → returns empty string (line 181-183)
- `startPM3Task()` sees empty result → triggers `reworkPM3All()` (line 349)
- `reworkPM3All()` calls `connect2PM3()` (line 432) — **recovery-only initialization**
- Net effect: First command ALWAYS fails, triggers reconnect, then retries

**Impact:** Every first PM3 command in every flow fails silently. The retry mechanism
may or may not recover depending on timing and RemoteTaskManager state.

**Original firmware behavior:** The original `.so` likely calls `connect2PM3()` during
init or has the socket pre-connected. This must be verified via trace.

### 2.2 Test Launchers Mock Everything

All test launchers completely bypass real PM3 communication:

```python
# tools/launcher_current.py:516-517
executor.startPM3Task = _pm3_mock      # Returns canned fixture responses
executor.connect2PM3 = lambda *a, **k: True  # No-op
```

This means tests prove the UI responds correctly to fixture data, but say
**absolutely nothing** about whether the PM3 communication chain works.

### 2.3 PM3 Communication Chain IS Implemented

The good news: the actual PM3 communication code is real and complete.

```
Middleware → executor (TCP:8888) → RemoteTaskManager (port 8888) → PM3 subprocess (stdin/stdout)
```

- `src/main/rftask.py`: Real `subprocess.Popen()` to proxmark3 binary (line 343)
- `src/middleware/executor.py`: Real TCP socket with `Nikola.D.CMD` protocol (line 186-189)
- Response parsing: Real regex matching on `CONTENT_OUT_IN__TXT_CACHE`
- No hardcoded responses in production code

**The chain exists but may not be properly bootstrapped on real hardware.**

### 2.4 Progress Bar: Event-Driven but Artificial

The scan middleware reports fixed progress percentages at pipeline stage boundaries:
```python
# src/middleware/scan.py (Scanner class)
self._call_progress_method(23)   # Before scan_14a
self._call_progress_method(33)   # Before scan_lfsea
self._call_progress_method(53)   # Before scan_hfsea
self._call_progress_method(67)   # Before scan_t55xx
self._call_progress_method(83)   # Before scan_em4x05
self._call_progress_method(90)   # Before scan_felica
self._call_progress_method(100)  # Completion
```

These fire synchronously as the pipeline executes. If PM3 commands fail silently
(empty response, immediate return), the progress bar races through 0→100% instantly
with no real scanning occurring.

### 2.5 Sleep Audit

Production middleware sleeps (not test code):
| File | Line | Duration | Context |
|------|------|----------|---------|
| `executor.py` | 98 | 0.05s | Waiting for task stop |
| `executor.py` | 107 | 0.1s | Post-stop delay |
| `executor.py` | 369 | 0.05s | stopPM3Task wait loop |
| `executor.py` | 431 | 3.0s | reworkPM3All recovery delay |
| `write.py` | 136, 228 | 0.3s | Post-write delay |
| `rftask.py` | 202 | 1.0s | PM3 subprocess restart |
| `activity_read.py` | 484 | 2.0s | Read completion fallback |
| `activity_main.py` | 894 | 0.3s | Console poll interval |

None of these are "fake progress" sleeps — they are operational delays. The issue is
not fake delays but rather **real operations that fail silently and return immediately**.

---

## 3. AUDIT METHODOLOGY

### 3.1 Flow-by-Flow Real-Device Testing

Each flow will be tested on the real device with full instrumentation. The trace
captures activity transitions, PM3 commands, responses, and scan cache state.

**Test order** (simple → complex, each builds on the previous):

| # | Flow | Complexity | PM3 Required | Dependencies |
|---|------|-----------|-------------|-------------|
| 1 | About | None | No | None |
| 2 | PC Mode | Low | No | None |
| 3 | Scan | High | Yes | executor, rftask, scan, all parsers |
| 4 | Read | High | Yes | Scan + read modules |
| 5 | Write | High | Yes | Scan + Read + write modules |
| 6 | Auto-Copy | Very High | Yes | Scan + Read + Write pipeline |
| 7 | Simulate | Medium | Yes | Scan + simulate |
| 8 | Erase | Medium | Yes | Scan + erase modules |
| 9 | Dump Files | Medium | Partial | File operations + PM3 write |
| 10 | Sniff | High | Yes | PM3 sniff commands |
| 11 | LUA Scripts | Medium | Yes | PM3 script execution |
| 12 | Time Settings | Low | No | System commands |

### 3.2 Instrumentation Protocol

We use the established tracer from `docs/HOW_TO_RUN_LIVE_TRACES.md`. The tracer
captures ALL information needed to diagnose real-device failures.

**Two-phase capture** (NEVER simultaneous):
1. **Application trace** — Python-level patching of `actstack`, `executor`, `scan`
2. **Framebuffer capture** — `/dev/fb1` screenshots at 500ms intervals

### 3.3 Comparison Against Ground Truth

Every trace from the OSS firmware will be compared against the original firmware traces:

| Original Trace | Flow | Date |
|---------------|------|------|
| `trace_scan_flow_20260331.txt` | Scan (HF mixed) | 2026-03-31 |
| `trace_lf_scan_flow_20260331.txt` | Scan (15 LF badges) | 2026-03-31 |
| `trace_iclass_scan_20260331.txt` | Scan (iCLASS) | 2026-03-31 |
| `full_read_write_trace_20260327.txt` | Read→Write (MFC 1K) | 2026-03-27 |
| `trace_read_flow_20260401.txt` | Read | 2026-04-01 |
| `trace_erase_flow_20260330.txt` | Erase | 2026-03-30 |
| `trace_autocopy_mf1k_standard.txt` | AutoCopy (MFC 1K) | 2026-03-29 |
| `trace_sniff_flow_20260403.txt` | Sniff | 2026-04-03 |
| `trace_dump_files_20260403.txt` | Dump Files | 2026-04-03 |
| `trace_console_flow_20260401.txt` | Console/LUA | 2026-04-01 |
| `trace_misc_flows_20260330.txt` | About/PCMode/Time | 2026-03-30 |

---

## 4. DETAILED AUDIT PROCEDURE

### Phase 1: Pre-Flight Diagnostics (No User Action Required)

Before any manual testing, perform automated diagnostics via SSH.

```bash
# === 1. Verify device is accessible ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'uname -a && uptime'

# === 2. Check if OSS firmware is running ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'ps aux | grep python | grep -v grep'

# === 3. Check if PM3 subprocess is running ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'ps aux | grep proxmark3 | grep -v grep'

# === 4. Check if RemoteTaskManager TCP server is listening ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'ss -tlnp | grep 8888'

# === 5. Check PM3 device node exists ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'ls -la /dev/ttyACM*'

# === 6. Check DRM status (cpuinfo serial) ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat /proc/cpuinfo | grep Serial'
# Expected: 02c000814dfb3aeb

# === 7. Check executor socket state ===
# Deploy a one-shot diagnostic script:
sshpass -p 'fa' ssh -p 2222 root@localhost 'python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.settimeout(2)
    s.connect((\"127.0.0.1\", 8888))
    s.sendall(b\"Nikola.D.CMD = hw version\n\")
    import time; time.sleep(2)
    data = b\"\"
    s.settimeout(1)
    while True:
        try:
            chunk = s.recv(1024)
            if not chunk: break
            data += chunk
        except: break
    print(\"PM3 RESPONSE:\", data.decode(errors=\"replace\")[:500])
except Exception as e:
    print(\"CONNECTION FAILED:\", e)
finally:
    s.close()
"'

# === 8. Check app log for errors ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'tail -50 /mnt/upan/app.log 2>/dev/null || echo "No app.log"'

# === 9. Check tagtypes DRM status ===
sshpass -p 'fa' ssh -p 2222 root@localhost 'grep -r "DRM" /mnt/upan/*.log 2>/dev/null || echo "No DRM logs"'
```

**Expected healthy state:**
- Python app running (`app.py`)
- PM3 subprocess running (`proxmark3`)
- TCP 8888 listening
- `/dev/ttyACM0` exists
- `hw version` returns PM3 firmware info
- DRM serial matches `02c000814dfb3aeb`

**Record all diagnostic output to:** `docs/Real_Hardware_Intel/oss_preflight_YYYYMMDD.txt`

### Phase 2: Deploy Instrumentation

Deploy the standard tracer from `docs/HOW_TO_RUN_LIVE_TRACES.md` Section 5.

```bash
# Deploy tracer
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat > /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py' < tools/tracer_sitecustomize.py

# Clear old trace
sshpass -p 'fa' ssh -p 2222 root@localhost 'rm -f /mnt/upan/full_trace.log'

# Restart app (watchdog relaunches)
sshpass -p 'fa' ssh -p 2222 root@localhost 'kill $(pgrep -f "python.*app.py" | head -1)'

# Wait for boot + tracer install
sleep 30

# Verify tracer is running
sshpass -p 'fa' ssh -p 2222 root@localhost 'head -5 /mnt/upan/full_trace.log'
```

### Phase 3: SCAN Flow Audit (First Priority)

The Scan flow is the foundation for all RFID flows. If Scan doesn't work, nothing works.

#### 3a. User performs scan with a known HF tag (MIFARE Classic 1K)

1. User navigates to: Main Menu → Scan
2. User places MFC 1K tag on reader
3. User waits for scan result
4. User removes tag, presses PWR to exit
5. User reports what they saw on screen

#### 3b. Retrieve and analyze trace

```bash
# Pull trace
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat /mnt/upan/full_trace.log' \
  > docs/Real_Hardware_Intel/trace_oss_scan_YYYYMMDD.txt
```

#### 3c. Compare against original trace

**Original reference:** `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt`

Compare the following dimensions:

| Dimension | Original Behavior | What to Check in OSS |
|-----------|------------------|---------------------|
| Activity start | `START(ScanActivity, None)` | Same activity pushed? |
| First PM3 cmd | `hf 14a info` within 64ms of activity start | Command sent? Timing? |
| PM3 response | `ret=1` + UID/SAK/ATQA data | Real response or empty? |
| Command sequence | `14a → cgetblk → mfu info` (for MFC 1K) | Same sequence? |
| Scan cache | `type=1 uid=3AF73501` | Cache populated? |
| Activity finish | `FINISH(top=dict d=2)` | Activity exits cleanly? |
| Timing | 5-10s for full scan cycle | Instant (= fake) or real? |

**Critical questions:**
1. Are PM3 commands actually sent? (`PM3>` lines in trace)
2. Do PM3 commands get real responses? (`PM3< ret=1` with data, not empty)
3. Is the scan cache populated with real tag data?
4. Does the UI show the correct tag type and UID?
5. What is the total scan duration? (Instant = broken, 5-10s = working)

#### 3d. Failure taxonomy

Based on the trace, classify the failure:

| Failure Type | Symptom in Trace | Root Cause | Fix |
|-------------|-----------------|-----------|-----|
| **No PM3 commands** | No `PM3>` lines | `connect2PM3()` never called, socket=None | Add `connect2PM3()` to startup |
| **PM3 commands fail** | `PM3< ret=-1` or empty response | RemoteTaskManager not running or PM3 subprocess dead | Fix RTM startup, check `/dev/ttyACM0` |
| **Commands sent but no tag found** | `PM3< ret=1` but no UID data | PM3 binary wrong version, antenna not powered | Check PM3 binary, verify `hw tune` |
| **Tag found but UI doesn't show** | Trace has cache data but screen blank | UI callback chain broken | Debug `onScanFinish` → UI render path |
| **Instant completion** | All commands in <100ms | Commands fail immediately, no retry | Fix retry/rework logic |

### Phase 4: Fix Identified Issues

Based on Phase 3 findings, fixes will follow a strict pattern:

1. **Identify** — Trace shows exact failure point
2. **Compare** — What does original trace show at same point?
3. **Root-cause** — What code path produces the wrong behavior?
4. **Fix** — Modify the minimum code to match original behavior
5. **Verify** — Re-run trace on device, compare again

**No guessing. No "try this". Every fix must be justified by trace evidence.**

### Phase 5: Remaining Flow Audits

After Scan is confirmed working, proceed through each flow:

#### About Flow
- **What to trace:** Activity transitions only (no PM3)
- **Key check:** Version string, serial number display, USB ID
- **Original reference:** `trace_misc_flows_20260330.txt`

#### PC Mode Flow
- **What to trace:** Activity transitions, PM3 process management
- **Key check:** PM3 enters standalone mode, USB gadget switches to CDC-ACM
- **Original reference:** `trace_misc_flows_20260330.txt`

#### Read Flow
- **What to trace:** Full pipeline (scan → read activity → sector reads)
- **Key check:** `hf mf rdbl` / `hf mf rdsc` commands sent, data saved to dump file
- **Original reference:** `trace_read_flow_20260401.txt`, `full_read_write_trace_20260327.txt`
- **Tag required:** MIFARE Classic 1K (known working tag from scan test)

#### Write Flow
- **What to trace:** Full pipeline (scan → read → prompt → write → verify)
- **Key check:** `hf mf wrbl` commands sent, verification pass
- **Original reference:** `full_read_write_trace_20260327.txt`
- **Tags required:** Source MFC 1K + target Gen1a or blank MFC 1K

#### Auto-Copy Flow
- **What to trace:** Full pipeline (scan → read → swap prompt → write → verify)
- **Key check:** All 4 stages complete, correct toast at each transition
- **Original reference:** `trace_autocopy_mf1k_standard.txt`
- **Tags required:** Source MFC 1K + target Gen1a

#### Simulate Flow
- **What to trace:** `hf 14a sim` command with correct UID
- **Key check:** Simulation starts, trace captured, displayed
- **Original reference:** `trace_scan_flow_20260331.txt` (lines 71-84 show sim after scan)

#### Erase Flow
- **What to trace:** Wipe commands per tag type
- **Key check:** `hf mf cwipe` or equivalent sent, success toast
- **Original reference:** `trace_erase_flow_20260330.txt`

#### Dump Files Flow
- **What to trace:** File listing, file selection, write from dump
- **Key check:** `/mnt/upan/dump/` directory scanned, correct files listed
- **Original reference:** `trace_dump_files_20260403.txt`

#### Sniff Flow
- **What to trace:** `hf sniff` / `lf sniff` PM3 commands
- **Key check:** Sniff starts, data captured, listing shown
- **Original reference:** `trace_sniff_flow_20260403.txt`

#### LUA Scripts Flow
- **What to trace:** Script listing, execution
- **Key check:** PM3 `script run` command sent
- **Original reference:** `trace_console_flow_20260401.txt`

#### Time Settings Flow
- **What to trace:** System date commands
- **Key check:** `date` command called, time updated
- **Original reference:** `trace_misc_flows_20260330.txt`

---

## 5. KNOWN ISSUES TO INVESTIGATE

### 5.1 connect2PM3() Bootstrap Gap

**Priority: CRITICAL**

`connect2PM3()` is never called during startup. The original firmware likely has this
call somewhere in its init sequence. Two possible fixes:

**Option A:** Add `connect2PM3()` call at end of `main.py:main()`, after RTM starts:
```python
# After rtm.startManager()
import time
time.sleep(2)  # Wait for RTM to be ready
import executor
executor.connect2PM3()
```

**Option B:** Add lazy init to `_send_and_cache()`:
```python
def _send_and_cache(cmd, timeout=5888):
    global _socket_instance
    if _socket_instance is None:
        connect2PM3()
    # ... rest of function
```

**Verify:** Check original firmware trace — does the first PM3 command succeed
immediately, or does it also fail-and-retry? The trace at line 5 shows
`PM3> hf 14a info` succeeds with `ret=1` and immediate response — no retry pattern
visible. This suggests the original firmware pre-connects.

### 5.2 Scan Pipeline Order

**Priority: MEDIUM**

The documented ground truth shows the original scan order is:
```
14a → LF search → (lf_wav_filter) → HF search → FeliCa → T55XX detect → EM4x05
```

Our reimplementation's order must be verified against the traces. Any order mismatch
can cause tag type misidentification.

### 5.3 Progress Callback Accuracy

**Priority: LOW** (cosmetic, not functional)

Current progress callbacks use fixed percentages (23, 33, 53...) called synchronously
before each pipeline stage. The original firmware likely uses similar fixed markers.
Verify via trace timing.

### 5.4 Toast Timing

**Priority: LOW** (cosmetic, not functional)

- "Tag found" toast: auto-dismisses after 2000ms (default)
- "Not found" toast: `duration_ms=0` (persists until key press)
- Verify these match original firmware behavior via framebuffer captures.

---

## 6. TOOLS AND COMMANDS

### 6.1 Trace Deployment (Application Instrumentation)

```bash
# One-command deploy + restart
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat > /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py << "PYEOF"
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

    import actstack, executor, scan

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
                r, (executor.CONTENT_OUT_IN__TXT_CACHE or "").replace("\n", "\\n")))
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
PYEOF'

# Restart app
sshpass -p 'fa' ssh -p 2222 root@localhost 'kill $(pgrep -f "python.*app.py" | head -1)'
sleep 30

# Verify
sshpass -p 'fa' ssh -p 2222 root@localhost 'head -5 /mnt/upan/full_trace.log'
```

### 6.2 Trace Retrieval

```bash
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat /mnt/upan/full_trace.log' \
  > docs/Real_Hardware_Intel/trace_oss_<flow>_$(date +%Y%m%d).txt
```

### 6.3 Cleanup (MANDATORY after every session)

```bash
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'rm -f /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py'
```

### 6.4 Framebuffer Capture (Separate Session)

```bash
# Deploy FB capture script (NEVER simultaneous with app tracer)
sshpass -p 'fa' ssh -p 2222 root@localhost 'mkdir -p /mnt/upan/fb_caps && while true; do
  cp /dev/fb1 /mnt/upan/fb_caps/$(date +%s%N).raw
  sleep 0.5
done' &

# Retrieve captures
sshpass -p 'fa' scp -P 2222 root@localhost:/mnt/upan/fb_caps/*.raw \
  docs/Real_Hardware_Intel/framebuffer_captures/oss_<flow>/
```

### 6.5 Hot-Deploy — Direct File Upload (Skip IPK Install)

Since we're running open-source Python, we can push modified files directly to the
device via SCP, skipping the full IPK build/install cycle. This dramatically shortens
the fix → test loop.

#### Device Application Layout

```
/home/pi/ipk_app_main/
├── app.py                     ← src/app.py
├── lib/                       ← src/lib/*.py AND src/middleware/*.py (both here)
│   ├── activity_main.py
│   ├── widget.py
│   ├── executor.py            ← src/middleware/executor.py
│   ├── scan.py                ← src/middleware/scan.py
│   ├── *.so                   ← kept original .so modules (non-replaced)
│   └── ...
├── main/                      ← src/main/*.py
│   ├── main.py
│   ├── rftask.py
│   └── install.py
├── screens/                   ← src/screens/*.json
├── pm3/                       ← proxmark3 binary + lua.zip
├── res/                       ← audio, font, img resources
└── data/
    └── conf.ini
```

**Key mapping:** `src/middleware/*.py` files go to `lib/` on device (NOT `middleware/`).
This is because `app.py` adds `lib` to `sys.path` — both UI and middleware modules live
in the same flat directory on device.

#### Step 1: Create Backup (MANDATORY — Do This ONCE Before Any Changes)

```bash
# Create a timestamped backup of the entire app directory
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'cp -a /home/pi/ipk_app_main /home/pi/ipk_app_main_BACKUP_$(date +%Y%m%d_%H%M%S)'

# Verify backup exists
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'ls -d /home/pi/ipk_app_main_BACKUP_* && echo "BACKUP OK"'

# Also pull a local copy for safety
mkdir -p backups/device_$(date +%Y%m%d)
sshpass -p 'fa' scp -r -P 2222 root@localhost:/home/pi/ipk_app_main/ \
  backups/device_$(date +%Y%m%d)/
```

**RULE:** Never modify the device without a backup. If things go wrong, restore with:
```bash
# RESTORE from device-side backup
sshpass -p 'fa' ssh -p 2222 root@localhost '
  BACKUP=$(ls -d /home/pi/ipk_app_main_BACKUP_* | tail -1)
  if [ -n "$BACKUP" ]; then
    rm -rf /home/pi/ipk_app_main
    cp -a "$BACKUP" /home/pi/ipk_app_main
    kill $(pgrep -f "python.*app.py" | head -1)
    echo "RESTORED from $BACKUP — app restarting"
  else
    echo "ERROR: No backup found!"
  fi
'
```

#### Step 2: Push Modified Files

```bash
# Single middleware file (e.g., fixed executor.py)
sshpass -p 'fa' scp -P 2222 \
  src/middleware/executor.py \
  root@localhost:/home/pi/ipk_app_main/lib/executor.py

# Single lib file (e.g., fixed activity_main.py)
sshpass -p 'fa' scp -P 2222 \
  src/lib/activity_main.py \
  root@localhost:/home/pi/ipk_app_main/lib/activity_main.py

# Single main file (e.g., fixed main.py)
sshpass -p 'fa' scp -P 2222 \
  src/main/main.py \
  root@localhost:/home/pi/ipk_app_main/main/main.py

# Bulk push all middleware + lib (use with care)
sshpass -p 'fa' scp -P 2222 \
  src/middleware/*.py src/lib/*.py \
  root@localhost:/home/pi/ipk_app_main/lib/

# Bulk push main modules
sshpass -p 'fa' scp -P 2222 \
  src/main/*.py \
  root@localhost:/home/pi/ipk_app_main/main/
```

#### Step 3: Restart App

```bash
# Kill the app — the system watchdog auto-relaunches it
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'kill $(pgrep -f "python.*app.py" | head -1)'

# Wait for restart
sleep 10

# Verify it's running
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'pgrep -fa "python.*app.py" && echo "APP RUNNING"'
```

#### One-Liner: Fix → Push → Restart → Verify

```bash
# Example: push fixed executor.py, restart, verify in one command
sshpass -p 'fa' scp -P 2222 src/middleware/executor.py root@localhost:/home/pi/ipk_app_main/lib/executor.py && \
sshpass -p 'fa' ssh -p 2222 root@localhost 'kill $(pgrep -f "python.*app.py" | head -1)' && \
sleep 10 && \
sshpass -p 'fa' ssh -p 2222 root@localhost 'pgrep -fa "python.*app.py" && echo "READY"'
```

#### Post-Audit Cleanup: Restore Clean System

After all testing is complete, restore the device to the pre-audit state:

```bash
# Restore from the first backup taken
sshpass -p 'fa' ssh -p 2222 root@localhost '
  BACKUP=$(ls -d /home/pi/ipk_app_main_BACKUP_* | head -1)
  rm -rf /home/pi/ipk_app_main
  cp -a "$BACKUP" /home/pi/ipk_app_main
  kill $(pgrep -f "python.*app.py" | head -1)
  echo "RESTORED to clean pre-audit state"
'

# Optionally remove all backups
sshpass -p 'fa' ssh -p 2222 root@localhost \
  'rm -rf /home/pi/ipk_app_main_BACKUP_*'
```

### 6.6 Enhanced Tracer — Socket State Monitoring

For diagnosing connect2PM3 issues, use this enhanced tracer that also logs socket state:

```python
# Additional patch for executor socket monitoring
_orig_connect = executor.connect2PM3
def _traced_connect(*a, **kw):
    lg("CONNECT> connect2PM3(%s, %s)" % (a, kw))
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
```

---

## 7. EXECUTION PLAN

### Step 0: Create Device Backup (Agent — ONCE, Before Anything Else)

1. SSH to device
2. Create timestamped backup of `/home/pi/ipk_app_main/` (see Section 6.5 Step 1)
3. Pull local copy to `backups/device_YYYYMMDD/`
4. Verify backup integrity
5. **Do NOT proceed until backup is confirmed**

### Step 1: Pre-Flight (Agent — No User Action)

1. SSH to device
2. Run all diagnostics from Section 4 Phase 1
3. Record results
4. Identify any infrastructure issues (PM3 not running, RTM not listening, etc.)
5. Fix infrastructure issues before proceeding

### Step 2: Deploy Instrumentation (Agent)

1. Deploy enhanced tracer (standard + socket monitoring from 6.5)
2. Restart app
3. Verify tracer is active
4. Confirm to user: "Device is instrumented. Please perform a Scan with a tag."

### Step 3: User Performs Scan

**User action required:**
1. Navigate to Main Menu → Scan
2. Place a known MIFARE Classic 1K tag on the reader
3. Wait for result (or timeout)
4. Report what you see on screen
5. Press PWR to exit back to main menu

### Step 4: Retrieve and Analyze Trace (Agent)

1. Pull trace from device
2. Save to `docs/Real_Hardware_Intel/trace_oss_scan_YYYYMMDD.txt`
3. Compare line-by-line against `trace_scan_flow_20260331.txt`
4. Produce diagnostic report:
   - Were PM3 commands sent?
   - Did they get responses?
   - Was scan cache populated?
   - What was the timing?
   - Where did it diverge from original?

### Step 5: Root-Cause and Fix (Agent)

1. Based on trace analysis, identify root cause
2. Propose fix with ground-truth justification
3. Implement fix locally (edit `src/` files)
4. Hot-deploy modified files to device via SCP (Section 6.5 Step 2)
5. Restart app (Section 6.5 Step 3)
6. Re-deploy tracer and re-test

### Step 6: Iterate Through Remaining Flows

Repeat Steps 2-5 for each flow in order (Section 3.1 table).

### Step 7: Regression Testing

After all flows are verified on real device:
1. Run full QEMU test suite (`tests/flows/run_all_flows.sh`) to ensure no regressions
2. Run IPK release gates (`tools/test_ipk_release.py`)
3. Final real-device smoke test of all flows

---

## 8. COMPARISON CHECKLIST (Per Flow)

For each flow, this checklist must be completed:

```
Flow: _______________
Date: _______________
OSS Trace: docs/Real_Hardware_Intel/trace_oss_<flow>_YYYYMMDD.txt
Original Trace: docs/Real_Hardware_Intel/<original_trace>.txt

PRE-FLIGHT
[ ] PM3 subprocess running
[ ] RTM listening on 8888
[ ] /dev/ttyACM0 exists
[ ] DRM serial correct

PM3 COMMUNICATION
[ ] PM3 commands appear in trace (PM3> lines)
[ ] PM3 responses are non-empty (PM3< ret=1 with data)
[ ] Command sequence matches original
[ ] Command timeouts match original
[ ] No spurious reworkPM3All() calls

FUNCTIONAL
[ ] Correct tag type detected
[ ] Correct UID extracted
[ ] Scan cache populated correctly
[ ] Activity transitions match original
[ ] Result callback fired correctly

UI
[ ] Progress bar updates visible
[ ] Correct toast shown for result
[ ] Toast timing matches original
[ ] Screen content matches original framebuffer captures

TIMING
[ ] Total flow duration within 2x of original
[ ] No instant completion (sign of silent failure)
[ ] No excessive delays (sign of retry loops)
```

---

## 9. GROUND-TRUTH REFERENCE TABLE

| Resource | Path | Content |
|----------|------|---------|
| Original scan trace (HF) | `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` | MFC1K, NTAG, ISO15693, Indala, FDX-B scans |
| Original scan trace (LF) | `docs/Real_Hardware_Intel/trace_lf_scan_flow_20260331.txt` | 15 LF badge types |
| Original scan trace (iCLASS) | `docs/Real_Hardware_Intel/trace_iclass_scan_20260331.txt` | iCLASS with key recovery |
| Original read/write trace | `docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt` | MFC 1K complete pipeline |
| Original erase trace | `docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt` | Multiple tag types |
| Original autocopy trace | `docs/Real_Hardware_Intel/trace_autocopy_mf1k_standard.txt` | MFC 1K standard auto-copy |
| Original sniff trace | `docs/Real_Hardware_Intel/trace_sniff_flow_20260403.txt` | HF/LF sniff |
| Original dump files trace | `docs/Real_Hardware_Intel/trace_dump_files_20260403.txt` | File listing + write from dump |
| Scan command sequences | `docs/Real_Hardware_Intel/V1090_SCAN_COMMAND_TRACES.md` | Per-tag PM3 command sequences |
| Module API reference | `docs/V1090_MODULE_AUDIT.txt` | All .so module signatures |
| Module strings | `docs/V1090_SO_STRINGS_RAW.txt` | All .so string tables |

---

## 10. SUCCESS CRITERIA

The audit is complete when ALL of the following are true:

1. **Every flow** in Section 3.1 has been tested on the real device with traces
2. **Every trace** shows PM3 commands being sent and receiving real responses
3. **Scan** correctly detects at least: MFC 1K, MFC 4K, NTAG, LF (T55XX, EM410x, HID)
4. **Read** correctly reads full tag data for detected tags
5. **Write** correctly writes dump data to target tags
6. **Auto-Copy** completes full scan→read→write→verify pipeline
7. **No silent failures** — every PM3 command that should succeed does succeed
8. **Timing** is within 2x of original firmware for equivalent operations
9. **QEMU test suite** still passes 402/402 (no regressions)
10. **IPK release gates** pass all 33 checks

---

## 11. LAWS (Inherited from Project)

1. **Tests are immutable.** NEVER edit test files.
2. **The .so middleware IS the logic.** Ground-truth source only.
3. **Never guess.** Every fix must cite trace evidence.
4. **Never flash PM3 bootrom.** No JTAG = bricked device.
5. **Only ground-truth resources.** No invented responses.
6. **DEBUG and TRACE** — we have full instrumentation. Never need to guess.
7. **Clean up tracer** after every session. Left-behind sitecustomize.py crashes the app.
8. **NEVER access ~/.ssh on any device.**
9. **NEVER run strace + framebuffer simultaneously.** Resource contention crashes the app.
10. **Always smoke-test DRM first** when .so modules fail silently.
11. **Always back up before modifying device files.** Create a backup of `/home/pi/ipk_app_main/` before the first hot-deploy. Restore to clean state after audit is complete.
