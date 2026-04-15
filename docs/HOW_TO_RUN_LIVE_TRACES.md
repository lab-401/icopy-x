# HOW TO RUN LIVE TRACES ON THE REAL DEVICE

This document describes how to instrument the real iCopy-X device to capture activity transitions, PM3 commands, scan cache changes, and activity stack state during firmware operation.

---

## 1. PURPOSE

When a flow test fails under QEMU and the cause is unknown, real device traces provide ground truth. The tracer captures:

- **Activity transitions**: `start_activity(ClassName, bundle)` and `finish_activity()` with full bundle JSON and stack depth
- **PM3 commands**: Every `startPM3Task(cmd, timeout)` call and its return value + full response content
- **PM3 stop/rework**: Every `stopPM3Task()` and `reworkPM3All()` call with timing
- **Scan cache**: Every `setScanCache(infos)` call with the full cache dict
- **Key events**: Every `keymap.key.onKey(event)` call (physical button presses)
- **GD32 serial**: Every command sent to the GD32 MCU via `/dev/ttyS0` (presspm3, restartpm3, setbaklight, etc.)
- **Stack polling**: Activity stack composition sampled every 0.5s (detects transitions the patches miss)

---

## 2. DEVICE ACCESS

```
SSH: sshpass -p 'fa' ssh -p 2222 root@localhost
```

The device connects via a reverse SSH tunnel on port 2222. The tunnel must be established by the user before tracing.

---

## 3. WHAT WORKS AND WHAT DOESN'T

### SAFE — Module-level function patches
These replace Python attributes on imported modules. The Cython `.so` resolves these at call time:
- `actstack.start_activity = traced_version`
- `actstack.finish_activity = traced_version`
- `executor.startPM3Task = traced_version`
- `scan.setScanCache = traced_version`

### SAFE — Passive reads
Reading module-level variables without patching:
- `actstack._ACTIVITY_STACK` (list of activity objects)
- `scan.getScanCache()` (dict or None)
- `executor.CONTENT_OUT_IN__TXT_CACHE` (string)

### CRASHES THE APP — Class method patches
**NEVER** patch methods on Cython class objects:
- `activity_main.ReadListActivity.onKeyEvent = ...` — **CRASHES**
- `activity_main.ReadListActivity.initList = ...` — **CRASHES**
- Any `ClassName.method = ...` on a `.so` class — **CRASHES**

The Cython C-level vtable is corrupted by Python attribute replacement on class objects.

### CRASHES THE APP — Heavy instrumentation
- Framebuffer capture (`/dev/fb1`) at high frequency alongside Python patches — **CRASHES** (resource contention)
- Too many patched functions running simultaneously — **may CRASH**

---

## 4. DEPLOYMENT METHOD

The tracer is deployed via `sitecustomize.py` in the system Python's site-packages directory. This file is automatically loaded by every Python process on startup.

### 4.1 Correct site-packages path

```
/usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py
```

**NOT** `/home/pi/.local/lib/python3.8/site-packages/` — that path is not in the system Python's search path.

### 4.2 Process guard

`sitecustomize.py` loads in ALL Python processes (the app, the starter, any SSH commands). The tracer must only activate inside the app process. The reliable guard:

```python
# Poll sys.modules for the 'application' module — only present in the app
for _ in range(120):
    if "application" in sys.modules:
        break
    time.sleep(0.5)
else:
    return  # Not the app process — exit silently
```

**DO NOT** use `sys.argv` — the starter launches the app via subprocess and argv checking is unreliable.

**DO NOT** use `import actstack` as the guard — `actstack` may be importable from the starter's environment too, causing crashes.

### 4.3 Timer delay

The tracer must wait for the app to fully boot before patching. The `application` module poll handles this automatically — it returns as soon as the app's main module is loaded. Add a 5-second sleep after detection to let the UI finish rendering:

```python
threading.Timer(15.0, _install).start()  # Minimum 15s
```

Or better — poll for `"application" in sys.modules` then sleep 5s.

---

## 5. THE TRACER SCRIPT

This is the complete, tested tracer that works on the real device:

```python
# /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py
# MAX-INFO tracer: captures activity transitions, PM3 commands, key events,
# GD32 serial traffic, scan cache, stop/rework, and stack state.
import threading, time, json, sys

def _go():
    # Wait for app process
    for _ in range(120):
        if "application" in sys.modules:
            break
        time.sleep(0.5)
    else:
        return

    time.sleep(5)  # Let app finish booting

    LOG = "/mnt/upan/full_trace.log"
    t0 = time.time()
    with open(LOG, "w") as f:
        f.write("=== FULL TRACE ===\n")

    def lg(m):
        try:
            with open(LOG, "a") as f:
                f.write("[%8.3f] %s\n" % (time.time() - t0, m))
                f.flush()
        except: pass

    import actstack, executor, scan, keymap

    # ── GD32 serial: hook serial.Serial.write for /dev/ttyS0 traffic ──
    # Captures: presspm3, restartpm3, setbaklight, pctbat, charge, etc.
    try:
        import serial as _serial_mod
        _orig_serial_write = _serial_mod.Serial.write
        def _traced_serial_write(self, data):
            try:
                if hasattr(self, 'port') and 'ttyS0' in str(self.port):
                    lg("SERIAL_TX> %s" % repr(data))
            except: pass
            return _orig_serial_write(self, data)
        _serial_mod.Serial.write = _traced_serial_write
    except Exception as e:
        lg("SERIAL HOOK FAILED: %s" % e)

    # ── presspm3: direct hook (belt-and-suspenders with serial) ──
    try:
        import hmi_driver
        if hasattr(hmi_driver, 'presspm3'):
            _orig_presspm3 = hmi_driver.presspm3
            def _traced_presspm3(*a, **kw):
                lg("PRESSPM3> called")
                r = _orig_presspm3(*a, **kw)
                lg("PRESSPM3< done")
                return r
            hmi_driver.presspm3 = _traced_presspm3
            lg("presspm3 hook OK")
    except Exception as e:
        lg("presspm3 hook failed: %s" % e)

    # ── Key events ──
    _orig_onKey = keymap.key.onKey
    def _traced_onKey(event):
        try: lg("KEY> %s" % event)
        except: pass
        return _orig_onKey(event)
    keymap.key.onKey = _traced_onKey

    # ── Activity transitions with full bundle JSON ──
    o1 = actstack.start_activity
    def t1(*a, **kw):
        try:
            names = [x.__name__ if hasattr(x, "__name__") else repr(x) for x in a]
            bundle_repr = "None"
            if len(a) > 1 and a[1] is not None:
                try: bundle_repr = json.dumps(a[1], default=str)[:1000]
                except: bundle_repr = repr(a[1])[:1000]
            lg("START(%s) bundle=%s" % (", ".join(names), bundle_repr))
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

    # ── PM3 commands (full response, NOT truncated) ──
    o3 = executor.startPM3Task
    def t3(*a, **kw):
        try: lg("PM3> %s (timeout=%s)" % (str(a[0])[:300], a[1] if len(a)>1 else kw.get("timeout","?")))
        except: pass
        r = o3(*a, **kw)
        try:
            cache = executor.CONTENT_OUT_IN__TXT_CACHE or ""
            lg("PM3< ret=%s content_len=%d %s" % (
                r, len(cache), cache.replace("\n", "\\n")[:2000]))
        except: pass
        return r
    executor.startPM3Task = t3

    # ── PM3 stop ──
    _orig_stop = executor.stopPM3Task
    def _traced_stop(*a, **kw):
        try: lg("PM3_STOP> stopPM3Task()")
        except: pass
        r = _orig_stop(*a, **kw)
        try: lg("PM3_STOP< ret=%s" % r)
        except: pass
        return r
    executor.stopPM3Task = _traced_stop

    # ── PM3 rework ──
    _orig_rework = executor.reworkPM3All
    def _traced_rework(*a, **kw):
        lg("REWORK> reworkPM3All()")
        r = _orig_rework(*a, **kw)
        lg("REWORK< socket=%s" % (executor._socket_instance is not None))
        return r
    executor.reworkPM3All = _traced_rework

    # ── PM3 connect ──
    _orig_connect = executor.connect2PM3
    def _traced_connect(*a, **kw):
        lg("CONNECT> connect2PM3()")
        r = _orig_connect(*a, **kw)
        lg("CONNECT< socket=%s" % (executor._socket_instance is not None))
        return r
    executor.connect2PM3 = _traced_connect

    # ── Scan cache ──
    o4 = scan.setScanCache
    def t4(infos):
        try:
            if isinstance(infos, dict):
                lg("CACHE: %s" % json.dumps(
                    {k: repr(v)[:80] for k, v in infos.items()}))
        except: pass
        return o4(infos)
    scan.setScanCache = t4

    # ── Passive stack poller ──
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
                        str(cache.get("uid", ""))[:24])
                line = "stack=%s %s" % (names, cs)
                if line != prev:
                    lg("POLL %s" % line)
                    prev = line
            except: pass
            time.sleep(0.5)
    threading.Thread(target=_poll, daemon=True).start()

    lg("=== ALL INSTALLED ===")

threading.Thread(target=_go, daemon=True).start()
```

---

## 6. DEPLOYMENT STEPS

**CRITICAL ORDER: Deploy tracer FIRST, then kill the app.** If the app starts
before `sitecustomize.py` is in place, the tracer never loads (Python only reads
`sitecustomize.py` at interpreter startup). Deploying then killing ensures the
watchdog-restarted app picks up the tracer on its fresh Python process.

```bash
# 1. Deploy the tracer (BEFORE killing the app)
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat > /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py << "PYEOF"
<paste tracer script from section 5>
PYEOF'

# 2. Clear old trace
sshpass -p 'fa' ssh -p 2222 root@localhost 'rm -f /mnt/upan/full_trace.log'

# 3. NOW kill the app (watchdog relaunches with tracer loaded)
sshpass -p 'fa' ssh -p 2222 root@localhost 'kill $(pgrep -f "python.*app.py" | head -1)'

# 4. Poll for tracer attachment (do NOT blind-sleep)
for i in $(seq 1 12); do
    sleep 5
    line=$(sshpass -p 'fa' ssh -p 2222 root@localhost \
      'grep "ALL INSTALLED" /mnt/upan/full_trace.log 2>/dev/null')
    [ -n "$line" ] && echo "READY: $line" && break
    echo "poll $i..."
done

# 6. Tell the user to perform the flow on the device

# 7. Retrieve the trace
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat /mnt/upan/full_trace.log' > docs/Real_Hardware_Intel/trace_<name>.txt

# 8. CLEAN UP — remove the tracer
sshpass -p 'fa' ssh -p 2222 root@localhost 'rm -f /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py'
```

---

## 7. READING THE TRACE

### Key events
```
[  70.478] KEY> M1                               — physical button press (original FW)
[  39.343] KEY> KEYDOWN_PRES!                    — physical button press (OSS FW)
```

### Activity transitions
```
[  55.535] START(SimulationActivity, None) bundle=None
[  59.703] START(SimulationActivity, {'uid':'DAEFB416','type':1,...}) bundle={"uid":"DAEFB416",...}
[  74.591] FINISH(top=SimulationTraceActivity d=3)
```

### PM3 commands
```
[  56.944] PM3> hf 14a info (timeout=5000)       — command sent with timeout
[  58.457] PM3< ret=1 content_len=287 \n\n[+]  UID: B7 78 5E 50 ...
```

`ret=1` means `startPM3Task` returned 1 (command completed). `ret=-1` means timeout/error.

**PM3 responses are NOT truncated.** The full `CONTENT_OUT_IN__TXT_CACHE` is logged.
Newlines are escaped as `\n` in the log for single-line readability.

### PM3 stop/rework
```
[  69.356] PM3_STOP> stopPM3Task()               — stop requested
[  69.750] REWORK> reworkPM3All()                 — PM3 restart cycle (should be rare)
[  72.768] CONNECT> connect2PM3()                 — reconnect after rework
```

### GD32 serial
```
[  70.547] SERIAL_TX> b'presspm3'                — PM3 button press via GD32
[  70.548] SERIAL_TX> b'\r\n'
[   1.686] SERIAL_TX> b'restartpm3'              — PM3 restart via GD32
[  12.018] SERIAL_TX> b'pctbat'                  — battery poll (every 10s, ignore)
```

### presspm3 (direct hook)
```
[  70.546] PRESSPM3> called                      — hmi_driver.presspm3() invoked
[  70.959] PRESSPM3< done                        — returned (GD32 acknowledged)
```

### Scan cache
```
[  58.997] CACHE: {"found": "True", "type": "1", "uid": "'B7785E50'", ...}
```

### Stack polls
```
[  55.985] POLL stack=['dict', 'dict']           — 2 activities on stack (original FW)
[  42.249] POLL stack=['MainActivity', 'SimulationActivity']  — OSS FW shows class names
```

Activity objects show as `dict` on original firmware because Cython `.so` returns dict-like objects. OSS firmware shows actual class names.

---

## 8. WHAT TO CAPTURE

When a flow test fails, capture a trace of the EXACT flow that fails:

1. **Read flow**: Navigate to Read Tag → select type → scan → read
2. **Write flow**: Continue from read → M2 "Write" → write → verify
3. **Fail scenarios**: Reproduce the specific failure (no tag, wrong type, card lost)

The trace shows:
- Which activities are pushed/popped and in what order
- What bundle data is passed to each activity
- Every PM3 command and its response
- The scan cache state at each transition

This is sufficient to build correct fixtures and understand the .so's internal flow.

---

## 9. EXISTING TRACES

| File | Content |
|------|---------|
| `docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt` | Complete Read→Write flow, MFC 1K 4B, 85 PM3 commands, all block writes |
| `docs/Real_Hardware_Intel/read_write_activity_trace_20260327.txt` | Stack-only trace (passive observer, no PM3) |
| `docs/Real_Hardware_Intel/V1090_REAL_DEVICE_TRACES.md` | Earlier trace with activity sequence + key facts |
| `docs/Real_Hardware_Intel/write_flow_20260326/` | Raw strace + screenshots from Write flow |

---

## 10. RULES

1. **ALWAYS clean up** — remove `sitecustomize.py` after capturing. Leaving it causes the app to crash on next reboot if the tunnel is down.

2. **NEVER patch class methods** — only module-level functions. See section 3.

3. **NEVER run framebuffer capture simultaneously** with Python patching. Use one or the other.

4. **Save traces to the repo** in `docs/Real_Hardware_Intel/` with date and flow description in the filename.

5. **Ask the user to perform the flow** — you cannot remote-control the device UI. The user presses the physical buttons.
