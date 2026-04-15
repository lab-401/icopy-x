# UI_MAP_COMPLETE.md -- Master UI Map for iCopy-X Firmware

Generated: 2026-03-31
Updated: 2026-03-31 (post-adversarial audit corrections)
Sources: 17 activity docs + 3 framework docs + resources.py StringEN

---

## Section 1: Master Screen Chart

Every screen state across all activities. Each row = one distinct visual state the user can see.

| # | Activity | State | Title | M1 (Left) | M2 (Right) | Content | Source |
|---|----------|-------|-------|-----------|-----------|---------|--------|
| 1 | MainActivity | IDLE (page N) | "Main Page N/M" | (none) | (none) | ListView: 14 items, 5/page, 3 pages. Icons + text. | 01_main_menu, FB: read_mf1k_4b/0000.png |
| 2 | AutoCopyActivity | SCANNING | "Auto Copy" | (none) | (none) | ProgressBar "Scanning..." | 02_auto_copy, FB: autocopy_mf1k_gen1a/0249.png |
| 3 | AutoCopyActivity | NO_TAG_FOUND | "Auto Copy" | "Rescan" | "Rescan" | Toast: "No tag found" | 02_auto_copy, ref: sub_00_auto_copy.png |
| 4 | AutoCopyActivity | TAG_FOUND | "Auto Copy" | (none) | (none) | Tag info panel (family, type, freq, UID, SAK/ATQA) | 02_auto_copy, FB: autocopy_mf1k_gen1a/0275.png |
| 5 | AutoCopyActivity | READING_CHKDIC | "Auto Copy" | (none) | (none) | Tag info + timer + "ChkDIC...N/Mkeys" | 02_auto_copy, FB: autocopy_mf1k_gen1a/0300.png |
| 6 | AutoCopyActivity | READING_NESTED | "Auto Copy" | (none) | (none) | Tag info + timer + "Nested...N/Mkeys" | 02_auto_copy, FB: autocopy_mf1k_gen1a/0344.png |
| 7 | AutoCopyActivity | READING_BLOCKS | "Auto Copy" | (none) | (none) | Tag info + "Reading...N/MKeys" | 02_auto_copy, FB: autocopy_mf1k_gen1a/0426.png |
| 8 | AutoCopyActivity | READ_SUCCESS | "Auto Copy" | "Reread" | "Write" | Toast: "Read Successful! File saved" | 02_auto_copy, FB: autocopy_mf1k_gen1a/0450.png |
| 9 | AutoCopyActivity | READ_FAILED | "Auto Copy" | "Rescan" | "Rescan" | Toast: "Read Failed!" | 02_auto_copy |
| 10 | AutoCopyActivity | DATA_READY | "Data ready!" | "Watch" | "Write" | "Data ready for copy!\nPlease place new tag..." + TYPE | 02_auto_copy, FB: autocopy_mf1k_gen1a/0472.png |
| 11 | AutoCopyActivity | WRITING | "Write Tag" | (disabled) | (disabled) | Tag info + "Writing..." / "Verifying..." progress | 02_auto_copy, FB: autocopy_mf1k_gen1a/0556.png |
| 12 | AutoCopyActivity | WRITE_SUCCESS | "Write Tag" | "Verify" | "Rewrite" | Toast: "Write successful!" | 02_auto_copy, FB: autocopy_mf1k_gen1a/0600.png |
| 13 | AutoCopyActivity | WRITE_FAILED | "Write Tag" | "Verify" | "Rewrite" | Toast: "Write failed!" | 02_auto_copy |
| 14 | AutoCopyActivity | VERIFY_SUCCESS | "Write Tag" | "Verify" | "Rewrite" | Toast: "Verification successful!" | 02_auto_copy |
| 15 | AutoCopyActivity | VERIFY_FAILED | "Write Tag" | "Verify" | "Rewrite" | Toast: "Verification failed!" | 02_auto_copy |
| 16 | CardWalletActivity | TYPE_LIST | "Dump Files N/M" | (none) | (none) | ListView: dump type categories (only non-empty shown) | 03_dump_files, v1090: 090-Dump-Types.png |
| 17 | CardWalletActivity | FILE_LIST | "Dump Files N/M" | "Details" | "Delete" | ListView: dump files sorted by ctime | 03_dump_files, v1090: 090-Dump-Types-Files.png |
| 18 | CardWalletActivity | DELETE_CONFIRM | "Dump Files N/M" | (Cancel) | (Confirm) | Toast: "Delete?" | 03_dump_files |
| 19 | CardWalletActivity | TAG_INFO | "Tag Info" | "Simulate" | "Write" | Tag info panel (parsed from dump file) | 03_dump_files, v1090: 090-Dump-Types-Files-Info.png |
| 20 | CardWalletActivity | DATA_READY | "Data ready!" | "Watch" | "Write" | "Data ready for copy!\nPlease place new tag..." + TYPE | 03_dump_files, v1090: 090-Dump-Types-Files-Info-Write.png |
| 21 | ScanActivity | IDLE (type select) | "Scan Tag N/M" | (none) | (none) | ListView: 31+ tag types, 5/page, paginated | 04_scan_tag |
| 22 | ScanActivity | SCANNING | "Scan Tag" | (none) | (none) | ProgressBar "Scanning..." | 04_scan_tag |
| 23 | ScanActivity | FOUND | "Scan Tag" | "Rescan" | (context) | Toast: "Tag Found" + tag info | 04_scan_tag |
| 24 | ScanActivity | NOT_FOUND | "Scan Tag" | "Rescan" | (none) | Toast: "No tag found" | 04_scan_tag |
| 25 | ScanActivity | WRONG_TYPE | "Scan Tag" | "Rescan" | (none) | Toast: "No tag found Or Wrong type found!" | 04_scan_tag |
| 26 | ScanActivity | MULTI | "Scan Tag" | "Rescan" | (none) | Toast: "Multiple tags detected!" | 04_scan_tag |
| 27 | ReadListActivity | LIST | "Read Tag N/M" | (none) | (none) | ListView: 40 readable types, 5/page, 8 pages | 05_read_tag, FB: read_mf1k_4b/0050.png |
| 28 | ReadActivity | SCANNING | "Read Tag" | (none) | (none) | ProgressBar "Scanning..." | 05_read_tag, FB: read_mf1k_4b/0070.png |
| 29 | ReadActivity | TAG_FOUND_READING | "Read Tag" | (none) | (none) | Tag info + "Reading..." | 05_read_tag, FB: read_mf1k_4b/0090.png |
| 30 | ReadActivity | KEY_CHECKING | "Read Tag" | (none) | (none) | Tag info + timer + "ChkDIC...N/Mkeys" | 05_read_tag, FB: read_mf1k_4b/0100.png |
| 31 | ReadActivity | READING_KEYS | "Read Tag" | (none) | (none) | Tag info + "Reading...N/MKeys" | 05_read_tag, FB: read_mf1k_4b/0110.png |
| 32 | ReadActivity | READ_SUCCESS | "Read Tag" | "Reread" | "Write" | Toast: "Read Successful! File saved" | 05_read_tag, FB: read_mf1k_4b/0200.png |
| 33 | ReadActivity | READ_SUCCESS_PARTIAL | "Read Tag" | "Reread" | "Write" | Toast: "Read Successful! Partial data saved" | 05_read_tag |
| 34 | ReadActivity | READ_FAILED | "Read Tag" | "Reread" | (none) | Toast: "Read Failed!" | 05_read_tag |
| 35 | ReadActivity | NO_TAG_FOUND | "Read Tag" | "Rescan" | (none) | Toast: "No tag found Or Wrong type found!" | 05_read_tag |
| 36 | WarningM1Activity | PAGE_0 (Sniff) | "Missing keys" | "Cancel" | "Sniff" | Option 1) sniff keys / Option 2) enter keys | 05_read_tag |
| 37 | WarningM1Activity | PAGE_1 (Enter) | "Missing keys" | "Cancel" | "Enter" | Option 1) sniff keys / Option 2) enter keys | 05_read_tag |
| 38 | WarningM1Activity | PAGE_2 (Force) | "Missing keys" | "Cancel" | "Force" | Option 3) force read / Option 4) PC mode hardnested | 05_read_tag |
| 39 | WarningM1Activity | PAGE_3 (PC-M) | "Missing keys" | "Cancel" | "PC-M" | Option 3) force read / Option 4) PC mode hardnested | 05_read_tag |
| 40 | KeyEnterM1Activity | KEY_ENTRY | "Key Enter" | "Cancel" | "Enter" | InputMethods: 12-char hex key input | 05_read_tag |
| 41 | SniffActivity | TYPE_SELECT | "Sniff TRF 1/1" | (none) | (none) | ListView: 5 sniff types (14A, 14B, iClass, Topaz, T5577) | 06_sniff, sniff_trf_list_1_1.png |
| 42 | SniffActivity | INSTRUCTION (HF) | "Sniff TRF N/4" | "Start" | "Finish" | 4-step instruction text (one step per page) | 06_sniff, sniff_trf_1_4_1.png |
| 43 | SniffActivity | INSTRUCTION (T5577) | "Sniff TRF" | "Start" | "Finish" | T5577 instruction text | 06_sniff |
| 44 | SniffActivity | SNIFFING | "Sniff TRF N/4" | "Start" | "Finish" | Toast: "Sniffing in progress..." overlaid on instruction text | 06_sniff, sniff_trf_sniffing.png |
| 45 | SniffActivity | RESULT | "Sniff TRF" | "Start" | "Save" | Console/trace data + "TraceLen: N" | 06_sniff, sniff_trf_1_4_2.png |
| 46 | SniffForMfReadActivity | (directed) | "Sniff TRF" | varies | varies | Directed HF sniff for MIFARE key recovery | 06_sniff |
| 47 | SniffForT5XReadActivity | (directed) | "Sniff TRF" | varies | varies | Directed LF sniff for T5577 password | 06_sniff |
| 48 | SimulationActivity | TYPE_SELECT | "Simulation N/M" | (none) | (none) | ListView: 16 sim types, 5/page, 4 pages. No button labels. | 07_simulation, simulation_list_1_4.png |
| 49 | SimulationActivity | SIM_UI | "Simulation" | "Stop" | "Start" | Per-type input fields (UID/FC/CN/etc) | 07_simulation, simulation_detail_1.png |
| 50 | SimulationActivity | SIMULATING | "Simulation" | "Stop" | "Start" | Toast: "Simulation in progress..." | 07_simulation, simulation_in_progress.png |
| 51 | SimulationTraceActivity | DISPLAY | "Trace" | "Back" | "Save" | BigTextListView: trace data | 07_simulation |
| 52 | PCModeActivity | IDLE | "PC-Mode" | "Start" | "Start" | Tips: "Please connect to the computer..." | 08_pcmode, pc_mode.png |
| 53 | PCModeActivity | STARTING | "PC-Mode" | (disabled) | (disabled) | Toast: "Processing..." | 08_pcmode |
| 54 | PCModeActivity | RUNNING | "PC-Mode" | "Stop" | "Button" | Toast: "PC-mode Running..." | 08_pcmode |
| 55 | PCModeActivity | STOPPING | "PC-Mode" | (disabled) | (disabled) | Teardown in progress | 08_pcmode |
| 56 | DiagnosisActivity | MAIN | "Diagnosis" | (none) | (none) | ListView: "User diagnosis" / "Factory diagnosis" | 09_diagnosis |
| 57 | DiagnosisActivity | TEST_LIST | "Diagnosis" | "Cancel" | "Start" | CheckedListView: 9 test items, pass/fail indicators | 09_diagnosis, diagnosis_menu_2.png |
| 58 | DiagnosisActivity | RESULTS | "Diagnosis 1/1" | (none) | (none) | CheckedListView: test results with checkmarks and values | 09_diagnosis, diagnosis_results_1_1.png |
| 59 | ScreenTestActivity | TIPS | "Diagnosis" | (none) | (none) | Tips: "Press OK to start test..." | 09_diagnosis |
| 60 | ScreenTestActivity | COLOR_TEST | (none) | (none) | (none) | Full-screen solid color (cycling) | 09_diagnosis |
| 61 | ScreenTestActivity | CONFIRMATION | "Diagnosis" | "Pass" | "Fail" | "Is the screen OK?" | 09_diagnosis |
| 62 | ButtonTestActivity | BUTTON_TEST | "Diagnosis" | (none) | (none) | Button layout with indicators; press all 6 to pass | 09_diagnosis |
| 63 | SoundTestActivity | PLAYING | "Diagnosis" | "Pass" | "Fail" | "Do you hear the music?" | 09_diagnosis |
| 64 | HFReaderTestActivity | TIPS | "Diagnosis" | "Start" | (none) | "Please place Tag with IC Test" | 09_diagnosis |
| 65 | HFReaderTestActivity | TESTING | "Diagnosis" | (none) | (none) | PM3 HF reader test in progress | 09_diagnosis |
| 66 | LfReaderTestActivity | TIPS | "Diagnosis" | "Start" | (none) | "Please place Tag with ID Test" | 09_diagnosis |
| 67 | LfReaderTestActivity | TESTING | "Diagnosis" | (none) | (none) | PM3 LF reader test in progress | 09_diagnosis |
| 68 | UsbPortTestActivity | CHARGER_TEST | "Diagnosis" | "Pass" | "Fail" | "Please connect to charger." | 09_diagnosis |
| 69 | UsbPortTestActivity | USB_SERIAL_TEST | "Diagnosis" | "Pass" | "Fail" | "Does computer have USBSerial found?" | 09_diagnosis |
| 70 | UsbPortTestActivity | OTG_TEST | "Diagnosis" | "Pass" | "Fail" | "Connect to OTG tester..." | 09_diagnosis |
| 71 | BacklightActivity | SETTINGS | "Backlight" | (none) | (none) | CheckedListView: Low / Middle / High (3 items) | 10_backlight |
| 72 | VolumeActivity | SETTINGS | "Volume" | (none) | (none) | CheckedListView: Off / Low / Middle / High (4 items) | 11_volume |
| 73 | AboutActivity | INFO_DISPLAY (pg 1) | "About 1/2" | (none) | (none) | 6-line version info: iCopy-XS, HW, HMI, OS, PM, SN | 12_about, about_1_2.png |
| 74 | AboutActivity | INFO_DISPLAY (pg 2) | "About 2/2" | (none) | (none) | Firmware update instructions (5 lines) | 12_about, about_2_2.png |
| 75 | AboutActivity | UPDATE_AVAILABLE | "About" | (none) | (none) | Firmware update instructions (conditional per checkUpdate) | 12_about |
| 76 | WipeTagActivity | TYPE_SELECT | "Erase Tag" | (none) | (none) | ListView: "Erase MF1/L1/L2/L3" / "Erase T5577" | 13_erase_tag, v1090: 090-Erase-Types.png |
| 77 | WipeTagActivity | SCANNING | "Erase Tag" | (none) | (none) | ProgressBar "Scanning..." | 13_erase_tag, erase_tag_menu_2.png |
| 78 | WipeTagActivity | ERASING | "Erase Tag" | "Erase" | "Erase" | ProgressBar "ChkDIC" / "Erasing N%" / block progress | 13_erase_tag, erase_tag_menu_3-5.png |
| 79 | WipeTagActivity | RESULT_SUCCESS | "Erase Tag" | (none) | (none) | Toast: "Erase successful" | 13_erase_tag |
| 80 | WipeTagActivity | RESULT_FAIL | "Erase Tag" | "Erase" | "Erase" | Toast: "Erase failed" or "No tag found" | 13_erase_tag, v1090: 090-Erase-Types-Erase-Failed.png |
| 81 | WipeTagActivity | NO_KEYS | "Erase Tag" | (none) | (none) | Toast: "No valid keys, Please use Auto Copy first..." | 13_erase_tag |
| 82 | TimeSyncActivity | DISPLAY_MODE | "Time Settings" | "Edit" | "Edit" | InputMethodList: YYYY-MM-DD HH:MM:SS (read-only) | 14_time_settings, v1090: 090-Time.png |
| 83 | TimeSyncActivity | EDIT_MODE | "Time Settings" | "Cancel" | "Save" | InputMethodList: editable fields with arrows | 14_time_settings, v1090: 090-Time-Select.png |
| 84 | LUAScriptCMDActivity | FILE_LIST | "LUA Script N/M" | (none) | (none) | ListView: .lua scripts, paginated. No button bar. | 15_lua_script, lua_script_1_10.png |
| 85 | ConsolePrinterActivity | RUNNING | (full-screen) | "Cancel" | (none) | Full-screen monospace console (cyan/green on black). No title bar. | 15_lua_script, lua_console_1-10.png |
| 86 | ConsolePrinterActivity | COMPLETE | (full-screen) | "Cancel" | "OK" | Full-screen monospace console (finished) | 15_lua_script |
| 87 | WarningWriteActivity | DATA_READY | "Data ready!" | "Cancel"/"Watch" | "Write" | "Data ready for copy!" + TYPE + tag short name | 16_write_tag, FB: Step - 3.png |
| 88 | WriteActivity | IDLE | "Write Tag" | "Write" | "Verify" | Tag info panel | 16_write_tag |
| 89 | WriteActivity | WRITING | "Write Tag" | (disabled) | (disabled) | "Writing..." + progress bar | 16_write_tag, FB: Step - 4.png |
| 90 | WriteActivity | WRITE_SUCCESS | "Write Tag" | "Verify" | "Rewrite" | Toast: "Write successful!" | 16_write_tag, autocopy_mf1k_gen1a/0800.png |
| 91 | WriteActivity | WRITE_FAILED | "Write Tag" | "Verify" | "Rewrite" | Toast: "Write failed!" | 16_write_tag, FB: Step - 5.png, write_tag_write_failed.png |
| 92 | WriteActivity | VERIFYING | "Write Tag" | (disabled) | (disabled) | "Verifying..." + progress bar | 16_write_tag |
| 93 | WriteActivity | VERIFY_SUCCESS | "Write Tag" | "Verify" | "Rewrite" | Toast: "Verification successful!" | 16_write_tag |
| 94 | WriteActivity | VERIFY_FAILED | "Write Tag" | "Verify" | "Rewrite" | Toast: "Verification failed!" | 16_write_tag |
| 95 | SnakeGameActivity | IDLE | "Greedy Snake" | (none) | (none) | Toast: "Press OK to start game." | 17_secondary |
| 96 | SnakeGameActivity | PLAYING | "Greedy Snake" | (none) | (none) | Snake game grid | 17_secondary |
| 97 | SnakeGameActivity | PAUSED | "Greedy Snake" | (none) | (none) | Toast: "Pausing" | 17_secondary |
| 98 | SnakeGameActivity | GAME_OVER | "Greedy Snake" | (none) | (none) | Toast: "Game Over" | 17_secondary |
| 99 | SnakeGameActivity | WIN | "Greedy Snake" | (none) | (none) | Toast: "You win" | 17_secondary |
| 100 | WearableDeviceActivity | STEP1 | "Watch" | "Start" | (none) | "1. Copy UID..." tips | 17_secondary |
| 101 | WearableDeviceActivity | STEP2 | "Watch" | "Finish" | (none) | "2. Record UID..." tips | 17_secondary |
| 102 | WearableDeviceActivity | STEP3 | "Watch" | "Start" | (none) | "3. Write data..." tips | 17_secondary |
| 103 | IClassSEActivity | WAITING | "SE Decoder" | (none) | (none) | "Please place iClass SE tag on USB decoder..." | 17_secondary |
| 104 | IClassSEActivity | READING | "SE Decoder" | (none) | (none) | SE decoder read in progress | 17_secondary |
| 105 | IClassSEActivity | COMPLETE | "SE Decoder" | (none) | (none) | Read data display | 17_secondary |
| 106 | WarningT5X4X05KeyEnterActivity | KEY_ENTRY | "Key Enter"/"No valid key" | "Enter" | "Cancel" | Hex key input for T5577/EM4305 | 17_secondary |
| 107 | OTAActivity | BATTERY_CHECK | "Update" | (none) | (none) | Battery level check | 17_secondary |
| 108 | OTAActivity | UPDATE_CONFIRM | "Update" | "Start" | (none) | "Do you want to start the update?" | 17_secondary |
| 109 | OTAActivity | UPDATING | "Update" | (disabled) | (disabled) | "Updating..." progress bar | 17_secondary |
| 110 | OTAActivity | UPDATE_COMPLETE | "Update" | (none) | (none) | "The update is successful." or install failure | 17_secondary |
| 111 | WarningDiskFullActivity | WARNING | "Disk Full" | "Clear" | (none) | "The disk space is full. Please clear it after backup." | 17_secondary |
| 112 | SleepModeActivity | SLEEPING | (none) | (none) | (none) | Screen off / blank | 17_secondary |
| 113 | AutoExceptCatchActivity | ERROR_DISPLAY | (none) | "Save" | (none) | Exception/crash info | 17_secondary |

**Total: 113 distinct screen states**

---

## Section 2: Activity Index

| # | Activity Class | Module (.so) | Menu Pos | Doc Path | State Count |
|---|---------------|-------------|----------|----------|-------------|
| 1 | MainActivity | actmain.so | -- | 01_main_menu/ | 1 |
| 2 | AutoCopyActivity | activity_main.so | 0 | 02_auto_copy/ | 14 |
| 3 | CardWalletActivity | activity_main.so | 1 | 03_dump_files/ | 5 |
| 4 | ScanActivity | activity_main.so | 2 | 04_scan_tag/ | 6 |
| 5 | ReadListActivity | activity_main.so | 3 (Read Tag) | 05_read_tag/ | 1 |
| 6 | ReadActivity | activity_main.so | (sub) | 05_read_tag/ | 9 |
| 7 | WarningM1Activity | activity_main.so | (sub) | 05_read_tag/ | 4 |
| 8 | KeyEnterM1Activity | activity_main.so | (sub) | 05_read_tag/ | 1 |
| 9 | SniffActivity | activity_main.so | 4 | 06_sniff/ | 5 |
| 10 | SniffForSpecificTag | activity_main.so | (sub) | 06_sniff/ | 1 |
| 11 | SniffForMfReadActivity | activity_main.so | (sub) | 06_sniff/ | 1 |
| 12 | SniffForT5XReadActivity | activity_main.so | (sub) | 06_sniff/ | 1 |
| 13 | SimulationActivity | activity_main.so | 5 | 07_simulation/ | 3 |
| 14 | SimulationTraceActivity | activity_main.so | (sub) | 07_simulation/ | 1 |
| 15 | PCModeActivity | activity_main.so | 6 | 08_pcmode/ | 4 |
| 16 | DiagnosisActivity | activity_tools.so | 7 | 09_diagnosis/ | 3 |
| 17 | ScreenTestActivity | activity_tools.so | (sub) | 09_diagnosis/ | 3 |
| 18 | ButtonTestActivity | activity_tools.so | (sub) | 09_diagnosis/ | 1 |
| 19 | SoundTestActivity | activity_tools.so | (sub) | 09_diagnosis/ | 1 |
| 20 | HFReaderTestActivity | activity_tools.so | (sub) | 09_diagnosis/ | 2 |
| 21 | LfReaderTestActivity | activity_tools.so | (sub) | 09_diagnosis/ | 2 |
| 22 | UsbPortTestActivity | activity_tools.so | (sub) | 09_diagnosis/ | 3 |
| 23 | BacklightActivity | activity_main.so | 8 | 10_backlight/ | 1 |
| 24 | VolumeActivity | activity_main.so | 9 | 11_volume/ | 1 |
| 25 | AboutActivity | activity_main.so | 10 | 12_about/ | 3 |
| 26 | WipeTagActivity | activity_main.so | 11 | 13_erase_tag/ | 6 |
| 27 | TimeSyncActivity | activity_main.so | 12 | 14_time_settings/ | 2 |
| 28 | LUAScriptCMDActivity | activity_main.so | 13 | 15_lua_script/ | 1 |
| 29 | ConsolePrinterActivity | activity_main.so | (sub) | 15_lua_script/ | 2 |
| 30 | WarningWriteActivity | activity_main.so | (sub) | 16_write_tag/ | 1 |
| 31 | WriteActivity | activity_main.so | (sub) | 16_write_tag/ | 7 |
| 32 | SnakeGameActivity | activity_main.so | (hidden) | 17_secondary/ | 5 |
| 33 | WearableDeviceActivity | activity_main.so | (sub) | 17_secondary/ | 3 |
| 34 | ReadFromHistoryActivity | activity_main.so | (sub) | 17_secondary/ | 2 |
| 35 | IClassSEActivity | activity_main.so | (sub) | 17_secondary/ | 3 |
| 36 | AutoExceptCatchActivity | activity_main.so | (system) | 17_secondary/ | 1 |
| 37 | OTAActivity | actmain.so | (sub) | 17_secondary/ | 4 |
| 38 | SleepModeActivity | actmain.so | (system) | 17_secondary/ | 1 |
| 39 | WarningDiskFullActivity | actmain.so | (system) | 17_secondary/ | 1 |
| 40 | WarningT5X4X05KeyEnterActivity | activity_main.so | (sub) | 17_secondary/ | 1 |

### Main Menu Items (14 total, 3 pages of 5+5+4)

| Position | Item Name      | Activity Class       | Page |
|----------|----------------|----------------------|------|
| 0        | Auto Copy      | AutoCopyActivity     | 1    |
| 1        | Dump Files     | CardWalletActivity   | 1    |
| 2        | Scan Tag       | ScanActivity         | 1    |
| 3        | Read Tag       | ReadActivity         | 1    |
| 4        | Sniff TRF      | SniffActivity        | 1    |
| 5        | Simulation     | SimulationActivity   | 2    |
| 6        | PC-Mode        | PCModeActivity       | 2    |
| 7        | Diagnosis      | DiagnosisActivity    | 2    |
| 8        | Backlight      | BacklightActivity    | 2    |
| 9        | Volume         | VolumeActivity       | 2    |
| 10       | About          | AboutActivity        | 3    |
| 11       | Erase Tag      | WipeTagActivity      | 3    |
| 12       | Time Settings  | TimeSyncActivity     | 3    |
| 13       | LUA Script     | LUAScriptCMDActivity | 3    |

**Citations:** `main_page_1_3_1.png` (page 1), `main_page_2_3_1.png` (page 2: Simulation, PC-Mode, Diagnosis, Backlight, Volume), `main_page_3_3_1.png` (page 3). Note: "Write Tag" does NOT appear as a main menu item. WriteActivity is launched as a sub-activity from Read/AutoCopy/Dump flows.

---

## Section 3: Framework Summary

### 3.1 Screen Zones (240x240 LCD)

| Zone | Rectangle | Height | Background |
|------|----------|--------|------------|
| Title bar | (0,0)-(240,40) | 40px | #788098 (hardware measured) / #222222 (code) |
| Content area | (0,40)-(240,200) | 160px (with buttons) / 200px (without) | white (#f8fcf8 measured) |
| Button bar | (0,200)-(240,240) | 40px | #222222 (#202020 measured) |

### 3.2 Fonts

| Element | Font | Source |
|---------|------|--------|
| Title text | Consolas 18 | actbase_ghidra_raw.txt STR@0x0001fed4 |
| Button text | mononoki 16 | actbase_ghidra_raw.txt STR@0x0001feac |
| Content text | mononoki (varies by widget) | widget.so |

### 3.3 ListView Widget

| Parameter | Value | Source |
|-----------|-------|--------|
| Items per page | 5 | Measured from screenshots (0000.png, 0050.png) |
| Item height | ~40-41px | 204px content / 5 items |
| Selection highlight | Full-width dark rectangle (~RGB 100,100,120) | Measured from 0000.png |
| Page indicator | Numeric "N/M" embedded in title string | Screenshots: "Main Page 1/3", "Read Tag 1/8" |

### 3.4 CheckedListView Widget

| Parameter | Value | Source |
|-----------|-------|--------|
| Inherits from | ListView | widget_ghidra_raw.txt class structure |
| Items per page | 5 (inherited) | Same as ListView |
| Check indicator position | RIGHT side of each item row | backlight_1-5.png, volume_1-6.png |
| Unchecked state | Grey-stroked square outline (border only, no fill) | backlight_1-5.png, volume_1-6.png |
| Checked state | Blue-stroked square outline + inner blue-filled square | backlight_1-5.png, volume_1-6.png |
| Check state storage | Item tuple index [1] | widget_ghidra_raw.txt line 75487 |

**Note:** The CheckedListView check indicator is NOT a green checkmark on the left. It is a two-part fillsquare rendering on the RIGHT side: one HMI call for the border stroke (grey for unchecked, blue for checked), and one HMI call for the inner fill (present only for checked items).

### 3.5 Toast Overlay

| Parameter | Value | Source |
|-----------|-------|--------|
| Position | Centered overlay on content area | Screenshots |
| Background | Semi-transparent dark | Screenshots |
| Icon | Checkmark (success) or X (failure) | Screenshots |
| Dismiss | TOAST_CANCEL (canvas mask deletion) | reference_toast_dismiss.md |

### 3.6 ProgressBar

| Parameter | Value | Source |
|-----------|-------|--------|
| Position | Bottom of content area | Screenshots |
| Fill color | Blue | FB captures |
| Text | Above progress bar | Screenshots |

### 3.7 Battery Icon

| Parameter | Value | Source |
|-----------|-------|--------|
| Position | Upper-right title bar, ~x=207-232, y=14-27 | Measured from 0000.png |
| Shape | Rectangular outline with fill bars + terminal nub | Screenshots |
| Module | batteryui.so (BatteryBar class) | actbase decompiled |

---

## Section 4: Known Corrections (Post-Adversarial Audit)

These corrections were found during ground-truth analysis and adversarial screenshot audit. Each correction lists what was wrong and what the corrected value is.

### 4.1 Items Per Page: 5, NOT 4

- **Before (old docs):** Some references stated "4 items per page" for ListViews
- **After (corrected):** 5 items per page, confirmed by EVERY framebuffer capture showing 5 items
- **Evidence:** read_mf1k_4b/0000.png shows 5 main menu items; read_mf1k_4b/0050.png shows 5 read tag types; sub_05_simulation.png shows 5 simulation types

### 4.2 Page Indicator: In Title String, NOT Separate Widget

- **Before (old docs):** Page indicator described as a separate widget at a fixed position
- **After (corrected):** Page indicator is part of the title text, formatted as "Title N/M" in a single setTitle() call
- **Evidence:** Screenshots show "Main Page 1/3", "Read Tag 1/8", "Simulation 1/4" with page numbers visually continuous with title text

### 4.3 Button Labels: NO "OK" Buttons on Screen

- **Before (old docs):** Some descriptions referenced visible "OK" buttons
- **After (corrected):** No activity shows "OK" as a visible button label on screen. The physical OK key exists but has no on-screen label. Button labels are context-specific (Write, Verify, Start, etc.)
- **Evidence:** All screenshots examined show either empty button bar or specific action labels, never "OK"

### 4.4 Settings Save Key: OK, NOT M2

- **Before (old docs):** Some references stated M2 saves settings
- **After (corrected):** On CheckedListView settings screens (Backlight, Volume), OK key saves and M1/M2 have NO action
- **Evidence:** feedback_settings_ok_key.md: "Settings save key is OK, not M2. M1/M2 have no action on CheckedListView settings screens"

### 4.5 Title Bar Background Color

- **Before (old docs/code):** Title bar color is #222222 (from binary string literal)
- **After (corrected):** Real hardware renders #788098 (measured from framebuffer captures). The #222222 is the canvas fill color in the tkinter development environment; the STM32 HMI MCU renders differently.
- **Evidence:** Pixel measurement from framebuffer_captures/read_mf1k_4b/0000.png shows rgb(120,128,152)

### 4.6 Button Bar Background Color

- **Before (old docs/code):** Button bar color is #222222
- **After (corrected):** Real hardware renders #202020 (measured). Within LCD RGB565 quantization tolerance of #222222.
- **Evidence:** Pixel measurement from framebuffer_captures/read_mf1k_4b/0084.png shows rgb(32,32,32)

### 4.7 Write Activity Post-Operation Buttons: SAME for Success and Failure

- **Before (old docs):** After write failure, buttons were described as opposite order from write success
- **After (corrected):** After ANY write or verify operation (success or failure), button labels are always M1(left)="Verify", M2(right)="Rewrite"
- **Evidence:** autocopy_mf1k_gen1a/0800.png (success) and Step - 5.png (failure) and write_tag_write_failed.png (failure) all show "Verify" left, "Rewrite" right

### 4.8 Main Menu: No "Write Tag" Item; Diagnosis at Position 7

- **Before (old docs):** Write Tag listed as menu item at position 5; Diagnosis described as "hidden"
- **After (corrected):** Write Tag does NOT appear in the main menu. Page 2 order is: Simulation (5), PC-Mode (6), Diagnosis (7), Backlight (8), Volume (9). 14 total items across 3 pages (5+5+4).
- **Evidence:** `main_page_2_3_1.png` shows page 2 with Simulation, PC-Mode, Diagnosis, Backlight, Volume. Test infrastructure: `backlight_common.sh` line 42 `BACKLIGHT_MENU_POS=8`, `volume_common.sh` line 49 `VOLUME_MENU_POS=9`.

### 4.9 Simulation Buttons: "Stop"/"Start", NOT "Edit"/"Simulate"

- **Before (old docs/master chart):** SIM_UI state described M1="Edit", M2="Simulate"
- **After (corrected):** SIM_UI and SIMULATING states both show M1="Stop" (left), M2="Start" (right). Button labels do not change between SIM_UI and SIMULATING states.
- **Evidence:** `simulation_detail_1.png` (SIM_UI) and `simulation_in_progress.png` (SIMULATING) both show M1="Stop", M2="Start"

### 4.10 Sniff Activity Button Labels: "Start"/"Finish" (not "Stop")

- **Before (old docs/master chart):** SNIFFING state described M1="Stop"/"Finish", RESULT described M1="Save"
- **After (corrected):**
  - INSTRUCTION: M1="Start", M2="Finish" (both visible on all pages)
  - SNIFFING: M1="Start" (unchanged from instruction), M2="Finish"
  - RESULT: M1="Start", M2="Save"
- **Evidence:** `sniff_trf_1_4_1.png` through `sniff_trf_4_4.png` (instruction pages), `sniff_trf_sniffing.png` (sniffing state), `sniff_trf_1_4_2.png` (result)

### 4.11 About Activity: 2 Pages with Page Indicator

- **Before (old docs/master chart):** About described as single-page with no pagination
- **After (corrected):** About has 2 pages. Title shows "About 1/2" (device info) and "About 2/2" (firmware update instructions). First line is device name "iCopy-XS" (not a version with "v" prefix).
- **Evidence:** `about_1_2.png` (page 1: iCopy-XS, HW 1.7, HMI 1.4, OS 1.0.90, PM 3.1, SN 02150004), `about_2_2.png` (page 2: firmware update instructions)

### 4.12 Diagnosis TEST_LIST Buttons: M1="Cancel", M2="Start"

- **Before (old docs/master chart):** TEST_LIST described M1="Start", M2=(none)
- **After (corrected):** M1="Cancel" (left), M2="Start" (right)
- **Evidence:** `diagnosis_menu_2.png` clearly shows "Cancel" on left and "Start" on right

### 4.13 Diagnosis RESULTS State Added

- **Before (old docs/master chart):** RESULTS state not separately documented
- **After (corrected):** RESULTS state shows "Diagnosis 1/1" title, CheckedListView with pass checkmarks and measured values (e.g., "HF Voltage : (37V)")
- **Evidence:** `diagnosis_results_1_1.png`

### 4.14 LUA Script File List: No Button Bar

- **Before (old docs/master chart):** FILE_LIST described M2="OK"
- **After (corrected):** No button bar visible. List occupies full content area.
- **Evidence:** `lua_script_1_10.png` and `lua_script_10_10.png` show no button bar

### 4.15 Console Printer: Full-Screen, No Title Bar

- **Before (old docs):** ConsolePrinterActivity described with title bar from bundle
- **After (corrected):** Console is full-screen with NO title bar and NO buttons visible during execution. Cyan/green monospace text on black background.
- **Evidence:** `lua_console_1.png` through `lua_console_10.png`

### 4.16 CheckedListView Indicator: Two-Part Rendering

- **Before (old docs/framework):** Check indicator described generically as "filled square/rectangle"
- **After (corrected):** Two-part rendering on RIGHT side: unchecked = grey-stroked square outline (border only); checked = blue-stroked square outline + inner blue-filled square. NOT a green checkmark on the left.
- **Evidence:** `backlight_1.png` through `backlight_5.png`, `volume_1.png` through `volume_6.png`

### 4.17 Sniff TYPE_SELECT Title: Includes Page Indicator

- **Before (old docs):** TYPE_SELECT title shown as just "Sniff TRF"
- **After (corrected):** Title includes page indicator: "Sniff TRF 1/1" (5 items fit on one page)
- **Evidence:** `sniff_trf_list_1_1.png`

### 4.18 Sniff INSTRUCTION Titles: Include Step Page Indicator

- **Before (old docs):** INSTRUCTION title shown as "Sniff TRF"
- **After (corrected):** INSTRUCTION titles include page indicator: "Sniff TRF 1/4" through "Sniff TRF 4/4"
- **Evidence:** `sniff_trf_1_4_1.png`, `sniff_trf_2_4.png`, `sniff_trf_3_4.png`, `sniff_trf_4_4.png`

### 4.19 Erase SCANNING and ERASING States: Screenshot Evidence Added

- **Before:** SCANNING/ERASING states had no screenshot citations
- **After:** Added citations for ProgressBar position, ChkDIC dictionary check phase, "Erasing N%" progress
- **Evidence:** `erase_tag_menu_2.png` (scanning), `erase_tag_menu_3.png` (ChkDIC), `erase_tag_menu_4-5.png` (Erasing 0%), `erase_tag_menu_6.png` (post-erase buttons)

---

## Section 5: Screenshot Coverage Map

### Activities WITH framebuffer/screenshot evidence:

| Activity | State(s) Captured | Source |
|----------|-------------------|--------|
| MainActivity | IDLE (pages 1-3) | main_page_1_3_1.png, main_page_2_3_1.png, main_page_3_3_1.png, read_mf1k_4b/0000.png, v1090: 090-Home-Dump.png, 090-Home-Page3.png |
| AutoCopyActivity | SCANNING, TAG_FOUND, KEY_CRACK, READ_SUCCESS, DATA_READY, WRITING, WRITE_SUCCESS | autocopy_mf1k_gen1a/ series (0249-0762) |
| AutoCopyActivity | NO_TAG_FOUND | ref: sub_00_auto_copy.png |
| CardWalletActivity | TYPE_LIST, FILE_LIST, TAG_INFO, DATA_READY | v1090: 090-Dump-Types*.png series |
| ReadListActivity | LIST (pages 1-4) | read_mf1k_4b/0050.png, read_ultralight_ev1/0000.png, etc. |
| ReadActivity | SCANNING, TAG_FOUND, KEY_CHECK, READING, READ_SUCCESS | read_mf1k_4b/ series, read_mf1k_nested/ series |
| SniffActivity | TYPE_SELECT, INSTRUCTION (all 4 pages), SNIFFING, RESULT | sniff_trf_list_1_1.png, sniff_trf_1_4_1.png-4_4.png, sniff_trf_sniffing.png, sniff_trf_1_4_2.png |
| SimulationActivity | TYPE_SELECT, SIM_UI, SIMULATING | simulation_list_1_4.png, simulation_detail_1.png, simulation_in_progress.png, ref: sub_05_simulation.png |
| PCModeActivity | IDLE | pc_mode.png |
| DiagnosisActivity | TEST_LIST, RESULTS, testing states | diagnosis_menu_2-6.png, diagnosis_results_1_1.png |
| BacklightActivity | SETTINGS (all items) | backlight_1.png - backlight_5.png |
| VolumeActivity | SETTINGS (all items) | volume_1.png - volume_6.png |
| AboutActivity | INFO_DISPLAY (both pages) | about_1_2.png, about_2_2.png |
| WipeTagActivity | TYPE_SELECT, SCANNING, ERASING, RESULT_FAIL | v1090: 090-Erase-Types*.png, erase_tag_menu_1-6.png, erase_tag_scanning.png |
| TimeSyncActivity | DISPLAY_MODE, EDIT_MODE, sync sequence | v1090: 090-Time*.png, time_settings_1-10.png, time_settings_sync_1-4.png |
| LUAScriptCMDActivity | FILE_LIST | v1090: 090-Lua.png, ref: sub_13_lua_script.png, lua_script_1_10.png, lua_script_10_10.png |
| ConsolePrinterActivity | RUNNING/COMPLETE | v1090: 090-Lua-Resullts.png, lua_console_1-10.png |
| WarningWriteActivity | DATA_READY | FB: Step - 3.png |
| WriteActivity | WRITING, WRITE_FAILED, WRITE_SUCCESS | FB: Step - 4.png, Step - 5.png, write_tag_write_failed.png, autocopy_mf1k_gen1a/0800.png |

### Activities with DECOMPILED-CODE-ONLY evidence (no screenshots):

| Activity | Notes |
|----------|-------|
| ScanActivity | All states documented from decompiled binary only |
| WarningM1Activity | Documented from decompiled binary + resources.py keys |
| KeyEnterM1Activity | Documented from decompiled binary |
| SniffForSpecificTag / SniffForMfReadActivity / SniffForT5XReadActivity | Directed sniff variants, code-only |
| SimulationTraceActivity | Code-only |
| SnakeGameActivity | Code-only |
| WearableDeviceActivity | Code-only |
| IClassSEActivity | Code-only |
| OTAActivity | Code-only |
| SleepModeActivity | Code-only |
| WarningDiskFullActivity | Code-only |
| WarningT5X4X05KeyEnterActivity | Code-only |
| AutoExceptCatchActivity | Code-only |

---

## Section 6: String Resources Cross-Reference

### 6.1 StringEN.title Keys -- Coverage

| Key | Value | Referenced In Doc(s) | Status |
|-----|-------|---------------------|--------|
| main_page | "Main Page" | 01_main_menu | COVERED |
| auto_copy | "Auto Copy" | 02_auto_copy | COVERED |
| about | "About" | 12_about | COVERED |
| backlight | "Backlight" | 10_backlight | COVERED |
| key_enter | "Key Enter" | 05_read_tag, 17_secondary | COVERED |
| network | "Network" | -- | ORPHANED (no activity doc references it) |
| update | "Update" | 17_secondary (OTAActivity) | COVERED |
| pc-mode | "PC-Mode" | 08_pcmode | COVERED |
| read_tag | "Read Tag" | 05_read_tag | COVERED |
| scan_tag | "Scan Tag" | 04_scan_tag | COVERED |
| sniff_tag | "Sniff TRF" | 06_sniff | COVERED |
| sniff_notag | "Sniff TRF" | 06_sniff | COVERED |
| volume | "Volume" | 11_volume | COVERED |
| warning | "Warning" | -- | ORPHANED (no specific activity doc for generic warning) |
| missing_keys | "Missing keys" | 05_read_tag | COVERED |
| no_valid_key | "No valid key" | 17_secondary | COVERED |
| no_valid_key_t55xx | "No valid key" | 17_secondary | COVERED |
| data_ready | "Data ready!" | 02_auto_copy, 03_dump_files, 16_write_tag | COVERED |
| write_tag | "Write Tag" | 16_write_tag, 02_auto_copy | COVERED |
| disk_full | "Disk Full" | 17_secondary | COVERED |
| snakegame | "Greedy Snake" | 17_secondary | COVERED |
| trace | "Trace" | 07_simulation, 06_sniff | COVERED |
| simulation | "Simulation" | 07_simulation | COVERED |
| diagnosis | "Diagnosis" | 09_diagnosis | COVERED |
| wipe_tag | "Erase Tag" | 13_erase_tag | COVERED |
| time_sync | "Time Settings" | 14_time_settings | COVERED |
| se_decoder | "SE Decoder" | 17_secondary | COVERED |
| write_wearable | "Watch" | 17_secondary, 02_auto_copy | COVERED |
| card_wallet | "Dump Files" | 03_dump_files | COVERED |
| tag_info | "Tag Info" | 03_dump_files | COVERED |
| lua_script | "LUA Script" | 15_lua_script | COVERED |

**ORPHANED title keys:** `network`, `warning` (2 keys not referenced by any activity doc)

### 6.2 StringEN.button Keys -- Coverage

| Key | Value | Referenced In | Status |
|-----|-------|--------------|--------|
| button | "Button" | 08_pcmode | COVERED |
| read | "Read" | 04_scan_tag | COVERED |
| stop | "Stop" | 06_sniff, 07_simulation, 08_pcmode | COVERED |
| start | "Start" | 06_sniff, 08_pcmode, 09_diagnosis, 17_secondary | COVERED |
| reread | "Reread" | 02_auto_copy, 05_read_tag | COVERED |
| rescan | "Rescan" | 02_auto_copy, 04_scan_tag, 05_read_tag | COVERED |
| retry | "Retry" | -- | ORPHANED |
| sniff | "Sniff" | 05_read_tag (WarningM1) | COVERED |
| write | "Write" | 02_auto_copy, 03_dump_files, 16_write_tag | COVERED |
| simulate | "Simulate" | 03_dump_files | COVERED |
| finish | "Finish" | 06_sniff, 17_secondary | COVERED |
| save | "Save" | 06_sniff, 07_simulation, 14_time_settings | COVERED |
| enter | "Enter" | 05_read_tag, 17_secondary | COVERED |
| pc-m | "PC-M" | 05_read_tag (WarningM1), 08_pcmode | COVERED |
| cancel | "Cancel" | 09_diagnosis, 14_time_settings, 15_lua_script, 16_write_tag | COVERED |
| rewrite | "Rewrite" | 02_auto_copy, 16_write_tag | COVERED |
| force | "Force" | 05_read_tag (WarningM1) | COVERED |
| verify | "Verify" | 02_auto_copy, 16_write_tag | COVERED |
| forceuse | "Force-Use" | -- | ORPHANED |
| clear | "Clear" | 17_secondary (WarningDiskFull) | COVERED |
| shutdown | "Shutdown" | -- | ORPHANED |
| yes | "Yes" | -- | ORPHANED |
| no | "No" | -- | ORPHANED |
| fail | "Fail" | 09_diagnosis | COVERED |
| pass | "Pass" | 09_diagnosis | COVERED |
| save_log | "Save" | 17_secondary (AutoExceptCatch) | COVERED |
| wipe | "Erase" | 13_erase_tag | COVERED |
| edit | "Edit" | 14_time_settings | COVERED |
| delete | "Delete" | 03_dump_files | COVERED |
| details | "Details" | 03_dump_files | COVERED |

**ORPHANED button keys:** `retry`, `forceuse`, `shutdown`, `yes`, `no` (5 keys)

### 6.3 StringEN.toastmsg Keys -- Coverage

| Key | Value | Referenced In | Status |
|-----|-------|--------------|--------|
| update_finish | "Update finish." | 12_about | COVERED |
| update_unavailable | "No update available" | 12_about | COVERED |
| pcmode_running | "PC-mode Running..." | 08_pcmode | COVERED |
| read_ok_2 | "Read Successful! Partial..." | 05_read_tag | COVERED |
| read_ok_1 | "Read Successful! File saved" | 02_auto_copy, 05_read_tag | COVERED |
| read_failed | "Read Failed!" | 02_auto_copy, 05_read_tag | COVERED |
| no_tag_found2 | "No tag found Or Wrong type..." | 04_scan_tag, 05_read_tag | COVERED |
| no_tag_found | "No tag found" | 02_auto_copy, 04_scan_tag, 13_erase_tag | COVERED |
| tag_found | "Tag Found" | 04_scan_tag | COVERED |
| tag_multi | "Multiple tags detected!" | 04_scan_tag | COVERED |
| processing | "Processing..." | 08_pcmode | COVERED |
| trace_saved | "Trace file saved" | 06_sniff, 07_simulation | COVERED |
| sniffing | "Sniffing in progress..." | 06_sniff | COVERED |
| t5577_sniff_finished | "T5577 Sniff Finished" | 06_sniff | COVERED |
| write_success | "Write successful!" | 02_auto_copy, 16_write_tag | COVERED |
| write_verify_success | "Write and Verify successful!" | 02_auto_copy, 16_write_tag | COVERED |
| write_failed | "Write failed!" | 02_auto_copy, 16_write_tag | COVERED |
| verify_success | "Verification successful!" | 02_auto_copy, 16_write_tag | COVERED |
| verify_failed | "Verification failed!" | 02_auto_copy, 16_write_tag | COVERED |
| you_win | "You win" | 17_secondary | COVERED |
| game_over | "Game Over" | 17_secondary | COVERED |
| game_tips | "Press OK to start game." | 17_secondary | COVERED |
| pausing | "Pausing" | 17_secondary | COVERED |
| trace_loading | "Trace Loading..." | 06_sniff, 07_simulation | COVERED |
| simulating | "Simulation in progress..." | 07_simulation | COVERED |
| sim_valid_input | "Input invalid:..." | 07_simulation | COVERED |
| sim_valid_param | "Invalid parameter" | 07_simulation | COVERED |
| bcc_fix_failed | "BCC repair failed" | -- | ORPHANED |
| wipe_success | "Erase successful" | 13_erase_tag | COVERED |
| wipe_failed | "Erase failed" | 13_erase_tag | COVERED |
| keys_check_failed | "Time out" | -- | ORPHANED |
| wipe_no_valid_keys | "No valid keys..." | 13_erase_tag | COVERED |
| err_at_wiping | "Unknown error" | 13_erase_tag | COVERED |
| time_syncing | "Synchronizing system time" | 14_time_settings | COVERED |
| time_syncok | "Synchronization successful!" | 14_time_settings | COVERED |
| device_disconnected | "USB device is removed!" | -- | ORPHANED |
| plz_remove_device | "Please remove USB device!" | -- | ORPHANED |
| start_clone_uid | "Start writing UID" | -- | ORPHANED |
| unknown_error | "Unknown error." | -- | ORPHANED |
| write_wearable_err1 | "original tag and tag(new)..." | 17_secondary | COVERED |
| write_wearable_err2 | "Encrypted cards not supported" | 17_secondary | COVERED |
| write_wearable_err3 | "Change tag position..." | 17_secondary | COVERED |
| write_wearable_err4 | "UID write failed..." | 17_secondary | COVERED |
| delete_confirm | "Delete?" | 03_dump_files | COVERED |
| opera_unsupported | "Invalid command" | -- | ORPHANED |

**ORPHANED toast keys:** `bcc_fix_failed`, `keys_check_failed`, `device_disconnected`, `plz_remove_device`, `start_clone_uid`, `unknown_error`, `opera_unsupported` (7 keys)

### 6.4 StringEN.tipsmsg Keys -- Coverage

All 25 tipsmsg keys are COVERED by at least one activity doc.

### 6.5 StringEN.procbarmsg Keys -- Coverage

All 20 procbarmsg keys are COVERED by at least one activity doc.

### 6.6 StringEN.itemmsg Keys -- Coverage

| Key | Status |
|-----|--------|
| missing_keys_msg1 | COVERED (05_read_tag) |
| missing_keys_msg2 | COVERED (05_read_tag) |
| missing_keys_msg3 | ORPHANED (not referenced; similar to msg1 but with periods) |
| missing_keys_t57 | COVERED (06_sniff) |
| enter_known_keys | ORPHANED (exists but no doc references it directly) |
| aboutline1-6 | COVERED (12_about) |
| aboutline1-5_update | COVERED (12_about) |
| valueline1-4 | COVERED (11_volume) |
| blline1-3 | COVERED (10_backlight) |
| sniffline1-4, sniffline_t5577 | COVERED (06_sniff) |
| sniff_item1-5 | COVERED (06_sniff) |
| sniff_decode, sniff_trace | COVERED (06_sniff) |
| diagnosis_item1-2 | COVERED (09_diagnosis) |
| diagnosis_subitem1-9 | COVERED (09_diagnosis) |
| key_item | ORPHANED (generic "Key{}: " format, not in any specific doc) |
| uid_item | ORPHANED (generic "UID: " format, not in any specific doc) |
| wipe_m1, wipe_t55xx | COVERED (13_erase_tag) |
| write_wearable_tips1-3 | COVERED (17_secondary) |

**ORPHANED itemmsg keys:** `missing_keys_msg3`, `enter_known_keys`, `key_item`, `uid_item` (4 keys)

### 6.7 Summary of Orphaned Keys

| Category | Orphaned Keys | Count |
|----------|--------------|-------|
| title | network, warning | 2 |
| button | retry, forceuse, shutdown, yes, no | 5 |
| toastmsg | bcc_fix_failed, keys_check_failed, device_disconnected, plz_remove_device, start_clone_uid, unknown_error, opera_unsupported | 7 |
| itemmsg | missing_keys_msg3, enter_known_keys, key_item, uid_item | 4 |
| **Total** | | **18** |

Note: These orphaned keys likely exist in the .so binaries for edge cases, error handling, or features not fully documented. They are NOT errors -- they are simply not referenced by any current activity document.

---

## Section 7: Completeness Audit

### Audit Criteria

1. Identity section with class name and module
2. ALL states listed with title/M1/M2
3. Key bindings for each state
4. State transitions documented
5. Ground-truth sources cited (decompiled line numbers or screenshot filenames)
6. Avoids known errors (no "OK" buttons, 5 items/page, page indicator in title)
7. Post-audit corrections applied where screenshots contradicted decompiled assumptions

### Results

#### PASS (15 docs)

| Doc | Notes |
|-----|-------|
| 01_main_menu | Full identity, all states, key bindings, transitions, screenshot + decompiled citations. Correctly shows 5 items/page, page in title, no button labels. Corrected: removed Write Tag, added Diagnosis at pos 7. |
| 02_auto_copy | Full identity (7 methods listed). 14 states fully documented. Key summary table per state. Extensive screenshot evidence (0249-0762). Flow diagram. |
| 03_dump_files | 16 methods listed. 5 states fully documented. Key handling tables. Screenshot evidence. File system layout. Pagination documented. |
| 05_read_tag | 4 activities covered (ReadList, Read, WarningM1, KeyEnterM1). All states with layouts. Key binding tables. Screenshot evidence for SCANNING through READ_SUCCESS. |
| 06_sniff | 4 classes documented (Sniff, SniffForSpecific, SniffForMf, SniffForT5X). 5 states. PM3 commands. Full method inventories. Complete key/button string tables. Corrected: button labels verified against 8 screenshots. |
| 07_simulation | 52+ methods listed. 3 states with full layout. 16 sim types with PM3 commands. Input field specs per type. SimulationTraceActivity also covered. Corrected: button labels to Stop/Start from screenshots. |
| 08_pcmode | 13 methods + closures. 4 states documented. External dependencies (gadget_linux, socat). Button labels per state table. Verified: IDLE M1/M2 both "Start". |
| 09_diagnosis | 20+ methods for DiagnosisActivity + 6 sub-test activities. All states documented with string resources. Corrected: TEST_LIST buttons to M1="Cancel", M2="Start". Added RESULTS state. |
| 10_backlight | Full identity with settings persistence. CheckedListView with 3 items. Key bindings with instant preview. Ground truth checklist table. No M1/M2 buttons (correct). Corrected: check indicator description. |
| 11_volume | Mirrors backlight structure. 4 items including "Off". Differences table vs backlight. Ground truth checklist. No M1/M2 buttons (correct). Corrected: check indicator description. |
| 12_about | Full identity, 3 states (INFO_DISPLAY pages 1-2, UPDATE_AVAILABLE). Corrected: 2-page pagination with "About 1/2"/"About 2/2" titles, first line is device name "iCopy-XS". |
| 13_erase_tag | 12 methods listed. 6 states. PM3 command reference from real device trace. Screenshot evidence. Gen1a vs standard MF1 paths documented. Corrected: added ChkDIC/Erasing screenshots. |
| 14_time_settings | Two modes (Display/Edit) fully documented. 6 input fields with ranges. Screenshots for both modes. InputMethodList widget architecture. Ground truth checklist. All buttons verified. |
| 15_lua_script | Both LUAScriptCMDActivity (8 methods) and ConsolePrinterActivity (15 methods) documented. States, key bindings, screenshot evidence. Corrected: no button bar on file list, full-screen console. |
| 16_write_tag | WarningWriteActivity + WriteActivity. 8 states total. All button labels per state documented. Screenshots for WRITING, WRITE_FAILED, WRITE_SUCCESS. Cross-reference table. Corrected: button order consistent for success and failure. |

#### PARTIAL (2 docs)

| Doc | Missing Elements |
|-----|-----------------|
| 04_scan_tag | Identity section present. States documented. However: many states marked [UNRESOLVED -- NO SCREENSHOT EVIDENCE] for visual details. Key bindings are documented but less structured than other docs. No ground-truth checklist table. |
| 17_secondary | 9 secondary/hidden activities documented. State machines for each. String resource cross-references. However: ALL states are code-only (no screenshot evidence). Activity accessibility summary table present. |

#### FAIL (0 docs)

No documents contain outright errors or contradictions with the established ground truth after corrections. All documents correctly use 5 items/page, place the page indicator in the title, and avoid showing "OK" as an on-screen button label.

### Framework Docs Audit

| Doc | Status | Notes |
|-----|--------|-------|
| 00_framework/SCREEN_LAYOUT.md | PASS | Exhaustive. Pixel measurements from framebuffers. Color constants with hex values. HMI serial protocol documented. Canvas tag system. Known discrepancies between desktop and hardware rendering explicitly called out. |
| 00_framework/LISTVIEW.md | PASS | Constructor signature, item height, display max, selection highlight, text drawing, page indicator -- all documented with decompiled line references. Summary table. |
| 00_framework/CHECKED_LISTVIEW.md | PASS | Class hierarchy, _updateViews rendering sequence, check indicator analysis, summary table. Corrected to show two-part fillsquare rendering: grey-stroked outline for unchecked, blue-stroked outline + blue fill for checked. |
