# Read Tag — Exhaustive UI Mapping

## Covered Activities

| Activity            | Binary symbol prefix                          | .so file          |
|---------------------|-----------------------------------------------|-------------------|
| ReadListActivity    | `__pyx_pw_13activity_main_16ReadListActivity_` | activity_main.so  |
| ReadActivity        | `__pyx_pw_13activity_main_12ReadActivity_`     | activity_main.so  |
| WarningM1Activity   | `__pyx_pw_13activity_main_17WarningM1Activity_`| activity_main.so  |
| KeyEnterM1Activity  | `__pyx_pw_13activity_main_18KeyEnterM1Activity_`| activity_main.so |

Binary source: `/home/qx/icopy-x-reimpl/decompiled/activity_main_ghidra_raw.txt`
String table: `/home/qx/icopy-x-reimpl/src/lib/resources.py` (StringEN dicts)

---

## 1. ReadListActivity — Tag Type Selection

### 1.1 Activity Identity

- **ACT_NAME**: `read_list`
- **Binary methods** (from STR table, activity_main_ghidra_raw.txt lines 326-627):
  - `getManifest` (line 465, @0x00059de8)
  - `__init__` (line 626, @0x000cdb8c)
  - `initList` (line 463, @0x00059230)
  - `showScanToast` (line 462, @0x00058884)
  - `how2Scan` (line 343, @0x000322c4)
  - `onAutoScan` (line 336, @0x00031870)
  - `set_tag_list_enable` (line 458, @0x000574a0)
  - `onCreate` (line 460, @0x0005805c)
  - `onKeyEvent` (line 456, @0x000550b0)

### 1.2 Screen Layout

```
+---------------------------------------+
|  Read Tag 1/8              [battery]  |  <- Title bar: 40px, Consolas 18, white on grey-purple
+---------------------------------------+
|  1. M1 S50 1K 4B                     |  <- Content: 160px area
|  2. M1 S50 1K 7B                     |     ListView: 5 items per page
|  3. M1 S70 4K 4B                     |     mononoki 16, black on white
|  4. M1 S70 4K 7B                     |     Selected item: dark highlight bar
|  5. M1 Mini                          |
+---------------------------------------+
|  (no button bar on this screen)       |  <- Button bar: NOT visible by default
+---------------------------------------+
```

**Evidence**: Framebuffer capture `read_mf1k_4b/0050.png` shows exactly this layout: title "Read Tag 1/8", 5 items (1-5), no button bar visible.

### 1.3 Page Indicator

The page indicator is embedded in the title string, NOT a separate widget.

- Format: `"Read Tag N/M"` where N=current page, M=total pages
- Title key: `resources.get_str('read_tag')` = `"Read Tag"` (resources.py line 76)
- Pagination: `ceil(40 items / 5 per page) = 8` total pages

**Evidence**:
- `read_mf1k_4b/0050.png`: title shows "Read Tag 1/8"
- `read_ultralight_ev1/0000.png`: title shows "Read Tag 2/8"
- `read_ntag216/0000.png`: title shows "Read Tag 3/8"
- `read_iclass_legacy/0000.png`: title shows "Read Tag 4/8"

### 1.4 Complete Tag Type List (40 items, 8 pages)

Source: Real device framebuffer captures + `activity_main.py` line 2148 `READABLE_TYPES`, verified on real device 2026-03-25.

| # | Display Name     | Type ID | Page | Frequency |
|---|------------------|---------|------|-----------|
| 1 | M1 S50 1K 4B    | 1       | 1/8  | HF        |
| 2 | M1 S50 1K 7B    | 42      | 1/8  | HF        |
| 3 | M1 S70 4K 4B    | 0       | 1/8  | HF        |
| 4 | M1 S70 4K 7B    | 41      | 1/8  | HF        |
| 5 | M1 Mini          | 25      | 1/8  | HF        |
| 6 | M1 Plus 2K       | 26      | 2/8  | HF        |
| 7 | Ultralight       | 2       | 2/8  | HF        |
| 8 | Ultralight C     | 3       | 2/8  | HF        |
| 9 | Ultralight EV1   | 4       | 2/8  | HF        |
| 10 | NTAG213 144b    | 5       | 2/8  | HF        |
| 11 | NTAG215 504b    | 6       | 3/8  | HF        |
| 12 | NTAG216 888b    | 7       | 3/8  | HF        |
| 13 | ISO15693 ICODE  | 19      | 3/8  | HF        |
| 14 | ISO15693 ST SA  | 46      | 3/8  | HF        |
| 15 | Legic MIM256    | 20      | 3/8  | HF        |
| 16 | Felica          | 21      | 4/8  | HF        |
| 17 | iClass Legacy   | 17      | 4/8  | HF        |
| 18 | iClass Elite    | 18      | 4/8  | HF        |
| 19 | EM410x ID       | 8       | 4/8  | LF        |
| 20 | HID Prox ID     | 9       | 4/8  | LF        |
| 21 | Indala ID       | 10      | 5/8  | LF        |
| 22 | AWID ID         | 11      | 5/8  | LF        |
| 23 | IO Prox ID      | 12      | 5/8  | LF        |
| 24 | GProx II ID    | 13      | 5/8  | LF        |
| 25 | Securakey ID    | 14      | 5/8  | LF        |
| 26 | Viking ID       | 15      | 6/8  | LF        |
| 27 | Pyramid ID      | 16      | 6/8  | LF        |
| 28 | FDXB ID         | 28      | 6/8  | LF        |
| 29 | GALLAGHER ID    | 29      | 6/8  | LF        |
| 30 | Jablotron ID    | 30      | 6/8  | LF        |
| 31 | KERI ID         | 31      | 7/8  | LF        |
| 32 | NEDAP ID        | 32      | 7/8  | LF        |
| 33 | Noralsy ID      | 33      | 7/8  | LF        |
| 34 | PAC ID          | 34      | 7/8  | LF        |
| 35 | Paradox ID      | 35      | 7/8  | LF        |
| 36 | Presco ID       | 36      | 8/8  | LF        |
| 37 | Visa2000 ID     | 37      | 8/8  | LF        |
| 38 | NexWatch ID     | 45      | 8/8  | LF        |
| 39 | T5577           | 23      | 8/8  | LF        |
| 40 | EM4305          | 24      | 8/8  | LF        |

**Screenshot evidence for pages 1-4**:
- Page 1: `read_mf1k_4b/0050.png` shows items 1-5
- Page 2: `read_ultralight_ev1/0000.png` shows items 6-10
- Page 3: `read_ntag216/0000.png` shows items 11-15
- Page 4: `read_iclass_legacy/0000.png` shows items 16-20

### 1.5 Key Bindings — ReadListActivity

Source: decompiled `onKeyEvent` at activity_main_ghidra_raw.txt line 37648 (@0x000550b0).

| Key   | Action                                        |
|-------|-----------------------------------------------|
| UP    | ListView.prev() + update title page indicator |
| DOWN  | ListView.next() + update title page indicator |
| M2    | Launch ReadActivity with selected type (how2Scan) |
| OK    | Same as M2                                    |
| M1    | finish() — return to Main Page                |
| PWR   | finish() — universal exit/back                |

**Binary evidence**: The `onKeyEvent` decompilation (line 37648) shows a -1 comparison branch (line 37765: `piVar1[2] == -1`). When key == -1 (PWR), it takes a separate exit path. The other branches compare against key constants for UP/DOWN/M1/M2/OK.

### 1.6 Button Bar — ReadListActivity

**Not visible on screen by default.** The framebuffer captures (read_mf1k_4b/0050.png, read_ultralight_ev1/0000.png, etc.) show NO button bar at the bottom. The full 200px below the title is used by the ListView.

However, from the binary `onCreate` (line 40243), the activity calls setLeftButton and setRightButton. The button labels are set but the button bar is visually absent in captures. This is consistent with the original firmware design where the buttons are mapped to physical keys with no on-screen labels for this particular list screen.

### 1.7 initList() — Tag List Population

Source: decompiled `initList` at line 41235 (@0x00059230).

Flow:
1. Call `tagtypes.getReadable()` to get list of readable type IDs
2. For each type ID, call `tagtypes.getTypeName(type_id)` to get display name
3. Build indexed list for ListView: `{index: (type_name, index+1)}`
4. Set item count and page state

The `initList` function in the binary creates an ordered dictionary mapping each item name to a tuple of `(display_name, 1-based_index)`. This is consistent with the numbered list format seen in screenshots ("1. M1 S50 1K 4B").

### 1.8 how2Scan() — Launch ReadActivity

Source: decompiled `how2Scan` at line 6616 (@0x000322c4).

Flow:
1. Get currently selected item index from ListView
2. Map index to `tag_type` ID and `tag_name` string
3. Build bundle: `{'tag_type': type_id, 'tag_name': tag_name}`
4. Call `actstack.start_activity(ReadActivity, bundle)`

---

## 2. ReadActivity — Scanning + Reading

### 2.1 Activity Identity

- **ACT_NAME**: `read`
- **Binary methods** (from STR table):
  - `getManifest` (line 326, @0x0002f418)
  - `__init__` (line 571, @0x000cceb8)
  - `startRead` (line 567, @0x000ccdfc)
  - `stopRead` (line 394, @0x000ca580)
  - `showReadToast` (line 533, @0x000cc534)
  - `hideReadToast` (line 393, @0x000ca548)
  - `canidle` (line 412, @0x000ca9e0)
  - `onCreate` (line 494, @0x000cbcdc)
  - `onResume` (line 498, @0x000cbd44)
  - `onDestroy` (line 496, @0x000cbcdc)
  - `onData` (line 566, @0x000ccd94)
  - `onKeyEvent` (line 573, @0x000ccf20)

### 2.2 State Machine

ReadActivity is a multi-phase state machine. The phases are driven by callbacks from scan.so and read.so via `onData()`.

```
SCANNING --> TAG_FOUND --> READING --> READ_SUCCESS
    |            |             |           |
    v            v             v           v
NO_TAG_FOUND  WRONG_TYPE  MISSING_KEYS  READ_PARTIAL
                                |           |
                                v           v
                          WarningM1     WRITE_PROMPT
                          Activity
```

### 2.3 State: Scanning

**Title**: "Read Tag" (no page indicator — plain title)
**Evidence**: `read_mf1k_4b/0070.png`, `read_mf1k_nested/0000.png`

```
+---------------------------------------+
|  Read Tag                  [battery]  |  <- Title: "Read Tag" (resources key: read_tag)
+---------------------------------------+
|                                       |
|                                       |
|            Scanning...                |  <- procbarmsg 'scanning' = "Scanning..."
|  [====       progress bar       ]     |  <- ProgressBar widget, blue fill
+---------------------------------------+
|  (no button bar)                      |
+---------------------------------------+
```

**Key bindings during SCANNING**:

| Key | Action |
|-----|--------|
| PWR | finish() — abort scan and return |
| All others | Ignored (busy state) |

**Evidence**: `read_mf1k_4b/0070.png` shows "Scanning..." with progress bar. `read_mf1k_nested/0010.png` shows same state with more progress fill.

### 2.4 State: Tag Found — Tag Info Display

After scan completes successfully, the tag info is displayed and reading begins automatically.

**Title**: "Read Tag" (unchanged)
**Evidence**: `read_mf1k_4b/0090.png`, `read_mf1k_nested/0025.png`

```
+---------------------------------------+
|  Read Tag                  [battery]  |
+---------------------------------------+
|  MIFARE                               |  <- Tag family name (from scan result)
|  M1 S50 1K (4B)                       |  <- Type name with UID length
|  Frequency: 13.56MHZ                  |  <- Frequency
|  UID: 2CADC272                        |  <- Tag UID (hex)
|  SAK: 08  ATQA: 0004                  |  <- SAK and ATQA values
|                                       |
|            Reading...                 |  <- procbarmsg 'reading' = "Reading..."
+---------------------------------------+
|  (no button bar)                      |
+---------------------------------------+
```

**Evidence**: `read_mf1k_4b/0090.png` shows exactly this layout for a MIFARE Classic 1K 4B tag with UID 2CADC272.

### 2.5 State: Key Checking (MIFARE only)

For encrypted MIFARE tags, a key checking phase precedes the read.

**Evidence**: `read_mf1k_4b/0100.png`

```
+---------------------------------------+
|  Read Tag                  [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)                       |
|  Frequency: 13.56MHZ                  |
|  UID: 2CADC272                        |
|  SAK: 08  ATQA: 0004                  |
|                                       |
|           01'06''                      |  <- Elapsed time (procbarmsg time format)
|      ChkDIC...32/32keys               |  <- Dictionary check progress
+---------------------------------------+
```

**Evidence**: `read_mf1k_4b/0100.png` shows "01'06'' ChkDIC...32/32keys". The time format matches `procbarmsg['time<1h']` = `"      %02d'%02d''"`.

For tags with unknown keys, the flow enters Nested/Darkside cracking:

**Evidence**: `read_mf1k_nested/0029.png` shows "01'09'' ChkDIC...0/32keys" — zero keys found during dictionary check, will proceed to cracking.

### 2.6 State: Reading with Key Progress

**Evidence**: `read_mf1k_4b/0110.png`

```
+---------------------------------------+
|  Read Tag                  [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)                       |
|  Frequency: 13.56MHZ                  |
|  UID: 2CADC272                        |
|  SAK: 08  ATQA: 0004                  |
|                                       |
|      Reading...32/32Keys              |  <- procbarmsg 'reading_with_keys' format
+---------------------------------------+
```

The progress message format is `procbarmsg['reading_with_keys']` = `"Reading...{}/{}Keys"` (resources.py line 188).

**Evidence**: `read_mf1k_4b/0110.png` through `0170.png` all show "Reading...32/32Keys" with the progress bar advancing.

### 2.7 State: Read Success

**Title**: "Read Tag"
**Evidence**: `read_mf1k_4b/0200.png`, `Step - 2.png`

```
+---------------------------------------+
|  Read Tag                  [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)     +--------+       |
|  Frequency: 13.56MHZ| Read   |       |
|  UID: 2CADC272       |Successf|       |  <- Toast overlay with checkmark icon
|  SAK: 08  ATQA: 0004|ul!     |       |
|                      |File    |       |
|                      |saved   |       |
+---------------------------------------+
|  Reread              Write            |  <- M1="Reread", M2="Write"
+---------------------------------------+
```

Toast message: `toastmsg['read_ok_1']` = `"Read\nSuccessful!\nFile saved"` (resources.py line 105)

**Evidence**: `read_mf1k_4b/0200.png` shows the toast "Read Successful! File saved" with check icon overlaid on tag info. Button bar shows "Reread" (left) and "Write" (right).

**Key bindings**:

| Key | Action |
|-----|--------|
| M1  | startRead() again (Reread) |
| M2  | Launch WarningWriteActivity (proceed to write) |
| OK  | Same as M2 |
| PWR | finish() — exit to ReadListActivity |

### 2.8 State: Read Success (Partial)

When some sectors cannot be read (missing keys), a partial success toast is shown.

Toast message: `toastmsg['read_ok_2']` = `"Read\nSuccessful!\nPartial data\nsaved"` (resources.py line 104)

**Button bar**: M1="Reread", M2="Write" (same as full success)

### 2.9 State: Read Failed

Toast message: `toastmsg['read_failed']` = `"Read Failed!"` (resources.py line 106)

**Button bar**: M1="Reread", M2 not shown or disabled

**Key bindings**:

| Key | Action |
|-----|--------|
| M1  | startRead() again (retry) |
| PWR | finish() — exit |

### 2.10 State: No Tag Found

When scan times out without finding a matching tag.

Toast message: `toastmsg['no_tag_found2']` = `"No tag found \nOr\n Wrong type found!"` (resources.py line 107)

**Button bar**: M1="Rescan", M2="Rescan" — both buttons show "Rescan"

**Screenshot citations**:
- `read_tag_no_tag_or_wrong_type_1.png`: Toast "No tag found Or Wrong type found!" displayed, no buttons visible yet (toast still showing)
- `read_tag_no_tag_or_wrong_type_2.png`: After toast dismissal, both M1="Rescan" (left) and M2="Rescan" (right) visible

### 2.11 State: Missing Keys (MIFARE)

When read.so reports that key checking failed or timed out, the activity launches **WarningM1Activity** to present recovery options.

This transition is handled via `onData()` callback from read.so. The `onData` method (decompiled at line 566) processes the result code and decides the next action.

### 2.12 Key Bindings — ReadActivity

Source: decompiled `onKeyEvent` at activity_main_ghidra_raw.txt line 573 (symbol @0x000ccf20).

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | startScan() | finish() | startScan() | finish() |
| SCANNING | no-op | no-op | no-op | no-op | no-op | cancel + IDLE | cancel + IDLE | cancel + finish() |
| SCAN_FOUND | no-op | no-op | no-op | no-op | startRead() | startScan() | startRead() | finish() |
| READING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | cancel + finish() |
| READ_SUCCESS | no-op | no-op | no-op | no-op | launchWrite() | reread() | launchWrite() | finish() |
| READ_PARTIAL | no-op | no-op | no-op | no-op | launchWrite() | reread() | launchWrite() | finish() |
| READ_FAILED | no-op | no-op | no-op | no-op | no-op | reread() | no-op | finish() |
| ERROR | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |

**Notes:**
- IDLE: M2/OK start scan for the configured tag type. M1/PWR exit.
- SCANNING: M1/M2 cancel scan, return to IDLE. PWR cancels and exits.
- SCAN_FOUND: M2/OK start read operation. M1 rescans.
- READING: Only PWR works (cancel read + exit). All other keys blocked.
- READ_SUCCESS/READ_PARTIAL: M2/OK launch WarningWriteActivity (write prompt). M1 re-reads.
- READ_FAILED: M1 re-reads. No write option available.
- ERROR: Any key exits.

**Bundle data passed to WarningWriteActivity:** `{'infos': dict}` containing tag type, UID, read data, keys.

**Source:** `src/lib/activity_read.py` lines 153-228.

---

## 3. WarningM1Activity — Missing Keys Options

### 3.1 Activity Identity

- **ACT_NAME**: `warning_m1`
- **Binary methods** (from STR table):
  - `__init__` (line 357, @0x00034a28)
  - `onCreate` (line 490, @0x00063798)
  - `onWarningPageUpdate` (line 391, @0x000ca4c0)
  - `updateBtnText` (line 641, @0x000cdef4)
  - `gotoSniff` (line 492, @0x000cbc04)
  - `gotoForce` (line 600, @0x000cd564)
  - `onData` (line 554, @0x000ccab4)

### 3.2 Overview

WarningM1Activity displays a multi-page set of recovery options when MIFARE key checking fails. It has **4 pages** (one option per page), navigated with UP/DOWN.

### 3.3 Screen Layout

**Title**: "Missing keys" — `resources.get_str('missing_keys')` = `"Missing keys"` (resources.py line 81)

#### Page 0 (Option 1: Sniff)

```
+---------------------------------------+
|  Missing keys              [battery]  |
+---------------------------------------+
|  Option 1) Go to reader to            |
|  sniff keys                           |
|                                       |
|  Option 2) Enter known keys           |
|  manually                             |
+---------------------------------------+
|  Cancel                 Sniff         |  <- M1="Cancel", M2="Sniff"
+---------------------------------------+
```

Content: `itemmsg['missing_keys_msg1']` = `"Option 1) Go to reader to sniff keys\n\nOption 2) Enter known keys manually"` (resources.py line 204)

#### Page 1 (Option 2: Enter Keys)

Same content as page 0 but M2 action changes.

M2 label: "Enter" — `resources.get_str('enter')` (resources.py line 46)

#### Page 2 (Option 3: Force Read)

```
+---------------------------------------+
|  Missing keys              [battery]  |
+---------------------------------------+
|  Option 3) Force read  to get         |
|  partial data                         |
|                                       |
|  Option 4) Go into PC Mode to         |
|  perform hardnest                     |
+---------------------------------------+
|  Cancel                 Force         |  <- M1="Cancel", M2="Force"
+---------------------------------------+
```

Content: `itemmsg['missing_keys_msg2']` = `"Option 3) Force read  to get partial data\n\nOption 4) Go into PC Mode to perform hardnest"` (resources.py line 205)

#### Page 3 (Option 4: PC Mode)

Same content as page 2 but M2 action changes.

M2 label: "PC-M" — `resources.get_str('pc-m')` (resources.py line 47)

### 3.4 Page-Specific M2 Labels and Actions

Source: Binary `updateBtnText` (STR table line 641) + `onWarningPageUpdate` (line 14975, @0x0003b868).

| Page | M2 Label | M2 Action                     | resources key |
|------|----------|-------------------------------|---------------|
| 0    | Sniff    | Launch SniffForMfReadActivity | `'sniff'`     |
| 1    | Enter    | Launch KeyEnterM1Activity     | `'enter'`     |
| 2    | Force    | Force read (partial data)     | `'force'`     |
| 3    | PC-M     | Enter PC Mode for hardnested  | `'pc-m'`      |

### 3.5 Key Bindings — WarningM1Activity

| Key   | Action                                        |
|-------|-----------------------------------------------|
| UP    | Previous page (min page 0)                    |
| DOWN  | Next page (max page 3)                        |
| M1    | finish() — cancel, return to ReadActivity     |
| M2    | Execute page-specific action (see table above)|
| OK    | Same as M2                                    |
| PWR   | finish() — cancel/back                        |

### 3.6 __init__ — Instance Variables

Source: decompiled `__init__` at line 8800 (@0x00034a28).

The `__init__` method takes `(self, infos)` and sets 5 attributes on `self`:
1. `self.page` = 0 (current page index)
2. `self.page_count` = N/A (set via reference)
3. `self.warning_page_update` = callback ref
4. `self.btn_text_update` = callback ref
5. `self.current_page_text` = initial page text

Evidence: In the decompilation (lines 8974-9019), there are 5 sequential `PyObject_SetAttr` calls on `piVar10` (self), each setting a different attribute. The last one (line 9018-9019) sets an attribute to a constant value (likely page = 0).

### 3.7 onWarningPageUpdate — Page Content Rendering

Source: decompiled `onWarningPageUpdate` at line 14975 (@0x0003b868).

This function takes 3 parameters: `(self, page_content, m2_label)`.
1. Calls `self.btlv.setText(page_content, m2_label)` — updates the BigTextListView content
2. Calls `self.btlv.show()` — refreshes the display

Evidence: The decompilation (line 15151-15164) shows a PyTuple_New(2) call packing two arguments before passing them to a method call, matching the `setText(content, label)` signature.

---

## 4. KeyEnterM1Activity — Manual Hex Key Entry

### 4.1 Activity Identity

- **ACT_NAME**: `key_enter`
- **Binary methods** (from STR table):
  - `__init__` (line 528, @0x000cc410)
  - `onCreate` (line 488, @0x000cbb24)
  - `create_key_index` (line 487, @0x000cbae4)
  - `onKeyEvent` (line 593, @0x000cd3c8)
  - `run_save_keys_and_finish` (line 619, @0x000cd9d4)

### 4.2 Screen Layout

**Title**: "Key Enter" — `resources.get_str('key_enter')` = `"Key Enter"` (resources.py line 71)

```
+---------------------------------------+
|  Key Enter                 [battery]  |
+---------------------------------------+
|                                       |
|  Key:                                 |  <- tipsmsg 'enter_55xx_key_tips' (but used for M1 too)
|  [F][F][F][F][F][F][F][F][F][F][F][F] |  <- 12-char hex input, cursor on active char
|                                       |
|                                       |
+---------------------------------------+
|  Cancel                  Enter        |  <- M1="Cancel", M2="Enter"
+---------------------------------------+
```

Default key value: `FFFFFFFFFFFF` (12 hex chars)
Key length: 12 characters (6 bytes, standard MIFARE key)

### 4.3 Key Bindings — KeyEnterM1Activity

| Key   | Action                                       |
|-------|----------------------------------------------|
| UP    | Roll current hex digit up (0->1->...->F->0)  |
| DOWN  | Roll current hex digit down (F->E->...->0->F)|
| LEFT  | Move cursor to previous character             |
| RIGHT | Move cursor to next character                 |
| M1    | finish() — cancel, return without saving      |
| M2    | Confirm: save key and finish with result      |
| OK    | Same as M2                                    |
| PWR   | finish() — cancel/back                        |

### 4.4 onCreate — Setup

Source: decompiled `onCreate` at line 49745 (@0x000629a0).

Flow:
1. `setTitle("Key Enter")`
2. `setLeftButton("Cancel")`, `setRightButton("Enter")`
3. Create InputMethods widget with hex format, length=12
4. Set placeholder to default key (FFFFFFFFFFFF or from bundle)
5. Show input widget

The binary `onCreate` is a long function (~800 lines decompiled, lines 49745-50531) that builds the hex input UI, sets up the key index mapping, and initializes the cursor position.

### 4.5 create_key_index

Source: decompiled at line 49458 (@0x000624bc).

This method creates a mapping from cursor positions to key byte indices, used for hex digit grouping and display. It is called during `onCreate`.

### 4.6 run_save_keys_and_finish

Source: STR table line 619 (@0x000cd9d4).

When M2/OK is pressed:
1. Read the current 12-char hex value from InputMethods
2. Package result: `{'action': 'enter_key', 'key': hex_value}`
3. Call `finish()` — return result to calling WarningM1Activity

---

## 5. ReadActivity — Detailed State Transitions

### 5.1 onCreate

Source: decompiled at line 51130 (@0x00064214).

Flow:
1. Super `onCreate(bundle)`
2. Set title: `setTitle("Read Tag")` — resources key `read_tag`
3. Extract `tag_type` and `tag_name` from bundle
4. Create ProgressBar and Toast widgets
5. Call `startRead()` to begin scan automatically

Evidence: The decompilation (lines 51326, 51457, 51537, 51649) shows a sequence of:
- `CallOneArg(piVar1, piVar8)` — passing scan params to startRead
- `SetAttr(piVar4, ...)` — storing result handle
- `CallNoArg(...)` calls setting up widgets

### 5.2 startRead

Source: STR table line 567 (@0x000ccdfc).

Flow:
1. Show ProgressBar with "Scanning..." message
2. Start PM3 scan command via scan.so (asynchronous)
3. Register `onData` callback for results

### 5.3 onData — Result Handler

Source: STR table line 566 (@0x000ccd94).

The `onData` method receives callbacks from scan.so and read.so with status updates. It processes:

- **Scan progress**: Update progress bar percentage
- **Tag found**: Display tag info (MIFARE, UID, SAK, ATQA)
- **Key check progress**: Update "ChkDIC...N/Nkeys" message
- **Read progress**: Update "Reading...N/NKeys" message
- **Cracking progress**: Show timer and attack name (Nested, Darkside, STnested)
- **Read complete**: Show success/fail toast
- **Missing keys**: Launch WarningM1Activity

### 5.4 onKeyEvent

Source: STR table line 573 (@0x000ccf20).

State-dependent key handling:

| State          | M1          | M2          | OK          | PWR       |
|----------------|-------------|-------------|-------------|-----------|
| SCANNING       | (disabled)  | (disabled)  | (disabled)  | finish()  |
| READING        | (disabled)  | (disabled)  | (disabled)  | finish()  |
| READ_SUCCESS   | Reread      | Write       | Write       | finish()  |
| READ_PARTIAL   | Reread      | Write       | Write       | finish()  |
| READ_FAILED    | Reread      | (disabled)  | (disabled)  | finish()  |
| NO_TAG_FOUND   | Rescan      | (disabled)  | (disabled)  | finish()  |

### 5.5 showReadToast / hideReadToast

Source: STR table lines 533-534.

`showReadToast()` overlays a Toast widget on the tag info content area. The toast has an icon (checkmark for success, X for failure) and multi-line text.

Toast messages (from resources.py):
- Success: `"Read\nSuccessful!\nFile saved"` (toastmsg 'read_ok_1', line 105)
- Partial: `"Read\nSuccessful!\nPartial data\nsaved"` (toastmsg 'read_ok_2', line 104)
- Failed: `"Read Failed!"` (toastmsg 'read_failed', line 106)

`hideReadToast()` removes the toast overlay, restoring the full tag info display.

### 5.6 Button Labels After Read Completion

**After success/partial success**:
- M1: "Reread" — `resources.get_str('reread')` = `"Reread"` (resources.py line 38)
- M2: "Write" — `resources.get_str('write')` = `"Write"` (resources.py line 42)

**After failure**:
- M1: "Reread" — same as above
- M2: (may be empty or absent)

**Evidence**: `read_mf1k_4b/0200.png` shows "Reread" on left and "Write" on right after successful read. `Step - 2.png` shows same button labels.

### 5.7 onResume / onDestroy

Source: STR table lines 498, 496.

- `onResume`: Called when activity comes back to foreground. Re-registers callbacks.
- `onDestroy`: Called when activity is being removed from stack. Cancels pending PM3 operations via `stopRead()`.

### 5.8 stopRead / canidle

Source: STR table lines 394, 412.

- `stopRead()`: Cancels any in-progress PM3 command. Called from `onDestroy` and when user presses PWR during active operations.
- `canidle()`: Returns True when no PM3 operation is pending, allowing the display to enter power-saving mode.

---

## 6. Progress Bar Message Formats

All progress bar messages come from `resources.py` `StringEN.procbarmsg`:

| Key                  | Display Text                     | Used In              |
|----------------------|----------------------------------|----------------------|
| `scanning`           | `Scanning...`                    | ReadActivity scan    |
| `reading`            | `Reading...`                     | ReadActivity read    |
| `reading_with_keys`  | `Reading...{}/{}Keys`            | MIFARE read progress |
| `t55xx_checking`     | `T55xx keys checking...`         | T55xx key check      |
| `t55xx_reading`      | `T55xx Reading...`               | T55xx read           |
| `ChkDIC`             | `ChkDIC`                         | Dictionary check     |
| `Darkside`           | `Darkside`                       | Darkside attack      |
| `Nested`             | `Nested`                         | Nested attack        |
| `STnested`           | `STnested`                       | Static nested attack |
| `time<1h`            | `      %02d'%02d''`             | Time < 1 hour        |
| `10h>time>=1h`       | `    %dh %02d'%02d''`           | 1h <= time < 10h     |
| `time>=10h`          | `    %02dh %02d'%02d''`         | Time >= 10 hours     |

---

## 7. Toast Messages

| Key                  | Display Text                           | Icon      |
|----------------------|----------------------------------------|-----------|
| `read_ok_1`          | `Read\nSuccessful!\nFile saved`        | checkmark |
| `read_ok_2`          | `Read\nSuccessful!\nPartial data\nsaved` | checkmark |
| `read_failed`        | `Read Failed!`                         | X         |
| `no_tag_found`       | `No tag found`                         | X         |
| `no_tag_found2`      | `No tag found \nOr\n Wrong type found!`| X         |
| `tag_found`          | `Tag Found`                            | checkmark |
| `tag_multi`          | `Multiple tags detected!`              | X         |
| `keys_check_failed`  | `Time out`                             | X         |

---

## 8. Activity Flow Diagram

```
Main Page
    |
    | OK (on "Read Tag")
    v
ReadListActivity
    |
    | M2/OK (select type)
    v
ReadActivity
    |
    +-- Scan phase
    |     |
    |     +-- Tag found -> Reading phase
    |     +-- No tag found -> Toast, M1=Rescan
    |     +-- Wrong type -> Toast, M1=Rescan
    |
    +-- Reading phase
    |     |
    |     +-- All keys found -> Read data -> Success toast
    |     +-- Some keys missing -> Read partial -> Partial success
    |     +-- No keys -> WarningM1Activity
    |     +-- Key check timeout -> "Time out" toast
    |
    +-- Read Success
    |     |
    |     +-- M1 = Reread (restart ReadActivity)
    |     +-- M2/OK = Launch WarningWriteActivity -> WriteActivity
    |     +-- PWR = Exit to ReadListActivity
    |
    +-- WarningM1Activity (missing keys)
          |
          +-- Page 0: M2 = SniffForMfReadActivity (sniff keys)
          +-- Page 1: M2 = KeyEnterM1Activity (manual key entry)
          +-- Page 2: M2 = Force read (partial data)
          +-- Page 3: M2 = PC Mode (hardnested via PM3 client)
          |
          +-- M1/PWR = Cancel, return to ReadActivity
```

---

## 9. Tag Info Display Format

When a tag is detected, the content area shows tag details. Format varies by tag family.

### HF Tags (MIFARE, Ultralight, NTAG, iClass, etc.)

```
MIFARE
M1 S50 1K (4B)
Frequency: 13.56MHZ
UID: 2CADC272
SAK: 08  ATQA: 0004
```

Evidence: `read_mf1k_4b/0090.png`, `read_mf1k_nested/0025.png`

### LF Tags (EM410x, HID Prox, etc.)

```
{TAG FAMILY}
{Tag type name}
Frequency: 125KHZ
ID: {hex ID}
```

### Fields

| Field     | Source        | Notes                              |
|-----------|--------------|------------------------------------|
| Family    | scan.so      | "MIFARE", "ULTRALIGHT", etc.       |
| Type      | scan.so      | "M1 S50 1K (4B)", etc.             |
| Frequency | scan.so      | "13.56MHZ" or "125KHZ"            |
| UID/ID    | scan.so      | Hex string, length varies by type  |
| SAK       | scan.so      | HF only, 2-digit hex              |
| ATQA      | scan.so      | HF only, 4-digit hex              |

---

## 10. Cross-References

| From                | To                        | Trigger           | Bundle                           |
|---------------------|---------------------------|--------------------|----------------------------------|
| MainPage            | ReadListActivity          | OK on "Read Tag"   | None                             |
| ReadListActivity    | ReadActivity              | M2/OK on selection  | `{tag_type, tag_name}`           |
| ReadActivity        | WarningM1Activity         | Missing keys result | `{infos: read_data}`             |
| ReadActivity        | WarningWriteActivity      | M2/OK after success | `{infos: read_data}`             |
| WarningM1Activity   | SniffForMfReadActivity    | Page 0 M2          | `{infos: read_data}`             |
| WarningM1Activity   | KeyEnterM1Activity        | Page 1 M2          | `{infos: read_data}`             |
| WarningWriteActivity| WriteActivity             | M2/OK confirm       | `{infos: tag_data}`              |

---

## Corrections Applied

1. **NOT_FOUND state buttons**: Fixed from M1="Rescan" only to M1="Rescan", M2="Rescan" (both buttons show "Rescan"). Citation: `read_tag_no_tag_or_wrong_type_2.png` clearly shows both "Rescan" labels.
