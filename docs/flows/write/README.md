# Write Flow — UI Integration Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Write Tag** flow — `write.so` and related protocol modules (`hfmfwrite.so`, `lfwrite.so`, `iclasswrite.so`, `hf15write.so`, `hfmfuwrite.so`) must call back to our Python `WarningWriteActivity` / `WriteActivity`, displaying correct UI at every step.

**Current status:** The Write flow activities (`WarningWriteActivity`, `WriteActivity`) already exist in `src/lib/activity_main.py` and are wired to `write.so`. The test suite reports 63/63 PASS — but **13 of those are FALSE POSITIVES** that pass on screenshot state count alone, without validating toast content. Your job is to audit, fix the false positives, and ensure all 63 tests are TRUE passes.

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

We lost HOURS to this. The launcher had a wrong serial (`02150004f4584d53`). The args to write.so were byte-for-byte identical between working and broken — only the cpuinfo serial differed.

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/read/ui-integration/README.md` — **READ THIS FIRST.** Complete post-mortem of the Read flow integration. Contains every lesson learned, every mistake to avoid, the correct architecture, and the ground truth rules. The Write flow follows the same patterns.

2. `docs/flows/scan/ui-integration/README.md` — Scan flow post-mortem. Same ground truth rules apply.

3. `docs/WRITE-TESTS-STATUS.md` — **CRITICAL.** Documents the 13 false positive scenarios, their root causes, and the specific fixture fixes required. This is your primary task list.

4. `docs/HOW_TO_BUILD_FLOWS.md` — Methodology, fixture structure, keyword matching, logic tree extraction.

5. `docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt` — **THE KEY TRACE.** Real device trace of a complete MFC 1K read-to-write-to-verify cycle. Shows: exact PM3 command sequence, activity stack transitions, block write order (reverse: 60→0), trailer write order, verify phase. **Study this trace before touching any code.**

6. `docs/Real_Hardware_Intel/awid_write_trace_20260328.txt` — LF AWID write to T55xx. Shows: wipe → clone → DRM password (b7=20206666) → detect verify → content verify. **All LF clones follow this pattern.**

7. `docs/Real_Hardware_Intel/fdxb_t55_write_trace_20260328.txt` — FDX-B clone to T55xx. DRM password sequence confirmed.

8. `docs/Real_Hardware_Intel/t55_to_t55_write_trace_20260328.txt` — T55xx restore flow. Shows: wipe with password → detect → restore → detect verify.

9. `docs/Real_Hardware_Intel/mf4k_gen1a_read_write_trace_20260329.txt` — Complete MF4K Gen1a read+write trace. 567 lines, extensive activity stack and PM3 logging.

10. `docs/Real_Hardware_Intel/read_write_activity_trace_20260327.txt` — Activity stack proof: WriteActivity is NOT pushed during Read. Read completes within ReadListActivity. Write triggered by M2 → WarningWriteActivity → WriteActivity.

11. `docs/Real_Hardware_Intel/write_flow_20260326/` — **270 sequential state screenshots** of a complete write flow. Shows all UI states from main menu through write completion.

12. `docs/Real_Hardware_Intel/Screenshots/write_tag_writing_1-3.png` — WriteActivity progress bar screenshots.

13. `docs/Real_Hardware_Intel/Screenshots/write_tag_write_failed.png` — Write failure toast.

14. `docs/UI_Mapping/16_write_tag/README.md` — **Exhaustive UI specification** for WarningWriteActivity and WriteActivity. All states, buttons, toasts, key bindings.

15. Decompiled binaries:
    - `decompiled/write_ghidra_raw.txt` — write.so (13,763 lines): write(), verify() entry points
    - `decompiled/hfmfwrite_ghidra_raw.txt` — MFC write module (22,233 lines)
    - `decompiled/lfwrite_ghidra_raw.txt` — LF write module (16,478 lines)
    - `decompiled/iclasswrite_ghidra_raw.txt` — iCLASS write module (11,781 lines)
    - `decompiled/hf15write_ghidra_raw.txt` — ISO15693 write module (5,726 lines)
    - `decompiled/hfmfuwrite_ghidra_raw.txt` — Ultralight/NTAG write module (6,628 lines)

16. Extracted .so strings:
    - `docs/v1090_strings/write_strings.txt` — Generic write module symbols
    - `docs/v1090_strings/hfmfwrite_strings.txt` — MFC write commands and keywords
    - `docs/v1090_strings/lfwrite_strings.txt` — LF write commands, DRM password 20206666
    - `docs/v1090_strings/iclasswrite_strings.txt` — iCLASS write commands
    - `docs/v1090_strings/hf15write_strings.txt` — ISO15693 restore and csetuid
    - `docs/v1090_strings/hfmfuwrite_strings.txt` — Ultralight/NTAG write commands
    - `docs/v1090_strings/activity_main_strings.txt` — WriteActivity and WarningWriteActivity method symbols

17. `src/lib/activity_main.py` — Current activity implementations (WarningWriteActivity lines ~3011-3127, WriteActivity lines ~3133-3436).

18. `src/lib/activity_read.py` — `_launchWrite()` at line 769 — the read→write transition.

19. `tools/launcher_current.py` — The launcher script for the "current" test infrastructure.

20. `src/screens/write_tag.json` — WriteActivity state machine definition (JSON UI).

## Critical lessons from Scan and Read flows (DO NOT REPEAT THESE MISTAKES)

### 1. Scanner/Reader/Writer API Discovery
The .so module APIs are NOT what you expect. Probe under QEMU first. For write.so:
- Check `docs/v1090_strings/write_strings.txt` for class/method names
- WriteActivity calls `write.write(infos, callback)` and `write.verify(infos, callback)` on background threads
- The `infos` dict comes from `scan.getScanCache()` and includes dump file paths
- **Do NOT assume the API. Verify against traces.**

### 2. template.so Renders Tag Info — NOT Python
WarningWriteActivity's "Data ready!" screen shows tag info. This comes from `template.so` or the tag info dict — do NOT build display logic in Python.

### 3. NEVER Invent Middleware
If you find yourself writing tag-specific write logic, STOP — it belongs in `write.so` / `hfmfwrite.so` / `lfwrite.so` etc. Our Python is a thin UI shell that calls `.so` module functions and renders their results.

### 4. NEVER Mass-Modify Fixtures
**BEFORE MODIFYING ANY FIXTURES — REQUEST EXPLICIT CONFIRMATION FROM THE USER.** Only fix fixtures that are SPECIFICALLY identified as broken in `docs/WRITE-TESTS-STATUS.md`. Verify each fix individually. Run the single test before and after.

### 5. Fixture Fixes Need Real Traces
If a fixture is broken, the fix MUST come from: (a) a real device trace, (b) the decompiled .so binary, or (c) PM3 source code at `https://github.com/iCopy-X-Community/icopyx-community-pm3`. Never guess PM3 response formats.

### 6. Sequential Fixture Responses Are Critical
Write flows call the SAME PM3 command multiple times with different expected responses (e.g., `lf t55xx detect` returns different Block0 values after wipe vs. after clone). These must be sequential lists in the fixture:
```python
'lf t55xx detect': [
    (0, '... Block0 000880E0 ...'),   # after wipe
    (0, '... Block0 00148040 ...'),   # after clone
]
```

### 7. Block Write Order (MFC)
Confirmed by `full_read_write_trace_20260327.txt`: Data blocks written in REVERSE order (60→0 for MF4K, highest first). Trailers written in reverse order after data blocks. UID (block 0) written last.

### 8. LF DRM Password Pattern
ALL LF clones use: `wipe → clone → b7=20206666 → b0 config with pwd bit → detect p 20206666`. Confirmed in `awid_write_trace_20260328.txt` and `fdxb_t55_write_trace_20260328.txt`.

### 9. PWR Key Goes Through onKeyEvent
As discovered in the Read flow: PWR dispatches to each activity's `onKeyEvent()`, not a global `finish_activity()`. The `_COMPAT_MAP` in `keymap.py` now includes `'PWR_PRES!'`. Each activity must handle PWR in its `onKeyEvent`.

### 10. Canvas Cleanup Between States
When transitioning between WRITING→SUCCESS→VERIFYING→RESULT, clear ALL canvas items from previous states. ProgressBar.hide(), Toast.cancel(), template.dedraw(canvas).

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/*.txt`
2. Real activity traces: `docs/Real_Hardware_Intel/trace_*.txt` and `docs/Real_Hardware_Intel/*_write_trace*.txt`
3. Real screenshots: `docs/Real_Hardware_Intel/Screenshots/*.png` and `docs/Real_Hardware_Intel/write_flow_20260326/`
4. UI Mapping: `docs/UI_Mapping/16_write_tag/README.md`
5. **NEVER deviate.** Never invent. Never guess. Never "try something".
6. **ALL work must derive from these ground truths.**
7. **EVERY action** must cite its ground-truth reference.
8. **Before writing code:** Does this come from ground truth? If not, don't.
9. **After writing code:** Audit — does this come from ground truth? If not, undo.
10. **Use existing launcher tools** — `tools/launcher_current.py` — Do not roll your own infrastructure.

If no ground truth exists, ask the user before proceeding.

### Supplementary ground truth
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` — use when trace responses are truncated (e.g., `cmdlf.c` for `lf t55xx` commands, `cmdhfmf.c` for `hf mf wrbl` output)
- QEMU API dump: `archive/root_old/qemu_api_dump_filtered.txt` — method signatures
- Live trace methodology: `docs/HOW_TO_RUN_LIVE_TRACES.md` — deploy tracer to real device (tunnel on port 2222, `root:fa`)

## Write flow architecture

### Activity stack transitions

```
ReadActivity (state: read_success, M2="Write")
    ↓ (user presses M2 → _launchWrite())
WarningWriteActivity (stack depth +1)
    ├─ Title: "Data ready!"
    ├─ Content: tag type tips + "place empty tag" message
    ├─ M1: "Cancel" → finish()
    ├─ M2: "Write" → _confirm_write() → finish with result
    └─ PWR: finish()
        ↓ (user presses M2)
WriteActivity (stack depth +1, replaces WarningWrite)
    ├─ IDLE: M1="Write", M2="Verify"
    ├─ WRITING: progress bar "Writing...", buttons disabled
    │   └─ write.write(infos, callback) on background thread
    │   └─ PM3 commands: scan dest → fchk → wrbl × N → verify inline
    ├─ WRITE_SUCCESS: toast "Write successful!", M1="Verify", M2="Rewrite"
    ├─ WRITE_FAILED: toast "Write failed!", M1="Verify", M2="Rewrite"
    ├─ VERIFYING: progress bar "Verifying...", buttons disabled
    │   └─ write.verify(infos, callback) on background thread
    ├─ VERIFY_SUCCESS: toast "Verification successful!", M1="Verify", M2="Rewrite"
    └─ VERIFY_FAILED: toast "Verification failed!", M1="Verify", M2="Rewrite"
```

**Ground Truth**: `full_read_write_trace_20260327.txt` lines 72-103, `read_write_activity_trace_20260327.txt`

### WriteActivity state machine

| State | M1/OK | M2 | PWR |
|-------|-------|----|-----|
| IDLE | startWrite() | startVerify() | finish() |
| WRITING | disabled | disabled | finish() |
| WRITE_SUCCESS | startWrite() | startVerify() | finish() |
| WRITE_FAILED | startWrite() | startVerify() | finish() |
| VERIFYING | disabled | disabled | finish() |
| VERIFY_SUCCESS | startWrite() | startVerify() | finish() |
| VERIFY_FAILED | startWrite() | startVerify() | finish() |

**Ground Truth**: `docs/UI_Mapping/16_write_tag/README.md`, `activity_main_strings.txt` — WriteActivity.setBtnEnable, WriteActivity.startWrite, WriteActivity.startVerify

### Write algorithms by tag family

**MFC (MF1K, MF4K, MF Mini, MF Plus):** Scan dest → UID check → load keys → fchk → wrbl blocks (reverse order) → wrbl trailers (reverse) → inline verify
- Ground Truth: `full_read_write_trace_20260327.txt` lines 78-95

**LF (T55xx-based: EM410x, HID, FDX-B, AWID, etc.):** Wipe → clone → DRM password (b7=20206666, b0 config) → detect verify → content verify
- Ground Truth: `awid_write_trace_20260328.txt`, `fdxb_t55_write_trace_20260328.txt`

**Ultralight/NTAG:** Select → csetuid (if different) → wrbl × N → verify
- Ground Truth: `hfmfuwrite_strings.txt`, `hfmfuwrite_ghidra_raw.txt`

**iCLASS:** Key calc (Elite) → wrbl blocks → rdbl verify
- Ground Truth: `iclasswrite_strings.txt`, `iclasswrite_ghidra_raw.txt`

**ISO15693:** Restore from dump → csetuid → verify
- Ground Truth: `hf15write_strings.txt`, `hf15write_ghidra_raw.txt`

**EM4305:** Write 16 blocks → read-back verify (regex `| HEX -`)
- Ground Truth: `lfwrite_strings.txt`

## The 13 false positive scenarios (YOUR PRIMARY TASK)

From `docs/WRITE-TESTS-STATUS.md`:

### Group 1: Fixture data incomplete — .so shows "Write failed!" instead of "Write successful!"

| Scenario | Root Cause | Fix |
|----------|-----------|-----|
| `write_em4305_dump_success` | No `lf em 4x05_read` fixture for verify phase — readback empty | Add sequential `lf em 4x05_read` responses matching written blocks (16 blocks, `\| HEX -` format) |
| `write_iclass_elite_success` | Generic `hf iclass rdbl` returns block-06 data for ALL blocks | Add per-block `rdbl b XX k ELITE_KEY` patterns for blocks 6-18 |
| `write_iclass_key_calc_success` | Same generic rdbl issue | Same per-block rdbl fix |
| `write_iclass_legacy_success` | Same generic rdbl issue | Same per-block rdbl fix |

### Group 2: Missing toast validation (arg 4 empty)

| Scenario | Fix |
|----------|-----|
| `write_em4305_dump_fail` | Add arg 4 `"toast:Write failed"` |
| `write_iclass_key_calc_fail` | Add arg 4 |
| `write_iclass_tag_select_fail` | Add arg 4 |
| `write_iso15693_restore_fail` | Add arg 4 |
| `write_iso15693_uid_fail` | Add arg 4 |
| `write_mf4k_gen1a_success` | Add arg 4 `"toast:Write failed"` (known .so limitation for 4K Gen1a) |

### Group 3: Wrong toast text

| Scenario | Shows | Should Show | Fix |
|----------|-------|-------------|-----|
| `write_lf_em410x_verify_fail` | "Write failed!" | "Verification failed!" | Sequential `lf t55xx detect` + `lf sea` responses, remove `no_verify`, add Phase 5 |
| `write_mf1k_standard_partial` | "Write failed!" | "Write successful!" (partial) | Sequential `hf mf wrbl` responses: some isOk:01, some isOk:00 |

### Group 4: Wrong navigation

| Scenario | Fix |
|----------|-----|
| `write_mf_possible_7b_success` | Change `TAG_TYPE = 44` → `TAG_TYPE = 42` |

## Test infrastructure

### 5-phase write test pipeline (`write_common.sh`)

1. **Phase 1**: Navigate to Read Tag → select tag type → OK starts scan+read
2. **Phase 2**: Wait for `M2:Write` (read complete) → TOAST_CANCEL → generate dump file
3. **Phase 3**: M2 → WarningWriteActivity → wait `title:Data ready` → M2 → WriteActivity
4. **Phase 4**: Wait `M2:Rewrite` (write complete) → validate `write_toast_trigger` (arg 4)
5. **Phase 5**: (if not `no_verify`) → TOAST_CANCEL → M1 (verify) → wait `final_trigger` (arg 2)

### Running tests

```bash
# Single test locally
TEST_TARGET=current SCENARIO=write_mf1k_standard_success FLOW=write \
  bash tests/flows/write/scenarios/write_mf1k_standard_success/write_mf1k_standard_success.sh

# Full parallel suite on remote (48-core server)
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/write/test_writes_parallel.sh 16'

# Results
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cat ~/icopy-x-reimpl/tests/flows/_results/current/write/scenario_summary.txt'
```

### Framework constants

```
PM3_DELAY=0.5
BOOT_TIMEOUT=600
READ_TRIGGER_WAIT=200
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
WARNING_TRIGGER_WAIT=30
```

## Environment

- Branch: `feat/ui-integrating` at latest commit
- QEMU rootfs: `/mnt/sdcard/root2/root/`
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`, sudo: `proxmark`, 48 cores)
- Real device SSH: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be established by user)
- Run single test: `TEST_TARGET=current SCENARIO=<name> FLOW=write bash tests/flows/write/scenarios/<name>/<name>.sh`
- Run parallel on remote: `test_writes_parallel.sh 16`

## Working flows (don't break these)

- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 63/63 PASS (but 13 are false positives — this is your task)

## PM3 command reference for write flow

### MFC Write
- `hf mf wrbl {block} {keytype} {key_hex} {data_hex}` — Write single block. Response: `isOk:01` (success) or `isOk:00` (fail)
- `hf mf csetuid {uid_hex}` — Magic write UID (Gen1a only)
- `hf mf cload b {keysfile}` — Load keys
- `hf mf fchk {type} {keysfile}` — Find all sector keys

### LF T55xx
- `lf t55xx wipe [p {password}]` — Erase all blocks
- `lf t55xx write b {block} d {data} [p {password}]` — Write block
- `lf t55xx detect [p {password}]` — Detect, read Block0
- `lf t55xx restore f {dumpfile}` — Restore from dump
- `lf {type} clone {data}` — Type-specific clone (em410x, hid, fdxb, awid, etc.)

### iCLASS
- `hf iclass wrbl {block} {key} {data}` — Write block
- `hf iclass rdbl b {block} k {key} [e]` — Read block (verify)
- `hf iclass calcnewkey` — Elite key calculation

### ISO15693
- `hf 15 restore f {dumpfile}` — Restore from dump. Keywords: "Write OK" (success), NOT "restore failed"
- `hf 15 csetuid {new_uid}` — Change UID

### Ultralight/NTAG
- `hf mfu wrbl {block} {data}` — Write block
- `hf mfu csetuid {uid}` — Set NFCID
- `hf mfu restore` — Restore from dump

### EM4305
- `lf em 4x05_write {block} {data}` — Write block (16 blocks total)
- `lf em 4x05_read {block}` — Read block. Response format: `Block N | AABBCCDD - r/w`

## Known limitations

### MIFARE Plus 2K detection (SAK 0x08)

A MIFARE Plus 2K card in SL1 (Security Level 1) mode has SAK=0x08 — identical to MIFARE Classic 1K. The PM3 `hf 14a info` response lists BOTH as "Possible types". The iCopy-X `hf14ainfo.so` parser matches `"MIFARE Classic 1K"` first and returns type 1 (M1_S50_1K_4B). There is no way to distinguish Plus 2K SL1 from Classic 1K at the SAK/ATQA level.

**Ground truth**: PM3 source `cmdhf14a.c` line 1468 — SAK 0x08 bitmask check outputs "MIFARE Classic 1K / Classic 1K CL2" + "MIFARE Plus 2K / Plus EV1 2K". `hf14ainfo.so` keyword priority: `"MIFARE Classic 1K"` > `"MIFARE Plus"`.

A Plus 2K in **SL3 mode** (SAK=0x10) would be detectable as type 26 (M1_PLUS_2K) via the `"MIFARE Plus"` keyword. We don't have a SL3 sample card to test.

**Status**: Cannot fix without firmware change. The write/read tests for Plus 2K SL1 accept type 1 (Classic 1K) as correct.

## Known type numbering differences

ReadListActivity uses one set of type IDs (from `tagtypes.getReadable()`), but `scan.so` returns a DIFFERENT numbering in `scan_cache.type`. Example:

| Card | ReadListActivity type | scan.so type | Evidence |
|------|----------------------|--------------|----------|
| MIFARE Plus 2K | 26 | **43** | `read_mf_plus_2k_all_keys` state dumps show `scan_cache.type=43` across all 7 states |

The write test `write_mf_plus_2k_success` had post-validation checking `scan_cache.type == '26'` — this was wrong. Fixed to `'43'` based on ground truth from the read flow (99/99 PASS).

**Rule**: When validating scan_cache types, use the value scan.so ACTUALLY returns (from state dumps), not the ReadListActivity menu type ID. These are different numbering systems.

## Definition of done

1. All 13 false positive scenarios have correct toast validation (arg 4 in .sh file)
2. All 13 false positive scenarios produce the CORRECT toast from write.so (fixtures fixed with ground-truth evidence)
3. All 63 write tests are TRUE passes — correct toast content verified, not just state count
4. No regressions: Scan 45/45, Read 99/99, Volume 7/7, Backlight 7/7 still pass
5. Every fixture fix cites its ground-truth source (trace, decompiled binary, or PM3 source)

## Approach

For each of the 13 false positive scenarios:

1. **Read the scenario's fixture.py** and `.sh` file
2. **Identify the root cause** from `docs/WRITE-TESTS-STATUS.md`
3. **Find the ground truth** — real trace, decompiled .so, or PM3 source
4. **Fix the fixture** — add sequential responses, per-block data, or correct command patterns
5. **Fix the .sh file** — add arg 4 toast validation if missing
6. **Run the single test** — verify it passes with correct toast
7. **Run the full suite** — verify no regressions

**DO NOT batch-fix all 13 at once.** Fix one, verify, then move to the next. Each fixture fix must be individually justified with a ground-truth citation.
