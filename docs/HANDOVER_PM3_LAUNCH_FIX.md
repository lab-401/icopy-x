# HANDOVER: PM3 Subprocess Launch Failure on Real Device

**Date:** 2026-04-10
**Status:** BLOCKED — PM3 fails USB-CDC handshake when launched from app process
**Priority:** CRITICAL — blocks all RFID functionality

---

## 1. THE PROBLEM

The PM3 (proxmark3) binary **successfully connects to hardware when launched from SSH**
but **fails when launched as a child of the Python app process** via the systemd service.

### Consistent failure output (from `/mnt/upan/pm3_startup_debug.log`):
```
PM3 launched: pid=XXXX cmd=/home/pi/ipk_app_main/pm3/proxmark3 /dev/ttyACM0 -w --flush
STDOUT: [=] Output will be flushed after every print.
STDOUT: [+] loaded from JSON file /home/pi/.proxmark3/preferences.json
STDOUT: [+] Waiting for Proxmark3 to appear on /dev/ttyACM0
STDOUT: [\] 20[|] 19[=] Communicating with PM3 over USB-CDC
STDOUT: [!] Communicating with Proxmark3 device failed
```

### Successful manual launch (from SSH, same binary, same args):
```
[=] Output will be flushed after every print.
[+] loaded from JSON file /root/.proxmark3/preferences.json
[+] Waiting for Proxmark3 to appear on /dev/ttyACM0
[\] 20[|] 19[=] Communicating with PM3 over USB-CDC
[!!] STDIN unexpected end, exit...     ← connected, exited only because stdin closed
```

### Key fact: PM3 finds the USB device in BOTH cases
It counts down from 20, finds the device at 19, opens USB-CDC.
The **protocol handshake** after USB-CDC is established is what fails.

---

## 2. WHAT HAS BEEN TRIED (ALL FAILED)

| Approach | Result | Why it failed |
|----------|--------|--------------|
| `sudo -s /path/proxmark3 ...` (original string) | `ERROR: cannot communicate with the Proxmark` | `sudo -s` creates bash shell; PM3 times out entirely (doesn't even open USB) |
| Direct binary (no sudo) | `Communicating with Proxmark3 device failed` | Opens USB-CDC but handshake fails |
| `sudo` without `-s` | Same as direct binary | Same failure |
| `start_new_session=True` | Same failure | |
| `start_new_session=False` | Same failure | |
| `shell=True` | Same failure | |
| `preexec_fn` with signal resets | Same failure | |
| USB device reset before launch | Same failure | |
| All combinations of the above | Same failure | |

**The ONLY configuration that works:** launching PM3 from a **separate process tree**
(via SSH) — not as a child of the Python app process.

---

## 3. WHAT HAS BEEN CONFIRMED

1. **PM3 binary works** — `proxmark3 --version` returns `RRG/Iceman/master/385d892-dirty-unclean 2022-08-16`
2. **USB device exists** — `/dev/ttyACM0` (166,0), `crw-rw---- root dialout`
3. **DRM serial correct** — `02c000814dfb3aeb`
4. **RTM TCP server works** — port 8888 listens, responds to Nikola protocol
5. **Original firmware works** — `ipk_app_DISABLED/` (renamed from `ipk_app_bak`) has compiled `rftask.so` + `main.so` that launch PM3 successfully with `sudo -s`
6. **Preferences identical** — `/root/.proxmark3/preferences.json` == `/home/pi/.proxmark3/preferences.json`
7. **App FDs clean** — app has no USB/ACM file descriptors open (fd 9 → /dev/ttyS0 for HMI only)
8. **No strace on device** — `strace` is not installed

---

## 4. WHAT HAS NOT BEEN DONE (GROUND-TRUTH APPROACH)

**The original firmware at `ipk_app_DISABLED/` successfully launches PM3.**
That directory contains the compiled Cython `.so` files (`rftask.so`, `main.so`).

### The correct diagnostic approach:

1. **Temporarily restore the original firmware:**
   ```bash
   ssh root@device 'sudo systemctl stop icopy; killall -9 proxmark3 2>/dev/null
   mv /home/pi/ipk_app_DISABLED /home/pi/ipk_app_bak
   sudo systemctl start icopy'
   ```

2. **Wait for PM3 to connect** (it will — the original .so works)

3. **Compare the PM3 process state vs our version:**
   ```bash
   # Original firmware's PM3:
   pm3pid=$(pgrep -x proxmark3)
   ls -la /proc/$pm3pid/fd/                    # What FDs does it have?
   cat /proc/$pm3pid/status                    # Threads, state, signals?
   cat /proc/$pm3pid/environ | tr '\0' '\n'    # Environment?
   cat /proc/$pm3pid/cmdline | tr '\0' ' '     # Exact command line?
   cat /proc/$pm3pid/maps | head -30           # Memory maps?
   ```

4. **Check the parent process chain:**
   ```bash
   # How does the original rftask.so structure the process tree?
   pstree -p $(pgrep -f "python.*app.py")
   ```

5. **Install strace and trace the original PM3 launch:**
   ```bash
   apt-get install strace
   # Then restart the service with strace on the app:
   # Wrap the app launch with strace to see the exact fork/exec sequence
   ```

6. **Compare the exact `open()` / `ioctl()` calls** on `/dev/ttyACM0` between
   the original (working) and our version (failing). The handshake failure is
   at the USB-CDC protocol level — the `ioctl()` parameters or sequence likely differ.

### Alternative: use the original `rftask.so` directly

Since `rftask.so` is a Cython module that exports the `RemoteTaskManager` class,
our `main.py` could potentially `import` the original `.so` instead of our `.py`:
```python
# In main.py, temporarily:
sys.path.insert(0, '/home/pi/ipk_app_DISABLED/main/')
import rftask  # loads the original .so
```
This would confirm whether the issue is in our rftask.py or in main.py's startup.

---

## 5. CURRENT STATE OF FILES ON DEVICE

### Device directory structure:
```
/home/pi/
├── ipk_app_main/              ← OUR firmware (currently deployed, PM3 broken)
│   ├── app.py
│   ├── main/
│   │   ├── main.py            ← MODIFIED (no sudo -s, connect2PM3 added)
│   │   └── rftask.py          ← MODIFIED (debug logging, various Popen attempts)
│   ├── lib/                   ← middleware + UI .py files
│   ├── pm3/proxmark3          ← PM3 binary (works fine standalone)
│   └── ...
├── ipk_app_DISABLED/          ← ORIGINAL firmware (renamed from ipk_app_bak)
│   ├── main/
│   │   ├── main.so            ← Original compiled Cython
│   │   └── rftask.so          ← Original compiled Cython (LAUNCHES PM3 SUCCESSFULLY)
│   ├── lib/*.so               ← 62 original compiled .so modules
│   └── ...
├── ipk_app_main_BACKUP_20260410_112105/  ← Pre-audit backup of our firmware
└── (no ipk_app_bak — renamed to DISABLED to prevent starter fallback)
```

### Local backup:
```
/home/qx/icopy-x-reimpl/backups/device_20260410/  ← Full copy of ipk_app_main
```

### Current dirty state of modified files:

**`src/main/main.py`** — Changes from original reimplementation:
- Line 58: `killall` without `-w` flag (prevents zombie hang)
- Line 69: `pm3_cmd` without `sudo -s` (direct binary invocation)
- Line 70: `pm3_kill_cmd` without `-w` flag
- Lines 88-100: Added `connect2PM3()` call after RTM startup
- Comments updated throughout

**`src/main/rftask.py`** — Changes from original reimplementation:
- Lines 342-357: `_create_subprocess()` — currently has `sudo` prefix + `start_new_session=True` (latest untested iteration). NEEDS CLEANUP.
- Lines 360-366: Debug file logging in `_create_subprocess` (TEMPORARY — remove after fix)
- Lines 372-399: `_destroy_subprocess()` — always-reap fix (KEEP)
- Lines 449-454: Debug file logging in `_run_std_output_error` (TEMPORARY — remove)
- Lines 485-490: Debug file logging in `_read_stderr` (TEMPORARY — remove)

---

## 6. DEVICE ACCESS

```bash
# SSH access
sshpass -p 'fa' ssh -p 2222 root@localhost

# Deploy a file
sshpass -p 'fa' scp -P 2222 src/main/rftask.py root@localhost:/home/pi/ipk_app_main/main/rftask.py

# Restart service
sshpass -p 'fa' ssh -p 2222 root@localhost 'sudo systemctl restart icopy'

# NOTE: killing the app causes the starter to restart it. If ipk_app_bak exists,
# the starter falls back to it on non-zero exit. That's why ipk_app_bak was
# renamed to ipk_app_DISABLED.
```

---

## 7. GROUND-TRUTH RESOURCES

| Resource | Path | Use |
|----------|------|-----|
| Original rftask.so binary | `orig_so/main/rftask.so` | Decompile/analyze subprocess creation |
| Original main.so binary | `orig_so/main/main.so` | Decompile/analyze PM3 cmd construction |
| Original rftask.so on device | `/home/pi/ipk_app_DISABLED/main/rftask.so` | Run it to trace working behavior |
| Original main.so on device | `/home/pi/ipk_app_DISABLED/main/main.so` | Run it to trace working behavior |
| Decompiled summary | `decompiled/SUMMARY.md` | Binary analysis reference |
| String extractions | `docs/v1090_strings/` | Binary string tables |
| Module audit | `docs/V1090_MODULE_AUDIT.txt` | All .so module signatures |
| Original scan trace | `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` | Working PM3 command/response sequence |
| PM3 binary version | `RRG/Iceman/master/385d892-dirty-unclean 2022-08-16` | On device at `pm3/proxmark3` |

---

## 8. RULES

1. **Only use ground-truth resources.** No guessing. No "let me try this."
2. **The original .so IS the source of truth.** If it works, study HOW it works.
3. **Trace, don't guess.** Install strace if needed. Use GDB if needed. Compare process state.
4. **Tests are immutable.** Never edit test files.
5. **Never flash PM3 bootrom.** No JTAG = bricked device.
6. **Never access ~/.ssh on any device.**
7. **Backup exists** at `/home/pi/ipk_app_main_BACKUP_20260410_112105` — restore if needed.
8. **Remove debug logging** from rftask.py when the fix is found (lines 360-366, 449-454, 485-490).

---

## 9. TASK FOR NEXT AGENT

1. Use ground-truth methods (Section 4) to determine exactly why the original
   `rftask.so` successfully launches PM3 but our `rftask.py` does not.
2. The difference is in the subprocess creation or process environment — the
   PM3 binary itself is identical in both cases.
3. Apply the fix to `src/main/rftask.py` based on ground-truth findings.
4. Remove all temporary debug logging.
5. Verify PM3 connects on real device.
6. Then proceed with the scan flow audit per `docs/HOW-TO-Real-Device - OSS Audit.md`.
