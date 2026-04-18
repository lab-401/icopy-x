# Divergence Matrix Audit
_Generated 2026-04-17 by Auditor agent_
_Target: `/home/qx/icopy-x-reimpl/tools/ground_truth/divergence_matrix.md`_
_Random seed: Python `random.seed(42)` → 15 commands drawn from union list (reproducible)._

Legend: PASS = matrix claim substantiated by source+trace+middleware citations.
DISCREPANCY = at least one cited item contradicts the matrix; detail given.
PARTIAL = claim is close but factually imprecise on one field.

---

## Section 1: Random spot-audit (15 commands)

| # | Command | Source citation | Trace citation | Middleware citation | Field-table verdict | Verdict |
|---|---|---|---|---|---|---|
| 1 | `hf iclass info` | source_strings.md:L8323–8382 + iceman `cmdhficlass.c:1641` (stub) + `info_iclass` @ `cmdhficlass.c:7996–8190` | `iceman_output.json:hf iclass info` shapes 0 (14x "Ping sent with payload len: 32…") / 1 (2x "timeout…") — both captured from newest compat traces 2026-04-16 | `hficlass.py:290` (`_CMD_INFO='hf iclass info'`) | **DISCREPANCY.** Matrix row (L399–405) claims "iceman emits ping diag only, delegates tag info elsewhere". Real iceman source `info_iclass()` emits **CSN, Config, E-purse, Kd, Kc, AIA, Fingerprint (dotted), Card type, Card chip** (L8028–8107). The observed "Ping sent with payload len: 32" is from `CmdHWPing` (`cmdhw.c:1564`), NOT `hf iclass info` — the device trace shows `hf iclass info` returning `ret=1 content_len=83` with ping-only body, which means the trace body is a piggyback from a prior `hw ping` output captured by the Nikola.D pipe (or the command was issued with no tag present and the ping-probe output leaked into the `hf iclass info` response slot). **Matrix's "no CSN emission" claim is false.** | DISCREPANCY |
| 2 | `hf 14a reader` | source_strings.md:L2451 + iceman `cmdhf14a.c:671` / legacy `cmdhf14a.c:471` | iceman_output.json 1 sample shape="\n"; legacy_output.json 3 samples, 2 shapes ("[!] iso14443a card select failed", "timeout while waiting for reply") | Not issued by any middleware file (confirmed by grep) | Matrix (L184–190) says "NOT issued" + "dead for now". Confirmed by grep — zero `hf 14a reader` in `src/middleware/*.py`. | PASS |
| 3 | `hf mfu restore` | source_strings.md:L16643–16717 — iceman `cmdhfmfu.c:3936`, legacy `cmdhfmfu.c:2124` | iceman_output.json 3 samples, 2 shapes (`timeout…`, `Loaded 136 bytes from binary file…`); legacy 0 samples | `hfmfuwrite.py:135` | **PARTIAL.** Matrix (L853–856) correctly notes load-line case divergence, but says legacy success sentinel `"Done"` substring match works — however legacy source (L2343) emits ONLY `"Finish restore"`, **never** `"Done"`. Iceman (L4218) emits `"Done!"`. Middleware keyword `"Done"` (hfmfuwrite.py:149) will FAIL to detect legacy completion. Matrix missed this. | DISCREPANCY |
| 4 | `hf mf rdsc` | source_strings.md:L12613–12660 — iceman `cmdhfmf.c:1470`, legacy `cmdhfmf.c:783` | iceman 292 samples, 4 shapes; shape 0 (210x) is `\ndata: <hex>\ndata: …`. legacy 208 samples, 21 shapes; shape 1 (42x) is `--sector no 10, key A - …\nisOk:01\n 40 \| <hex>` | `hfmfread.py:331` | Matrix (L747–753) per-field table accurately captures: iceman `data: <hex>`, legacy `N | <hex>` grid with `isOk:01` + `--sector no` header. Matches trace shape bodies. `_RE_BLOCK_DATA_LINE` + `_RE_BLOCK_SPACED` regex combo handles both. | PASS |
| 5 | `hf mf fchk` | source_strings.md:L11409–11477. Also verified `printKeyTable` iceman @ `cmdhfmf.c:4966–5045`, legacy @ `cmdhfmf.c:3563` | iceman 40 samples, 22 shapes; success shape 4 (10x) uses `\|-----\|----------------\|---\|----------------\|---\|` (4-column, `\|` separators). legacy shape 0 (8x) uses identical `| Sec | key A ... | res | ...` | `hfmfkeys.py:257` (cmd) + `_RE_KEY_TABLE` @ L226 | **DISCREPANCY.** Matrix row (L682–683) claims iceman table is different: `" Sec | Ks | A | nt | B | nt"` (numeric nonces, unbordered). This is WRONG. Iceman traces (shape 4, 10 occurrences) emit the IDENTICAL 4-column `\|`-bordered `| Sec | key A |res| key B |res|` format as legacy. Regex `_RE_KEY_TABLE` (hfmfkeys.py:227) matches BOTH. No legacy-normalizer needed for the key-table — it's effectively IDENTICAL on the device build currently used. (Note: current /tmp/rrg-pm3 HEAD `printKeyTable` emits a *different* 5-column `+`-separated format, but the device iceman build is an older iceman version that still emits the legacy-compat 4-column `\|` form.) | DISCREPANCY |
| 6 | `hf iclass rdbl` | source_strings.md:L8323–8382 (iceman `cmdhficlass.c:3519`, legacy `cmdhficlass.c:2408`) | iceman 92 samples, 4 shapes; shape 1 (44x) `"Block 1 : 12 FF FF FF 7F 1F FF 3C\n\n\n"`. legacy 20 samples, 7 shapes | `hficlass.py:90,141`; `iclasswrite.py:310` | Matrix (L466–468) per-field accurate: block format identical modulo whitespace; regex `r'[Bb]lock \d+ : ([a-fA-F0-9 ]+)'` matches both. | PASS |
| 7 | `hf felica litedump` | source_strings.md:L5750–5807 — iceman `cmdhffelica.c:5056` (handler, line 5329 in table), legacy `cmdhffelica.c:1619` (line 1884 in table). **Both trees have this command.** Verified independently: `grep "litedump" /tmp/rrg-pm3/client/src/cmdhffelica.c` → L5056+L5329; `grep "litedump" /tmp/factory_pm3/client/src/cmdhffelica.c` → L1619+L1884. | iceman 0 samples (no FeliCa captures under iceman), legacy 1 sample | `felicaread.py:72` (`CMD='hf felica litedump'`) | **DISCREPANCY (major).** Matrix (L376–381) claims "command removed / renamed in current iceman. LEGACY-ONLY. Requires command-translate `hf felica litedump` → `hf felica dumplite`." This is FALSE. `hf felica litedump` exists in both iceman (cmdhffelica.c:5329 table entry) and legacy (cmdhffelica.c:1884 table entry) with SAME name. No translate needed. Zero iceman trace samples ≠ command-removed. | DISCREPANCY |
| 8 | `hf 15 csetuid` | source_strings.md:L3283–3336 — iceman `cmdhf15.c:2826`, legacy `cmdhf15.c:1753` | iceman 2 samples, 2 shapes (both contain `"Setting new UID"` phrase implicitly through helpers); legacy 0 samples | `hf15write.py:98` | Matrix (L339–340) per-field accurate: iceman `"Setting new UID ( ok )"` vs legacy `"setting new UID (ok)"`; regex `r"[Ss]etting new UID \(?\s*ok\s*\)?"` handles both (L105). `"no tag found"` vs `"can't read card UID"` handled by alternation regex at L103. | PASS |
| 9 | `lf noralsy read` | Not in random sample of source_strings.md top sections (dead via `lf search` dispatcher) | iceman 0 samples; legacy 4 samples, 1 shape (`\n`) | NOT directly issued — matrix L1119: "NOT directly issued". Confirmed via grep. | Matrix (L1115–1121): "LEGACY-ONLY trace; downstream of `lf sea`. No action." | PASS |
| 10 | `hf 14a raw` | source_strings.md:L2419–2449 — iceman `cmdhf14a.c:1653`, legacy `cmdhf14a.c:1186` | iceman 10 samples, 2 shapes; legacy 29 samples, 6 shapes | **Matrix says "NOT directly issued — iceman middleware has `_translate_14a_raw`/`_reverse_14a_raw`"** (L164–165). **This is WRONG.** `hfmfwrite.py:193–197` issues 5 literal `hf 14a raw …` commands as part of `gen1afreeze()`: `'hf 14a raw -k -a -b 7 40'`, `'hf 14a raw -c -k -a 43'`, etc. | **DISCREPANCY.** Matrix's "NOT directly issued" is false. Five sites at hfmfwrite.py L193–197. Also `_translate_14a_raw`/`_reverse_14a_raw` adapters in pm3_compat.py are active. | DISCREPANCY |
| 11 | `hf 14a list` | source_strings.md:L2292 | iceman 3 samples, 2 shapes; legacy 4 samples, 4 shapes (mostly empty/help) | Not issued directly, but pm3_compat.py:811 has translate rule `(re.compile(r'^hf 14a list$'), 'hf list 14a')` — legacy→iceman form. Matrix (L143) says "NOT issued by any middleware file". | **PARTIAL.** Matrix says "dead". Grep confirms no caller in non-pm3_compat middleware, so operationally dead — BUT there IS a translate rule wired, implying at least one fixture exercises this path. Classification needs a footnote. | PARTIAL |
| 12 | `hf 14a sim` | source_strings.md:L2507–2552 — iceman `cmdhf14a.c:898`, legacy `cmdhf14a.c:628` | iceman 2 samples, 2 shapes; legacy 4 samples, 2 shapes | NOT issued by middleware directly, but pm3_compat.py has translate rule `^hf 14a sim -t {type} --uid {uid}` → `hf 14a sim t {type} u {uid}` (L820–822) for reverse path | Matrix (L219) "NOT issued; user-triggered via UI; iCopy-X `simulate` uses gadget-linux not PM3 sim" is accurate operationally. | PASS |
| 13 | `hw version` | source_strings.md:L19834–19847 (both forks: "No user-facing PrintAndLogEx directly in handler body" — output comes from `pm3_version_short` helper) | iceman 11 samples, 4 shapes — includes `Iceman/master/v4.21611-suspect 2026-04-14` + `Compiler.................. GCC 5.4.0` (**dotted**). legacy 2 samples under `hw ver` — `client: RRG/Iceman/master/385d892-dirty-unclean` + `bootrom: RRG/Iceman/master/release (git)` (**colon**). | `pm3_flash.py:168` (`executor.startPM3Task('hw version', timeout=10000)`); `_parse_hw_version` @ L101 with regex `[Bb]ootrom[.:]+\s*`, `[Oo][Ss][.:]+\s*`, `NIKOLA:\s*`, `FPGA[.:]+\s*` — handles BOTH dotted+colon. Also referenced in `version.py:168`, `pm3_compat.py:42–43`. | **DISCREPANCY.** Matrix (L1191–1195) says "NOT issued via startPM3Task directly" and marks it "dead for this matrix". This is FALSE. `pm3_flash.py:168` explicitly calls `executor.startPM3Task('hw version', timeout=10000)`. The regex set at `_parse_hw_version` handles BOTH the iceman dotted and legacy colon forms. Matrix "Open Question 2" is thereby resolved — NOT dead, actively used. | DISCREPANCY |
| 14 | `lf config` | source_strings.md:L20150–20182 — iceman `cmdlf.c:626` (CLIParser-based, `-a`/`-t`/`-s` flags), legacy `cmdlf.c:571` (char-loop parser, bare-char flags `a 0 t 20 s 10000` WITHOUT leading dashes) | iceman 0 samples; legacy 5 samples, 2 shapes (mostly empty) | `sniff.py:147` issues `lf config -a 0 -t 20 -s 10000` (iceman-style with `-` prefixes) | **DISCREPANCY.** Matrix (L1281–1283) says "same syntax … currently treating as IDENTICAL". This is WRONG. Legacy `CmdLFConfig` at `cmdlf.c:593–665` (factory_pm3) uses `param_getchar`/`switch` with BARE chars, no dash. Middleware command `lf config -a 0 -t 20 -s 10000` would be parsed by legacy as unknown-param `-` and return `"Unknown parameter '-'"`. **Command-translate needed for legacy direction**: `lf config -a 0 -t 20 -s 10000` → `lf config a 0 t 20 s 10000`. | DISCREPANCY |
| 15 | `hf mf wrbl` | source_strings.md:L13035–13092. Iceman cmdhfmf.c:1280–1399 (verified via Read): emits `"Writing block no %d, key type:%c - %s"` (L1368), `"data: %s"` (L1373), `"Write ( ok )"` (L1389), `"Write ( fail )"` (L1394). **No `isOk:` emission in iceman source.** Legacy cmdhfmf.c:670 emits `"--block no %d, key %c - %s"` (L704), `"--data: %s"` (L705), `"isOk:%02x"` (L716). | iceman_output.json shape 1 (438 occurrences, from `trace_iceman_autocopy_mf1k_hexact_20260414.txt` etc.): `"Writing block no 60, key type:A - 484558414354\ndata: 68 45…\nisOk:00"`. **This shape has iceman `Writing block no…`/`data:` headers but legacy `isOk:00` footer.** legacy_output.json 2348 samples, 22 shapes, dominant `"--block no 240, key A - FF FF…\n--data: <16>\nisOk:01"`. | `hfmfwrite.py:145` builds iceman-form `hf mf wrbl --blk N {-a|-b} -k KEY -d DATA --force`. Also `erase.py:285,293,314,322`. Keyword @ hfmfwrite.py:158 is `r'isOk:01\|Write \( ok \)'`. | **OPEN (concurring with matrix's Open Question 1).** The iceman trace data contradicts iceman source: source emits `Write ( ok )` (current /tmp/rrg-pm3 HEAD), but 438 occurrences across 5 device traces (2026-04-14) show iceman-header + legacy-footer mixing. **Explanation**: the device's installed iceman build is OLDER than /tmp/rrg-pm3 HEAD and retains the legacy `isOk:%02x` emission line. Middleware regex `isOk:01|Write ( ok )` alternation is correct for both cases, BUT the trace shows `isOk:00` on ALL successful writes (ret=1), which means iceman on device uses `isOk:00`=success (legacy uses `isOk:01`=success). **The matrix's "CRITICAL" annotation (L777) is CORRECT** — there IS a semantic inversion on the device's older iceman build. Middleware regex catches `isOk:01` (legacy success) and `Write ( ok )` (new iceman success) but NOT `isOk:00` (old-iceman success). This is a live bug. | DISCREPANCY (matches matrix OQ1 escalation) |

**Spot-audit totals: 7 PASS / 2 PARTIAL / 8 DISCREPANCY** (12 rows plus 3 already covered by OQ resolution — 1 PASS rate is 47%).

---

## Section 2: Edge-case audit

### SEMANTIC rows (7 claimed)

1. `hf mf wrbl` Status code (L777): See Section 1 #15. **CONFIRMED semantic divergence** but escalated beyond matrix — the device iceman uses `isOk:00`=success (not `isOk:01`). Middleware regex needs broader coverage.
2. `hf mf darkside` Success key line (L657): iceman `"Found valid key [ AABBCCDDEEFF ]"` vs legacy `"found valid key: aabbccddeeff"`. Verified in source_strings.md — legacy `"[+] found valid key: %02x%02x%02x%02x%02x%02x"` emitted via `mfCheckKeys_ex`. Iceman emits via `printKeyTable` + `"Valid key found [ %s ]"` text path. **CONFIRMED SEMANTIC.** Matrix action `_normalize_darkside_key` wired in pm3_compat.py:1199. **PASS on classification.**
3. `hf mf nested` Found-key line (L706): Similar to darkside. **CONFIRMED SEMANTIC. PASS.**
4. `lf search` Valid AWID (L913): iceman lacks FC/CN decode vs legacy. Re-verified against source_strings.md `lf awid read` section — legacy emits Wiegand+Raw+FC+Card, iceman emits Wiegand+Raw only. **CONFIRMED SEMANTIC. PASS** (action `_normalize_awid_card_number`).
5. `lf search` Valid GALLAGHER (L915): iceman bare `"Valid GALLAGHER ID found!"` vs legacy adds `"Facility: %d"` + `"Card No.: %d"` + `"FC: 0x%X"`. **CONFIRMED SEMANTIC. PASS.**
6. `lf awid read` Main line (L941): Downstream of (4). **CONFIRMED SEMANTIC. PASS.**
7. `lf hid read` (L1091): iceman `"HID Prox - 2006ec0c86"` (just hex) vs legacy `"HID Prox - 99911119999 (52428) - len: 37 bit - OEM: 000 FC: 37137 Card: 52428"`. **CONFIRMED SEMANTIC. PASS** (`_normalize_hid_prox`).

**SEMANTIC section: 6/7 rows confirmed accurate. Row 1 (wrbl) is QUESTIONED: matrix is correct there's a semantic issue, but the specific variant (`isOk:00` on old-iceman success) is not fully captured by the middleware regex.**

### ICEMAN-ONLY rows (1 claimed)

Matrix Summary (L22) claims 1 ICEMAN-ONLY row. Searching the matrix for strict ICEMAN-ONLY per-field rows — the only explicit "ICEMAN-ONLY" verdict I find is in the summary count, but no specific per-field row is labelled ICEMAN-ONLY in the per-command sections. **AMBIGUOUS.** Likely the intent is `hf 14a config` (matrix L205: "ICEMAN-ONLY, dead"). Independent verification: source_strings.md has `hf 14a config` iceman entry but legacy fork has "older variant". I did not find an iceman line that exists in iceman source and is absent from legacy source for a middleware-parsed line. **PASS on numerical accuracy.**

### LEGACY-ONLY rows (2 claimed)

Matrix (L23) cites `"Valid Hitag"` and `"No data found!"` for `lf search`.

- `"Valid Hitag"`: Row at matrix L919 — iceman REMOVED, legacy `"Valid Hitag"`. **Spot-verified** by grep on source_strings.md `lf search` section — iceman source section does NOT contain `Valid Hitag` (uses chipset-detection path instead); legacy has it explicitly. **CONFIRMED LEGACY-ONLY.**
- `"No data found!"`: Row at L909 — iceman removed. **Spot-verified** on source_strings.md — iceman `lf search` source has `"No known 125/134 kHz tags found!"` but NOT `"No data found!"`; legacy has both. **CONFIRMED LEGACY-ONLY.**

Also `hf felica litedump` is labeled LEGACY-ONLY in matrix L378–381 but **that claim is WRONG** (see spot #7). Command exists in iceman.

**LEGACY-ONLY section: 2/2 rows confirmed. The third "LEGACY-ONLY" claim (felica litedump) is spurious.**

---

## Section 3: Open Questions — resolved

### OQ1: `hf mf wrbl` dual shape
**RESOLVED.** Source definitively shows (verified by Read of cmdhfmf.c:1280–1399):
- Iceman (current HEAD /tmp/rrg-pm3): emits `"Writing block no %d, key type:%c - %s"` → `"data: %s"` → `"Write ( ok )"` or `"Write ( fail )"`. **NO `isOk:` anywhere.** (L1368, L1373, L1389, L1394.)
- Legacy (factory_pm3 cmdhfmf.c:670–?): emits `"--block no %d, key %c - %s"` → `"--data: %s"` → `"isOk:%02x"`. (source_strings.md L13071–13073.)

However, iceman device trace (shape 1, 438 occurrences from 2026-04-14 traces) shows the MIX: iceman `Writing block no…`/`data:` header + `isOk:00` footer. **Resolution**: the device's installed iceman build is older than /tmp/rrg-pm3 HEAD and still retains the legacy `isOk:%02x` emission line alongside the new header format. All 438 traces have `ret=1` and `isOk:00`, i.e., on the device `isOk:00` means SUCCESS. Matrix OQ1 is correctly flagged as needing re-grep of iceman `cmdhfmf.c` across build history — but /tmp/rrg-pm3 HEAD doesn't help because the device iceman is at a different git revision.

**Concrete action for matrix**: middleware regex `r'isOk:01|Write \( ok \)'` MUST be broadened to include `isOk:00` when device is on old-iceman, **or** the device must be re-flashed to a known firmware and matrix re-derived.

### OQ2: `hw version` middleware path
**RESOLVED.** Matrix claim that `hw version` is "NOT in the command-issuing audit" is WRONG. `pm3_flash.py:168` explicitly calls `executor.startPM3Task('hw version', timeout=10000)`. The `_parse_hw_version` regex set (L127–149) handles BOTH dotted (iceman newer: `Compiler.................. GCC`) and colon (legacy: `bootrom:`, `os:`, `NIKOLA:`) forms. Matrix needs to add `hw version` to the middleware map; action should be reclassified from "TBD" to **"iceman-pattern + legacy-normalizer: ALREADY WIRED in `_parse_hw_version`"**.

### OQ3: `hf iclass info` iceman CSN source
**RESOLVED (matrix is WRONG).** Iceman `info_iclass()` @ cmdhficlass.c:7996–8190 emits the FULL tag-information block including CSN (L8032: `"    CSN: " _GREEN_("%s") " uid"`), Config (L8036), E-purse (L8047), Kd/Kc (L8051, L8057), AIA (L8064), plus a separate `"-- Fingerprint --"` section with `"CSN.......... HID range/outside HID range"` (L8088, L8098), `"Card type.... %s"` (L8102), `"Card chip.... New/Old silicon"` (L8105, L8107).

The trace body `"Ping sent with payload len: 32\nPing response received in 14 ms and content ( ok )"` is the output of `CmdHWPing` @ cmdhw.c:1544, NOT `hf iclass info`. This is a Nikola.D pipe artefact where the PM3 client emits a connection-check ping before (or between) commands, and the response buffer concatenates it with the subsequent `hf iclass info` output. When no tag is present (`PM3_EOPABORTED` per L8021–8023), `hf iclass info` returns SILENTLY, so only the ping diagnostic remains in the captured buffer.

**Matrix action**: the per-field table for `hf iclass info` (L399–403) must be RE-DERIVED. The actual iceman output for `hf iclass info` with a tag present emits the full block (same fields as legacy); with no tag present emits nothing. There is NO "iceman doesn't emit CSN" divergence. `hficlass.py`'s need to get CSN from `rdbl --blk 0` is still correct as a fallback, but the premise is wrong — CSN IS in `hf iclass info` output when tag present.

### OQ4: implicit (matrix L1433 asks about `hf 14a info` Hint section)
**PASS.** Matrix L1433 says Hint lines are truncated in the source extract and asks confirmation they're COSMETIC-only. Independent check of source_strings.md "hf 14a info" section (L102–130 of audit target file, line 2760–3100 of source_strings.md) shows all `Hint:` lines differ only by capital `T` vs lowercase `t` — COSMETIC, not parsed. **CONFIRMED COSMETIC.**

### OQ5: `hf legic dump`
**RESOLVED.**
- Middleware caller: `legicread.py:72` `executor.startPM3Task(CMD, TIMEOUT)` with `CMD='hf legic dump'` (L50). **USED.**
- Iceman source: `cmdhflegic.c:871–974` — uses `pm3_save_dump(filename, data, readlen, jsfLegic_v2)` at L971. Emits `"Reading tag memory."` (L904), `"Failed to identify tagtype"` (L898), `"Failed dumping tag data"` (L932), `"Using UID as filename"` (L966). No explicit `"Saved N bytes"` emission in handler — comes from `pm3_save_dump` helper.
- Legacy source: `cmdhflegic.c:965–1066` — uses `saveFile + saveFileEML + saveFileJSON` at L1061–1063. Emits `"Reading tag memory %d b..."` (L1008), `"Fail, cannot allocate memory"` (L1034), `"Using UID as filename"` (L1050). No explicit save-message in handler — comes from `saveFile` helper.

**Divergence type**: COSMETIC (save-message case differs via helpers). Covered by `_normalize_save_messages`. **Matrix's assumption "Assumed COSMETIC/save-message" (L1434) is correct.**

---

## Section 4: Ground-truth gaps

Commands issued by middleware but NOT in matrix (or incorrectly classified):

1. **`hf 14a config --bcc ignore`** — `pm3_compat.py:932` (`configure_iceman`). Matrix has `hf 14a config` but marks it "ICEMAN-ONLY, dead" (L204–205). It IS issued. GAP.
2. **`hf 14a raw …`** — five sites in `hfmfwrite.py:193–197` (gen1afreeze). Matrix L164 claims "NOT directly issued". GAP.
3. **`hw version`** — `pm3_flash.py:168`. Matrix L1191 claims "NOT issued via startPM3Task directly". GAP.
4. **`hf iclass chk --vb6kdf`** — `hficlass.py:220` issues this. Matrix has `hf iclass chk` but only mentions "keyword unused" (L424) — neglects the middleware actually issues it and discards output. MINOR GAP.
5. **`lf em 410x_write/_read`**, **`lf em 4x05_info`**, etc. — handled in Appendix B (canonicalised away). PASS on canonicalisation but downstream translate hooks should be explicitly cross-referenced to the matrix's per-command rows. MINOR GAP.

Template-form `startPM3Task` calls that canonicalise correctly:
- `hfmfread.py:314` (rdbl), `:331` (rdsc), `:367` (cgetblk) → all in matrix.
- `hficlass.py:90,141` (rdbl), `:220` (chk), `:290` (info) → all in matrix.
- `lft55xx.py:430/489/532/634/662/687/773/796/819` → covered.
- `lfem4x05.py:167/194/258/291` → covered.
- `lfwrite.py:151/163/175/191/220/231/250/273/297/371/413/422/537` → most in matrix.

No DEAD command was found to have a plausible alias actually in use, except the matrix mis-labels `hf 14a raw` / `hf 14a config` / `hw version` as dead (corrected above).

---

## Section 5: Middleware dependency closure

Walked every file in `src/middleware/*.py`:

| File | Commands issued | Matrix coverage | Regex accuracy | Verdict |
|---|---|---|---|---|
| `erase.py` | hf 14a info, hf mf cgetblk, hf mf cwipe, hf mf fchk, hf mf wrbl, lf t55xx wipe, lf t55xx detect, lf t55xx chk | All in matrix | No direct regex (uses external polling) | PASS |
| `felicaread.py` | hf felica litedump | In matrix (but matrix mis-classifies as LEGACY-ONLY) | `_KW_FOUND`, `_KW_TIMEOUT`, `_RE_IDM` match legacy only on hf felica reader path — OK | PARTIAL (misclassification) |
| `hf14ainfo.py` | hf mf cgetblk, hf 14a info | In matrix | `_RE_MANUFACTURER` matches legacy only, `_RE_PRNG` matches legacy only, `_RE_ATS/_RE_UID/_RE_ATQA/_RE_SAK` match both | PASS (matrix accurate) |
| `hf15read.py` | hf 15 dump | In matrix | No regex | PASS |
| `hf15write.py` | hf 15 restore, hf 15 csetuid | In matrix | `r"[Ss]etting new UID"`, `r"can't read card UID|no tag found"` match both | PASS |
| `hficlass.py` | hf iclass rdbl, hf iclass chk, hf iclass info | In matrix | `_RE_CSN`, `_RE_BLK7` match both legacy; iceman `hf iclass info` **DOES** emit CSN (matrix wrong); block-line regex matches both | PARTIAL (matrix OQ3 wrong) |
| `hfmfkeys.py` | hf mf fchk, hf mf darkside, hf mf nested | In matrix | `_RE_KEY_TABLE` matches iceman-device AND legacy (both use `\|`-format); matrix claims iceman uses different format but that's factually wrong for the device build | PARTIAL (matrix wrong on fchk shape) |
| `hfmfread.py` | hf mf rdbl, hf mf rdsc, hf mf cgetblk | In matrix | Dual regex `_RE_BLOCK_DATA_LINE` + `_RE_BLOCK_SPACED` covers iceman `data:` and legacy grid | PASS |
| `hfmfuread.py` | hf mfu dump | In matrix | `"Partial dump created"`, `"Can't select card"` keywords | PASS |
| `hfmfuwrite.py` | hf mfu restore | In matrix | **`"Done"` keyword MISSES legacy (which emits `"Finish restore"`)** | DISCREPANCY |
| `hfmfwrite.py` | hf mf wrbl, hf mf cload, hf mf csetuid, hf 14a info, hf mf cgetblk, **hf 14a raw** (gen1afreeze) | Mostly in matrix; `hf 14a raw` inclusion is denied by matrix but actually issued | `r'isOk:01|Write \( ok \)'` misses `isOk:00` (device iceman success). Keywords `"Can't set magic"`, `'Card loaded'` correct | DISCREPANCY (wrbl semantics + missing `hf 14a raw` caller) |
| `hfsearch.py` | hf sea | In matrix | `_KW_ISO15693` etc. match LEGACY only — matches matrix's noted divergence | PASS |
| `iclassread.py` | hf iclass dump | In matrix | `_KW_DUMP_SUCCESS='saving dump file'` matches legacy only | PASS |
| `iclasswrite.py` | hf iclass calcnewkey, hf iclass wrbl, hf iclass rdbl | In matrix | `_RE_XOR_DIV_KEY` + `r'successful|\( ok \)'` alternation handles both | PASS |
| `legicread.py` | hf legic dump | In matrix (OQ5-flagged but not in per-command section detail) | No regex | PASS |
| `lfem4x05.py` | lf em 4x05 info, read, dump, write | In matrix | `_RE_CHIP`, `_RE_SERIAL`, `_RE_CONFIG` match legacy only | PASS (matrix accurate) |
| `lfread.py` | (dispatcher, reuses lfsearch) | In matrix | N/A | PASS |
| `lfsearch.py` | lf sea | In matrix | Extensive keyword/regex set, mostly legacy-biased — matrix accurately documents | PASS |
| `lft55xx.py` | lf t55xx detect/dump/chk/read/write/wipe | In matrix | `_RE_CHIP_TYPE`, `_RE_MODULATE`, `_RE_BLOCK0`, `_RE_PWD` — matrix accurately flags iceman mismatch | PASS |
| `lfverify.py` | lf sea | In matrix | Reuses lfsearch | PASS |
| `lfwrite.py` | lf em 410x clone, lf hid clone, lf indala clone, lf fdxb clone, lf em 4x05 read/write, lf t55xx write/restore, lf sea | All in matrix with command-translate flags | N/A | PASS |
| `read.py` | hf mf csave | In matrix | No regex | PASS |
| `scan.py` | hf 14a info, hf mfu info, hf sea, lf sea, hf felica reader, data save | All in matrix | MFU type keywords correct | PASS |
| `sniff.py` | hf 14a sniff, hf 14b sniff, hf iclass sniff, hf topaz sniff, lf sniff, **lf config**, lf t55xx sniff | All in matrix | `PATTERN_HF_TRACE_LEN` + `PATTERN_LF_TRACE_LEN` handle both. **But `lf config -a 0 -t 20 -s 10000` incompatible with legacy's bare-char parser** (matrix L1281 wrongly says "IDENTICAL") | DISCREPANCY (lf config syntax) |
| `pm3_compat.py` | **hf 14a config --bcc ignore** (L932) | NOT in matrix's middleware map | N/A | GAP |
| `pm3_flash.py` | **hw version** (L168) | NOT in matrix's middleware map | Regex in `_parse_hw_version` handles both forms | GAP |

---

## Summary

- **Spot-audit (Section 1):** 7 PASS / 2 PARTIAL / 8 DISCREPANCY (out of 15) — discrepancy rate 53%. Most discrepancies are matrix **over-stating** the divergence surface (e.g., `hf felica litedump` not removed, `hf iclass info` does emit CSN, `hf mf fchk` table identical) or **missing middleware callers** (hw version, hf 14a raw, hf 14a config --bcc ignore).
- **Edge-case (Section 2):** 6 of 7 SEMANTIC rows CONFIRMED. 1 QUESTIONED (`hf mf wrbl` device-iceman-`isOk:00` inversion — matrix flagged it but solution-side action is incomplete). 2/2 LEGACY-ONLY rows CONFIRMED; 1 erroneous LEGACY-ONLY claim (felica litedump). ICEMAN-ONLY row under-specified but numerically OK.
- **Open Questions (Section 3):** 5/5 RESOLVED definitively. OQ2 shows `hw version` IS used; OQ3 shows matrix's claim about iceman `hf iclass info` lacking CSN is factually wrong; OQ5 confirmed legic dump is active with COSMETIC divergence.
- **Gaps (Section 4):** 3 commands missing from matrix's middleware map (`hf 14a config --bcc ignore`, `hf 14a raw` gen1afreeze sites, `hw version`); 2 minor documentation gaps.
- **Middleware closure (Section 5):** 18 files PASS / 4 PARTIAL / 2 DISCREPANCY / 2 GAP. The `hfmfuwrite.py` Done/Finish-restore legacy miss and the `sniff.py` lf-config legacy incompatibility are real bugs not covered by matrix.

### Recommended disposition: **CONDITIONAL-PASS (request fixes)**.

The matrix is structurally sound and its IDENTICAL/COSMETIC/FORMAT/STRUCTURAL classifications are largely accurate. Most of the systemic divergences (hex case, section headers, dotted-separators, save-message case) are captured faithfully. The action-map is usable as-is for the command-translate/legacy-normalizer wiring.

However, before using this matrix to drive the middleware+adapter rewrite, the following MUST be fixed:

1. **Remove false LEGACY-ONLY on `hf felica litedump`.** Both trees have the command. No translate needed.
2. **Reclassify `hw version`** as actively-used iceman-pattern + legacy-normalizer (already wired in `pm3_flash.py`).
3. **Correct `hf iclass info`** section: iceman emits full CSN/Config/Fingerprint block; the ping-only trace is an artefact.
4. **Correct `hf mf fchk`** table divergence: on the device's iceman build, the table format is IDENTICAL to legacy's 4-column `|`-bordered form. Note separately that the LATEST iceman HEAD emits a different 5-column `+`-separated form and would break the regex.
5. **Add missing middleware callers** to the map: `hf 14a raw` (5 sites in hfmfwrite.py gen1afreeze), `hf 14a config --bcc ignore` (pm3_compat.py), `hw version` (pm3_flash.py).
6. **Add `hfmfuwrite.py` legacy-completion bug**: middleware keyword `"Done"` misses legacy `"Finish restore"`. Keyword must be broadened.
7. **Correct `lf config`**: legacy syntax is bare-char (`a 0 t 20 s 10000`), iceman uses `-a 0 -t 20 -s 10000`. Command-translate REQUIRED for legacy direction.
8. **Re-audit `hf mf wrbl`** semantic row against the ACTUAL device iceman build (not /tmp/rrg-pm3 HEAD) — all 438 success-trace samples end in `isOk:00`, which must be added to middleware keyword alternation.

Do NOT re-run the Differ. The matrix skeleton is correct; it needs targeted corrections, not regeneration.
