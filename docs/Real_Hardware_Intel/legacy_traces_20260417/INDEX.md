# Legacy-FW Live-Device Traces (Phase 6 session) — 2026-04-17

Trace captures from the iCopy-X device during Phase 6 compat-flip
verification on the `feat/compat-flip` branch.

Device: iCopy-X with `noflash` IPK build from commit `a3a4a72`, running
iCopy-X Community fork PM3 (`RRG/Iceman/master/385d892f-dirty 2022-08-16`).

Tracer: `sitecustomize.py` (docs/HOW_TO_RUN_LIVE_TRACES.md section 5),
hooks `startPM3Task`, `stopPM3Task`, `reworkPM3All`, `connect2PM3`,
`scan.setScanCache`, `keymap.key.onKey`, serial.Serial.write, and polls
the activity stack every 0.5s. Output truncated to 2000 chars per event.

## Per-flow capture index

| File | Flow |
|---|---|
| `trace_legacy_session_final_20260417.txt` | Final live log at session close — LF Pyramid + Viking AutoCopy attempts |
| `trace_legacy_mf1k_read_regression_20260417.txt` | MF1K standard read — pre-rdsc-normalizer failure (all sectors readable but middleware returned empty) |
| `trace_legacy_mf1k_nested_hang_20260417.txt` | MF1K nested-attack hang before `o`-prefix fix |
| `trace_legacy_mfu_write_special_block_fail_20260417.txt` | MFU/NTAG restore with -s -e flags on plain MFU — "failed to write block" cascade |
| `trace_legacy_mfu_restore_e_flag_20260417.txt` | MFU restore with `-e -f` flags (post-fix, pre-tolerant-fail-check) |
| `trace_legacy_mfu_ev1_write_20260417.txt` | EV1 AutoCopy restore on fresh card (clean pass) |
| `trace_legacy_hid_prox_autocopy_20260417.txt` | HID Prox scan + raw extraction via `_normalize_hid_prox` |
| `trace_legacy_fdxb_autocopy_20260417.txt` | FDX-B scan + Animal ID/Raw normalization |
| `trace_legacy_iclass_elite_scan_20260417.txt` | iCLASS Elite scan (session 3 anchor retest) |
| `trace_legacy_iso15693_autocopy_20260417.txt` | ISO15693 AutoCopy with empty-UID scan (pre-UID normalizer) |
| `trace_legacy_iso15693_autocopy_v2_20260417.txt` | ISO15693 AutoCopy with UID-normalizer and matching-UID target |
| `trace_legacy_pac_clone_hang_20260417.txt` | PAC/Stanley clone hang via `lf pac clone` (PM3 firmware hang) |
| `trace_legacy_pac_workaround_target_fail_20260417.txt` | PAC workaround first attempt — target card `lf t55xx detect` failure |
| `trace_legacy_pac_workaround_success_20260417.txt` | PAC workaround success via direct `lf t55xx write` block path |
| `trace_legacy_pyramid_autocopy_20260417.txt` | Pyramid AutoCopy (clean happy-path) |
| `trace_legacy_t55xx_chk_stuck_20260417.txt` | T55xx chk 180s timeout + recovery |

## Key session fixes (in commit order on feat/compat-flip)

- `2737b11` — application.py: probe PM3 version unconditionally (manifest gate bug)
- `59233ec` — pm3_compat: MF rdsc/rdbl grid → iceman `data:` normalizer
- `89c38fe` — pm3_compat: drop broken EM410x keyword rewrite
- `cc30a5e` — pm3_compat: darkside/nested found-key → iceman `[ hex ]` bracketed
- `3c793fe` — pm3_compat: MFU restore `Finish restore` → `Done!` + rule variants
- `de4b977` — hfmfuwrite: conditional flags per tag type + tolerant fail
- `43f940c` — pm3_compat: drop `o` override from t55xx --page1
- `cac2c36` — pm3_compat: iclass wrbl/calcnewkey/chk device-binary-backed syntax
- `e7e5d85` — pm3_compat: csetuid ATQA/SAK swap + indala clone removal

Plus uncommitted at session close:
- universal `_post_normalize` rewrites for `Raw  <hex>` → `Raw:` and
  `Animal ID  <id>` → `Animal ID........... `
- `_normalize_hf_sea` for ISO15693 `UID:` → `UID....`
- `_normalize_hid_prox` synthesizes `raw: <hex>` from `HID Prox - <hex>`
- `lf hid reader` / `lf hid read` normalizer registration
- `lfwrite.B0_WRITE_MAP` — PAC/Stanley (type 34) moved from RAW_CLONE_MAP
  to B0_WRITE_MAP with config word `00080080` (deviation from ground
  truth; workaround for PM3 firmware hang in `clone_t55xx_tag()`)

## Ground-truth deviations (flagged in code)

- **PAC/STANLEY (type 34)**: bypasses `lf pac clone` due to firmware hang
  (see `lfwrite.py:132-160`). Falls through to direct T55xx block writes.
