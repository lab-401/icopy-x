# Dump Files Flow — UI Integration Post-Mortem

**Branch:** `feat/ui-integrating` (commit `c35a632`)
**Date:** 2026-04-05
**Status:** 35/35 PASS (`--target=current`, 1 worker, 1531s)
**Files modified:** `src/lib/activity_main.py`, `src/screens/dump_files.json`

---

## 1. Initial State

### 1.1 What Existed

CardWalletActivity was a simplified 2-mode stub (MODE_LIST + MODE_DETAIL) that:
- Accepted `dump_type`/`dump_dir` in the bundle and showed a flat file list
- Had internal detail view with "Back"/"Delete" buttons
- Deleted files immediately on M2 (no confirmation)
- Had a basic `_parseFilename` that extracted UID and format

ReadFromHistoryActivity was a 22-line stub:
```python
class ReadFromHistoryActivity(BaseActivity):
    ACT_NAME = 'read_history'
    def __init__(self, bundle=None):
        self._dump_data = None
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('card_wallet'))  # Wrong title
        self.setLeftButton('Back')
        self.setRightButton(resources.get_str('write'))
        ...
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            self.finish()
        elif key in (KEY_M2, KEY_OK):
            self.finish()  # No write dispatch, no simulate
```

`dump_files.json` had 4 states: `file_list`, `file_list_empty`, `detail_view`, `delete_confirm`. No `type_list` state.

### 1.2 What Was Broken — Functionality

| # | Gap | Impact |
|---|-----|--------|
| 1 | **No Type List** | GOTO:1 showed a flat file list; original shows 28 categorized types |
| 2 | **No ReadFromHistoryActivity** | OK on file list showed internal detail; original pushes a sub-activity with Tag Info rendering |
| 3 | **No Delete Confirmation** | M2 deleted immediately; original shows "Delete?" toast with No/Yes |
| 4 | **No Write dispatch** | No write_file_base/write_id/write_lf_dump routing; no bundle format handling |
| 5 | **No Simulate dispatch** | No SimulationActivity push from Tag Info |
| 6 | **No onActivity chain** | WarningWriteActivity result never chained to WriteActivity |
| 7 | **No scan cache population** | scan.setScanCache never called; write.so had no tag data |

### 1.3 What Was Broken — UI

| # | Issue | Impact |
|---|-------|--------|
| 1 | Title always "Dump Files" | ReadFromHistoryActivity should show "Tag Info" |
| 2 | M1 button "Back" on file list | Should be "Details" (toggle date display) |
| 3 | M2 button "Details" on file list | Should be "Delete" |
| 4 | No Tag Info rendering | Original uses `template.draw()` for structured display (MIFARE header, UID, SAK/ATQA) |
| 5 | M1 "Simulation" on Tag Info | Original says "Simulate"; also must be grayed out for non-simulatable types |
| 6 | PWR from file list calls finish() | Should return to type list, not exit entirely |
| 7 | No page indicator on type list | Original shows "Dump Files 1/6" |

---

## 2. Ground Truth Resources

### 2.1 Critical Resources

| Resource | Path | What It Provided |
|----------|------|-----------------|
| **HANDOVER.md** | `docs/flows/dump_files/HANDOVER.md` | Complete spec: type order, bundle formats, parse regexes, scan cache formats, write dispatch table |
| **Canonical Trace #1** | `docs/Real_Hardware_Intel/trace_dump_files_20260403.txt` | MF1K standard write, FDX clone, MFU restore, Gen1a write — 270 lines |
| **Canonical Trace #2** | `docs/Real_Hardware_Intel/trace_dump_files_em410x_t55xx_write_20260405.txt` | EM410x write, T55xx restore — 305 lines |
| **Real Device Screenshots** | `docs/Real_Hardware_Intel/Screenshots/dump_files_*.png` | 7 screenshots: type list, file list pagination, date toggle, delete confirmation |
| **Seed Tool** | `tools/seed_dump_files.py` | 31 type definitions with real device filename formats, used for test seeding |
| **Prior Post-Mortems** | `docs/flows/{erase,write,auto-copy,simulate,sniff}/ui-integration/` | Activity stack patterns, onActivity chain, DRM rules, per-gate validation |

### 2.2 Techniques That Were Vital

**1. QEMU State Dump Tracing**

The launcher's `_dump_state()` function captures complete canvas state as JSON: every text element with exact (x, y) position, font, color, and tags. This was essential for:
- Verifying type list content and order (28 types at correct indices)
- Confirming button text/color/active state at each transition
- Detecting that template.draw overwrites the title bar (required re-init)
- Finding that "MIFARE" content was present on canvas but misclassified by the state dump scanner

**2. Cross-Target Comparison**

Running the same scenario with `--target=original` and `--target=current` then comparing state dumps side-by-side revealed:
- `len` field needed to be integer `4`, not string `'4'` (write.so type check)
- `nameStr` field was missing from scan cache (template.so fell back to default)
- Simulate button was active for MF1 Mini (type 25 not in SIM_MAP)

**3. QEMU LD_PREFIX File Redirection Discovery**

The most impactful discovery: QEMU user-mode with `QEMU_LD_PREFIX` redirects ALL file access to the rootfs path. Files seeded at `/mnt/upan/dump/mf1/` on the host were invisible under QEMU because it read from `/mnt/sdcard/root2/root/mnt/upan/dump/mf1/` (which was empty).

**Fix:** Symlink the rootfs dump/keys directories to the host paths:
```bash
sudo rm -rf /mnt/sdcard/root2/root/mnt/upan/dump
sudo ln -s /mnt/upan/dump /mnt/sdcard/root2/root/mnt/upan/dump
sudo rm -rf /mnt/sdcard/root2/root/mnt/upan/keys
sudo ln -s /mnt/upan/keys /mnt/sdcard/root2/root/mnt/upan/keys
```

This affected ALL dump file tests — without it, `os.listdir('/mnt/upan/dump/mf1/')` returned `[]` despite the host having files. The symlink must be created on both local and remote QEMU environments.

**4. Per-Gate Test Validation**

The test harness (`dump_common.sh`) validates at each critical transition:
```bash
# Gate 1: Type list entered
wait_for_ui_trigger "title:Dump Files" "${DUMP_TRIGGER_WAIT}" ...

# Gate 2: File list entered (after type selection)
wait_for_ui_trigger "M1:Details" "${DUMP_TRIGGER_WAIT}" ...

# Gate 3: Tag Info entered (after OK from file list)
wait_for_ui_trigger "title:Tag Info" "${DUMP_TRIGGER_WAIT}" ...

# Gate 4: Data Ready entered (after M2 from Tag Info)
wait_for_ui_trigger "title:Data ready" "${DUMP_TRIGGER_WAIT}" ...

# Gate 5: Write result (after write completes)
wait_for_ui_trigger "toast:Write successful" "${WRITE_TRIGGER_WAIT}" ...
```

Each gate checks specific content (title text, button labels, toast messages) — never just state count. A failure at any gate reports exactly what was expected vs what was found.

---

## 3. Solutions Implemented

### 3.1 DUMP_TYPE_ORDER — Fixed 28-Type List

The original firmware shows ALL 28 type categories in a fixed order, regardless of whether files exist. This order was extracted from QEMU tracing and verified against test scenario `type_index` values.

```python
DUMP_TYPE_ORDER = [
    ('Viking',            'viking'),     # 0
    ('Ultralight & NTAG', 'mfu'),        # 1
    ('Visa2000',          'visa2000'),   # 2
    ('HID Prox',          'hid'),        # 3
    ('Mifare Classic',    'mf1'),        # 4  — most test scenarios use this
    ('Animal ID(FDX)',    'fdx'),        # 5
    ('Paradox',           'paradox'),    # 6
    ('Jablotron',         'jablotron'),  # 7
    ('Pyramid',           'pyramid'),    # 8
    ('Noralsy',           'noralsy'),    # 9
    ('NexWatch',          'nexwatch'),   # 10
    ('Securakey',         'securakey'),  # 11
    ('Felica',            'felica'),     # 12
    ('KERI',              'keri'),       # 13
    ('IO Prox',           'ioprox'),     # 14
    ('AWID',              'awid'),       # 15
    ('Legic Mini 256',    'legic'),      # 16
    ('T5577 ID',          't55xx'),      # 17
    ('15693 ICODE/STSA',  'icode'),      # 18
    ('EM410x ID',         'em410x'),     # 19
    ('PAC',               'pac'),        # 20
    ('GProx II',          'gproxii'),    # 21
    ('NEDAP',             'nedap'),      # 22
    ('GALLAGHER',         'gallagher'),  # 23
    ('Presco',            'presco'),     # 24
    ('Indala',            'indala'),     # 25
    ('iClass',            'iclass'),     # 26
    ('EM4X05',            'em4x05'),     # 27
]
```

**Verification:** Test scenarios use `type_index` to navigate — `dump_files_browse` uses index 4 (Mifare Classic), `dump_sim_lf` uses index 19 (EM410x ID), `dump_detail_t55xx` uses index 17. All match.

### 3.2 CardWalletActivity — 3-Mode State Machine

Replaced the 2-mode stub with three distinct modes:

**MODE_TYPE_LIST** (initial):
- ListView with 28 type display names, 5 items/page
- No M1/M2 softkeys (only UP/DOWN/OK/PWR)
- OK selects type and transitions to FILE_LIST
- PWR calls finish() (back to main menu)

**MODE_FILE_LIST**:
- Files sorted by name, filtered to valid extensions (.bin, .eml, .txt, .json, .pm3)
- M1="Details" toggles `_is_dump_show_date` (renders creation dates instead of filenames)
- M2="Delete" enters DELETE_CONFIRM
- OK pushes ReadFromHistoryActivity with full file path string
- PWR returns to TYPE_LIST (not finish — critical difference from the stub)
- Empty directory shows "No dump info.\nOnly support:\n.bin .eml .txt"

**MODE_DELETE_CONFIRM**:
- Toast "Delete?" with timeout=0 (persistent)
- M1="No" returns to FILE_LIST
- M2="Yes" deletes file, returns to FILE_LIST (or TYPE_LIST if last file)
- PWR returns to TYPE_LIST (universal back)

**onResume** refreshes the file list when returning from a child activity.

### 3.3 ReadFromHistoryActivity — Full Implementation

The 22-line stub became ~250 lines implementing the complete file parser, scan cache builder, and sub-activity dispatcher.

**onCreate flow:**
1. Store file path from bundle (string, with extension)
2. Determine `_dump_type_key` from directory name
3. Parse filename via type-specific regex
4. Build scan cache with native Python types and call `scan.setScanCache()`
5. Render tag info via `template.draw()` (same renderer as ScanActivity)
6. Set title "Tag Info" (must be AFTER template.draw, which overwrites the title)
7. Set Simulate button (active or grayed based on SIM_MAP membership)

**5 filename parsers** (from binary regex at L21251-22113):
```python
# MF1: M1-{size}-{uidLen}B_{UID}_{index}.{ext}
re.match(r'M1-(\S+)-(\S+)_([A-Fa-f\d]+)_(\d+).*\.(.*)', fname)

# T55xx: T55xx_{B0}_{B1}_{B2}_{index}.{ext}
re.match(r'(\S+)_(\S+)_(\S+)_(\S+)_(\d+).*\.(.*)', fname)

# UID-based (MFU, Felica, ICODE, HF14A): {Type}_{UID}_{index}.{ext}
re.match(r'(\S+)_([A-Fa-f\d]+)_(\d+).*\.(.*)', fname)

# Legic: Legic_{UID}_{index}.{ext}
re.match(r'(\S+)_(\S+)_(\d+)\.(.*)', fname)

# ID-based (all LF types + iClass): {Type}_{Data}_{index}.{ext}
# Also 4-field variant: {Type}_{F1}_{F2}_{F3}_{index}.{ext}
```

**Write dispatch** (three methods, routed by type):
```python
# HF file-based types (mf1, mfu, iclass, felica, legic, hf14a, icode)
def _write_file_base(self):
    bundle = os.path.splitext(self._file_path)[0]  # path WITHOUT extension
    actstack.start_activity(WarningWriteActivity, bundle)

# LF ID types (em410x, hid, awid, fdx, viking, etc.)
def _write_id(self):
    actstack.start_activity(WarningWriteActivity, dict(self._scan_cache))

# T55xx/EM4x05 raw dump
def _write_lf_dump(self):
    actstack.start_activity(WarningWriteActivity, {'file': self._file_path})
```

**onActivity chain** (mirrors AutoCopyActivity pattern):
```python
def onActivity(self, result):
    if result is None or not isinstance(result, dict):
        return
    if result.get('action') == 'write':
        actstack.start_activity(WriteActivity, result.get('read_bundle'))
```

### 3.4 Tag Info Rendering via template.draw()

The initial implementation used `BigTextListView` for plain text rendering ("Mifare Classic\n1K-4B-DAEFB416(1)"). This was incorrect — the original firmware uses `template.draw()` which renders structured tag info with labeled fields.

**Before (wrong):**
```python
from lib.widget import BigTextListView
btlv = BigTextListView(canvas)
btlv.drawStr('Mifare Classic\n1K-4B-DAEFB416(1)')
```

**After (correct):**
```python
import template
template.draw(tag_type, self._scan_cache, canvas)
# template.draw overwrites the title bar — force re-init
self._is_title_inited = False
self.setTitle('Tag Info')
```

**Critical detail:** `template.draw()` clears the canvas and draws its own title bar (e.g., "MIFARE"). The title must be re-initialized AFTER the draw call by resetting `_is_title_inited = False` and calling `setTitle('Tag Info')`.

### 3.5 Scan Cache — Native Types Required

The scan cache format from the HANDOVER showed string-quoted values like `"uid": "'B7785E50'"`. These were trace log representations, NOT the actual Python values. The real scan.so returns native types:

```python
# WRONG (initial implementation)
cache = {'found': 'True', 'type': '1', 'uid': "'DAEFB416'", 'len': '4'}

# CORRECT (matching scan.so output format)
cache = {'found': True, 'type': 1, 'uid': 'DAEFB416', 'len': 4}
```

**How this was discovered:** Running `--target=original` and comparing the `[WRITE.write]` log line showed:
```
[WRITE.write] arg1: dict {'uid': 'DAEFB416', 'len': 4, 'sak': '08', ...}
```

The `len` field as string `'4'` vs integer `4` caused write.so to fail silently after `hf mf cgetblk 0` — no PM3 commands beyond the initial card detection, immediate write failure.

### 3.6 nameStr for MF1 Variants

`template.draw()` uses a `nameStr` field in the scan cache to display the card model name. Without it, template.so falls back to the type-number default — always showing "M1 S50 1K (4B)" even for 4K and Mini cards.

```python
if size == '4K':
    cache['nameStr'] = 'M1 S70 4K (%s)' % uidlen
    cache['type'] = 0   # 4K uses type 0
elif size == 'Mini':
    cache['nameStr'] = 'M1 Mini 0.3K'
    cache['type'] = 25  # Mini uses type 25
else:
    cache['nameStr'] = 'M1 S50 1K (%s)' % uidlen
```

**How this was discovered:** Cross-target comparison of `dump_detail_mf1_4k` showed original renders "M1 S70 4K (4B)" while current showed "M1 S50 1K (4B)".

### 3.7 Simulate Button — Gray for Non-Simulatable Types

The Simulate button must be grayed out when the tag type has no simulation support. The check uses SIM_MAP type IDs, not the dump directory key (because `mf1` directory contains 1K, 4K, and Mini — only some are simulatable).

```python
_sim_type_ids = {entry[1] for entry in SIM_MAP}
sim_active = self._scan_cache.get('type', -1) in _sim_type_ids
self.setLeftButton(resources.get_str('simulate'), active=sim_active)
```

Types correctly grayed: MF1 Mini (type 25), T55xx (type 23), EM4X05 (type 24), and any LF type without a SIM_MAP entry.

---

## 4. Test Validation — Per-Gate Assertions

### 4.1 Never Trust State Count Alone

The test harness validates **content** at each critical stage, not just the number of unique screenshots:

```bash
# After selecting type → verify File List entered
wait_for_ui_trigger "M1:Details" "${DUMP_TRIGGER_WAIT}" ...
# Fallback: check M2=Delete
wait_for_ui_trigger "M2:Delete" 5 ...

# After OK from file list → verify Tag Info
wait_for_ui_trigger "title:Tag Info" "${DUMP_TRIGGER_WAIT}" ...
# Fallback: check M1=Simulate
wait_for_ui_trigger "M1:Simulate" 5 ...

# After M2 from file list → verify Delete toast
wait_for_ui_trigger "toast:Delete" "${DUMP_TRIGGER_WAIT}" ...
wait_for_ui_trigger "M1:No" 5 ...

# After write → verify result toast
wait_for_ui_trigger "toast:Write successful" "${WRITE_TRIGGER_WAIT}" ...
```

If a gate fails, the report says exactly what was missing:
```
[FAIL] dump_write_mf1k_success: Write toast 'toast:Write successful' not found (5 states)
```

Not:
```
[FAIL] dump_write_mf1k_success: 5 unique states (expected >= 7)
```

### 4.2 Test Execution on QEMU Server

Tests run on the remote server (`qx@178.62.84.144`, 48 cores) with 1 worker to avoid seed file race conditions on the shared `/mnt/upan/dump/` filesystem.

```bash
# Sync code
sshpass -p proxmark rsync -az --delete --exclude='.git' --exclude='tests/flows/_results' \
  --exclude='__pycache__' --exclude='.development assistant' \
  /home/qx/icopy-x-reimpl/ qx@178.62.84.144:/home/qx/icopy-x-reimpl/

# Run (1 worker mandatory for dump_files)
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cd ~/icopy-x-reimpl && TEST_TARGET=current bash tests/flows/dump_files/test_dump_files_parallel.sh 1'
```

**Do NOT use blind sleeps when waiting for results.** Poll progress actively:
```bash
# Poll every 60s
sshpass -p proxmark ssh qx@178.62.84.144 \
  'cat tests/flows/_results/current/dump_files/scenarios/*/result.txt 2>/dev/null | grep -c PASS'
```

---

## 5. JSON UI Requirements

`src/screens/dump_files.json` defines the state machine with 4 states:

```json
{
    "id": "dump_files",
    "initial_state": "type_list",
    "states": {
        "type_list": {
            "screen": {
                "title": "Dump Files",
                "content": {"type": "list", "items": "{dump_type_list}"},
                "buttons": {"left": "", "right": ""},
                "keys": {
                    "UP": "scroll:-1", "DOWN": "scroll:1",
                    "OK": "run:selectType", "PWR": "finish"
                }
            }
        },
        "file_list": {
            "screen": {
                "title": "Dump Files",
                "content": {"type": "list", "items": "{dump_file_list}"},
                "buttons": {"left": "Details", "right": "Delete"},
                "keys": {
                    "UP": "scroll:-1", "DOWN": "scroll:1",
                    "M1": "run:toggleDateDisplay", "M2": "run:enterDeleteConfirm",
                    "OK": "run:openTagInfo", "PWR": "run:backToTypeList"
                }
            }
        },
        "file_list_empty": {
            "screen": {
                "title": "Dump Files",
                "content": {"type": "text", "text": "No dump info. \\nOnly support:\\n.bin .eml .txt"},
                "buttons": {"left": "", "right": ""},
                "keys": {"PWR": "run:backToTypeList"}
            }
        },
        "delete_confirm": {
            "screen": {
                "title": "Dump Files",
                "content": {"type": "empty"},
                "toast": {"text": "Delete?", "timeout": 0},
                "buttons": {"left": "No", "right": "Yes"},
                "keys": {
                    "M1": "run:cancelDelete", "M2": "run:confirmDelete",
                    "PWR": "run:backToTypeList"
                }
            }
        }
    }
}
```

Key requirements:
- `type_list` is `initial_state` — NOT `file_list`
- Type list has **no softkey buttons** (empty strings)
- File list PWR is `run:backToTypeList`, NOT `finish`
- Delete confirm PWR is `run:backToTypeList` (universal back)
- `detail_view` state removed — replaced by pushing ReadFromHistoryActivity as a sub-activity

---

## 6. No-Middleware Rules

### 6.1 The Rule

CardWalletActivity and ReadFromHistoryActivity send **ZERO** PM3 commands. They are:
- **CardWalletActivity:** A file browser. Reads directories, lists files, deletes files.
- **ReadFromHistoryActivity:** A file parser + sub-activity launcher. Parses filenames, populates scan cache, pushes WarningWriteActivity/SimulationActivity.

All RFID logic lives in the .so modules (write.so, scan.so, template.so) which are called by WriteActivity, SimulationActivity, etc.

### 6.2 Middleware Instances Found and Avoided

| Instance | What It Would Be | Why It's Wrong | Correct Approach |
|----------|-----------------|----------------|------------------|
| Parsing dump file contents for RFID data | Read .bin file, extract sectors | ReadFromHistoryActivity just parses the FILENAME, not the file content. write.so reads the file. |
| Building PM3 write commands | `hf mf wrbl` in Python | write.so builds and sends ALL PM3 commands via executor.startPM3Task |
| Tag type detection from file | Read header bytes, determine protocol | The filename encodes the type (M1-, T55xx_, EM410x-ID_). Parse the name, not the data. |
| Scan cache with computed fields | Calculate BCC, derive SAK from UID length | Use constants from the original firmware. SAK=08, ATQA=0004 for all MF1 variants (matching original behavior). |

### 6.3 The Erase Exception

The Erase flow is the **only** justified exception to the no-middleware rule. This is because:

1. **No `erase.so` exists.** Erase logic is embedded directly in `activity_main.so`'s `WipeTagActivity` class.
2. **Our Python reimplements `activity_main.so`.** Since WipeTagActivity is part of the binary we're replacing, its PM3 command sequences belong in our code.
3. **The .so modules have wrong APIs for erase.** `write.so`, `hfmfkeys.so`, `lft55xx.so` don't expose erase-specific functions.

**Structure implemented for Erase:**
```
src/middleware/erase.py    # PM3 command dispatch for erase operations
    detect_mf1_tag()       # hf 14a info → determine MF1 subtype
    erase_mf1_detected()   # fchk → wrbl ×64 (with progress callback)
    erase_t5577()          # lf t55xx wipe (with password detection)
```

`src/middleware/` is on `sys.path` with priority, loaded by the launcher. This pattern can be extended for future middleware needs, but should ONLY be used when no .so module provides the required API.

---

## 7. QEMU Validation Methodology

### 7.1 Original Firmware as Reference

Every behavior was validated by running the same scenario against the original firmware:

```bash
# Run original
TEST_TARGET=original SCENARIO=dump_detail_mf1_1k FLOW=dump_files \
  bash tests/flows/dump_files/scenarios/dump_detail_mf1_1k/dump_detail_mf1_1k.sh

# Run current
TEST_TARGET=current SCENARIO=dump_detail_mf1_1k FLOW=dump_files \
  bash tests/flows/dump_files/scenarios/dump_detail_mf1_1k/dump_detail_mf1_1k.sh

# Compare state dumps
diff <(python3 -c "...extract Tag Info state from original...") \
     <(python3 -c "...extract Tag Info state from current...")
```

### 7.2 State Dump Inspection

The launcher's `_dump_state()` captures complete application state as JSON:
```json
{
    "title": "Tag Info",
    "M1": "Simulate", "M2": "Write",
    "M1_active": true, "M2_active": true,
    "content_text": [
        {"text": "M1 S50 1K (4B)", "x": 18, "y": 82, "font": "mononoki 14"},
        {"text": "Frequency: 13.56MHZ", "x": 18, "y": 106, "font": "mononoki 13"},
        {"text": "UID: DAEFB416", "x": 18, "y": 128},
        {"text": "SAK: 08  ATQA: 0004", "x": 18, "y": 151}
    ],
    "scan_cache": {"found": true, "type": 1, "uid": "DAEFB416", "len": 4},
    "current_activity": "ReadFromHistoryActivity"
}
```

This allowed detecting issues that screenshots alone couldn't reveal: wrong type numbers, missing scan cache fields, inactive button states.

### 7.3 Using strace for Vital Information

Real device traces (captured via strace on the device SSH) provided the ground truth for:
- **Bundle formats:** HF types pass file path strings, LF types pass scan cache dicts, T55xx passes `{'file': path}`
- **Scan cache format:** Exact key names and value types from scan.setScanCache calls
- **Activity stack depth:** ReadFromHistoryActivity sits between CardWalletActivity and WarningWriteActivity (depth=4 during write)
- **PM3 command sequences:** Exact order of `hf 14a info` → `hf mf cgetblk 0` → `hf mf fchk` → `hf mf wrbl ×64`

These traces were captured during Phase 1 and documented in the HANDOVER. They provided the **iterative, provable** integration path: implement one behavior, verify against the trace, proceed to the next.

---

## 8. Summary

### 8.1 Problems and Solutions

| # | Problem | Root Cause | Solution | How Verified |
|---|---------|-----------|----------|--------------|
| 1 | No type list | Stub jumped straight to file list | Added MODE_TYPE_LIST with 28 fixed-order types | `title:Dump Files` + content check |
| 2 | QEMU can't see seed files | QEMU_LD_PREFIX redirects file access to rootfs | Symlink rootfs `/mnt/upan/dump` → host path | `os.listdir()` returns files under QEMU |
| 3 | Write fails silently | `len` field was string `'4'` not integer `4` | Use native Python types in scan cache | `[PM3] cmd=hf mf fchk` appears in log |
| 4 | Wrong nameStr for 4K/Mini | scan cache missing `nameStr` field | Add `nameStr` per MF1 variant | Cross-target comparison of content_text |
| 5 | Simulate active for Mini | Check used directory key, not type number | Check against SIM_MAP type ID set | `M1_active=False, fill=#808080` |
| 6 | template.draw overwrites title | template.so draws its own title bar | Reset `_is_title_inited`, re-call `setTitle()` | `title='Tag Info'` in state dump |
| 7 | No write chain | Missing onActivity handler | Added handler mirroring AutoCopyActivity pattern | Full write pipeline: 7+ unique states |
| 8 | PWR exits instead of back | finish() called from file list | `_backToTypeList()` returns to type list mode | `title:Dump Files` after PWR from file list |
| 9 | M1 says "Simulation" | Wrong resource key | Changed to `resources.get_str('simulate')` | `M1='Simulate'` matches original |
| 10 | No delete confirmation | Immediate delete on M2 | Toast "Delete?" with M1=No/M2=Yes/PWR=type list | `toast:Delete` + `M1:No` gates |

### 8.2 What Would Have Made This Faster

1. **QEMU_LD_PREFIX file redirection documented upfront.** This cost 45+ minutes of debugging. A single note — "QEMU redirects /mnt/upan/ to rootfs; create symlinks" — would have saved the entire investigation.

2. **Scan cache type examples with ACTUAL Python types.** The HANDOVER showed trace log representations (`"type": "1"`, `"uid": "'B7785E50'"`). These looked like the real values but were string-escaped log output. A note saying "scan.so returns `type=1` (int), `uid='B7785E50'` (str without quotes), `found=True` (bool)" would have prevented the write failure.

3. **template.draw() title overwrite behavior documented.** A one-line note — "template.draw clears the canvas including the title bar; call setTitle AFTER with `_is_title_inited=False`" — would have saved the title debugging.

4. **SIM_MAP type IDs listed alongside dump types.** The mapping from dump_type_key to sim_index was indirect (directory → type number → SIM_MAP search). A lookup table in the HANDOVER would have been cleaner.

5. **SAK/ATQA constant behavior documented.** The original firmware uses SAK=08/ATQA=0004 for ALL MF1 variants regardless of size. The HANDOVER listed different values per size (4K→18/0002, Mini→09/0044). Cross-target comparison revealed the orignal uses constants.

---

## 9. Final Test Results

```
========================================
  DUMP FILES FLOW TEST SUMMARY
========================================
  Total:   35
  PASS:    35
  FAIL:    0
  MISSING: 0
  Time:    1531s (1 workers)
========================================
```

35 scenarios covering: type list (empty/single/multi/scroll), file list (browse/scroll/empty/date), delete (confirm_yes/confirm_no/pwr_cancel/last_file), tag info (mf1_1k/mf1_4k/mf1_mini/uid_based/t55xx/lf_id), simulate (hf/lf), write (mf1k_success/mf1k_fail/mf1k_gen1a/mf1k_verify_success/mf1k_verify_fail/mfu_success/lf_success/t55xx_success/t55xx_fail/cancel), PWR navigation (type_list/file_list/tag_info/data_ready/warning_write).
