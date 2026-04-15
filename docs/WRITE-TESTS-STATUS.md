# Write Flow Tests — Status (2026-03-29)

## Current State: 65/65 PASS — 13 are FALSE POSITIVES

Duration: 328s with 12 parallel workers on remote (48-core).

**The test suite reports 65/65 PASS but 13 scenarios do not validate their toast content.** They pass solely on deduplicated screenshot count (>= 4 or 5). The actual toast shown by the .so is never checked against the expected outcome.

---

## False Positive Mechanism

`run_write_scenario` in `write_common.sh` takes 4 arguments:

```
run_write_scenario MIN_STATES "FINAL_TRIGGER" "no_verify" "WRITE_TOAST_TRIGGER"
```

- **Arg 2** (`final_trigger`): Only checked in Phase 5 (explicit verify). Skipped when `no_verify` is set.
- **Arg 4** (`write_toast_trigger`): Phase 4b toast validation. If empty, toast is never checked.

All 13 broken scenarios use `no_verify` (arg 3) but have no arg 4. Result: the ONLY pass gate is `DEDUP_COUNT >= min_unique` — a state count, not a content check.

## The 13 False Positive Scenarios

### Group 1: Toast is "Write failed!" but should be "Write successful!"

These show "Write failed!" because the .so's internal verify rejects the fixture data (read-back doesn't match dump).

| Scenario | Root Cause | Fix Required |
|----------|-----------|--------------|
| `write_em4305_dump_success` | No `lf em 4x05_read` fixture — verify reads back empty data, mismatch | Add sequential `lf em 4x05_read` responses matching written blocks. The .so DOES issue write commands (QEMU limitation claim in .sh comment is FALSE — confirmed by trace showing 16 `lf em 4x05_write` commands). |
| `write_iclass_elite_success` | Generic `hf iclass rdbl` returns block-06 data for ALL blocks — block 7+ mismatch. Also: `hf iclass rdbl b 01` returns error for ALL calls including verify (elite key not distinguished from scan keys). Also: `hf iclass dump ... e` creates file with ` e` in path — mock must strip trailing ` e` flag. | Per-block sequential rdbl list OR specific `rdbl b XX k ELITE_KEY` patterns. Add `hf iclass rdbl b 01 k aea684a6dab21232` for verify. Fix mock `hf iclass dump` path extraction. |
| `write_iclass_key_calc_success` | Same generic rdbl issue — block 7+ data doesn't match dump | Per-block sequential rdbl list for blocks 6-18 |
| `write_iclass_legacy_success` | Same generic rdbl issue | Per-block sequential rdbl list for blocks 6-18 |

### Group 2: Toast is "Write failed!" but should be a specific error

| Scenario | Root Cause | Fix Required |
|----------|-----------|--------------|
| `write_em4305_dump_fail` | No toast validation — passes on state count alone | Add arg 4 `"toast:Write failed"` to validate |
| `write_iclass_key_calc_fail` | Same — no toast validation | Add arg 4 |
| `write_iclass_tag_select_fail` | Same — no toast validation | Add arg 4 |
| `write_iso15693_restore_fail` | Same — no toast validation | Add arg 4 |
| `write_iso15693_uid_fail` | Same — no toast validation | Add arg 4 |
| `write_mf4k_gen1a_success` | 4K Gen1a write path not implemented in .so — silently fails. No toast validation. | Add arg 4 `"toast:Write failed"` (known .so limitation) |

### Group 3: Wrong toast text

| Scenario | Shows | Should Show | Root Cause |
|----------|-------|-------------|-----------|
| `write_lf_em410x_verify_fail` | "Write failed!" | "Verification failed!" | Write inline verify sees mismatched `lf sea` data (single static response). Needs: write to succeed first (matching `lf sea`/`lf em 410x_read`), then Phase 5 explicit verify to fail (mismatched sequential responses). Missing `lf t55xx detect p 20206666` entry. Single detect response instead of sequential [after-wipe, after-clone]. `.sh` uses `no_verify` but should run Phase 5. |
| `write_mf1k_standard_partial` | "Write failed!" | "Write successful!" (partial) | Single `hf mf wrbl` response (all fail). Needs sequential list: some succeed, some fail → non-empty `write_success_list` → "Write successful!" |

### Group 4: Wrong navigation

| Scenario | Problem | Fix |
|----------|---------|-----|
| `write_mf_possible_7b_success` | `TAG_TYPE = 44` has no entry in `read_list_map.json` → defaults to page 1 pos 0 = "M1 S50 1K 4B" | Change to `TAG_TYPE = 42` (M1 S50 1K 7B, page 1 pos 1) |

---

## Fix Approach Per Scenario

For each scenario:

1. Add arg 4 (`write_toast_trigger`) to the `.sh` file's `run_write_scenario` call
2. Fix the fixture so the .so produces the CORRECT toast
3. Verify by checking `scenario_states.json` shows expected toast AND test passes

### iCLASS Verify Data Pattern

The .so verify reads blocks back with `hf iclass rdbl b XX k KEY` and compares against the dump file. `generate_write_dump.py` creates:
```python
blocks[i] = bytes([i, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])  # for blocks 6-18
```

So per-block rdbl responses must be:
```
Block 06 : 06 01 02 03 04 05 06 07
Block 07 : 07 01 02 03 04 05 06 07
...
Block 18 : 12 01 02 03 04 05 06 07
```

### EM4305 Verify Data Pattern

The .so writes 16 blocks via `lf em 4x05_write N HEXDATA`, then reads back with `lf em 4x05_read N`. The read response must use the `| HEX -` format that `getContentFromRegexG('\\| ([a-fA-F0-9]+) -', 1)` can parse:
```
Block N | AABBCCDD - r/w
```

### LF EM410x Verify-Fail Pattern

Requires sequential responses across write + verify phases:
- `lf t55xx detect`: [after-wipe, after-clone] (sequential list)
- `lf t55xx detect p 20206666`: separate entry (password detect, longer key = matched first)
- `lf sea`: [matching-ID (write), mismatched-ID (Phase 5)]
- `lf em 410x`: [matching, matching, matching (read+write), mismatched (Phase 5)]
- `.sh`: remove `no_verify`, use Phase 5 with `"toast:Verification failed"`

### Elite iCLASS ` e` Flag

Mock `hf iclass dump` path extraction must strip trailing ` e` elite flag:
```python
if fpath.endswith(' e'):
    fpath = fpath[:-2]
```
Without this, dump is created at `...7 e.bin` but iclasswrite.so opens `...7.bin` — file not found, no wrbl commands issued.

---

## Key Discoveries

### LF Clone Write Paths (from real device traces)

**Path A: Clone command** (EM410x, HID, FDX-B, Indala, GProx, Securakey, Viking, Pyramid, Gallagher, Jablotron, Keri, Nedap, Noralsy, PAC, Paradox, Presco, Visa2000, NexWatch)
```
wipe → detect(wiped) → lf <type> clone → detect(cloned) → DRM(b7+b0) → detect+password → lf sea → lf <type> read
```

**Path B: Direct block writes** (AWID, IO ProxII)
```
wipe → detect(wiped) → write b1 → write b2 → write b3 → write b0(config) → detect(cloned) → DRM(b7+b0) → detect+password → lf sea → lf <type> read
```

### Sequential Detect Responses

The .so reads Block0 from `lf t55xx detect` after wipe/clone to compute DRM password config. The mock must return different responses at each stage via sequential list responses.

### T55XX DRM

Password `20206666` written to block 7, password bit set in block 0 config. Every LF clone gets this DRM.

### ISO15693 Write Keywords

`hf15write.so` checks 4 keywords on `hf 15 restore` response:
1. NOT "restore failed"
2. NOT "Too many retries"
3. HAS "Write OK"
4. HAS "done"

Flow order: restore FIRST, then csetuid.

### EM4305 Write — QEMU Works Fine

Previous claim that `write_dump_em4x05()` fails under QEMU was **wrong**. Trace confirms 16 `lf em 4x05_write` commands are issued. The failure is from the verify step: `lf em 4x05_read` has no fixture, so read-back returns empty data → mismatch → "Write failed!".

### iCLASS Elite ` e` Flag in Dump Path

`hf iclass dump k KEY f PATH e` — the ` e` flag gets captured in the mock's path extraction, creating `PATH e.bin`. The .so stores the path as `PATH` (without ` e`), so writes fail with file-not-found. Mock must strip trailing ` e`.

### PM3 Mock Matching Order

`minimal_launch_090.py` sorts fixture keys by length (longest first) and matches by substring. This means:
- `hf iclass rdbl b 01 k aea684a6dab21232` (42 chars) beats `hf iclass rdbl b 01` (22 chars) beats `hf iclass rdbl` (15 chars)
- `lf t55xx detect p 20206666` (28 chars) beats `lf t55xx detect` (16 chars)

Use longer, more specific patterns to override shorter generic ones for different phases (scan vs verify).

---

## Infrastructure

| File | Purpose |
|------|---------|
| `tests/flows/write/includes/write_common.sh` | 5-phase pipeline with Phase 4b toast validation (arg 4) |
| `tests/flows/write/test_writes_parallel.sh` | Parallel runner (FIFO semaphore, Xvfb per worker) |
| `tools/minimal_launch_090.py` | PM3 mock with sequential responses + dump file handlers |
| `tools/generate_write_dump.py` | Creates valid dump files per tag type |
| `tools/fix_lf_write_fixtures.py` | Batch-fixes LF fixtures with sequential detect |

## Scenario Inventory (65 total)

| Group | Count | True Status |
|-------|-------|-------------|
| LF clone (all 20 types) | 20 | 20/20 PASS |
| MFC Standard | 7 | 7/7 PASS |
| MFC Gen1a | 4 | 3/4 PASS (mf4k_gen1a known .so limitation) |
| Ultralight/NTAG | 9 | 9/9 PASS |
| iCLASS | 6 | 3/6 FALSE POSITIVE (elite, legacy, key_calc success) |
| ISO15693 | 5 | 3/5 FALSE POSITIVE (restore_fail, uid_fail no toast check) |
| T55XX | 5 | 5/5 PASS |
| EM4305 | 2 | 0/2 FALSE POSITIVE (both lack toast validation) |
| LF fail/verify-fail | 3 | 2/3 FALSE POSITIVE (em410x_verify_fail wrong toast) |
| MFC Plus 2K | 1 | 1/1 PASS |
| MFC other (mini, possible) | 3 | 1/3 FALSE POSITIVE (partial wrong toast, 7b wrong nav) |
| **Total** | **65** | **52/65 TRUE PASS, 13 FALSE POSITIVE** |

## Real Device Traces

| File | Content |
|------|---------|
| `fdxb_t55_write_trace_20260328.txt` | FDX-B clone → T55XX, full DRM sequence |
| `t55_to_t55_write_trace_20260328.txt` | T55XX restore, block-level verify |
| `awid_write_trace_20260328.txt` | AWID direct block writes (Path B discovery) |
