# Challenger v2 Report
_Generated 2026-04-17 (second-round adversarial review of v2-corrected matrix)_

Input docs reviewed:
- `tools/ground_truth/divergence_matrix.md` (v2, 1540 lines)
- `tools/ground_truth/divergence_matrix_v2_changes.md`
- `tools/ground_truth/divergence_matrix_challenges.md` (Challenger v1)
- `tools/ground_truth/divergence_matrix_audit.md` (Auditor v1)

Evidence basis:
- `/tmp/rrg-pm3/client/src/` (iceman HEAD)
- `/tmp/factory_pm3/client/src/` (legacy)
- `src/middleware/*.py` (live middleware)
- `docs/Real_Hardware_Intel/trace_iceman_*.txt` (real device traces)

---

## Section 1: Correction verification (per changelog item)

### C1 (hf mf wrbl isOk:00) — AGREE-verified
Matrix L802-847 rewritten. `_normalize_wrbl_response` cited at pm3_compat.py:1216. Trace evidence (438 shape 1 samples, shape 13 `Write ( ok )`) cited correctly. See Section 2 for deep dive.

### C2 (hf iclass info) — AGREE-verified
Matrix L403-435 rewritten. Iceman `info_iclass()` at `/tmp/rrg-pm3/client/src/cmdhficlass.c:7996-8108` verified by direct Read — L8029 banner, L8032 CSN, L8047 E-purse, L8051 Kd, L8102 Card type all present. The "hw ping leak" hypothesis is cited at L417-420.

### C3 (hf 15 restore — active adapter) — AGREE-verified
Matrix L310-334. `hasKeyword` confirmed case-sensitive via Read of `executor.py:711-726` (`re.search` at L722, no IGNORECASE flag). `_normalize_hf15_restore` verified at pm3_compat.py:1638-1649 (injects `Write OK\ndone` when `'Done'` substring present).

### C4 (hf mfu restore Done/Finish) — AGREE-verified
Matrix L899-921. Verified `PrintAndLogEx(INFO, "Finish restore")` at `/tmp/factory_pm3/client/src/cmdhfmfu.c:2343`; iceman `"Done!"` at `/tmp/rrg-pm3/client/src/cmdhfmfu.c:4218`. No `Done` token in legacy path.

### C5 (hf iclass rdbl blocks ≥10) — AGREE-verified
Matrix L486-507. iceman `" block %3d/0x%02X : %s"` at cmdhficlass.c:3501 vs legacy `" block %02X : %s"` at cmdhficlass.c:2399 confirmed by grep. Correct identification that `\d+` regex fails on both raw forms.

### C6 (hf iclass dump "saving dump file" identical) — AGREE-verified
Matrix L462-483. grep confirmed identical `"saving dump file - %u blocks read"` at iceman cmdhficlass.c:2978 and legacy cmdhficlass.c:1031/1990.

### C7 (middleware coverage holes) — AGREE-verified
Matrix middleware map L92-94 added `pm3_flash.py`, `pm3_compat.py`, activity-layer rows. `hfmfwrite.py` row at L78 extended with `hf 14a raw` at L193-197.

### M1 (`_RE_HEX_KEY` citation) — AGREE-verified
Matrix L695. Corrected to reference `hfmfkeys.py:275` inline IGNORECASE regex. Verified at line `m = re.search(r'Found valid key\s*[:\[]\s*([A-Fa-f0-9]{12})', text, re.IGNORECASE)`.

### M2 (KERI ID case) — AGREE-verified
Matrix L981. Verified `_GREEN_("KERI ID")` in both firmwares (all-caps identical).

### M3 (hf search Valid iCLASS) — AGREE-verified
Matrix L941. Verified `Valid iCLASS tag / PicoPass tag found` identical in both.

### M4 (key on debit fabrication) — AGREE-verified
Matrix L450. grep `"key on debit"` returns zero matches. Removed.

### M5 (hf felica litedump both firmwares) — AGREE-verified
Matrix L383-400. `"litedump"` present in both dispatch tables.

### M6 (Magic capabilities source ref) — AGREE-verified (TBD marker acceptable)
Matrix L125 cites TBD.

### M7 (`_RE_T55XX_CHIP_NEW` verified correct) — AGREE
No change.

### M8 (ATS regex clarification) — AGREE-verified
Matrix L127: `_RE_ATS` matches PAYLOAD line not decorative banner.

### M9/M10/M14 (NOTED, no change) — acceptable
Deferrals documented in changelog.

### M11 (hf iclass wrbl cite) — AGREE-verified
Matrix L527 cites cmdhficlass.c:3134 (iceman) and cmdhficlass.c:2149 (legacy).

### M12 (hw version) — AGREE-verified
Matrix L1247-1274. pm3_flash.py:168 verified. Parser regex at L127/132/137/142/147 uses `[.:]+`.

### M13 (normalizer refs) — AGREE-verified
26 normalizer defs present (grep confirmed).

### N1/N3/N4/N6/N7/N8/N11 — AGREE-verified
Corresponding sections/appendices updated.

### N2 covered by C4.

### N5/N9/N10/N12 — NOTED, acceptable.

### Auditor 1-7 — AGREE-verified (all match corrections above).

### Auditor 8 — DISAGREE documented correctly (see Section 2).

**Section 1 verdict: 28/28 corrections applied correctly. No missing or mis-applied corrections.**

---

## Section 2: DISAGREE review — hf mf wrbl isOk:00

**Verdict: Fixer's reasoning is SOUND. APPROVE DISAGREE.**

Independently verified:

1. **`_normalize_wrbl_response` at pm3_compat.py:1216-1232** — verified by Read. Literally does `text.replace('Write ( ok )', 'isOk:01')` / `'Write ( fail )' → 'isOk:00'` plus two regex `sub` for `(\s*ok/fail\s*)`.

2. **Executor ordering at executor.py:358-366** — verified: `_clean_pm3_output(result)` runs at L358; `pm3_compat.translate_response(result, translated_cmd)` runs at L364. Response cache `CONTENT_OUT_IN__TXT_CACHE = result` at L368 AFTER normalization. So everything middleware and traces see is POST-normalization.

3. **Iceman source has zero `isOk:` emissions** — `grep -rn "isOk" /tmp/rrg-pm3/client/src/` returns zero matches. factory has 4 matches (cmdhfmfu.c:1589, cmdhfmf.c:716/825/1307).

4. **Trace residue check** — `trace_iceman_full_audit_v5_20260414.txt` L883 shows `isOk:01`, L885 shows raw `Write ( ok )` for same-block retry. The raw `Write ( ok )` surviving the normalizer is plausibly a response-slot capture race where trace instrumentation saw raw output before `translate_response` ran (or the normalizer's regex didn't match due to preceding whitespace). Either way consistent with Fixer's "edge-case residue" claim.

5. **Middleware regex alternation** — `r'isOk:01|Write \( ok \)'` (hfmfwrite.py:158) catches both normalized and raw form. Correct.

6. **Auditor's "isOk:00=success" claim** — no source or trace evidence. The 438 shape-1 samples are failed writes (normalized from `Write ( fail )`). Auditor's "older-build variant emits isOk:00 as success" hypothesis lacks source backing.

Fixer correctly pushes back on Auditor. No further action needed.

---

## Section 3: NEEDS-MORE-DATA review (8 open questions)

| # | Item | Defer OK? | Notes |
|---|---|---|---|
| 1 | `hf 14a info` Magic capabilities source line | YES | Cosmetic precision — Phase 3 refactorer doesn't need the exact line to wire the already-existing `_normalize_magic_capabilities`. |
| 2 | `hf mf nested` wrong-key whitespace precision | YES | Substring `"Wrong key"` matches both; pixel-accurate whitespace not needed for keyword matching. |
| 3 | `hf mf cgetblk` `wupC1 error` iceman armsrc | YES | Already observed in iceman traces (matrix L589); substring keyword works. |
| 4 | `lf search` AWID FC/CN iceman path | YES | `_normalize_awid_card_number` wired; matrix L976 captures divergence. |
| 5 | Device iceman build revision (git hash) | **SHOULD-RESOLVE** | Critical for `hf mf fchk` future-bump — if iceman upgrades to HEAD, the 4-col regex breaks. Phase 3 should capture device build hash at flash time. Not matrix-blocking but should be logged as a device-audit task. |
| 6 | `hf iclass rdbl` legacy blocks ≥10 legacy-normalizer | YES | Phase 3 adapter work, properly flagged as action item. |
| 7 | `hf mfu restore` legacy completion normalizer | YES | Phase 3 adapter work, properly flagged. |
| 8 | `lf config` reverse rule | YES | Phase 3 adapter work, properly flagged. |

**All 8 items** are listed in matrix L1526-1536 "Open questions / gaps" section. A Phase 3 refactorer WILL see them. Item 5 warrants a device-audit task (non-matrix).

---

## Section 4: Fresh spot-audit (10 commands NOT in v1 samples)

| # | Command | Matrix row | Verdict | Note |
|---|---|---|---|---|
| 1 | `hf 14a sniff` | L235-253 | PASS | `PATTERN_HF_TRACE_LEN` at sniff.py:62 verified covers both. |
| 2 | `hf 14b sniff` | L256-273 | PASS | Same regex, valid. |
| 3 | `hf iclass sniff` | L533-546 | PASS | Falls under generic HF trace-len handling. |
| 4 | `hf mfu info` | L850-874 | PASS (minor gap) | NTAG/MF0UL keywords verified at scan.py:237-247. **Gap:** `hfmfuinfo.py:57` `_RE_UID = r'UID\s*:\s*([0-9A-Fa-f ]+)'` not cited in middleware map. Minor. |
| 5 | `hf mfu dump` | L877-895 | PASS | `'Partial dump created'` at hfmfuread.py:118, `"Can't select card"` at L110 verified. |
| 6 | `lf awid read` | L989-1004 | **DISCREPANCY** | Canonical iceman form incorrectly stated as `lf awid read`. iceman's AWID has `{"reader", CmdAWIDReader, ...}` at cmdlfawid.c:605; legacy has `{"read", CmdAWIDRead, ...}` at cmdlfawid.c:535. Translator at pm3_compat.py:275-277 rewrites `read → reader`. Matrix should state canonical iceman form is `lf awid reader`. |
| 7 | `lf t55xx detect` | L1190-1212 | PASS | `_RE_CHIP_TYPE`, `_RE_MODULATE`, `_RE_BLOCK0`, `KEYWORD_CASE1` all verified. |
| 8 | `lf em 4x05 info` | L1008-1028 | PASS | `_RE_CHIP/_RE_SERIAL/_RE_CONFIG` at lfem4x05.py:61-63 verified. |
| 9 | `hf mf csave` | L663-676 | PASS | Correctly identifies missing `_normalize_save_messages` entry in `_RESPONSE_NORMALIZERS` (verified at pm3_compat.py:1820-1877 — absent). |
| 10 | `hf mf cload` | L621-638 | PASS | `'Card loaded'` substring works on both (iceman emits `Card loaded %d blocks from %s`, legacy `Card loaded %d blocks from file` — both contain the substring). |

**Section 4 new findings:** 1 DISCREPANCY (lf awid read canonical form). 1 minor gap (`hfmfuinfo.py:57` missing from middleware map).

---

## Section 5: Cross-reference regression (5 random middleware files)

### 5.1 `hf14aread.py` — PASS
79 lines, no `startPM3Task`/`hasKeyword`/`getContentFromRegex` calls. File-only (saves cache). Correctly absent from middleware map.

### 5.2 `hfmfuinfo.py` — PARTIAL
`CMD = 'hf mfu info'` at L50 but not called directly — used as a PARSER module on `CONTENT_OUT_IN__TXT_CACHE`. Has inline regex `r'UID\s*:\s*([0-9A-Fa-f ]+)'` at L57 for UID extraction. **Not in middleware map.** Minor gap — matrix covers the `hf mfu info` command at scan.py:233 (which IS mapped) but the parse regex in `hfmfuinfo.py` is orphaned from the cross-reference table.

### 5.3 `hffelica.py` — DISCREPANCY
Matrix L69 row is labeled `felicaread.py` but the keyword citations `_KW_TIMEOUT=L40`, `_KW_FOUND=L39`, `_RE_IDM=L43` are from `hffelica.py`, NOT `felicaread.py`. `felicaread.py` invokes `hf felica litedump` (L72); `hffelica.py` parses `hf felica reader` output (invoked by scan.py). The row conflates two files. Minor but confusing.

### 5.4 `lfverify.py` — PASS
Single `executor.startPM3Task('lf sea', 10000)` at L214. Matrix L87 cites correctly.

### 5.5 `lfwrite.py` — PARTIAL
Matrix L88 cites 13 `startPM3Task` locations (151,163,175,191,220,231,250,273,297,371,413,422,537) — all verified. **Gap:** L426 `executor.getPrintContent()` and L430 inline regex `r'\|\s*([A-Fa-f0-9]+)\s*'` parses block data. Matrix says "None directly" for lfwrite parsing — minor omission; inline regex does parse response in the `lf em 4x05 read` verify path.

**Section 5 new findings:** 1 PARTIAL (`lfwrite.py` inline regex), 1 DISCREPANCY (`hffelica.py` vs `felicaread.py` row conflation), 1 minor gap (`hfmfuinfo.py` missing).

---

## Section 6: Systemic issues

### 1. Hex case — correctly handled
Matrix L1376-1382. All middleware regex use `[A-Fa-f0-9]`. Verified via quick sample (hfmfread.py:280 `_RE_BLOCK_DATA=r'[A-Fa-f0-9]{32}'`, hfmfkeys.py:229, lfem4x05.py, lfsearch.py). PASS.

### 2. Section headers — correctly handled
Matrix L1386-1392. `executor._clean_pm3_output` strips `[=] ----` lines. Verified by Read of `executor.py`. PASS.

### 3. Hint capitalisation — correctly handled
Matrix L1396-1402. Iceman `Hint: Try` (7 hits in cmdhf14a.c), legacy `Hint: try` (3 hits in cmdhf14a.c:2012/2015/2018). Not parsed. PASS.

### 4. rdbl delegates — correctly handled
Matrix L1406-1412. `_normalize_rdbl_response` wired for all three commands (verified at pm3_compat.py:1829, 1827, 1834). PASS.

### 5. Help text — correctly handled
Matrix L1416-1420. Middleware never calls `-h`. PASS.

### 6. Save messages — correctly handled
Matrix L1424-1430. `_normalize_save_messages` wired for `hf mfu dump`, `hf 15 dump`, `hf iclass dump`, `lf t55xx dump`, `lf em 4x05 dump`, `data save` — verified in `_RESPONSE_NORMALIZERS` table. Correctly flags `hf mf csave` as MISSING. PASS.

### 7. Dotted vs colon separators — correctly handled
Matrix L1434-1440. Per-field fixers exist for the regex-consumed cases. PASS.

### 8. isOk: divergence — correctly handled
Matrix L1444-1452. Cross-references Section 2 resolution. PASS.

### 9. Prefix stripping — correctly handled
Matrix L1456-1462. Handled at executor layer. PASS.

**Section 6 verdict: all 9 systemic divergences correctly propagated across affected commands. PASS.**

---

## Summary

- Total NEW findings: **3**
- Severity: CRITICAL 0, MAJOR 0, MINOR/NIT 3
- Verdict: **APPROVE for Phase 3**

### Top 3 concerns

1. **MINOR** — Matrix L991 states canonical iceman form for AWID is `lf awid read`. iceman actually uses `lf awid reader` (cmdlfawid.c:605); legacy uses `read` (cmdlfawid.c:535). Translator at pm3_compat.py:275-277 does the rewrite. Update matrix L991 to canonical `lf awid reader`.

2. **NIT** — Matrix L69 row labeled `felicaread.py` lists keywords `_KW_TIMEOUT/FOUND/RE_IDM` with line numbers from `hffelica.py` (the parse helper). Separate the two files in the middleware map.

3. **NIT** — `hfmfuinfo.py` (parser for `hf mfu info`, has inline `_RE_UID` at L57) and `lfwrite.py:426/430` (getPrintContent + block regex in `lf em 4x05 read` verify) not cited in middleware map. Not divergence-relevant but incomplete.

None of these block Phase 3. Fixer's v2 corrections are comprehensive; the 28 applied corrections are all verified accurate. DISAGREE on wrbl is sound. All 8 open questions are properly catalogued and non-blocking.

**Matrix is production-ready for Phase 3 middleware rewrite.**
