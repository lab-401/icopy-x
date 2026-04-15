# WipeTagActivity — Exhaustive UI Mapping

Source: `activity_main.so` decompiled via Ghidra (string table in `activity_main_strings.txt`)
Real device trace: `docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt`
Screenshots: `docs/Real_Hardware_Intel/Screenshots/v1090_captures/090-Erase-Types*.png`
String table: `resources.py` StringEN

---

## 1. Activity Identity

### Module Location

Binary: `orig_so/lib/activity_main.so`
String references: `docs/v1090_strings/activity_main_strings.txt` lines 20574-23169
Binary string symbols: `docs/V1090_SO_STRINGS_RAW.txt` lines 69-133

**Note**: Despite the task prompt referencing WriteActivity for erase, WipeTagActivity
EXISTS as its own class in `activity_main.so`. This is confirmed by 40+ symbol references
in the binary string table (activity_main_strings.txt lines 20574-23169).

### Class Methods (from binary string table)

```
WipeTagActivity.__init__                (activity_main_strings.txt:21222)
WipeTagActivity.getManifest             (activity_main_strings.txt:21074)
WipeTagActivity.onCreate                (activity_main_strings.txt:21167)
WipeTagActivity.onKeyEvent              (activity_main_strings.txt:21103)
WipeTagActivity.start_wipe              (activity_main_strings.txt:21102)
WipeTagActivity.wipe_m1                 (activity_main_strings.txt:21185)
WipeTagActivity.wipe_magic_m1           (activity_main_strings.txt:21025)
WipeTagActivity.wipe_std_m1             (activity_main_strings.txt:21073)
WipeTagActivity.wipe_t5577              (activity_main_strings.txt:21101)
WipeTagActivity.call_on_write_magic_m1  (activity_main_strings.txt:20891)
WipeTagActivity.call_on_write_std_m1    (activity_main_strings.txt:20890)
WipeTagActivity.call_on_wipe_t55xx      (activity_main_strings.txt:20892)
```

---

## 2. State Machine

### STATE: TYPE_SELECT (Initial)

**Screenshot evidence**: `090-Erase-Types.png`

- **Title**: "Erase Tag" (resources.py StringEN.title.wipe_tag, line 7)
- **View type**: ListView (standard list, NOT CheckedListView)
- **Items**: 2 items, single page
  - Item 0: "1. Erase MF1/L1/L2/L3" (prefixed numbering visible in screenshot)
    - Resource key: `wipe_m1` (resources.py StringEN.itemmsg.wipe_m1 = "Erase MF1/L1/L2/L3", line 11)
    - Display format: "1. " + wipe_m1 value
  - Item 1: "2. Erase T5577"
    - Resource key: `wipe_t55xx` (resources.py StringEN.itemmsg.wipe_t55xx = "Erase T5577", line 11)
    - Display format: "2. " + wipe_t55xx value
- **Footer**: None visible in TYPE_SELECT screenshot
- **Navigation**:
  - UP/DOWN: Navigate list cursor
  - OK: Select erase type, transition to SCANNING
  - PWR: Exit activity (universal back)

### STATE: SCANNING (After type selection)

**Screenshot evidence**: `erase_tag_menu_2.png`, `erase_tag_scanning.png`, `090-Erase-Types-Erase.png`

- **Title**: "Erase Tag" (with battery indicator in title bar)
- **Content**: Progress bar with text "Scanning..." (resources.py StringEN.procbarmsg.scanning, line 10)
  - ProgressBar position: bottom of content area, blue fill bar on left, grey track extending right
  - Text "Scanning..." displayed above the progress bar, centered horizontally
- **Footer**: None (operation in progress, no button labels visible)
- **Operation**:
  - For MF1: Sends `hf 14a info` (timeout=5000ms) to detect tag
    (trace_erase_flow_20260330.txt line 6-7)
  - For T5577: Sends equivalent LF detection command
- **Navigation**:
  - PWR: Cancel scan, return to TYPE_SELECT

### STATE: ERASING (Tag found, erase in progress)

- **Title**: "Erase Tag"
- **Content**: Progress bar with text "Erasing N%" or "ChkDIC" (dictionary check phase)
  - Dictionary check phase: Shows "ChkDIC" text above progress bar (`erase_tag_menu_3.png`)
  - Erasing phase: Shows "Erasing 0%" text above progress bar (`erase_tag_menu_4.png`, `erase_tag_menu_5.png`)
  (resources.py StringEN.procbarmsg.tag_wiping = "Erasing...", line 10)
  (resources.py StringEN.procbarmsg.wipe_block = "Erasing", line 10)
- **Footer buttons** (visible after erase attempt completes):
  - M1: "Erase" (resources.py StringEN.button.wipe = "Erase", line 6)
  - M2: "Erase" (resources.py StringEN.button.wipe = "Erase", line 6)

**Screenshot citations**:
- `erase_tag_menu_3.png`: "ChkDIC" text with blue progress bar during dictionary key check
- `erase_tag_menu_4.png`: "Erasing 0%" with blue progress bar
- `erase_tag_menu_5.png`: "Erasing 0%" with thinner blue progress bar (progress advancing)
- `erase_tag_menu_6.png`: Post-erase state with M1="Erase", M2="Erase" buttons visible, no progress bar

- **Operation flow for MF1 erase** (from trace_erase_flow_20260330.txt):
  1. Detect tag: `hf 14a info` (line 9)
  2. Try Gen1a magic wipe: `hf mf cwipe` timeout=28888ms (line 10)
  3. If Gen1a detected (UID changes to 01020304): Gen1a path
  4. If standard card: Key check via `hf mf fchk` (line 21)
  5. Block-by-block erase: `hf mf wrbl {block} A ffffffffffff 00000000...` (lines 23+)
  6. Writes zeros to data blocks, transport config to trailer blocks
  7. Progress shown as "Erasing" with block counter

- **Operation flow for T5577 erase** (from V1090_ERASE_FLOW_COMPLETE.md):
  1. `lf t55xx wipe` -- no password attempt
  2. `lf t55xx wipe p FFFFFFFF` -- default password attempt
  3. `lf t55xx wipe p {key}` -- known key attempt (if available)
  4. Fallback chain through wipe0/wipe1/wipe_t/wipe methods

### STATE: RESULT_SUCCESS (Erase completed)

- **Content**: Toast overlay showing:
  "Erase successful"
  (resources.py StringEN.toastmsg.wipe_success, line 8)
- **Navigation**:
  - Any key or toast timeout: Return to TYPE_SELECT

### STATE: RESULT_FAIL (Erase failed)

**Screenshot evidence**: `090-Erase-Types-Erase-Failed.png`

- **Content**: Toast overlay showing one of:
  - "No tag found" (resources.py StringEN.toastmsg.no_tag_found, line 8)
  - "Erase failed" (resources.py StringEN.toastmsg.wipe_failed, line 8)
  - "Unknown error" (resources.py StringEN.toastmsg.err_at_wiping, line 8)
- **Footer buttons visible**: M1="Erase", M2="Erase" (from screenshot)
- **Navigation**:
  - M1/M2: Retry erase
  - PWR: Return to TYPE_SELECT

### STATE: NO_KEYS (MF1 erase without valid keys)

- **Content**: Toast overlay showing:
  "No valid keys, Please use 'Auto Copy' first, Then erase"
  (resources.py StringEN.toastmsg.wipe_no_valid_keys, line 8)
- **Navigation**:
  - Any key or toast timeout: Return to TYPE_SELECT

---

## 3. Erase Methods Detail

### wipe_m1 (activity_main_strings.txt:21185)

Master MF1 erase dispatcher. Determines whether the detected card is Gen1a
(magic) or standard, then delegates accordingly.

Decision logic:
1. Sends `hf 14a info` to detect tag
2. Sends `hf mf cgetblk 0` to test for Gen1a magic card
   - If response contains `wupC1 error` -> NOT Gen1a, use `wipe_std_m1`
   - If response returns block 0 data -> IS Gen1a, use `wipe_magic_m1`

### wipe_magic_m1 (activity_main_strings.txt:21025)

Gen1a magic card erase:
1. `hf mf cwipe` -- wipes all blocks via backdoor commands (timeout=28888ms)
2. Progress shown block by block: `[|]wipe block 0[/]wipe block 1...`

### wipe_std_m1 (activity_main_strings.txt:21073)

Standard MF1 card erase (requires keys):
1. Check keys via `hf mf fchk` -- verifies all sector keys are known
2. If no keys -> show `wipe_no_valid_keys` toast, abort
3. For each sector, for each block:
   - Data blocks: write `00000000000000000000000000000000`
   - Trailer blocks: write `FFFFFFFFFFFFFF078069FFFFFFFFFFFF` (transport config)
   - Command: `hf mf wrbl {block} A {key} {data}` (timeout=5888ms)
   - Success check: response contains `isOk:01`
4. Blocks are erased in reverse sector order (from trace: 240,241,...254, then 224,...238, etc.)

### wipe_t5577 (activity_main_strings.txt:21101)

T55xx erase with fallback chain:
1. `lf t55xx wipe` (no password)
2. `lf t55xx wipe p FFFFFFFF` (default password)
3. `lf t55xx wipe p {key}` (known key if available)

### call_on_write_magic_m1 (activity_main_strings.txt:20891)

Callback for Gen1a magic write completion during erase operation.

### call_on_write_std_m1 (activity_main_strings.txt:20890)

Callback for standard M1 write completion during erase operation.

### call_on_wipe_t55xx (activity_main_strings.txt:20892)

Callback for T55xx wipe completion.

---

## 4. PM3 Command Reference (from real device trace)

All commands from `docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt`:

| Command | Timeout | Purpose |
|---------|---------|---------|
| `hf 14a info` | 5000ms | Detect HF tag |
| `hf mf cwipe` | 28888ms | Gen1a magic wipe (all blocks) |
| `hf mf cgetblk 0` | 5888ms | Test for Gen1a backdoor |
| `hf mf fchk 4 /tmp/.keys/mf_tmp_keys` | 600000ms | Key check (10 min timeout) |
| `hf mf wrbl {block} A {key} {data}` | 5888ms | Write block data |

---

## 5. String Resource Cross-Reference

| Category | Key | Value | resources.py line |
|----------|-----|-------|-------------------|
| title | wipe_tag | "Erase Tag" | 7 |
| button | wipe | "Erase" | 6 |
| toastmsg | wipe_success | "Erase successful" | 8 |
| toastmsg | wipe_failed | "Erase failed" | 8 |
| toastmsg | wipe_no_valid_keys | "No valid keys, Please use 'Auto Copy' first, Then erase" | 8 |
| toastmsg | err_at_wiping | "Unknown error" | 8 |
| toastmsg | no_tag_found | "No tag found" | 8 |
| itemmsg | wipe_m1 | "Erase MF1/L1/L2/L3" | 11 |
| itemmsg | wipe_t55xx | "Erase T5577" | 11 |
| procbarmsg | scanning | "Scanning..." | 10 |
| procbarmsg | tag_wiping | "Erasing..." | 10 |
| procbarmsg | wipe_block | "Erasing" | 10 |

---

## Corrections Applied

1. **SCANNING state**: Added screenshot citations and documented ProgressBar position (bottom of content area, blue fill bar). Citations: `erase_tag_menu_2.png`, `erase_tag_scanning.png`.
2. **ERASING state**: Added documentation for "ChkDIC" dictionary check phase and "Erasing N%" progress display. Citations: `erase_tag_menu_3.png` (ChkDIC), `erase_tag_menu_4.png`/`erase_tag_menu_5.png` (Erasing 0%).
3. **RESULT_FAIL state**: Confirmed button labels M1="Erase", M2="Erase" match `erase_tag_unknown_error.png` and `erase_tag_menu_6.png`. No corrections needed for button labels.
4. **TYPE_SELECT state**: Confirmed matches `erase_tag_menu_1.png` — no corrections needed.
5. **ChkDIC note**: The "ChkDIC" text visible in `erase_tag_menu_3.png` is a middleware progress message from the erase operation, not a separate UI state. Documented as part of the ERASING state progression.

---

## Key Bindings

### WipeTagActivity.onKeyEvent (activity_main_ghidra_raw.txt)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TYPE_SELECT | prev() | next() | no-op | no-op | startErase() | finish() | startErase() | finish() |
| ERASING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | cancel + finish() |
| SUCCESS | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |
| FAILED | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |
| NO_KEYS | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |

**Notes:**
- TYPE_SELECT: 2-item list (Erase MF1, Erase T5577). UP/DOWN scroll. M2/OK start erase, M1/PWR exit.
- ERASING: Only PWR can abort (cancels PM3 task then exits).
- Result states: Any action key exits.

**Source:** `src/lib/activity_main.py` lines 2403-2431.
