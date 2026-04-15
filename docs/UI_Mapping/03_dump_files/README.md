# CardWalletActivity (Dump Files) UI Mapping

Binary source: `activity_main.so` class `CardWalletActivity` (16 methods)
Source: `docs/v1090_strings/_all_ui_text.txt:106-124`

Note: CardWalletActivity is a v1.0.90+ feature. The decompiled function bodies are NOT
in `activity_main_ghidra_raw.txt` (which covers v1.0.80 binary). The method list, string
references, and PATH_DUMP_* constants are confirmed via `_all_ui_text.txt:106-124`,
`_all_ui_text.txt:652-669`, and `appfiles_ghidra_raw.txt` STR table (lines 384-504).

## Methods (from _all_ui_text.txt)

| Method | Purpose |
|--------|---------|
| `__init__` | Constructor |
| `getManifest` | Returns activity manifest dict |
| `onKeyEvent` | Key dispatch for all states |
| `onMultiPIUpdate` | Handles page indicator update callbacks |
| `showDumps` | Populates file list for selected type |
| `showDumps.get_ctime` | Local: gets file creation time for sorting |
| `showDumps.get_file` | Local: extracts file from path |
| `showDetail` | Shows tag info detail view for selected file |
| `parseInfoByM1FileName` | Parses Mifare Classic dump filename to extract tag info |
| `parseInfoByIDFileName` | Parses LF ID card dump filename to extract tag info |
| `parseInfoByT55xxInfoFileName` | Parses T5577 info filename to extract tag info |
| `parseInfoByUIDInfoFileName` | Parses UID-based (MFU/14443A) filename to extract tag info |
| `parseInfoByLegicInfoFileName` | Parses Legic filename to extract tag info |
| `setBtn2ListMode` | Sets softkeys to list mode (Details/Delete) |
| `setBtn2DelMode` | Sets softkeys to delete confirmation mode |
| `delDump` | Deletes selected dump file |
| `getKeyInfo` | Retrieves key data associated with a dump |
| `setTipsTxt` | Sets tips/message text on screen |

---

## 1. Title Bar

Title string: `StringEN.title['card_wallet']` = **"Dump Files"**
Source: `src/lib/resources.py:95`

The title bar shows **"Dump Files"** followed by a page indicator (e.g., "1/1", "1/5") and battery icon.

Page indicator format: `"{page}/{total}"` appended to title.

Screenshots:
- `v1090_captures/090-Dump-Types.png` -- title "Dump Files 1/1" (2 types fit on 1 page)
- `v1090_captures/090-Dump-Types-Files.png` -- title "Dump Files 1/5" (paginated file list)
- `reference_screenshots/sub_01_dump_files.png` -- title "Dump Files 1/1" (4 types visible)

---

## 2. State Machine Overview

CardWalletActivity has 3 main view states and 2 sub-states:

```
[Type List] --> [File List] --> [Tag Info / Detail]
                    |                   |
                    v                   v
              [Delete Confirm]   [Data Ready / Write]
```

---

## 3. State 1: Type List (Initial View)

The initial view shows a numbered list of dump file categories. Only categories that contain at least one dump file are shown.

### Display Layout

Title: **"Dump Files {page}/{total}"**
List items: Numbered entries, one per line, 4 items per page.

Items per page: **4** (standard ListView page size).

### Known Type Categories

From `appfiles_ghidra_raw.txt` PATH_DUMP_* constants (lines 384-455) and appfiles_strings.txt:

| # | Display Name | appfiles constant | Parse Method |
|---|-------------|-------------------|-------------|
| 1 | Mifare Classic | PATH_DUMP_M1 (line 454) | parseInfoByM1FileName |
| 2 | T5577 ID | PATH_DUMP_T55XX (line 412) | parseInfoByT55xxInfoFileName |
| 3 | iClass | PATH_DUMP_ICLASS (line 401) | parseInfoByIDFileName (re-used) |
| 4 | Felica | PATH_DUMP_FELICA (line 402) | parseInfoByUIDInfoFileName |
| 5 | Legic Mini 256 | PATH_DUMP_LEGIC (line 414) | parseInfoByLegicInfoFileName |
| 6 | ISO 14443A | PATH_DUMP_HF14A (line 416) | parseInfoByUIDInfoFileName |
| 7 | ICODE | PATH_DUMP_ICODE (line 415) | parseInfoByUIDInfoFileName |
| 8 | EM410x ID | PATH_DUMP_EM410x (line 403) | parseInfoByIDFileName |
| 9 | EM4X05 ID | PATH_DUMP_EM4X05 (line 403) | parseInfoByIDFileName |
| 10 | HID Prox ID | PATH_DUMP_HID (line 439) | parseInfoByIDFileName |
| 11 | Indala ID | PATH_DUMP_INDALA (line 400) | parseInfoByIDFileName |
| 12 | AWID ID | PATH_DUMP_AWID (line 425) | parseInfoByIDFileName |
| 13 | Keri ID | PATH_DUMP_KERI (line 424) | parseInfoByIDFileName |
| 14 | Viking ID | PATH_DUMP_VIKING (line 397) | parseInfoByIDFileName |
| 15 | Pyramid ID | PATH_DUMP_PYRAMID (line 390) | parseInfoByIDFileName |
| 16 | Presco ID | PATH_DUMP_PRESCO (line 398) | parseInfoByIDFileName |
| 17 | Paradox ID | PATH_DUMP_PARADOX (line 391) | parseInfoByIDFileName |
| 18 | Noralsy ID | PATH_DUMP_NORALSY (line 392) | parseInfoByIDFileName |
| 19 | Gproxii ID | PATH_DUMP_GPROXII (line 393) | parseInfoByIDFileName |
| 20 | Ioprox ID | PATH_DUMP_IOPROX (line 399) | parseInfoByIDFileName |
| 21 | PAC ID | PATH_DUMP_PAC (line 437) | parseInfoByIDFileName |
| 22 | Animal ID(FDX) | PATH_DUMP_FDX (line 440) | parseInfoByIDFileName |
| 23 | Nedap ID | PATH_DUMP_NEDAP (line 413) | parseInfoByIDFileName |
| 24 | Securakey ID | PATH_DUMP_SECURAKEY (line 384) | parseInfoByIDFileName |
| 25 | Jablotron ID | PATH_DUMP_JABLOTRON (line 385) | parseInfoByIDFileName |
| 26 | Gallagher ID | PATH_DUMP_GALLAGHER (line 386) | parseInfoByIDFileName |
| 27 | Visa2000 ID | PATH_DUMP_VISA2000 (line 388) | parseInfoByIDFileName |
| 28 | Nexwatch ID | PATH_DUMP_NEXWATCH (line 389) | parseInfoByIDFileName |

String sources from `appfiles_strings.txt`:
- "Mifare Classic" (line 2422)
- "T5577 ID" (line 2560)
- "iClass" (line 2603)
- "Felica" (line 2616)
- "Legic Mini 256" (line 2423)
- "ICODE" (line 2645)

### Screenshot Evidence -- Type List

**v1090_captures/090-Dump-Types.png**: Shows "Dump Files 1/1" with 2 entries:
```
1. Mifare Classic
2. T5577 ID
```
This device only had dump files in these 2 categories.

**reference_screenshots/sub_01_dump_files.png**: Shows "Dump Files 1/1" with 4 entries:
```
1. Mifare Classic
2. iClass
3. Legic Mini 256
4. Felica
```
This device had dump files in 4 categories.

**docs/Real_Hardware_Intel/Screenshots/dump_files_1_1.png**: Shows "Dump Files 1/1" with 4 entries:
```
1. Mifare Classic
2. Animal ID(FDX)
3. T5577 ID
4. AWID ID
```
This device had dump files in 4 categories. Note: FDX type displays as "Animal ID(FDX)" not "FDX ID".

### Key Handling -- Type List

| Key | Action |
|-----|--------|
| UP | Move selection up |
| DOWN | Move selection down |
| OK | Enter selected type -> show file list (State 2) |
| PWR | Exit to main menu |
| M1 | No action |
| M2 | No action |

Pagination: When more than 4 types have files, page indicator updates. UP/DOWN scrolls through items and pages automatically.

---

## 4. State 2: File List (Per-Type View)

After selecting a type category, `showDumps` is called to populate the file list.

### Display Layout

Title: **"Dump Files {page}/{total}"** (page indicator updates for file pagination)
List items: Filenames sorted by creation time (newest first, via `get_ctime` local function)
Items per page: **4**
Softkeys: **"Details" / "Delete"**
- M1: `StringEN.button['details']` = "Details" (resources.py:63)
- M2: `StringEN.button['delete']` = "Delete" (resources.py:62)

### Screenshot Evidence -- File List

**v1090_captures/090-Dump-Types-Files.png**: Shows "Dump Files 1/5" with file entries:
```
Mini-4B-8800E177(1)
1K-4B-DAEF8416(1)
1K-4B-DAEF8416(1)
1K-4B-DAEF8416(1)
```
Softkeys: "Details" / "Delete"

**docs/Real_Hardware_Intel/Screenshots/dump_files_1_10_1.png**: Shows "Dump Files 1/10" with 4 file entries:
```
1K-4B-DAEFB416(1)
1K-4B-DAEFB416(2)
1K-4B-DAEFB416(3)
1K-4B-DAEFB416(4)
```
Softkeys: "Details" / "Delete". Confirms 4 items per page with 10 pages (40 files total).

**docs/Real_Hardware_Intel/Screenshots/dump_files_1_10_4.png**: Shows "Dump Files 1/10" scrolled down:
```
1K-4B-DAEFB416(2)
1K-4B-DAEFB416(3)
1K-4B-DAEFB416(4)
1K-4B-DAEFB416(5)
```
Confirms 4-item page window scrolls item-by-item before page flips.

The filename format for Mifare Classic files encodes: `{type}-{uid_len}-{uid}({index})`
- `Mini-4B-8800E177(1)` -- Mifare Mini, 4-byte UID 8800E177, index 1
- `1K-4B-DAEF8416(1)` -- Mifare 1K, 4-byte UID DAEF8416, index 1

### File Naming Conventions (from parseInfo methods)

**parseInfoByM1FileName**: Mifare Classic
- Format: `{size}-{uid_bytes}B-{UID}({index})`
- Example: `1K-4B-DEADBEEF(1)`, `Mini-4B-8800E177(1)`, `4K-7B-04AABBCCDDEE(2)`

**parseInfoByIDFileName**: LF ID cards (EM410x, HID, Indala, etc.)
- Format: `{type}-{ID}({index})`
- Example: `EM410x-1234567890(1)`

**parseInfoByT55xxInfoFileName**: T5577 cards
- Format: `T5577-{ID}({index})`

**parseInfoByUIDInfoFileName**: UID-based HF tags (MFU, 14443A, ICODE, Felica)
- Format: `{UID}({index})`

**parseInfoByLegicInfoFileName**: Legic tags
- Format: `Legic-{UID}({index})`

### Key Handling -- File List

| Key | Action |
|-----|--------|
| UP | Move selection up (with pagination) |
| DOWN | Move selection down (with pagination) |
| OK | Show detail view for selected file (State 3) |
| PWR | Go back to type list (State 1) |
| M1 | "Details" -- show detail view (same as OK) |
| M2 | "Delete" -- enter delete confirmation (State 2b) |

### Empty Category

If a type category has no dump files (or only unsupported file formats):
- Toast: **"No dump info. \nOnly support:\n.bin .eml .txt"** (`StringEN.tipsmsg['no_tag_history']`, resources.py:176)
- Returns to type list

---

## 5. State 2b: Delete Confirmation

When M2 (Delete) is pressed on a file in the list:

### Display Layout

Softkeys change via `setBtn2DelMode`:
- Toast/prompt: **"Delete?"** overlay centered on dimmed file list (`StringEN.toastmsg['delete_confirm']`, resources.py:144)
- Confirmation softkeys set by `setBtn2DelMode`:
  - M1: **"No"** (returns to list mode via `setBtn2ListMode`)
  - M2: **"Yes"** (calls `delDump`, removes file, refreshes list)

Screenshot evidence:
- `docs/Real_Hardware_Intel/Screenshots/dump_files_delete_confirm_1.png` -- "Delete?" overlay appears on dimmed file list, softkeys still show "Details" / "Delete" (transition frame)
- `docs/Real_Hardware_Intel/Screenshots/dump_files_delete_confirm_2.png` -- "Delete?" overlay with softkeys **"No" / "Yes"** (confirmation state)

After deletion or cancel, `setBtn2ListMode` restores softkeys to "Details" / "Delete".

If the last file in a category is deleted, returns to type list (State 1) and that category is no longer shown.

---

## 6. State 3: Tag Info / Detail View

When OK or M1 (Details) is pressed on a file, `showDetail` is called.

### Display Layout

Title: **"Tag Info"** (`StringEN.title['tag_info']`, resources.py:96)
Body: Tag information panel showing parsed file data

Content depends on file type (parsed by the appropriate parseInfo method):

**Mifare Classic (parseInfoByM1FileName)**:
```
MIFARE
M1 Mini 0.3K     (or: M1 S50 1K (4B), M1 S70 4K (4B), etc.)
Frequency: 13.56MHZ
UID: 8800E177
SAK: 08  ATQA: 0004
```

**LF ID cards (parseInfoByIDFileName)**:
```
{Tag Type Name}
ID: {card ID}
```

**T5577 (parseInfoByT55xxInfoFileName)**:
```
T5577
ID: {raw data}
Key: {key if known}
```

Softkeys: **"Simulate" / "Write"**
- M1: `StringEN.button['simulate']` = "Simulate" (resources.py:43)
- M2: `StringEN.button['write']` = "Write" (resources.py:42)

### Screenshot Evidence -- Tag Info

**v1090_captures/090-Dump-Types-Files-Info.png**: Shows "Tag Info" title with:
```
MIFARE
M1 Mini 0.3K
Frequency: 13.56MHZ
UID: 8800E177
SAK: 08  ATQA: 0004
```
Softkeys: "Simulate" / "Write"

### Key Handling -- Tag Info

| Key | Action |
|-----|--------|
| M1 | "Simulate" -- launch SimulationActivity with this dump file |
| M2 | "Write" -- transition to Data Ready state (State 4) |
| PWR | Go back to file list (State 2) |
| OK | No action |
| UP/DOWN | No action (single-screen view) |

---

## 7. State 4: Data Ready (Write Prompt)

When M2 (Write) is pressed on the Tag Info view:

### Display Layout

Title: **"Data ready!"** (`StringEN.title['data_ready']`, resources.py:84)
Body:
```
Data ready for copy!
Please place new tag for copy.

TYPE:
M1-4b
```

- Body text: `StringEN.tipsmsg['place_empty_tag']` = "Data ready for copy!\nPlease place new tag for copy." (resources.py:152)
- Type label: `StringEN.tipsmsg['type_tips']` = "TYPE:" (resources.py:153)
- Type value: e.g., "M1-4b" in large font (derived from parsed filename)

Softkeys: **"Watch" / "Write"**
- M1: `StringEN.title['write_wearable']` = "Watch" (resources.py:94) -- launches wearable write flow
- M2: `StringEN.button['write']` = "Write" (resources.py:42) -- starts standard write

### Screenshot Evidence -- Data Ready

**v1090_captures/090-Dump-Types-Files-Info-Write.png**: Shows "Data ready!" title with:
```
Data ready for copy!
Please place new tag
for copy.
TYPE:
M1-4b
```
Softkeys: "Watch" / "Write"

### Key Handling -- Data Ready

| Key | Action |
|-----|--------|
| M1 | "Watch" -- launch WarningWriteActivity/WriteWearableActivity |
| M2 | "Write" -- launch WriteActivity with dump data |
| PWR | Go back to Tag Info (State 3) |
| OK | No action |

---

## 8. State 5: Write Flow (Sub-Activity)

After pressing M2 (Write) on Data Ready, the write flow launches as a sub-activity (WriteActivity). This follows the same pattern as AutoCopy's write states:

1. **Writing**: Progress bar with "Writing..." (`StringEN.procbarmsg['writing']`, resources.py:181)
2. **Verifying**: Progress bar with "Verifying..." (`StringEN.procbarmsg['verifying']`, resources.py:182)
3. **Write Success**: Toast "Write successful!" with softkeys "Verify" / "Rewrite"
4. **Write Failure**: Toast "Write failed!" with softkeys "Verify" / "Rewrite"

See `02_auto_copy/README.md` States 6-8 for full write sub-activity documentation.

---

## 9. Pagination via onMultiPIUpdate

`onMultiPIUpdate` handles the MultiPageIndicator widget callbacks. When the user scrolls past page boundaries (beyond item 4 on a page), the page indicator in the title updates.

Page indicator format: `"{current_page}/{total_pages}"`
Appended to the title: `"Dump Files {current_page}/{total_pages}"`

Evidence:
- `v1090_captures/090-Dump-Types.png` -- "Dump Files 1/1" (all types fit on 1 page)
- `v1090_captures/090-Dump-Types-Files.png` -- "Dump Files 1/5" (20 files across 5 pages)
- `reference_screenshots/sub_01_dump_files.png` -- "Dump Files 1/1"

The page indicator is rendered as part of the title string in the title bar, not as a separate widget.

---

## 10. File System Layout

From `appfiles_ghidra_raw.txt` STR constants (lines 384-504):

```
PATH_DUMP (root)
  +-- PATH_DUMP_M1        -- Mifare Classic .bin/.eml dumps
  +-- PATH_DUMP_T55XX     -- T5577 ID dumps
  +-- PATH_DUMP_ICLASS    -- iClass dumps
  +-- PATH_DUMP_FELICA    -- Felica dumps
  +-- PATH_DUMP_LEGIC     -- Legic Mini 256 dumps
  +-- PATH_DUMP_ICODE     -- 15693/ICODE/SLIX dumps
  +-- PATH_DUMP_HF14A     -- ISO 14443A UID dumps
  +-- PATH_DUMP_MFU       -- Mifare Ultralight dumps
  +-- PATH_DUMP_EM410x    -- EM410x ID dumps
  +-- PATH_DUMP_EM4X05    -- EM4X05 ID dumps
  +-- PATH_DUMP_HID       -- HID Prox ID dumps
  +-- PATH_DUMP_INDALA    -- Indala ID dumps
  +-- PATH_DUMP_AWID      -- AWID ID dumps
  +-- PATH_DUMP_KERI      -- Keri ID dumps
  +-- PATH_DUMP_VIKING    -- Viking ID dumps
  +-- PATH_DUMP_PYRAMID   -- Pyramid ID dumps
  +-- PATH_DUMP_PRESCO    -- Presco ID dumps
  +-- PATH_DUMP_PARADOX   -- Paradox ID dumps
  +-- PATH_DUMP_NORALSY   -- Noralsy ID dumps
  +-- PATH_DUMP_GPROXII   -- Gproxii ID dumps
  +-- PATH_DUMP_IOPROX    -- Ioprox ID dumps
  +-- PATH_DUMP_PAC       -- PAC ID dumps
  +-- PATH_DUMP_FDX       -- FDX-B ID dumps
  +-- PATH_DUMP_NEDAP     -- Nedap ID dumps
  +-- PATH_DUMP_SECURAKEY -- Securakey ID dumps
  +-- PATH_DUMP_JABLOTRON -- Jablotron ID dumps
  +-- PATH_DUMP_GALLAGHER -- Gallagher ID dumps
  +-- PATH_DUMP_VISA2000  -- Visa2000 ID dumps
  +-- PATH_DUMP_NEXWATCH  -- Nexwatch ID dumps
  +-- PATH_DUMP_ID        -- Generic ID dumps

PATH_KEYS (separate)
  +-- PATH_KEYS_M1        -- Mifare Classic key files
  +-- PATH_KEYS_T5577     -- T5577 key files (from appfiles_strings.txt:2395)

PATH_TRACE               -- Sniff trace files

PATH_KEYS                -- Key storage root
```

Supported file extensions: `.bin`, `.eml`, `.txt`
Source: `StringEN.tipsmsg['no_tag_history']` = "No dump info. \nOnly support:\n.bin .eml .txt" (resources.py:176)

---

## 11. Flow Diagram

```
[Main Menu: "Dump Files"]
        |
        v
[State 1: Type List]
  "Dump Files 1/1"
  1. Mifare Classic    <-- only types with files shown
  2. T5577 ID
  ...
  UP/DOWN: navigate
  OK: select type
  PWR: exit
        |
        v (OK)
[State 2: File List]
  "Dump Files 1/5"
  Mini-4B-8800E177(1)    <-- sorted by creation time
  1K-4B-DAEF8416(1)
  ...
  M1:Details  M2:Delete
  UP/DOWN: navigate (paginated, 4 per page)
  OK/M1: show detail
  PWR: back to type list
        |
   +----+----+
   |         |
   v (M1)    v (M2)
[State 3:   [State 2b:
 Tag Info]   Delete?]
  "Tag Info"    |
  MIFARE        M1:"No" -> back to file list
  M1 Mini...    M2:"Yes" -> delDump -> refresh list
  UID: ...
  M1:Simulate  M2:Write
  PWR: back to file list
        |
   +----+----+
   |         |
   v (M1)    v (M2)
[Launch     [State 4:
 Simulation  Data Ready]
 Activity]   "Data ready!"
             "Place new tag..."
             TYPE: M1-4b
             M1:Watch  M2:Write
             PWR: back to tag info
                    |
                    v (M2)
             [State 5: WriteActivity]
              Writing... -> Verifying...
              -> Write Success/Failure
```

---

## 12. getKeyInfo

`getKeyInfo` retrieves associated key data for a dump file. For Mifare Classic dumps, this looks up the corresponding key file in PATH_KEYS_M1. For T5577, it looks in PATH_KEYS_T5577.

Key files are linked to dump files by UID/filename matching. The key info is displayed as part of the Tag Info detail view and is passed to WriteActivity when initiating a write.

---

## 13. Simulate/Write Bundle

When launching SimulationActivity (M1 on Tag Info) or WriteActivity (M2 on Data Ready), CardWalletActivity packages a bundle containing:

- Dump file path
- Parsed tag info (type, UID, frequency, SAK, ATQA as applicable)
- Key file path (if available, via getKeyInfo)

This bundle format is shared with ReadActivity's completion bundle, ensuring write/simulate can work with dumps from either source (fresh reads or saved files).

---

## Corrections Applied

- **2026-03-31 (adversarial audit vs Real_Hardware_Intel screenshots)**: Audited against 7 real hardware screenshots. Corrections:
  1. **Items per page: 5 -> 4**. All file list screenshots (`dump_files_1_10_1.png` through `_4.png`) consistently show 4 items per page, not 5. Corrected in sections 3, 4, 9, and flow diagram.
  2. **FDX display name: "FDX ID" -> "Animal ID(FDX)"**. Screenshot `dump_files_1_1.png` shows "Animal ID(FDX)" as the type list entry for FDX-B tags. Corrected in type categories table.
  3. **Delete confirmation softkey labels: "Cancel"/"Confirm" -> "No"/"Yes"**. Screenshot `dump_files_delete_confirm_2.png` shows softkeys labeled "No" (M1) and "Yes" (M2), not generic "Cancel"/"Confirm". Corrected in section 5 and flow diagram.
  4. **Added real hardware screenshot references** to type list, file list, and delete confirmation sections.
  5. **Corrected "25 files across 5 pages" -> "20 files across 5 pages"** in pagination section to be consistent with 4 items/page.

---

## Key Bindings

### CardWalletActivity.onKeyEvent (activity_main_ghidra_raw.txt)

Two modes: LIST (file browser) and DETAIL (single file info).

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LIST (empty) | no-op | no-op | no-op | no-op | no-op | finish() | no-op | finish() |
| LIST (files) | prev() | next() | no-op | no-op | _showDetail() | finish() | _showDetail() | finish() |
| DETAIL | no-op | no-op | no-op | no-op | _deleteFile() | _showDumps() (back) | _deleteFile() | _showDumps() (back) |

**Bundle data passed to CardWalletActivity:** `{'dump_type': str, 'dump_dir': str}` from the calling activity.

**Source:** `src/lib/activity_main.py` lines 4935-4958.
