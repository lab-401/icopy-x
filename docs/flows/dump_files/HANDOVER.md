# Dump Files Flow -- Phase 2 Handover: UI Integration

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task

Implement the **Dump Files** flow (`CardWalletActivity` + `ReadFromHistoryActivity`) in Python so that it matches the original firmware's behavior. **Phase 1 is COMPLETE** -- 35 test scenarios are built, validated, and passing against the original `.so` firmware under QEMU. Your job is Phase 2.

---

## TWO ABSOLUTE LAWS

### LAW 1: NO MIDDLEWARE
CardWalletActivity is a **file browser**. ReadFromHistoryActivity is a **file parser + sub-activity launcher**. Neither sends PM3 commands. Neither interprets dump file contents beyond filename parsing. All RFID logic lives in the `.so` modules (write.so, scan.so, etc.) which are called by WriteActivity, SimulationActivity, etc. -- activities that ALREADY WORK.

If you find yourself writing PM3 command strings, tag-specific RFID logic, or protocol-level code in CardWalletActivity or ReadFromHistoryActivity -- **STOP. You are violating Law 1.**

### LAW 2: NO CHANGING SCENARIOS
The 35 test scenarios are **IMMUTABLE**. They are the acceptance criteria. They were built from ground truth (real device traces, decompiled .so strings, real screenshots) and validated against the original firmware (35/35 PASS). You may NOT modify scenario scripts, fixtures, triggers, or thresholds. If a scenario fails with `--target=current`, the bug is in YOUR implementation, not in the scenario.

If you believe a scenario is wrong, present evidence and ask the user. Never silently change a test to make it pass.

---

## What Phase 2 IS and IS NOT

**Phase 2 IS**: Crafting an open-source Python UI implementation of the Dump Files workflow that faithfully reproduces the original firmware's behavior, and therefore passes all 35 scenarios.

**Phase 2 IS NOT**: "Making tests pass." Do not hack, shortcut, or reverse-engineer the test expectations. Implement the real behavior. The tests pass as a CONSEQUENCE of correct implementation.

---

## Phase 1 Results (COMPLETE -- DO NOT REPEAT)

**35/35 PASS** with `--target=original` (sequential, 1 worker, 1655s).

```
tests/flows/dump_files/scenarios/
  dump_types_empty          dump_types_single         dump_types_multi
  dump_types_scroll         dump_files_browse         dump_files_scroll
  dump_files_empty_type     dump_files_show_date      dump_delete_confirm_yes
  dump_delete_confirm_no    dump_delete_pwr_cancel    dump_delete_last_file
  dump_detail_mf1_1k        dump_detail_mf1_4k        dump_detail_mf1_mini
  dump_detail_t55xx         dump_detail_lf_id          dump_detail_uid_based
  dump_pwr_type_list        dump_pwr_file_list         dump_pwr_tag_info
  dump_pwr_data_ready       dump_pwr_warning_write     dump_sim_hf
  dump_sim_lf               dump_write_mf1k_success    dump_write_mf1k_fail
  dump_write_mf1k_gen1a     dump_write_mf1k_verify_success
  dump_write_mf1k_verify_fail  dump_write_lf_success
  dump_write_mfu_success    dump_write_cancel
  dump_write_t55xx_success  dump_write_t55xx_fail
```

---

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/HOW_TO_INTEGRATE_A_FLOW.md` -- **READ FIRST.** Integration methodology, 4-layer architecture, JSON UI system.
2. `docs/flows/dump_files/README.md` -- **THE PRIMARY SPEC.** Complete specification with TRACE CORRECTIONs.
3. `docs/Real_Hardware_Intel/trace_dump_files_20260403.txt` -- **CANONICAL TRACE #1.** 270 lines: MF1K standard write, FDX clone, MFU restore, MF1K Gen1a write.
4. `docs/Real_Hardware_Intel/trace_dump_files_em410x_t55xx_write_20260405.txt` -- **CANONICAL TRACE #2.** 305 lines: EM410x write, T55xx restore. Includes T55xx scan cache format and bundle format.
5. Post-mortems (read for patterns, not for dump-files-specific details):
   - `docs/flows/erase/ui-integration/README.md`
   - `docs/flows/write/ui-integration/README.md`
   - `docs/flows/auto-copy/ui-integration/README.md`
   - `docs/flows/simulate/ui-integration/README.md`

---

## Critical discoveries from Phase 1 (GROUND TRUTH)

These were discovered by QEMU tracing and real device instrumentation during Phase 1. They OVERRIDE any conflicting information in the README or UI Mapping docs.

### Type List behavior
- The original firmware shows **ALL 28 type categories** regardless of whether their directories contain files. It is NOT filtered to only types with dumps.
- **5 items per page** under QEMU (not 4 as documented from real device screenshots -- resolution difference).
- **Fixed type order** (0-indexed): Viking=0, Ultralight & NTAG=1, Visa2000=2, HID Prox=3, Mifare Classic=4, Animal ID(FDX)=5, Paradox=6, Jablotron=7, Pyramid=8, Noralsy=9, NexWatch=10, Securakey=11, Felica=12, KERI=13, IO Prox=14, AWID=15, Legic Mini 256=16, T5577 ID=17, 15693 ICODE/STSA=18, EM410x ID=19, PAC=20, GProx II=21, NEDAP=22, GALLAGHER=23, Presco=24, Indala=25, iClass=26, EM4X05=27.
- **No M1/M2 softkey buttons** on the Type List screen. Only UP/DOWN/OK/PWR are active.
- Title: `"Dump Files"` with page indicator `"1/6"` at top-right.
- Selecting a type with no files shows inline tip: `"No dump info. \nOnly support:\n.bin .eml .txt"`.

### File List behavior
- **M1 ("Details") toggles `is_dump_show_date`** -- re-renders the file list showing creation dates (`%Y-%m-%d %H:%M:%S`) instead of parsed filenames. M1 does NOT push ReadFromHistoryActivity.
- **OK pushes `ReadFromHistoryActivity(file_path_with_extension)`** -- this is the only way to enter Tag Info.
- **M2 enters Delete Confirmation** -- toast "Delete?" with M1="No", M2="Yes".
- Softkeys: M1="Details" / M2="Delete".
- Title remains `"Dump Files"` (not the type name).

### ReadFromHistoryActivity behavior
- Bundle = **file path string WITH extension** (e.g., `/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11.eml`).
- Calls `scan.setScanCache(parsed_info)` to populate scan cache before any write/sim.
- Title: `"Tag Info"`. Softkeys: M1="Simulate" / M2="Write".
- M1 → `sim_for_info()` → push SimulationActivity.
- M2 → `write_file_base()` or `write_id()` or `write_lf_dump()` → push WarningWriteActivity.
- PWR → `finish()` → back to CardWalletActivity file list.

### Bundle formats (from traces)
- **HF types** (MF1, MFU, iClass): File path string WITHOUT extension → WarningWriteActivity.
  - Example: `'/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11'`
- **LF ID types** (EM410x, AWID, FDX): Scan cache dict → WarningWriteActivity.
  - Example: `{'data': '06007416C2', 'raw': '06007416C2', 'found': True, 'type': 8}`
- **T55xx dumps**: File path dict → WarningWriteActivity.
  - Example: `{'file': '/mnt/upan/dump/t55xx/T55xx_00148040_00000000_00000000_1.bin'}`

### Scan cache formats (from traces)
- **MF1**: `{"uid": "'B7785E50'", "len": "4", "sak": "'08'", "atqa": "'0004'", "found": "True", "type": "1"}`
- **EM410x**: `{"data": "'06007416C2'", "raw": "'06007416C2'", "found": "True", "type": "8"}`
- **MFU**: `{"uid": "'00000000000000'", "found": "True", "type": "2"}`
- **T55xx**: `{"b0": "'00148040'", "modulate": "'--------'", "chip": "'T55xx/Unknown'", "found": "True", "type": "23"}`

### Write dispatch methods
| Method | Tag Types | Bundle to WarningWriteActivity |
|--------|-----------|-------------------------------|
| `write_file_base()` | MF1, MFU, iClass, Felica, Legic, HF14A, ICODE | File path string (no extension) |
| `write_id()` | EM410x, AWID, FDX, HID, Indala, Keri, Viking, etc. | Scan cache dict |
| `write_lf_dump()` | T55xx | File path dict `{'file': path}` |

### Parse methods and regex patterns
| Method | Regex (from binary L21251-22113) | Tag Types |
|--------|----------------------------------|-----------|
| `parseInfoByM1FileName` | `M1-(\S+)-(\S+)_([A-Fa-f\d]+)_(\d+).*\.(.*)` | MF1 (1K, 4K, Mini) |
| `parseInfoByIDFileName` | `(\S+)_(\S+)_(\S+)_(\S+)_(\d+).*\.(.*)` (4-field) or `(\S+)_(\S+)_(\d+).*\.(.*)` (2-field) | EM410x, AWID, HID, etc. + iClass |
| `parseInfoByT55xxInfoFileName` | `(\S+)_(\S+)_(\S+)_(\S+)_(\d+).*\.(.*)` (4-field, same as ID) | T55xx |
| `parseInfoByUIDInfoFileName` | `(\S+)_(\S+)-(\S+)_(\d+).*\.(.*)` | MFU, Felica, ICODE, HF14A |
| `parseInfoByLegicInfoFileName` | `(\S+)_(\S+)_(\d+)\.(.*)` | Legic |

### Real filename examples (from device dumps)
```
mf1:     M1-1K-4B_DAEFB416_1.bin, M1-4K-4B_E93C5221_1.bin, M1-Mini-4B_8800E177_1.bin
mfu:     M0-UL_00000000000000_1.bin
t55xx:   T55xx_00148040_00000000_00000000_1.bin  (4 underscore-separated fields!)
em410x:  EM410x-ID_06007416C2_1.txt
fdx:     FDX-ID_0060-030207938416_4.txt
iclass:  Iclass-Elite_4A678E15FEFF12E0_1.bin
felica:  FeliCa_010108018D162D1A_1.txt
awid:    AWID-ID_FC123-CN4567_1.txt
```

### WarningWriteActivity buttons
- WarningWriteActivity shows: title="Data ready!", M1="Cancel" (or "Watch"), M2="Write".
- M2 → finishes WarningWriteActivity → ReadFromHistoryActivity.onActivity pushes WriteActivity.
- There is NO separate "Data Ready" state inside ReadFromHistoryActivity -- WarningWriteActivity IS "Data Ready".

### Delete confirmation
- Toast: "Delete?", M1="No" / M2="Yes".
- PWR from delete confirmation goes back to TYPE LIST (not file list). PWR is "universal back" and pops the entire activity context.
- M1="No" goes back to file list.
- Deleting the last file in a category should return to the type list.

### Verify mode limitation
- The M1="Verify" button in WriteActivity uses cached write data for verification. Fixture-based forced failures are not possible -- the verify always succeeds when the write succeeds. This is a known limitation documented in `dump_write_mf1k_verify_fail`.

---

## Implementation gaps (YOUR WORK)

### Gap 1: Type List state
**Current**: CardWalletActivity takes `dump_type`/`dump_dir` in bundle and shows flat file list.
**Required**: On launch with no bundle, show ALL 28 type categories, 5 items/page under QEMU.

### Gap 2: ReadFromHistoryActivity (6 missing methods)
**Current**: 3-method stub.
**Required**: `get_type()`, `get_info()`, `onData()`, `sim_for_info()`, `write_file_base()`, `write_id()`, `write_lf_dump()`, proper `onKeyEvent`.

### Gap 3: Delete Confirmation toast
**Current**: Immediate delete on M2.
**Required**: "Delete?" toast overlay with M1="No" / M2="Yes".

### Gap 4: Sub-activity wiring
**Current**: OK/M1 in file list calls internal `_showDetail()`.
**Required**: OK pushes ReadFromHistoryActivity. M1 toggles date display.

### Gap 5: Bundle format routing
**Current**: No bundle passing.
**Required**: HF=path string, LF ID=scan cache dict, T55xx=file dict.

### Gap 6: Seed dump files
**DONE** in Phase 1. `tools/seed_dump_files.py` uses real device filename formats.

### Gap 7: JSON state machine
**Current**: 4 states in `dump_files.json`.
**Required**: Add type_list state. Remove detail_view (replaced by ReadFromHistoryActivity push).

---

## How to use QEMU tracing for heuristics

When implementing a specific behavior and you're unsure of the exact heuristic, you can run the **original** firmware under QEMU and observe what it does:

```bash
# Boot QEMU with original target, seed specific files, navigate
export DISPLAY=:50
Xvfb :50 -screen 0 240x240x24 -ac +render -noreset &>/dev/null &
python3 tools/seed_dump_files.py --type mf1
TEST_TARGET=original python3 tools/launcher_current.py \
  --fixture /path/to/minimal_fixture.py \
  --keys "GOTO:1,SLEEP:2,STATE_DUMP,DOWN,DOWN,DOWN,DOWN,OK,SLEEP:2,STATE_DUMP,FINISH"
```

This is your reference implementation. If your Python code doesn't produce the same state dumps as the original, your implementation is wrong. The fixture matcher uses **longest-match-first substring matching** (`sorted by len desc, pat in cmd`).

---

## Running tests

```bash
# Single scenario
TEST_TARGET=current SCENARIO=dump_types_empty FLOW=dump_files \
  bash tests/flows/dump_files/scenarios/dump_types_empty/dump_types_empty.sh

# Full suite sequential (for development -- avoids race conditions on /mnt/upan/dump/)
TEST_TARGET=current bash tests/flows/dump_files/test_dump_files_parallel.sh 1

# Full suite on remote (48 cores, max 9 workers -- BUT dump_files has shared filesystem race)
# Use 1 worker for dump_files to avoid seed file conflicts
sshpass -p proxmark rsync -az --delete --exclude='.git' --exclude='tests/flows/_results' \
  --exclude='__pycache__' --exclude='.development assistant' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/dump_files/test_dump_files_parallel.sh 1'
```

**IMPORTANT**: Dump files scenarios share `/mnt/upan/dump/`. Running with >1 worker causes race conditions where one worker's seed cleanup deletes another worker's files. Always use 1 worker for reliable results.

---

## Key files to modify

| File | What to change |
|------|----------------|
| `src/lib/activity_main.py` | CardWalletActivity (L5829+), ReadFromHistoryActivity (L6295+) |
| `src/screens/dump_files.json` | Add type_list state, fix softkeys |
| `tools/seed_dump_files.py` | Already done (Phase 1) |

---

## Definition of done

1. `TEST_TARGET=current bash tests/flows/dump_files/test_dump_files_parallel.sh 1` → **35/35 PASS**
2. No regressions on existing suites (Scan 45, Read 99, Write 63, Auto-Copy 52, Simulate 32, Erase 10, Sniff 28)
3. Every implementation decision cites a ground truth source (trace line, screenshot, binary string)
4. NO middleware -- CardWalletActivity/ReadFromHistoryActivity send ZERO PM3 commands
5. NO scenario modifications

---

## Environment

- Branch: `bug/ui-integrating-sniff` at commit `774bd6b`
- Remote: `qx@178.62.84.144` (password: `proxmark`, 48 cores)
- Real device: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be up)
