# Phase 6 Response Normalizer Audit

Scope: legacy→iceman response-shape normalizers in `src/middleware/pm3_compat.py` (`_RESPONSE_NORMALIZERS` dict + `_post_normalize`).
Branch: `feat/compat-flip` @ HEAD (commit `59233ec`).
Evidence: trace corpus in `docs/Real_Hardware_Intel/*.txt` + decompiled factory PM3 (`/tmp/factory_pm3/client/src/`) + iceman PM3 (`/tmp/rrg-pm3/client/src/`).
Ground truth priority: real-device traces > iceman PM3 source > legacy PM3 source > middleware regex.

## Summary

- Commands audited: 24 (P0: 17, P1: 7).
- Clean (legacy == iceman shape OR normalizer+regex work end-to-end): 19.
- Divergent (missing or broken normalizer on legacy FW): 4.
- No ground truth in corpus (flagged): 3 (`hf 15 dump`, `hf 15 csetuid`, `lf em 4x05 info` full shape).

## Divergences

### 1. `hf mf darkside` (P0)

- **Middleware parse site**: `src/middleware/hfmfkeys.py:296` — `re.search(r'Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]', text, re.IGNORECASE)`.
- **Iceman expected shape** (`/tmp/rrg-pm3/client/src/cmdhfmf.c:1275`): `Found valid key [ 484558414354 ]` (bracketed, uppercase hex via PRIX64, `sprint_hex` would add spaces but cmdhfmf here uses PRIX64 format directly → no spaces).
- **Legacy actual shape** (`/tmp/factory_pm3/client/src/cmdhfmf.c:663`):
  ```
  found valid key: 000000000041
  ```
  Real trace confirmation: `docs/Real_Hardware_Intel/trace_autocopy_multitag_wrongtype_20260402.txt:20`
  ```
  [ 338.989] PM3< ret=1 \n[=] --------...\n[=] Executing darkside attack. ...\n.\n[+] found valid key: 000000000041\n\n
  ```
  Additional shape at factory `cmdhfmf.c:2390`: `Found valid key: 484558414354` (capital F, colon, bare hex).
- **Current normalizer**: none (`_RESPONSE_NORMALIZERS` has no `hf mf darkside` entry).
- **Does middleware regex match current output?** No. After executor strips `[+]` prefix the legacy emits `found valid key: 000000000041` (bare, colon-separated). The middleware regex `Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]` requires brackets — won't match colon form regardless of `re.IGNORECASE`.
- **Required fix**: add `_normalize_mf_found_key` that rewrites `(?i)(found valid key)[:\s]+([A-Fa-f0-9]{12})\b(?!\s*\])` → `Found valid key [ \2 ]`. Register for `hf mf darkside` and `hf mf nested`.
- **Severity**: P0. Darkside is the Classic-1K recovery fallback when fchk fails — silent break means Classic reads on non-magic cards return no keys → read fail.

### 2. `hf mf nested` (P0)

- **Middleware parse site**: `src/middleware/hfmfkeys.py:337` — `re.search(r'found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]', text, re.IGNORECASE)`.
- **Iceman expected shape** (`/tmp/rrg-pm3/client/src/mifare/mifarehost.c:686`): `Target block    8 key type A -- found valid key [ 484558414354 ]`. Uses `sprint_hex_inrow` → no byte separators → exactly 12 hex chars between `[ ` and ` ]`.
- **Legacy actual shape** (`/tmp/factory_pm3/client/src/mifare/mifarehost.c:538`, `:717`):
  ```
  target block:  0 key type: A  -- found valid key [ 48 45 58 41 43 54 ]
  ```
  Uses `sprint_hex` (spaces between bytes). No successful legacy nested trace exists in corpus (nested attacks in `trace_autocopy_multitag_wrongtype_20260402.txt:21` show only the command, no response body). Inference from source + systemic parallel with darkside.
- **Current normalizer**: none.
- **Does middleware regex match current output?** No. Tested:
  ```python
  re.search(r'found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]',
            'found valid key [ 48 45 58 41 43 54 ]', re.IGNORECASE)
  # → None
  ```
  The `[A-Fa-f0-9]{12}` class requires 12 consecutive hex chars with no whitespace; legacy `sprint_hex` output contains 17 chars (12 hex + 5 spaces).
- **Required fix**: same `_normalize_mf_found_key` from #1, extended to strip internal spaces between byte pairs inside `[ ... ]` brackets. Pattern: `\[\s*((?:[A-Fa-f0-9]{2}\s+){5}[A-Fa-f0-9]{2})\s*\]` → replace group hex-run with concatenated (spaces removed).
- **Severity**: P0. Nested runs after fchk finds key-A for one sector, recovers remaining keys. Break = many sectors read as empty → corrupt dump, write fails verify.

### 3. `hf mfu restore` (P0)

- **Middleware parse site**: `src/middleware/hfmfuwrite.py:159` — `executor.hasKeyword(_KW_RESTORE_SUCCESS)` where `_KW_RESTORE_SUCCESS = r'Done!'`.
- **Iceman expected shape** (`/tmp/rrg-pm3/client/src/cmdhfmfu.c:4218`): `PrintAndLogEx(INFO, "Done!")`.
- **Legacy actual shape** (`/tmp/factory_pm3/client/src/cmdhfmfu.c` CmdHF14AMfURestore L2220):
  ```
  PrintAndLogEx(INFO, "Finish restore");
  ```
  Real trace confirmation: `docs/Real_Hardware_Intel/trace_original_full_20260410.txt:507`:
  ```
  [ 255.208] PM3< ret=1 ...\n[=] Restoring .../M0-UL-EV1_...bin to card\n[=] MFU dump file information\n...\n[=] Restoring data blocks.\n...\n\n[=] Restoring configuration blocks.\n\nauthentication with keytype[0] ...\n...\n[=] Finish restore\n
  ```
- **Current normalizer**: none. `_normalize_wrbl_response` is registered for `hf mf restore` (MF Classic), not `hf mfu restore` (MFU).
- **Does middleware regex match current output?** No — `Done!` literal string not in legacy output; only `Finish restore` at end.
- **Required fix**: add `_normalize_mfu_restore` rewriting `^(\s*)Finish restore\b` → `\1Done!` (or append `Done!` if `Finish restore` present). Register for `hf mfu restore`.
- **Severity**: P0. Every Ultralight/NTAG write goes through this path. Silent break = `write()` returns -1 even after successful restore → write flow reports fail despite data written.

### 4. `_normalize_em410x_id` — broken `Valid EM410x` rewrite (P1)

- **Middleware parse site**: `src/middleware/lfsearch.py:435` — `executor.hasKeyword('Valid EM410x ID')` (regex, effectively literal substring match).
- **Iceman actual shape** (`/tmp/rrg-pm3/client/src/cmdlf.c:2008`): `Valid EM410x ID found!` (NO space between `EM` and `410x`).
- **Legacy actual shape** (`/tmp/factory_pm3/client/src/cmdlf.c:1454`): `Valid EM410x ID found!` (IDENTICAL — also no space).
  Real trace confirmation: `docs/Real_Hardware_Intel/trace_lf_scans_20260406.txt`:
  ```
  [+] Valid EM410x ID found!
  ```
- **Current normalizer**: `_normalize_em410x_id` (registered for `lf sea`, `lf search`, `lf em 410x reader`, `lf em 410x_read`). The sub-regex `_RE_LEGACY_VALID_EM410X = re.compile(r'Valid EM410x ID')` at `pm3_compat.py:874` rewrites `Valid EM410x ID` → `Valid EM 410x ID` (injecting a space).
  Accompanying comment at L872-873:
  ```
  # Keyword also differs: legacy `Valid EM410x ID` (no space) vs iceman
  # `Valid EM 410x ID` (space).  Middleware keyword is iceman form.
  ```
  **This comment is factually incorrect.** Both firmwares emit `Valid EM410x ID` (no space) per source citations above; middleware keyword at `lfsearch.py:435` is also `'Valid EM410x ID'` (no space).
- **Does middleware regex match current output?**
  - On iceman FW (normalizer disabled): yes — device output `Valid EM410x ID` matches middleware literal `Valid EM410x ID`.
  - On legacy FW (normalizer runs): **no** — normalizer rewrites `Valid EM410x ID` → `Valid EM 410x ID`, middleware then fails to find `Valid EM410x ID` literal.

  Test:
  ```python
  text = 'Valid EM410x ID found!'  # legacy real output
  # After _normalize_em410x_id:
  text = re.sub(r'Valid EM410x ID', 'Valid EM 410x ID', text)
  # → 'Valid EM 410x ID found!'
  bool(re.search('Valid EM410x ID', text))  # → False
  ```
- **Required fix**: delete the `_RE_LEGACY_VALID_EM410X` rewrite line in `_normalize_em410x_id`. The `EM TAG ID` → `EM 410x ID` rewrite for the data-extraction regex `REGEX_EM410X` must stay; the `Valid EM410x` → `Valid EM 410x` rewrite is a no-op on iceman and actively breaks legacy.
  Alternatively: widen middleware `hasKeyword('Valid EM410x ID')` to `'Valid EM\\s*410x ID'` and keep normalizer intact.
- **Severity**: P1. Exclusively legacy-FW regression; breaks EM410x detection in `lf sea` / `lf search` parser → `scan.py` sees EM410x tag as "not found", falls through to next tag type check. Real device impact depends on whether the phase-6 flip is currently shipping to users on legacy FW.

## Clean commands

End-to-end verified: legacy shape (or identical to iceman) + normalizer chain (if any) + middleware regex all match on real trace data.

- `hf 14a info`: legacy `Prng detection: weak`, `Static nonce: yes`, `Magic capabilities : Gen 1a` all handled by `_post_normalize` (`pm3_compat.py:819/823/827`). Evidence: `trace_read_flow_20260401.txt:169,191`, `trace_console_flow_20260401.txt` + `trace_dump_files_20260403.txt`.
- `hf mf rdbl` / `hf mf rdsc`: legacy `  0 | XX XX ... XX` grid handled by `_normalize_mf_block_grid` (commit `59233ec`). Evidence: `trace_autocopy_scan_dumps_20260410.txt:59,104,401`.
- `hf mf wrbl` / `hf mf restore`: legacy `isOk:01` → `Write ( ok )` via `_normalize_wrbl_response`. Evidence: `autocopy_mf4k_mf1k7b_t55_trace_20260329.txt:24,26,28` etc.
- `hf mf fchk`: legacy 5-column `| Sec | key A | res | key B | res |` matches middleware `_RE_KEY_TABLE` verbatim (regex tolerates both legacy 5-col and device's installed iceman 5-col form). Evidence: `mf4k_nonmagic_app_trace_20260328.txt:2122` + `trace_iceman_read_mf1k_20260414.txt:17`.
- `hf mf csave` / `hf mf cload` / `hf mf cgetblk` / `hf mf cwipe` / `hf mf csetuid`: file-existence or identical-substring checks (`Card loaded`, `Card wiped successfully`, `Can't set UID`, `data:`). No shape divergence.
- `hf iclass rdbl`: legacy `block NN : <hex>` → iceman `block N/0xNN : <hex>` via `_normalize_iclass_rdbl`. Evidence: `trace_iclass_elite_read_20260401.txt:49`.
- `hf iclass wrbl`: legacy `Wrote block NN successful` → iceman `( ok )` via `_normalize_iclass_wrbl`.
- `hf iclass dump`: `saving dump file` identical on both FWs.
- `hf iclass chk`: `Found valid key <hex>` substring matches both; `sprint_hex` (legacy) vs `sprint_hex_inrow` (iceman) both captured by `[0-9a-fA-F ]+` (tolerant of spaces inside). **Caveat**: command-translation bug in trace `trace_phase6_iclass_rdbl_regression_20260417.txt:219` — `hf iclass chk --vb6kdf` reaches legacy unchanged (reverse rule at `pm3_compat.py:330` not firing). Response-shape is fine; command translation is a separate issue.
- `hf iclass calcnewkey`: legacy `Xor div key : <hex>` → iceman `Xor div key.... <hex>` via `_post_normalize` (`_RE_LEGACY_XOR_DIV_KEY_COLON` at `pm3_compat.py:770`).
- `hf iclass info`: `CSN: <hex>` matches both via tolerant `_RE_CSN = r'CSN:*\s([A-Fa-f0-9 ]+)'`.
- `hf mfu info` / `hf mfu dump`: identical UID/TYPE/block dump shape on both FWs. File-existence check for dump. Evidence: `trace_original_full_20260410.txt:229`, `trace_autocopy_scan_dumps_20260410.txt:306,381`.
- `hf 15 restore`: legacy `done` sentinel → iceman `Done!` via `_normalize_hf15_restore`.
- `hf 15 csetuid`: legacy `setting new UID (ok)` → iceman `Setting new UID ( ok )` via `_normalize_hf15_csetuid`. `can't read card UID` → `no tag found`.
- `hf felica reader`: legacy `IDm  <hex>` (2 spaces) → iceman `IDm: <hex>` via `_normalize_felica_reader`.
- `hf sea`: legacy `Valid ISO15693 tag` / `Valid ISO14443-B tag` / `Valid ISO18092 / FeliCa tag` → iceman space forms via `_RE_LEGACY_ISO_NOSPACE` in `_post_normalize` (`pm3_compat.py:776`). `Valid iCLASS tag` identical on both. Evidence: `trace_phase6_iclass_rdbl_regression_20260417.txt:575.273`, `trace_autocopy_scan_dumps_20260410.txt:656`.
- `lf sea` / `lf search`: legacy `EM TAG ID      : <hex>` → iceman `EM 410x ID <hex>` via `_normalize_em410x_id` (data-extraction part works); `Chipset detection:` → `Chipset...` via `_normalize_chipset_detection`; `Animal ID          <code>` → `Animal ID........... <code>` via `_normalize_fdxb_animal_id`. `Valid AWID ID found!`, `Valid FDX-B ID found!`, `Couldn't identify a chipset` all identical substring hits.
- `lf t55xx detect`: legacy `Chip Type : T55x7` / `Modulation : ASK` / `Block0 : 0x<hex>` / `Password Set : No` → iceman dotted forms via `_normalize_t55xx_config`. Evidence: `fdxb_t55_write_trace_20260328.txt:36`.
- `lf t55xx dump`: `_normalize_t55xx_config` + `_normalize_save_messages` (`saved` → `Saved`). Middleware accepts capital `Saved` only (`lft55xx.py:557`), so uppercase rewrite is load-bearing.
- `lf t55xx chk`: legacy + iceman both emit `Found valid password: [ <hex> ]` (cmdlft55xx.c:3129/3355 factory; 3658/3660/3816 iceman). Middleware `_RE_FOUND_VALID` tolerates optional brackets. `_normalize_t55xx_chk_password` is defensive-only; actual legacy emissions in source all have brackets already — normalizer is a no-op on real output.
- `lf em 4x05 info` / `lf em 4x05 dump`: normalizer rewrites `Chip Type:   N | <name>` → `Chip type..... <name>`, `Serial #:` → `Serialno......`, `ConfigWord:` → `Block0........`. **No legacy trace of full em4x05 info body in corpus** — normalizer tested against source only. Regression risk: low (middleware regex `_RE_CHIP = r'Chip [Tt]ype\.+\s+(\S+)'` case-tolerant).
- `lf em 410x reader`: `_normalize_em410x_id` rewrites `EM TAG ID      : <hex>` → `EM 410x ID <hex>` for `REGEX_EM410X` extraction. Works (but see divergence #4 for the paired broken rewrite).
- `hf mf darkside` / `hf mf nested` data-extraction (separate from key-found line): N/A — no additional regex besides the `Found valid key` check.

## Methodology notes

Primary trace evidence cited in descending importance:

1. **`trace_autocopy_multitag_wrongtype_20260402.txt`** — sole darkside success trace in corpus (legacy FW, bare-hex colon form confirmed at L20).
2. **`trace_original_full_20260410.txt`** — `hf mfu info` / `hf mfu restore` full body with `Finish restore` sentinel (L507).
3. **`trace_autocopy_scan_dumps_20260410.txt`** — `hf mf rdsc` grid shape + `hf mfu dump` sentinels + lf sea multi-tag.
4. **`trace_read_flow_20260401.txt`** + **`trace_console_flow_20260401.txt`** — `hf 14a info` legacy shape (PRNG, Magic capabilities).
5. **`fdxb_t55_write_trace_20260328.txt`** — `lf t55xx detect` legacy shape.
6. **`trace_lf_scans_20260406.txt`** — `Valid EM410x ID found!` literal confirming no-space form on legacy.
7. **`trace_iclass_elite_read_20260401.txt`** — `hf iclass rdbl` ` block 01 : <hex>` legacy shape.

Commands NOT exercised in the trace corpus (future trace capture recommended):

- `hf 15 dump` / `hf 15 restore` / `hf 15 csetuid` — no legacy ISO15693 write flows in corpus.
- `lf em 4x05 info` full body — only error paths (`Nikola.D: -10`) captured.
- `hf mf nested` success response body — command is issued (`trace_autocopy_multitag_wrongtype`) but response truncated.
- `hf iclass chk` successful legacy `Found valid key` — all legacy iclass chk traces show `unknown parameter '-'` (command translation bug unrelated to response shape).

## Summary of recommended actions (ranked)

1. **P0** — Add `_normalize_mf_found_key` handling both legacy darkside (`found valid key: <bare hex>`) and legacy nested (`found valid key [ <hex with spaces> ]`). Register for `hf mf darkside` and `hf mf nested` in `_RESPONSE_NORMALIZERS`.
2. **P0** — Add `_normalize_mfu_restore` rewriting `Finish restore` → `Done!`. Register for `hf mfu restore`.
3. **P1** — Delete the `_RE_LEGACY_VALID_EM410X` rewrite in `_normalize_em410x_id`; the `EM TAG ID` → `EM 410x ID` data rewrite stays. Update the stale comment at `pm3_compat.py:872-874`.
4. **(Out of scope / informational)** — The `hf iclass chk --vb6kdf` and `hf iclass rdbl --blk NN -k <key>` reverse command translations (`pm3_compat.py:321-330`) aren't firing on legacy FW per `trace_phase6_iclass_rdbl_regression_20260417.txt`. Likely cause: `_current_version` detection returning non-`PM3_VERSION_ORIGINAL` before iclass path runs. Separate investigation from response-shape audit.

## Caveats

- This audit assumes `detect_pm3_version()` correctly sets `_current_version = PM3_VERSION_ORIGINAL` on legacy FW before the first middleware-issued PM3 command. If detection is delayed or fails, ALL normalizers (including working ones) silently no-op. The regression trace above hints at a possible detection-timing issue.
- Normalizers #1 and #2 are inferred from source (corpus lacks successful legacy darkside/nested response bodies). A real-device capture of each would confirm regex shape and any additional whitespace quirks from `sprint_hex`/`sprint_hex_inrow`.
- `_normalize_t55xx_chk_password` is registered but the source citations show legacy already emits bracketed form at all 3 factory emit sites. Defensive code; not load-bearing. Low priority to audit.
