# iCopy-X v1.0.90 — UI Navigation Flowchart

All branches extracted from .so binary strings. Every arrow = a verified transition.

## Main Menu (14 items, 5/page, 3 pages)

```
                         ┌──────────────────────────────┐
                         │       MAIN MENU              │
                         │  BigTextListView 14 items    │
                         │  5/page, 3 pages             │
                         │  UP/DOWN=scroll  OK=select   │
                         └──────────┬───────────────────┘
                                    │ OK on selected item
        ┌───────────┬───────────┬───┴───┬───────────┬──────────────┐
        ▼           ▼           ▼       ▼           ▼              ▼
   [0]AutoCopy [1]DumpFiles [2]Scan [3]Read    [4]Sniff      [5]Simulation
        │           │           │       │           │              │
        ▼           ▼           ▼       ▼           ▼              ▼
  (see below)  (see below)    ...     ...         ...            ...

   [6]PC-Mode  [7]Backlight [8]Diagnosis [9]Volume [10]About
        │           │           │           │          │
        ▼           ▼           ▼           ▼          ▼
  (standalone) (standalone) (standalone) (standalone) (2 pages)

   [11]EraseTag [12]TimeSettings [13]LUAScript
        │              │               │
        ▼              ▼               ▼
  (see below)    (standalone)    ConsolePrinter
```

## [0] Auto Copy — Full Pipeline

```
AutoCopyActivity
    │ (auto-start on enter)
    ▼
┌─SCANNING─────────────────────────────────────────────┐
│ M1=disabled  M2=disabled                             │
│ Toast: "Scanning"                                    │
├──────────────────────────────────────────────────────┤
│ onScanFinish():                                      │
│   ├─ found=True ──→ READING                          │
│   ├─ found=False ──→ toast "No tag found" → IDLE     │
│   ├─ wrong_type ──→ toast "Wrong type" → IDLE        │
│   └─ multi ──→ toast "Multiple tags" → IDLE          │
└──────────────────────────────────────────────────────┘
    │ found
    ▼
┌─READING──────────────────────────────────────────────┐
│ Toast: "Reading"                                     │
├──────────────────────────────────────────────────────┤
│   ├─ success ──→ PLACE_CARD_PROMPT                   │
│   ├─ partial ──→ PLACE_CARD_PROMPT                   │
│   ├─ failed ──→ toast "Read Failed!" → IDLE          │
│   └─ missing_keys ──→ WarningM1Activity              │
└──────────────────────────────────────────────────────┘
    │ success
    ▼
┌─PLACE_CARD_PROMPT────────────────────────────────────┐
│ "Data ready for copy! Please place new tag."         │
│ M1=Back  M2=Start(Write)                             │
├──────────────────────────────────────────────────────┤
│ M2 ──→ WRITING                                       │
│ PWR ──→ IDLE                                         │
└──────────────────────────────────────────────────────┘
    │ M2
    ▼
┌─WRITING──→──VERIFYING──→──DONE/FAIL─────────────────┐
│ Toast: "Writing" → "Verifying"                       │
│   ├─ success ──→ toast "Write and Verify successful!"│
│   └─ fail ──→ toast "Write failed!"                  │
│ M2=Start (clone another) │ PWR=exit                  │
└──────────────────────────────────────────────────────┘
```

## [1] Dump Files — Browse → Detail → Write/Sim/Delete

```
ReadListActivity ("Dump Files X/6")
│ BigTextListView: tag type families
│ UP/DOWN=scroll  M2=select family  PWR=back
│
└─ M2 ──→ CardWalletActivity (FILE LIST MODE)
          │ Title: family name (e.g. "Viking ID")
          │ Files sorted by ctime
          │ M1="Write"  M2="Details"  PWR=back
          │
          ├─ [EMPTY] ──→ "place_empty_tag" message, buttons disabled
          │
          ├─ M1 (Write) ──→ WarningWriteActivity ──→ WriteActivity
          │
          └─ M2 (Details) ──→ CardWalletActivity (DETAIL VIEW)
                              │ Content: template.draw() per type
                              │ M1="Delete"  M2="Simulate"  PWR=back to list
                              │
                              ├─ M1 (Delete) ──→ toast "Delete?" ──→ confirm ──→ file removed
                              │                                   └─ cancel ──→ stay
                              │
                              └─ M2 (Simulate) ──→ SimulationActivity
```

## [3] Read Tag → Write Path

```
ReadActivity ("Read Tag")
│ BigTextListView: 40 tag types (8 pages)
│ UP/DOWN=scroll  M2=select type  PWR=back
│
└─ M2 ──→ scan phase ──→ read phase
          │
          ├─ SUCCESS ──→ WarningWriteActivity
          │               │ "Data ready! Place new tag."
          │               │ M1=Cancel  M2=Confirm
          │               │
          │               └─ M2 ──→ WriteActivity
          │                         │ M1="Verify" M2="Write"
          │                         │
          │                         ├─ M2 (Write) ──→ WRITING
          │                         │   ├─ success ──→ toast "Write successful!"
          │                         │   │   M1="Verify"(enabled) M2="Rewrite"(enabled)
          │                         │   └─ fail ──→ toast "Write failed!"
          │                         │       M1="Verify"(enabled) M2="Rewrite"(enabled)
          │                         │
          │                         └─ M1 (Verify) ──→ VERIFYING
          │                             ├─ success ──→ toast "Verification successful!"
          │                             └─ fail ──→ toast "Verification failed!"
          │
          ├─ FAILED ──→ toast "Read Failed!"
          ├─ MISSING_KEYS ──→ WarningM1Activity (multi-page options)
          │                    Page 1: Sniff / Enter keys
          │                    Page 2: Force / PC-Mode
          ├─ NO_TAG ──→ toast "No tag found"
          └─ WRONG_TYPE ──→ toast "Wrong type found!"
```

## [11] Erase Tag

```
WipeTagActivity ("Erase Tag")
│ 2 items: "Erase MF1/L1/L2/L3" / "Erase T5577"
│ M2=select  PWR=back
│
├─ Item 1 (MF1) ──→ scan for MF1 tag
│   ├─ found ──→ WarningM1Activity (confirm erase)
│   │             M2=confirm ──→ ERASING ──→ success/fail toast
│   └─ not found ──→ toast "No tag found"
│
└─ Item 2 (T5577) ──→ scan for T5577
    ├─ found ──→ WarningT5XActivity (confirm)
    │   ├─ has password? ──→ WarningT5X4X05KeyEnterActivity
    │   └─ M2=confirm ──→ ERASING ──→ success/fail toast
    └─ not found ──→ toast "No tag found"
```

## [4] Sniff TRF

```
SniffActivity ("Sniff TRF")
│ 5 items: 14A/14B/iclass/Topaz/T5577
│ M2=select  PWR=back
│
└─ M2 ──→ SNIFFING state
          │ M1=Stop  M2=disabled
          │
          ├─ complete ──→ RESULT state
          │   ├─ HF result: decoded trace lines (showHfResult)
          │   └─ T5577 result: extracted keys (showT5577Result)
          │   M1=Back  M2=Save
          │   └─ M2 ──→ saveSniffData() → SimulationTraceActivity
          │
          └─ SniffForSpecificTag / SniffForMfReadActivity / SniffForT5XReadActivity
```

## [5] Simulation

```
SimulationActivity ("Simulation X/4")
│ Paginated list of ~16 simulatable types
│ M2=select type  PWR=back
│
└─ M2 ──→ Input screen (per-type: draw_hf_sim_4b, draw_lf_awid, etc.)
          │ UP/DOWN=change value  LEFT/RIGHT=move field
          │ M2=Start simulation  PWR=back to list
          │
          └─ M2 ──→ SIMULATING state
                    │ Toast: "Simulation in progress..."
                    │ M1=Stop  M2=disabled
                    └─ M1 ──→ stopSim() → back to input screen
```

## Standalone Activities (no sub-navigation)

| Activity | Content | M1 | M2 |
|----------|---------|----|----|
| PC-Mode | Status text | Stop/Back | Start/Stop |
| Backlight | CheckedListView (3 levels) | Back | OK (apply) |
| Volume | CheckedListView (4 levels) | Back | OK (apply) |
| About | 2-page info | Back | Update |
| Time Settings | 6 input fields | Edit | Save |
| LUA Script | File list → ConsolePrinter | Back | Execute |
| Diagnosis | 2-level test menu | Back | Start |

## Hidden Activities (not in main menu)

| Activity | Access Path | Purpose |
|----------|-------------|---------|
| WriteActivity | Read→success→Warning→Write | Tag writing |
| WarningWriteActivity | Read/DumpFiles→Write | Write confirmation |
| WarningM1Activity | Read→missing keys | Key recovery options |
| WarningT5XActivity | Erase→T5577 | T5577 erase confirm |
| WarningT5X4X05KeyEnterActivity | Erase→T5577→password | Key entry for T5577/EM4305 |
| KeyEnterM1Activity | WarningM1→Enter | Manual MIFARE key entry |
| IClassSEActivity | Read→iClass SE | iClass SE USB reader |
| CardWalletActivity | DumpFiles→family | File browser + detail |
| ReadFromHistoryActivity | (internal) | Load previous read |
| WearableDeviceActivity | (internal) | Smartwatch write |
| ConsolePrinterActivity | LUA→execute | Script output |
| SimulationTraceActivity | Sniff→save | Trace replay |
| SnakeGameActivity | (hidden menu) | Easter egg game |
| 6× Factory Test Activities | Diagnosis→Factory | Hardware tests |
| AutoExceptCatchActivity | (system) | Crash logger |
