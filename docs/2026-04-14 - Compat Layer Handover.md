# PM3 Compatibility Layer — Session Handover (2026-04-14)

## Branch: `working/compatibility-layer`
## Latest commit: `e95448c`
## Tests: 378/378 passing

---

## Device Access

```
SSH: sshpass -p 'fa' ssh -p 2222 root@localhost
```
Requires reverse SSH tunnel from the device. User establishes this manually.
If tunnel drops, ask user to reconnect.

### Key device paths
- App: `/home/pi/ipk_app_main/`
- PM3 binary: `/home/pi/ipk_app_main/pm3/proxmark3`
- PM3 device: `/dev/ttyACM0`
- USB storage: `/mnt/upan/`
- IPK install: copy to `/mnt/upan/`, install via device UI Settings > Install
- Dump files: `/mnt/upan/dump/`
- Trace output: `/mnt/upan/full_trace.log`

---

## Build & Deploy Pipeline

### PM3 Client (ARM cross-compiled for iCopy-X Ubuntu 16.04)
```bash
# Rebuild Docker image (includes all tools/patches/pm3_*.patch)
sudo docker build -f tools/docker/Dockerfile.pm3-client -t pm3-client-builder .

# Compile — output goes to build/proxmark3
sudo docker run --rm -v $(pwd)/build:/out pm3-client-builder
```
- Platform: `PM3ICOPYX`
- Patches applied automatically: `pm3_eor_marker`, `pm3_suppress_inplace`, `pm3_readline_compat`, `pm3_14a_select_warning`
- SKIPREADLINE=1 (daemon mode, no interactive readline)

### PM3 Firmware (ARM bare-metal for AT91SAM7S512)
```bash
# Requires arm-none-eabi-gcc (apt install gcc-arm-none-eabi)
cd /tmp/pm3_new  # or clone fresh: git clone --depth 1 --branch v4.21128 https://github.com/RfidResearchGroup/proxmark3.git /tmp/pm3_new
git checkout .

# Apply patches
for p in /home/qx/icopy-x-reimpl/tools/patches/pm3_*.patch; do
    git apply --check "$p" 2>/dev/null && git apply "$p"
done

# Build firmware (NEVER bootrom — permanent brick, no JTAG)
make -j$(nproc) fullimage PLATFORM=PM3ICOPYX SKIPREVENGTEST=1

# Output: armsrc/obj/fullimage.elf
```
Copy to `res/firmware/pm3/fullimage.elf` + update `manifest.json`.
The app auto-detects version mismatch and prompts the user to flash.
Manifest `pm3_firmware_version` must NOT match the running firmware's version string to trigger flash.

### IPK Package
```bash
python3 tools/build_ipk.py --output /tmp/icopy-x-latest.ipk

# Push to device
sshpass -p 'fa' scp -P 2222 /tmp/icopy-x-latest.ipk root@localhost:/mnt/upan/
```
Install via device UI: Settings > Install. Device reboots after install.

### CI/CD: `.github/workflows/build-ipk.yml`
- Client build: Docker ubuntu:16.04, cross-compile with patches
- Firmware build: native arm-none-eabi-gcc, PLATFORM=PM3ICOPYX, patches applied
- IPK: combines client + firmware + Python UI + resources
- Platform: `PM3ICOPYX` for both client and firmware (XC3S100E FPGA)

---

## Live Device Tracing

### Deploy tracer (app instrumentation)
Full protocol: `docs/HOW_TO_RUN_LIVE_TRACES.md` section 5.

Quick deploy:
```bash
# 1. Write sitecustomize.py tracer (see docs/HOW_TO_RUN_LIVE_TRACES.md section 5 for full script)
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat > /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py << "PYEOF"
<full tracer script from docs>
PYEOF'

# 2. Clear old trace + kill app (watchdog restarts with tracer)
sshpass -p 'fa' ssh -p 2222 root@localhost 'rm -f /mnt/upan/full_trace.log; kill $(pgrep -f "python.*app.py" | head -1)'

# 3. Verify tracer loaded
sshpass -p 'fa' ssh -p 2222 root@localhost 'grep "ALL INSTALLED" /mnt/upan/full_trace.log'
```

### Live streaming (real-time monitoring)
Use the Monitor tool:
```
Monitor(
    description="Live device trace",
    persistent=True,
    command="sshpass -p 'fa' ssh -p 2222 root@localhost 'tail -f /mnt/upan/full_trace.log' 2>&1 | grep -E --line-buffered 'START|FINISH|PM3>|PM3<.*ret=|CACHE|REWORK|PRESSPM3|error|failed|timeout'"
)
```
Tighten filter if output rate too high (monitor auto-stops). Remove `PM3<.*ret=` to reduce volume.

### Pull trace + cleanup
```bash
sshpass -p 'fa' ssh -p 2222 root@localhost 'cat /mnt/upan/full_trace.log' > docs/Real_Hardware_Intel/trace_iceman_<name>_$(date +%Y%m%d).txt
sshpass -p 'fa' ssh -p 2222 root@localhost 'rm -f /usr/local/python-3.8.0/lib/python3.8/site-packages/sitecustomize.py'
```
**ALWAYS clean up sitecustomize.py** — leaving it causes app crash on next reboot.

### Trace format
```
[  56.944] PM3> hf 14a info (timeout=5000)      — command sent
[  58.457] PM3< ret=1 content_len=287 \n UID:... — response (full, not truncated)
[  59.703] START(ScanActivity, None) bundle=None  — activity transition
[  74.591] FINISH(top=ScanActivity d=2)           — activity exit
[  70.547] SERIAL_TX> b'presspm3'                 — GD32 serial command
[  58.997] CACHE: {"found": "True", ...}          — scan cache update
[  69.356] REWORK> reworkPM3All()                 — PM3 restart
```

### Direct PM3 testing (bypass RTM)
```bash
# Stop app first
sshpass -p 'fa' ssh -p 2222 root@localhost 'systemctl stop icopy; killall -9 python3; sleep 3'

# Run PM3 directly
sshpass -p 'fa' ssh -p 2222 root@localhost 'timeout 15 sh -c "echo \"hf 14a info\" | /home/pi/ipk_app_main/pm3/proxmark3 /dev/ttyACM0 -w --flush"'

# Restart app after
sshpass -p 'fa' ssh -p 2222 root@localhost 'systemctl start icopy'
```

---

## Architecture

### Communication flow
```
[middleware .py] → executor.startPM3Task(cmd, timeout)
    → pm3_compat.translate(cmd)          # old→new command syntax
    → TCP:8888 "Nikola.D.CMD = {cmd}"
    → [rftask.py RTM] → PM3 stdin
    → PM3 stdout → reader thread → EOR detection ("pm3 -->")
    → response back via TCP
    → pm3_compat.translate_response(text, cmd)  # new→old response format
    → executor.CONTENT_OUT_IN__TXT_CACHE
    → executor.hasKeyword() / getContentFromRegex()  # middleware pattern matching
```

### PM3 patches (tools/patches/)
| Patch | Target | Purpose |
|-------|--------|---------|
| `pm3_eor_marker.patch` | client (proxmark3.c) | Emit `pm3 -->` EOR marker after each command for RTM detection |
| `pm3_suppress_inplace.patch` | client (ui.c) | Suppress INPLACE spinner on piped stdin |
| `pm3_readline_compat.patch` | client (ui.c) | Stub `rl_clear_visible_line` for readline 6.3 |
| `pm3_14a_select_warning.patch` | client (cmdhf14a.c) | Card select failures at WARNING level (not DEBUG) |

All patches follow naming convention `pm3_*.patch` — the Dockerfile and CI glob `pm3_*.patch` to apply them.

### PM3 source trees (for reference)
- Legacy: `git clone --depth 1 https://github.com/iCopy-X-Community/icopyx-community-pm3.git /tmp/pm3_old`
- Iceman: `git clone --depth 1 --branch v4.21128 https://github.com/RfidResearchGroup/proxmark3.git /tmp/pm3_new`

---

## What's Done

### Command Translation (52+ rules in pm3_compat.py)
- All MIFARE Classic commands (rdbl, wrbl, rdsc, fchk, nested, darkside, cload, csetuid, etc.)
- All iCLASS commands (rdbl --blk, dump 3-arg with -f, wrbl --blk, calcnewkey --old/--new, chk --vb6kdf)
- All 19 LF read→reader renames
- lf fdx→fdxb namespace change
- lf em4x05 -a (not -b) for address
- hf 14a sim -t/-u, hf list -t, lf config flags
- hf iclass info blocked (hangs PM3 due to FPGA mismatch)
- hf 14a raw -p→-k flag rename

### Response Normalization (18 normalizers)
- fchk table format, darkside key, wrbl isOk, rdbl data: format
- EM410x ID, Chipset detection, T55xx config, EM4x05 info
- iCLASS rdbl/wrbl, hf15 csetuid, FeliCa, manufacturer label
- EOR marker stripping, trace length parsing (both legacy + iceman formats)

### RTM Stability (rftask.py)
- EOR marker patch — PM3 emits `pm3 -->` after each command
- Reader thread join on rework (no zombie threads)
- 3s+1s rework delay for device re-enumeration
- `_expecting_response` gate prevents pipeline contamination
- Auto-recovery on timeout (restart PM3) and empty response (retry)

### Write/Erase Flow Fixes
- Card presence check (UID required before fchk — prevents 600s hang)
- WriteActivity presspm3 + stopPM3Task on PWR exit
- erase.py Gen1a detection uses data: format (not isOk:01)
- iCLASS Elite wrbl adds --elite flag for type 18
- hf15 restore double .bin fix
- hf 14a config --bcc ignore at startup for Gen1a compatibility

---

## CRITICAL RULE: No Atomic Device Edits

**Do NOT make atomic edits to the live device.** No rsync of individual files, no remote edits via SSH, no hot-patching of running code. The ONLY way to deploy code changes is via IPK:

1. Build: `python3 tools/build_ipk.py --output /tmp/icopy-x-latest.ipk`
2. Push: `sshpass -p 'fa' scp -P 2222 /tmp/icopy-x-latest.ipk root@localhost:/mnt/upan/`
3. Install: User installs via device UI **Settings > Install**
4. Device reboots automatically after install

The device filesystem is volatile. The watchdog may revert to `ipk_app_bak` if the main app crashes. Tracing via `sitecustomize.py` is the ONLY acceptable file modification on the device.

**Save EVERY live trace** to `/home/qx/icopy-x-reimpl/docs/Real_Hardware_Intel/` with naming convention `trace_iceman_<description>_<YYYYMMDD>.txt`. Save BEFORE redeploying the tracer — redeploy clears the trace file.

---

## Remaining Bugs

### FIXED and device-verified (commit 95e81f8, 2026-04-14)

| Bug | Issue | Fix | Verified |
|-----|-------|-----|----------|
| 1 | AWID FC/CN X,X | pm3_compat: extract card number from unknown format `(NNNNN)` | ✅ device |
| 2 | HID Prox raw hex | lfsearch: extract FC/CN from Wiegand decode; pm3_compat: strip leading zeros | ✅ device |
| 3 | FDX-B empty data | pm3_compat: `[\s.]*:` regex in Phase C (after dot-to-colon conversion); lfsearch+template: Country/NC two-line display | ✅ device |
| 5 | Gallagher FC/CN X,X | pm3_compat: normalize `Facility:`→`FC:`, `Card No.:`→`Card:` | ✅ device |
| 6 | SecuraKey FC X | pm3_compat: convert hex FC `0x2AAA` to decimal `10922` | ✅ device |
| 10 | ISO15693 ST SA→generic | pm3_compat: `STMicroelectronics`→`ST Microelectronics SA France` | normalizer added, no ST tag to verify |
| 11 | iCLASS write verify failure | iclasswrite: pass `elite=is_elite` to `readTagBlock()`; hficlass: remove stale `[+]` check; iclasswrite: `int()` type conversion | ✅ device |

### Additional bugs found and fixed during device testing

| Issue | Fix | Verified |
|-------|-----|----------|
| iCLASS Elite wrbl missing `--elite` | iclasswrite: `' e'`→`' --elite'` | ✅ device |
| hf 15 restore `Done!` not recognized | pm3_compat: normalizer injects `Write OK` + `done` | ✅ device |
| hf mf wrbl block 0 rejected | pm3_compat: `--force` on ALL `hf mf wrbl` (block 0 + sector trailers) | ✅ device |
| MFU restore timeout 5000ms too short | hfmfuwrite: ground truth timeouts UL=10888, UL-EV1=16888, NTAG=30000-120000 | ✅ device |
| MFU write false success on incomplete restore | hfmfuwrite: require `Done` keyword in response | ✅ device |
| WipeTagActivity PWR ignored during fchk | activity_main: PWR cancels during SCANNING (not during ERASING) | ✅ device |
| Gen1a erase cwipe | Working end-to-end | ✅ device |
| MF1K Gen2 erase | Working with `--force` on sector trailers | ✅ device |

### Key lesson: iceman dotted separators

Iceman uses `Field...........: value` (dotted alignment) in multi-line output. `_post_normalize` converts these to `Field: value` in Phase C. **Normalizers that match field names with colons MUST run in Phase C** (after dot-to-colon conversion), not Phase B. The FDX-B `Animal ID` fix was blocked for hours by this — the Phase B normalizer saw `Animal ID...........:` which didn't match the regex.

### Not fixed

| Bug | Issue | Status |
|-----|-------|--------|
| 4 | FDX-A detected as HID Prox | PM3 firmware limitation — no FDX-A demodulator in iceman |
| 7 | Keri detected as Indala | Keyword case normalizer added, no Keri tag available to verify |
| 8 | Indala UID showing 0000000000 | Best-effort `Card:` line added but lfsearch handler uses `setRAW` — needs handler change |
| 9 | NTAG203 subtype→Ultralight | Not investigated — need to compare iceman `hf mfu info` output for NTAG203 |
| 12-15 | Gen1a BCC, GProx II, NexWatch, IdTeck/Noralsy | PM3 firmware/hardware — not fixable in compat layer |

### OPEN ISSUE: PM3 pipeline dirty after command timeout

**Problem:** When a PM3 command times out (e.g., MFU restore at old 5s timeout), the socket buffer retains stale response data. Subsequent commands receive the stale data instead of their own response, causing a cascade of wrong results.

**Failed fix attempt:** Calling `reworkPM3All()` in `onDestroy` of AutoCopyActivity/WipeTagActivity. This crashes the app because:
1. `reworkPM3All()` calls `time.sleep(3)` — blocks the Tk main thread
2. During the 3s sleep, PWR key events queue up in the Tk event loop
3. When sleep ends, queued PWRs fire in burst — popping ALL activities including MainActivity
4. Empty activity stack = grey screen (app dead but process alive)

**Evidence:** `trace_iceman_crash_diag_20260414.txt` — `FINISH_ENTER stack=['MainActivity']` → `FINISH_OK stack_after=[]`

**Needs:** A non-blocking pipeline cleanup mechanism. Research the original firmware's ground truth for how it handled PM3 state between flows. The `reworkPM3All` function itself works (tested from background thread) — the issue is calling it from the Tk main thread context.

---

## Verified Working Flows (updated 2026-04-14)

| Flow | Status | Notes |
|------|--------|-------|
| Scan — MIFARE Classic 1K/4K | ✅ | Fast (2s) |
| Scan — iCLASS Legacy/Elite | ✅ | 10s (via hf search fallthrough) |
| Scan — ISO15693/ICODE | ✅ | 10s |
| Scan — NTAG213/216 | ✅ | |
| Scan — Ultralight/EV1/C | ✅ | Some subtypes show as generic |
| Scan — EM4100 | ✅ | |
| Scan — AWID | ✅ | FC/CN: X,33825 (X for unknown format, CN extracted) |
| Scan — HID Prox | ✅ | FC,CN: 128,54641 (from Wiegand decode) |
| Scan — FDX-B | ✅ | Country: 112 / NC: 025880314020 (two-line display) |
| Scan — Gallagher | ✅ | FC,CN: 4369,00000 |
| Scan — SecuraKey | ✅ | FC,CN: 10922,52428 (hex→decimal) |
| Scan — Other LF (Paradox, Pyramid, Viking, PAC, Jablotron, IO Prox, T55xx) | ✅ | Detection works |
| Read — MIFARE Classic 1K | ✅ | fchk + rdsc all working |
| Read — iCLASS Legacy | ✅ | dump with -k -f working |
| Read — iCLASS Elite | ✅ | dump with -k -f --elite working |
| Read — ISO15693 | ✅ | hf 15 dump -f working |
| Read — NTAG216 | ✅ | hf mfu dump -f working |
| Read — Ultralight EV1 | ✅ | Intermittent (RF coupling) |
| Write — MIFARE Classic Gen1a (cload) | ✅ | Full clone + freeze + verify |
| Write — MIFARE Classic Gen2 (wrbl) | ✅ | With --force, key B fallback |
| Write — AWID (T55xx clone) | ✅ | wipe + write blocks |
| Write — iCLASS Legacy | ✅ | wrbl --blk working + verify working |
| Write — iCLASS Elite | ✅ | wrbl --elite + verify with elite flag |
| Write — ISO15693 | ✅ | hf 15 restore (no double .bin) + Done normalizer |
| Write — Ultralight EV1 (mfu restore) | ✅ | timeout=16888 (ground truth) |
| AutoCopy — MIFARE Classic | ✅ | End-to-end scan→read→write→verify |
| AutoCopy — iCLASS Elite | ✅ | End-to-end with --elite |
| Simulate — MIFARE Classic | ✅ | hf 14a sim + trace capture + save |
| Sniff — HF 14A | ✅ | Trace data + TraceLen correct |
| Erase — MIFARE Classic (standard) | ✅ | wrbl with --force on all blocks |
| Erase — Gen1a (cwipe) | ✅ | Full wipe successful |
| Erase — PWR cancel during fchk | ✅ | Cancels during key check, not during block writes |

---

## Key Files
- `src/middleware/pm3_compat.py` — all translation rules + response normalizers
- `src/middleware/lfsearch.py` — LF response parsing regexes (bugs 1-8)
- `src/middleware/scan.py` — scan orchestrator
- `src/middleware/hfmfread.py` — MIFARE read with data: line parsing
- `src/middleware/hfmfwrite.py` — MIFARE write with card presence check
- `src/middleware/erase.py` — erase with Gen1a data: detection
- `src/middleware/iclasswrite.py` — iCLASS write with --elite flag
- `src/middleware/hf15write.py` — ISO15693 write with .bin fix
- `src/middleware/sniff.py` — trace length regex (both formats)
- `src/lib/activity_main.py` — WriteActivity PWR abort, trace parsing, BCC config
- `src/main/rftask.py` — RTM with stability fixes
- `src/middleware/executor.py` — PM3 command executor
- `tools/patches/` — 4 PM3 patches (pm3_*.patch naming convention)
- `tools/docker/Dockerfile.pm3-client` — client cross-compilation
- `.github/workflows/build-ipk.yml` — CI/CD pipeline
- `res/firmware/pm3/` — fullimage.elf + manifest.json
- `docs/Real_Hardware_Intel/trace_iceman_*.txt` — 13+ device traces from this session

## Audit Data (in /tmp/, may need regeneration)
- `/tmp/pm3_audit_phase1.txt` — all middleware PM3 commands + patterns (772 lines)
- `/tmp/pm3_audit_phase2a.txt` — HF command mapping legacy↔iceman (692 lines)
- `/tmp/pm3_audit_phase2b.txt` — LF command mapping legacy↔iceman (792 lines)
- `/tmp/pm3_blind_audit.txt` — blind audit findings (632 lines)

To regenerate: clone both PM3 repos to /tmp/pm3_old and /tmp/pm3_new, then run the audit agents from the plan.
