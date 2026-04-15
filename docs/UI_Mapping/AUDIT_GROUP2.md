# UI Mapping Audit — Group 2

Auditor: Adversarial screenshot-vs-document comparison
Date: 2026-03-31
Method: Every claim in each UI mapping document was compared against real device screenshots. Screenshots are ABSOLUTE TRUTH.

---

## 1. Scan Tag (`04_scan_tag/README.md`)

### Screenshots examined
- `scan_tag_scanning_1.png` — Scanning state, early progress
- `scan_tag_scanning_2.png` — Scanning state, mid progress
- `scan_tag_no_tag_found_1.png` — "No tag found" toast, no buttons visible yet
- `scan_tag_no_tag_found_2.png` — "No tag found" toast with Rescan/Rescan buttons
- `scan_tag_no_tag_found_3.png` — Tag Found state: MIFARE info + "Tag Found" toast + Rescan/Simulate buttons

### CONFIRMED
- Title during scanning: "Scan Tag" -- CORRECT (visible in scanning_1, scanning_2)
- Progress bar text: "Scanning..." -- CORRECT (visible in both scanning screenshots)
- Progress bar is blue horizontal bar -- CORRECT
- No buttons visible during scanning -- CORRECT (scanning_1, scanning_2 show no button bar)
- Toast "No tag found" text -- CORRECT (no_tag_found_1 shows exactly "No tag found" with X icon)
- Toast "Tag Found" text -- CORRECT (no_tag_found_3 shows "Tag Found" with checkmark icon)
- Tag info display after found: shows MIFARE, M1 S50 1K (4B), Frequency, UID, SAK, ATQA -- CORRECT (no_tag_found_3)
- `toastmsg.tag_found` = "Tag Found" -- CORRECT
- `toastmsg.no_tag_found` = "No tag found" -- CORRECT
- `procbarmsg.scanning` = "Scanning..." -- CORRECT
- `button.rescan` = "Rescan" -- CORRECT

### ERRORS

**ERROR 1: "No tag found" buttons are BOTH "Rescan", not just left button**
- Document (line 225): "Left button 'Rescan' shown" -- implies only one button
- Screenshot `scan_tag_no_tag_found_2.png`: Shows BOTH M1="Rescan" AND M2="Rescan"
- The document does not mention that M2 is also labeled "Rescan" in the NOT_FOUND state

**ERROR 2: FOUND state buttons — M2 is "Simulate", not context-dependent**
- Document (line 184-185): "Right button: context-dependent (may show 'Read' or 'Sniff' depending on flow)"
- Screenshot `scan_tag_no_tag_found_3.png` (which is actually the FOUND state): Shows M1="Rescan" and M2="Simulate" clearly
- In standalone Scan Tag, the right button is definitively "Simulate", NOT "Read" or "Sniff"

**ERROR 3: Document says "No tag found" toast appears without describing the X icon**
- Screenshot `scan_tag_no_tag_found_1.png`: Toast shows a circled-X icon to the left of "No tag found"
- Screenshot `scan_tag_no_tag_found_3.png`: "Tag Found" toast shows a circled-checkmark icon
- Document does not mention toast icons at all

**ERROR 4: The "no_tag_found" state shows two sequential phases not documented**
- Phase 1 (`no_tag_found_1.png`): Toast appears, NO buttons visible yet
- Phase 2 (`no_tag_found_2.png`): Toast still visible, buttons "Rescan"/"Rescan" NOW appear
- Document does not distinguish these two phases

### CORRECTIONS NEEDED
1. Section "State: NOT_FOUND": Change "Left button 'Rescan' shown" to "Both buttons shown: M1='Rescan', M2='Rescan'"
2. Section "State: FOUND": Change "Right button: context-dependent" to "Right button: 'Simulate' in standalone scan flow"
3. Add toast icon descriptions: X icon for failure toasts, checkmark icon for success toasts
4. Document the phased button appearance: buttons appear AFTER toast display, not simultaneously

---

## 2. Sniff (`06_sniff/README.md`)

### Screenshots examined
- `sniff_trf_list_1_1.png` — Type selection list
- `sniff_trf_1_4_1.png` — Step 1 instruction
- `sniff_trf_2_4.png` — Step 2 instruction
- `sniff_trf_3_4.png` — Step 3 instruction
- `sniff_trf_4_4.png` — Step 4 instruction
- `sniff_trf_sniffing.png` — Sniffing in progress
- `trace.png` — Trace result screen

### CONFIRMED
- Title: "Sniff TRF" -- CORRECT (visible in all screenshots)
- Type list: 5 items ("1. 14A Sniff", "2. 14B Sniff", "3. iclass Sniff", "4. Topaz Sniff", "5. T5577 Sniff") -- CORRECT (list_1_1.png)
- Page indicator on type list: "1/1" -- CORRECT (list_1_1.png shows "Sniff TRF 1/1")
- No buttons visible on type selection screen -- CORRECT (list_1_1.png shows no button bar)
- Step instructions are displayed one at a time as paginated pages, not all at once
- Step 1 text matches document (with formatting difference, see errors)
- Step 2 text matches document (with formatting difference, see errors)
- Step 3 text matches document (with formatting difference, see errors)
- Step 4 text matches document (with formatting difference, see errors)
- Buttons during INSTRUCTION: M1="Start", M2="Finish" -- CORRECT (all step screenshots show "Start" left, "Finish" right)
- Sniffing in progress toast: "Sniffing in progress..." -- CORRECT (sniffing.png shows this exact text as overlay)
- Trace result screen title: "Trace" -- CORRECT (trace.png)
- Trace result shows "TraceLen: 0" -- consistent with `itemmsg.sniff_trace` = "TraceLen: {}"
- Trace result buttons: M1="Cancel", M2="Save" -- CORRECT (trace.png)

### ERRORS

**ERROR 1: Instruction step text formatting does not match screenshots**
- Document (line 117): `"Step 1: \nPrepare client's \nreader and tag, \nclick start."`
- Screenshot `sniff_trf_1_4_1.png`: Shows "Step 1:\nPrepare client's\nreader and tag,\nclick start." -- The text wrapping is different. The actual text reads "Prepare client's reader and tag, click start." as a flowing paragraph, NOT with explicit line breaks as the resource strings suggest. The device renders by word-wrapping to fit the screen width.
- This applies to all 4 steps -- the document quotes resource strings with explicit `\n` that represent the original string, but the actual device rendering wraps differently.

**ERROR 2: Instruction pages show page indicator "N/4", not mentioned in document**
- Screenshots show: "Sniff TRF 1/4", "Sniff TRF 2/4", "Sniff TRF 3/4", "Sniff TRF 4/4"
- Document (line 107): States "Title bar: 'Sniff TRF' (unchanged)" for INSTRUCTION state
- The title DOES change -- it appends a page indicator "N/4" showing which step is displayed

**ERROR 3: Navigation arrows visible between buttons not documented**
- Screenshots (all step pages): Show up/down arrow icons (triangle pair) between "Start" and "Finish" buttons at the bottom
- Document does not mention these navigation arrow indicators

**ERROR 4: Buttons during SNIFFING are "Start" and "Finish", not "Stop"**
- Document (line 179): States left button "changes to 'Stop' or 'Finish'" during SNIFFING
- Screenshot `sniff_trf_sniffing.png`: Shows M1="Start" and M2="Finish" -- the Start button does NOT change to "Stop"
- The button labels remain "Start"/"Finish" even during active sniffing

**ERROR 5: Trace result buttons document says "Save" for left button**
- Document (line 214): "Left button: `button.save_log` -> 'Save'"
- Screenshot `trace.png`: Shows M1="Cancel" (left) and M2="Save" (right)
- The left button is "Cancel", not "Save". "Save" is the RIGHT button (M2).

**ERROR 6: Sniffing state still shows Step 1 instruction text behind toast**
- Screenshot `sniff_trf_sniffing.png`: The step 1 instruction text is still visible behind the "Sniffing in progress..." toast overlay
- Document (line 175) implies "instruction text remains visible" for HF types, which is correct but understated -- it's the specific step page that was showing, not all instructions

### CORRECTIONS NEEDED
1. INSTRUCTION state title: Change "Sniff TRF (unchanged)" to "Sniff TRF N/4" with page indicator
2. Add description of navigation arrow icons between Start and Finish buttons
3. SNIFFING state buttons: Change to M1="Start", M2="Finish" (no "Stop" button)
4. RESULT state buttons: M1="Cancel" (left), M2="Save" (right) -- fix the reversal
5. Clarify that the resource string `\n` characters may not correspond to actual screen line breaks (device word-wraps to fit)

---

## 3. Erase Tag (`13_erase_tag/README.md`)

### Screenshots examined
- `erase_tag_menu_1.png` — Type selection (2 items)
- `erase_tag_menu_2.png` — Scanning state with progress bar
- `erase_tag_menu_3.png` — ChkDIC phase
- `erase_tag_menu_4.png` — "Erasing 0%" with progress bar
- `erase_tag_menu_5.png` — "Erasing 0%" different progress
- `erase_tag_menu_6.png` — Erase/Erase buttons visible
- `erase_tag_scanning.png` — Scanning state (no progress text visible)
- `erase_tag_unknown_error.png` — "Unknown error" toast with Erase/Erase buttons

### CONFIRMED
- Title: "Erase Tag" -- CORRECT (visible in all screenshots)
- Menu items: "1. Erase MF1/L1/L2/L3" and "2. Erase T5577" -- CORRECT (menu_1.png)
- 2 items, single page -- CORRECT
- Scanning state shows "Scanning..." with progress bar -- CORRECT (menu_2.png)
- ChkDIC phase visible -- CONFIRMED (menu_3.png shows "ChkDIC")
- Erasing progress shows percentage: "Erasing 0%" -- CONFIRMED (menu_4.png, menu_5.png)
- Error toast: "Unknown error" -- CORRECT (erase_tag_unknown_error.png)
- Both buttons show "Erase"/"Erase" after error -- CORRECT (erase_tag_unknown_error.png, menu_6.png)
- `toastmsg.err_at_wiping` = "Unknown error" -- CORRECT
- `itemmsg.wipe_m1` = "Erase MF1/L1/L2/L3" -- CORRECT
- `itemmsg.wipe_t55xx` = "Erase T5577" -- CORRECT

### ERRORS

**ERROR 1: ERASING state progress format not fully documented**
- Document (line 80): Says progress text is "Erasing..." (`procbarmsg.tag_wiping`)
- Screenshots `menu_4.png`, `menu_5.png`: Show "Erasing 0%" -- with a percentage appended
- The actual progress format is "Erasing N%" not just "Erasing..."
- The document's `procbarmsg.wipe_block` = "Erasing" (line 81) is closer -- it seems "Erasing" is the base string with percentage appended

**ERROR 2: No buttons visible during scanning**
- Document (line 68): "Footer: None (operation in progress)" -- CORRECT
- Screenshot `erase_tag_scanning.png`: Shows an empty progress bar area with no text -- no "Scanning..." text visible
- This contradicts `menu_2.png` which does show "Scanning..." -- the `scanning.png` may be a different capture timing
- The document is ambiguous about which scanning sub-phase shows which text

**ERROR 3: ChkDIC intermediate phase not documented**
- Screenshot `menu_3.png`: Shows "ChkDIC" text above the progress bar
- Document does not mention a "ChkDIC" phase in the ERASING/SCANNING states
- This is the dictionary key checking phase that occurs between scanning and erasing

**ERROR 4: Document says both M1 and M2 show "Erase" during/after erase but does not distinguish states**
- Screenshots show that buttons "Erase"/"Erase" appear in the result/error state (menu_6.png, unknown_error.png)
- The document is correct that both show "Erase" but unclear about WHEN they appear -- they appear AFTER the operation completes (success or failure), not during

### CORRECTIONS NEEDED
1. ERASING state: Progress format should be "Erasing N%" (with percentage), not just "Erasing..."
2. Add ChkDIC intermediate phase: Between scanning and erasing, a "ChkDIC" key checking phase is shown
3. Clarify button visibility timing: "Erase"/"Erase" buttons appear only after operation completion, not during scanning/erasing
4. Document the difference between `erase_tag_scanning.png` (blank progress bar) and `erase_tag_menu_2.png` (shows "Scanning...")

---

## 4. Diagnosis (`09_diagnosis/README.md`)

### Screenshots examined
- `diagnosis_menu_1.png` — Main menu: "User diagnosis" / "Factory diagnosis"
- `diagnosis_menu_2.png` — Tips screen: "Press start button to start diagnosis."
- `diagnosis_menu_3.png` — Testing: "Testing with: HF Voltage"
- `diagnosis_menu_4.png` — Testing: "Testing with: LF Voltage"
- `diagnosis_menu_5.png` — Testing: "Testing with: LF reader"
- `diagnosis_menu_6.png` — Testing: "Testing with: Flash Memory"
- `diagnosis_results_1_1.png` — Results checklist page 1/1

### CONFIRMED
- Title: "Diagnosis" -- CORRECT (all screenshots)
- Main menu items: "User diagnosis" and "Factory diagnosis" -- CORRECT (menu_1.png)
- 2 items, single page -- CORRECT
- Tips text: "Press start button to start diagnosis." -- CORRECT (menu_2.png)
- Testing display format: "Testing with: {test_name}" -- CORRECT (menu_3 through menu_6)
- Test names visible: "HF Voltage", "LF Voltage", "LF reader", "Flash Memory" -- CORRECT
- `itemmsg.diagnosis_item1` = "User diagnosis" -- CORRECT
- `itemmsg.diagnosis_item2` = "Factory diagnosis" -- CORRECT
- `tipsmsg.start_diagnosis_tips` matches -- CORRECT

### ERRORS

**ERROR 1: Tips screen buttons are REVERSED from document**
- Document (line 93-94): "M1: 'Start' -- starts selected test" and "M2: (none)"
- Screenshot `diagnosis_menu_2.png`: Shows M1="Cancel" (left) and M2="Start" (right)
- The "Start" button is on the RIGHT (M2), not the LEFT (M1). And there IS an M1 button: "Cancel"

**ERROR 2: Document does not mention "Cancel" button on tips screen**
- Screenshot `diagnosis_menu_2.png`: Clearly shows "Cancel" on the left
- Document only lists "Start" for M1

**ERROR 3: Results page format partially wrong**
- Document (line 73-74): Describes CheckedListView with "test name on LEFT, pass/fail indicator (filled square) on RIGHT"
- Screenshot `diagnosis_results_1_1.png`: Shows results as "HF Voltage  : [checkmark] (37V)", "LF Voltage  : [checkmark] (43V)", "HF reader   : [checkmark]", "LF reader   : [checkmark]", "Flash Memory: [checkmark]"
- The format is NOT a filled square indicator -- it uses a checkmark character followed by voltage values in parentheses for voltage tests
- The page indicator shows "1/1" -- CORRECT for 5 results fitting on one page

**ERROR 4: Document says 9 test items across 2 pages but results show 5 items on 1 page**
- Document (line 73): "9 items across 2 pages (5 items/page, page indicator in title)"
- Screenshot `diagnosis_results_1_1.png`: Shows page indicator "1/1" with 5 items
- This suggests only 5 tests ran (user diagnosis may show fewer tests than the full 9), OR the remaining tests are on a second page not captured
- The page indicator "1/1" contradicts the "2 pages" claim -- at least for the captured user diagnosis run, there is only 1 page

**ERROR 5: Result value format not documented**
- Screenshot `diagnosis_results_1_1.png`: HF Voltage shows "checkmark (37V)", LF Voltage shows "checkmark (43V)"
- Document does not mention that voltage test results include the actual voltage reading in parentheses

**ERROR 6: Testing state display not described in document**
- Screenshots `diagnosis_menu_3.png` through `diagnosis_menu_6.png`: Show blue text "Testing with:\n{test name}" centered on screen with no buttons
- Document does not describe this intermediate testing state at all -- the `tipsmsg.testing_with` string is listed in the resource table (line 552) but not described as a screen state

### CORRECTIONS NEEDED
1. Tips screen buttons: M1="Cancel" (left), M2="Start" (right) -- reverse the document
2. Add "Cancel" button documentation for the tips screen
3. Results format: Use checkmark character with optional voltage values in parentheses, NOT filled squares
4. Clarify page count for user diagnosis -- may show 1 page (5 items) not 2
5. Document the intermediate "Testing with:" state screen (blue text, no buttons)
6. Add voltage value display format for HF/LF Voltage test results

---

## 5. Read Tag (`05_read_tag/README.md`)

### Screenshots examined
- `read_tag_list_1_8.png` — Tag list page 1/8
- `read_tag_list_8_8.png` — Tag list page 8/8
- `read_tag_scanning_1.png` through `read_tag_scanning_12.png` — Scanning and reading phases
- `read_tag_reading_1.png` through `read_tag_reading_7.png` — Reading/key checking phases
- `read_tag_no_tag_or_wrong_type_1.png` through `read_tag_no_tag_or_wrong_type_3.png` — Error and success states

### CONFIRMED
- List title: "Read Tag 1/8" -- CORRECT (read_tag_list_1_8.png)
- Page 1 items: "1. M1 S50 1K 4B", "2. M1 S50 1K 7B", "3. M1 S70 4K 4B", "4. M1 S70 4K 7B", "5. M1 Mini" -- CORRECT (read_tag_list_1_8.png)
- 5 items per page -- CORRECT
- Page 8/8 items: "36. Presco ID", "37. Visa2000 ID", "38. NexWatch ID", "39. T5577", "40. EM4305" -- CORRECT (read_tag_list_8_8.png)
- 40 items total, 8 pages -- CORRECT
- No button bar on list screen -- CORRECT (list screenshots show no buttons)
- Scanning state title: "Read Tag" (no page indicator) -- CORRECT (scanning_1.png)
- Scanning state: "Scanning..." text with progress bar -- CORRECT (scanning_1 through scanning_3)
- Tag info display after scan: MIFARE, M1 S50 1K (4B), Frequency: 13.56MHZ, UID: 3AF73501, SAK: 08 ATQA: 0004 -- CORRECT (scanning_4.png onward)
- Key checking format: "ChkDIC...32/32keys" -- CORRECT (scanning_4.png shows "ChkDIC...32/32keys")
- Reading format: "Reading...32/32Keys" -- CORRECT (scanning_5.png through scanning_11.png)
- Elapsed time format: "00'36''" -- CORRECT (scanning_4.png shows "00'36''")
- No tag found toast: "No tag found Or Wrong type found!" -- CORRECT (no_tag_or_wrong_type_1.png)
- Error state buttons: M1="Rescan", M2="Rescan" -- CORRECT (no_tag_or_wrong_type_2.png)
- Read success toast: "Read Successful! File saved" -- CORRECT (no_tag_or_wrong_type_3.png shows checkmark with "Read Successful! File saved")
- Success buttons: M1="Reread", M2="Write" -- CORRECT (no_tag_or_wrong_type_3.png)
- `toastmsg.no_tag_found2` text matches screenshot -- CORRECT

### ERRORS

**ERROR 1: "No tag found" buttons listed wrong in document**
- Document (line 359): "M1='Rescan'" -- implies only one button
- Screenshot `no_tag_or_wrong_type_2.png`: Shows BOTH M1="Rescan" AND M2="Rescan"
- The document does not mention M2="Rescan" for the no-tag-found state

**ERROR 2: Key checking phase shows timer countdown, not just elapsed time**
- Screenshots `reading_1.png` through `reading_7.png`: Show countdown timer format "01'08''", "01'07''", "01'06''", "01'05''", "01'04''", "01'03''" -- this is a COUNTDOWN, decreasing
- Also show "ChkDIC...0/32keys" -- starting from 0, counting up
- Document (line 266-270) describes the time format but implies it's elapsed time going up
- The actual behavior is a countdown timer (decreasing)

**ERROR 3: "Reading..." phase appears after key check with no button bar**
- Screenshots confirm no button bar during scanning/reading phases -- CORRECT
- But document does not mention that `reading_1.png` shows "Reading..." (without key count) as a brief initial state before the key progress appears

**ERROR 4: Post-scan tag info display appears during scanning, not after scanning**
- Screenshots `scanning_4.png` onward: Tag info (MIFARE, M1 S50 1K (4B), etc.) appears WHILE the key checking is in progress
- This is correctly described in the document (section 2.5) but the state labeling could be clearer -- "Tag Found" state and "Key Checking" state overlap visually

**ERROR 5: Document section 2.10 says toast is `no_tag_found2` but does not mention both Rescan buttons**
- Document (line 359): "Button bar: M1='Rescan'" -- only lists one button
- Screenshot `no_tag_or_wrong_type_2.png`: Both M1 and M2 show "Rescan"

### CORRECTIONS NEEDED
1. Section 2.10 (No Tag Found): Add M2="Rescan" -- both buttons show "Rescan"
2. Section 2.5 (Key Checking): Clarify that the timer is a COUNTDOWN (decreasing), not elapsed time
3. Add brief "Reading..." initial state (without key count) before "Reading...N/NKeys"
4. Section 5.4 (onKeyEvent) NO_TAG_FOUND row: Add M2 = Rescan

---

## 6. Write Tag (`16_write_tag/README.md`)

### Screenshots examined
- `data_ready.png` — WarningWriteActivity: "Data ready!"
- `write_tag_writing_1.png` — Writing state (no progress bar yet)
- `write_tag_writing_2.png` — Writing state (progress bar visible)
- `write_tag_writing_3.png` — After writing: Verify/Rewrite buttons
- `write_tag_write_failed.png` — "Write failed!" toast

### CONFIRMED
- Data ready screen title: "Data ready!" -- CORRECT (data_ready.png)
- Data ready content: "Data ready for copy! Please place new tag for copy." -- CORRECT (data_ready.png)
- Data ready TYPE display: "TYPE:" followed by "M1-4b" in large text -- CORRECT (data_ready.png)
- Data ready buttons: M1="Watch", M2="Write" -- CORRECT (data_ready.png)
- Write Tag title: "Write Tag" -- CORRECT (writing_1.png through write_failed.png)
- Tag info display: MIFARE, M1 S50 1K (4B), Frequency: 13.56MHZ, UID: 3AF73501, SAK: 08 ATQA: 0004 -- CORRECT
- Writing state shows "Writing..." text -- CORRECT (writing_1.png, writing_2.png)
- Progress bar visible during writing -- CORRECT (writing_2.png)
- After writing: M1="Verify" (left), M2="Rewrite" (right) -- CORRECT (writing_3.png)
- Write failed toast: "Write failed!" with X icon -- CORRECT (write_failed.png)
- After failure: M1="Verify" (left), M2="Rewrite" (right) -- CORRECT (write_failed.png)
- `toastmsg.write_failed` = "Write failed!" -- CORRECT

### ERRORS

**ERROR 1: Document claims tag UID is "2CADC272" but screenshots show "3AF73501"**
- Document (sections 2.3-2.9): Consistently uses UID "2CADC272" in all ASCII art diagrams
- Screenshots `write_tag_writing_1.png` through `write_tag_write_failed.png`: Show UID "3AF73501"
- This is a different tag -- the document's ASCII art uses evidence from different captures than the provided screenshots. The document correctly references its own screenshot evidence elsewhere but the UID in the template diagrams is from a different tag capture.
- This is NOT an error in the UI mapping logic, just different test tags in different captures.

**ERROR 2: Document says buttons disabled during writing show "buttons disabled/greyed"**
- Document (line 195): "(buttons disabled/greyed)"
- Screenshots `writing_1.png` and `writing_2.png`: Show NO button bar at all during writing -- buttons are not just greyed, they appear to be completely absent
- The document implies buttons are visible but greyed; screenshots suggest they are entirely hidden

**ERROR 3: Document section 2.6 claims "This is the OPPOSITE order from write success" -- WRONG**
- Document (line 253): "IMPORTANT: After write failure, the button labels are... This is the OPPOSITE order from write success."
- Screenshots show: After write SUCCESS (`writing_3.png`): M1="Verify", M2="Rewrite"
- After write FAILURE (`write_failed.png`): M1="Verify", M2="Rewrite"
- The button order is IDENTICAL in both success and failure states. The document's claim that they are "OPPOSITE" is factually wrong.
- Later in the same document (section 4.3 on_write, line 387), it correctly states they are the same for both outcomes. This is a direct self-contradiction.

**ERROR 4: Initial WriteActivity buttons not visible in screenshots**
- Document (line 170): Shows M1="Write", M2="Verify" as initial state
- No screenshot provided shows the initial IDLE state with Write/Verify buttons
- Cannot confirm or deny from available screenshots

### CORRECTIONS NEEDED
1. Section 2.6: Remove the claim "This is the OPPOSITE order from write success" -- the order is IDENTICAL (M1="Verify", M2="Rewrite") for both success and failure
2. WRITING state: Change "buttons disabled/greyed" to "button bar hidden" (not visible at all during write)
3. Note that the self-contradiction between section 2.6 and section 4.3 must be resolved -- section 4.3 is correct

---

## 7. Time Settings (`14_time_settings/README.md`)

### Screenshots examined
- `time_settings_1.png` — Display mode: 2026-03-31, 01:15:16, Edit/Edit
- `time_settings_2.png` — Display mode: 2026-03-31, 01:15:17, Edit/Edit
- `time_settings_3.png` — Edit mode: caret on year field, Cancel/Save
- `time_settings_4.png` — Edit mode: caret on year field, Cancel/Save
- `time_settings_5.png` — Edit mode: caret on day field, Cancel/Save
- `time_settings_6.png` — Edit mode: caret on hour field, Cancel/Save
- `time_settings_7.png` — Edit mode: caret on minute field, Cancel/Save
- `time_settings_8.png` — Edit mode: minute changed to 17, caret on minute
- `time_settings_9.png` — Edit mode: caret on second field
- `time_settings_10.png` — Display mode: showing updated time 01:17:21, Edit/Edit
- `time_settings_sync_1.png` — Sync toast: "Synchronizing system time"
- `time_settings_sync_2.png` — Sync toast: "Synchronization successful!"
- `time_settings_sync_3.png` — Sync toast: "Synchronization successful!" (continued)
- `time_settings_sync_4.png` — Sync toast: "Synchronization successful!" (continued)

### CONFIRMED
- Title: "Time Settings" -- CORRECT (all screenshots)
- Display mode shows 6 numeric fields in YYYY-MM-DD / HH:MM:SS format -- CORRECT
- Display mode separators: "-" between date fields, ":" between time fields -- CORRECT
- Display mode buttons: M1="Edit", M2="Edit" -- CORRECT (time_settings_1.png, _2.png, _10.png)
- Edit mode buttons: M1="Cancel", M2="Save" -- CORRECT (time_settings_3.png through _9.png)
- Edit mode shows caret/arrow indicator on focused field -- CORRECT (visible in all edit screenshots)
- Caret moves between fields: seen on year (3), day (5), hour (6), minute (7,8), second (9) -- CORRECT
- Sync toast: "Synchronizing system time" -- CORRECT (sync_1.png)
- Sync success toast: "Synchronization successful!" -- CORRECT (sync_2.png through sync_4.png)
- After sync, returns to Display mode with Edit/Edit buttons -- CORRECT (sync screenshots show Edit/Edit in button bar)
- Field values are editable (minute changed from 15 to 17 between screenshots) -- CORRECT

### ERRORS

**ERROR 1: Document shows caret as "^" but real device shows an upward-pointing triangle**
- Document (line 57-58): Shows "^" character as focus indicator
- Screenshots (time_settings_3.png through _9.png): Show a filled upward-pointing triangle (arrow) beneath the focused field
- This is cosmetic but the document should use the correct glyph description

**ERROR 2: Document says "up/down arrows on focused field" but only ONE arrow visible**
- Document (line 70): "six fields with up/down arrows visible on the focused field"
- Screenshots: Only show a SINGLE upward-pointing arrow beneath the focused field -- there is no downward arrow visible. The arrow always points UP.
- The document incorrectly describes two arrows; there is only one.

**ERROR 3: Document diagram shows date "1970-02-12" and time "03:38:42" -- stale example**
- Document (line 23-28): Shows example values 1970-02-12 and 03:38:42
- Screenshots show 2026-03-31 and 01:15:16 (current time)
- Not a mapping error per se, but the document uses epoch-near values suggesting it was written from decompilation, not from real device observation

### CORRECTIONS NEEDED
1. Change "up/down arrows" to "single upward-pointing triangle arrow" beneath the focused field
2. Clarify that the focus indicator is a single upward triangle, not a pair of up/down arrows
3. Update example values to real-world values for clarity (optional, cosmetic)

---

## 8. LUA Script (`15_lua_script/README.md`)

### Screenshots examined
- `lua_script_1_10.png` — Script list page 1/10
- `lua_script_10_10.png` — Script list page 10/10
- `lua_console_1.png` through `lua_console_10.png` — Console output

### CONFIRMED
- Title: "LUA Script" with page indicator -- CORRECT
- Page format: "LUA Script 1/10" -- CORRECT (lua_script_1_10.png)
- 5 items per page on page 1 -- CORRECT (lua_script_1_10.png shows 5 items)
- Page 10/10 shows 3 items (partial page) -- CORRECT (lua_script_10_10.png: "lf_t55xx_defaultpsk", "lf_t55xx_writetest", "mfc_gen3_writer")
- Script names displayed without .lua extension -- CORRECT
- Script names use underscore format -- CORRECT
- Console shows PM3 command output -- CORRECT (console screenshots show "[usb|script] pm3 --> script run ...")
- Console text is cyan/green on black background -- CORRECT (all console screenshots)
- Console shows "Nikola.D: 0" at end -- CORRECT (lua_console_10.png)

### ERRORS

**ERROR 1: Document says 10 pages but references 18 pages from 090-Lua.png**
- Document (line 90-91): References `090-Lua.png` showing "LUA Script 1/18" with 18 pages
- Screenshots provided: `lua_script_1_10.png` shows "LUA Script 1/10" -- 10 pages
- The document notes this discrepancy (line 101) about dynamic page count, so it's acknowledged but the reference to 18 pages from a different screenshot set is confusing

**ERROR 2: Script list items differ from document's reference screenshots**
- Document (line 82-87): Lists items from `sub_13_lua_script.png`: "legic", "test_t55x7_bi", "mifareplus", "mfu_magic", "dumptoemul"
- Document (line 92-98): Lists items from `090-Lua.png`: "data_dumptohtml", "data_emulatortodump", "data_emulatortohtml", "data_example_cmdline", "data_example_parameter"
- Screenshot `lua_script_1_10.png`: Shows "data_dumptohtml", "data_emulatortodump", "data_emulatortohtml", "data_example_cmdline", "data_example_parameter"
- The real device screenshot matches the 090-Lua.png items but NOT the sub_13_lua_script.png items (which are from QEMU). This is not an error in the document per se, but the QEMU screenshot shows different/fewer scripts.

**ERROR 3: Document does not describe button labels for script list**
- Document (line 75-76): "M1: '' (empty), M2: 'OK'"
- Screenshots `lua_script_1_10.png` and `lua_script_10_10.png`: Show NO button bar at all -- the list takes up the full screen below the title
- The document claims M2="OK" but no buttons are visible in the screenshots

**ERROR 4: Console button labels not visible or described accurately**
- Document (line 245-248): States M1="Cancel" while RUNNING, M2="" (empty), and when COMPLETE M2="OK"
- Console screenshots: Show no button bar visible in any of the console captures
- Cannot confirm button labels from available screenshots -- all console captures show pure text output filling the screen

**ERROR 5: Console title not visible in screenshots**
- Document (line 219): "Title: Set from bundle 'title' parameter, or default 'Console'"
- Console screenshots: No title bar visible -- the console appears to use the full screen for text output
- Cannot confirm the title claim from screenshots

### CORRECTIONS NEEDED
1. Clarify that the script list screen may or may not show buttons -- screenshots show no button bar
2. Note that console uses full-screen text output with no visible title bar or button bar in the available captures
3. Reconcile the page count discrepancy (10 vs 18) more clearly -- it depends on the number of scripts installed on the device

---

## Summary of All Errors Found

| Document | Error Count | Critical Errors |
|----------|------------|-----------------|
| 04_scan_tag | 4 | Buttons in FOUND state wrong (shows "Simulate" not "Read") |
| 06_sniff | 6 | RESULT buttons reversed (Cancel/Save not Save/--); Start button doesn't change to Stop; page indicator missing from INSTRUCTION title |
| 13_erase_tag | 4 | Missing ChkDIC phase; erasing format is "Erasing N%" not "Erasing..." |
| 09_diagnosis | 6 | Tips screen buttons REVERSED (Cancel/Start not Start/--); result format wrong (checkmarks not squares); testing-with state undocumented |
| 05_read_tag | 5 | Both buttons "Rescan" in no-tag state; timer is countdown not elapsed |
| 16_write_tag | 3 | Self-contradiction about button order (section 2.6 vs 4.3); buttons hidden not greyed during write |
| 14_time_settings | 3 | Only single up-arrow visible, not up/down pair |
| 15_lua_script | 5 | No button bar visible on list screen; console uses full-screen with no visible title/buttons |
| **TOTAL** | **36** | |
