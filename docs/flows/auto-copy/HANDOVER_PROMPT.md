# Auto-Copy Flow — Handover Prompt for New Agent Session

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Audit and integrate the **Auto Copy** flow — `AutoCopyActivity` is a single activity that combines Scan → Read → Write → Verify into one automated pipeline. The activity already exists in `src/lib/activity_main.py`. The test suite reports 51/51 PASS — your job is to visually audit every test, ensure UI matches ground truth pixel-for-pixel, and fix any false positives or UI issues.

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/auto-copy/README.md` — **READ THIS FIRST.** Complete specification for the Auto-Copy flow. Architecture, state machine, key bindings, test infrastructure, all ground-truth resources.

2. `docs/flows/write/ui-integration/README.md` — **READ THIS SECOND.** Write flow post-mortem. Contains the DRM blocker discovery (6+ hours lost, 1-line fix), write.so call signature (`write.write(callback, scan_cache, bundle)` — 3 args, async, returns -9999), WriteActivity attribute naming (`.infos` not `._infos`, `.playWriting()` not `._playWriting()`), callback pattern (progress dicts then completion dict). Auto-Copy reuses the SAME write.so pipeline.

3. `docs/flows/read/ui-integration/README.md` — Read flow post-mortem. Scanner/Reader API discovery, template.so rendering, 4 completion mechanisms, console inline view.

4. `docs/flows/scan/ui-integration/README.md` — Scan flow post-mortem. Scanner API, ground truth rules.

5. `docs/UI_Mapping/02_auto_copy/README.md` — Exhaustive UI specification: 8 main states, key bindings matrix, button labels, toast messages.

6. `docs/Real_Hardware_Intel/trace_autocopy_mf1k_standard.txt` — **THE KEY TRACE.** Complete MFC 1K auto-copy flow (340 lines).

7. `docs/Real_Hardware_Intel/autocopy_mf4k_mf1k7b_t55_trace_20260329.txt` — Multi-tag trace: MF4K + MF1K-7B + T55XX (746 lines).

8. `docs/Real_Hardware_Intel/trace_lf_hf_write_autocopy_20260402.txt` — Live trace with write.so call signature + AutoCopy section (542 lines).

9. `docs/DRM-KB.md` and `docs/DRM-Issue.md` — DRM mechanism, correct cpuinfo serial, all 6 gated modules.

10. `docs/HOW_TO_RUN_LIVE_TRACES.md` — Deploy tracer to real device if new traces needed.

## Critical rules (from 3 completed flows)

### DRM — CHECK FIRST
Before debugging ANY silent .so failure, check the launcher log:
```
[OK] tagtypes DRM passed natively: 40 readable types    ← MUST see this
```
If you see `[WARN] tagtypes DRM failed`, the cpuinfo serial is wrong. Correct: `02c000814dfb3aeb`. This blocked the entire Write flow for 6+ hours.

### Ground Truth ONLY
- **NEVER invent.** Never guess. Never "try something".
- Every line of code must cite a decompiled .so, real trace, or real screenshot.
- If no ground truth exists, **ASK THE USER** before proceeding.
- After writing code, audit: does this come from ground truth? If not, undo.

### No Middleware
Our Python is a thin UI shell. scan.so, read.so, write.so, template.so, container.so handle ALL RFID logic. If you're writing tag-specific logic in Python — STOP.

### No Fixture Guessing
BEFORE modifying ANY fixture, request explicit user confirmation. Fix must come from: real trace, decompiled .so, or PM3 source (`https://github.com/iCopy-X-Community/icopyx-community-pm3`).

### UI Rules (from Write flow visual audit)
- **No action bar during active operations** (scanning, reading, writing, verifying). Only on result screens.
- **Toast margins**: 5px right, 5px icon gap, `wrap='auto'`
- **Button Y position**: 233 (global constant `BTN_LEFT_Y` / `BTN_RIGHT_Y`)
- **"Data ready!" screen**: Blue text (#1C6AEB), type name from `container.get_public_id(infos)`, JSON UI schema at `src/screens/warning_write.json`
- **Font sizes**: `normal`=10pt, `large`=13pt, `xlarge`=28pt
- **State dump toast text**: Joined with space (not `\n`)

### Test Results — Clean Local Before Rsync
```bash
rm -rf /home/qx/icopy-x-reimpl/tests/flows/_results/current/
sshpass -p proxmark rsync -az qx@178.62.84.144:/home/qx/icopy-x-reimpl/tests/flows/_results/current/ \
  /home/qx/icopy-x-reimpl/tests/flows/_results/current/
```
Stale screenshots from previous runs pollute visual reviews if you don't clean first.

## Auto-Copy architecture (key difference from Write flow)

Auto-Copy is a **SINGLE activity** (`AutoCopyActivity`) — NOT a chain of ReadActivity → WarningWriteActivity → WriteActivity. It handles scan+read+write+verify with internal state transitions.

```
AutoCopyActivity
    ├─ SCANNING → auto-starts in onCreate
    ├─ SCAN_NOT_FOUND / SCAN_MULTI / SCAN_WRONG_TYPE → toast + rescan
    ├─ READING → auto-starts after scan success
    ├─ READ_FAILED / READ_NO_KEY / READ_MISSING_KEYS / READ_TIMEOUT → error toasts
    ├─ PLACE_CARD → "Data ready!" prompt (M1=Watch, M2=Write)
    ├─ WRITING → write.write(callback, infos, bundle)
    ├─ WRITE_SUCCESS / WRITE_FAILED → toast
    ├─ VERIFYING → write.verify(callback, infos, bundle)
    └─ VERIFY_SUCCESS / VERIFY_FAILED → toast
```

The write/verify phase uses the **exact same write.so API** as WriteActivity:
```python
write.write(self.on_write, self.infos, self._read_bundle)  # 3 args, async
write.verify(self.on_verify, self.infos, self._read_bundle)
```

## What's already working

- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 61/61 PASS
- Auto-Copy: 51/51 PASS (needs visual audit)
- Volume: 7/7 PASS
- Backlight: 7/7 PASS

## What to do

1. **Run the full auto-copy suite** on remote with 9 workers
2. **Bring results back locally** (clean first!)
3. **Visually audit** key scenarios — compare screenshots with real device captures
4. **Check for UI issues**: action bar during operations, toast wrapping, font sizes, button positioning, "Data ready!" screen formatting
5. **Identify false positives** — tests passing on state count without validating toast content
6. **Fix issues one at a time** with ground-truth citations
7. **Run all suites** (scan + read + write + auto-copy) to verify no regressions

## Environment

- Branch: `feat/ui-integrating`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores, max 9 workers safe)
- Real device: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be up)
- Run single: `TEST_TARGET=current SCENARIO=autocopy_mf1k_happy FLOW=auto-copy bash tests/flows/auto-copy/scenarios/autocopy_mf1k_happy/autocopy_mf1k_happy.sh`
- Run all: `TEST_TARGET=current bash tests/flows/auto-copy/test_auto_copy_parallel.sh 9`

## Definition of done

1. All 51 auto-copy tests are TRUE passes with correct toast validation
2. UI matches real device at every state (no action bar during operations, correct toasts, correct fonts)
3. No regressions on scan/read/write flows
4. Every fix cites ground-truth source
