# Simulate Flow -- Handover Prompt for New Agent Session

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Audit and integrate the **Simulate Tag** flow -- `SimulationActivity` selects a tag type from a 16-item list, accepts UID/parameter input via editable fields, sends a PM3 simulation command, and (for HF types) captures a trace via `SimulationTraceActivity`. The activities already exist in `src/lib/activity_main.py`. The test suite has 30 scenarios. Your job is to run every test, visually audit screenshots against real device captures, and fix any failures or UI issues.

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/simulate/README.md` -- **READ THIS FIRST.** Complete specification for the Simulate flow. Architecture, state machine, SIM_MAP table (16 types), SIM_FIELDS (per-type input definitions), key bindings, HF vs LF differences, test infrastructure, all ground-truth resources.

2. `docs/flows/auto-copy/ui-integration/README.md` -- **READ THIS SECOND.** Auto-Copy post-mortem. Contains: scan.so Scanner API fix, scan.isTagMulti()/isTagFound() predicates, ConsoleMixin, WarningM1Activity for key failures, MF4K race condition (poll thread vs onReading), middleware removal lessons. Every lesson applies to this flow.

3. `docs/flows/write/ui-integration/README.md` -- Write flow post-mortem. DRM blocker (6+ hours lost, 1-line fix), callback patterns, no-middleware rules.

4. `docs/flows/read/ui-integration/README.md` -- Read flow post-mortem. Scanner/Reader API, template.so rendering, 4 completion mechanisms.

5. `docs/flows/scan/ui-integration/README.md` -- Scan flow post-mortem. Scanner API, ground truth rules.

6. `docs/UI_Mapping/07_simulation/README.md` -- **Exhaustive UI specification**: 52 exported methods, complete state machine, per-type field specs, input method system, PM3 command building, trace viewer.

7. `docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt` lines 71-84 -- **THE KEY TRACE.** Real device MFC 1K simulation: `hf 14a sim t 1 u 3AF73501 (timeout=-1)` -> stop -> `START(SimulationTraceActivity)` -> `hf 14a list (timeout=18888)` -> FINISH chain.

8. Real device screenshots:
    - `docs/Real_Hardware_Intel/Screenshots/simulation_list_1_4.png` -- Type list (page 1/4)
    - `docs/Real_Hardware_Intel/Screenshots/simulation_detail_1.png` -- Sim UI with UID field
    - `docs/Real_Hardware_Intel/Screenshots/simulation_in_progress.png` -- Toast overlay

9. `docs/DRM-KB.md` and `docs/DRM-Issue.md` -- DRM mechanism, correct cpuinfo serial.

10. `docs/HOW_TO_RUN_LIVE_TRACES.md` -- Deploy tracer to real device if new traces needed.

## Critical rules (from 4 completed flows)

### DRM -- CHECK FIRST
Before debugging ANY silent .so failure, check the launcher log:
```
[OK] tagtypes DRM passed natively: 40 readable types    <- MUST see this
```
If not, the cpuinfo serial is wrong. Correct: `02c000814dfb3aeb`. See `docs/DRM-KB.md`.

### Ground Truth ONLY
- **NEVER invent.** Never guess. Never "try something".
- Every line of code must cite a decompiled .so, real trace, or real screenshot.
- If no ground truth exists, **ASK THE USER** before proceeding.
- After writing code, audit: does this come from ground truth? If not, undo.

### No Middleware
Our Python is a thin UI shell. The .so modules handle ALL RFID logic. SimulationActivity builds PM3 commands from SIM_MAP templates and user input, then calls `executor.startPM3Task()`. It does NOT parse PM3 responses or make tag-specific decisions.

### Tests are IMMUTABLE
NEVER modify test files (fixtures, .sh, triggers, timeouts) without explicit user permission. Present findings and ASK.

### No Blind Sleeps
Never sleep 240s waiting for tests. Poll output every 10-30s or run foreground. Catch crashes in seconds, not minutes.

### No Fixture Guessing
BEFORE modifying ANY fixture, request explicit user confirmation. Fix must come from: real trace, decompiled .so, or PM3 source.

## Simulate flow architecture

### State machine
```
SimulationActivity
    |-- LIST_VIEW: 16 types in 4 pages (5 per page)
    |   UP/DOWN scroll, M2/OK select, PWR exit
    |
    |-- SIM_UI: input fields for selected type
    |   M1 toggle edit, UP/DOWN field/char, LEFT/RIGHT cursor
    |   M2/OK validate + start sim, PWR back to list
    |
    '-- SIMULATING: PM3 command running
        HF: timeout=-1, M2/PWR stop -> push SimulationTraceActivity
        LF: timeout=30000, M2/PWR stop -> back to SIM_UI

SimulationTraceActivity (HF only)
    Shows trace from `hf 14a list`
    M2/OK save, M1/PWR back
```

### Key trace (real device, lines 71-84)
```
START(SimulationActivity, {scan_cache})
PM3> hf 14a sim t 1 u 3AF73501  (timeout=-1)
PM3< [+] Emulating ISO/IEC 14443 type A tag... Trace length: 0
START(SimulationTraceActivity, None)
PM3> hf 14a list (timeout=18888)
PM3< [+] Recorded activity (trace len = 0 bytes)
FINISH(SimulationTraceActivity)
FINISH(SimulationActivity)
```

### HF vs LF differences

| | HF (types 0-4) | LF (types 5-15) |
|---|---|---|
| PM3 timeout | `-1` (runs forever) | `30000` (self-terminates) |
| Stop action | push SimulationTraceActivity | back to SIM_UI |
| After stop | `hf 14a list` fetches trace | no trace |

## What's already working

- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 61/61 PASS
- Auto-Copy: 52/52 PASS
- Volume: 7/7 PASS
- Backlight: 7/7 PASS

## What to do

1. **Run the full simulate suite** on remote with 9 workers
2. **Bring results back locally** (clean first!)
3. **Visually audit** key scenarios -- compare screenshots with real device captures
4. **Check for UI issues**: list pagination, input field rendering, toast messages, button positions, page indicators
5. **Identify failures** -- tests failing on trigger or state count
6. **Fix issues one at a time** with ground-truth citations
7. **Run all suites** (scan + read + write + auto-copy + simulate) to verify no regressions

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores, max 9 workers safe)
- Real device: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be up)
- Run single: `TEST_TARGET=current SCENARIO=sim_em410x FLOW=simulate bash tests/flows/simulate/scenarios/sim_em410x/sim_em410x.sh`
- Run all: `TEST_TARGET=current bash tests/flows/simulate/test_simulate_parallel.sh 9`
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

## Definition of done

1. All 30 simulate tests are TRUE passes with correct UI validation
2. UI matches real device at every state (list, sim UI, simulating, trace)
3. Input field editing works for all types (hex, decimal, selector)
4. HF trace capture flow works end-to-end
5. No regressions on scan/read/write/auto-copy flows
6. Every fix cites ground-truth source
