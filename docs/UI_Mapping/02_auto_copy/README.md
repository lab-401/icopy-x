# AutoCopyActivity UI Mapping

Binary source: `activity_main.so` class `AutoCopyActivity` (7 methods)
- `__init__` @ 0x000332ac (activity_main_ghidra_raw.txt:7534)
- `getManifest` @ 0x00060760 (activity_main_ghidra_raw.txt:47805)
- `onCreate` @ 0x00060118 (activity_main_ghidra_raw.txt:47456)
- `onKeyEvent` @ 0x0006bc04 (activity_main_ghidra_raw.txt:57877)
- `onScanFinish` @ STR 0x000cc480 (activity_main_ghidra_raw.txt:530)
- `showScanToast` @ STR 0x000cd200 (activity_main_ghidra_raw.txt:585)
- `startScan` @ 0x0003b0e8 (activity_main_ghidra_raw.txt:14556)

Source: `docs/v1090_strings/_all_ui_text.txt:38-45`

---

## 1. Title Bar

Title string: `StringEN.title['auto_copy']` = **"Auto Copy"**
Source: `src/lib/resources.py:68`

Confirmed in screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0249.png` -- title reads "Auto Copy" with battery icon
- `framebuffer_captures/autocopy_mf1k_gen1a/0344.png` -- same "Auto Copy" title
- `docs/reference_screenshots/sub_00_auto_copy.png` -- "Auto Copy" title visible

The title bar displays "Auto Copy" (no page indicator) with battery icon on right.

---

## 2. Activity Manifest (getManifest)

`getManifest` (activity_main_ghidra_raw.txt:47805) builds a dict:
- Sets activity title via `resources.get_str` for `'auto_copy'`
- References `ScanActivity.startScan` for scan pipeline integration
- Manifest dict includes both title and scan entry point

The manifest pattern constructs a PyDict with at minimum a `title` key and a `scan_entry` tuple referencing the scan module. The code at 0x60760 calls `PyDict_New()` then `PyDict_SetItem()` with the title key (line 47850), then obtains module globals for the scan class and its `startScan` method, builds a tuple of (scan_class, scan_method), and sets it as a second dict entry (line 48008).

---

## 3. onCreate (Activity Initialization)

`onCreate` (activity_main_ghidra_raw.txt:47456) performs:

1. Calls super().__init__ via the parent class (line 47582-47584)
2. Calls super().onCreate() (line 47607)
3. Gets module global reference to `ScanActivity` (line 47635-47649)
4. Gets `startScan` attribute from `ScanActivity` (line 47657-47661)
5. Calls `startScan(self)` -- this kicks off the automatic scan immediately on entry (line 47693)

Key behavior: **AutoCopy starts scanning automatically upon activity entry.** There is no user prompt or "Start" button -- the scan begins as soon as onCreate completes.

Confirmed in screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0249.png` -- shows "Scanning..." with progress bar immediately
- `framebuffer_captures/autocopy_mf1k_gen1a/0266.png` -- progress bar advancing

---

## 4. State Machine (Complete Flow)

AutoCopy is a linear pipeline: Scan -> Read -> Write. The flow progresses automatically between stages with minimal user input required.

### State 1: Scanning

Title: **"Auto Copy"**
Display: Progress bar with text **"Scanning..."** (`StringEN.procbarmsg['scanning']`, resources.py:183)

Screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0249.png` -- "Scanning..." with small blue progress bar
- `framebuffer_captures/autocopy_mf1k_gen1a/0266.png` -- larger blue progress bar, still "Scanning..."

The scan runs automatically with no user buttons visible (no softkey labels). The progress bar animates across the bottom of the screen.

### State 2: Scan Result -- Tag Found

When a tag is detected, `onScanFinish` fires and the activity transitions directly to the read phase. The scan result displays the tag information:

Display elements:
- Tag family name (e.g., **"MIFARE"**) in bold
- Tag type: **"M1 S50 1K (4B)"**
- Frequency: **"Frequency: 13.56MHZ"**
- UID: **"UID: DEADBEEF"**
- SAK and ATQA: **"SAK: 08  ATQA: 0004"**

Screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0275.png` -- tag info with "Reading..." at bottom
- `framebuffer_captures/autocopy_mf1k_gen1a/0300.png` -- tag info visible, cracking phase started

### State 2b: Scan Result -- No Tag Found

Title: **"Auto Copy"**
Toast: **"No tag found"** (`StringEN.toastmsg['no_tag_found']`, resources.py:108)
Softkeys: **"Rescan" / "Rescan"** (M1 and M2 both mapped to rescan)

Screenshot:
- `docs/reference_screenshots/sub_00_auto_copy.png` -- shows "No tag found" toast with X icon, both softkeys labeled "Rescan"

The `showScanToast` method (STR @ 0x000cd200) displays the no-tag-found toast. Both softkeys invoke `startScan` to retry.

### State 3: Reading / Key Cracking

Title: **"Auto Copy"** (remains unchanged)
The read process happens automatically after scan completion, no user action needed.

#### Sub-state 3a: Dictionary Check (ChkDIC)
Display: Tag info panel + timer + **"ChkDIC...0/32keys"**
- Timer format: `StringEN.procbarmsg['time<1h']` = `"      %02d'%02d''"` (resources.py:197)
- Progress: ChkDIC...{found}/{total}keys

Screenshot:
- `framebuffer_captures/autocopy_mf1k_gen1a/0300.png` -- shows "01'03''" timer and "ChkDIC...0/32keys"

#### Sub-state 3b: Nested Attack
Display: Tag info panel + timer + **"Nested...{found}/{total}keys"**
- Progress format: `StringEN.procbarmsg['Nested']` = `"Nested"` (resources.py:193)

Screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0344.png` -- "Nested...30/32keys" with timer "00'18''"
- `framebuffer_captures/autocopy_mf1k_gen1a/0360.png` -- "Nested...30/32keys" timer "00'16''"
- `framebuffer_captures/autocopy_mf1k_gen1a/0366.png` -- "Nested...32/32keys" timer "00'12''"

#### Sub-state 3c: Block Reading
Display: Tag info panel + **"Reading...{done}/{total}Keys"**
- Progress: `StringEN.procbarmsg['reading_with_keys']` = `"Reading...{}/{}Keys"` (resources.py:188)

Screenshot:
- `framebuffer_captures/autocopy_mf1k_gen1a/0426.png` -- "Reading...32/32Keys"

### State 4: Read Success (Toast)

Title: **"Auto Copy"** (dimmed background)
Toast overlay:
- Checkmark icon
- **"Read\nSuccessful!\nFile saved"** (`StringEN.toastmsg['read_ok_1']`, resources.py:105)
Softkeys: **"Reread" / "Write"** (M1 = Reread, M2 = Write)
- M1 `StringEN.button['reread']` = "Reread" (resources.py:38)
- M2 `StringEN.button['write']` = "Write" (resources.py:42)

Screenshot:
- `framebuffer_captures/autocopy_mf1k_gen1a/0450.png` -- toast "Read Successful! File saved" with checkmark, softkeys "Reread" / "Write"

If user presses M1 (Reread): re-enters State 3 (startScan again)
If user presses M2 (Write): transitions to State 5

### State 4b: Read Failure

Toast: **"Read Failed!"** (`StringEN.toastmsg['read_failed']`, resources.py:106)
Softkeys: **"Rescan" / "Rescan"** (both retry)

### State 5: Data Ready (Place Card Prompt)

Title: **"Data ready!"** (`StringEN.title['data_ready']`, resources.py:84)
Body text:
- **"Data ready for copy!\nPlease place new tag for copy."** (`StringEN.tipsmsg['place_empty_tag']`, resources.py:152)
- **"TYPE:"** (`StringEN.tipsmsg['type_tips']`, resources.py:153)
- Tag type in large font: e.g., **"M1-4b"**
Softkeys: **"Watch" / "Write"**
- M1: navigates to Write Wearable flow (`StringEN.title['write_wearable']` = "Watch", resources.py:94)
- M2: starts the write process

Screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0472.png` -- "Data ready!" title, body text, "M1-4b" type, "Watch" / "Write" softkeys
- `framebuffer_captures/autocopy_mf1k_gen1a/0487.png` -- identical stable state
- `framebuffer_captures/autocopy_mf1k_gen1a/0500.png` -- identical
- `v1090_captures/090-Dump-Types-Files-Info-Write.png` -- same "Data ready!" screen from v1090

### State 6: Writing

Title: **"Write Tag"** (`StringEN.title['write_tag']`, resources.py:85)
Display: Tag info panel with write progress
Progress: **"Writing..."** / **"Verifying..."**
- `StringEN.procbarmsg['writing']` = "Writing..." (resources.py:181)
- `StringEN.procbarmsg['verifying']` = "Verifying..." (resources.py:182)

Screenshot:
- `framebuffer_captures/autocopy_mf1k_gen1a/0556.png` -- "Write Tag" title, tag info panel, "Verifying..." at bottom

Note: The title changes from "Auto Copy" to "Write Tag" when the write phase begins. This is because AutoCopy launches WriteActivity as a sub-activity.

### State 7: Write Success

Title: **"Write Tag"**
Toast overlay:
- Checkmark icon
- **"Write successful!"** (`StringEN.toastmsg['write_success']`, resources.py:115)
  or **"Write and Verify successful!"** (`StringEN.toastmsg['write_verify_success']`, resources.py:116)
Softkeys: **"Verify" / "Rewrite"**
- M1: `StringEN.button['verify']` = "Verify" (resources.py:51)
- M2: `StringEN.button['rewrite']` = "Rewrite" (resources.py:49)

Screenshots:
- `framebuffer_captures/autocopy_mf1k_gen1a/0600.png` -- "Write successful!" toast with checkmark, "Verify" / "Rewrite" softkeys
- `framebuffer_captures/autocopy_mf1k_gen1a/0611.png` -- same state persisted
- `framebuffer_captures/autocopy_mf1k_gen1a/0664.png` -- same
- `framebuffer_captures/autocopy_mf1k_gen1a/0714.png` -- same
- `framebuffer_captures/autocopy_mf1k_gen1a/0762.png` -- same (user idle)

### State 7b: Write Failure

Toast: **"Write failed!"** (`StringEN.toastmsg['write_failed']`, resources.py:117)
Softkeys: **"Verify" / "Rewrite"** (same as success -- allows retry)

### State 8: Verification (after pressing M1 on Write Success)

Returns to Write Tag display with **"Verifying..."** progress text.

On success: **"Verification successful!"** (`StringEN.toastmsg['verify_success']`, resources.py:118)
On failure: **"Verification failed!"** (`StringEN.toastmsg['verify_failed']`, resources.py:119)

---

## 5. Key Handling (onKeyEvent)

`onKeyEvent` (activity_main_ghidra_raw.txt:57877-58772) is the largest method in AutoCopyActivity at ~900 lines of decompiled code. It handles state-dependent key dispatch:

The method receives `(self, key)` as two positional args (line 57912: `iVar10 != 2` checks arg count is exactly 2).

### Key dispatch logic (decompiled structure):

1. **Check `self.isRunning`** (line 57979-57984): Get attribute, test boolean
   - If True (task running): check `self.isTimeOut()` (line 58013-58024)
     - If timed out: True branch -- call `self.stopTask()` (line 58194-58200)
     - If not timed out: return None (ignore key press during active operation)
   - If False (no task running): fall through to key comparison

2. **Compare key against `Keys.KEY_OK`** (line 58055-58093): RichCompare with `==`
   - If key == KEY_OK: call `self.startScan()` (line 58194-58200, via attribute lookup)
   - This allows re-scanning from the idle/toast state

3. **Compare key against `Keys.KEY_M1`** (line 58123-58175): RichCompare with `==`
   - If key == KEY_M1: call `StartNewActivity(self, key)` (line 58176)
   - This dispatches the M1 softkey action (Rescan, Reread, Verify, Watch depending on state)

4. **Check `self.readOK`** (line 58224-58253): Get attribute, test boolean
   - If False (read not complete): check `self.isRunning` again
     - If running: compare key to `Keys.KEY_M2` (line 58293-58329)
       - If key == KEY_M2: call `self.startScan()` -- M2 is also "Rescan" in this state
     - If not running: compare key to `Keys.KEY_M2` (line 58382-58423)
       - If key == KEY_M2: call `self.finish()` -- exit activity
   - If True (read complete):
     - Compare key to `Keys.KEY_M2` (line 58475-58531)
       - If key == KEY_M2: call `self.readFile.write()` -- navigate to write flow

5. **Compare key against `Keys.KEY_PWR`** (line 58543-58600):
   - If key == KEY_PWR: check `self.readFile` existence
     - If readFile exists: call `self.readFile.cancel()` then `self.finish()`
     - If no readFile: just `self.finish()`
   - PWR always exits/goes back (universal back key per project rules)

6. **Fallback**: compare key to `Keys.KEY_M2` for remaining states
   - If key == KEY_M2 and write state: call `StartNewActivity(self, key)` (line 58734)
   - This dispatches M2 softkey action (Write, Rewrite depending on state)

### Key summary by state:

| State | M1 | M2 | OK | PWR |
|-------|----|----|----|----|
| Scanning (running) | ignored | ignored | stopTask (if timeout) | cancel + finish |
| No tag found | Rescan | Rescan | startScan | finish |
| Reading (running) | ignored | ignored | stopTask (if timeout) | cancel + finish |
| Read success | Reread | Write | startScan | finish |
| Read failed | Rescan | Rescan | startScan | finish |
| Data ready | Watch | Write | -- | finish |
| Writing (running) | ignored | ignored | stopTask (if timeout) | cancel + finish |
| Write success | Verify | Rewrite | -- | finish |
| Write failed | Verify | Rewrite | -- | finish |

---

## 6. startScan

`startScan` (activity_main_ghidra_raw.txt:14556-14819) takes one arg `(self)`:

1. Sets `self.isRunning = True` (line 14637-14643, via SetAttr)
2. Sets `self.readOK = False` (line 14649-14654, same SetAttr pattern with same value)
3. Gets `self.clearCanvas` and calls it with no args (line 14660-14671) -- clears display
4. Calls super class `startScan` via parent chain (line 14694-14760)
   - Constructs PyTuple with (self.__class__, self) and calls `ScanActivity.startScan`
   - Then calls `.start()` on the returned task object

This re-uses the same scan infrastructure as ScanActivity but wraps it in the AutoCopy flow.

---

## 7. Flow Diagram

```
[Entry / onCreate]
        |
        v
  [State 1: Scanning]  <-- "Scanning..." + progress bar
        |
   tag found?
   /        \
  No         Yes
  |           |
  v           v
[No tag     [State 3: Reading/Cracking]
 toast]      ChkDIC -> Nested -> Reading
  |           |
  M1/M2:     success?
  Rescan      /      \
  |         Yes       No
  |          |         |
  +-----+   v         v
        |  [Read      [Read Failed
        |   Success    toast]
        |   toast]      |
        |    |     M1/M2: Rescan
        |    M1:Reread --+
        |    M2:Write
        |         |
        |         v
        |  [State 5: Data Ready]
        |   "Place new tag"
        |    M1:Watch  M2:Write
        |         |
        |         v
        |  [State 6: Writing]
        |   Writing... / Verifying...
        |         |
        |    success?
        |    /      \
        |  Yes       No
        |   |         |
        |   v         v
        |  [Write    [Write Failed
        |   Success   toast]
        |   toast]    M1:Verify
        |   M1:Verify M2:Rewrite
        |   M2:Rewrite
        |
  PWR at any state --> finish (exit to main menu)
```

---

## Key Bindings

### onKeyEvent (activity_main_ghidra_raw.txt line 57877)

PWR is handled at the keymap.so level (calls `actstack.finish_activity()`). Individual state handling below includes PWR defense-in-depth checks from the binary.

**Framework-level:** `isbusy()` check -- when busy (scan/read/write/verify in progress), only PWR works; all other keys are ignored.

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| SCANNING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| SCAN_NOT_FOUND | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| SCAN_WRONG_TYPE | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| SCAN_MULTI | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| READING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| READ_FAILED | no-op | no-op | no-op | no-op | _startRead() | startScan() | _startRead() | finish() |
| READ_NO_KEY_HF | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| READ_NO_KEY_LF | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| READ_MISSING_KEYS | no-op | no-op | no-op | no-op | _promptSwapCard() | startScan() | _promptSwapCard() | finish() |
| READ_TIMEOUT | no-op | no-op | no-op | no-op | _startRead() | startScan() | _startRead() | finish() |
| PLACE_CARD | no-op | no-op | no-op | no-op | _startWrite() | startScan() | _startWrite() | finish() |
| WRITING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| WRITE_SUCCESS | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| WRITE_FAILED | no-op | no-op | no-op | no-op | _startWrite() | startScan() | _startWrite() | finish() |
| VERIFYING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| VERIFY_SUCCESS | no-op | no-op | no-op | no-op | startScan() | startScan() | startScan() | finish() |
| VERIFY_FAILED | no-op | no-op | no-op | no-op | _startWrite() | startScan() | _startWrite() | finish() |

**Key pattern:** In scan-fail states (scan_found == False), M1/M2/OK all trigger rescan. In post-scan states (scan_found == True), M1 always rescans, M2/OK depends on the specific state.

**Source:** `src/lib/activity_main.py` lines 3630-3699, cross-referenced with `activity_main_ghidra_raw.txt` lines 57877-58772.

---

## 8. Sub-Activity Transitions

AutoCopy is unique because it chains multiple activities internally:
1. Uses `ScanActivity.startScan` for the scan phase
2. Transitions to read module (via `hfmfread.so`, `hf14aread.so`, etc.) for reading
3. Launches `WriteActivity` (or `WarningWriteActivity` for Gen1a) for the write phase

The "Write Tag" title change at State 6 confirms the write phase runs as a sub-activity under WriteActivity's own manifest. The title bar switches from "Auto Copy" to "Write Tag".

---

## 9. Audio Cues

Based on `audio_copy_ghidra_raw.txt` and `audio_ghidra_raw.txt`:
- Scan start: beep
- Tag found: success tone
- Read success: success tone
- Write success: success tone
- Failure states: error tone

---

## Corrections Applied

- **2026-03-31 (adversarial audit vs Real_Hardware_Intel screenshots)**: Audited against 6 real hardware screenshots (`auto_copy_scanning_1..4.png`, `auto_copy_no_tag_found.png`, `data_ready.png`). All title text, button labels, progress bar appearance, toast messages, and "Data ready!" screen layout confirmed accurate. No errors found.
