# Full Flow Test Suite Results — 2026-04-12

**Target:** `original` (v1.0.90 firmware .so modules under QEMU)
**Server:** qx@178.62.84.144 (remote QEMU)
**Workers:** 9 parallel (sequential for dump_files, backlight, volume, diagnosis)
**Total:** 87 PASS / 214 FAIL / 301 total (9557s = ~2h 39m)

> Note: `dump_files` wrote results to `_results/current/` (35 scenarios not included in the 301 total).

## Per-flow breakdown

| Flow | PASS | FAIL | Total | Time | Notes |
|------|------|------|-------|------|-------|
| **scan** | 45 | 0 | 45 | 223s | Perfect |
| **read** | 0 | 97 | 97 | 2385s | Known blocker: initList crash |
| **write** | 0 | 61 | 61 | 1017s | "M2:Write" trigger never reached |
| **auto-copy** | 10 | 42 | 52 | 1976s | 10 edge-case passes |
| **erase** | 0 | 10 | 10 | 38s | "M2 not 'Erase'" — same nav blocker |
| **simulate** | 23 | 5 | 28 | 135s | 5 FDX-B/Nedap failures |
| **sniff** | 24 | 3 | 27 | ~300s | 3 iclass/nav failures |
| **lua-script** | 10 | 1 | 11 | 51s | 1 failure: `lua_no_scripts` |
| **time_settings** | 13 | 0 | 13 | 47s | Perfect |
| **about** | 11 | 0 | 11 | 39s | Perfect |
| **install** | 1 | 12 | 13 | 130s | "title:Update" gate not reached |
| **pc_mode** | 7 | 1 | 8 | 32s | 1 button label issue |
| **dump_files** | 33 | 2 | 35 | ~2100s | In `current/` target |
| **backlight** | 7 | 0 | 7 | ~60s | Perfect |
| **volume** | 2 | 5 | 7 | 137s | Save/re-entry verification fails |
| **diagnosis** | 4 | 0 | 4 | 128s | Perfect |

## Perfect flows (6)

- scan (45/45)
- time_settings (13/13)
- about (11/11)
- backlight (7/7)
- diagnosis (4/4)
- dump_files (33/35 — 94%)

## Bulk failure root cause

**read**, **write**, and **erase** all trace to the known `initList SetItem` crash at `0x60ec6` in the original .so modules under QEMU. This blocks navigation past scan results, so toast triggers (`File saved`, `Read Failed`, `M2:Write`, `M2:Erase`) are never reached.

## Targeted failures

### simulate (5 failures)
- `sim_fdxb_animal` — wrong tag type label
- `sim_fdxb_animal_validation_fail` — wrong tag type label
- `sim_fdxb_data` — wrong tag type label
- `sim_fdxb_data_validation_fail` — wrong tag type label
- `sim_nedap_validation_fail` — validation toast not found

### sniff (3 failures)
- `sniff_iclass_real_csn` — validation check failed
- `sniff_iclass_trace_with_csn` — validation check failed
- `sniff_list_navigation` — T5577 not reached after DOWN×4

### install (12 failures)
- All except `install_no_ipk` fail on "Gate 'title:Update' not reached"

### volume (5 failures)
- Save/re-entry verification mismatches (highlight position wrong after save+reopen)

### pc_mode (1 failure)
- `pcmode_starting_buttons` — M1 label changed during STARTING

### lua-script (1 failure)
- `lua_no_scripts` — validation failed

### dump_files (2 failures)
- `dump_write_mf1k_fail` — write trigger not reached
- `dump_write_mf1k_success` — write trigger not reached (same MFC write blocker)
