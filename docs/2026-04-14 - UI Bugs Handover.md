# UI Bugs & Pipeline Cleanup — Session Handover (2026-04-14, Session 2)

## Branch: `working/compatibility-layer`
## Previous handover: `docs/2026-04-14 - Compat Layer Handover.md`

---

## What Was Done This Session

### 1. PM3 Pipeline Cleanup Mechanism (IMPLEMENTED, DEVICE-VERIFIED)

**Problem:** When a PM3 command is interrupted (user presses PWR during fchk/scan), stale response data remains in the TCP socket buffer. Subsequent commands receive wrong data.

**Solution — two-layer escalation system:**

#### executor.py (`src/middleware/executor.py`)
- Added `_pipeline_needs_cleanup` flag — set when `_send_and_cache` breaks its recv loop due to STOPPING
- Added `_ensure_pipeline_ready()` — closes stale TCP socket and reconnects. Called at the top of `startPM3Task()`, NOT during activity exit (avoids Tk thread blocking)
- The reconnect discards all stale TCP data and gets a fresh HandleServer thread in rftask.py

#### rftask.py (`src/main/rftask.py`)
- Added `_cmd_lock` (threading.Lock) to `RemoteTaskManager` — serializes `_send_cmd` access across concurrent HandleServer threads
- `_send_cmd` acquires lock with **3-second timeout** — if the previous command is still in flight (PM3 stuck), returns None which triggers `_request_task_cmd`'s auto-recovery → `reworkManager()` → `restartpm3` via GD32
- `_destroy_subprocess` sets `_output_event` — unblocks any `_send_cmd` waiting on the old process
- Reader thread exit (`_run_std_output_error`) sets `_output_event` — same unblock on EOF/shutdown

**Device verification trace:** `docs/Real_Hardware_Intel/trace_iceman_pwr_fix_verify_20260414.txt`
- Pipeline cleanup fires: `CONNECT> connect2PM3()` after interrupted fchk
- Subsequent scan succeeds with clean responses

**Tests:** `tests/ui/test_pipeline_cleanup.py` — 16 tests, all passing

### 2. PWR Key Fix for Scan/Read/AutoCopy Activities (IMPLEMENTED, DEVICE-VERIFIED)

**Problem:** PWR key was completely swallowed during busy states (scanning, reading, fchk) in AutoCopyActivity, ScanActivity, and ReadActivity. Root cause: `_handlePWR()` in BaseActivity checks `_is_busy` and returns True (swallowing the key). The Ghidra decompilation comment says the OPPOSITE: "isbusy() — if True, only PWR works (finish)".

**Fix:** PWR handler moved BEFORE the busy-state check in three activities. PWR now calls `presspm3()` + `stopPM3Task()` + `finish()` even during busy operations.

**Files changed:**
- `src/lib/activity_main.py` — AutoCopyActivity.onKeyEvent, ScanActivity.onKeyEvent
- `src/lib/activity_read.py` — ReadActivity.onKeyEvent

**Device verification:**
- PWR during `hf 14a info`: exits in ~1.5s
- PWR during `hf mf fchk` (600s timeout): exits in ~19s (PM3 hardware abort time)
- No grey screen, no crash, pipeline cleanup works on next flow

### 3. Hot-Patch Applied (MUST BE CONSOLIDATED)

The device was hot-patched (authorized by user) because the IPK with a syntax error broke navigation. The fix has been applied to the source files but **the device should receive a clean IPK install** to consolidate. The hot-patched files:
- `/home/pi/ipk_app_main/lib/activity_main.py`
- `/home/pi/ipk_app_main/lib/activity_read.py`

### 4. Diagnosis Fixes (IMPLEMENTED, DEVICE-VERIFIED)

Three bugs in DiagnosisActivity fixed and verified on real hardware:

| Fix | Change | File |
|-----|--------|------|
| Voltage 0V → real value | `re.findall` + last match instead of `re.search` (first match was always 0mV warmup) | `activity_tools.py:277` |
| Reader false OK | Check response content (UID/ATQA/TAG ID) instead of `ret == 1` | `activity_tools.py:283` |
| Flash `load` → `upload` | pm3_compat rule: `mem spiffs load f o` → `mem spiffs upload -s -d` (subcommand renamed in iceman) | `pm3_compat.py:433` |

**Device verification trace:** `docs/Real_Hardware_Intel/trace_iceman_diagnosis_fix_20260414.txt`

### 5. LUA Scripts — Path Fix (IMPLEMENTED, PARTIALLY VERIFIED)

**Problem:** LUA scripts bundled in `lua.zip` were never extracted to a location PM3 can find.

**Root cause chain:**
1. Installer looked for `lua.zip` at `/mnt/upan/lua.zip` but IPK puts it at `pm3/lua.zip` inside the package
2. Factory firmware extracted to `/home/pi/luascripts/` — not in iceman's search path
3. Iceman PM3 searches: `~/.proxmark3/luascripts/` and `<app>/share/proxmark3/luascripts/`
4. `LUAScriptCMDActivity` lists scripts from `/mnt/upan/luascripts/` (correct — user-editable location)

**Fix implemented in `install.py`:**
1. Find `lua.zip` from IPK (`unpkg_path/pm3/lua.zip`) or USB drive (`/mnt/upan/lua.zip`)
2. Extract to `/mnt/upan/` (user-editable, survives reinstalls)
3. Create symlinks: `<app>/share/proxmark3/luascripts` → `/mnt/upan/luascripts` (iceman path)
4. Create symlinks: `<app>/share/proxmark3/lualibs` → `/mnt/upan/lualibs`
5. Create symlinks: `<app>/luascripts` → `/mnt/upan/luascripts` (CWD-relative fallback)
6. Create symlinks: `<app>/lualibs` → `/mnt/upan/lualibs`

**Verified:** Symlinks work, PM3 finds and executes scripts. But factory `lua.zip` has Lua 5.1 `module()` calls incompatible with iceman's Lua 5.4. Needs iceman-compatible `lua.zip` — see Task 9 below.

### 6. Iceman lua.zip Compatibility (RESEARCHED, NEEDS CI/CD INTEGRATION)

**Finding:** Factory lualibs use `module()` (Lua 5.1 only, removed in 5.2+). Iceman PM3 uses Lua 5.4.7. Scripts crash with `attempt to call a nil value (global 'module')`.

**Iceman lualibs are backwards compatible** — they use standard `local` + `return` pattern that works in all Lua versions. Factory lualibs are NOT forwards compatible.

**Additional finding:** Iceman lualibs require two **auto-generated** Lua files that are produced during PM3 client compilation:
- `pm3_cmd.lua` — generated from `pm3_cmd.h` via `pm3_cmd_h2lua.awk` (299 lines of command constants)
- `mfc_default_keys.lua` — generated from `mfc_default_keys.dic`

These must be generated during Docker build and included in the iceman `lua.zip`. See Task 9 for full spec.

---

## Device Access

```
SSH: sshpass -p 'fa' ssh -p 2222 root@localhost
```
Requires reverse SSH tunnel from the device. User establishes manually.

### Key device paths
- App: `/home/pi/ipk_app_main/`
- PM3 binary: `/home/pi/ipk_app_main/pm3/proxmark3`
- Dump files: `/mnt/upan/dump/`
- IPK install: copy to `/mnt/upan/`, install via device UI Settings > Install

### Build & Deploy
```bash
python3 tools/build_ipk.py --output /tmp/icopy-x-latest.ipk
sshpass -p 'fa' scp -P 2222 /tmp/icopy-x-latest.ipk root@localhost:/mnt/upan/
```
Install via device UI: Settings > Install. Device reboots after install.

### Live Tracing
Full protocol: `docs/HOW_TO_RUN_LIVE_TRACES.md`

---

## CRITICAL RULES

1. **No atomic device edits** — deploy via IPK only (hot-patch requires explicit user authorization)
2. **NEVER flash PM3 bootrom** — no JTAG = permanent brick
3. **NEVER access ~/.ssh on any device**
4. **Tests are IMMUTABLE** — never modify test files without explicit permission
5. **Never change activity flow architecture** — only fix bugs WITHIN existing activities
6. **Always clean up sitecustomize.py** after tracing — leaving it crashes the app

---

## PENDING BUGS (8 items)

### Bug 1: ReadActivity ProgressBar stalls at 50% during key check

**Activity:** ReadActivity (`src/lib/activity_read.py`)
**Flow:** Read Tag → select type → scan → fchk (key checking phase)
**Symptom:** ProgressBar quickly jumps to 50% then stalls while waiting for keys (fchk). No visual feedback during the 10-60s key check.
**Expected:** ProgressBar should progress at ~1% per second up to 80% max until it gets updated by the key check completion routine.
**Approach:** Add a timer-based progress animation during the fchk phase. When fchk starts, animate the bar from current position at ~1%/s. When fchk returns with results, jump to the real percentage.

### Bug 2: WriteActivity ProgressBar not updating during writes

**Activity:** WriteActivity (`src/lib/activity_main.py`, search `class WriteActivity`)
**Symptom:** No ProgressBar updates visible during block write operations.
**Expected:** If there are no events to report or we are waiting, progress should advance at ~1% per second up to 60% max until updated by another routine (e.g., wrbl completion callback).
**Approach:** Similar timer-based animation. Check how the original firmware updated progress during writes (look at write middleware callbacks).

### Bug 3: VerifyActivity ProgressBar not updating during verification

**Activity:** Likely part of WriteActivity's verify phase or AutoCopyActivity's verify step
**Symptom:** No ProgressBar updates during card verification after write.
**Expected:** ProgressBar should show progress during verification.
**Approach:** Identify the verify code path and add progress callbacks. Check if verify uses a separate activity or is a state within WriteActivity/AutoCopyActivity.

### Bug 4: Post-Scan "No Card Found" button mapping wrong

**Activity:** ScanActivity (`src/lib/activity_main.py`, line ~1092)
**State:** `STATE_NOT_FOUND` (and possibly `STATE_WRONG_TYPE`, `STATE_MULTI`)
**Symptom:** After scan finds no card, M1 and M2 both show "Rescan", and OK is the mapped action button.
**Expected:** Remove M1 label. Map M2 to "Rescan". Unmap OK.
**Approach:** In the state transition to NOT_FOUND/WRONG_TYPE/MULTI, call `setM1('')` or hide M1, set `setM2('Rescan')`, and in onKeyEvent don't handle OK for rescan in these states.

### Bug 5: Erase Tag (Gen1a) — ProgressBar stuck at "Scanning"

**Activity:** WipeTagActivity (`src/lib/activity_main.py`, search `class WipeTagActivity`)
**Flow:** Erase Tag → OK → Gen1a card
**Symptom:** ProgressBar shows "Scanning" label and doesn't update throughout the entire erase flow.
**Expected:** Label should progress through phases: "Scanning..." → "Formatting..." etc. ProgressBar should update.
**Approach:** The erase middleware (`src/middleware/erase.py` / `src/lib/erase.py`) likely has callbacks. Wire them to update the progress bar label and percentage in WipeTagActivity.

### Bug 6: Erase Tag (Gen2) — ProgressBar stuck at "ChkDIC"

**Activity:** WipeTagActivity
**Flow:** Erase Tag → OK → Gen2 (non-Gen1a MIFARE Classic) card
**Symptom:** ProgressBar shows "ChkDIC" label and doesn't update during key checking and block erasure.
**Expected:** Labels should progress: "Scanning..." → "Checking Keys..." → "Formatting..." etc. ProgressBar should update.
**Approach:** Same as Bug 5 — wire erase middleware callbacks to WipeTagActivity progress updates.

### Bug 7: PWR must enforce 5-second max wait, then restart PM3

**Current behavior:** PWR during AutoCopy/Scan/Read calls `stopPM3Task(wait=True)` which blocks until the PM3 command finishes. For fchk, this can take ~19s (observed in device trace).
**Expected:** PWR should wait MAX 5 seconds for the PM3 command to finish naturally. If not done in 5s, restart the PM3 unit (`hmi_driver.restartpm3()` or `executor.reworkPM3All()`).
**Constraint:** PWR will NOT work during WRITE or ERASE operations (unchanged — WriteActivity and WipeTagActivity keep their current busy-blocks).
**Approach:** Change PWR handlers in AutoCopyActivity, ScanActivity, ReadActivity to use `stopPM3Task(wait=False)`, then spawn a background thread that waits up to 5s for the task to finish. If still running after 5s, call `reworkPM3All()`. The pipeline cleanup mechanism (`_ensure_pipeline_ready`) already handles the aftermath on the next `startPM3Task` call. Call `self.finish()` immediately (don't wait for the background cleanup).

### Bug 8: AutoCopy read-failed state — ActionBar persists over ProgressBar

**Activity:** AutoCopyActivity (`src/lib/activity_main.py`, line ~4658)
**State:** `STATE_READ_FAILED` or `STATE_READ_MISSING_KEYS`
**Symptom:** After a read failure, M1 shows "Rescan" and M2 shows "Reread". If the user presses either, the scan/read restarts but the dark ActionBar (M1/M2 button bar) persists and overlaps the ProgressBar.
**Expected:** When rescan or reread starts, the ActionBar should be hidden to reveal the ProgressBar underneath.
**Approach:** In the `_startRead()` and `startScan()` methods (or in the state transition), call `setM1('')` + `setM2('')` or hide the button bar. Check BaseActivity for ActionBar hide/show methods (`hideButtons()`, `showButtons()`, or similar).

### Task 9: LUA Scripts — Docker/CI Integration + Dual lua.zip

**Priority:** High — LUA scripts are completely non-functional until this is done.

**Background (fully researched this session):**

The PM3 LUA scripting system requires:
- `luascripts/*.lua` — the actual scripts (e.g., `hf_read.lua`, `hf_14a_raw.lua`)
- `lualibs/*.lua` — shared libraries (e.g., `ansicolors.lua`, `commands.lua`, `utils.lua`)
- `pm3_cmd.lua` — **auto-generated** command constants from `pm3_cmd.h` (299 lines)
- `mfc_default_keys.lua` — **auto-generated** default key dictionary

**Compatibility matrix:**
| | Factory PM3 (Lua 5.1) | Iceman PM3 (Lua 5.4) |
|---|---|---|
| Factory lualibs | Works | **BROKEN** — `module()` removed in Lua 5.2 |
| Iceman lualibs | Works — uses standard `local`+`return` pattern | Works |

**Two lua.zip files needed:**
- `build/factory_lua.zip` — **already exists** at `/home/qx/icopy-x-reimpl/build/factory_lua.zip` (69 files, 549KB). This is the original factory firmware's lua bundle. Ships in the no-flash IPK.
- `build/lua.zip` — **needs to be built by Docker/CI**. Iceman luascripts + lualibs + generated `pm3_cmd.lua` + `mfc_default_keys.lua`. Ships in the flash IPK.

**Docker changes needed (`tools/docker/Dockerfile.pm3-client`):**
1. During PM3 client build, the Makefile generates `lualibs/pm3_cmd.lua` and `lualibs/mfc_default_keys.lua`
2. After compilation, package everything into `lua.zip`:
   ```bash
   cd /tmp/proxmark3/client
   zip -r /out/lua.zip luascripts/ lualibs/
   ```
3. The Docker output volume (`build/`) receives both `proxmark3` (binary) and `lua.zip`

**How `pm3_cmd.lua` is generated:**
```bash
awk -f client/pm3_cmd_h2lua.awk include/pm3_cmd.h > client/lualibs/pm3_cmd.lua
```
This is done automatically by the Makefile (`make proxmark3` target depends on `lualibs/pm3_cmd.lua`).

**How `mfc_default_keys.lua` is generated:**
The Makefile rule: `lualibs/mfc_default_keys.lua : mfc_default_keys.dic`
Check the Makefile for the exact generation command.

**CI/CD changes needed (`.github/workflows/build-ipk.yml`):**
- Flash IPK: uses `build/lua.zip` (iceman, from Docker build output)
- No-flash IPK: uses `build/factory_lua.zip` (factory, checked into repo)
- `build_ipk.py` already picks up `build/lua.zip` — just needs Docker to produce it

**Installer changes (already done in `src/main/install.py`):**
- Finds `lua.zip` from IPK package (`unpkg_path/pm3/lua.zip`) or USB drive (`/mnt/upan/lua.zip`)
- **Must wipe** `/mnt/upan/luascripts` and `/mnt/upan/lualibs` before extracting — prevents mixed Lua 5.1/5.4 versions
- Extracts to `/mnt/upan/` (user-editable)
- Creates symlinks in app dir for PM3 to find them

**Current installer state:** The extract + symlink logic is implemented but the wipe-before-extract is NOT yet implemented. Add this:
```python
# Before extracting, wipe existing lua dirs to prevent version confusion
for dirname in (upan_luascripts, upan_lualibs):
    if os.path.isdir(dirname):
        shutil.rmtree(dirname)
```

**PM3 script search paths (from `strings proxmark3` + `script list`):**
1. `~/.proxmark3/luascripts/` (user home)
2. `<app>/share/proxmark3/luascripts/` (relative to PM3 binary: `pm3/../share/proxmark3/`)
3. `<app>/luascripts/` NOT searched by `script run` (only by implicit file search)

The symlinks at `<app>/share/proxmark3/luascripts` → `/mnt/upan/luascripts` are what make it work.

**LUAScriptCMDActivity (`src/lib/activity_main.py:2335`):**
- `SCRIPT_DIR = '/mnt/upan/luascripts'` — scans this directory to list scripts. No change needed.

**Test verification sequence:**
1. Build Docker → produces `build/proxmark3` + `build/lua.zip`
2. Build IPK → includes `pm3/lua.zip`
3. Install IPK on device
4. Verify: `/mnt/upan/luascripts/` populated, `<app>/share/proxmark3/luascripts` is symlink
5. Navigate to LUA Scripts → select `hf_read` → should execute without errors

**Iceman PM3 source (for Docker build):**
```bash
git clone --depth 1 --branch v4.21128 https://github.com/RfidResearchGroup/proxmark3.git
```

---

## Key Files

### Activities (where bugs live)
- `src/lib/activity_main.py` — AutoCopyActivity (~line 4658), ScanActivity (~line 1092), WipeTagActivity (~line 2649), WriteActivity (~line 4024)
- `src/lib/activity_read.py` — ReadActivity (~line 150)
- `src/lib/actbase.py` — BaseActivity (buttons, toast, busy state, _handlePWR)

### Middleware (progress callbacks)
- `src/middleware/hfmfread.py` — MIFARE read with fchk
- `src/middleware/hfmfwrite.py` — MIFARE write with wrbl
- `src/middleware/erase.py` — Erase flow
- `src/middleware/scan.py` — Scan orchestrator
- `src/middleware/executor.py` — PM3 command executor (pipeline cleanup)

### Infrastructure
- `src/main/rftask.py` — PM3 subprocess manager (cmd_lock, pipeline escalation)
- `src/lib/widget.py` — ProgressBar, Toast, CheckedListView UI widgets

### Device traces (reference)
- `docs/Real_Hardware_Intel/trace_iceman_pwr_fix_verify_20260414.txt` — PWR fix verification
- `docs/Real_Hardware_Intel/trace_iceman_pwr_debug_20260414.txt` — PWR swallowed (pre-fix)
- `docs/Real_Hardware_Intel/trace_iceman_mfu_pipeline_desync_20260414.txt` — Full AutoCopy flow with all PM3 commands

---

## Test Infrastructure

- **Pipeline cleanup tests:** `tests/ui/test_pipeline_cleanup.py` (16 tests)
- **PM3 compat tests:** `tests/ui/test_pm3_compat.py`, `tests/ui/test_pm3_response_compat.py`
- **Pre-existing failures:** `tests/ui/activities/test_auto_copy.py::TestAutoCopyScan::test_scan_found_starts_read` and ~50 others in test_read_tag, test_sniff, test_volume, etc. — these predate this session's changes

---

## Architecture Notes for Next Agent

### ProgressBar pattern
The ProgressBar widget (`src/lib/widget.py`) has `setProgress(percent)` and `setLabel(text)` methods. Activities typically create one in `onCreate` and update it from middleware callbacks or timer-based animation.

### Button bar pattern
BaseActivity manages M1/M2 buttons via `setM1(label)`, `setM2(label)`. Empty string or None hides the button. The button bar visibility is controlled by `_m1_visible`/`_m2_visible` flags. Check `showButtons()`/`hideButtons()` if they exist, otherwise set labels to empty strings.

### PWR 5-second timeout pattern (Bug 7)
```python
# Pseudocode for the PWR handler:
if key == KEY_PWR:
    hmi_driver.presspm3()
    executor.stopPM3Task(wait=False)  # Non-blocking
    self.finish()  # Exit immediately
    # Background cleanup with 5s timeout
    def _cleanup():
        deadline = time.monotonic() + 5
        while executor.LABEL_PM3_CMD_TASK_RUNNING:
            if time.monotonic() > deadline:
                executor.reworkPM3All()
                break
            time.sleep(0.1)
    threading.Thread(target=_cleanup, daemon=True).start()
```
The `_ensure_pipeline_ready()` in executor.py handles the aftermath on the next `startPM3Task` call regardless of how the cleanup finishes.

### stopPM3Task(wait=False) caveat
Currently `stopPM3Task(wait=False)` sets STOPPING then immediately clears it — the flag may not be seen by `_send_and_cache`. For the 5-second timeout approach, you may need to modify `stopPM3Task` so `wait=False` leaves STOPPING set, and have `startPM3Task` clear it at the end of its run. Test carefully.
