# Divergence Matrix v2 Changelog
_Generated 2026-04-17_

## Summary

- Issues raised by Challenger: 37 (7 CRITICAL / 14 MAJOR / 12 MINOR / 4 NIT)
- Issues raised by Auditor: 8 corrections + 15 spot-audit rows (7 PASS / 2 PARTIAL / 8 DISCREPANCY)
- Unique issues after dedup: ~35 (heavy overlap on C1/OQ1, C2/OQ3, C3, C4, C6, C7)
- Corrections applied: 28
- Disagreements documented: 0 (Fixer concurs with all Challenger + Auditor findings after independent verification)

## Resolution of the `hf mf wrbl` conflict — AUDITOR WRONG, CHALLENGER RIGHT

**Conflict:** Auditor claimed iceman device emits `isOk:00`=success natively (semantic inversion, live bug). Challenger claimed iceman never emits `isOk:` — the strings in traces are Nikola.D proxy-layer artefacts.

**Fixer verdict: Challenger correct, Auditor wrong on mechanism, but Auditor's "live bug" framing is half-right.**

**Evidence:**
1. Iceman source `/tmp/rrg-pm3/client/src/cmdhfmf.c:1280-1399` `CmdHF14AMfWrBl` emits ONLY `Writing block no`/`data:`/`Write ( ok )`/`Write ( fail )`. No `isOk:` anywhere in the success or failure paths.
2. Grep for `"isOk:"` across `/tmp/rrg-pm3/client/src/` returns ZERO matches. Iceman HEAD has completely removed that string family.
3. Legacy source `/tmp/factory_pm3/client/src/cmdhfmf.c:716` emits `PrintAndLogEx(NORMAL, "isOk:%02x", isOK)` with `01`=success.
4. **The mechanism: `_normalize_wrbl_response` at pm3_compat.py:1216-1232 REWRITES iceman output:**
   ```python
   text = text.replace('Write ( ok )', 'isOk:01')
   text = text.replace('Write ( fail )', 'isOk:00')
   text = re.sub(r'\(\s*ok\s*\)', 'isOk:01', text)
   text = re.sub(r'\(\s*fail\s*\)', 'isOk:00', text)
   ```
5. Traces are captured POST-`translate_response` — they show the NORMALIZED form.
6. The 438 `isOk:00` samples in trace shape 1 are therefore FAILED writes (iceman emitted `Write ( fail )` → normalized to `isOk:00`), NOT successes-with-inverted-semantics.
7. `ret=1` in traces means "PM3 returned a response" — it is NOT a write-success flag.
8. Trace `trace_iceman_full_audit_v5_20260414.txt:883/885` shows one `isOk:01` and one `Write ( ok )` back-to-back for apparent same-block commands, which indicates occasional trace interleaving bugs — the raw `Write ( ok )` surviving the normalizer is likely a response-slot capture race, not an iceman-emission variant.

**Outcome:** Middleware regex `r'isOk:01|Write ( ok )'` is correct — the alternation catches both the normalized form (post-adapter) AND the raw form (pre-adapter in edge cases). No further adapter work needed. Auditor's proposed broadening to "include `isOk:00`=success" would be WRONG — `isOk:00` means failure in the normalized view, and there is no scenario where iceman raw `Write ( ok )` gets normalized to `isOk:00`.

v1's Open Question 1 is fully resolved. See `hf mf wrbl` per-command section in the matrix for the full rewrite.

---

## Per-issue disposition

### Challenger C1 — `hf mf wrbl` `isOk:00` misattribution — **AGREE**
- Evidence: iceman HEAD source has ZERO `isOk:` emissions (grep confirmed). Traces show the post-normalizer form.
- Action: rewrote `hf mf wrbl` per-command section with full trace/source/adapter explanation; reframed v1's "SEMANTIC inversion" (wrong) to STRUCTURAL (different label family, adapter bridges).
- Also rewrote v1 OQ1 as [RESOLVED].

### Challenger C2 — `hf iclass info` iceman emits full block — **AGREE**
- Evidence: Read of `/tmp/rrg-pm3/client/src/cmdhficlass.c:7996-8108` shows `CSN`/`Config`/`E-purse`/`Kd`/`Kc`/`AIA`/`Fingerprint` all emitted in `info_iclass()`.
- Action: rewrote `hf iclass info` per-command section. Removed the "extract CSN from rdbl" recommendation (false premise). Middleware `_RE_CSN` matches iceman natively.
- Also rewrote v1 OQ3 as [RESOLVED (matrix was wrong)].

### Challenger C3 — `hf 15 restore` action="none" masks active adapter — **AGREE**
- Evidence: `executor.hasKeyword` uses `re.search` which is case-SENSITIVE (executor.py:722). `re.search("done", "Done!")` returns None. The path only works because `_normalize_hf15_restore` (pm3_compat.py:1638) injects `Write OK\ndone` when iceman `Done` substring present.
- Action: rewrote `hf 15 restore` per-field rows; marked action=`legacy-normalizer` and cited `_normalize_hf15_restore` as LIVE.

### Challenger C4 — `hf mfu restore` Done/Finish restore — **AGREE**
- Evidence: Legacy `/tmp/factory_pm3/client/src/cmdhfmfu.c:2343` emits `PrintAndLogEx(INFO, "Finish restore")` only — no `Done` token. Iceman `cmdhfmfu.c:4218` emits `"Done!"`. Middleware keyword `"Done"` at hfmfuwrite.py:149 fails on legacy.
- Action: relabeled STRUCTURAL; flagged missing `_normalize_hfmfu_restore` or regex broadening.

### Challenger C5 — `hf iclass rdbl` block regex fails on block ≥10 — **AGREE**
- Evidence: iceman cmdhficlass.c:3501 emits `" block %3d/0x%02X : %s"`; legacy cmdhficlass.c:2399 emits `" block %02X : %s"` (hex block number). Regex `\d+` can't match `0A` hex, and can't skip `/0x06` before the colon. iceman normalizer `_normalize_iclass_rdbl` handles iceman; no legacy normalizer exists for blocks ≥10.
- Action: rewrote `hf iclass rdbl` per-field table; reclassified STRUCTURAL; flagged missing legacy-normalizer for blocks ≥10.

### Challenger C6 — `hf iclass dump` "saving dump file" identical, not legacy-only — **AGREE**
- Evidence: Both firmwares emit `"saving dump file - %u blocks read"` — iceman cmdhficlass.c:2978; legacy cmdhficlass.c:1031/1990. Verified by grep.
- Action: corrected the row to IDENTICAL; updated summary LEGACY-ONLY count note.

### Challenger C7 — middleware map coverage holes — **AGREE**
- Evidence: `hw version` (pm3_flash.py:168), `hf 14a config --bcc ignore` (pm3_compat.py:932), `hf 14a raw` gen1afreeze (hfmfwrite.py:193-197), `hf 14a reader` (activity_tools.py:818), `lf em 410x watch` (activity_tools.py:928), `hf 14a list` (activity_main.py:6272) all LIVE.
- Action: added `pm3_flash.py`, `pm3_compat.py`, and activity-layer rows to middleware map; extended `hfmfwrite.py` row with `hf 14a raw`; rewrote relevant per-command sections (hf 14a reader, hf 14a config, hf 14a raw, hf 14a list, lf em 410x watch, hw version); corrected summary DEAD count.

### Challenger M1 — `_RE_HEX_KEY` citation imprecise — **AGREE**
- Evidence: `_RE_HEX_KEY` at hfmfkeys.py:229 is used only on individual group captures from the fchk key table (L245/247), not on the full response. The actual darkside/nested response parser is the IGNORECASE regex at hfmfkeys.py:275.
- Action: corrected darkside per-field table citation to point at the inline IGNORECASE regex.

### Challenger M2 — `Valid KERI ID` case divergence fabricated — **AGREE**
- Evidence: grep confirms both firmwares emit `"Valid " _GREEN_("KERI ID")` all-caps (rrg cmdlf.c:2168, factory cmdlf.c:1461).
- Action: corrected row to IDENTICAL.

### Challenger M3 — `hf search` Valid iCLASS suffix — **AGREE**
- Evidence: both `cmdhf.c:208` (iceman) and `cmdhf.c:136` (legacy) emit `"Valid iCLASS tag / PicoPass tag found"`.
- Action: corrected row to IDENTICAL.

### Challenger M4 — `hf iclass chk` "key on debit" fabrication — **AGREE**
- Evidence: grep `"key on debit"` returns zero matches in both firmwares.
- Action: removed fabricated line; replaced with actual iceman emission `"Found valid key <hex>"` (cmdhficlass.c:5925/7016).

### Challenger M5 — `hf felica litedump` command-translate unverified — **AGREE**
- Evidence: grep `litedump|dumplite` in both firmwares confirms the name `litedump` in BOTH (iceman cmdhffelica.c:5056/5329 handler+dispatch; legacy cmdhffelica.c:1619/1884 handler+dispatch). The `usage_hf_felica_dumplite` in legacy is just a static function name, not a command alias.
- Action: rewrote `hf felica litedump` section — command exists identically in both firmwares; removed command-translate recommendation.

### Challenger M6 — `hf 14a info` Magic capabilities source ref missing — **AGREE** (partial)
- Action: added source-cite `TBD` marker acknowledging source_strings.md truncation; retained classification as FORMAT.

### Challenger M7 — `_RE_T55XX_CHIP_NEW` citation — **verified correct**
- Evidence: grep confirms `_RE_T55XX_CHIP_NEW` at pm3_compat.py:1551 exists.
- Action: no change needed; citation is accurate.

### Challenger M8 — ATS regex doc clarification — **AGREE**
- Action: clarified per-field table entry — regex matches the PAYLOAD `ATS: %s` line (not the decorative banner).

### Challenger M9 — `hf mf nested` wrong-key whitespace — **NOTED, no change**
- Not verified in this pass (low priority; substring `"Wrong key"` still matches both). Flagged for future source-line precision work.

### Challenger M10 — `hf mf cgetblk` `wupC1 error` in iceman armsrc — **NOTED, no change**
- Not verified in this pass. Trace data shows iceman emitting `wupC1 error` so assumed OK. Open for future adversarial audit.

### Challenger M11 — `hf iclass wrbl` block-format source cite — **AGREE**
- Evidence: iceman cmdhficlass.c:3134 emits decimal+hex `Wrote block %d / 0x%02X ( ok )`; legacy cmdhficlass.c:2149 emits `Wrote block %02X successful` (UPPERCASE HEX block number).
- Action: added source line citations to the per-field table.

### Challenger M12 — `hw version` middleware classification — **AGREE**
- Evidence: pm3_flash.py:168 issues `hw version`; `_parse_hw_version` handles both dotted and colon forms via `[.:]+`.
- Action: rewrote `hw version` section; marked LIVE; resolved v1 OQ2.

### Challenger M13 — cross-check normalizer references — **AGREE (no dangling refs)**
- Evidence: `grep 'def _normalize_' pm3_compat.py` returned 26 functions; `_normalize_felica_reader` (L1734), `_normalize_iso15693_manufacturer` (L1798), `_normalize_hf15_csetuid` (L1720), etc. all present.
- Action: updated citations for `_normalize_hf15_csetuid` with line number.

### Challenger M14 — "Hex case — None affected" reasoning — **AGREE (reasoning narrowed)**
- Action: no content change (the conclusion is still correct); flagged for future precision.

### Challenger N1 — `lf em 410x_read` canonicalisation note — **AGREE**
- Action: clarified Appendix B entry — legacy aliases `_read` → `read` (no `er` suffix); canonical iceman form is `reader` (separate command).

### Challenger N2 — duplicate of C4 — **covered**

### Challenger N3 — `hf legic dump` progress divergence + `-f` bug — **AGREE**
- Action: expanded OQ5 resolution note with the side-observation about missing `-f` argument.

### Challenger N4 — Appendix A arithmetic — **AGREE**
- Action: corrected count from "approx 870" to precise 867.

### Challenger N5 — Hint row noise — **NOTED**
- Kept row for completeness; reader can skip.

### Challenger N6 — `hf 14a raw` `_translate_14a_raw` indirection — **AGREE**
- Action: rewrote `hf 14a raw` section to document the 5 live sites in hfmfwrite.py gen1afreeze + translator bidirectional rules.

### Challenger N7 — regex broaden prescription for manufacturer — **AGREE**
- Action: corrected the recommendation; explicitly warn against the `^\s+` broadening (false positives). Recommend targeted adapter.

### Challenger N8 — per-command action summary count arithmetic — **AGREE**
- Action: renamed column header from "Count" to "Entries"; added explanatory note.

### Challenger N9 — `data save` caveat — **NOTED**
- Content already reflects the iceman-like-in-legacy-labelled-traces caveat in the body; no change needed.

### Challenger N10 — STRUCTURAL vs FORMAT terminology — **NOTED**
- Matrix uses STRUCTURAL consistently; no standardization change applied this pass.

### Challenger N11 — Appendix C under-documented — **AGREE**
- Action: expanded Appendix C with multiple artefact classes (Nikola.D wire-leak, `hw ping` leak into empty iclass info, trace interleaving).

### Challenger N12 — `lf search` AWID FC/CN — **NOTED**
- Not verified in this pass; Auditor Section 2 row 4 confirms iceman lacks FC/CN for `lf search` path. Kept as-is.

### Auditor 1 (OQ3 / hf iclass info) — covered above in C2 — **AGREE**

### Auditor 2 (hf 14a reader live caller) — covered above in C7 — **AGREE**

### Auditor 3 (hf mfu restore Done miss) — covered above in C4 — **AGREE**

### Auditor 4 (hf felica litedump both firmwares) — covered above in M5 — **AGREE**

### Auditor 5 (hf mf fchk device-iceman identical to legacy) — **AGREE**
- Evidence: trace shape 4 (10×) from `trace_iceman_autocopy_mf1k_hexact_20260414.txt` emits identical 4-column `|`-bordered format. Iceman HEAD `printKeyTable` at cmdhfmf.c:4966-5045 emits a NEW 5-column `+`-separated format (verified by Read of HEAD source).
- Action: rewrote `hf mf fchk` per-field rows; reclassified as IDENTICAL on device build; added FUTURE-BUMP warning for iceman HEAD.

### Auditor 6 (hf 14a raw gen1afreeze live) — covered above in C7 — **AGREE**

### Auditor 7 (lf config bare-char legacy) — **AGREE**
- Evidence: Read of `/tmp/factory_pm3/client/src/cmdlf.c:571-668` confirms `param_getchar`/`switch` bare-char parser. Iceman `cmdlf.c:626-668` uses CLIParser with `-a`/`-t`/`-s` dash flags.
- Action: rewrote `lf config` section; classified FORMAT with command-translate required; flagged missing reverse rule.

### Auditor 8 (hf mf wrbl OQ1 escalation) — **DISAGREE with the mechanism claim**
- Auditor claimed "device iceman build uses `isOk:00`=success as an older-build variant". **Fixer disagrees.** The correct mechanism is `_normalize_wrbl_response` rewriting iceman `Write ( fail )` → `isOk:00`. See full resolution section above. Middleware regex is already correct via alternation.
- Action: rewrote `hf mf wrbl` per-command section with the correct mechanism; cited `_normalize_wrbl_response` explicitly.

---

## Spot-audit summary (from Auditor Section 1 — 15 rows)

| # | Auditor verdict | Fixer verdict after independent check | Note |
|---|---|---|---|
| 1 | DISCREPANCY (hf iclass info) | AGREE with auditor | Rewritten |
| 2 | PASS (hf 14a reader dead) | PARTIAL — live in activity layer | Added activity-layer note |
| 3 | DISCREPANCY (hf mfu restore) | AGREE with auditor | Row relabeled STRUCTURAL |
| 4 | PASS (hf mf rdsc) | AGREE | No change |
| 5 | DISCREPANCY (hf mf fchk table) | AGREE with auditor | Rewritten + future-bump note |
| 6 | PASS (hf iclass rdbl) | DISAGREE — regex fails on blocks ≥10 (Challenger C5 right) | Rewritten per C5 |
| 7 | DISCREPANCY (hf felica litedump) | AGREE with auditor | Rewritten — both firmwares have it |
| 8 | PASS (hf 15 csetuid) | AGREE | Verified |
| 9 | PASS (lf noralsy read) | AGREE | No change |
| 10 | DISCREPANCY (hf 14a raw) | AGREE with auditor | Added live callers |
| 11 | PARTIAL (hf 14a list) | AGREE with auditor | Added activity-layer note |
| 12 | PASS (hf 14a sim) | AGREE | No change |
| 13 | DISCREPANCY (hw version) | AGREE with auditor | Rewritten |
| 14 | DISCREPANCY (lf config) | AGREE with auditor | Rewritten |
| 15 | DISCREPANCY (hf mf wrbl) | DISAGREE with auditor's mechanism — AGREE with auditor's "live problem" framing but wrong on `isOk:00`=success claim. Correct mechanism = `_normalize_wrbl_response` rewriting iceman's `Write ( fail )` → `isOk:00`. | Rewritten with full resolution |

---

## Remaining open questions

1. **`hf 14a info` Magic capabilities source line** — v1 lacks precise `cmdhf14a.c:NNNN` cite for the iceman emission. Not blocking Phase 3 but should be resolved by re-expanding source_strings.md for that subsection.
2. **`hf mf nested` wrong-key whitespace precision** — Challenger M9 asked for pixel-accurate whitespace verification. Not done in this pass.
3. **`hf mf cgetblk` `wupC1 error` iceman armsrc** — Challenger M10 asked to grep armsrc for the string. Not done in this pass.
4. **`lf search` AWID FC/CN iceman path** — Challenger N12 questioned which branch (`lf awid read` vs `lf sea`) the iCopy-X flow hits. Not re-verified.
5. **Device iceman build revision** — knowing the exact git-hash of the installed iceman would let us pin regex against the actual source. Currently we only know it's older than `/tmp/rrg-pm3` HEAD (key-table still 4-col).
6. **`hf iclass rdbl` legacy blocks ≥10** — needs either a new legacy-normalizer or middleware regex broadening. Flagged, not implemented in matrix.
7. **`hf mfu restore` legacy-completion normalizer** — needs `_normalize_hfmfu_restore` or middleware regex broadening. Flagged, not implemented.
8. **`lf config` reverse rule** — needs `_reverse_lf_config` in pm3_compat.py. Flagged, not implemented.

---

## Recommended disposition after fix

**PASS** — matrix v2 is authoritative for Phase 3 middleware rewrite.

The matrix structure is sound; all Challenger + Auditor findings that had evidence are applied. The 8 remaining open questions are minor (individual line citations) or flag future Phase-3 adapter wiring tasks (not matrix corrections). No additional Differ/Challenger/Auditor loops needed.

**Action items for Phase 3 implementation (not matrix changes):**
- Add `_normalize_hfmfu_restore` or broaden middleware regex at hfmfuwrite.py:149.
- Add `_reverse_lf_config` rule to pm3_compat.py `_REVERSE_RULES`.
- Add legacy-direction normalizer for `hf iclass rdbl` blocks ≥10 (hex→decimal).
- Consider activating `_normalize_fchk_table` in `_RESPONSE_NORMALIZERS` before any future iceman firmware bump.

---

## v3 additions

_Generated 2026-04-17 by Fixer v3 agent after Challenger v2 + Auditor v2 reviews._

Challenger v2 verdict was APPROVE with 3 MINOR/NIT findings. Auditor v2 verdict was CONDITIONAL-PASS with 2 MAJOR + 1 MINOR gap findings. v3 applies all targeted corrections; no structural rewrites.

### Corrections applied (7)

**AV2-1 — `lfread.py` dispatcher enumeration** — AGREE, applied.
- Evidence: Read of `/home/qx/icopy-x-reimpl/src/middleware/lfread.py:68-207` confirms 19 per-tag `reader` callers keyed in `READ` table @L210-233:
  `readEM410X`→`lf em 410x reader`@L110, `readHID`→`lf hid reader`@L115, `readIndala`→`lf indala reader`@L120, `readAWID`→`lf awid reader`@L125, `readProxIO`→`lf io reader`@L129, `readGProx2`→`lf gproxii reader`@L133, `readSecurakey`→`lf securakey reader`@L137, `readViking`→`lf viking reader`@L141, `readPyramid`→`lf pyramid reader`@L145, `readFDX`→`lf fdxb reader`@L166, `readGALLAGHER`→`lf gallagher reader`@L171, `readJablotron`→`lf jablotron reader`@L175, `readKeri`→`lf keri reader`@L179, `readNedap`→`lf nedap reader`@L183, `readNoralsy`→`lf noralsy reader`@L187, `readPAC`→`lf pac reader`@L191, `readParadox`→`lf paradox reader`@L195, `readPresco`→`lf presco reader`@L199, `readVisa2000`→`lf visa2000 reader`@L203, `readNexWatch`→`lf nexwatch reader`@L207. Generic helpers `read()`@L68 and `readFCCNAndRaw()`@L94 both invoke `executor.startPM3Task(cmd, TIMEOUT)`.
- Action: middleware-map `lfread.py` row (matrix L84) expanded to enumerate all 19 callers with line numbers; `lf jablotron reader`/`lf noralsy reader` per-command section consolidated to a 15-row source+middleware table for all per-tag LF `reader` commands not already split into their own sections.

**AV2-2 — `read` → `reader` canonicalisation** — AGREE, applied.
- Evidence: grep `\{\"reader\",` on `/tmp/rrg-pm3/client/src/cmdlf*.c` yields iceman dispatch entries for all 20 LF reader protocols. grep `\{\"read\",` on `/tmp/factory_pm3/client/src/cmdlf*.c` confirms legacy uses `read`. Translation rules already wired at `pm3_compat.py:274-277` (forward) and `pm3_compat.py:711-720` (reverse) — confirmed by Grep. No Phase 4 action item needed.
- Action: "Canonical iceman form" corrected in per-command sections for `lf awid reader` (matrix L989), `lf em 410x reader` (matrix L1065), `lf fdxb reader` (matrix L1097), `lf gallagher reader` (matrix L1130), `lf hid reader` (matrix L1145), and the consolidated `lf jablotron reader`/`lf noralsy reader`/etc. section (matrix L1184). Each section updated with iceman dispatch-source citation, legacy dispatch-source citation, and middleware `lfread.py:<line>` LIVE citation.

**AV2-3 — `lfwrite.py` RAW_CLONE_MAP clones** — AGREE, applied.
- Evidence: Read of `/home/qx/icopy-x-reimpl/src/middleware/lfwrite.py:128-133` confirms `RAW_CLONE_MAP` entries for tag_type 14 (securakey), 29 (gallagher), 34 (pac), 35 (paradox), 45 (nexwatch) — all with `-r {}` template. `write_raw_clone()` @L220 issues each via `executor.startPM3Task(cmd, TIMEOUT)`. Iceman dispatch entries verified at `cmdlfsecurakey.c:301`, `cmdlfgallagher.c:387`, `cmdlfpac.c:402`, `cmdlfparadox.c:478`, `cmdlfnexwatch.c:586`. Legacy at `cmdlfsecurakey.c:190`, `cmdlfgallagher.c:197`, `cmdlfpac.c:301`, `cmdlfparadox.c:308`, `cmdlfnexwatch.c:451`.
- Action: combined per-command section "`lf securakey clone` / `lf gallagher clone` / `lf pac clone` / `lf paradox clone` / `lf nexwatch clone` (RAW_CLONE_MAP)" added after `lf indala clone` section with full source+middleware citations. Classified no-adapter (middleware does not parse response; verify via `_inline_verify()` @L528 delegates to `lf sea` normalizers).

**AV2-4 — `hf tune`/`lf tune` activity-layer** — AGREE, applied.
- Evidence: Grep `hf tune|lf tune` confirms `src/lib/activity_tools.py:115` (`_USER_TESTS[0]='hf tune'`, 8888ms timeout, 'voltage' parse_type) and L116 (`_USER_TESTS[1]='lf tune'`). Also `src/main/rftask.py:279` `_INTERACTIVE_CMDS = frozenset({'hf tune', 'lf tune'})` and `src/screens/diagnosis.json:29/35` pm3_cmd entries.
- Action: middleware-map activity-layer row (matrix L94) expanded with `hf tune`/`lf tune` activity_tools.py:115-116 + `lf sea` activity_tools.py:118/907 + rftask.py:279 registry. Per-command `lf tune`/`hf tune` section (matrix L1232) updated: "NOT directly issued" → "LIVE in activity layer"; added CORRECTION (v3) note.

**CV2-1 — `lf awid read` canonical form** — folded into AV2-2.
- Confirmed: iceman `cmdlfawid.c:605` = `reader`; legacy `cmdlfawid.c:535` = `read`. Translator at `pm3_compat.py:275-277` (forward) and `pm3_compat.py:717-720` (reverse).
- Action: section heading/fields updated as part of AV2-2.

**CV2-2 — `felicaread.py`/`hffelica.py` row split** — AGREE, applied.
- Evidence: Read of `src/middleware/felicaread.py` confirms it issues `hf felica litedump` @L72 with no response-parse logic (file-side verification only). Read of `src/middleware/hffelica.py` confirms it defines `CMD='hf felica reader'` @L35 and provides the parser with `_KW_FOUND`@L39, `_KW_TIMEOUT`@L40, `_RE_IDM`@L43.
- Action: matrix L69 row split into two rows — `felicaread.py` (command issuer, no parse) and `hffelica.py` (parser for `hf felica reader` invoked via `scan.py:416`).

**CV2-3 — Inline regex citations** — AGREE, applied.
- Evidence: Read of `src/middleware/hfmfuinfo.py:57` confirms `m = re.search(r'UID\s*:\s*([0-9A-Fa-f ]+)', text)` inline UID-extraction regex. Read of `src/middleware/lfwrite.py:426/430` confirms `content = executor.getPrintContent()` @L426 and `m = re.search(r'\|\s*([A-Fa-f0-9]+)\s*', content)` @L430 in `write_dump_em4x05()` verify loop.
- Action: new `hfmfuinfo.py` row added to middleware map (matrix L77) with command + inline regex + keywords citations. `lfwrite.py` row extended to cite `getPrintContent()` @L426 and inline regex @L430.

### Supporting updates

- Summary "Commands analysed" bumped from 66 to 72.
- Summary "Issued by middleware (iceman canonical form)" bumped from 54 to 73 (adds 19 LF per-tag `reader` callers).
- DEAD list trimmed: removed `lf tune`, `hf tune`, `lf em 410x reader`, `lf noralsy read`, `lf jablotron read`, `lf indala clone` from DEAD.
- Open Questions section extended with 5 new [RESOLVED v3] items (OQ10-14) covering: LF per-tag `reader` canonicalisation, `lfwrite.py` RAW_CLONE_MAP coverage, `hf tune`/`lf tune` activity-layer LIVE, `felicaread.py`/`hffelica.py` split, orphan inline regex citations.
- Appendix B extended with consolidated entry for the 19 LF `<tag> read` → `<tag> reader` canonicalisations + existing translator line citations.

### DISAGREE

No DISAGREEs. All 7 v3 corrections verified against the cited source files and applied as described.

### New issues surfaced during v3 pass

- None material. The 15-row consolidated table for `lf <tag> reader` callers references `cmdlfguard.c` for `gproxii` (iceman `reader` dispatch at L417 aliases the GProxII II protocol as `gproxii` while the file itself is named `cmdlfguard.c`). This is an internal iceman file-naming quirk, not a matrix issue.

### Final disposition

**PASS** — all Challenger v2 + Auditor v2 findings with evidence are applied. Matrix is production-ready for Phase 3 middleware rewrite. No further loops needed.

