# v1.0.90 Complete Fixture Requirements

Every PM3 mock response needed to exercise every decision branch in the firmware.
Derived from V1090_PM3_PATTERN_MAP.md (ground truth from .so binaries).

## Principle
For each regex/keyword comparison in the firmware, we need:
- A fixture where the pattern MATCHES (happy path)
- A fixture where the pattern DOES NOT MATCH (sad path)

## SCAN FIXTURES (23 existing + 1 needed)

All 23 tag types covered by existing `ALL_SCAN_SCENARIOS`. Each triggers specific keyword checks.

**Existing (23):** no_tag, mf_classic_1k_4b, mf_classic_1k_7b, mf_classic_4k_4b, mf_classic_4k_7b, mf_mini, mf_ultralight, ntag215, mf_desfire, multi_tags, mf_possible_4b, hf14a_other, iclass, iso15693_icode, iso15693_st, legic, iso14443b, topaz, felica, em410x, hid_prox, indala, t55xx_blank

**Missing (1):**
- `scan_cancelled` — trigger scan, inject M1 to cancel (key-based, no fixture needed)

## KEY RECOVERY FIXTURES (3 existing + 4 needed)

### Existing:
- `mf1k_all_default_keys` — fchk finds all 32 keys → skip darkside/nested
- `mf1k_no_keys` — fchk finds 0, darkside succeeds, nested completes
- `mf1k_darkside_fail` — fchk finds 0, darkside fails (hardened card)

### Missing:
- `mf1k_partial_fchk` — fchk finds 16/32 keys, nested recovers remaining
  - Triggers: fchk partial match + nested path (without darkside)
  - Response: fchk table with 16 '1' results and 16 '0' results

- `mf1k_nested_partial` — fchk finds 1, darkside skip, nested finds 28/31 remaining
  - Triggers: nested partial recovery → force read option
  - Response: nested returns keys for some sectors, timeout for others

- `mf1k_stnested` — static nonce card that requires STnested instead of nested
  - Triggers: STnested code path (alternative to standard nested)
  - Response: darkside finds key, but nested fails, STnested succeeds

- `mf4k_all_keys` — 4K card (40 sectors, 80 keys) with all default keys
  - Triggers: larger sector count code path

## READ FIXTURES (need 10 new)

### MIFARE Classic Read:
- `read_mf1k_all_sectors` — all 16 sectors read successfully
  - Response: `hf mf rdsc` returns 4 blocks per sector, all matching `[a-fA-F0-9]{32}`

- `read_mf1k_partial_sectors` — 12/16 sectors read, 4 fail
  - Response: `hf mf rdsc` returns -1 for sectors 12-15

- `read_mf1k_tag_lost` — tag removed mid-read
  - Response: first 8 sectors succeed, then `CODE_PM3_TASK_ERROR` for remaining

### Ultralight/NTAG Read:
- `read_ultralight_success` — `hf mfu dump` clean success
  - Response: no "Partial dump created" keyword, return 0

- `read_ultralight_partial` — `hf mfu dump` partial
  - Response: output contains "Partial dump created"

- `read_ntag215_success` — same as ultralight but for NTAG
  - Response: clean dump

### iCLASS Read:
- `read_iclass_legacy` — legacy key found, 19 blocks read
  - Response: `hf iclass dump` output contains "saving dump file - 19 blocks read"

- `read_iclass_no_key` — no key found
  - Response: `hf iclass chk` returns no key match

### LF Read:
- `read_lf_em410x` — `lf em 410x_read` returns UID
  - Response: "EM TAG ID      : 0F0368568B"

- `read_lf_t55xx` — `lf t55xx detect` + `lf t55xx dump`
  - Response: detect shows chip info, dump shows 12 blocks

### ISO15693 Read:
- `read_iso15693` — `hf 15 dump` success
  - Response: clean execution, no error

### LEGIC Read:
- `read_legic` — `hf legic dump` success
  - Response: clean execution

## WRITE FIXTURES (3 existing + 15 needed)

### Existing:
- `gen1a_success` — Gen1a magic card cload success
- `standard_success` — Standard wrbl success
- `standard_fail` — Standard wrbl failure

### MIFARE Classic Write (5 new):
- `write_mf1k_gen1a_cload` — `hf mf cload b` with "Card loaded N blocks from file"
  - Triggers: Gen1a path with cload keyword match

- `write_mf1k_gen1a_uid` — `hf mf csetuid` with "New UID" in output
  - Triggers: Gen1a UID-only write path

- `write_mf1k_standard_all` — all `hf mf wrbl` return "isOk:01"
  - Triggers: all blocks written successfully

- `write_mf1k_standard_partial` — some wrbl succeed, some fail
  - Triggers: partial write path (some blocks have "isOk:01", others don't)

- `write_mf1k_verify_fail` — write succeeds but verify reads different data
  - Triggers: verify comparison mismatch branch

### Ultralight/NTAG Write (2 new):
- `write_ultralight_success` — `hf mfu restore` without "failed to write block"
- `write_ultralight_fail` — `hf mfu restore` output contains "failed to write block"

### iCLASS Write (3 new):
- `write_iclass_success` — `hf iclass wrbl` success for all blocks
- `write_iclass_fail` — `hf iclass wrbl` timeout
- `write_iclass_key_calc` — `hf iclass calcnewkey` returns "Xor div key : XXXX"

### LF Write (3 new):
- `write_lf_em410x` — `lf em 410x_write` success
- `write_lf_hid_clone` — `lf hid clone` success
- `write_lf_t55xx_restore` — `lf t55xx restore` success

### ISO15693 Write (2 new):
- `write_iso15693_success` — `hf 15 restore` with "Write OK"
- `write_iso15693_fail` — `hf 15 restore` with "restore failed"

## AUTOCOPY FIXTURES (5 existing + 3 needed)

### Existing:
- `autocopy_happy`, `autocopy_darkside`, `autocopy_gen1a`, `autocopy_darkside_fail`, `autocopy_write_fail`

### Missing:
- `autocopy_no_tag` — scan returns no tag (all PM3 timeouts)
- `autocopy_partial_read` — scan succeeds, read is partial (force read prompt)
- `autocopy_verify_fail` — scan+read+write succeed but verify fails

## ERASE FIXTURES (4 new)

- `erase_mf1_success` — scan MF1K, wipe all blocks
  - Response: `hf 14a info` returns tag, `hf mf wrbl` all return "isOk:01"
  - Activity_main.so checks: `\[.\]wipe block ([0-9]+)` and `Card wiped successfully`

- `erase_mf1_no_keys` — scan MF1K, no keys for wipe
  - Response: `hf 14a info` returns tag, fchk returns no keys

- `erase_t5577_success` — T5577 wipe
  - Response: `lf t55xx detect` returns chip, `lf t55xx wipe` succeeds

- `erase_t5577_fail` — T5577 wipe timeout
  - Response: `lf t55xx wipe` returns timeout

## DIAGNOSIS FIXTURES (2 existing + 1 needed)

### Existing:
- `hw_tune_ok` — both antennas pass
- `hw_tune_lf_fail` — LF fails, HF passes

### Missing:
- `hw_tune_hf_fail` — HF fails, LF passes

## SNIFF FIXTURES (3 new)

- `sniff_14a_trace` — `hf 14a sniff` returns trace data
  - Response: trace with "trace len = NNN"

- `sniff_t5577_keys` — T5577 sniff returns recovered keys
  - Response: "Default pwd write | XXXXXXXX |" and "key XXXXXXXXXXXX"

- `sniff_empty` — sniff returns no data

## SUMMARY

| Category | Existing | New Needed | Total |
|----------|----------|------------|-------|
| Scan | 23 | 0 | 23 |
| Key Recovery | 3 | 4 | 7 |
| Read | 0 | 12 | 12 |
| Write | 3 | 15 | 18 |
| AutoCopy | 5 | 3 | 8 |
| Erase | 0 | 4 | 4 |
| Diagnosis | 2 | 1 | 3 |
| Sniff | 0 | 3 | 3 |
| **TOTAL** | **36** | **42** | **78** |

78 total fixtures → 116+ capture scenarios (many fixtures used in multiple scenarios).
