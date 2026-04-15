# iCopy-X v1.0.90 — UI Map Summary

Exhaustive UI mapping extracted from .so binary strings and Ghidra decompilations.

## Document Structure

| File | Activity | Lines | States | Confidence |
|------|----------|-------|--------|------------|
| [00_main_menu/](00_main_menu/README.md) | MainActivity | 485 | 4 | HIGH (QEMU verified) |
| [01_auto_copy/](01_auto_copy/README.md) | AutoCopyActivity | 950 | 16 | HIGH (flow doc validated) |
| [02_dump_files/](02_dump_files/README.md) | ReadListActivity + CardWalletActivity | 862 | 5 | MEDIUM (flow doc exists) |
| [03_scan_tag/](03_scan_tag/README.md) | ScanActivity | 584 | 6 | HIGH (walker validated, 44 scenarios) |
| [04_read_tag/](04_read_tag/README.md) | ReadActivity + warnings | 969 | 13 | HIGH (walker validated, 400+ scenarios) |
| [05_sniff/](05_sniff/README.md) | SniffActivity + sub-sniff | 526 | 6 | MEDIUM (flow doc exists) |
| [06_simulation/](06_simulation/README.md) | SimulationActivity | 853 | 14 | MEDIUM (flow doc exists) |
| [07_pc_mode/](07_pc_mode/README.md) | PCModeActivity | 407 | 4 | MEDIUM (.so strings) |
| [08_backlight/](08_backlight/README.md) | BacklightActivity | 219 | 2 | MEDIUM (flow doc exists) |
| [09_diagnosis/](09_diagnosis/README.md) | DiagnosisActivity + 6 test activities | 510 | 12 | MEDIUM (.so strings) |
| [10_volume/](10_volume/README.md) | VolumeActivity | 233 | 2 | MEDIUM (flow doc exists) |
| [11_about/](11_about/README.md) | AboutActivity + UpdateActivity | 317 | 4 | MEDIUM (flow doc exists) |
| [12_erase_tag/](12_erase_tag/README.md) | WipeTagActivity + warnings | 877 | 12 | MEDIUM (flow doc exists) |
| [13_time_settings/](13_time_settings/README.md) | TimeSyncActivity | 303 | 3 | MEDIUM (.so strings) |
| [14_lua_script/](14_lua_script/README.md) | LUAScriptCMDActivity + ConsolePrinter | 307 | 3 | MEDIUM (.so strings) |
| [15_write_tag/](15_write_tag/README.md) | WriteActivity + WarningWriteActivity | 711 | 8 | HIGH (fixtures validated) |
| [16_hidden/](16_hidden/README.md) | 12 hidden/factory activities | 765 | ~20 | LOW-MEDIUM |
| **TOTAL** | **37 activities** | **9,878** | **~134** | |

## Activity Inventory (37 classes)

### Main Menu (14 items)
| Pos | Class | Title | Folder |
|-----|-------|-------|--------|
| 0 | AutoCopyActivity | Auto Copy | 01_auto_copy |
| 1 | ReadListActivity | Dump Files | 02_dump_files |
| 2 | ScanActivity | Scan Tag | 03_scan_tag |
| 3 | ReadActivity | Read Tag | 04_read_tag |
| 4 | SniffActivity | Sniff TRF | 05_sniff |
| 5 | SimulationActivity | Simulation | 06_simulation |
| 6 | PCModeActivity | PC-Mode | 07_pc_mode |
| 7 | BacklightActivity | Backlight | 08_backlight |
| 8 | DiagnosisActivity | Diagnosis | 09_diagnosis |
| 9 | VolumeActivity | Volume | 10_volume |
| 10 | AboutActivity | About | 11_about |
| 11 | WipeTagActivity | Erase Tag | 12_erase_tag |
| 12 | TimeSyncActivity | Time Settings | 13_time_settings |
| 13 | LUAScriptCMDActivity | LUA Script | 14_lua_script |

### Secondary (not in main menu)
| Class | Parent | Folder |
|-------|--------|--------|
| WriteActivity | Read/AutoCopy/DumpFiles | 15_write_tag |
| WarningWriteActivity | Read/DumpFiles | 15_write_tag |
| CardWalletActivity | ReadListActivity | 02_dump_files |
| WarningM1Activity | Read/Erase | 04_read_tag, 12_erase_tag |
| WarningT5XActivity | Erase | 12_erase_tag |
| WarningT5X4X05KeyEnterActivity | Erase | 12_erase_tag |
| KeyEnterM1Activity | WarningM1 | 16_hidden |
| IClassSEActivity | Read | 16_hidden |
| ConsolePrinterActivity | LUA | 14_lua_script |
| SimulationTraceActivity | Sniff/Sim | 05_sniff |
| ReadFromHistoryActivity | (internal) | 16_hidden |
| WearableDeviceActivity | (internal) | 16_hidden |
| SnakeGameActivity | (hidden) | 16_hidden |
| SniffForSpecificTag | Sniff | 05_sniff |
| SniffForMfReadActivity | Sniff | 05_sniff |
| SniffForT5XReadActivity | Sniff | 05_sniff |
| 6× Test Activities | Diagnosis | 09_diagnosis, 16_hidden |
| AutoExceptCatchActivity | (system) | 16_hidden |

## Confidence Levels

| Level | Meaning | Count |
|-------|---------|-------|
| **HIGH** | Verified by walker tests (400+ scenarios) or real device traces | 5 activities |
| **MEDIUM** | Extracted from .so binary strings with supporting flow documentation | 20 activities |
| **LOW** | Extracted from .so strings only, purpose inferred | 12 activities |

## Sources

All data extracted from these ground-truth files:
- `docs/v1090_strings/activity_main_strings.txt` (31,575 lines)
- `docs/v1090_strings/resources_strings.txt` (4,766 lines)
- `docs/v1090_strings/actmain_strings.txt` — MainActivity
- `docs/v1090_strings/actbase_strings.txt` — BaseActivity API
- `docs/v1090_strings/actstack_strings.txt` — Activity lifecycle
- `docs/v1090_strings/widget_strings.txt` — ListView widgets
- `docs/v1090_strings/tagtypes_strings.txt` — Tag type system
- `decompiled/actbase.c`, `actmain.c`, `actstack.c`, `hmi_driver.c` — Ghidra output
