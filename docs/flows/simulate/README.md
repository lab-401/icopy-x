# Simulate Flow -- UI Integration Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Simulate Tag** flow -- `SimulationActivity` and `SimulationTraceActivity` must display the correct UI at every step: type selection list, input fields with editing, PM3 simulation execution, and HF trace capture/display.

**Current status:** `SimulationActivity` and `SimulationTraceActivity` exist in `src/lib/activity_main.py` (lines ~4702-5087). The test suite has 30 scenarios. Your job is to audit every test visually, ensure UI matches ground truth pixel-for-pixel, and fix any issues.

## CRITICAL -- DRM SMOKE TEST

**Before debugging ANY silent .so failure, ALWAYS check DRM first:**

```bash
# Check launcher log for this line:
[OK] tagtypes DRM passed natively: 40 readable types    # <- MUST see this
[WARN] tagtypes DRM failed -- falling back to bypass      # <- THIS MEANS MODULES MAY FAIL
```

**Correct serial**: `02c000814dfb3aeb` (in `launcher_current.py` cpuinfo mock)

**Reference**: `docs/DRM-KB.md`, `docs/DRM-Issue.md`

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/auto-copy/ui-integration/README.md` -- **READ THIS FIRST.** Complete post-mortem of the Auto-Copy flow integration. Contains: scan.so Scanner API pattern, scan.isTagMulti()/isTagFound() predicates, ConsoleMixin, WarningM1Activity for key failures, MF4K race condition fix, middleware removal lessons. The Simulate flow follows the same ground truth rules.

2. `docs/flows/write/ui-integration/README.md` -- Write flow post-mortem. DRM blocker (6+ hours lost, 1-line fix), write.so call signature, callback patterns.

3. `docs/flows/read/ui-integration/README.md` -- Read flow post-mortem. Scanner/Reader API, template.so rendering, 4 completion mechanisms.

4. `docs/flows/scan/ui-integration/README.md` -- Scan flow post-mortem. Ground truth rules.

5. `docs/UI_Mapping/07_simulation/README.md` -- **Exhaustive UI specification** for SimulationActivity. All 16 types, input fields, key bindings, state machine, PM3 commands, trace viewer.

6. `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` lines 71-84 -- **THE KEY TRACE.** Real device simulation of MFC 1K: `hf 14a sim t 1 u 3AF73501` -> trace capture -> `hf 14a list` -> SimulationTraceActivity -> FINISH chain.

7. Real device screenshots:
    - `docs/Real_Hardware_Intel/Screenshots/simulation_list_1_4.png` -- Type list (5 items, page "1/4")
    - `docs/Real_Hardware_Intel/Screenshots/simulation_detail_1.png` -- Sim UI: "M1 S50 1k", UID field, Stop/Start
    - `docs/Real_Hardware_Intel/Screenshots/simulation_detail_2.png`
    - `docs/Real_Hardware_Intel/Screenshots/simulation_detail_3.png`
    - `docs/Real_Hardware_Intel/Screenshots/simulation_detail_4.png`
    - `docs/Real_Hardware_Intel/Screenshots/simulation_in_progress.png` -- Toast "Simulation in progress..."

8. Decompiled binary:
    - `decompiled/actmain_ghidra_raw.txt` -- SimulationActivity (52 methods)
    - `docs/v1090_strings/activity_main_strings.txt` -- SimulationActivity and SimulationTraceActivity symbols

9. `src/lib/activity_main.py` -- Current implementations:
    - `SIM_MAP` table (lines ~4653-4670): 16 simulation types with PM3 command templates
    - `SIM_FIELDS` table (lines ~4672-4699): per-type input field definitions
    - `SimulationActivity` class (lines ~4702-5037)
    - `SimulationTraceActivity` class (lines ~5040-5087)

10. `src/screens/simulation.json` -- JSON UI state machine (3 states: list_view, sim_ui, simulating)

11. `tools/launcher_current.py` -- Launcher with PM3 mock, DRM fix, state dump.

12. `tests/flows/simulate/includes/sim_common.sh` -- Test framework with navigation, field editing, trigger polling.

## Critical lessons from completed flows (DO NOT REPEAT)

### 1. Scanner/Reader API -- Use the REAL .so API
Probed and confirmed patterns: `scan.Scanner()` with callbacks, `read.Reader()` with callbacks. For simulation: `executor.startPM3Task(cmd, timeout)` sends PM3 commands. `timeout=-1` for HF sim (runs until stopped). Check the trace: line 73 shows `hf 14a sim t 1 u 3AF73501 (timeout=-1)`.

### 2. template.so Renders Tag Info -- NOT Python
Do NOT build display logic in Python. The .so modules handle rendering.

### 3. NEVER Invent Middleware
If you find yourself writing simulation-specific PM3 command parsing, STOP -- it belongs in the .so modules. Our Python is a thin UI shell that builds the PM3 command from SIM_MAP templates and user input, then calls `executor.startPM3Task()`.

### 4. NEVER Mass-Modify Fixtures
**BEFORE MODIFYING ANY FIXTURES -- REQUEST EXPLICIT CONFIRMATION FROM THE USER.** Verify each fix individually.

### 5. Fixture Fixes Need Real Traces
If a fixture is broken, the fix MUST come from: (a) a real device trace, (b) the decompiled .so binary, or (c) PM3 source code at `https://github.com/iCopy-X-Community/icopyx-community-pm3`. Never guess PM3 response formats.

### 6. Tests are IMMUTABLE
NEVER modify test files (fixtures, .sh, triggers, timeouts) without explicit user permission. Present findings and ASK.

### 7. No Blind Sleeps
Never put blind sleeps on test runs. Poll output every 10-30s. Catch crashes in seconds, not minutes.

### 8. scan.so Predicate Functions Take Arguments
`scan.isTagMulti(result)` and `scan.isTagFound(result)` take the result dict as argument. Zero-argument calls fail silently via except handler.

### 9. actstack Callback is `onActivity()` not `onActivityResult()`
When a child activity finishes with a result, the parent receives it via `onActivity(result)`. Using the wrong name silently fails.

### 10. ConsoleMixin for Shared Console Logic
Inline PM3 console view is shared via `ConsoleMixin` in `activity_read.py`. Don't duplicate it.

## Simulate flow architecture

### Activity stack transitions

```
MainActivity
    | (user selects "Simulation" from main menu)
SimulationActivity (stack depth 2)
    |-- LIST_VIEW: 16 simulation types in 4 pages (5 items per page)
    |   |-- UP/DOWN: scroll list
    |   |-- M2/OK: select type -> SIM_UI
    |   '-- PWR: finish (back to main)
    |
    |-- SIM_UI: input fields for selected type
    |   |-- M1: toggle edit mode on focused field
    |   |-- UP/DOWN: switch field (not editing) / edit char value (editing)
    |   |-- LEFT/RIGHT: move cursor within field (editing)
    |   |-- M2/OK: validate inputs + start simulation -> SIMULATING
    |   '-- PWR: back to LIST_VIEW
    |
    '-- SIMULATING: PM3 command running
        |-- HF types: hf 14a sim (timeout=-1, runs until stopped)
        |   '-- M2/PWR: stopSim -> push SimulationTraceActivity
        '-- LF types: lf <type> sim (timeout=30000, self-terminating)
            '-- M2/PWR: stopSim -> back to SIM_UI

SimulationTraceActivity (stack depth 3, HF only)
    |-- Shows trace data from `hf 14a list`
    |-- M2/OK: save trace data
    |-- M1/PWR: finish (back to SimulationActivity SIM_UI)
```

**Ground Truth**: `trace_scan_flow_20260331.txt` lines 71-84, `docs/UI_Mapping/07_simulation/README.md`

### Real device trace (MFC 1K simulation)

```
[ 259.358] START(SimulationActivity, {'found': True, 'uid': '3AF73501', ...})
[ 259.802] PM3> hf 14a sim t 1 u 3AF73501  (timeout=-1)
[ 262.964] PM3< ret=1 [...] Emulator stopped. Trace length: 0
[ 263.325] START(SimulationTraceActivity, None)
[ 263.409] PM3> hf 14a list (timeout=18888)
[ 263.444] PM3< ret=1 [...] Recorded activity (trace len = 0 bytes)
[ 264.315] FINISH(SimulationTraceActivity)
[ 265.308] FINISH(SimulationActivity)
```

### SIM_MAP -- 16 simulation types

| # | Display Name | Type ID | Freq | PM3 Command |
|---|-------------|---------|------|-------------|
| 0 | M1 S50 1k | 1 | HF | `hf 14a sim t 1 u {uid}` |
| 1 | M1 S70 4k | 0 | HF | `hf 14a sim t 2 u {uid}` |
| 2 | Ultralight | 2 | HF | `hf 14a sim t 7 u {uid}` |
| 3 | Ntag215 | 6 | HF | `hf 14a sim t 8 u {uid}` |
| 4 | FM11RF005SH | 40 | HF | `hf 14a sim t 9 u {uid}` |
| 5 | Em410x ID | 8 | LF | `lf em 410x_sim {uid}` |
| 6 | HID Prox ID | 9 | LF | `lf hid sim {data}` |
| 7 | AWID ID | 11 | LF | `lf awid sim {fc} {cn} {fmt}` |
| 8 | IO Prox ID | 12 | LF | `lf io sim {ver} {fc} {cn}` |
| 9 | G-Prox II ID | 13 | LF | `lf gproxii sim {fc} {cn} {fmt}` |
| 10 | Viking ID | 15 | LF | `lf Viking sim {uid}` |
| 11 | Pyramid ID | 16 | LF | `lf Pyramid sim {fc} {cn}` |
| 12 | Jablotron ID | 30 | LF | `lf Jablotron sim {id}` |
| 13 | Nedap ID | 32 | LF | `lf nedap sim s {sub} c {cn} i {id}` |
| 14 | FDX-B Animal | 28 | LF | `lf FDX sim c {country} n {id} s` |
| 15 | FDX-B Data | 28 | LF | `lf FDX sim c {country} n {id} e {ext}` |

### SIM_FIELDS -- per-type input definitions

Each field is `(label, default, format, max_value)`:

| Draw Key | Fields |
|----------|--------|
| `hf_4b` | `UID: 12345678 (hex, 8 chars)` |
| `single_7b` | `UID: 123456789ABCDE (hex, 14 chars)` |
| `single_4b` | `UID: 12345678 (hex, 8 chars)` |
| `lf_4b` | `UID: 1234567890 (hex, 10 chars)` |
| `lf_5b` | `ID: 112233445566 (hex, 12 chars)` |
| `lf_awid` | `FC: (dec, max 65535), CN: (dec, max 65535), Format: (dec, max 255)` |
| `lf_io` | `Version: (hex, 2), FC: (dec, max 255), CN: (dec, max 999)` |
| `lf_gporx` | `FC: (dec, max 255), CN: (dec, max 65535), Format: (dec, max 255)` |
| `lf_pyramid` | `FC: (dec, max 255), CN: (dec, max 99999)` |
| `lf_jab` | `ID: 1C6AEB (hex, 6 chars)` |
| `lf_nedap` | `Subtype: (hex, 2), CN: (dec, max 65535), ID: (dec, max 65535)` |
| `lf_fdx_a` | `Country: (dec, max 2001), ID: (dec, max 4294967295), Animal: (sel, 0/1)` |
| `lf_fdx_d` | `Country: (dec, max 2001), ID: (dec, max 4294967295), Ext: (dec, max 255)` |

### Key differences: HF vs LF simulation

| | HF (types 0-4) | LF (types 5-15) |
|---|---|---|
| PM3 timeout | `-1` (runs forever) | `30000` (30s, self-terminates) |
| Stop behavior | `stopPM3Task()` -> push `SimulationTraceActivity` | `stopPM3Task()` -> back to SIM_UI |
| After stop | `hf 14a list` fetches trace | No trace capture |
| Bundle to SimActivity | scan_cache dict (from Read flow) | scan_cache dict or manual entry |

### SimulationActivity key bindings

| State | M1 | M2/OK | UP | DOWN | LEFT | RIGHT | PWR |
|-------|----|----|----|----|----|----|-----|
| LIST_VIEW | -- | select type | scroll up | scroll down | -- | -- | finish |
| SIM_UI (not editing) | toggle edit | start sim | prev field | next field | -- | -- | back to list |
| SIM_UI (editing) | toggle edit | start sim | char value up | char value down | cursor left | cursor right | back to list |
| SIMULATING | -- | stop sim | -- | -- | -- | -- | stop sim |

### SimulationTraceActivity key bindings

| Key | Action |
|-----|--------|
| M2/OK | Save trace data |
| M1/PWR | finish (back to SimulationActivity) |

## Test infrastructure

### 30 test scenarios

| Category | Scenarios | What they test |
|----------|-----------|---------------|
| HF sim + trace data | 5 | M1 S50, M1 S70, Ultralight, Ntag215, FM11RF005SH with trace |
| HF sim + trace empty | 5 | Same types, trace len = 0 |
| HF trace save | 1 | M1 S50 trace save action |
| LF sim happy | 10 | Em410x, HID, AWID, IO Prox, G-Prox II, Viking, Pyramid, Jablotron, Nedap, FDX-B Animal/Data |
| Validation fail | 6 | AWID, FDX-B Animal/Data, G-Prox II, IO Prox, Nedap, Pyramid -- overflow values |
| PWR during sim | 1 | PWR stops simulation cleanly |

### Test modes

- `lf_sim` -- LF simulation: navigate -> edit fields -> start -> wait for sim completion
- `trace_data` -- HF simulation with trace data: navigate -> start -> stop -> verify trace content
- `trace_empty` -- HF simulation with empty trace: navigate -> start -> stop -> verify empty trace
- `trace_save` -- HF trace save: same as trace_data + M2 to save
- `validation_fail` -- Input overflow values -> toast "Input invalid"
- `pwr_during_sim` -- Start sim -> PWR -> verify clean stop

### Running tests

```bash
# Single test
TEST_TARGET=current SCENARIO=sim_em410x FLOW=simulate \
  bash tests/flows/simulate/scenarios/sim_em410x/sim_em410x.sh

# Full parallel suite on remote
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/simulate/test_simulate_parallel.sh 9'

# Retrieve results
rm -rf tests/flows/_results/current/simulate/
sshpass -p proxmark rsync -az qx@178.62.84.144:/home/qx/icopy-x-reimpl/tests/flows/_results/current/simulate/ \
  tests/flows/_results/current/simulate/
```

### Framework constants

```
PM3_DELAY=0.5
BOOT_TIMEOUT=600
SIM_TRIGGER_WAIT=120
TRACE_TRIGGER_WAIT=30
```

## PM3 command reference for simulation

### HF Simulation
- `hf 14a sim t {type} u {uid}` -- Simulate ISO14443-A tag. Type: 1=MFC1K, 2=MFC4K, 7=UL, 8=NTAG215, 9=FM11RF005SH. Response: `[+] Emulating ISO/IEC 14443 type A tag with N byte UID`. Runs until stopped (`timeout=-1`).
- `hf 14a list` -- Download trace from Proxmark3. Response includes `Recorded activity (trace len = N bytes)`.

### LF Simulation
- `lf em 410x_sim {uid}` -- Simulate EM410x. Self-terminates.
- `lf hid sim {data}` -- Simulate HID Prox.
- `lf awid sim {fc} {cn} {format}` -- Simulate AWID.
- `lf io sim {version} {fc} {cn}` -- Simulate IO Prox.
- `lf gproxii sim {fc} {cn} {format}` -- Simulate G-Prox II.
- `lf Viking sim {uid}` -- Simulate Viking.
- `lf Pyramid sim {fc} {cn}` -- Simulate Pyramid.
- `lf Jablotron sim {id}` -- Simulate Jablotron.
- `lf nedap sim s {subtype} c {cn} i {id}` -- Simulate Nedap.
- `lf FDX sim c {country} n {id} s` -- Simulate FDX-B Animal.
- `lf FDX sim c {country} n {id} e {ext}` -- Simulate FDX-B Data.

PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` -- `cmdhf14a.c` for HF sim, `cmdlf*.c` for LF sim commands.

## Environment

- Branch: `feat/ui-integrating` at latest commit
- QEMU rootfs: `/mnt/sdcard/root2/root/`
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`, sudo: `proxmark`, 48 cores)
- Real device SSH: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be established by user)
- Max parallel workers: **9** (safe)

## Working flows (don't break these)

- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 61/61 PASS
- Auto-Copy: 52/52 PASS

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/*.txt`
2. Real activity traces: `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` lines 71-84
3. Real screenshots: `docs/Real_Hardware_Intel/Screenshots/simulation_*.png`
4. UI Mapping: `docs/UI_Mapping/07_simulation/README.md`
5. **NEVER deviate.** Never invent. Never guess. Never "try something".
6. **ALL work must derive from these ground truths.**
7. **EVERY action** must cite its ground-truth reference.
8. **Before writing code:** Does this come from ground truth? If not, don't.
9. **After writing code:** Audit -- does this come from ground truth? If not, undo.
10. **Use existing launcher tools** -- `tools/launcher_current.py` -- Do not roll your own infrastructure.
11. **When .so modules fail silently -- ALWAYS smoke-test DRM first.**

If no ground truth exists, ask the user before proceeding.

### Supplementary ground truth
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` -- use when trace responses are truncated
- Live trace methodology: `docs/HOW_TO_RUN_LIVE_TRACES.md` -- deploy tracer to real device (tunnel on port 2222, `root:fa`)

## Definition of done

1. All 30 simulate test scenarios PASS with correct UI state validation
2. UI matches real device screenshots at every state (list view, sim UI, simulating, trace)
3. No action bar during active simulation
4. Input field editing works correctly for all field types (hex, decimal, selector)
5. Validation toasts shown for overflow values
6. HF simulation -> trace capture -> trace display flow works end-to-end
7. LF simulation -> clean termination flow works
8. No regressions: Scan 45/45, Read 99/99, Write 61/61, Auto-Copy 52/52
9. Every change cites ground-truth source

## Approach

1. **Run the full simulate suite** on remote with 9 workers
2. **Bring results back locally** (clean first!)
3. **Visually audit** key scenarios -- compare screenshots with real device captures
4. **Check for UI issues**: list pagination, input field rendering, toast messages, button labels
5. **Identify failures** -- tests failing on trigger or state count
6. **Fix issues one at a time** with ground-truth citations
7. **Run all suites** (scan + read + write + auto-copy + simulate) to verify no regressions
