# Auditor v2 Report

_Generated 2026-04-17 by Auditor v2 agent_
_Target: `/home/qx/icopy-x-reimpl/tools/ground_truth/divergence_matrix.md` (v2 corrections applied)_
_Scope: Independent ground-truth verification — no adversarial overlap with Challenger v2_

## Section 1: Changelog spot-check (10 entries)

| # | Entry | Claim verified against source | Verdict |
|---|---|---|---|
| 1 | **C1** — `hf mf wrbl` isOk misattribution | `grep isOk: /tmp/rrg-pm3/client/src/` → 0 matches. iceman cmdhfmf.c:1389/1394 emits `Write ( ok )/Write ( fail )` only. Legacy cmdhfmf.c:716 emits `isOk:%02x`. Matrix section L802-846 rewritten with `_normalize_wrbl_response` mechanism. | PASS — Fixer reasoning sound |
| 2 | **C2** — `hf iclass info` iceman emits full block | Read of `/tmp/rrg-pm3/client/src/cmdhficlass.c:7996-8108` confirms iceman `info_iclass()` emits CSN (L8032), Config (L8036), AIA (L8043), E-purse (L8047), Kd (L8051), Kc (L8057), Fingerprint banner (L8072), Card type (L8102), Card chip (L8105/8107). Matrix section L403-436 rewritten correctly. | PASS |
| 3 | **C3** — `hf 15 restore` action="none" masks adapter | executor.py:722 `re.search` is case-sensitive (verified). `_normalize_hf15_restore` at pm3_compat.py:1638-1648 injects `Write OK\ndone` when iceman `Done` detected. Matrix row L326-327 correctly cites the adapter. | PASS |
| 4 | **C5** — `hf iclass rdbl` regex fails block ≥10 | iceman cmdhficlass.c:3501 = `" block %3d/0x%02X : %s"`. Legacy cmdhficlass.c:2399 = `" block %02X : %s"`. Middleware regex `\d+` at hficlass.py:99 cannot match legacy hex blocks `0A`+. Matrix section L486-508 rewritten, flags missing legacy-normalizer. | PASS |
| 5 | **C7** — middleware map coverage holes | Verified: `pm3_flash.py:168` issues `hw version`; `pm3_compat.py:932` issues `hf 14a config --bcc ignore` via `configure_iceman()`; `hfmfwrite.py:193-197` issues 5 `hf 14a raw` in `gen1afreeze()`; `activity_tools.py:818/928` issues `hf 14a reader`/`lf em 410x watch`; `activity_main.py:6272` issues `hf 14a list`. Matrix middleware map L92-94 now includes all. | PASS |
| 6 | **M2** — `Valid KERI ID` case divergence fabricated | `grep "Valid.*KERI ID"` → `/tmp/rrg-pm3/client/src/cmdlf.c:2168` + `/tmp/factory_pm3/client/src/cmdlf.c:1461`, both all-caps `KERI ID`. Matrix row L981 corrected to IDENTICAL. | PASS |
| 7 | **M4** — `hf iclass chk` "key on debit" fabrication | `grep "key on debit"` → zero matches in BOTH firmware trees. Matrix section L438-458 now cites `"Found valid key <hex>"` (cmdhficlass.c:5925/7016) only. | PASS |
| 8 | **M11** — `hf iclass wrbl` block-format | iceman cmdhficlass.c:3134 = `"Wrote block %d / 0x%02X ( ok )"`. Legacy cmdhficlass.c:2149 = `"Wrote block %02X successful"`. Matrix section L525-527 has exact citations. | PASS |
| 9 | **N1** — `lf em 410x_read` canonicalisation | Legacy `cmdlfem410x.c` aliases `_read`→`read`. Iceman dispatcher uses separate `reader` command. Matrix Appendix B L1503 updated correctly. | PASS |
| 10 | **Auditor 7** — `lf config` bare-char legacy | `/tmp/factory_pm3/client/src/cmdlf.c:593-615` uses `param_getchar` switch over bare chars `h`/`H`/`L`/`q`/`f`/`t`. Iceman cmdlf.c:628-657 uses CLIParser with `-a/-t/-s`. Matrix section L1350-1371 rewritten correctly. | PASS |

**10/10 PASS.** All Fixer claims verified against source.

## Section 2: Fresh random audit (15 commands, seed=43 from 72-command pool)

3 overlap with v1 sample (hf mf wrbl, hf 14a raw, lf noralsy read) treated as re-audit of Fixer corrections.

| # | Command | Sections verified | Verdict |
|---|---|---|---|
| 1 | `hf 14a config` | src(pm3_compat.py:928-933 `configure_iceman`), trace(iceman: 3 samples), mw(LIVE iceman-only), action(no-adapter) | PASS |
| 2 | `hf search` | src(`Valid iCLASS tag/PicoPass tag` both cmdhf.c:208/136 IDENTICAL, v2-corrected), mw(hfsearch.py:88 `hf sea`), per-field table accurate | PASS |
| 3 | `hf iclass wrbl` | src(iceman cmdhficlass.c:3134 `Wrote block %d / 0x%02X ( ok )`; legacy :2149 `Wrote block %02X successful`), mw(iclasswrite.py:175, keyword L180 `r'successful\|\( ok \)'`) | PASS |
| 4 | `lf t55xx dump` | src(dotted-vs-colon), trace(0 iceman / 2 legacy), mw(lft55xx.py:489), per-field table OK | PASS |
| 5 | `lf fdxb clone` | src+trace OK, mw(lfwrite.py:188 cmd built, :191 startPM3Task). Matrix cite L191 points at startPM3Task not cmd-build — consistent with matrix convention | PASS |
| 6 | `hf felica reader` | src OK, trace(55 iceman / 37 legacy), mw(scan.py:416 + hffelica.py:35 parse) | PASS |
| 7 | `lf t55xx read` | src+trace OK, mw(lft55xx.py:634,662). LEGACY-ONLY classification accurate (0 iceman / 78 legacy samples). | PASS |
| 8 | `lf tune` | no middleware caller (correct). Matrix marks DEAD L1240. Minor note: `activity_tools.py:116` is an activity-layer caller — matrix didn't mention it here (did mention for `hf 14a reader`/`lf em 410x watch`). MINOR CONSISTENCY gap. | PARTIAL |
| 9 | `hf 14a raw` | src(iceman cmdhf14a.c:1653, legacy :1186), mw(hfmfwrite.py:193-197 five gen1afreeze sites verified). Matrix section L165-184 accurate. | PASS |
| 10 | `hf mf wrbl` | Full re-verification: iceman source emits ONLY `Write ( ok )/Write ( fail )` (zero `isOk:` matches across entire tree). Trace isOk:00=175/isOk:01=53 matches 438 failed writes normalization claim. `_normalize_wrbl_response` at pm3_compat.py:1216 verified. Matrix v2 resolution CORRECT — Fixer rightly disagreed with Auditor v1's "isOk:00=success" mechanism. | PASS |
| 11 | `hf mf darkside` | src OK, mw(hfmfkeys.py:269), regex corrected to inline IGNORECASE at L275 matches both `[:` and `[\[` forms. Matrix row L694-696 accurate. | PASS |
| 12 | `lf sniff` | mw(sniff.py:127), regex `PATTERN_HF_TRACE_LEN` handles both. IDENTICAL classification accurate. | PASS |
| 13 | `hf mf cwipe` | mw(erase.py:132), matrix row L609-615 accurate (no regex dependency). | PASS |
| 14 | `lf em 4x05 info` | src+mw OK (lfem4x05.py:167). Matrix section L1008-1028 accurately flags FORMAT divergence on dotted-vs-pipe. | PASS |
| 15 | `lf noralsy read` | **DISCREPANCY**. Matrix L1177 "Canonical iceman form: lf noralsy read" is WRONG. Iceman dispatcher at `/tmp/rrg-pm3/client/src/cmdlfnoralsy.c:291` = `{"reader", CmdNoralsyReader,...}`. Legacy at `cmdlfnoralsy.c:225` = `{"read", CmdNoralsyRead,...}`. Additionally, `lfread.py:187` issues `'lf noralsy reader'` — matrix "NOT directly issued" is FALSE. | DISCREPANCY |

**14 PASS / 1 PARTIAL / 1 DISCREPANCY** (15 rows; row 15 is the `lf noralsy` canonicalisation issue, representative of a broader systemic gap for all `lfread.py` callers).

## Section 3: Recently-added sections

| Section | Source cite | Trace cite | Middleware cite | Classification | Verdict |
|---|---|---|---|---|---|
| `hw version` (L1247-1275) | Both forks via `pm3_version_short` helper — handler has no direct PrintAndLogEx | 11 iceman dotted samples / 2 legacy colon samples | pm3_flash.py:168 via `get_running_version()` → `_parse_hw_version` L101 | FORMAT; already wired. Matches regex at L127/132/137/142 handles dotted+colon | PASS |
| `hf 14a config` (L204-215) | iceman has command; legacy older variant | 3 iceman / 0 legacy | pm3_compat.py:932 `configure_iceman()` | ICEMAN-ONLY; fire-and-forget. LIVE, not dead | PASS |
| `hf 14a raw` (L165-184) | iceman cmdhf14a.c:1653; legacy :1186 | 10 iceman / 29 legacy | hfmfwrite.py:193-197 (5 sites) + pm3_compat.py:235/547 translators | FORMAT + command-translate | PASS |
| `hf 14a reader` (L186-200) | iceman cmdhf14a.c:671; legacy :471 | 1 iceman / 3 legacy | activity_tools.py:818 (activity-layer, out of middleware scope) | Out-of-scope (activity-layer) | PASS |
| `hf 14a list` (L141-162) | source via `hf list` dispatcher | 3 iceman / 4 legacy | activity_main.py:6272 (activity-layer) | Out-of-scope; pm3_compat.py:811 translate rule | PASS |
| `lf em 410x watch` (L1081-1093) | iceman syntax | 0 iceman / 1 legacy (wire-leak) | activity_tools.py:928 (activity-layer) | Out-of-scope | PASS |

**6/6 PASS** — all new sections meet Differ quality bar with citations present.

## Section 4: v1 DISCREPANCY resolution (8 items + 2 PARTIAL = 10)

| v1 item | Status in v2 | Verdict |
|---|---|---|
| `hf iclass info` (DISCREPANCY) | Section L403-436 rewritten with CSN/Config/AIA/E-purse/Kd/Kc/Fingerprint per source L8028-8107 | RESOLVED |
| `hf 14a reader` (PASS→PARTIAL in v1 S5) | L186-200 notes activity_tools.py:818 live caller | RESOLVED |
| `hf mfu restore` (DISCREPANCY) | L899-923 reclassified STRUCTURAL, cites `"Finish restore"` legacy, flags missing `_normalize_hfmfu_restore` | RESOLVED (flagged in OQ8) |
| `hf mf fchk` (DISCREPANCY) | L702-730 corrected to IDENTICAL on device build + FUTURE-BUMP warning for iceman HEAD | RESOLVED |
| `hf felica litedump` (DISCREPANCY) | L382-399 corrected: both firmwares have command at :5056/:1619 handler+:5329/:1884 dispatch; no translate needed | RESOLVED |
| `hf 14a raw` (DISCREPANCY) | L165-184 documents 5 `gen1afreeze` sites + bidirectional translators | RESOLVED |
| `hf 14a list` (PARTIAL) | L141-162 activity-layer note added | RESOLVED |
| `hw version` (DISCREPANCY) | L1247-1275 marks LIVE with pm3_flash.py:168, regex L127-149 | RESOLVED |
| `lf config` (DISCREPANCY) | L1350-1371 FORMAT + command-translate REQUIRED for legacy (flagged OQ9) | RESOLVED |
| `hf mf wrbl` (DISCREPANCY) | L802-846 rewritten with `_normalize_wrbl_response` mechanism. Fixer disagreed with v1's "isOk:00=success" — correctly. | RESOLVED (with disagreement) |

**10/10 v1 discrepancies RESOLVED.**

## Section 5: Gap follow-through

| Middleware file | Gap | Status |
|---|---|---|
| `lfread.py` | **MAJOR GAP**: 19 `lf <tag> reader` callers at L110-207 (em 410x, hid, indala, awid, io, gproxii, securakey, viking, pyramid, fdxb, gallagher, jablotron, keri, nedap, noralsy, pac, paradox, presco, visa2000, nexwatch) — none listed in matrix middleware map beyond a vague "dispatcher" note at L84 | NEW GAP |
| `lfwrite.py` RAW_CLONE_MAP | 5 additional clone commands (securakey, gallagher, pac, paradox, nexwatch) via `write_raw_clone()` — `lf pac clone`, `lf paradox clone`, `lf nexwatch clone`, `lf securakey clone` missing from matrix | NEW GAP |
| `pm3_flash.py:168` | `hw version` | RESOLVED in v2 |
| `pm3_compat.py:932` | `hf 14a config --bcc ignore` | RESOLVED in v2 |
| `hfmfwrite.py:193-197` | `hf 14a raw` gen1afreeze | RESOLVED in v2 |
| `activity_*` layer | `hf 14a reader`, `hf 14a list`, `lf em 410x watch`, `hf tune`, `lf tune` | PARTIAL — matrix lists reader/list/watch but NOT `hf tune`/`lf tune` activity_tools.py:115-116 callers (still marked DEAD on line 37). MINOR inconsistency. |

## Section 6: Open Questions evaluation

| OQ | Type | Verdict |
|---|---|---|
| OQ1 `hf mf wrbl` isOk | RESOLVED in matrix L1528 | Correctly resolved; Phase 3 can proceed |
| OQ2 `hw version` | RESOLVED in matrix L1529 | Correctly resolved |
| OQ3 `hf iclass info` | RESOLVED in matrix L1530 | Correctly resolved |
| OQ4 `hf 14a info` Hint truncation | Matrix-level: request source_strings.md re-expand | Phase 3-actionable, minor; documented for future refresh |
| OQ5 `hf legic dump` PARTIAL | Matrix-level side-observation about missing `-f` arg | Phase 3 bug-fix candidate (pre-existing, not a divergence concern) |
| OQ6 Device iceman build revision | Hardware-dependent | Genuine blocker — cannot be resolved at matrix level |
| OQ7 `hf iclass rdbl` legacy blocks ≥10 | Phase 3 adapter: add legacy-normalizer | Actionable; enough info for Phase 3 |
| OQ8 `hf mfu restore` legacy completion | Phase 3 adapter: add `_normalize_hfmfu_restore` or broaden regex | Actionable |
| OQ9 `lf config` reverse rule | Phase 3 adapter: add `_reverse_lf_config` to pm3_compat.py | Actionable |

**All 9 OQs are either fully resolved or clearly Phase-3-actionable with sufficient detail.**

## Summary

- **Spot-audit (15 rows):** 14 PASS / 1 PARTIAL / 1 DISCREPANCY. Only discrepancy: `lf noralsy` canonicalisation wrong + systemic `lfread.py` middleware-map gap.
- **Changelog spot-check:** 10/10 PASS — all Fixer claims verified against raw source.
- **v1 discrepancies resolved:** 10/10 (8 DISCREPANCY + 2 PARTIAL all addressed).
- **Recently-added sections:** 6/6 PASS quality bar.
- **New gaps:** 2 material (`lfread.py` ~19 reader callers; `lfwrite.py` RAW_CLONE_MAP 5 clone commands). 1 minor (`hf tune`/`lf tune` activity-layer mention).
- **Open Questions:** 9/9 appropriately dispositioned for Phase 3.

### Overall verdict: **CONDITIONAL-PASS**

The v2 matrix is substantially accurate on source citations, trace interpretations, and middleware wiring for the commands it covers. All Challenger/Auditor v1 findings with evidence are applied. The `hf mf wrbl` mechanism resolution is correct (Fixer rightly overruled Auditor v1). However, the matrix has a residual coverage gap on the 19 `lfread.py` per-tag `reader` callers and 4 uncovered LF clone commands in `lfwrite.py`'s RAW_CLONE_MAP. These are LIVE middleware callers not cataloged. The per-command sections for `lf jablotron`, `lf noralsy`, `lf em 410x reader` etc. claim "NOT directly issued" when in fact the iceman-canonical `reader` form IS issued via lfread.py. The canonical iceman form for these is `reader`, not `read`.

**Recommendation:** Apply one more targeted Fixer pass to:
1. Expand matrix middleware map `lfread.py` row to enumerate all 19 `lf <tag> reader` callers with line citations.
2. Add rows for `lf pac clone`, `lf paradox clone`, `lf nexwatch clone`, `lf securakey clone` from `lfwrite.py` RAW_CLONE_MAP L128-134.
3. Correct "Canonical iceman form" from `lf <tag> read` → `lf <tag> reader` for jablotron/noralsy/pac/keri/viking/visa2000/presco/etc. per iceman source dispatch tables.
4. Flip "NOT directly issued" → "LIVE via lfread.py:<line>" for those commands.
5. Optional: mention `activity_tools.py:115-116` for `hf tune`/`lf tune` consistency.

These are targeted corrections, not structural rewrites. After applying, v3 should APPROVE.
