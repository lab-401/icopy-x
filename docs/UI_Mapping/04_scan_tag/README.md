# ScanActivity UI Mapping

Source: `activity_main.so` (ScanActivity class), `scan.so` (Scanner class, scan0-scan5, scanForType)
Binary: `activity_main.so` MD5=809b40ad17ff8d6947e87452e974f41c
Binary: `scan.so` MD5=b44a7d7a72623148dd8a30a566b70a54

## Class Hierarchy

```
AutoExceptCatchActivity
  └── ScanActivity
```
(decompiled/activity_main_ghidra_raw.txt — class listed at V1090_MODULE_AUDIT.txt:1794)

## Activity Registration (getManifest)

ScanActivity.getManifest() builds and returns a dict with:
- title key: `scan_tag` -> "Scan Tag"  (resources.py:76, StringEN.title)
- Associated with `ScanActivity` class and a list view constructor

(decompiled/activity_main_ghidra_raw.txt:56496-56796, function `__pyx_pw_13activity_main_12ScanActivity_1getManifest @0x0006a314`)

## Methods (from V1090_MODULE_AUDIT.txt:1794-1837)

| Method | Purpose |
|--------|---------|
| `__init__(self, canvas)` | Initialize activity with canvas, set initial state attributes |
| `getManifest()` | Return activity manifest dict (title, class, list) |
| `onCreate(self)` | Setup UI: title bar, tag type ListView, buttons |
| `onKeyEvent(self, event)` | Handle KEY_OK, KEY_PWR, KEY_UP, KEY_DOWN |
| `onScanning(self, progress)` | Called during scan with (tag_type_name, progress_msg) tuple |
| `onScanFinish(self, data)` | Called when scan completes; dispatches getD closure |
| `onAutoScan(self)` | Initiate scan of selected type |
| `how2Scan(self)` | Get the scan method from Scanner and invoke it |
| `canidle(self, infos)` | Idle callback; returns None |
| `showButton(self, found, cansim=False)` | Show/hide left/right buttons based on found state |
| `showScanToast(self, found, multi)` | Display tag_found / no_tag_found / tag_multi toasts |
| `startScan(self)` | Begin scanning process |
| `playScanning()` | Play scanning sound |
| `unique_id(self, tags)` | De-duplicate tag list |

## State Machine

### State: IDLE (Tag Type Selection)

**Title bar:** "Scan Tag" (resources.py:76 `title.scan_tag`)

**Content:** Paginated ListView of tag types, 5 items per visible page.

The tag type list is loaded from `tagtypes.so` module (scan_ghidra_raw.txt:437 STR `tagtypes`).
The complete tag type list extracted from `tagtypes.so` (docs/V1090_SO_STRINGS_RAW.txt:3077-3227):

**HF Tags (High Frequency, 13.56 MHz):**

| # | Internal Key | Display Name |
|---|-------------|--------------|
| 1 | ISO14443B | ISO14443B |
| 2 | ISO15693_ICODE | ISO15693 ICODE |
| 3 | ISO15693_ST_SA | ISO15693 ST SA |
| 4 | MIFARE_DESFIRE | MIFARE DESFire |
| 5 | NTAG213_144B | NTAG213 144b |
| 6 | NTAG215_504B | NTAG215 504b |
| 7 | NTAG216_888B | NTAG216 888b |
| 8 | LEGIC_MIM256 | LEGIC_MIM256 |
| 9 | Topaz | Topaz |
| 10 | Ultralight | Ultralight |
| 11 | Ultralight C | Ultralight C |
| 12 | Ultralight EV1 | Ultralight EV1 |

**LF Tags (Low Frequency, 125/134 kHz):**

| # | Internal Key | Display Name |
|---|-------------|--------------|
| 13 | AWID_ID | AWID ID |
| 14 | EM410X_ID | EM410x ID |
| 15 | FDXB_ID | FDXB ID |
| 16 | T55X7_ID | T55x7_ID / T5577 |
| 17 | HID Prox ID | HID Prox ID |
| 18 | Hitag2 ID | Hitag2 ID |
| 19 | Indala ID | Indala ID |
| 20 | Jablotron ID | Jablotron ID |
| 21 | KERI_ID | KERI ID |
| 22 | NEDAP_ID | NEDAP ID |
| 23 | NexWatch ID | NexWatch ID |
| 24 | Noralsy ID | Noralsy ID |
| 25 | PAC_ID | PAC ID |
| 26 | Paradox ID | Paradox ID |
| 27 | Presco ID | Presco ID |
| 28 | Pyramid ID | Pyramid ID |
| 29 | Securakey ID | Securakey ID |
| 30 | Viking ID | Viking ID |
| 31 | Visa2000 ID | Visa2000 ID |

(docs/V1090_SO_STRINGS_RAW.txt:3077-3227, tagtypes.so string table)

**Note:** The exact number of types may be up to ~48 depending on firmware version. The above are all types confirmed in the `tagtypes.so` binary string table. Additional types visible in `template.so` include iCLASS, iCLASS SE, Gallagher, MIFARE (MF1K/MF4K implied), MIFARE Mini — these may be detected during scan but registered under different display keys.

**Pagination:** 5 items per page, with page indicator in the title bar (e.g., "Scan Tag 1/7").

**Buttons:** Both left and right buttons are initially dismissed (hidden).

**Key handling in IDLE:**
- KEY_UP: Move selection up in ListView. If at top of page, scroll to previous page.
- KEY_DOWN: Move selection down in ListView. If at bottom of page, scroll to next page.
- KEY_OK: Select highlighted tag type -> transition to SCANNING state via `onAutoScan()`
- KEY_PWR: Exit activity (finish)

(decompiled/activity_main_ghidra_raw.txt:56004-56494, `__init__` sets up multiple attributes to None;
decompiled/activity_main_ghidra_raw.txt:16842-16959, `onAutoScan` calls `how2Scan()`;
V1090_MODULE_AUDIT.txt:1818 `onKeyEvent(self, event)`)

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: exact ListView visual rendering, item highlight style, page indicator format, font sizes, icon presence/absence]

### State: SCANNING (Progress Bar)

**Transition:** Triggered when user presses OK on a tag type in IDLE state.

**Title bar:** "Scan Tag" (unchanged)

**Content:** Progress bar with message from `procbarmsg.scanning` -> "Scanning..." (resources.py:186)

**Mechanism:**
1. `onAutoScan(self)` is called (decompiled/activity_main_ghidra_raw.txt:16842)
2. This calls `how2Scan(self)` which invokes the Scanner method
3. Scanner dispatches to one of `scan0` through `scan5` in `scan.so` depending on tag type (scan_ghidra_raw.txt:619-658)
4. `onScanning(self, progress)` is called as callback with a tuple `(tag_type_name, progress_message)` (decompiled/activity_main_ghidra_raw.txt:10585-10904)
5. The progress callback updates the scan progress bar text and title with tag info

**scan.so scan functions:**

| Function | Purpose |
|----------|---------|
| `scan0` | Primary scan function (scan_ghidra_raw.txt:619, `scan.scan0`) |
| `scan1` | Secondary scan function (scan_ghidra_raw.txt:625, `scan.scan1`) |
| `scan2` | Tertiary scan function (scan_ghidra_raw.txt:618, `scan.scan2`) |
| `scan3` | Scan function (scan_ghidra_raw.txt:643, `scan.scan3`) |
| `scan4` | Scan function (scan_ghidra_raw.txt:658, `scan.scan4`) |
| `scan5` | Scan function (scan_ghidra_raw.txt:636, `scan.scan5`) |
| `scanForType` | Route to correct scan function by tag type (scan_ghidra_raw.txt:307) |
| `lf_wav_filter` | T55XX gatekeeper: amplitude >= 90 filter (scan_ghidra_raw.txt:341) |

**Scanner class methods (scan_ghidra_raw.txt:292-348):**

| Method | Purpose |
|--------|---------|
| `Scanner.__init__` | Initialize scanner with callbacks |
| `Scanner.scan_type_asynchronous` | Async scan for single type |
| `Scanner.scan_type_synchronous` | Sync scan for single type |
| `Scanner.scan_all_asynchronous` | Async scan all types |
| `Scanner.scan_all_synchronous` | Sync scan all types |
| `Scanner.scan_stop` | Stop current scan |
| `Scanner._is_can_next` | Check if scanner can proceed |
| `Scanner._set_stop_label` / `_set_run_label` | Set scan state labels |
| `Scanner.call_progress` | Invoke progress callback |
| `Scanner.call_resulted` | Invoke result callback |
| `Scanner.call_exception` | Invoke exception callback |
| `Scanner._raise_on_multi_scan` | Handle multiple tag detection |

**Special scan string:** `CMD_DETECT_NO_KEY` (scan_ghidra_raw.txt:385 STR@0x00033d78) — used for T55xx detection without key.

**LF T55XX specifics:**
- `lf_wav_filter()` in scan.so processes LF waveform data
- `set_scan_t55xx_key` (scan_ghidra_raw.txt:319) — sets key for T55xx scan
- `set_scan_em4x05_key` (scan_ghidra_raw.txt:318) — sets key for EM4x05 scan
- `lf em 4x05_info` PM3 command (scan_ghidra_raw.txt:392 STR@0x00033dfc)

**Buttons:** Both buttons dismissed during scanning.

**Key handling in SCANNING:**
- KEY_PWR: Abort scan and return to IDLE

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: exact progress bar visual appearance, animation style]

### State: FOUND (Tag Found)

**Transition:** `onScanFinish(self, data)` called when scan succeeds.

**Toast:** `toastmsg.tag_found` -> "Tag Found" (resources.py:109)

**Content:** Tag info display showing scan results (type name, UID if available).

**Buttons:**
- Left button: `button.rescan` -> "Rescan" (resources.py:39)
- Right button: context-dependent (may show "Read" or "Sniff" depending on flow)
- `showButton(self, found, cansim)` controls visibility (V1090_MODULE_AUDIT.txt:1832)

**Scan result functions (scan.so):**

| Function | Purpose |
|----------|---------|
| `isTagFound` | Check if tag was found (scan_ghidra_raw.txt:309) |
| `isTagMulti` | Check if multiple tags detected (scan_ghidra_raw.txt:310) |
| `isTagLost` | Check if tag was lost (scan_ghidra_raw.txt:311) |
| `isTagTypeWrong` | Check if wrong type detected (scan_ghidra_raw.txt:312) |
| `isTimeout` | Check if scan timed out (scan_ghidra_raw.txt:308) |
| `isCanNext` | Check if can proceed (scan_ghidra_raw.txt:347) |
| `getScanCache` | Get cached scan results (scan_ghidra_raw.txt:325) |
| `set_infos_cache` | Cache scan info (scan_ghidra_raw.txt:298) |

**Key handling in FOUND:**
- KEY_OK (M1/Left): Rescan
- KEY_PWR: Exit to main menu

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: tag info layout, font, positioning of UID/type text]

### State: NOT_FOUND (No Tag)

**Transition:** `onScanFinish` when no tag detected, or timeout.

**Toast:** `toastmsg.no_tag_found` -> "No tag found" (resources.py:108)

**Alternate toast:** `toastmsg.no_tag_found2` -> "No tag found \nOr\n Wrong type found!" (resources.py:107)
This alternate is shown when `isTagTypeWrong` returns true (scan_ghidra_raw.txt:312).

**Error result creators (scan.so):**

| Function | Return Code | Purpose |
|----------|-------------|---------|
| `createTagNoFound` | Error object | No tag found (scan_ghidra_raw.txt:317) |
| `createTagLost` | Error object | Tag lost during scan (scan_ghidra_raw.txt:316) |
| `createTagMulti` | Error object | Multiple tags (scan_ghidra_raw.txt:315) |
| `createExecTimeout` | Error object | Execution timeout (scan_ghidra_raw.txt:314) |
| `createTagTypeWrong` | Error object | Wrong type found (scan_ghidra_raw.txt:313) |

**Buttons:** Left button "Rescan" shown.

**Key handling:** Same as FOUND (rescan or exit).

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: toast positioning, dismiss timing]

### State: MULTI (Multiple Tags)

**Transition:** `onScanFinish` when `isTagMulti` returns true.

**Toast:** `toastmsg.tag_multi` -> "Multiple tags detected!" (resources.py:110)

This state is triggered by `Scanner._raise_on_multi_scan` (scan_ghidra_raw.txt:299).

**Buttons:** Left button "Rescan" shown.

[UNRESOLVED -- NO SCREENSHOT EVIDENCE: toast display format]

### State: WRONG_TYPE (Wrong Tag Type)

**Transition:** `onScanFinish` when tag found but type doesn't match selection.

**Toast:** `toastmsg.no_tag_found2` -> "No tag found \nOr\n Wrong type found!" (resources.py:107)

Detected by `isTagTypeWrong` (scan_ghidra_raw.txt:312).

[UNRESOLVED -- NO SCREENSHOT EVIDENCE]

## Key Event Flow (onKeyEvent)

`ScanActivity.onKeyEvent(self, event)` (decompiled/activity_main_ghidra_raw.txt:587, `__pyx_pw_13activity_main_12ScanActivity_25onKeyEvent @0x000cd278`)

The function receives `(self, event)` where event contains:
- Key code comparison against KEY_OK, KEY_UP, KEY_DOWN, KEY_PWR
- State-dependent behavior: in IDLE selects tag type, during scan aborts

## ScanActivity __init__ Attributes

From decompiled/activity_main_ghidra_raw.txt:56004-56494 (`__pyx_pw_13activity_main_12ScanActivity_3__init__ @0x000699c8`):

The __init__ method calls the parent `__init__`, then sets approximately 10+ instance attributes to None:
- Scan state tracking attributes
- ListView reference
- Button references
- Progress bar reference
- Scanner instance reference
- Tag type cache

## Integration with Other Activities

ScanActivity is used as:
1. **Standalone scan:** Main menu -> Scan Tag -> select type -> scan
2. **Pre-read scan:** Read flow starts ScanActivity to detect tag, then transitions to ReadActivity via `onScanFinish`
3. **Pre-autocopy scan:** AutoCopy flow also starts with ScanActivity

The `onScanFinish` method (decompiled/activity_main_ghidra_raw.txt:544, `@0x000cc7bc`) contains a closure `getD` (line 6402, `@0x00031eb0`) that extracts scan data for downstream activities.

## Toast Strings Summary

| Key | Value | Source |
|-----|-------|--------|
| `toastmsg.tag_found` | "Tag Found" | resources.py:109 |
| `toastmsg.no_tag_found` | "No tag found" | resources.py:108 |
| `toastmsg.no_tag_found2` | "No tag found \nOr\n Wrong type found!" | resources.py:107 |
| `toastmsg.tag_multi` | "Multiple tags detected!" | resources.py:110 |
| `procbarmsg.scanning` | "Scanning..." | resources.py:186 |

## Button Strings Summary

| Key | Value | Source |
|-----|-------|--------|
| `button.rescan` | "Rescan" | resources.py:39 |
| `button.read` | "Read" | resources.py:34 |
| `button.simulate` | "Simulate" | resources.py:43 |

---

## Key Bindings

### ScanActivity.onKeyEvent (activity_main_ghidra_raw.txt line 587)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev() | next() | no-op | no-op | _startScanFromList() | finish() | _startScanFromList() | finish() |
| SCANNING | no-op | no-op | no-op | no-op | no-op | cancel + IDLE | cancel + IDLE | cancel + finish() |
| FOUND | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| NOT_FOUND | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| WRONG_TYPE | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| MULTI_TAGS | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |

**Notes:**
- In IDLE state, UP/DOWN scroll the 48-type tag list. M1 = "Back" (finish), M2/OK = "Scan" (start scan for selected type).
- In SCANNING state, M1/M2 both cancel scan and return to IDLE. PWR cancels and exits activity.
- In result states (FOUND/NOT_FOUND/WRONG_TYPE/MULTI), M1/M2/OK all trigger rescan.
- PWR is universal exit at all states.

**Source:** `src/lib/activity_main.py` lines 958-996, `activity_main_ghidra_raw.txt` line 587 (symbol), decompiled body at lines 20226+.
