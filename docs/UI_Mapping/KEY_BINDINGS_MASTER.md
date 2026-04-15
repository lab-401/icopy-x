# Key Bindings Master Reference

**Source of truth:** Decompiled `.so` binaries (Ghidra) cross-referenced with Python reimplementation (`src/lib/`).
**Date:** 2026-03-31

## Framework-Level Key Handling

PWR is intercepted at the `keymap.so` level:
- `KeyEvent.onKey()` translates hardware codes to logical keys
- PWR always calls `actstack.finish_activity()` (pops current activity)
- All other keys (UP, DOWN, LEFT, RIGHT, OK, M1, M2) are dispatched to the bound activity's `callKeyEvent()` -> `onKeyEvent()`
- Individual activities may include PWR handling as defense-in-depth

**8 physical keys:** UP, DOWN, LEFT, RIGHT, OK, M1 (left softkey), M2 (right softkey), PWR (power)

---

## 1. MainActivity (Main Menu)

Source: `actmain.so` / `src/lib/actmain.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev() | next() | no-op | no-op | launch activity | no-op | launch activity | sleep/shutdown |

---

## 2. AutoCopyActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

Busy check: when `_btn_enabled == False`, only PWR works.

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| SCANNING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| SCAN_NOT_FOUND | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| SCAN_WRONG_TYPE | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| SCAN_MULTI | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| READING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| READ_FAILED | no-op | no-op | no-op | no-op | reread | rescan | reread | finish() |
| READ_NO_KEY_HF | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| READ_NO_KEY_LF | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| READ_MISSING_KEYS | no-op | no-op | no-op | no-op | force-use | rescan | force-use | finish() |
| READ_TIMEOUT | no-op | no-op | no-op | no-op | reread | rescan | reread | finish() |
| PLACE_CARD | no-op | no-op | no-op | no-op | write | rescan | write | finish() |
| WRITING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| WRITE_SUCCESS | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| WRITE_FAILED | no-op | no-op | no-op | no-op | rewrite | rescan | rewrite | finish() |
| VERIFY_SUCCESS | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| VERIFY_FAILED | no-op | no-op | no-op | no-op | rewrite | rescan | rewrite | finish() |

---

## 3. CardWalletActivity (Dump Files)

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LIST (empty) | no-op | no-op | no-op | no-op | no-op | finish() | no-op | finish() |
| LIST (files) | prev() | next() | no-op | no-op | detail | finish() | detail | finish() |
| DETAIL | no-op | no-op | no-op | no-op | delete | back to list | delete | back to list |

---

## 4. ScanActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev() | next() | no-op | no-op | scan | finish() | scan | finish() |
| SCANNING | no-op | no-op | no-op | no-op | no-op | cancel->IDLE | cancel->IDLE | cancel+finish() |
| FOUND | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| NOT_FOUND | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| WRONG_TYPE | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |
| MULTI_TAGS | no-op | no-op | no-op | no-op | rescan | rescan | rescan | finish() |

---

## 5. ReadListActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LIST | prev() | next() | no-op | no-op | launch Read | finish() | launch Read | finish() |

Bundle passed to ReadActivity: `{'tag_type': int, 'tag_name': str}`

---

## 6. ReadActivity

Source: `activity_main.so` / `src/lib/activity_read.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | scan | finish() | scan | finish() |
| SCANNING | no-op | no-op | no-op | no-op | no-op | cancel->IDLE | cancel->IDLE | cancel+finish() |
| SCAN_FOUND | no-op | no-op | no-op | no-op | read | rescan | read | finish() |
| READING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | cancel+finish() |
| READ_SUCCESS | no-op | no-op | no-op | no-op | write | reread | write | finish() |
| READ_PARTIAL | no-op | no-op | no-op | no-op | write | reread | write | finish() |
| READ_FAILED | no-op | no-op | no-op | no-op | no-op | reread | no-op | finish() |
| ERROR | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |

---

## 7. SniffActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TYPE_SELECT | prev() | next() | no-op | no-op | start sniff | finish() | start sniff | finish() |
| SNIFFING | no-op | no-op | no-op | no-op | no-op | stop+finish() | stop+result | stop->TYPE_SELECT |
| RESULT | prev page | next page | no-op | no-op | save | prev page | save | ->TYPE_SELECT |

---

## 8. SimulationActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LIST | prev() | next() | no-op | no-op | select type | no-op | select type | finish() |
| SIM_UI (navigate) | prev field | next field | no-op | no-op | start sim | toggle edit | start sim | back to LIST |
| SIM_UI (edit) | roll up | roll down | prev char | next char | start sim | toggle edit | start sim | back to LIST |
| SIMULATING | no-op | no-op | no-op | no-op | no-op | no-op | stop sim | stop sim |

---

## 9. PCModeActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | start | start | start | finish() |
| STARTING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | no-op |
| RUNNING | no-op | no-op | no-op | no-op | no-op | stop | stop | stop |
| STOPPING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | no-op |

---

## 10. BacklightActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev()+preview | next()+preview | no-op | no-op | save (stay) | no-op | save (stay) | recovery+finish() |

UP/DOWN provide instant backlight preview. OK/M2 save but do NOT exit. PWR reverts to original level then exits.

---

## 11. VolumeActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | prev()+preview | next()+preview | no-op | no-op | save (stay) | no-op | save (stay) | finish() (no recovery) |

UP/DOWN provide instant audio preview. OK/M2 save but do NOT exit. PWR exits WITHOUT reverting (unlike Backlight).

---

## 12. AboutActivity

Source: `actmain.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| PAGE 0 | no-op | page 1 | no-op | no-op | update check | no-op | update check | finish() |
| PAGE 1 | page 0 | no-op | no-op | no-op | update check | page 0 | update check | finish() |

---

## 13. WipeTagActivity (Erase Tag)

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TYPE_SELECT | prev() | next() | no-op | no-op | erase | finish() | erase | finish() |
| ERASING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | cancel+finish() |
| SUCCESS | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |
| FAILED | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |
| NO_KEYS | no-op | no-op | no-op | no-op | finish() | finish() | finish() | finish() |

---

## 14. TimeSyncActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| DISPLAY | no-op | no-op | no-op | no-op | no-op | enter edit | enter edit | finish() |
| EDIT | increment | decrement | prev field | next field | no-op | no-op | save->DISPLAY | discard->DISPLAY |

6 fields: YYYY, MM, DD, HH, MM, SS. Values wrap at boundaries.

---

## 15. LUAScriptCMDActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| FILE_LIST | prev() | next() | prev page | next page | run script | no-op | run script | finish() |

---

## 16. WarningWriteActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| CONFIRM | no-op | no-op | no-op | no-op | confirm write | cancel | confirm write | cancel |

---

## 17. WriteActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | write | write | verify | finish() |
| WRITING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| VERIFYING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| W_SUCCESS | no-op | no-op | no-op | no-op | rewrite | rewrite | verify | finish() |
| W_FAILED | no-op | no-op | no-op | no-op | rewrite | rewrite | verify | finish() |
| V_SUCCESS | no-op | no-op | no-op | no-op | rewrite | rewrite | verify | finish() |
| V_FAILED | no-op | no-op | no-op | no-op | rewrite | rewrite | verify | finish() |

---

## 18. WarningM1Activity (Missing Keys)

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| PAGE N | prev page | next page | no-op | no-op | select option | cancel | select option | cancel |

4 pages: sniff, enter_key, force, pc_mode.

---

## 19. KeyEnterM1Activity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| KEY_ENTRY | roll up (0-F) | roll down (F-0) | prev char | next char | confirm | cancel | confirm | cancel |

12-digit hex key entry for MIFARE Classic.

---

## 20. ConsolePrinterActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| RUNNING | scroll up | scroll down | no-op | no-op | no-op | cancel+finish() | no-op | cancel+finish() |
| COMPLETE | scroll up | scroll down | no-op | no-op | finish() | finish() | finish() | finish() |

---

## 21. DiagnosisActivity

Source: `activity_tools.so` / `src/lib/activity_tools.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| ITEMS_MAIN | no-op | no-op | no-op | no-op | show tests | no-op | show tests | finish() |
| ITEMS_TEST | prev() | next() | no-op | no-op | start test | no-op | start test | back to MAIN |
| TESTING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | cancel test |

---

## 22. ScreenTestActivity

Source: `activity_tools.so` / `src/lib/activity_tools.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TIPS | no-op | no-op | no-op | no-op | start colors | Fail | Pass | Fail+exit |
| COLORS | prev color | next color | no-op | no-op | next/end | Fail | Pass | Fail+exit |

---

## 23. ButtonTestActivity

Source: `activity_tools.so` / `src/lib/activity_tools.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TESTING | record | record | record | record | record | record | record | record |

All 8 keys are recorded. All pressed = Pass. Timeout (30s) = Fail. PWR IS recorded here (not exit).

---

## 24. SoundTestActivity

Source: `activity_tools.so` / `src/lib/activity_tools.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| LISTEN | no-op | no-op | no-op | no-op | no-op | Fail | Pass | Fail+exit |

---

## 25. HFReaderTestActivity / LfReaderTestActivity

Source: `activity_tools.so` / `src/lib/activity_tools.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TIPS | no-op | no-op | no-op | no-op | run test | no-op | run test | Fail+exit |

---

## 26. UsbPortTestActivity

Source: `activity_tools.so` / `src/lib/activity_tools.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| TIPS | no-op | no-op | no-op | no-op | run check | no-op | run check | Fail+exit |

---

## 27. SleepModeActivity

Source: `actmain.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| SLEEPING | wake | wake | wake | wake | wake | wake | wake | wake |

Any key restores backlight and finishes.

---

## 28. WarningDiskFullActivity

Source: `actmain.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| WARNING | no-op | no-op | no-op | no-op | clear files | ignore+finish | clear files | ignore+finish |

---

## 29. WarningT5XActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| WARNING | no-op | no-op | no-op | no-op | proceed | cancel | proceed | cancel |

---

## 30. WarningT5X4X05KeyEnterActivity

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| KEY_ENTRY | roll up | roll down | prev char | next char | confirm | cancel | confirm | cancel |

8-digit hex key entry for T55xx/EM4305.

---

## 31. SnakeGameActivity (Easter Egg)

Source: `activity_main.so` / `src/lib/activity_main.py`

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | start | no-op | start | finish() |
| PLAYING | direction | direction | direction | direction | no-op | no-op | no-op | pause->IDLE |
| GAME_OVER | no-op | no-op | no-op | no-op | restart | no-op | restart | finish() |

---

## Key Patterns Summary

1. **UP/DOWN** = list navigation or value increment/decrement
2. **LEFT/RIGHT** = page navigation (LUA Script), cursor movement (hex input, time edit), or no-op
3. **OK** = primary action (same as M2 in most activities)
4. **M1** = cancel/back/secondary action
5. **M2** = primary action (usually same as OK)
6. **PWR** = universal exit/back (framework level via keymap.so)

Exceptions:
- **ButtonTestActivity**: PWR is recorded (not exit)
- **Backlight**: PWR reverts level before exit (recovery)
- **Volume**: PWR exits WITHOUT reverting
- **SleepModeActivity**: ANY key wakes (including PWR)
- **SimulationActivity SIM_UI**: M1 toggles edit mode
- **TimeSyncActivity**: M1 enters edit from display, PWR in edit returns to display (not exit)
