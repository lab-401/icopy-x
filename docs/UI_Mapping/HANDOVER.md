# UI Mapping Project — Agent Handover Document

## What was done

A complete UI mapping documentation set was built for the iCopy-X v1.0.90 firmware, extracted from decompiled .so binaries and validated against 140 real-device screenshots. This replaces previous documentation that contained significant errors.

## Why it was done

The previous UI_Mapping docs were written from assumptions and circular verification (comparing our Python reimplementation against our own docs). An audit revealed major errors:

- Items per page was 4 in docs, actually **5** on real device
- Item height was 40px, actually **~32px**
- Page indicator was documented as a separate widget, actually **embedded in title bar** as "Title N/M"
- Button label "OK" appeared on multiple screens — **no screen in the original firmware uses "OK"**
- CheckedListView used green checkmark on left — actually **grey-outline squares (unchecked) / blue-outline+blue-fill squares (checked) on the RIGHT**
- Menu positions 7-8 were swapped (Diagnosis/Backlight)

## Sources of truth (ranked)

1. **Real device screenshots** (140 files) — `docs/Real_Hardware_Intel/Screenshots/*.png` with `MANIFEST.txt`. Authoritative for visual appearance in the captured state. NOT authoritative for conditional logic or hidden key bindings.

2. **Decompiled .so binaries** — `decompiled/*.txt` (~263K lines of Ghidra ARM pseudocode). Authoritative for behavior: state machines, key bindings, conditional branches, string references. Hard to read but contains 100% of the logic.

3. **String tables** — `docs/v1090_strings/*.txt`. Every string literal from every .so module.

4. **resources.py StringEN dicts** — `src/lib/resources.py` (ONLY the StringEN class). Verified string key→value mappings.

**NOT sources**: `src/lib/*.py` (our reimplementation — contains errors to be fixed), `src/lib/_constants.py` (wrong values), `docs/UI_SPEC.md` (derived from wrong assumptions).

## Document structure

```
docs/UI_Mapping/
├── UI_MAP_COMPLETE.md          # Master chart: 113 screen states, 40 activity classes
├── KEY_BINDINGS_MASTER.md      # Complete key×state matrices for 31 activities
├── AUDIT_GROUP1.md             # Adversarial audit trail (group 1)
├── AUDIT_GROUP2.md             # Adversarial audit trail (group 2)
├── 00_framework/               # Shared rendering framework
│   ├── SCREEN_LAYOUT.md        # Title bar (40px), content (160px), button bar (40px)
│   ├── LISTVIEW.md             # 5 items/page, ~32px height, selection highlight
│   ├── CHECKED_LISTVIEW.md     # Grey-outline unchecked, blue-outline+blue-fill checked, RIGHT side
│   ├── PROGRESSBAR.md          # Position, colors, message text
│   ├── TOAST.md                # Overlay modes (120px/132px height), dismiss via cancel()
│   ├── INPUT_METHOD.md         # Cursor, character cycling, field navigation
│   ├── CONSOLE_VIEW.md         # NOT in widget.so — separate module
│   ├── BATTERY_BAR.md          # Top-right title bar, 3-color thresholds
│   └── VALIDATION_REPORT.md    # Screenshot validation results
├── 01_main_menu/               # 14 items, 3 pages (5+5+4), NO button labels
├── 02_auto_copy/               # 8+ states, auto scan→read→write pipeline
├── 03_dump_files/              # 4 items/page (exception!), "No"/"Yes" delete confirm
├── 04_scan_tag/                # 6 states, 31+ tag types
├── 05_read_tag/                # 8+ states, 40 types across 8 pages
├── 06_sniff/                   # 4 sniff activities, M1="Start" M2="Finish" during sniff
├── 07_simulation/              # 52+ methods, 16 sim types, M1="Stop" M2="Start"
├── 08_pcmode/                  # M1="Start" M2="Start" (both same)
├── 09_diagnosis/               # 7 sub-test activities, M1="Cancel" M2="Start"
├── 10_backlight/               # CheckedListView 3 items, OK saves (no exit), PWR exits with recovery
├── 11_volume/                  # CheckedListView 4 items, OK saves (no exit), PWR exits WITHOUT recovery
├── 12_about/                   # 2 pages ("About 1/2", "About 2/2"), conditional UPDATE_AVAILABLE
├── 13_erase_tag/               # 2 erase types, scan→erase flow
├── 14_time_settings/           # 6 InputMethod fields, display mode "Edit"/"Edit", edit mode "Cancel"/"Save"
├── 15_lua_script/              # File list (no buttons), full-screen console output
├── 16_write_tag/               # M1="Verify" M2="Rewrite" (same for success AND failure)
└── 17_secondary/               # 9 hidden/system activities (SnakeGame, Watch, OTA, etc.)
```

## Key corrections that were applied

### Menu structure
| Item | Old (wrong) | New (correct) | Evidence |
|------|------------|---------------|----------|
| Menu items | 14 with "Write Tag" at pos 5 | 14 WITHOUT Write Tag; pos 5=Simulation | `main_page_2_3_1.png` |
| Pos 7 | Backlight | **Diagnosis** | `main_page_2_3_1.png`, test GOTO:7 |
| Pos 8 | Diagnosis | **Backlight** | `main_page_2_3_1.png`, BACKLIGHT_MENU_POS=8 |

### Widget rendering
| Widget | Old (wrong) | New (correct) | Evidence |
|--------|------------|---------------|----------|
| Items/page | 4 | **5** | All main menu screenshots |
| Item height | 40px | **~32px** | 5×32=160px content area |
| Page indicator | Separate PageIndicator widget | **Embedded in title: "Title N/M"** | All paginated screenshots |
| CheckedListView | Green ✓ at x=5 LEFT | **Grey-outline square (unchecked) / blue-outline+blue-fill square (checked), RIGHT side** | `backlight_1.png`, `volume_1.png` |

### Button labels
| Screen | Old (wrong) | New (correct) | Evidence |
|--------|------------|---------------|----------|
| Main menu M2 | "OK" | **(empty)** | `main_page_1_3_1.png` |
| Backlight M2 | "OK" | **(empty)** | `backlight_1.png` |
| Volume M2 | "OK" | **(empty)** | `volume_1.png` |
| Simulation SIM_UI | M1="Edit" M2="Simulate" | **M1="Stop" M2="Start"** | `simulation_detail_1.png` |
| Sniff RESULT | M1="Save" | **M1="Cancel" M2="Save"** | `trace.png` |
| Diagnosis tips | M1="Start" | **M1="Cancel" M2="Start"** | `diagnosis_menu_2.png` |
| LUA Script list | M2="OK" | **(empty)** | `lua_script_1_10.png` |
| Write post-op | varies by success/fail | **Always M1="Verify" M2="Rewrite"** | `write_tag_write_failed.png` |
| Dump delete confirm | "Cancel"/"Confirm" | **"No"/"Yes"** | `dump_files_delete_confirm_2.png` |

### Key binding corrections
| Activity | Key | Old (wrong) | New (correct) |
|----------|-----|------------|---------------|
| Backlight | OK | Save AND exit | **Save only (stay on screen)** |
| Volume | OK | Save AND exit | **Save only (stay on screen)** |
| Volume | PWR | Restore original + exit | **Exit WITHOUT recovery** |
| Time Settings | OK (display) | Enter edit mode | **No action** |
| Main Menu | M2 | No action | **Same as OK (launches activity)** |

## Important principles learned

1. **Screenshots prove appearance, not behavior.** A screenshot showing one state cannot disprove conditional branches in the decompiled code. Example: About page 2 appearing in a screenshot doesn't prove UPDATE_AVAILABLE is unconditional.

2. **Middleware text is not UI state.** Progress bar labels like "ChkDIC" or "Erasing 50%" come from .so middleware at runtime. The UI mapping documents the widget position/formatting, not every possible middleware string.

3. **Some activities override items-per-page.** Dump Files uses 4 items/page while most lists use 5. The `setDisplayItemMax` call in each activity's onCreate determines this.

4. **PWR has dual-layer handling.** keymap.so intercepts PWR globally (calls actstack.finish_activity()). Individual activities also handle PWR in their onKeyEvent as defense-in-depth. ButtonTestActivity is the sole exception — it needs to RECEIVE PWR to test the button.

## What still needs work

1. **17_secondary docs** — limited screenshot coverage for hidden activities (SnakeGame, Watch, IClassSE, etc.)
2. **ConsoleView widget** — not found in widget.so; must be in a different module. Framework doc is minimal.
3. **Exact pixel coordinates** — many values marked `[UNRESOLVED FROM DECOMPILATION]` due to DAT_ address indirection in Ghidra output. The decompiled code has the values but they're behind pointer chains that are hard to resolve statically.
4. **DumpFiles items-per-page anomaly** — confirmed as 4 from screenshots, but the decompiled code reason (custom setDisplayItemMax call) hasn't been traced to exact line.

## Old docs

Previous (error-containing) docs archived to `/home/qx/archive/old_ui_map/`. These use the old numbering scheme (00_main_menu through 16_hidden) and should not be referenced.

## Process that produced this

```
Tier 1: Framework extraction (2 agents)
  → Read decompiled widget.so + actbase.so → 8 framework docs

Tier 2: Per-activity extraction (6 parallel agents)
  → Read decompiled activity_main.so + activity_tools.so + actmain.so → 17 activity docs

Tier 3: Validation + assembly (2 agents)
  → Screenshot validator + master assembler → UI_MAP_COMPLETE.md

Tier 4: Adversarial audit (2 agents)
  → Compared every doc against 140 real-device screenshots → found 50 errors

Correction pass (2 agents)
  → Fixed 47 valid errors (3 discarded as auditor mistakes)

Key binding pass (1 agent)
  → Extracted onKeyEvent from 31 activities → KEY_BINDINGS_MASTER.md + updated all docs
  → Found 5 additional errors during extraction

AutoCopy/DumpFiles audit (1 agent)
  → Found 3 additional errors (DumpFiles 4 items/page, FDX name, delete confirm labels)

UI_MAP_COMPLETE rebuild (1 agent)
  → Incorporated all corrections into master chart
```

Total: ~20 agents, ~36,900 lines of documentation produced.
