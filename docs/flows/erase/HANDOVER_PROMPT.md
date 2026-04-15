# Erase Flow -- Handover Prompt for New Agent Session

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Audit and integrate the **Erase Tag** flow -- `WipeTagActivity` erases MIFARE Classic (Gen1a magic + standard) and T5577 tags. The activity exists in `src/lib/activity_main.py`. The test suite has 11 scenarios. Your job is to run every test, visually audit screenshots against real device captures, and fix any failures or UI issues.

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/erase/README.md` -- **READ THIS FIRST.** Complete specification for the Erase flow. Architecture, state machine, erase algorithms, PM3 commands, test infrastructure, all ground-truth resources.

2. `docs/flows/simulate/ui-integration/README.md` -- **READ THIS SECOND.** Simulate flow post-mortem. Contains: SimFields widget (nested Select Box + Input Field), FB capture methodology, pixel measurement, content verification in tests, validation limit corrections, middleware removal. Every lesson applies.

3. `docs/flows/auto-copy/ui-integration/README.md` -- Auto-Copy post-mortem. scan.so predicates, ConsoleMixin, WarningM1Activity for key failures, middleware removal.

4. `docs/flows/write/ui-integration/README.md` -- Write flow post-mortem. DRM blocker (6+ hours lost, 1-line fix), write.so call signature, callback patterns. Erase uses same PM3 commands (`hf mf wrbl` for standard erase).

5. `docs/flows/read/ui-integration/README.md` -- Read flow post-mortem. Scanner/Reader API, template.so rendering.

6. `docs/flows/scan/ui-integration/README.md` -- Scan flow post-mortem. Scanner API, ground truth rules.

7. `docs/UI_Mapping/13_erase_tag/README.md` -- **Exhaustive UI specification**: 5 states, 2 erase types, PM3 commands, key bindings, callback methods (40+ binary symbols).

8. `docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt` -- **THE KEY TRACE.** Complete erase flow: Gen1a `hf mf cwipe` (timeout=28888), standard `hf mf fchk` + `hf mf wrbl`, T5577 `lf t55xx wipe`.

9. `docs/Real_Hardware_Intel/trace_erase_gen1a_and_standard.txt` -- Gen1a vs standard card erase comparison.

10. Real device screenshots:
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_1.png` -- Type selection (2 items)
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_2-3.png` -- Scanning + ChkDIC
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_4-5.png` -- Erasing progress
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_menu_6.png` -- Result with Erase/Erase buttons
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_scanning.png` -- Scanning progress bar
    - `docs/Real_Hardware_Intel/Screenshots/erase_tag_unknown_error.png` -- Error state

11. `docs/DRM-KB.md` and `docs/DRM-Issue.md` -- DRM mechanism, correct cpuinfo serial.

12. `docs/HOW_TO_RUN_LIVE_TRACES.md` -- Deploy tracer to real device if new traces needed.

## Critical rules (from 5 completed flows)

### DRM -- CHECK FIRST
Before debugging ANY silent .so failure, check the launcher log:
```
[OK] tagtypes DRM passed natively: 40 readable types    <- MUST see this
```
If not, cpuinfo serial is wrong. Correct: `02c000814dfb3aeb`. See `docs/DRM-KB.md`.

### Ground Truth ONLY
- **NEVER invent.** Never guess. Never "try something".
- Every line of code must cite a decompiled .so, real trace, or real screenshot.
- If no ground truth exists, **ASK THE USER** before proceeding.
- After writing code, audit: does this come from ground truth? If not, undo.

### No Middleware
Our Python is a thin UI shell. The .so modules handle ALL RFID logic. WipeTagActivity calls `executor.startPM3Task()` for PM3 commands. It does NOT parse PM3 responses or make tag-specific decisions in Python.

### Tests are IMMUTABLE
NEVER modify test files without explicit user permission. Present findings and ASK.

### No Blind Sleeps
Never sleep 240s waiting for tests. Poll output every 10-30s. Catch crashes in seconds.

### Visual Pixel Matching
Compare EVERY screenshot with real device FB captures side-by-side. Do NOT declare "close enough". Iterate until exact match. If you don't have FB captures for a state, request them from the user.

### Content Verification
After navigating to an activity, verify expected content appears in the state dump. This catches wrong-navigation bugs (Simulate had 7 scenarios going to wrong types).

### PM3 on Background Threads
`executor.startPM3Task(cmd, timeout)` with positional args. Run on `threading.Thread(daemon=True)`. No `callback=` kwarg (PM3 mock doesn't accept it).

## Erase flow architecture

### State machine
```
WipeTagActivity
    |-- TYPE_SELECT: 2-item list
    |   1. Erase MF1/L1/L2/L3
    |   2. Erase T5577
    |   M1/PWR: finish, M2/OK: start erase
    |
    |-- ERASING: "Processing..." toast
    |   MF1 Gen1a: hf mf cwipe (timeout=28888)
    |   MF1 Standard: hf 14a info -> cgetblk -> fchk -> wrbl x N
    |   T5577: lf t55xx wipe [p 20206666]
    |   PWR: cancel
    |
    |-- SUCCESS: "Erase successful!", M1/M2="Erase"
    |-- FAILED: "Erase failed!", M1/M2="Erase"
    '-- NO_KEYS: "No valid keys...", M1/M2="Erase"
```

### Key trace (real device)
```
# Gen1a magic wipe:
PM3> hf mf cwipe (timeout=28888)
PM3< ret=1 [+] Magic card wipe done

# Standard erase (block-by-block):
PM3> hf 14a info (timeout=5000)
PM3> hf mf cgetblk 0 (timeout=5888)   # test Gen1a -> fails
PM3> hf mf fchk 1 /tmp/.keys/mf_tmp_keys (timeout=600000)
PM3> hf mf wrbl 0 A ffffffffffff 00000000000000000000000000000000
PM3> hf mf wrbl 1 A ffffffffffff 00000000000000000000000000000000
...

# T5577 wipe:
PM3> lf t55xx wipe (timeout=5000)           # no password
PM3> lf t55xx wipe p 20206666 (timeout=5000) # with DRM password
```

### PM3 commands
- `hf mf cwipe` (timeout=28888) -- Gen1a magic wipe
- `hf mf cgetblk 0` (timeout=5888) -- Test Gen1a
- `hf mf fchk {type} {keyfile}` (timeout=600000) -- Find keys
- `hf mf wrbl {block} {keytype} {key} {zeros}` (timeout=5888) -- Zero block
- `lf t55xx wipe` / `lf t55xx wipe p 20206666` (timeout=5000) -- T5577 wipe

PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

## What's already working

- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 61/61 PASS
- Auto-Copy: 52/52 PASS
- Simulate: 28/28 PASS
- Volume: 7/7 PASS
- Backlight: 7/7 PASS

## What to do

1. **Run the full erase suite** on remote with 9 workers
2. **Bring results back locally** (clean first!)
3. **Visually audit** every scenario's screenshots against real device captures
4. **Check for UI issues**: type selection list, "Processing..." toast, result toasts, button labels, progress display
5. **Verify content**: correct erase type name appears, correct toast text
6. **Identify failures** -- tests failing on trigger or state count
7. **Fix issues one at a time** with ground-truth citations
8. **Run all suites** (scan + read + write + auto-copy + simulate + erase) to verify no regressions

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores, max 9 workers safe)
- Real device: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be up)
- Run single: `TEST_TARGET=current SCENARIO=erase_mf1_gen1a_success FLOW=erase bash tests/flows/erase/scenarios/erase_mf1_gen1a_success/erase_mf1_gen1a_success.sh`
- Run all: `TEST_TARGET=current bash tests/flows/erase/test_erase_parallel.sh 9`
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3`

## Definition of done

1. All 11 erase tests are TRUE passes with correct toast validation
2. UI matches real device at every state (type select, erasing, success, fail, no_keys)
3. "Processing..." toast during erase
4. Correct result toasts with Erase/Erase buttons
5. No regressions on scan/read/write/auto-copy/simulate
6. Every fix cites ground-truth source
