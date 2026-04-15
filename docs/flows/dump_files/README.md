# Dump Files Flow — UI Integration Specification

You are continuing work on the iCopy-X open-source firmware reimplementation.

## Your task
Integrate the **Dump Files** flow — `CardWalletActivity` (menu item #2) must present the full 5-state file browser, with working Type List, File List, Tag Info detail, Delete confirmation, Data Ready prompt, and sub-activity launches for **Simulate** and **Write**. The current implementation is a simplified 2-mode stub (list + detail) that lacks the Type List, proper Tag Info rendering, Delete confirmation toast, Data Ready state, and Simulate/Write sub-activity integration.

**Current status:** `CardWalletActivity` exists in `src/lib/activity_main.py` (lines 5294-5466) with 14 unit tests passing in `tests/ui/activities/test_dump_files.py`. However:

1. **No Type List (State 1):** The original firmware shows a categorized type list (e.g., "Mifare Classic", "T5577 ID", "Animal ID(FDX)") — only types with files are shown. The current implementation skips this and goes directly to a flat file list from a `dump_dir` bundle parameter.

2. **No proper Tag Info (State 3):** The original firmware's `showDetail` calls type-specific parse methods (`parseInfoByM1FileName`, `parseInfoByIDFileName`, `parseInfoByT55xxInfoFileName`, `parseInfoByUIDInfoFileName`, `parseInfoByLegicInfoFileName`) to render rich tag metadata. Softkeys are "Simulate" / "Write". The current implementation shows a generic `File: / UID: / Format: / Size:` view with "Back" / "Delete" softkeys.

3. **No Delete Confirmation (State 2b):** The original firmware shows a "Delete?" toast overlay with "No" / "Yes" softkeys. The current implementation deletes immediately on M2 in detail mode.

4. **No Data Ready (State 4):** The original firmware transitions to a "Data ready!" screen with "Watch" / "Write" softkeys before launching WriteActivity. This state is entirely missing.

5. **No Simulate/Write sub-activity integration:** The original firmware's Tag Info view launches `SimulationActivity` (M1) and transitions through `WarningWriteActivity` -> `WriteActivity` (M2 from Data Ready). None of this is wired.

6. **No integration flow tests:** Only unit tests exist. No QEMU-based flow tests that navigate the full Type List -> File List -> Tag Info -> Write/Simulate pipeline.

Your job is to:
- Implement the missing states to match the original firmware
- Build QEMU integration flow tests covering all states and transitions
- Ensure all existing unit tests and regression suites still pass

## Essential reading (READ ALL BEFORE ACTING)

1. `docs/flows/auto-copy/ui-integration/README.md` — **READ THIS FIRST.** Complete post-mortem of the Auto-Copy flow integration. Contains the correct architecture for pushing sub-activities (WarningWriteActivity -> WriteActivity), Scanner/Reader API patterns, no-middleware rules, and DRM handling. The Dump Files write sub-flow follows the SAME activity stack pattern as Auto-Copy.

2. `docs/flows/scan/ui-integration/README.md` — Scan flow post-mortem. Same ground truth rules apply.

3. `docs/flows/read/ui-integration/README.md` — Read flow post-mortem. The read-to-write transition (`_launchWrite()` at `activity_read.py:769`) is the same pattern CardWalletActivity must follow.

4. `docs/UI_Mapping/03_dump_files/README.md` — **THE PRIMARY SPEC.** Exhaustive UI specification for CardWalletActivity: all 5 states, key bindings, parse methods, pagination, file system layout, flow diagram, screenshot evidence. **This is your blueprint.**

5. `docs/HOW_TO_BUILD_FLOWS.md` — Methodology, fixture structure, keyword matching, logic tree extraction.

6. Real hardware screenshots (7 files):
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_1_1.png` — Type list: 4 categories (Mifare Classic, Animal ID(FDX), T5577 ID, AWID ID)
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_1_10_1.png` — File list page 1/10 (4 items per page)
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_1_10_2.png` — File list page 2
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_1_10_3.png` — File list page 3
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_1_10_4.png` — File list page 4
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_delete_confirm_1.png` — Delete confirmation transition frame
    - `docs/Real_Hardware_Intel/Screenshots/dump_files_delete_confirm_2.png` — Delete confirmation with "No" / "Yes" softkeys

7. V1090 captures:
    - `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Dump-Types.png` — "Dump Files 1/1" with 2 types
    - `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Dump-Types-Files.png` — "Dump Files 1/5" file list
    - `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Dump-Types-Files-Info.png` — Tag Info view: MIFARE, M1 Mini 0.3K, UID, SAK, ATQA
    - `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Dump-Types-Files-Info-Write.png` — Data Ready: "Data ready!" with "Watch" / "Write"
    - `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Home-Dump.png` — Main menu with "Dump Files" highlighted

8. Decompiled binaries:
    - `decompiled/activity_main_ghidra_raw.txt` — CardWalletActivity method signatures and string references (v1.0.80 binary; v1.0.90 method bodies NOT decompiled — use string refs + screenshots as ground truth)
    - `decompiled/appfiles_ghidra_raw.txt` — PATH_DUMP_* constants (lines 384-504): all 28+ dump directory paths

9. Extracted .so strings:
    - `docs/v1090_strings/activity_main_strings.txt` — CardWalletActivity methods: `text_card_wallet`, `is_dump_del_mode`, `dump_selection`, `setBtn2ListMode`, `setBtn2DelMode`, `delete_confirm`, `no_tag_history`, `text_data_ready`, `place_empty_tag`, `text_type_tips`
    - `docs/v1090_strings/appfiles_strings.txt` — Dump directory names and type display strings

10. `src/lib/activity_main.py` — Current CardWalletActivity implementation (lines 5294-5466), plus WarningWriteActivity (lines 3001-3127), WriteActivity (lines 3151-3436), SimulationActivity.

11. `src/screens/dump_files.json` — Current JSON UI state machine (4 states: file_list, file_list_empty, detail_view, delete_confirm). **Needs expansion** to include type_list, tag_info, data_ready states.

12. `tests/ui/activities/test_dump_files.py` — 14 existing unit tests.

13. `tools/seed_dump_files.py` — Creates test dump files for all 27+ tag types.

14. Simulate flow infrastructure:
    - `tests/flows/simulate/includes/sim_common.sh` — Simulate test common infrastructure (reference for how SimulationActivity is tested)
    - `tests/flows/simulate/scenarios/` — 32 simulate scenarios

15. Write flow infrastructure:
    - `docs/flows/write/` — Write flow specification and test infrastructure
    - `tests/flows/write/` — 63 write test scenarios

## CRITICAL — DRM SMOKE TEST

**If the Write sub-flow from Dump Files produces silent failures (write.so returning -9, no PM3 commands), ALWAYS check DRM first:**

```bash
# Check launcher log for this line:
[OK] tagtypes DRM passed natively: 40 readable types    # MUST see this
[WARN] tagtypes DRM failed — falling back to bypass      # THIS MEANS WRITES WILL FAIL
```

**Root cause**: `hfmfwrite.tagChk1()` performs an AES-based DRM check using `/proc/cpuinfo` Serial. If wrong, tagChk1 returns False -> `write_common()` returns -9 immediately — no fchk, no wrbl, "Write failed!" with zero PM3 write commands.

**Correct serial**: `02c000814dfb3aeb` (in `launcher_current.py` cpuinfo mock)

**Reference**: `docs/DRM-KB.md`, `docs/DRM-Issue.md`, `docs/flows/auto-copy/ui-integration/README.md` Section 4 (DRM)

## Critical lessons from previous flow integrations (DO NOT REPEAT THESE MISTAKES)

### 1. Activity Stack Architecture (from Auto-Copy post-mortem)
CardWalletActivity does NOT handle write internally. The real firmware pushes sub-activities:
```
CardWalletActivity (Tag Info, M2="Write")
    -> Data Ready state (M2="Write")
        -> WarningWriteActivity (activity stack push)
            -> WriteActivity (activity stack push)
```
**Ground Truth**: `docs/flows/auto-copy/ui-integration/README.md` Section 3.4 — AutoCopy pushes WarningWriteActivity, not internal _startWrite(). CardWalletActivity follows the same pattern.

### 2. template.so Renders Tag Info — NOT Python
The Tag Info detail view (State 3) shows rich tag metadata. For Mifare Classic dumps, this comes from the binary's `parseInfoByM1FileName` method and template rendering — NOT from Python string formatting. However, since we don't have the v1.0.90 CardWalletActivity method bodies decompiled, we must implement parse methods in Python based on the screenshot evidence and string patterns.

### 3. NEVER Invent Middleware
If you find yourself writing tag-specific RFID logic, STOP — it belongs in .so modules. CardWalletActivity is a file browser that launches sub-activities. It should NOT contain PM3 command logic.

### 4. NEVER Mass-Modify Fixtures
**BEFORE MODIFYING ANY FIXTURES — REQUEST EXPLICIT CONFIRMATION FROM THE USER.** Verify each fix individually.

### 5. PWR Key Goes Through onKeyEvent
As discovered in the Read flow: PWR dispatches to each activity's `onKeyEvent()`, not a global `finish_activity()`. CardWalletActivity must handle PWR in every state (Type List -> exit, File List -> back to Type List, Tag Info -> back to File List, Delete Confirm -> cancel, Data Ready -> back to Tag Info).

### 6. 4 Items Per Page (Exception)
CardWalletActivity uses **4 items per page**, NOT the default 5. Confirmed by all 7 real hardware screenshots showing 4 items per page consistently.

### 7. Only Types With Files Are Shown
The Type List only shows categories that have at least one dump file in their directory. Empty categories are hidden. This requires scanning all 28+ dump directories on startup.

### 8. File Sorting: Newest First
Files within a type category are sorted by creation time (newest first), using the `get_ctime` local function. NOT alphabetical.

### 9. Canvas Cleanup Between States
When transitioning between states, clear ALL canvas items from previous states. ListView.hide(), BigTextListView cleanup, Toast.cancel().

## Ground Truth Rules (ABSOLUTE)

**Only use ground-truth resources:**
1. The original decompiled .so files: `decompiled/*.txt`
2. Real hardware screenshots: `docs/Real_Hardware_Intel/Screenshots/dump_files_*.png` and `v1090_captures/090-Dump-*.png`
3. UI Mapping: `docs/UI_Mapping/03_dump_files/README.md`
4. String extractions: `docs/v1090_strings/activity_main_strings.txt`, `docs/v1090_strings/appfiles_strings.txt`
5. Previous flow post-mortems: `docs/flows/auto-copy/ui-integration/README.md`, `docs/flows/read/ui-integration/README.md`, `docs/flows/scan/ui-integration/README.md`
6. **NEVER deviate.** Never invent. Never guess. Never "try something".
7. **ALL work must derive from these ground truths.**
8. **EVERY action** must cite its ground-truth reference.
9. **Before writing code:** Does this come from ground truth? If not, don't.
10. **After writing code:** Audit — does this come from ground truth? If not, undo.
11. **Use existing launcher tools** — `tools/launcher_current.py` — Do not roll your own infrastructure.

If no ground truth exists, ask the user before proceeding.

### Supplementary ground truth
- PM3 source: `https://github.com/iCopy-X-Community/icopyx-community-pm3` — use for PM3 response formats
- QEMU API dump: `archive/root_old/qemu_api_dump_filtered.txt` — method signatures
- Live trace methodology: `docs/HOW_TO_RUN_LIVE_TRACES.md` — deploy tracer to real device (tunnel on port 2222, `root:fa`)

## TRACE CORRECTION (2026-04-03) — Real Device Trace Overrides Previous Assumptions

**Source**: `docs/Real_Hardware_Intel/trace_dump_files_20260403.txt` — 270 lines, 3 complete write flows through Dump Files.

The real device trace reveals a **fundamentally different architecture** than what the UI mapping spec described. The corrections below are CANONICAL — they override any conflicting information in the UI mapping.

### Correction 1: `ReadFromHistoryActivity` is the intermediary — NOT direct Tag Info

The UI mapping described CardWalletActivity showing Tag Info internally, then transitioning to Data Ready. **The real firmware pushes a SEPARATE activity: `ReadFromHistoryActivity`.**

```
REAL FLOW (from trace):
  CardWalletActivity(bundle=None)           ← from main menu
      ↓ (user selects file)
  ReadFromHistoryActivity(file_path)        ← PUSHED as sub-activity
      ↓ (calls setScanCache, shows tag info, user presses Write)
  WarningWriteActivity(bundle)              ← PUSHED by ReadFromHistoryActivity
      ↓ (user confirms)
  WriteActivity(bundle)                     ← PUSHED via onActivity chain
```

**Evidence** (trace lines 4-12):
```
START(CardWalletActivity, None)
START(ReadFromHistoryActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11.eml')
CACHE: {"uid": "'B7785E50'", "sak": "'08'", "atqa": "'0004'", "found": "True", "type": "1"}
START(WarningWriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11')
FINISH(top=dict d=4)
START(WriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11')
```

### Correction 2: `ReadFromHistoryActivity` has 9 methods (stub has 3)

**Binary methods** (from `activity_main_strings.txt` lines 20951-21020):

| Method | Purpose |
|--------|---------|
| `__init__` | Constructor |
| `onKeyEvent` | Key dispatch |
| `onData` | Data event handler |
| `get_info` | Parse dump file → tag info display |
| `get_type` | Determine tag type from filename |
| `sim_for_info` | Launch simulation with dump data |
| `write_file_base` | Write HF dump (file path based) |
| `write_id` | Write LF ID tag |
| `write_lf_dump` | Write LF dump (T55xx-based) |

**Current stub** (`activity_main.py:5759-5780`) only has `__init__`, `onCreate`, `onKeyEvent` — all minimal. The 6 missing methods contain the core logic.

### Correction 3: Bundle format differs by tag family

**HF tags** — bundle is a **file path string** (without extension):
```
START(WarningWriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11')
START(WriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11')
```

**LF tags** — bundle is a **scan cache dict**:
```
CACHE: {"data": "'0060-030207938416'", "raw": "'0060-030207938416'", "found": "True", "type": "28"}
START(WarningWriteActivity, {'data': '0060-030207938416', 'raw': '0060-030207938416', 'found': True, 'type': 28})
START(WriteActivity, {'data': '0060-030207938416', 'raw': '0060-030207938416', 'found': True, 'type': 28})
```

**Key insight**: `ReadFromHistoryActivity` calls `scan.setScanCache()` to populate the scan cache BEFORE pushing WarningWriteActivity. This is how write.so knows what to write.

### Correction 4: File path passed WITHOUT extension

```
File on disk:  /mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11.eml
Path in bundle: /mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11    ← NO .eml
```

write.so adds the correct extension (`.bin` for binary data, `.eml` for key data) internally.

### Correction 5: Filename format uses underscores (not parentheses)

**On-disk format** (from real device `/mnt/upan/dump/`):
```
M1-1K-4B_DAEFB416_2.bin        ← underscores separate UID and index
M1-4K-4B_E9784E21_1.eml
M1-Mini-4B_8800E177_1.bin
M0-UL_00000000000000_1.bin
T55xx_000880E8_00000000_1.eml
FDX-ID_0060-030207938416_4.txt
AWID-ID_FC,CN=X,X_1.txt
FeliCa_010108018D162D1A_1.txt
Iclass-Elite_4A678E15FEFF12E0_1.bin
```

**Display format** (what the UI list view shows — from screenshots):
```
1K-4B-DAEFB416(2)               ← hyphens and parentheses
```

The `parseInfoByM1FileName` method transforms: strips `M1-` prefix, replaces `_UID_` with `-UID`, converts `_INDEX` to `(INDEX)`.

### Correction 6: Three distinct write paths observed

| Tag Type | Write Method | PM3 Commands | Trace Lines |
|----------|-------------|--------------|-------------|
| **MF1K standard** (non-Gen1a) | `hf mf wrbl` per block | fchk → wrbl×48 (reverse) → trailer wrbl×16 | 13-147 |
| **MF1K Gen1a** (magic card) | `hf mf cload` (bulk) | cload → raw BCC fix sequence | 228-265 |
| **FDX-B LF** (T55xx clone) | `lf fdx clone` | wipe p 20206666 → detect → clone → write b7/b0 → detect p → lf sea | 172-189 |
| **MFU** (Ultralight) | `hf mfu restore` | restore → info | 201-209 |

### Correction 7: Activity stack depth = 4 during write

```
Stack during write:
  [0] MainActivity
  [1] CardWalletActivity
  [2] ReadFromHistoryActivity
  [3] WarningWriteActivity → WriteActivity
```

Write completion pops back: WriteActivity(d=4) → ReadFromHistoryActivity(d=3) → CardWalletActivity(d=2).

### Corrected state machine

```
[Main Menu: "Dump Files" (GOTO:1)]
        |
        v
[CardWalletActivity(bundle=None)]
  Type List → File List → Delete Confirm (internal states)
        |
        v (user selects file for details/write/simulate)
[ReadFromHistoryActivity(file_path)]          ← PUSHED as sub-activity
  Parses dump file via get_info() / get_type()
  Calls scan.setScanCache(parsed_info)
  Shows tag info + "Simulate"/"Write" softkeys
        |
   +----+----+
   |         |
   v (M1)    v (M2)
[SimulationActivity]  [WarningWriteActivity(bundle)]
                         |
                         v (M2 confirm)
                      [WriteActivity(bundle)]
                        PM3 commands...
                         |
                         v (FINISH × 3)
                      [back to CardWalletActivity]
```

### Real dump files pulled from device

160 files across 7 types pulled to `/tmp/device_dumps/dump/`:
- `mf1/` — 140+ files (1K, 4K, Mini variants, .bin/.eml/.json)
- `mfu/` — MFU dumps (.bin/.json)
- `t55xx/` — T55xx dumps
- `fdx/` — FDX-B ID dumps (.txt)
- `awid/` — AWID ID dumps (.txt)
- `felica/` — FeliCa dumps (.txt)
- `iclass/` — iClass Elite dumps (.bin/.eml/.json)

---

## CardWalletActivity state machine

### Full state machine (CORRECTED per trace)

```
[Main Menu: "Dump Files" (GOTO:1)]
        |
        v
[State 1: Type List]
  Title: "Dump Files {page}/{total}"
  Content: ListView of type categories (only types with dump files)
  Keys: UP/DOWN=navigate, OK=select type, PWR=exit to main
  Softkeys: none (no M1/M2 labels)
        |
        v (OK on a type)
[State 2: File List]
  Title: "Dump Files {page}/{total}"
  Content: ListView of filenames sorted by ctime (newest first)
  Softkeys: M1="Details" / M2="Delete"
  Keys: UP/DOWN=navigate, OK/M1=push ReadFromHistoryActivity, M2=delete confirm, PWR=back to type list
        |
   +----+----+
   |         |
   v (OK/M1) v (M2)
[ReadFromHistoryActivity]   [State 2b: Delete Confirm]
  (sub-activity push)         Toast: "Delete?"
  Parses file, shows info     M1="No" / M2="Yes"
  setScanCache(parsed)
  M1="Simulate" M2="Write"
  PWR=finish (back to files)
        |
   +----+----+
   |         |
   v (M1)    v (M2)
[SimulationActivity]  [WarningWriteActivity(bundle)]
  (sub-activity)         Title: "Data ready!"
                         M1="Watch" M2="Write"
                         PWR=finish (back)
                              |
                              v (M2)
                         [WriteActivity(bundle)]
                           Writing → Verifying → Result
```

**Ground Truth**: `docs/Real_Hardware_Intel/trace_dump_files_20260403.txt` (CANONICAL), `docs/UI_Mapping/03_dump_files/README.md` (corrected per trace)

### State transitions summary (CORRECTED)

| From | Key | To | Action |
|------|-----|----|--------|
| Type List | OK | File List | Show files for selected type |
| Type List | PWR | Main Menu | finish() |
| File List | OK/M1 | **ReadFromHistoryActivity** | **Push sub-activity** with file path |
| File List | M2 | Delete Confirm | Show "Delete?" toast |
| File List | PWR | Type List | Back to type categories |
| Delete Confirm | M1/PWR | File List | Cancel delete |
| Delete Confirm | M2/OK | File List | Delete file, refresh list |
| ReadFromHistoryActivity | M1 | SimulationActivity | Push SimulationActivity with dump bundle |
| ReadFromHistoryActivity | M2 | WarningWriteActivity | Push WarningWriteActivity (calls setScanCache first) |
| ReadFromHistoryActivity | PWR | File List | finish() back to CardWalletActivity |
| WarningWriteActivity | M2 | WriteActivity | Push WriteActivity with same bundle |
| WarningWriteActivity | M1/PWR | ReadFromHistoryActivity | Cancel, back |

**Ground Truth**: `docs/Real_Hardware_Intel/trace_dump_files_20260403.txt` lines 4-12, 165-171, 218-225

### Key bindings — CardWalletActivity (internal states)

| State | UP | DOWN | OK | M1 | M2 | PWR |
|-------|-----|------|-----|-----|-----|------|
| Type List (empty) | no-op | no-op | no-op | no-op | no-op | finish() |
| Type List (items) | prev() | next() | select type | no-op | no-op | finish() |
| File List | prev() | next() | push ReadFromHistoryActivity | push ReadFromHistoryActivity | confirmDelete() | back to types |
| Delete Confirm | no-op | no-op | deleteFile() | cancel (back) | deleteFile() | cancel (back) |

### Key bindings — ReadFromHistoryActivity (sub-activity)

| Key | Action |
|-----|--------|
| M1 | sim_for_info() — launch SimulationActivity |
| M2 | write_file_base() / write_lf_dump() — push WarningWriteActivity |
| PWR | finish() — back to CardWalletActivity file list |

**Ground Truth**: Binary methods (activity_main_strings.txt lines 20951-20956), real device trace

## Type categories (28 total)

From `appfiles_ghidra_raw.txt` PATH_DUMP_* constants and `docs/UI_Mapping/03_dump_files/README.md`:

| # | Display Name | dump_type key | Parse Method | Dump Path |
|---|-------------|---------------|-------------|-----------|
| 1 | Mifare Classic | mf1 | parseInfoByM1FileName | /mnt/upan/dump/mf1/ |
| 2 | T5577 ID | t55xx | parseInfoByT55xxInfoFileName | /mnt/upan/dump/t55xx/ |
| 3 | iClass | iclass | parseInfoByIDFileName | /mnt/upan/dump/iclass/ |
| 4 | Felica | felica | parseInfoByUIDInfoFileName | /mnt/upan/dump/felica/ |
| 5 | Legic Mini 256 | legic | parseInfoByLegicInfoFileName | /mnt/upan/dump/legic/ |
| 6 | ISO 14443A | hf14a | parseInfoByUIDInfoFileName | /mnt/upan/dump/hf14a/ |
| 7 | ICODE | icode | parseInfoByUIDInfoFileName | /mnt/upan/dump/icode/ |
| 8 | MFU | mfu | parseInfoByUIDInfoFileName | /mnt/upan/dump/mfu/ |
| 9 | EM410x ID | em410x | parseInfoByIDFileName | /mnt/upan/dump/em410x/ |
| 10 | EM4X05 ID | em4x05 | parseInfoByIDFileName | /mnt/upan/dump/em4x05/ |
| 11 | HID Prox ID | hid | parseInfoByIDFileName | /mnt/upan/dump/hid/ |
| 12 | Indala ID | indala | parseInfoByIDFileName | /mnt/upan/dump/indala/ |
| 13 | AWID ID | awid | parseInfoByIDFileName | /mnt/upan/dump/awid/ |
| 14 | Keri ID | keri | parseInfoByIDFileName | /mnt/upan/dump/keri/ |
| 15 | Viking ID | viking | parseInfoByIDFileName | /mnt/upan/dump/viking/ |
| 16 | Pyramid ID | pyramid | parseInfoByIDFileName | /mnt/upan/dump/pyramid/ |
| 17 | Presco ID | presco | parseInfoByIDFileName | /mnt/upan/dump/presco/ |
| 18 | Paradox ID | paradox | parseInfoByIDFileName | /mnt/upan/dump/paradox/ |
| 19 | Noralsy ID | noralsy | parseInfoByIDFileName | /mnt/upan/dump/noralsy/ |
| 20 | Gproxii ID | gproxii | parseInfoByIDFileName | /mnt/upan/dump/gproxii/ |
| 21 | Ioprox ID | ioprox | parseInfoByIDFileName | /mnt/upan/dump/ioprox/ |
| 22 | PAC ID | pac | parseInfoByIDFileName | /mnt/upan/dump/pac/ |
| 23 | Animal ID(FDX) | fdx | parseInfoByIDFileName | /mnt/upan/dump/fdx/ |
| 24 | Nedap ID | nedap | parseInfoByIDFileName | /mnt/upan/dump/nedap/ |
| 25 | Securakey ID | securakey | parseInfoByIDFileName | /mnt/upan/dump/securakey/ |
| 26 | Jablotron ID | jablotron | parseInfoByIDFileName | /mnt/upan/dump/jablotron/ |
| 27 | Gallagher ID | gallagher | parseInfoByIDFileName | /mnt/upan/dump/gallagher/ |
| 28 | Visa2000 ID | visa2000 | parseInfoByIDFileName | /mnt/upan/dump/visa2000/ |
| 29 | Nexwatch ID | nexwatch | parseInfoByIDFileName | /mnt/upan/dump/nexwatch/ |

**Ground Truth**: `docs/UI_Mapping/03_dump_files/README.md` Section 3, `decompiled/appfiles_ghidra_raw.txt` lines 384-455

**Display name evidence**: `dump_files_1_1.png` shows "Animal ID(FDX)" — NOT "FDX ID". The `HANDOVER.md` correction confirms this.

## File naming conventions and parse methods

### parseInfoByM1FileName (Mifare Classic)
Format: `{size}-{uid_bytes}B-{UID}({index}).{ext}`
Examples: `1K-4B-DEADBEEF(1).bin`, `Mini-4B-8800E177(1).eml`, `4K-7B-04AABBCCDDEE(2).bin`

Tag Info output:
```
MIFARE
M1 Mini 0.3K     (or: M1 S50 1K (4B), M1 S70 4K (4B), etc.)
Frequency: 13.56MHZ
UID: 8800E177
SAK: 08  ATQA: 0004
```
**Ground Truth**: `v1090_captures/090-Dump-Types-Files-Info.png`

### parseInfoByIDFileName (LF ID cards)
Format: `{type}-{ID}({index}).{ext}`
Example: `EM410x-1234567890(1).txt`

Tag Info output:
```
{Tag Type Name}
ID: {card ID}
```

### parseInfoByT55xxInfoFileName (T5577)
Format: `T5577-{ID}({index}).{ext}`

Tag Info output:
```
T5577
ID: {raw data}
Key: {key if known}
```

### parseInfoByUIDInfoFileName (MFU, 14443A, ICODE, Felica)
Format: `{UID}({index}).{ext}`
Example: `04AABBCCDDEE(1).bin`

### parseInfoByLegicInfoFileName (Legic)
Format: `Legic-{UID}({index}).{ext}`

**Ground Truth**: `docs/UI_Mapping/03_dump_files/README.md` Sections 4.3, 6

## Simulate/Write bundle format

When launching SimulationActivity or WriteActivity from CardWalletActivity, the bundle must contain:

- Dump file path (full path: e.g., `/mnt/upan/dump/mf1/1K-4B-DEADBEEF(1).bin`)
- Parsed tag info (type, UID, frequency, SAK, ATQA as applicable)
- Key file path (if available, via `getKeyInfo`)
- dump_type identifier

This bundle format is shared with ReadActivity's completion bundle, ensuring write/simulate can work with dumps from either source (fresh reads or saved files).

**Ground Truth**: `docs/UI_Mapping/03_dump_files/README.md` Section 13 (Simulate/Write Bundle), `docs/flows/auto-copy/ui-integration/README.md` Section 3.4

### Write sub-activity flow (same as Auto-Copy)

```
CardWalletActivity (State 4: Data Ready, M2="Write")
    -> push WarningWriteActivity(dump_bundle)
        -> "Data ready!" screen (same WarningWriteActivity used by AutoCopy/Read)
        -> M2 -> finish with result {action: 'write'}
    -> CardWalletActivity.onActivity(result)
        -> push WriteActivity(dump_bundle)
            -> WRITING -> WRITE_SUCCESS/WRITE_FAILED
            -> VERIFYING -> VERIFY_SUCCESS/VERIFY_FAILED
```

**Ground Truth**: `docs/flows/auto-copy/ui-integration/README.md` Section 3.4, `docs/UI_Mapping/03_dump_files/README.md` Section 8

## Implementation gaps (YOUR PRIMARY TASK — CORRECTED PER TRACE)

### Gap 1: Type List state — NOT IMPLEMENTED

**Current**: CardWalletActivity takes `dump_type`/`dump_dir` in bundle and shows a flat file list. When launched from main menu (no bundle), shows empty state.
**Required**: On launch with no bundle, scan ALL dump directories, show categories that have files.

Implementation:
- Add `MODE_TYPE_LIST` mode
- On `onCreate` with no `dump_type`, scan `DUMP_DIRS` for non-empty directories
- Show a ListView of type display names (4 items per page)
- OK on a type -> set `_dump_type` and `_dump_dir`, call `_showDumps()` (File List)
- PWR -> finish()
- Page indicator: "Dump Files {page}/{total}"

**Ground Truth**: `dump_files_1_1.png`, trace line 4: `START(CardWalletActivity, None)`

### Gap 2: ReadFromHistoryActivity — STUB (6 methods missing)

**This is the critical gap.** The real firmware uses `ReadFromHistoryActivity` as the intermediary between CardWalletActivity and the write/simulate pipeline. The current Python stub (`activity_main.py:5759-5780`) has only `__init__`, `onCreate`, `onKeyEvent` — all minimal.

**Current**: 3-method stub, wrong bundle format (`bundle.get('dump_data')`), no scan cache population, no write/simulate dispatch.
**Required**: Full implementation with 9 methods matching the binary.

Implementation:
- Fix `onCreate` to accept **file path string** as bundle (NOT dict) — trace evidence: `START(ReadFromHistoryActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11.eml')`
- Implement `get_type()` — determine tag type from filename pattern
- Implement `get_info()` — parse dump file → tag info for display (equivalent to the old parseInfoByM1FileName etc.)
- Implement `onData()` — data event handler
- Call `scan.setScanCache(parsed_info)` during load — trace evidence: `CACHE: {"uid": "'B7785E50'", ...}`
- Implement `write_file_base()` — push WarningWriteActivity with **file path** (HF types)
- Implement `write_lf_dump()` / `write_id()` — push WarningWriteActivity with **scan cache dict** (LF types)
- Implement `sim_for_info()` — push SimulationActivity with dump data
- Fix `onKeyEvent`: M1 → simulate, M2 → write, PWR → finish

**Ground Truth**: `trace_dump_files_20260403.txt` (all 3 flows), `activity_main_strings.txt` lines 20951-21020

### Gap 3: Delete Confirmation toast — NOT IMPLEMENTED

**Current**: M2 in detail mode calls `_deleteFile()` immediately (no confirmation).
**Required**: Show "Delete?" toast with "No" / "Yes" softkeys.

Implementation:
- Add `MODE_DELETE_CONFIRM` mode
- M2 in file list -> show "Delete?" toast, set softkeys to "No" / "Yes"
- M1/PWR in delete confirm -> cancel, back to file list
- M2/OK in delete confirm -> delete file, refresh list

**Ground Truth**: `dump_files_delete_confirm_2.png`

### Gap 4: CardWalletActivity → ReadFromHistoryActivity wiring — NOT IMPLEMENTED

**Current**: OK/M1 in file list calls internal `_showDetail()`.
**Required**: Push `ReadFromHistoryActivity` as a sub-activity with the full file path.

Implementation:
- On OK/M1 in file list: `actstack.start_activity(ReadFromHistoryActivity, file_path)`
- Where `file_path` = full path, e.g., `/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11.eml`
- Handle `onActivity(result)` when ReadFromHistoryActivity finishes (user pressed PWR)

**Ground Truth**: trace line 6: `START(ReadFromHistoryActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11.eml')`

### Gap 5: Bundle format — HF path vs LF dict — NOT IMPLEMENTED

**Current**: No bundle passing to write pipeline.
**Required**: ReadFromHistoryActivity must pass the correct bundle format to WarningWriteActivity:
- **HF types** (MF1, MFU, iClass): file path string WITHOUT extension
- **LF types** (FDX, AWID, EM410x, etc.): scan cache dict `{data, raw, found, type}`

**Ground Truth**:
- HF: trace line 9: `START(WarningWriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_B7785E50_11')`
- LF: trace line 168: `START(WarningWriteActivity, {'data': '0060-030207938416', 'raw': '0060-030207938416', 'found': True, 'type': 28})`

### Gap 6: Seed dump files with real filenames — WRONG FORMAT

**Current**: `seed_dump_files.py` creates `04AABBCC_1.bin` (minimal UID-only names).
**Required**: Real device format: `M1-1K-4B_DAEFB416_2.bin`, `FDX-ID_0060-030207938416_4.txt`, etc.

Implementation:
- Update `seed_dump_files.py` to use real filename patterns
- Copy representative real dumps from `/tmp/device_dumps/` for test use
- Filenames must match what `get_type()` and `get_info()` expect to parse

**Ground Truth**: 160 real files pulled from device in `/tmp/device_dumps/dump/`

### Gap 7: JSON UI state machine expansion — PARTIAL

**Current**: `dump_files.json` has 4 states (file_list, file_list_empty, detail_view, delete_confirm).
**Required**: Add `type_list` and `type_list_empty` states. Remove `detail_view` (replaced by ReadFromHistoryActivity sub-activity push).

### Gap 8: Integration flow tests — INFRASTRUCTURE BUILT, 29/31 FAILING

31 scenarios built in `tests/flows/dump_files/scenarios/`. 2 pass (empty state, PWR exit). 29 fail because Gap 1 (Type List) blocks all deeper navigation. Tests are acceptance criteria — they'll pass as gaps are filled.

## File system layout

```
/mnt/upan/dump/                    <- PATH_DUMP root
  +-- mf1/                         <- Mifare Classic .bin/.eml dumps
  +-- mfu/                         <- Mifare Ultralight dumps
  +-- t55xx/                       <- T5577 ID dumps
  +-- iclass/                      <- iClass dumps
  +-- felica/                      <- Felica dumps
  +-- legic/                       <- Legic Mini 256 dumps
  +-- hf14a/                       <- ISO 14443A UID dumps
  +-- icode/                       <- 15693/ICODE/SLIX dumps
  +-- em410x/                      <- EM410x ID dumps
  +-- em4x05/                      <- EM4X05 ID dumps
  +-- hid/                         <- HID Prox ID dumps
  +-- indala/                      <- Indala ID dumps
  +-- awid/                        <- AWID ID dumps
  +-- keri/                        <- Keri ID dumps
  +-- viking/                      <- Viking ID dumps
  +-- pyramid/                     <- Pyramid ID dumps
  +-- presco/                      <- Presco ID dumps
  +-- paradox/                     <- Paradox ID dumps
  +-- noralsy/                     <- Noralsy ID dumps
  +-- gproxii/                     <- Gproxii ID dumps
  +-- ioprox/                      <- Ioprox ID dumps
  +-- pac/                         <- PAC ID dumps
  +-- fdx/                         <- FDX-B ID dumps
  +-- nedap/                       <- Nedap ID dumps
  +-- securakey/                   <- Securakey ID dumps
  +-- jablotron/                   <- Jablotron ID dumps
  +-- gallagher/                   <- Gallagher ID dumps
  +-- visa2000/                    <- Visa2000 ID dumps
  +-- nexwatch/                    <- Nexwatch ID dumps

/mnt/upan/keys/                    <- PATH_KEYS root
  +-- mf1/                         <- Mifare Classic key files
  +-- t5577/                       <- T5577 key files
```

Supported file extensions: `.bin`, `.eml`, `.txt`, `.json`, `.pm3`
Empty-state message: "No dump info. \nOnly support:\n.bin .eml .txt"

**Ground Truth**: `decompiled/appfiles_ghidra_raw.txt` lines 384-504, `docs/UI_Mapping/03_dump_files/README.md` Section 10

## Test infrastructure

### Proposed flow test pipeline (`dump_common.sh`)

Following the pattern from `tests/flows/simulate/includes/sim_common.sh`:

1. **Phase 1**: Navigate to Dump Files (GOTO:1) -> verify "Dump Files" title
2. **Phase 2**: Select type category -> verify file list appears
3. **Phase 3**: Navigate file list -> select file -> verify Tag Info view
4. **Phase 4**: (varies by scenario):
    - **Browse**: Verify tag info content, PWR back
    - **Delete**: M2 on file list -> verify "Delete?" toast -> confirm/cancel
    - **Write**: M2 on Tag Info -> Data Ready -> M2 -> WarningWriteActivity -> WriteActivity
    - **Simulate**: M1 on Tag Info -> SimulationActivity -> verify sim started

### Proposed scenarios

| Scenario | Description | Min States |
|----------|-------------|------------|
| `dump_browse_mf1_types` | Navigate type list, verify Mifare Classic category | 3 |
| `dump_browse_mf1_files` | Enter MF1 category, browse file list, view detail | 5 |
| `dump_browse_mf1_tag_info` | View Tag Info for MF1 dump, verify parsed metadata | 6 |
| `dump_browse_t55xx_tag_info` | View Tag Info for T5577 dump, verify parsed metadata | 6 |
| `dump_browse_lf_id_tag_info` | View Tag Info for LF ID (e.g., EM410x) dump | 6 |
| `dump_browse_empty_type` | Select type with no files, verify empty state | 4 |
| `dump_delete_confirm` | M2 on file -> "Delete?" -> "Yes" -> file removed | 6 |
| `dump_delete_cancel` | M2 on file -> "Delete?" -> "No" -> file still exists | 5 |
| `dump_delete_last_file` | Delete the only file in a category -> return to type list | 7 |
| `dump_write_mf1_success` | Tag Info -> Data Ready -> Write -> verify write toast | 10 |
| `dump_write_lf_success` | Tag Info -> Data Ready -> Write for LF dump | 10 |
| `dump_simulate_mf1` | Tag Info -> M1 -> SimulationActivity launches | 8 |
| `dump_simulate_lf` | Tag Info -> M1 -> SimulationActivity for LF type | 8 |
| `dump_pwr_type_list` | PWR from type list exits to main menu | 3 |
| `dump_pwr_file_list` | PWR from file list returns to type list | 4 |
| `dump_pwr_tag_info` | PWR from tag info returns to file list | 5 |
| `dump_pwr_data_ready` | PWR from data ready returns to tag info | 6 |
| `dump_pagination_types` | Multiple type categories, verify page indicator | 4 |
| `dump_pagination_files` | Many files in one type, verify scrolling and page indicator | 5 |
| `dump_scroll_file_list` | UP/DOWN through file list, verify selection movement | 5 |

### Running tests

```bash
# Single test locally
TEST_TARGET=current SCENARIO=dump_browse_mf1_files FLOW=dump_files \
  bash tests/flows/dump_files/scenarios/dump_browse_mf1_files/dump_browse_mf1_files.sh

# Full parallel suite on remote (48-core server)
sshpass -p proxmark rsync -az --exclude='.git' --exclude='tests/flows/_results' --exclude='__pycache__' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/
sshpass -p proxmark ssh -o ServerAliveInterval=30 qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/dump_files/test_dump_files_parallel.sh 16'

# Results
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cat ~/icopy-x-reimpl/tests/flows/_results/current/dump_files/scenario_summary.txt'
```

### Framework constants

```
PM3_DELAY=0.3
BOOT_TIMEOUT=300
BROWSE_TRIGGER_WAIT=30
DELETE_TRIGGER_WAIT=15
WRITE_TRIGGER_WAIT=300
SIM_TRIGGER_WAIT=60
```

### Seed dump files for testing

```bash
# Seed all types with test dump files
python3 tools/seed_dump_files.py

# Seed specific type
python3 tools/seed_dump_files.py --type mf1

# Cleanup
python3 tools/seed_dump_files.py --clean
```

The `seed_dump_files.py` tool creates minimal valid dump files for each type, ensuring the Type List has entries to navigate.

## Environment

- Branch: `feat/ui-integrating` at latest commit
- QEMU rootfs: `/mnt/sdcard/root2/root/`
- Remote QEMU server: `qx@178.62.84.144` (password: `proxmark`, sudo: `proxmark`, 48 cores)
- Real device SSH: `sshpass -p 'fa' ssh -p 2222 root@localhost` (tunnel must be established by user)
- Main menu position: Item #2 ("Dump Files") -> GOTO:1
- Activity registry: `'dump_files': ('activity_main', 'CardWalletActivity')` in `actmain.py:44`

## Working flows (don't break these)

- Volume: 7/7 PASS
- Backlight: 7/7 PASS
- Scan: 45/45 PASS
- Read: 99/99 PASS
- Write: 63/63 PASS
- Auto-Copy: 52/52 PASS
- Simulate: 32/32 PASS (if applicable)

## No-Middleware Rules (from Auto-Copy post-mortem)

### Rule
Our Python is a thin UI shell. .so modules handle ALL RFID logic. CardWalletActivity is a FILE BROWSER that LAUNCHES sub-activities. If you're writing tag-specific RFID logic in Python — STOP.

### What CardWalletActivity SHOULD do:
- Scan directories for dump files
- Parse filenames to extract display metadata
- Render file lists with pagination
- Show tag info detail views
- Show delete confirmation
- Push SimulationActivity / WarningWriteActivity / WriteActivity as sub-activities
- Handle sub-activity results

### What CardWalletActivity should NOT do:
- Send PM3 commands
- Interpret dump file contents (beyond filename parsing)
- Validate tag compatibility
- Perform write/verify logic
- Render simulation UI

**Ground Truth**: `docs/flows/auto-copy/ui-integration/README.md` Section 7 (No-Middleware Rules)

## Definition of done (CORRECTED PER TRACE)

1. **Type List** shows only categories with dump files, 4 items per page, page indicator in title
2. **File List** shows files sorted by ctime, 4 items per page, "Details" / "Delete" softkeys
3. **Delete Confirmation** shows "Delete?" toast with "No" / "Yes" softkeys
4. **OK/M1 on file pushes ReadFromHistoryActivity** with full file path as bundle
5. **ReadFromHistoryActivity** parses dump, calls `setScanCache()`, shows tag info, "Simulate" / "Write" softkeys
6. **M1 in ReadFromHistoryActivity** launches SimulationActivity via `sim_for_info()`
7. **M2 in ReadFromHistoryActivity** pushes WarningWriteActivity with correct bundle format (path for HF, dict for LF)
8. **WarningWriteActivity → WriteActivity** chain works with Dump Files bundles
9. **PWR navigation** works at every level (Type List→exit, File List→types, ReadFromHistory→files, WarningWrite→back)
10. **Seed dump files** use real device filename format (`M1-1K-4B_UID_INDEX.ext`)
11. **All 14 existing unit tests** still pass (may need updates for new state machine)
12. **Integration flow tests**: 31/31 pass
13. **No regressions**: Volume, Backlight, Scan, Read, Write, Auto-Copy all pass
14. Every implementation decision cites trace or binary evidence

## Approach (CORRECTED PER TRACE)

### Phase A: Foundation (seed files + Type List)

1. **Fix `seed_dump_files.py`** — use real device filename format from `/tmp/device_dumps/`
2. **Implement Type List** in CardWalletActivity: scan DUMP_DIRS, show categories with files
3. **Verify under QEMU** — `dump_pwr_type_list`, `dump_types_single`, `dump_types_multi` should pass
4. **Implement Delete Confirmation** — "Delete?" toast with "No" / "Yes"
5. **Verify** — `dump_delete_*` scenarios should pass

### Phase B: ReadFromHistoryActivity (the critical path)

1. **Fix bundle reception** — accept file path string, not dict
2. **Implement `get_type()`** — parse filename to determine tag type
3. **Implement `get_info()`** — parse filename to extract tag metadata for display
4. **Call `scan.setScanCache()`** — populate scan cache from parsed dump
5. **Wire `onKeyEvent`**: M2 → write dispatch (path for HF, dict for LF), M1 → simulate, PWR → finish
6. **Implement `write_file_base()`** — push WarningWriteActivity with path (HF)
7. **Implement `write_lf_dump()` / `write_id()`** — push WarningWriteActivity with dict (LF)
8. **Implement `sim_for_info()`** — push SimulationActivity
9. **Wire CardWalletActivity** — OK/M1 in file list pushes ReadFromHistoryActivity instead of internal detail view

### Phase C: Integration testing

1. **Run browse scenarios** — `dump_files_browse`, `dump_detail_*` should pass
2. **Run write scenarios** — `dump_write_mf1k_success`, `dump_write_lf_success` should pass
3. **Run simulate scenarios** — `dump_sim_hf`, `dump_sim_lf` should pass
4. **Run full suite** — all 31 scenarios, then all regression suites
5. **Fix any failures** with ground truth from trace

**DO NOT skip Phase B.** ReadFromHistoryActivity is the keystone — without it, nothing past the file list works. Implement it method by method, verifying each against the trace.

## Appendix A: Real Device Screenshot Analysis

All screenshots captured from real iCopy-X hardware at 240x240 resolution, RGB565 framebuffer.

### A.1 Type List — `dump_files_1_1.png`

```
Title: "Dump Files 1/1" + battery icon
Content:
  1. Mifare Classic
  2. Animal ID(FDX)
  3. T5577 ID
  4. AWID ID
Softkeys: NONE (no M1/M2 labels visible at bottom)
```

**Key observations:**
- 4 items per page (confirmed)
- Title includes page indicator "1/1" (only 1 page needed for 4 types)
- NO softkey labels in Type List state — only UP/DOWN/OK/PWR are active
- "Animal ID(FDX)" display name confirmed (not "FDX ID")
- Only types with dump files are shown (this device had 4 types with files)
- List items are numbered 1-4

### A.2 File List — `dump_files_1_10_1.png`

```
Title: "Dump Files 1/10" + battery icon
Content:
  1K-4B-DAEFB416(1)
  1K-4B-DAEFB416(2)
  1K-4B-DAEFB416(3)
  1K-4B-DAEFB416(4)
Softkeys: "Details" (M1, left) / "Delete" (M2, right)
```

**Key observations:**
- "Details" / "Delete" softkeys (NOT "Back" / "Details" as in current `dump_files.json`)
- M1 = "Details" (shows Tag Info), M2 = "Delete" (enters delete confirmation)
- 4 items per page, page 1 of 10 = 40 files total
- MF1 filename format: `{size}-{uid_bytes}B-{UID}({index})` — no file extension shown in list
- Files appear to be listed without extension (just the base name)

### A.3 File List page 2 — `dump_files_1_10_2.png`

```
Title: "Dump Files 1/10"
Content:
  1980-01-01 00:00:00
  1980-01-01 00:00:00
  1980-01-01 00:00:00
  1980-01-01 00:00:00
Softkeys: "Details" / "Delete"
```

**Key observations:**
- Same page indicator "1/10" — this is a different scroll position, not page 2
- Shows date-formatted entries — likely dump filenames that are timestamps (from a different test set) OR the list view is showing creation times for files without parseable names
- Confirms 4-item page window

### A.4 File List empty area — `dump_files_1_10_3.png`

```
Title: "Dump Files 1/10" + battery icon
Content: (empty area — no visible file entries)
Softkeys: "Details" / "Delete"
```

**Key observations:**
- Empty visible area during scroll — likely a rendering state between scroll operations
- Softkeys remain "Details" / "Delete"

### A.5 File List scrolled — `dump_files_1_10_4.png`

```
Title: "Dump Files 1/10"
Content:
  1K-4B-DAEFB416(2)
  1K-4B-DAEFB416(3)
  1K-4B-DAEFB416(4)
  1K-4B-DAEFB416(5)
Softkeys: "Details" / "Delete"
```

**Key observations:**
- Items shifted down by 1 position from screenshot A.2 (starts at `(2)` instead of `(1)`)
- Confirms item-by-item scrolling (not page-by-page jump)
- Page indicator still "1/10" — page doesn't change until scrolling past item 4
- 4 items visible at all times

### A.6 Delete Confirm (transition) — `dump_files_delete_confirm_1.png`

```
Title: "Dump Files 1/10"
Content: file list dimmed, "Delete?" toast overlay centered
  1K-4B-DAEFB416(1)
  1K-4B-DAEFB416(2)  ← "Delete?" overlay here
  1K-4B-DAEFB416(3)
  1K-4B-DAEFB416(4)
Softkeys: "Details" / "Delete" (transition frame — not yet updated)
```

**Key observations:**
- "Delete?" toast appears OVER the dimmed file list (background stays visible)
- Softkeys still show "Details" / "Delete" — this is a mid-transition capture before softkeys update to "No" / "Yes"
- Toast is centered on the screen, overlaying the list

### A.7 Delete Confirm (final) — `dump_files_delete_confirm_2.png`

```
Title: "Dump Files 1/10"
Content: file list dimmed, "Delete?" toast overlay centered
  1K-4B-DAEFB416(1)
  1K-4B-DAEFB416(2)  ← "Delete?" overlay
  1K-4B-DAEFB416(3)
  1K-4B-DAEFB416(4)
Softkeys: "No" (M1, left) / "Yes" (M2, right)
```

**Key observations:**
- Softkeys updated to "No" / "Yes" (confirmed, matches `dump_files.json` delete_confirm state)
- M1 = "No" (cancel), M2 = "Yes" (confirm delete) — also OK = confirm delete
- Toast overlay persists with "Delete?" text
- File list remains visible but dimmed behind the toast

### A.8 Tag Info — `v1090_captures/090-Dump-Types-Files-Info.png`

```
Title: "Tag Info"
Content (blue text on dark background):
  MIFARE
  M1 Mini 0.3K
  Frequency: 13.56MHZ
  UID: 8800E177
  SAK: 08  ATQA: 0004
Softkeys: "Simulate" (M1, left) / "Write" (M2, right)
```

**Key observations:**
- Title changes from "Dump Files" to "Tag Info" in this state
- parseInfoByM1FileName renders full MIFARE metadata
- "Simulate" / "Write" softkeys confirmed
- Blue text rendering (distinct from white text in list views)
- SAK and ATQA on same line, separated by spaces

### A.9 Data Ready — `v1090_captures/090-Dump-Types-Files-Info-Write.png`

```
Title: "Data ready!"
Content (blue text on dark background):
  Data ready for copy!
  Please place new tag
  for copy.
  TYPE:
  M1-4b
Softkeys: "Watch" (M1, left) / "Write" (M2, right)
```

**Key observations:**
- Title: "Data ready!" (exact string)
- Body text wraps: "Please place new tag" / "for copy." (line break at ~20 chars)
- TYPE label on its own line, followed by type value "M1-4b" in larger font
- "Watch" / "Write" softkeys confirmed
- "M1-4b" = Mifare 1K, 4-byte UID (derived from parsed filename, NOT from dump content)

### A.10 V1090 Type List — `v1090_captures/090-Dump-Types.png`

```
Title: "Dump Files 1/1"
Content:
  1. Mifare Classic
  2. T5577 ID
Softkeys: NONE
```

**Key observations:**
- Only 2 types with files on this device (vs. 4 on the real hardware device)
- Confirms Type List format with numbered entries
- No softkeys visible (same as A.1)

### A.11 V1090 File List — `v1090_captures/090-Dump-Types-Files.png`

```
Title: "Dump Files 1/5"
Content:
  Mini-4B-8800E177(1)
  1K-4B-DAEF8416(1)
  1K-4B-DAEF8416(1)
  1K-4B-DAEF8416(1)
Softkeys: "Details" / "Delete"
```

**Key observations:**
- 5 pages of files (20 files total, 4 per page)
- Mix of Mini and 1K file types
- "Details" / "Delete" softkeys consistent with real hardware
- Mini file format: `Mini-4B-{UID}({index})`

## Appendix B: Softkey Correction — File List

**CRITICAL CORRECTION**: The current `dump_files.json` file_list state has:
```json
"buttons": { "left": "Back", "right": "Details" }
```

Real hardware screenshots (A.2, A.5, A.11) consistently show:
```
M1 (left) = "Details"
M2 (right) = "Delete"
```

The JSON UI and the CardWalletActivity implementation must be updated to match:
- **file_list** state: `"left": "Details"`, `"right": "Delete"`
- M1 in file_list = show detail (same as OK)
- M2 in file_list = enter delete confirmation

This contradicts the decompiled key binding table in `docs/UI_Mapping/03_dump_files/README.md` Section 13 which shows `M1=finish()`, but screenshots are canonical when they conflict with decompiled keybindings. The UI_Mapping Section 4 (Key Handling -- File List) correctly documents M1="Details" and M2="Delete".
