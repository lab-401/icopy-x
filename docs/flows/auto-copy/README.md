# Auto-Copy Flow — UI Integration Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Auto Copy** flow — `AutoCopyActivity` combines Scan → Read → Write → Verify into a single automated pipeline. The scan starts immediately on activity creation, reads the tag, prompts the user to swap cards, then writes and verifies.

**Current status:** `AutoCopyActivity` exists in `src/lib/activity_main.py` (lines ~3692-4150+) with 18 states. The test suite reports 51/51 PASS — but many may be false positives (same pattern as the Write flow). Your job is to audit every test visually, ensure UI matches ground truth, and fix any issues.

## CRITICAL — DRM SMOKE TEST

**Before debugging ANY silent .so failure (write.so returning -9, no PM3 commands, etc.), ALWAYS check DRM first:**

```bash
# Check launcher log for this line:
[OK] tagtypes DRM passed natively: 40 readable types    # ← MUST see this
[WARN] tagtypes DRM failed — falling back to bypass      # ← THIS MEANS WRITES WILL FAIL
```

**Root cause**: `hfmfwrite.tagChk1()` performs an AES-based DRM check using `/proc/cpuinfo` Serial. If the serial is wrong, tagChk1 returns False → `write_common()` returns -9 immediately — no fchk, no wrbl, "Write failed!" with zero PM3 write commands. This is completely silent.

**Correct serial**: `02c000814dfb3aeb` (in `launcher_current.py` cpuinfo mock)

**Reference**: `docs/DRM-KB.md`, `docs/DRM-Issue.md`

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/write/ui-integration/README.md` — **READ THIS FIRST.** Complete post-mortem of the Write flow integration. Contains the DRM blocker (6+ hours lost), write.so call signature discovery, WriteActivity attribute naming, callback patterns, and every lesson learned. Auto-Copy reuses the SAME write.so and verify pipeline.

2. `docs/flows/read/ui-integration/README.md` — Read flow post-mortem. ReadActivity patterns (4 completion mechanisms, console inline view, deferred results) apply to AutoCopy's read phase.

3. `docs/flows/scan/ui-integration/README.md` — Scan flow post-mortem. Scanner API discovery, template.so rendering rules.

4. `docs/UI_Mapping/02_auto_copy/README.md` — **Exhaustive UI specification** for AutoCopyActivity. All 8 main states, key bindings matrix, button labels, toast messages, activity transitions.

5. `docs/Real_Hardware_Intel/trace_autocopy_mf1k_standard.txt` — **THE KEY TRACE.** Complete MFC 1K auto-copy: scan → fchk → rdsc → wrbl → verify. 340 lines.

6. `docs/Real_Hardware_Intel/autocopy_mf4k_mf1k7b_t55_trace_20260329.txt` — Multi-tag auto-copy trace (MF4K + MF1K-7B + T55XX). 746 lines. Shows LF T55XX DRM pattern.

7. `docs/Real_Hardware_Intel/trace_lf_hf_write_autocopy_20260402.txt` — Live trace with write.so call signature discovery. Shows AutoCopy section with activity stack transitions.

8. `docs/Real_Hardware_Intel/Screenshots/auto_copy_scanning_1-4.png` — Scanning progress states.

9. `docs/Real_Hardware_Intel/Screenshots/auto_copy_no_tag_found.png` — No-tag-found toast.

10. Decompiled binaries:
    - `docs/v1090_strings/activity_main_strings.txt` — AutoCopyActivity symbols: `__init__`, `onCreate`, `onKeyEvent`, `startScan`, `showScanToast`, `onScanFinish`, `getManifest`
    - All write.so decompiled files (same as Write flow — `decompiled/write_ghidra_raw.txt`, `hfmfwrite_ghidra_raw.txt`, `lfwrite_ghidra_raw.txt`, etc.)

11. `src/lib/activity_main.py` — Current AutoCopyActivity implementation (lines ~3692-4150+).

12. `src/screens/autocopy.json` — AutoCopyActivity JSON UI state machine (17 states).

13. `tests/flows/auto-copy/includes/auto_copy_common.sh` — Test framework: 5-phase pipeline, 3 modes (early_exit, no_verify, full).

14. `tools/launcher_current.py` — Launcher with DRM fix, PM3 mock, state dump with `activity_state` field.

## Critical lessons from Scan, Read, and Write flows (DO NOT REPEAT)

### 1. DRM Blocks Writes Silently
The Write flow lost 6+ hours to a wrong cpuinfo serial. The DRM check in `hfmfwrite.tagChk1()` silently returns False → write returns -9 with zero PM3 commands. **ALWAYS smoke-test DRM first.** See `docs/flows/write/ui-integration/README.md` Section 3.

### 2. write.so Call Signature (from live trace)
```python
# Ground truth: trace_lf_hf_write_autocopy_20260402.txt
write.write(on_write_callback, scan_cache, read_bundle)
write.verify(on_verify_callback, scan_cache, read_bundle)
# Returns -9999 immediately (async). Result via callback.
# on_write receives: progress dicts {'max': N, 'progress': N} then completion {'success': bool}
```

### 3. WriteActivity Public Attribute Names
write.so accesses specific attributes on the activity via `callback.__self__`:
- `.infos` (NOT `._infos`), `.can_verify`, `._write_progressbar`, `._write_toast`
- `.playWriting()`, `.playVerifying()` (NOT underscore-prefixed)
- `.text_rewrite`, `.text_verify`, `.text_writing`, etc. (resource strings)
- Ground truth: `docs/Real_Hardware_Intel/trace_write_activity_attrs_20260402.txt`

### 4. Scanner/Reader API
```python
scanner = scan.Scanner()
scanner.call_progress = self.onScanning
scanner.call_resulted = self.onScanFinish
scanner.scan_all_asynchronous()
```

### 5. template.so Renders Tag Info — NOT Python
`template.draw(tag_type, scan_cache, canvas)` — never build display logic.

### 6. container.get_public_id(infos) for Type Display Names
The "Data ready!" screen type name comes from `container.get_public_id(scan_cache)`. Returns "M1-4b", "ID1", etc. Do NOT hardcode a lookup table.

### 7. NEVER Invent Middleware
Our Python is a thin UI shell. scan.so, read.so, write.so, template.so, container.so handle ALL RFID logic.

### 8. NEVER Mass-Modify Fixtures
Fix only specifically broken fixtures with ground-truth evidence and user confirmation.

### 9. Activity State Trigger
The state dump exposes `activity_state` from the top activity's `.state` property. Use `activity_state:reading` etc. for lifecycle-based test triggers — NOT button labels.

### 10. No Action Bar During Active Operations
Ground truth: No button bar during scanning, reading, writing, verifying. Only on result screens. `dismissButton()` when progress is active.

### 11. Toast Margins
Toast widget: `_MG=5` (icon gap), `_MR=5` (right margin), `wrap='auto'`. State dump joins toast text with space (not `\n`).

### 12. Button Label Y Position
`BTN_LEFT_Y = 233`, `BTN_RIGHT_Y = 233` (global constant, 5px lower than original).

## Auto-Copy flow architecture

### Activity stack transitions

```
MainActivity
    ↓ (user selects "Auto Copy" from main menu)
AutoCopyActivity (stack depth 2)
    ├─ SCANNING: auto-starts scan immediately in onCreate
    │   └─ scan.Scanner().scan_all_asynchronous()
    ├─ SCAN_NOT_FOUND / SCAN_MULTI / SCAN_WRONG_TYPE: toast + M1/M2=Rescan
    │
    ├─ READING: auto-starts read after scan success
    │   └─ read.Reader().start(tag_type, {'infos': scan_cache})
    ├─ READ_FAILED / READ_NO_KEY / READ_MISSING_KEYS / READ_TIMEOUT: error toasts
    │
    ├─ PLACE_CARD: "Data ready!" prompt — user swaps tag
    │   ├─ M1: "Watch" (Rescan) → startScan()
    │   └─ M2: "Write" → start write
    │
    ├─ WRITING: write.write(on_write, infos, bundle)
    │   └─ Progress bar "Writing..."
    ├─ WRITE_SUCCESS: toast "Write successful!"
    ├─ WRITE_FAILED: toast "Write failed!"
    │
    ├─ VERIFYING: write.verify(on_verify, infos, bundle)
    │   └─ Progress bar "Verifying..."
    ├─ VERIFY_SUCCESS: toast "Write and Verify successful!"
    └─ VERIFY_FAILED: toast "Verification failed!"
```

**Key difference from Write flow:** Auto-Copy is a SINGLE activity that handles scan+read+write+verify. Write flow uses separate ReadActivity → WarningWriteActivity → WriteActivity. Auto-Copy does it all in one activity with internal state transitions.

**Ground Truth**: `trace_autocopy_mf1k_standard.txt`, `docs/UI_Mapping/02_auto_copy/README.md`

### AutoCopyActivity state machine (key bindings)

| State | M1 | M2 | OK | PWR |
|-------|----|----|----|----|
| SCANNING | ignored | ignored | ignored | finish |
| SCAN_NOT_FOUND | startScan | startScan | startScan | finish |
| SCAN_WRONG_TYPE | startScan | startScan | startScan | finish |
| SCAN_MULTI | startScan | startScan | startScan | finish |
| READING | ignored | ignored | ignored | finish |
| READ_FAILED | startScan | startRead | startRead | finish |
| READ_MISSING_KEYS | startScan | force read | force read | finish |
| READ_TIMEOUT | startScan | retry | retry | finish |
| PLACE_CARD | startScan | startWrite | startWrite | finish |
| WRITING | ignored | ignored | ignored | finish |
| WRITE_SUCCESS | startScan | startScan | startScan | finish |
| WRITE_FAILED | startScan | startWrite | startWrite | finish |
| VERIFYING | ignored | ignored | ignored | finish |
| VERIFY_SUCCESS | startScan | startScan | startScan | finish |
| VERIFY_FAILED | startScan | startWrite | startWrite | finish |

**Ground Truth**: `docs/UI_Mapping/02_auto_copy/README.md` lines 345-364

### WarningWriteActivity in Auto-Copy context

In Auto-Copy, the "Data ready!" screen uses M1="Watch" (not "Cancel"). This is because AutoCopy's scan phase is "watching" for a new tag, not cancelling a manual operation.

**Ground Truth**: `data_ready.png` shows "Watch" / "Write" buttons

## Test infrastructure

### 5-phase auto-copy test pipeline (`auto_copy_common.sh`)

1. **Phase 1**: Navigate to Auto Copy from main menu (DOWN→OK)
2. **Phase 2**: Wait for scan+read completion via `M2:Write` trigger (or `activity_state` for scan-only failures)
3. **Phase 3**: WarningWriteActivity (if applicable) — wait `title:Data ready` → M2
4. **Phase 4**: WriteActivity — wait `M2:Rewrite` → validate write toast
5. **Phase 5**: (if not `no_verify`/`early_exit`) → M1 (verify) → wait final trigger

### Modes

- `early_exit` — scan/read failures, no write phase
- `no_verify` — write only, skip verify
- `""` (default) — full pipeline including verify

### Running tests

```bash
# Single test locally
TEST_TARGET=current SCENARIO=autocopy_mf1k_happy FLOW=auto-copy \
  bash tests/flows/auto-copy/scenarios/autocopy_mf1k_happy/autocopy_mf1k_happy.sh

# Full parallel suite on remote
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/auto-copy/test_auto_copy_parallel.sh 9'
```

### Framework constants

```
PM3_DELAY=0.5
BOOT_TIMEOUT=600
AUTOCOPY_TRIGGER_WAIT=240
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
```

### Bringing results back locally

```bash
# ALWAYS clean local first (stale screenshots pollute reviews)
rm -rf /home/qx/icopy-x-reimpl/tests/flows/_results/current/
sshpass -p proxmark rsync -az qx@178.62.84.144:/home/qx/icopy-x-reimpl/tests/flows/_results/current/ \
  /home/qx/icopy-x-reimpl/tests/flows/_results/current/
```

## Environment

- Branch: `feat/ui-integrating` at latest commit
- QEMU rootfs: `/mnt/sdcard/root2/root/`
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`, sudo: `proxmark`, 48 cores)
- Real device SSH: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be established by user)
- Max parallel workers: **9** (safe), 12 (max), 16 (causes resource contention failures)

## Working flows (don't break these)

- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 61/61 PASS
- Auto-Copy: 51/51 PASS (needs audit — may have false positives)

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/*.txt`
2. Real activity traces: `docs/Real_Hardware_Intel/trace_autocopy_*.txt`, `autocopy_*_trace*.txt`
3. Real screenshots: `docs/Real_Hardware_Intel/Screenshots/auto_copy_*.png`
4. UI Mapping: `docs/UI_Mapping/02_auto_copy/README.md`
5. **NEVER deviate.** Never invent. Never guess. Never "try something".
6. **ALL work must derive from these ground truths.**
7. **EVERY action** must cite its ground-truth reference.
8. **Before writing code:** Does this come from ground truth? If not, don't.
9. **After writing code:** Audit — does this come from ground truth? If not, undo.
10. **Use existing launcher tools** — `tools/launcher_current.py` — Do not roll your own infrastructure.
11. **When .so modules fail silently — ALWAYS smoke-test DRM first.**

If no ground truth exists, ask the user before proceeding.

### Supplementary ground truth
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` — use when trace responses are truncated
- Live trace methodology: `docs/HOW_TO_RUN_LIVE_TRACES.md` — deploy tracer to real device (tunnel on port 2222, `root:fa`)
- Write flow lessons: `docs/flows/write/ui-integration/README.md` — DRM, callback patterns, attribute names

## Definition of done

1. AutoCopyActivity UI matches real device screenshots at every state
2. All 51 auto-copy tests are TRUE passes — correct toast content verified
3. No action bar during scanning/reading/writing/verifying
4. "Data ready!" screen matches ground truth (blue text, large type name from `container.get_public_id()`)
5. Toast wrapping correct with 5px margins
6. Button labels at correct Y position (233)
7. No regressions: Scan 45/45, Read 99/99, Write 61/61
8. Every change cites ground-truth source

## Approach

1. **Run the full auto-copy suite** and establish baseline
2. **Visually audit** screenshots from every scenario — compare with real device
3. **Identify false positives** — tests that pass on state count but show wrong UI
4. **Fix one at a time** — code change, verify single test, verify no regression
5. **Apply Write flow patterns** — the write phase reuses the same write.so, same callbacks, same DRM
