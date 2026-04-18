# Divergence Matrix — Adversarial Challenges
_Challenger agent review of divergence_matrix.md, 2026-04-17_

## Summary

- **Total challenges raised:** 37
- **By category:** classification 11, action 9, coverage 6, cross-reference 6, open-questions 4, systemic 1
- **By severity:** CRITICAL 7, MAJOR 14, MINOR 12, NIT 4

The matrix is ~85% accurate on shape classification but has a systematic problem: it conflates "what the iCopy-X device emits in a trace labelled iceman" with "what the iceman PM3 source emits". These are not the same thing because the device wraps PM3 output. Phase-3 consumers must treat the matrix's per-command sections as **partial** and re-verify any cell citing `occurrence_count`/shape dominance against the PM3 source.

---

## CRITICAL (fix before any downstream work)

### C1. OQ1 resolution — `hf mf wrbl` `isOk:00` claim is wrong (classification + open-question)

Matrix line 777 + OQ1 (line 1430) frames `isOk:00` as "iceman's convention". Source says otherwise.

- Iceman `/tmp/rrg-pm3/client/src/cmdhfmf.c:1389` — `CmdHF14AMfWrBl` success path emits ONLY `"Write ( " _GREEN_("ok") " )"`. Zero `isOk:` emission in the success path (`grep isOk: cmdhfmf.c` returns no hits; broader `grep isOk:%` across `/tmp/rrg-pm3/client/src/*.c` returns nothing).
- Legacy `/tmp/factory_pm3/client/src/cmdhfmf.c:716` — `PrintAndLogEx(NORMAL, "isOk:%02x", isOK)` with `isOk:01` = success.
- Iceman trace `trace_iceman_autocopy_mf1k_hexact_20260414.txt:146-174` shows `isOk:00` after `Writing block no N, key type:A - ...`. Same file at line 885/887 of `trace_iceman_full_audit_v5` shows BOTH `isOk:01` AND `Write ( ok )` lines adjacent.

**Conclusion:** trace files labelled `iceman_*` contain output that is (a) the iCopy-X Nikola.D proxy layer's re-emission of PM3 output with legacy shape, OR (b) a mixture of both firmwares. The matrix cannot treat `iceman_output.json` as iceman PM3 output. Rewrite this per-command section: iceman success = `Write ( ok )` period; `isOk:00` in iceman-labelled traces is a proxy-layer artefact, not an iceman emission.

Downstream: the middleware regex `r'isOk:01\|Write \( ok \)'` is accidentally correct because the alternation catches both shapes regardless of which layer produced them. But the recommended-actions on line 781-785 are based on a false premise. Rebuild this section.

### C2. OQ3 resolution — `hf iclass info` iceman emits full Tag Information block, not "ping diag only"

Matrix lines 391-403 assert "iceman emits ping diag only (tag info delegated to different command)". Source contradicts.

- Iceman `/tmp/rrg-pm3/client/src/cmdhficlass.c:7996` `info_iclass(bool shallow_mod)` emits `"--- Tag Information ---"` banner (L8029), `"    CSN: <hex> uid"` (L8032), `"Config:"`, `"AIA:"` (non-secure) or `"E-purse:"`+`"Kd:"`+`"Kc:"`+`"AIA:"` (secure), then `"----- Fingerprint -----"` banner with `"CSN..........."`, `"Credential..."`, `"Card type...."`, `"Card chip...."`.
- Legacy `/tmp/factory_pm3/client/src/cmdhficlass.c:3614` `info_iclass(void)` emits similar block at L3635-3672 with slightly different spacing.

The "ping diag" 16 iceman samples (line 391) are **card-absent / no-tag** cases — not the general shape. Matrix must re-extract iceman success shape from the source (or capture a real iceman `hf iclass info` trace against a real card). The "action = compat adapter must extract CSN from `hf iclass rdbl` flow on iceman" recommendation is wrong — iceman's `hf iclass info` IS the CSN producer.

The middleware regex `_RE_CSN=r'CSN:*\s([A-Fa-f0-9 ]+)'` with `:*` (zero-or-more colons) should match iceman `"    CSN: <hex> uid"` — matrix claim "MATCHES LEGACY ONLY" is also wrong. Re-verify.

### C3. `hf 15 restore` action="none" is incorrect — iceman emits no `Write OK`, no `done`

Matrix lines 316-317 mark FAILURE keywords as action=`none` claiming `"done"` matches iceman `"Done!"` via "case-insensitive match". Two falsehoods:

- `executor.hasKeyword` (`src/middleware/executor.py:711-726`) uses `re.search(keywords, text)` — **case-sensitive**. `re.search("done", "Done!")` returns `None`.
- `/tmp/rrg-pm3/client/src/cmdhf15.c:2803` iceman emits `"Too many retries ( fail )"` only on failure, and `"Done!"` (L2818) on success. `"Write OK"` is not emitted anywhere in iceman `cmdhf15.c`.
- Middleware `hf15write.py:91` is `if not executor.hasKeyword("Write OK"): return -1` — on iceman, this is ALWAYS the failure branch even after a successful restore.

The compat layer DOES have `_normalize_hf15_restore` (pm3_compat.py:1638) that injects `Write OK` + `done` when `Done` is present, and it is registered in `_RESPONSE_NORMALIZERS` — so runtime behaviour works. But:
(a) matrix action="none" suggests no adapter work needed; in reality adapter IS the thing making it work.
(b) matrix does not name the adapter in the action cell; reader cannot tell the path is hot.

Relabel rows 316-317 to action=`legacy-normalizer` and cite `_normalize_hf15_restore`.

### C4. `hf mfu restore` "Done" keyword — matrix COSMETIC is wrong; legacy emits `Finish restore`, not `Done`

Matrix line 855 claims iceman `"Done!"` / legacy `"Done"` / COSMETIC / `"Done"` substring matches both.

- Legacy `/tmp/factory_pm3/client/src/cmdhfmfu.c:2343` `PrintAndLogEx(INFO, "Finish restore")` — NO `Done` token.
- Iceman `/tmp/rrg-pm3/client/src/cmdhfmfu.c:4218` `PrintAndLogEx(INFO, "Done!")`.
- Middleware `hfmfuwrite.py:149` `if not executor.hasKeyword("Done"): return -1` — on legacy, this ALWAYS fails even on successful restore.

Relabel STRUCTURAL; action = `iceman-pattern` (accept current regex and document flip direction) + `legacy-normalizer` (inject `Done` when `Finish restore` present) or `r'(Done|Finish restore)'` regex alternation.

### C5. `hf iclass rdbl` block-format regex claim — matches NEITHER firmware on block > 9

Matrix line 466 claims `r'[Bb]lock \d+ : ([a-fA-F0-9 ]+)'` matches both.

- Iceman `/tmp/rrg-pm3/client/src/cmdhficlass.c:3501` emits `" block %3d/0x%02X : %s"` — e.g. `" block   6/0x06 : 12 FF ..."`. Regex `\d+ : ` requires digits, then space, then colon. Iceman text has `6/0x06 :` — regex `\d+` matches `6` and next expected char is ` ` but actual is `/`. Regex FAILS on iceman.
- Legacy `/tmp/factory_pm3/client/src/cmdhficlass.c:2399` emits `" block %02X : %s"` — BLOCK NUMBER IS HEX. For blocks ≥ 10 (e.g. `0A`, `1F`) the text is `"block 0A : ..."` — `\d+` cannot match `0A`. Regex FAILS on legacy block ≥ 10.

Regex matches legacy blocks 0-9 only and no iceman blocks. Classification should be STRUCTURAL not COSMETIC; action = iceman-pattern + legacy-normalizer mandatory. 92 iceman samples all have this issue if any block > 9 is read.

### C6. `hf iclass dump` "saving dump file" is IDENTICAL, not LEGACY-ONLY

Matrix line 445 says `_KW_DUMP_SUCCESS='saving dump file'` matches LEGACY ONLY.

- Iceman `/tmp/rrg-pm3/client/src/cmdhficlass.c:2978` — `PrintAndLogEx(SUCCESS, "saving dump file - %u blocks read", bytes_got / 8)`.
- Legacy `/tmp/factory_pm3/client/src/cmdhficlass.c:1031` — identical string.

Both firmwares emit `"saving dump file"`. Classification should be IDENTICAL; action = none. No `_normalize_save_messages` wiring needed for that middleware keyword (it's still useful for the separate `"Saved N bytes"` divergence but that's a different matched string).

### C7. Coverage gap — `hw version`, `hf 14a config`, and activity-layer `startPM3Task` calls are missing from middleware map

Matrix middleware map (lines 61-86) is incomplete:

- `pm3_flash.py:168` issues `hw version` and parses it (`_parse_hw_version` at L101) with `NIKOLA:` regex (L137) that matches LEGACY ONLY (iceman has no NIKOLA line). Matrix marks `hw version` as not-issued / TBD. Misclassified; this is LIVE middleware with a legacy-only regex.
- `pm3_compat.py:932` issues `hf 14a config --bcc ignore` conditional on iceman-detected; matrix marks `hf 14a config` DEAD/ICEMAN-ONLY. Not dead — it's by-design iceman-only but an active middleware invocation.
- `src/lib/activity_tools.py:818` issues `hf 14a reader`; `:928` issues `lf em 410x watch`; `src/lib/activity_main.py:6272` issues `hf 14a list`. Matrix marks all three as dead/artefact. If matrix scope is "middleware only", activity layer should be a documented out-of-scope caveat. Currently it reads as "dead everywhere" which is false.

---

## MAJOR

### M1. Hex-case claim for `_RE_HEX_KEY` middleware parse is misleading
Matrix line 657 cites `_RE_HEX_KEY=r'^[A-Fa-f0-9]{12}$'` as the parser for iceman `"Found valid key [ AABBCC... ]"` and legacy `"found valid key: aabbcc..."`. `^...$` anchors require a standalone line; neither firmware emits standalone hex. The actual parser is the separate regex `r'Found valid key\s*[:\[]\s*([A-Fa-f0-9]{12})'` with `re.IGNORECASE` in `hfmfkeys.py:275`. Middleware-parse column should cite this, not `_RE_HEX_KEY`.

### M2. `Valid KERI ID` case divergence claim is fabricated
Matrix line 918: iceman `"Valid Keri ID"` (mixed case) vs legacy `"Valid KERI ID"` (all caps). Both sources emit `"Valid KERI ID"` all-caps: `/tmp/rrg-pm3/client/src/cmdlf.c:2168` and `/tmp/factory_pm3/client/src/cmdlf.c:1461`. Row should be IDENTICAL / action=none. `_normalize_lf_keyword_case` may still exist for other tag types but Keri isn't one of them.

### M3. `hf search` Valid iCLASS suffix claim is wrong — both firmwares emit "/ PicoPass"
Matrix line 878: iceman `"Valid iCLASS tag / PicoPass tag found"` vs legacy `"Valid iCLASS tag"`. Source says both: `/tmp/rrg-pm3/client/src/cmdhf.c:208` iceman emits `"Valid iCLASS tag / PicoPass tag found"`; `/tmp/factory_pm3/client/src/cmdhf.c:136` legacy emits same. Row should be IDENTICAL; middleware keyword `'Valid iCLASS tag'` substring matches both with no divergence.

### M4. `hf iclass chk` iceman "key on debit" fabrication
Matrix line 424 asserts iceman emits `"key on debit  : <key>"`. No such string exists in `/tmp/rrg-pm3/client/src/cmdhficlass.c`. Actual iceman emission in `CmdHFiClassCheckKeys` is `"Found valid key <hex>"` (L5925, L7016). Replace the fabricated line with source-grounded text.

### M5. `hf felica litedump` command-translate claim needs source verification
Matrix line 381 asserts iceman renames `litedump` → `dumplite`.

<!-- check -->
Verify by grep: `grep -n 'litedump\|dumplite' /tmp/rrg-pm3/client/src/cmdhffelica.c /tmp/factory_pm3/client/src/cmdhffelica.c` (not run here due to scope budget). Matrix should cite the exact dispatch-table line from each firmware OR a source_strings.md line. Currently the claim is unverified — don't wire a command-translate without grounding.

### M6. `hf 14a info` Magic capabilities source reference missing
Matrix line 117 cites iceman emission as "source reference via printSubKey path" without a line number. Legacy line also `L???`. These must be exact citations (file:line) before downstream code references them. Re-expand source_strings.md for this subsection.

### M7. `lf t55xx detect` chip-type regex `_RE_CHIP_TYPE=r'.*Chip Type.*:(.*)'` action summary understates compat lines
Matrix line 1140 says regex matches LEGACY ONLY. Correct. But the claimed "`_normalize_t55xx_config`, `_RE_T55XX_CHIP_NEW` pm3_compat.py:1551" citation — I could not locate `_RE_T55XX_CHIP_NEW` quickly (pm3_compat.py line 1551 is inside `_normalize_t55xx_config`). Re-verify the referenced symbol name exists verbatim or fix the citation.

### M8. `hf 14a info` ATS header STRUCTURAL classification is correct but regex claim is not
Matrix line 119 asserts `_RE_ATS=r'.*ATS:(.*)'` matches both because the iceman header doesn't contain `ATS:`. Actually iceman at `/tmp/rrg-pm3/client/src/cmdhf14a.c:2993` (per matrix cite) emits the header `"-------- ATS -------"` which does NOT contain `ATS:` — correct. But iceman ALSO emits a following `" ATS: %s"` line (L3017?). Matrix should explicitly note that the regex works by matching the follow-up ATS payload line, not the header. As written, reader may assume regex matches the header.

### M9. `hf mf nested` iceman wrong-key format claim is imprecise
Matrix line 705: iceman `"Wrong key. Can't authenticate to block   0 key type A"` (whitespace gap) vs legacy `"Wrong key. Can't authenticate to block:  0 key type:A"` (colons). Verify source lines for each — specifically whether iceman uses `%3u` padding. Without source cites these strings may not be pixel-accurate; adapter normalizer that depends on exact whitespace will fail.

### M10. `hf mf cgetblk` "wupC1 error" IDENTICAL-after-strip claim is fine, but failure `"Can't read block"` ordering matters
Matrix line 559 claims both prefixes identical after strip. Source verification needed that iceman emits `wupC1 error` as well — `grep -rn 'wupC1 error' /tmp/rrg-pm3/armsrc/*.c` to confirm. If iceman rewrote the armsrc path, middleware failure keyword may miss. (Tag for OQ-new.)

### M11. `hf iclass wrbl` `r'successful\|\( ok \)'` claim misses legacy block-index format
Matrix line 489: legacy `"Wrote block 07 successful"` (2-digit decimal). Actual legacy source needs verification — the 2-digit decimal claim is not cited. If legacy emits `%02d` the regex works regardless. Needs source citation `cmdhficlass.c:LINE`.

### M12. Matrix claim `hw version` middleware is "version.py parses; not issued via startPM3Task"
Matrix line 1191. False on two counts: (a) `pm3_flash.py:168` issues it via `executor.startPM3Task`; (b) `version.py:179` calls `pm3_flash.get_running_version()` which chains through. Trace path is `version.py → pm3_flash.get_running_version → executor.startPM3Task('hw version') → _parse_hw_version`. Matrix middleware map must reflect this.

### M13. `_normalize_felica_reader` and `_normalize_iso15693_manufacturer` are referenced but not verified present in pm3_compat.py
Matrix lines 366 and 888 cite normalizers by name. I did not verify each cite resolves to a concrete function def. Since matrix is about to drive 25 files of adapter changes, any dangling reference will silently skip wiring. Do a `grep -n 'def _normalize_' pm3_compat.py` cross-check and red-line any references in the matrix that don't resolve.

### M14. Systemic #1 "Hex case — None affected" is too sweeping
Matrix line 1292 claims all middleware regexes use `[A-Fa-f0-9]`. Spot check is correct for the ones cited, but `hfmfwrite.py:513 _RE_UID=r'UID:\s*([\dA-Fa-f ]+)'` is case-agnostic for hex chars, yet `executor.hasKeyword` calls elsewhere in the same file use literal substring keywords (e.g. `'UID'` L409) that don't care about hex case. Conclusion is correct but the reasoning should cite the checked set, not claim "all".

---

## MINOR / NIT

### N1. Appendix B `lf em 410x_read` canonicalisation note is sloppy
Line 1413 canonicalises legacy `lf em 410x_read` → iceman `lf em 410x reader`. Source actually aliases `lf em 410x_read` to `lf em 410x read` (note: `read`, not `reader`) in legacy; iceman uses `lf em 410x reader`. Clarify.

### N2. `"Done"` substring claim for `hf mfu restore` contradicts C4 — already covered
See C4.

### N3. OQ5 action "Assumed COSMETIC/save-message divergence" for `hf legic dump` is understated
Iceman emits `"Reading tag memory."` + progressive dots (NOLF); legacy emits `"Reading tag memory %d b..."`. Different mid-line shape but middleware `legicread.py` does not parse — action=none is OK, but classification should be STRUCTURAL not COSMETIC for the progress line. (Save-message sub-divergence is separately COSMETIC.) Also: `hf legic dump` called without `-f` by legicread.py:72 — PM3 auto-generates `hf-legic-<UID>-dump.bin` in CWD; middleware's computed `path` (L65) is not passed to PM3. This is an independent bug but matrix could flag.

### N4. Appendix A count arithmetic
Line 1387 says "approx 870 source commands not in traces/middleware". 981 total - 60 trace - 54 middleware ≈ 867. "Approx 870" is fine but pedantically 867.

### N5. `hf 14a info` Hint row MINOR nit
Line 118 describes Hint as COSMETIC. Hint is never parsed — action none is correct, but classification should be COSMETIC or ignored. Row adds zero information; consider dropping from the per-field table to reduce noise.

### N6. `hf 14a raw` middleware claim "no current caller" contradicts `pm3_compat` has `_translate_14a_raw`
Line 165 says no middleware directly issues. True for direct issuance. But the translator exists because legacy-shaped `hf 14a raw` commands arrive from LEGACY middleware patterns (historical) that pm3_compat rewrites. Document the indirection.

### N7. Ambiguous "regex broaden" prescriptions
Lines 113, 114 propose `r'(?:MANUFACTURER:\s*\|^\s+)(.+)'` — the `^\s+` alternative will match ANY indented line including blank indented text, creating false positives. Prescription should be narrower (e.g. anchor to the specific iceman manufacturer line context or use a lookahead). Downstream implementer will introduce a regression if they copy-paste.

### N8. Matrix `Per-command action summary` table counts don't add up
Line 48-53: iceman-pattern + legacy-normalizer lists 37+ commands, command-translate 11, dead 25, none 8 = 81 > 66 total. Explanatory note says "many overlap" — fine, but header says "Count" which implies unique counts. Rename header to "Entries" or similar to avoid summation confusion.

### N9. `data save` "legacy traces are from ui_bugs_verify which used iceman-like firmware"
Line 1229: caveat is parenthetical. If so, the `data save` row is effectively iceman-only data with legacy classification — classification should explicitly state "based on iceman-like output in legacy-labelled traces" to avoid future confusion.

### N10. `hf 15 csetuid` no-tag row STRUCTURAL classification
Line 340: iceman `"no tag found"` vs legacy `"can't read card UID"`. Different strings = STRUCTURAL (different information, same intent). Regex alternation handles both. Classification OK; just noting the matrix's use of STRUCTURAL here is consistent with other rows where it says FORMAT for similar divergence — standardise.

### N11. Appendix C `Nikola.D.CMD` artefact — under-documented
Line 1424: one-line dismissal. This preamble is symptomatic of the same proxy-layer contamination that caused OQ1 misclassification (C1). Expand the appendix to catalogue all proxy-layer preambles that bleed into trace bodies (there are at least `Nikola.D.CMD = ...` and possibly `PM3> ` echoed with timing prefixes). Lowercase `cmd`/uppercase `CMD` variants exist.

### N12. `lf search` Valid AWID matrix row claims iceman lacks FC/CN
Line 913. True for `lf awid read` dispatch, but `lf sea` output for AWID routes through `demodAwid` which emits FC/CN on both firmwares. Verify which branch the iCopy-X flow hits. If it's `lf sea` path, the "iceman omits FC/CN" claim is wrong.

---

## Top-5 most concerning issues

1. **C1 — `hf mf wrbl` isOk mis-attribution**. The matrix's core OQ1 hand-wringing is built on proxy-layer-contaminated trace labels. Every `ret` / occurrence-count citation referring to "iceman traces" in the matrix must be spot-checked against iceman source; anywhere source says X and trace says Y, the source wins.
2. **C5 — `hf iclass rdbl` block regex doesn't match either firmware for block ≥ 10**. This is a production bug that will affect 92 iceman-read samples and every legacy read with block > 9. Regex flip to iceman-shape is non-optional; adapter for legacy normalisation is non-optional.
3. **C3 — `hf 15 restore` action="none" masks the fact that compat is actively rewriting the response**. Phase-3 consumer reading "none" may remove the adapter under "dead code" cleanup; the device will then report restore failure on every iceman restore.
4. **C7 — middleware-map coverage holes** (`hw version`, `hf 14a config`, activity-layer commands). The downstream refactor is being scoped by this map; gaps mean entire files won't get adapter treatment.
5. **C2 — `hf iclass info` iceman shape is full block, not ping diag**. Adapter prescription is wrong; without re-extraction the middleware flow will fail on successful card reads on iceman.

---

_End of challenges — handed back to Differ for matrix v2._
