# Phase 3 → Phase 4 Gap Log

_Transition-period issues: middleware has been iceman-ified (Phase 3) but pm3_compat.py adapter still runs iceman→legacy direction (Phase 4 work). Live device regressions expected during Phase 3; Phase 4 reconciliation fixes all entries in this log._

_Generated per Option B user directive (2026-04-17): accept per-module transition breakage, reconcile at end of Phase 3 with Phase 4._

## Format

Each entry:
- **Flow**: P3.X name
- **Middleware now iceman-native**: list of regex/keyword literals
- **Adapter still running iceman→legacy**: cite pm3_compat.py:line of the conflicting normalizer
- **Live symptom**: what breaks on iceman FW (observable UI behavior or test assertion failure)
- **Phase 4 action**: disable/invert which normalizer + any paired changes

---

## P3.1 Scan flow

### Entry: hf 14a info dotted-field regressions

- **Middleware now iceman-native**:
  - `hf14ainfo._RE_PRNG = r'Prng detection\.+\s+(\w+)'` — iceman `cmdhf14a.c:3326/3328/3330` emits 5-dot `Prng detection..... weak`/`Prng detection..... hard`, 6-dot `Prng detection...... fail`.
  - `hf14ainfo._KW_STATIC_NONCE = 'Static nonce....... yes'` — iceman `cmdhf14a.c:3319`, 7 dots literal.
  - `hf14ainfo._KW_GEN1A = 'Magic capabilities... Gen 1a'` — iceman `mifare/mifarehost.c:1710`, 3 dots literal.
  - `hf14ainfo._KW_GEN2_CUID = 'Magic capabilities... Gen 2 / CUID'` — iceman `mifare/mifarehost.c:1718`, 3 dots literal.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1070-1071` `_RE_DOTTED_SEPARATOR = re.compile(r'^(\s*\S.*?\S)\.{3,}\s+', re.MULTILINE)`
  - `pm3_compat.py:1122` `_post_normalize()` applies `_RE_DOTTED_SEPARATOR.sub(r'\1: ', text)` generically to every response (runs after command-specific normalizers in `translate_response()` at `pm3_compat.py:1929`).
  - `pm3_compat.py:1273/1276/1282` `_normalize_magic_capabilities` (`_RE_MAGIC_DOTTED = re.compile(r'Magic capabilities\.{3,}\s+')`) explicitly rewrites `Magic capabilities... ` → `Magic capabilities : `. Wired for `hf 14a info` at `pm3_compat.py:1836` (`[_normalize_magic_capabilities, _normalize_manufacturer]`).
- **Live symptom (iceman FW)**:
  - `hf14ainfo.has_static_nonce()` returns False even when card is static-nonce (the 7-dot string has been rewritten to `Static nonce: yes` before the keyword match).
  - `hf14ainfo.is_gen1a_magic()` fallback keyword path returns False on Gen1a cards (`Magic capabilities... Gen 1a` rewritten to `Magic capabilities : Gen 1a`).
  - `hf14ainfo.get_prng_level()` returns empty string because `_RE_PRNG` expects dotted form but sees `Prng detection: weak`.
  - Observable in test: `tests/phase3_trace_parity/test_scan_flow.py` — 6 of 10 `hf 14a info` samples FAIL the `Prng detection` get_prng_level predicate; iceman_output.json was captured post-current-adapter so bodies already carry the legacy colon form.
- **Phase 4 action**:
  - Remove `_normalize_magic_capabilities` from `_RESPONSE_NORMALIZERS['hf 14a info']` (`pm3_compat.py:1836`).
  - In `_post_normalize()` (`pm3_compat.py:1109-1136`), drop the generic `_RE_DOTTED_SEPARATOR.sub` call OR gate it on `_current_version == PM3_VERSION_ORIGINAL` so legacy FW still gets dotted→colon conversion for middleware parity.
  - Before removing, grep middleware for `Prng detection:` / `Static nonce: yes` / `Magic capabilities :` literals to confirm no other consumer still expects the legacy colon shape; cross-check against P3.2-P3.N refactors.
  - Re-run `tests/phase3_trace_parity/test_scan_flow.py` — live samples should flip PASS once iceman_output.json is re-captured with the Phase 4 adapter in place.

### Entry: hf 14a info MANUFACTURER label injection

- **Middleware now iceman-native**:
  - `hf14ainfo._RE_MANUFACTURER = r'MANUFACTURER:\s*(.*)'` — target legacy shape only. Iceman `cmdhf14a.c:2837` emits `" " _YELLOW_("%s")` — an indented bare line with no `MANUFACTURER:` prefix.
  - Explicit inline `TODO(Phase 4)` at `hf14ainfo.py:100` documents the gap.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1755-1783` `_normalize_manufacturer()` injects `MANUFACTURER: ` prefix on iceman output by prepending the label when it detects a known manufacturer substring (NXP, Infineon, etc.) on an indented line.
  - Wired for `hf 14a info` at `pm3_compat.py:1836`.
- **Live symptom (iceman FW, adapter disabled)**:
  - `hf14ainfo.get_manufacturer()` returns empty string on iceman output.
  - `parser()` Priority 5/6 `POSSIBLE` classification still works (manufacturer key is optional), but `M1_POSSIBLE_*` result dict lacks `manufacturer`, so Scan→Simulate prepop of the manufacturer field fails.
- **Phase 4 action**:
  - KEEP `_normalize_manufacturer` active under iceman (inverse of dot normalizers — this one INJECTS, not strips). Middleware regex targets legacy shape deliberately so the iceman-native flow relies on the adapter.
  - Alternative: broaden `_RE_MANUFACTURER` in middleware to `r'(?:MANUFACTURER:\s*|^\s{4,})(\S.+)'` multiline — trickier to avoid false positives on other indented lines.
  - Decision deferred: once Phase 4 runs, pick one path; log which.

### Entry: hf sea ISO15693 UID regression (post fix)

- **Middleware now iceman-native** (post this Fixer pass):
  - `hfsearch._RE_UID = r'UID\.{3,}\s+([0-9A-Fa-f ]+)'` — iceman `cmdhf15.c:447` emits `UID.... %s` (4 dots literal) inside `getUID()` called by `readHF15Uid()` (cmdhf15.c:465), which is the path `hf sea` exercises (cmdhf.c:197).
  - `hfsearch._KW_ISO15693 = 'Valid ISO 15693'` — iceman `cmdhf.c:198` emits `Valid ISO 15693 tag found` with space between `ISO` and `15693`.
  - `hfsearch._KW_ISO14443B = 'Valid ISO 14443-B'` — iceman `cmdhf.c:186` emits with space.
  - `hfsearch._KW_FELICA = 'Valid ISO 18092 / FeliCa'` — iceman `cmdhf.c:220` emits with space.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1078` `_RE_ISO_SPACE = re.compile(r'\bISO\s+(1\d{4})')` — strips space between `ISO` and `15693`/`14443`/`18092` in `_post_normalize()` (`pm3_compat.py:1134`). This rewrites iceman `Valid ISO 15693` → `Valid ISO15693` — making the iceman-native `_KW_ISO15693 = 'Valid ISO 15693'` match FAIL because the substring now has no space.
- **Live symptom (iceman FW, with current adapter)**:
  - `hfsearch.parser()` Check 3 (`if executor.hasKeyword(_KW_ISO15693)`) fires on empty-check because `_post_normalize` stripped the space before the keyword search.
  - Observable: ISO15693 cards appear as type 19/46 ONLY when the older adapter shape happens to preserve space; on cleanup, they fall to Default no-tag-found path.
  - `_RE_UID` was previously `r'UID:\s+([0-9A-Fa-f ]+)'` (legacy shape). Adapter `_RE_DOTTED_SEPARATOR` converts `UID.... E0 04 ...` → `UID: E0 04 ...`, so the previous regex happened to work by accident. Post-fix (this PR) the middleware targets iceman 4-dot form directly; once adapter stops converting, the native regex still works.
- **Phase 4 action**:
  - Remove `_RE_ISO_SPACE.sub` call from `_post_normalize()` (`pm3_compat.py:1134`).
  - Remove `_RE_DOTTED_SEPARATOR` call from `_post_normalize()` (`pm3_compat.py:1122`) — same generic dot stripper flagged in the hf 14a info entry above.
  - Drop `_RE_UID_ANNOTATION` stripper at `pm3_compat.py:1131` — `hf14ainfo._RE_UID = r'UID:\s+((?:[0-9A-Fa-f]{2}\s+)+)'` uses non-greedy hex-pair capture that stops at `(` naturally; the annotation stripper is now unused.
  - Remove `_normalize_iso15693_manufacturer` (`pm3_compat.py:1798-1811`) — iceman emits different manufacturer string than the legacy keyword `ST Microelectronics SA France` expects; this one is a legacy→iceman DIRECTION normalizer that broadens short iceman names to the long legacy one so the middleware keyword matches. After compat flip, middleware should target iceman's short form (`STMicroelectronics`) instead — refactor `_KW_ST_MICRO` to match iceman's emission substring.

### Entry: lf sea dotted-separator + keyword-shape regressions

- **Middleware now iceman-native**:
  - `lfsearch.REGEX_ANIMAL = r'Animal ID\.+\s+([0-9\-]+)'` — iceman `cmdlffdxb.c:572/578` emits dotted `Animal ID........... <country>-<national>` (9-11 dots, decimal).
  - `lfsearch.REGEX_EM410X = r'EM 410x(?:\s+XL)?\s+ID\s+([0-9A-Fa-f]+)'` — iceman `cmdlfem410x.c:115` emits `EM 410x ID <hex>`; iceman dropped legacy `EM TAG ID :` entirely.
  - `lfsearch.REGEX_HID = r'raw:\s+([0-9A-Fa-f]+)'` — iceman `cmdlfhid.c:235` emits `raw: %s` (lowercase); iceman removed the legacy `HID Prox - %s` emission entirely (grep of `/tmp/rrg-pm3/client/src/` yields zero matches for `HID Prox -`).
  - `lfsearch.REGEX_RAW = r'(?:Raw|raw):\s*([xX0-9a-fA-F ]+)'` — iceman per-tag demods consistently emit `, Raw: <hex>` (capital) with HID outlier lowercase. Dropped legacy `Hex|HEX|hex` alternates never emitted.
  - `lfsearch._RE_CHIPSET = r'Chipset\.+\s+(.*)'` — iceman `cmdlf.c:1601-1655` emits dotted `Chipset... <name>` (3 dots); legacy emits `Chipset detection: <name>`.
  - `lfsearch._KW_CHIPSET_DETECTION = 'Chipset...'` — iceman shape.
  - `lfsearch._RE_FC = r'FC:\s+([xX0-9a-fA-F]+)'` — iceman uniform colon.
  - `lfsearch._RE_LEN = r'len:\s+(\d+)'` — iceman lowercase only.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1290/1296/1305` `_normalize_em410x_id` rewrites iceman `EM 410x ID <hex>` → legacy `EM TAG ID      : <hex>` AND iceman `Valid EM 410x ID` → legacy `Valid EM410x ID`. After the flip, iceman middleware keyword is `'Valid EM410x ID'` (no space) — luckily the adapter output matches, but the data-line normalization corrupts the regex target.
  - `pm3_compat.py:1313/1316/1322` `_normalize_chipset_detection` rewrites iceman `Chipset... <name>` → legacy `Chipset detection: <name>` — DIRECTLY BREAKS `_RE_CHIPSET = r'Chipset\.+\s+(.*)'` (expects dotted form).
  - `pm3_compat.py:1346/1352/1382` `_normalize_hid_prox` PREPENDS a synthetic legacy-shape `HID Prox - <raw>` line by reading the iceman `raw: <hex>` and also strips leading zeros. Middleware `REGEX_HID = r'raw:\s+([0-9A-Fa-f]+)'` targets iceman form; the prepended legacy line is now dead text.
  - `pm3_compat.py:1392/1395/1405` `_normalize_fdxb_animal_id` strips the colon after `Animal ID` on the assumption that the middleware regex needs whitespace; but iceman now emits 9-11 dot separator that `REGEX_ANIMAL = r'Animal ID\.+\s+([0-9\-]+)'` requires intact.
  - `pm3_compat.py:1070/1122` `_RE_DOTTED_SEPARATOR` in `_post_normalize` runs LAST — it will strip the Animal ID dots EVEN IF `_normalize_fdxb_animal_id` runs first (since post_normalize is Phase C after command-specific Phase B).
  - `pm3_compat.py:1495` `_normalize_lf_keyword_case` — catch-all case normalizer, may corrupt iceman-native keyword shapes.
- **Live symptom (iceman FW, with current adapter)**:
  - FDX-B: Animal ID capture fails — `_normalize_fdxb_animal_id` strips the colon (irrelevant now), then `_RE_DOTTED_SEPARATOR` strips the dots, leaving `Animal ID: <country>-<national>` which doesn't match `REGEX_ANIMAL`'s dotted-form anchor. `scan_lfsea()` returns FDX-B with empty `raw`/`data` → Scan→Simulate prepop fails.
  - Chipset detection: `_RE_CHIPSET` can't match on `Chipset detection: EM4x05` (adapter converted). Check 24 in `lfsearch.parser()` still fires (keyword `'Chipset...'` fails first — bubbles to Default). Result: T55xx/EM4x05 chipset classification returns `{'chipset': 'X', 'found': False}` instead of `{'chipset': 'EM4305', 'found': False}`.
  - HID: middleware `REGEX_HID` succeeds on `raw: ` line, but the synthetic `HID Prox -` prepended by adapter introduces a duplicate non-canonical line in the cache. `lfsearch.parser()` Check 3 produces correct UID but also logs extra noise; cosmetic only.
  - EM410x: middleware keyword `'Valid EM410x ID'` matches (adapter converts), but `REGEX_EM410X = r'EM 410x(?:\s+XL)?\s+ID\s+([0-9A-Fa-f]+)'` FAILS because adapter rewrote the data line to `EM TAG ID      : <hex>`. `seaObj['data']` ends up empty. 
- **Phase 4 action**:
  - REMOVE the entire `lf sea` / `lf search` normalizer chain in `_RESPONSE_NORMALIZERS` (`pm3_compat.py:1851-1860`): `_normalize_lf_no_data`, `_normalize_em410x_id`, `_normalize_hid_prox`, `_normalize_chipset_detection`, `_normalize_fdxb_animal_id`, `_normalize_gallagher_fields`, `_normalize_securakey_fc_hex`, `_normalize_awid_card_number`, `_normalize_lf_keyword_case`, `_normalize_indala_uid`.
  - KEEP `_normalize_lf_no_data` conditionally: iceman removes the "No data found!" emission; if middleware still gates on this keyword in Check 1, either (a) add an iceman-native empty-response indicator, or (b) keep the adapter's synthesis but run it only when `_current_version == PM3_VERSION_ICEMAN` AND the response is empty.
  - REMOVE `_RE_DOTTED_SEPARATOR.sub` from `_post_normalize()` (`pm3_compat.py:1122`) — generic stripper kills all iceman dotted forms including FDX-B Animal ID and Chipset.
  - REMOVE `_RE_ANIMAL_ID_COLON.sub` from `_post_normalize()` (`pm3_compat.py:1127`) — stripper for legacy→iceman that's irrelevant after flip.
  - Verify after removal: iceman `lf sea` responses hit middleware verbatim; no other consumer outside P3.1 depends on the legacy-shaped field conversions (cross-check P3.2 LF Read flow).

### Entry: P3.1 dormant / absent-emission keywords (informational)

Listed for Phase 4 audit; no live symptom but documented to prevent confusion:

- `hf14ainfo._KW_MULTIPLE_TAGS = 'Multiple tags detected'` (`hf14ainfo.py:135`) — DORMANT on both firmwares (zero grep hits in `/tmp/rrg-pm3/client/src/` and `/tmp/factory_pm3/client/src/`). Marked TODO(Phase 4) at `hf14ainfo.py:138-143` to either drop Case 1 precedence test or cite iceman-native multi-tag indicator.
- `hf14ainfo._KW_BCC0_INCORRECT = 'BCC0 incorrect'` (`hf14ainfo.py:144`) — absent on both firmwares (legacy iCopy-X firmware-patch vestige). Retained per matrix scope; no adapter needed.
- `hfsearch._KW_MULTIPLE_TAGS` — not currently defined in hfsearch; no-op.

---

## P3.7 iCLASS flow

### Entry: hf iclass rdbl block-read regex regression

- **Middleware now iceman-native**:
  - `hficlass._RE_BLOCK_READ = r'block\s+\d+\s*/0x[0-9A-Fa-f]+\s*:\s+([A-Fa-f0-9 ]+)'` — iceman `cmdhficlass.c:3501` emits ` block %3d/0x%02X : <hex>`, e.g. ` block   6/0x06 : 12 FF ...`. The regex targets the iceman-native shape (decimal block + slash + hex annotation + colon + hex run).
  - Same pattern applied inline at `iclasswrite.py:verify()` — replaces the prior `[Bb]lock\s*[0-9a-fA-F]+\s*:\s*hex` which matched NEITHER firmware (matrix divergence_matrix.md line 508 notes both legacy and iceman raw forms failed the old regex).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1675-1691` `_normalize_iclass_rdbl` rewrites iceman ` block   6/0x06 : 12 FF ...` → legacy `Block 6 : 12 FF ...` (strips `/0x..`, capitalises `B`, collapses spaces).
  - Wired for `hf iclass rdbl` at `pm3_compat.py:1846` (`_RESPONSE_NORMALIZERS['hf iclass rdbl'] = [_normalize_iclass_rdbl]`).
- **Live symptom (iceman FW, with current adapter)**:
  - `hficlass.checkKey()` returns False for EVERY valid key because `_RE_BLOCK_READ` targets the iceman raw shape with `/0x..`, but adapter rewrote it to `Block 6 : ...` before middleware sees it.
  - Cascading failures: `chkKeys_1`/`chkKeys_2` return None → `parser()` returns `type=ICLASS_ELITE` (default) but missing `key` field → `iclassread.readLegacy`/`readElite` return `-2` → Scan flow shows "Read Failed!" on EVERY iCLASS card.
  - Observable in test: `tests/phase3_trace_parity/test_iclass_flow.py` — 10/10 live iceman_output.json samples for `hf iclass rdbl` carry the adapter-normalized `Block 1 : ...` shape; iceman-native regex produces no-match as expected (parity test asserts non-match for normalized samples, match for synthetic iceman raw samples).
- **Phase 4 action**:
  - REMOVE `_normalize_iclass_rdbl` from `_RESPONSE_NORMALIZERS['hf iclass rdbl']` (`pm3_compat.py:1846`) OR gate it on `_current_version == PM3_VERSION_ORIGINAL`.
  - `_normalize_iclass_rdbl` function body itself (`pm3_compat.py:1680-1691`) can be retained as a dormant forward-direction rewriter if Phase 4 needs legacy-FW support; the systemic divergence #4 flag in the matrix says legacy raw shape has hex block numbers that `\d+` can't match, so the legacy→iceman direction would still need SOME normaliser.
  - Re-capture iceman_output.json after adapter disable; the 10 currently-normalized samples should flip to raw ` block   N/0x.. : ...` form, at which point the parity-test negative assertions become positive assertions.

### Entry: hf iclass wrbl success-keyword regression

- **Middleware now iceman-native**:
  - `iclasswrite._KW_WRBL_SUCCESS = r'\( ok \)'` — iceman `cmdhficlass.c:3134` emits `Wrote block %d / 0x%02X ( " _GREEN_("ok") " )`, e.g. `Wrote block 6 / 0x06 ( ok )`. Keyword targets the literal ` ( ok )` substring.
  - Previously `r'successful|\( ok \)'` — format-agnostic alternation carrying forward legacy `Wrote block 07 successful`. Dropped per Option B (iceman-native only).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1654-1666` `_normalize_iclass_wrbl` rewrites iceman ` ( ok )` → legacy ` successful` (string replace on line `Wrote block N / 0xNN ( ok )`). Wired at `pm3_compat.py:1847`.
- **Live symptom (iceman FW, with current adapter)**:
  - `iclasswrite.writeDataBlock()` returns -10 (error) for EVERY successful write because adapter has rewritten ` ( ok )` to ` successful` before middleware sees it; iceman-native keyword match fails.
  - Observable in test: live iceman_output.json samples for `hf iclass wrbl` all show the adapter-normalized `Wrote block 6 / 0x06 successful` shape — iceman-native keyword correctly misses these; parity test asserts non-match.
  - User-visible: Write flow reports FAIL on every iCLASS block write even when PM3 actually wrote successfully; `writeDataBlocks()` aborts on first block and returns -1; UI shows "Write Failed!" and rolls back the operation.
- **Phase 4 action**:
  - REMOVE `_normalize_iclass_wrbl` from `_RESPONSE_NORMALIZERS['hf iclass wrbl']` (`pm3_compat.py:1847`).
  - Legacy direction: if a legacy PM3 is ever exercised, its raw `Wrote block 07 successful` emission won't match `\( ok \)` — would need an inverse normalizer rewriting legacy `successful` → iceman `( ok )`. Dead path for iceman target (iceman is the reference), document as systemic-#8 entry.

### Entry: hf iclass calcnewkey 4-dot Xor div key regression

- **Middleware now iceman-native**:
  - `iclasswrite._RE_XOR_DIV_KEY = r'Xor div key\.+\s+([0-9A-Fa-f ]+)'` — iceman `cmdhficlass.c:5419` emits `Xor div key.... %s` with a **4-dot** separator (literal four dots, not five, not colon). Verified by reading `/tmp/rrg-pm3/client/src/cmdhficlass.c:5419`: `PrintAndLogEx(SUCCESS, "Xor div key.... " _YELLOW_("%s") "\n", ...)`.
  - Previously `r'Xor div key\s*:\s*([0-9A-Fa-f ]+)'` — colon form carried forward from legacy + prior matrix note. The prior matrix annotation (line 1361) claimed colon separator; this refactor reads iceman source directly and corrects the annotation: iceman emits dotted form, legacy emits colon form.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1070-1071` `_RE_DOTTED_SEPARATOR = re.compile(r'^(\s*\S.*?\S)\.{3,}\s+', re.MULTILINE)` in `_post_normalize()` (`pm3_compat.py:1122`) rewrites ALL dotted-separator lines including `Xor div key....` → `Xor div key: `. Generic stripper, same one flagged in P3.1 scan entry.
  - No command-specific normalizer; the generic post-normalize dot-stripper is the culprit.
- **Live symptom (iceman FW, with current adapter)**:
  - `iclasswrite.calcNewKey()` returns -10 (error) because adapter rewrote `Xor div key.... <hex>` → `Xor div key: <hex>` before middleware match; iceman-native 4-dot regex fails.
  - Cascading failure: `writePassword()` returns -10 → password rotation aborts → UI shows "Write Failed!" on the dedicated password change flow.
  - 0 live iceman_output.json samples exist (matrix line 1356 notes empty trace set); parity-test validation relies on synthetic iceman-native 4-dot samples.
- **Phase 4 action**:
  - REMOVE `_RE_DOTTED_SEPARATOR.sub` from `_post_normalize()` (`pm3_compat.py:1122`). Same action item logged in the P3.1 scan entries (hf 14a info) — this is the SAME generic stripper.
  - Once removed, iceman 4-dot separator reaches middleware verbatim and `_RE_XOR_DIV_KEY` matches.
  - Update matrix annotation at line 1361 to reflect the dotted form (done by this refactor's docs-commit).

### Entry: hf iclass info CSN extraction (matrix v2 correction-confirm)

- **Middleware now iceman-native** (status: ALREADY CORRECT, re-cited):
  - `hficlass._RE_CSN = r'CSN:*\s([A-Fa-f0-9 ]+)'` — iceman `cmdhficlass.c:8032` emits `    CSN: %s uid` (4-space indent, colon-space, hex run, ` uid` suffix). Regex captures hex run until non-hex char (stops naturally at ` uid`).
  - Matrix v2 correction at divergence_matrix.md line 422 confirmed iceman DOES emit the full tag-info block including CSN (v1 falsely claimed ping-only). No middleware change required.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1070-1071` `_RE_DOTTED_SEPARATOR` in `_post_normalize()` also fires on the iceman Fingerprint section `    CSN.......... HID range` (L8088/8098) and rewrites the dotted CSN line to `CSN: HID range`. But the middleware regex hex class `[A-Fa-f0-9 ]+` rejects `H` (for `HID`), so the regex naturally misses the annotation line and matches only the real CSN data line — no live symptom.
- **Live symptom (iceman FW, with current adapter)**: none — `_RE_CSN` works correctly on both the canonical `CSN: <hex> uid` line AND the Fingerprint-section dotted annotation (annotation line's non-hex content is rejected by the hex class).
- **Phase 4 action**: NO-OP for this field. Parity test asserts `_RE_CSN` successfully captures the hex CSN on the canonical line AND correctly misses the Fingerprint annotation line.

### Entry: hf iclass dump success-keyword (identical both firmwares)

- **Middleware now iceman-native** (status: ALREADY CORRECT, re-cited):
  - `iclassread._KW_DUMP_SUCCESS = 'saving dump file'` — iceman `cmdhficlass.c:2978` emits `saving dump file - %u blocks read`; legacy `cmdhficlass.c:1031`/`:1990` emit the identical substring. Matrix v2 correction at divergence_matrix.md line 484-487 confirmed the prior v1 claim of LEGACY-ONLY was false.
- **Adapter still running iceman→legacy**: none affecting this keyword.
- **Live symptom (iceman FW)**: none.
- **Phase 4 action**: NO-OP.

### Entry: P3.7 dormant / API-preservation (informational)

Listed for Phase 4 audit; no live symptom but documented to prevent confusion:

- `hficlass._RE_BLK7 = r'Blk7#:([0-9a-fA-F]+)'` (`hficlass.py:54`) — DORMANT on both firmwares; legacy-iCopy-X-specific synthesised line. No iceman source emits this shape. Retained for API compatibility with consumers that still read the `blk7` dict key. Phase 4 can drop if the consumer audit clears.
- `hficlass._CMD_CHK = 'hf iclass chk -f '` (`hficlass.py:50`) — DEAD; never formatted into a command (the fallback uses `--vb6kdf` literal instead). Retained for API symmetry with legacy `.so`; Phase 4 audit can drop.
- `hficlass.readTagBlock` — internal fallback chain (returns empty on failure; consumer `iclasswrite.verify` handles empty ret). Iceman-native path validated via synthetic samples.

---

## P3.2 Read HF flow

### Entry: hf mf darkside / hf mf nested key-extraction regression

- **Middleware now iceman-native**:
  - `hfmfkeys.darkside()` inline regex `r'Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]'` (hfmfkeys.py:282) — iceman `cmdhfmf.c:1275` emits `"Found valid key [ %012X ]"` (capital Found, bracketed, PRIX64 uppercase).
  - `hfmfkeys.nestedOneKey()` inline regex `r'found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]'` (hfmfkeys.py:320) — iceman `mifare/mifarehost.c:686` emits `"Target block %4u key type %c -- found valid key [ %012X ]"` (lowercase "found", bracketed).
  - `re.IGNORECASE` retained so either helper tolerates the counterpart's case. Matrix section `hf mf darkside` (divergence_matrix.md L687-707) + `hf mf nested` (L740-759).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1199-1211` `_normalize_darkside_key()` + `_RE_DARKSIDE_NEW = r'Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]'` rewrites iceman `"Found valid key [ AABBCCDDEEFF ]"` → legacy `"Found valid key: aabbccddeeff"` (lowercase, colon). Wired for `hf mf darkside` AND `hf mf nested` at `pm3_compat.py:1823-1824` (both normalizer lists include `_normalize_darkside_key`).
- **Live symptom (iceman FW)**:
  - `hfmfkeys.darkside()` returns -1 even when iceman emits a successful `Found valid key [ <hex> ]` line. The adapter rewrites the bracketed form to `Found valid key: <hex>` BEFORE the middleware regex runs; the middleware regex requires `[ ... ]` brackets, so the match fails.
  - `hfmfkeys.nestedOneKey()` same root cause — the adapter targets the same line shape; any successful nested attack that emits via mifarehost.c:686 gets rewritten to the legacy colon shape and the iceman-native regex misses it.
  - Observable: Read flow of a key-limited MF1K card succeeds on fchk (key-table still matches via 4-column `|` shape) but falls back to "total failure" when fchk is incomplete because darkside/nested can't extract keys. Read screen shows `M1-*_X_0.bin` with many empty sectors.
  - `iceman_output.json` samples DO NOT surface this failure: 6 darkside samples are all "Card is not vulnerable" shape (no Found-valid-key line), and the 4 nested success samples still carry the bracketed form verbatim (adapter didn't fire when capture ran, or capture pre-dates adapter activation).
- **Phase 4 action**:
  - REMOVE `_normalize_darkside_key` from `_RESPONSE_NORMALIZERS['hf mf darkside']` (`pm3_compat.py:1823`).
  - REMOVE `_normalize_darkside_key` from `_RESPONSE_NORMALIZERS['hf mf nested']` (`pm3_compat.py:1824`).
  - The function can remain defined for legacy→iceman direction if/when a legacy FW emits the colon form and middleware needs bracketed — unlikely needed. Safer to delete entirely after confirming no other consumer.

### Entry: hf mf rdbl / hf mf rdsc / hf mf cgetblk block-data regression (dormant)

- **Middleware now iceman-native**:
  - `hfmfread._RE_BLOCK_DATA_LINE = r'data:\s*((?:[A-Fa-f0-9]{2}\s+){15}[A-Fa-f0-9]{2})'` (hfmfread.py:293-294) — iceman `mf_print_block_one` via sprint_hex (cmdhfmf.c:572/601/603) on the device's installed build still emits `"data: XX XX XX XX ..."` sprint_hex form. Verified by iceman_output.json `hf mf rdsc` (all 10 success samples), `hf mf cgetblk` (samples 8-9).
  - `hfmfread._parse_blocks_from_text()` simplified to single-regex pass; legacy fallbacks (`_RE_BLOCK_DATA` continuous 32-hex, `_RE_BLOCK_SPACED` pipe-grid) removed.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1241-1268` `_normalize_rdbl_response()` + `_RE_RDBL_TABLE_ROW = r'^\s*(\d+)\s*\|\s*((?:[A-Fa-f0-9]{2}\s+){15}[A-Fa-f0-9]{2})\s*\|.*$'` rewrites iceman-HEAD grid form `  0 | AA BB ... | ascii` → legacy-compatible `data: AA BB ...`. Wired for `hf mf rdbl`, `hf mf rdsc`, `hf mf cgetblk` at `pm3_compat.py:1827-1829`.
  - `pm3_compat.py:1216-1234` `_normalize_wrbl_response()` rewrites `( ok )` / `( fail )` → `isOk:01` / `isOk:00`. Wired for `hf mf rdsc` at `pm3_compat.py:1828` (second entry in the list). This normalizer is WRITE-path; on rdsc it's dead weight — no rdsc response line contains those tokens.
- **Live symptom**:
  - DORMANT on the device's current iceman build. The adapter's `_RE_RDBL_TABLE_ROW` regex requires the HEAD grid `N | hex | ...` shape which the device's iceman does NOT emit; the `.sub()` never matches, leaving the existing `data: XX XX ...` lines intact. The iceman-native middleware regex matches correctly.
  - Future-bump risk: if the device is ever flashed to /tmp/rrg-pm3 HEAD iceman, rdbl/rdsc/cgetblk will emit the grid form. `_normalize_rdbl_response` would then fire and rewrite to `data:` for the middleware. Since middleware-native regex is already `data:`, this is SAFE on firmware bump — no action required.
- **Phase 4 action**:
  - No change required immediately; both adapter and middleware point to the same `data:` form.
  - OPTIONAL cleanup: remove `_normalize_wrbl_response` from `_RESPONSE_NORMALIZERS['hf mf rdsc']` (`pm3_compat.py:1828`) — rdsc never emits `Write ( ok )` / `( fail )`, so the normalizer is dead weight for that command.

### Entry: hf mf fchk key-table regression (dormant)

- **Middleware now iceman-native**:
  - `hfmfkeys._RE_KEY_TABLE = r'\|\s*(\d+)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d+)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d+)\s*\|'` (hfmfkeys.py:235) — iceman 4-column `|`-bordered shape as emitted by the device's installed iceman build. Matrix section `hf mf fchk` v2 correction (divergence_matrix.md L711-736) confirmed via iceman_output.json dominant shape. TODO(Phase 4 / firmware bump) comment at hfmfkeys.py:227-233 explicitly flags the regex for re-audit if device iceman is upgraded to HEAD (which emits 5-column `+`-separated format, cmdhfmf.c:4966-5060 printKeyTable).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1160-1192` `_normalize_fchk_table()` + `_RE_FCHK_NEW_ROW` rewrites the HEAD 5-column `+`-separated row → 4-column `|`-bordered row. Wired for `hf mf fchk`, `hf mf chk`, `hf mf nested`, `hf mf staticnested` at `pm3_compat.py:1821-1825`.
- **Live symptom**:
  - DORMANT. The device's installed iceman emits the 4-column `|`-bordered shape directly; `_RE_FCHK_NEW_ROW` (which matches only the HEAD 5-column shape) never fires. iceman_output.json `hf mf fchk` samples 0 and 3 confirm device iceman emits rows like `| 000 | 484558414354   | 1 | a22ae129c013   | 1 |` — middleware-native regex matches verbatim, adapter is no-op.
  - Future-bump risk: if device is upgraded, adapter will fire and rewrite to 4-column `|` form, middleware regex will match correctly. SAFE on firmware bump.
- **Phase 4 action**:
  - No change required. The adapter is a forward-compatibility helper — leave wired.

### Entry: hf mfu dump / hf mfu info passthrough

- **Middleware now iceman-native**:
  - `hfmfuread.read()` keywords `"Can't select card"` (cmdhf14a.c:1817) and `"Partial dump created"` (cmdhfmfu.c:3769). No regex parsing of response body; success path uses os.path.exists on .bin file.
  - `hfmfuinfo` subtype keywords preserved; iceman-native NTAG 213/215/216 verbatim substrings from cmdhfmfu.c:1034-1044.
- **Adapter still running iceman→legacy**:
  - `_RESPONSE_NORMALIZERS['hf mfu dump'] = [_normalize_save_messages]` (pm3_compat.py:1840) — lowercases `"Saved N bytes"` → `"saved N bytes"`. Dormant for hfmfuread which never parses the save line (verifies via filesystem).
  - `_RESPONSE_NORMALIZERS['hf mfu info'] = []` (pm3_compat.py:1839) — no normalizers wired. scan.py matches iceman-native TYPE substrings verbatim.
- **Live symptom**: NONE. Both commands pass through iceman-native text to middleware without adapter interference.
- **Phase 4 action**: No change required.

### Entry: P3.2 dormant keywords (informational)

Listed for Phase 4 audit; no live symptom but documented to prevent confusion:

- `hfmfuread.py:127` `"Can't select card"` — emission IDENTICAL on both firmwares AFTER executor strip (matrix L900). Iceman HEAD's `ul_select()` (cmdhfmfu.c:386-409) logs at DEBUG only, so on HEAD this keyword would be dormant for the `hf mfu dump` path. Device's older iceman build may still route some failures through the 14a reader helper (cmdhf14a.c:1817). Kept as defensive check — no action needed unless device trace confirms zero emission on current build.
- `hfmfkeys.onNestedCall(lines)` — pass-only stub (hfmfkeys.py:294). Legacy `.so` registered a progress callback for nested attacks; iceman emits `INPLACE` progress lines that the executor's PM3 wrapper discards. No wiring needed.

---

## P3.3 Write HF flow

### Entry: hf mf wrbl success-keyword flip (Write(ok) vs isOk:01)

- **Middleware now iceman-native**:
  - `hfmfwrite._KW_WRBL_SUCCESS = r'Write \( ok \)'` (hfmfwrite.py) — iceman `cmdhfmf.c:1389`, `:9677`, `:9760` emit `PrintAndLogEx(SUCCESS, "Write ( " _GREEN_("ok") " )")`. Three identical emission sites — all use the `Write ( ok )` literal.
  - Previously `r'isOk:01|Write \( ok \)'` — alternation carried the legacy sentinel forward for post-adapter keyword match. Dropped per Option B (iceman-native only).
  - Matrix v2 OQ1 RESOLVED (divergence_matrix.md L821): iceman has ZERO `isOk:` emissions in the write path (grep of `/tmp/rrg-pm3/client/src/` yields zero matches for `isOk:`).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1216-1234` `_normalize_wrbl_response()` rewrites iceman `"Write ( ok )"` → legacy `"isOk:01"` and `"Write ( fail )"` → legacy `"isOk:00"`. Also catches bare `( ok )` / `( fail )` regex forms for `hf mf restore` table rows.
  - Wired for `hf mf wrbl` at `pm3_compat.py:1826` (`_RESPONSE_NORMALIZERS['hf mf wrbl'] = [_normalize_wrbl_response]`). Also wired for `hf mf rdsc` at `:1828` (dead weight there — no rdsc line contains those tokens) and `hf mf restore` at `:1835`.
- **Live symptom (iceman FW, with current adapter)**:
  - `hfmfwrite.write_block()` returns -1 for EVERY successful per-block write: adapter rewrites iceman `Write ( ok )` → `isOk:01` before middleware sees it; iceman-native keyword `Write \( ok \)` no longer finds either literal.
  - Cascading failures: `write_with_standard()` accumulates `write_fail=True` → returns -1 → Write flow UI shows "Write Failed!" on every MF1K/MF2K/MF4K write even when PM3 actually wrote successfully.
  - Observable in test: `tests/phase3_trace_parity/test_write_hf_flow.py` — all 10 live `hf mf wrbl` samples carry adapter-normalised `isOk:00` tokens (the trace was captured post-adapter). Test asserts iceman-native keyword correctly MISSES these (expected during transition). 2 synthetic iceman-native samples (`Write ( ok )` / `Write ( fail )`) exercise the post-Phase-4 target shape and PASS.
- **Phase 4 action**:
  - REMOVE `_normalize_wrbl_response` from `_RESPONSE_NORMALIZERS['hf mf wrbl']` (`pm3_compat.py:1826`).
  - REMOVE same normaliser from `_RESPONSE_NORMALIZERS['hf mf rdsc']` (`pm3_compat.py:1828`, already flagged in P3.2 as dead weight).
  - KEEP `_normalize_wrbl_response` reachable via `_RESPONSE_NORMALIZERS['hf mf restore']` (`pm3_compat.py:1835`) — that path rewrites legacy→iceman for the rarely-used `hf mf restore` table view. Revisit during matrix rebuild.
  - Re-capture iceman_output.json after adapter disable; the 10 currently-normalised `isOk:00` samples should flip to `Write ( fail )` / `Write ( ok )` shape.

### Entry: hf 14a raw gen1afreeze -k flag (dormant)

- **Middleware now iceman-native**:
  - `hfmfwrite.gen1afreeze()` (hfmfwrite.py:188-201) issues 5 literal `hf 14a raw ... -k ...` commands; iceman `cmdhf14a.c:1547/1670` defines `-k` as "keep signal field ON after receive". Matrix L188 cites iceman CLI form explicitly.
  - No regex / keyword parse — response is discarded (fire-and-forget per matrix L189).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:235-243` `_translate_14a_raw` (legacy→iceman forward): rewrites `-p` → `-k`. Activated only when middleware sends legacy-shape `-p` — middleware now sends iceman `-k` directly, so this translator is dormant.
  - `pm3_compat.py:547-550` `_reverse_14a_raw` (iceman→legacy): rewrites `-k` → `-p`. Applies ONLY when `_current_version == PM3_VERSION_ORIGINAL` (legacy firmware). On iceman firmware, dormant.
- **Live symptom (iceman FW)**: NONE. Middleware emits iceman syntax; `_translate_14a_raw` never fires (pattern matches only `-p` form); `_reverse_14a_raw` never fires (gated on legacy firmware). Dormant both directions.
- **Phase 4 action**:
  - No change required. `_reverse_14a_raw` remains useful if the PM3 binary is ever flashed back to legacy. Document as LEGACY-FW-only adapter in the systemic-divergence section.

### Entry: hf mfu restore Done!/Finish restore (matrix v2 C4 correction)

- **Middleware now iceman-native**:
  - `hfmfuwrite._KW_RESTORE_SUCCESS = r'Done!'` (hfmfuwrite.py) — iceman `cmdhfmfu.c:4218` emits `PrintAndLogEx(INFO, "Done!")` inside `CmdHF14AMfURestore` (function body spans L3936-4220). The exclamation mark is part of the literal.
  - Previously `"Done"` (no exclamation) — substring match worked on iceman but would ALSO false-match any legacy line containing the word "Done" (e.g. progress messages). Tightened to iceman literal.
  - `hfmfuwrite._KW_SELECT_FAIL = "Can't select card"` — identical on both firmwares per matrix L924.
  - `hfmfuwrite._KW_WRITE_FAIL = "failed to write block"` — iceman write-loop per-block failure string (grep confirmed in cmdhfmfu.c).
- **Adapter still running iceman→legacy**:
  - NONE wired in `_RESPONSE_NORMALIZERS` for `hf mfu restore` at the current `pm3_compat.py`. Matrix v2 C4 + matrix L928 explicitly flag the MISSING adapter: legacy `cmdhfmfu.c:2343` emits `PrintAndLogEx(INFO, "Finish restore")` only — NO `Done` token anywhere in legacy path.
  - No `_normalize_hfmfu_restore` function exists; matrix L928 recommends adding one that injects `"Done!"` when `"Finish restore"` is present, OR broadening the middleware regex to `r'(Done!?\|Finish restore)'`.
- **Live symptom (legacy FW, hypothetical)**:
  - `hfmfuwrite.write()` returns -1 for EVERY successful legacy restore: legacy emits `Finish restore`; iceman-native keyword `Done!` doesn't match; middleware treats as silent failure; UI shows "Write Failed!" on every MFU/NTAG legacy-firmware restore.
  - On iceman FW (current target): NONE — iceman emits `Done!` natively and middleware matches.
- **Phase 4 action**:
  - Add `_normalize_hfmfu_restore(text)` to `pm3_compat.py`: `text.replace('Finish restore', 'Done!')` when legacy-direction active.
  - Wire at `_RESPONSE_NORMALIZERS['hf mfu restore'] = [_normalize_hfmfu_restore]`.
  - Alternative: broaden middleware to `r'(Done!?\|Finish restore)'` — but that's middleware-touching legacy, which violates Option B. Adapter route is the correct Phase 4 action.

### Entry: P3.3 dormant / identical-both-firmwares (informational)

Listed for Phase 4 audit; no live symptom but documented to prevent confusion:

- `hf mf cload` success keyword `'Card loaded'` (hfmfwrite.py:223) — iceman `cmdhfmf.c:6134` `"Card loaded %d blocks from %s"` / legacy `"Card loaded %d blocks from <file>"`: COSMETIC divergence only (backtick-quoting on path). Substring `'Card loaded'` matches both (matrix L643 SAFE). No action.
- `hf mf cload` failure keyword `"Can't set magic"` (hfmfwrite.py:221,241) — iceman `cmdhfmf.c:6061/6108/9028` all emit `"Can't set magic card block: %d"`. Substring matches iceman directly.
- `hf mf cgetblk` probe keywords (hfmfwrite.py:410-416) — `wupC1 error` emitted by iceman armsrc `mifarecmd.c:103/116/2921`; `Can't read block. error=%d` emitted by iceman `cmdhfmf.c:6171/6230/8828`. Both iceman-native substrings. `isOk:00` alternative KEPT as defensive fallback — matrix v2 L817 confirms iceman has zero `isOk:` emissions so this branch is dormant under iceman, but remains harmless and protects against any adapter-synth path. Phase 4 can drop if the alternative clause is proven dead across all normalisers.
- `hf mf csetuid` (hfmfwrite.py:241) — 0 trace samples on either firmware per matrix L656. Command-translate via `_translate_mf_csetuid` (pm3_compat.py:196) + reverse `_reverse_mf_csetuid` (:553). Middleware emits iceman syntax; translators dormant when sending iceman-native form. Matrix L664 notes `_RE_UID` at hfmfwrite.py:513 targets legacy UID diff-line shape (`"Old UID : %s"`) — iceman emits `"Old UID... %s"` (dotted). No UID diff parsing currently in verify (UID extracted from `hf 14a info` instead). DORMANT; Phase 4 re-audit if UID diff line ever becomes load-bearing.
- `hf 14a info` UID regex `r'UID:\s*([\dA-Fa-f ]+)'` (hfmfwrite.py:521,523) — iceman `hf 14a info` emits `" UID: 7A F2 EC B2"` (space-colon-space-hex). Regex matches iceman directly. IDENTICAL TO P3.1 SCAN refactor's _RE_UID alternation (hf14ainfo.py).
- `hfmfuwrite.verify()` path — uses `scan.scan_14a()` + `scan.isTagFound()`. Both iceman-native via the P3.1 scan refactor. No direct PM3-command emission in this code path.

### Entry: erase.py cross-module wrbl split-brain — **RESOLVED by P3.4**

- **Finding**: `src/middleware/erase.py` lines 79, 288, 296, 318, 326 still use the legacy alternation pattern `'isOk:01' in wr_cache or 'Write ( ok )' in wr_cache` (and the Gen1a block-0 regex at :79 still includes `isOk:01` in the alternation group). `hfmfwrite.py` is now iceman-strict (`_KW_WRBL_SUCCESS = r'Write \( ok \)'`) after P3.3 refactor. The two modules parse the SAME `hf mf wrbl` PM3 response with DIFFERENT expectations — a split-brain state: erase still tolerates adapter-synth `isOk:01`, write does not.
- **Raised during**: P3.3 Challenger + Auditor review (cross-module consistency check).
- **Scope boundary**: erase.py is P3.4's scope (scheduled next flow refactor). No edit made during P3.3 fixer — logged here for traceability only.
- **Phase 4 action**: NONE beyond P3.4 completing. When P3.4 refactors erase.py to iceman-native, all five alternation sites (79/288/296/318/326) collapse to the iceman literal `Write ( ok )` and this entry resolves by construction.
- **Status**: **RESOLVED by P3.4 refactor** (commit `refactor(erase): erase.py → iceman-native patterns`). Erase.py now declares `_KW_WRBL_SUCCESS = r'Write \( ok \)'` at module scope (identical constant to `hfmfwrite._KW_WRBL_SUCCESS`); all five call sites use `re.search(_KW_WRBL_SUCCESS, wr_cache)`; `_RE_CGETBLK_BLOCK_DATA` dropped `isOk:01` from alternation. See "P3.4 Erase flow → erase.py hf mf wrbl split-brain resolution" below for the full Phase-4 reconciliation plan (one adapter-removal closes both hfmfwrite.py and erase.py).

---

## P3.8 ISO15693/FeliCa/Legic/Sniff flow

### Entry: hf 15 restore success-sentinel flip (Done! vs Write OK+done)

- **Middleware now iceman-native**:
  - `hf15write._KW_RESTORE_SUCCESS = r"Done!"` (hf15write.py:69) — iceman `cmdhf15.c:2818` emits `PrintAndLogEx(INFO, "Done!")` as the sole success sentinel after the block-restore loop.
  - `hf15write._KW_RESTORE_TOO_MANY = r"Too many retries"` (hf15write.py:70) — iceman `cmdhf15.c:2803` emits `PrintAndLogEx(FAILED, "Too many retries ( fail )")`. Note: iceman does NOT emit a `"restore failed"` string anywhere in `cmdhf15.c` (grep-verified on `/tmp/rrg-pm3/client/src/cmdhf15.c`). Legacy `cmdhf15.c:1737` emitted a compound `"restore failed. Too many retries."`; iceman split the two messages apart.
  - Previous check chain (`hasKeyword("Write OK") AND hasKeyword("done")`) DROPPED: iceman never emits either literal anywhere in the restore path. Divergence matrix L333-334 confirms.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1638-1649` `_normalize_hf15_restore()` detects `"Done"` in iceman body and appends a literal `"\nWrite OK\ndone"` suffix, synthesising the legacy shape so the PRE-refactor middleware could keyword-match.
  - Wired for `hf 15 restore` at `pm3_compat.py:1843` (`_RESPONSE_NORMALIZERS['hf 15 restore'] = [_normalize_hf15_restore]`).
- **Live symptom (iceman FW, with current adapter)**:
  - Benign during transition: the post-refactor middleware `hf15write._KW_RESTORE_SUCCESS = "Done!"` correctly fires on the iceman-raw `"Done!"` line, regardless of whether the adapter has appended the legacy suffix (the adapter only APPENDS; it does not modify the raw text). `hf15write.write()` therefore still returns 1 on iceman writes.
  - No live-sample regression observed. Live `tests/phase3_trace_parity/test_iso_felica_legic_sniff_flow.py::hf 15 restore` → 1 sample, 1 pass.
- **Phase 4 action**:
  - REMOVE `_normalize_hf15_restore` from `_RESPONSE_NORMALIZERS['hf 15 restore']` (`pm3_compat.py:1843`).
  - The injected `Write OK\ndone` suffix becomes dead text once the middleware no longer consumes those keywords. No side effects elsewhere (grep confirms no other middleware consumer reads `Write OK` for `hf 15 restore`).

### Entry: hf 15 csetuid success-regex iceman-raw (Setting new UID ( ok ))

- **Middleware now iceman-native**:
  - `hf15write._RE_CSETUID_OK = r"Setting new UID\s*\(\s*ok\s*\)"` (hf15write.py:72) — iceman `cmdhf15.c:2900` emits `PrintAndLogEx(SUCCESS, "Setting new UID ( " _GREEN_("ok") " )")`. Capital `S` with spaces inside the parens.
  - `hf15write._KW_CSETUID_NO_TAG = r"no tag found"` (hf15write.py:71) — iceman `cmdhf15.c:2868/2891` emits `PrintAndLogEx(FAILED, "no tag found")` on UID-read failure (pre- and post-write sanity checks).
  - Previously `r"[Ss]etting new UID \(?\s*ok\s*\)?"` — dual-shape alternation retained lowercase `s` for legacy, optional `(` for adapter-stripped paren. Dropped per Option B: middleware targets iceman RAW only.
  - Previously `r"can't read card UID|no tag found"` — legacy `"can't read card UID"` branch REMOVED (iceman emits `"no tag found"` only; legacy `"can't read card UID"` source is in an entirely different hf15 path, cmdhf15.c legacy fork only).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1720-1728` `_normalize_hf15_csetuid()` rewrites iceman `"Setting new UID ( ok )"` → legacy `"setting new UID (ok)"` (lowercase, no spaces in parens). Also rewrites `"Setting new UID ( fail )"` → `"setting new UID (failed)"`.
  - Wired for `hf 15 csetuid` at `pm3_compat.py:1844`.
- **Live symptom (iceman FW, with current adapter)**:
  - `hf15write.write()` returns -1 for every successful csetuid: adapter rewrites iceman `Setting new UID ( ok )` → `setting new UID (ok)` before middleware sees it; iceman-native regex `Setting new UID\s*\(\s*ok\s*\)` (capital S) no longer finds a match.
  - Cascading failure: write flow UI shows "Write Failed!" on every ISO15693 UID-set even when PM3 actually set the UID successfully.
  - Observable in test: `tests/phase3_trace_parity/test_iso_felica_legic_sniff_flow.py` — live sample `hf 15 csetuid[1]` carries adapter-normalized `setting new UID (ok)`; iceman-native regex correctly MISSES (test asserts this as expected during transition).
- **Phase 4 action**:
  - REMOVE `_normalize_hf15_csetuid` from `_RESPONSE_NORMALIZERS['hf 15 csetuid']` (`pm3_compat.py:1844`). Matrix L362 already flags it as "arguably redundant" once the middleware regex is refactored to iceman-native form.
  - Re-capture iceman_output.json after adapter disable; the post-adapter normalized sample should flip to iceman `Setting new UID ( ok )` shape.

### Entry: hf felica reader sentinel flip (IDm: vs FeliCa tag info) — SEVERITY: HIGH

- **Middleware now iceman-native**:
  - `hffelica._KW_FOUND = r'IDm:\s'` (hffelica.py) — iceman `cmdhffelica.c:1183` emits `PrintAndLogEx(SUCCESS, "IDm: " _GREEN_("%s"), sprint_hex_inrow(card.IDm, sizeof(card.IDm)))`. The iceman `read_felica_uid()` helper (L1144) is the ONLY success emission site; legacy `readFelicaUid()` helper at L1803 — which emitted `"FeliCa tag info"` (L1835) — was replaced by the uid-only variant.
  - `hffelica._KW_TIMEOUT = 'card timeout'` (hffelica.py) — iceman `cmdhffelica.c:1431` emits `PrintAndLogEx(WARNING, "card timeout")`. Matches both firmwares (COSMETIC divergence on trailing `(-4)` status code, iceman-only).
  - `hffelica._RE_IDM = r'.*IDm(.*)'` unchanged — iceman emission `"IDm: XX XX ..."` is a superset of legacy `"IDm %s"`; capture after `IDm` yields the hex bytes (plus colon for iceman) which is then stripped of whitespace.
  - Previously `_KW_FOUND = 'FeliCa tag info'` — MATCHES LEGACY ONLY. Iceman has ZERO emissions of `"FeliCa tag info"` (grep-verified on `/tmp/rrg-pm3/client/src/cmdhffelica.c`). Divergence matrix L382 previously flagged the STRUCTURAL gap.
- **Adapter STILL ACTIVELY BREAKS iceman iff wired**:
  - `_normalize_felica_reader` (pm3_compat.py:1734-1749) rewrites iceman `"IDm: XX XX ..."` → legacy `"IDm  XX XX ..."` (two-space separator, NO colon). Exact sequence: `re.search(r'IDm:\s*([0-9A-Fa-f]+)', text)` captures the hex, emits `'IDm  %s' % spaced` with NO colon in the replacement (pm3_compat.py:1749).
  - Wired at pm3_compat.py:1849 (`_RESPONSE_NORMALIZERS['hf felica reader'] = [_normalize_felica_reader]`).
  - **Post-adapter text NO LONGER MATCHES the new middleware keyword**: `hffelica._KW_FOUND = r'IDm:\s'` requires the colon; adapter strips it. Every successful iceman FeliCa detection silently fails the `executor.hasKeyword(_KW_FOUND)` check in `hffelica.parser()`.
- **Live symptom (iceman FW, current adapter) — PRODUCTION IMPACT**:
  - iceman_output.json has 10 `hf felica reader` samples — all 10 are `"card timeout"` bodies (no successful FeliCa detections captured). Live samples therefore exercise the NEGATIVE path only; `parser()` returns `{'found': False}` for every sample.
  - Positive-path synthetic trace-parity samples BYPASS the adapter (they inject iceman-native `IDm: XX` directly into the executor cache) so the test suite is GREEN — but this masks the live breakage.
  - Against a real iceman PM3 talking through the current adapter: a valid FeliCa card emits `"IDm: 01 FE XX XX XX XX XX XX"`; adapter rewrites to `"IDm  01 FE XX XX XX XX XX XX"` (no colon); middleware `_KW_FOUND = r'IDm:\s'` fails to match; `parser()` returns `{'found': False}`; `scan_felica()` reports `createExecTimeout(5)`.
  - **FeliCa cards show as "no tag" on live iceman firmware until Phase 4 disables the adapter.** This is a hard live regression (Option B transition-period breakage, as accepted in the refactor charter — but logging HIGH severity so Phase 4 prioritises FeliCa normalizer removal).
- **Phase 4 action**:
  - REMOVE `_normalize_felica_reader` from `_RESPONSE_NORMALIZERS['hf felica reader']` (pm3_compat.py:1849).
  - Re-capture iceman_output.json with at least one FeliCa tag present to populate a positive sample and lock the iceman-native shape into the live fixture set.

### Entry: hf 15 dump / hf felica litedump / hf legic dump passthrough (identical both forks)

- **Middleware now iceman-native**:
  - `hf15read.py`: command form `"hf 15 dump -f {path}"` — iceman CLI `-f/--file` (cmdhf15.c:1803). Middleware only checks `executor.startPM3Task` return + file existence on disk; no keyword parsing.
  - `felicaread.py`: command form `"hf felica litedump"` — iceman `cmdhffelica.c:5056 CmdHFFelicaDumpLite`, dispatch table entry at `:5329` (`{"litedump", ...}`). Matrix v2 correction (L402) confirms iceman and legacy share the SAME command name — no command-translate needed.
  - `legicread.py`: command form `"hf legic dump"` — iceman `cmdhflegic.c:871 CmdLegicDump`, dispatch table entry at `:1471`. Emits `pm3_save_dump` "Saved N bytes ..." line on success; no `"Done!"` sentinel. Middleware only checks `startPM3Task` return + file existence.
- **Adapter still running iceman→legacy**:
  - `_normalize_save_messages` (pm3_compat.py; cited by matrix L1492-1496) lowercases iceman `"Saved N bytes..."` → legacy `"saved N bytes..."`. NOT on the middleware's critical path for any of these three commands (middleware does not parse the save line), but runs generically via `_RESPONSE_NORMALIZERS` wiring for any command that emits a save message.
  - `hf felica litedump` iceman behavior diverges from legacy (matrix L390-406): iceman `CmdHFFelicaDumpLite` at `:5113-5200` emits a TRACE block via `print_hex_break` but does NOT write a `.bin` dump file — the legacy fork wrote to disk. 0 iceman trace samples in iceman_output.json (matrix L396). Impact: middleware `felicaread.read()` reports `{'return': 0, 'file': path}` even though the file never exists on iceman. Phase 4 to reconcile once a real iceman FeliCa litedump capture is available.
- **Live symptom (iceman FW, current adapter)**: NONE observed for hf 15 dump and hf legic dump (file-existence path unaffected). For hf felica litedump: silent success-report with no file on disk — downstream consumers that open the reported path will hit a FileNotFoundError. No live breakage because the flow is rarely exercised; surfaced as a Phase 4 todo.
- **Phase 4 action**:
  - No adapter changes required for hf 15 dump / hf legic dump (middleware is already iceman-native command form + content-agnostic).
  - For hf felica litedump: when iceman trace capture is available, verify whether iceman actually writes a dump file via an alternate helper or if the middleware should issue a different command (e.g., `hf felica dump`). The matrix v2 correction reopens this question.

### Entry: sniff HF/LF trace-len patterns (iceman Recorded activity / Reading bytes)

- **Middleware now iceman-native**:
  - `sniff.PATTERN_HF_TRACE_LEN = r'(?:trace len = |Recorded activity \( )(\d+)'` (sniff.py) — iceman `cmdtrace.c:1181/1425` emits `PrintAndLogEx(SUCCESS, "Recorded activity ( %u bytes )", gs_traceLen)`. Legacy emitted `"trace len = N"`. Alternation keeps the legacy form tolerated during the Phase 4 transition; once adapter is disabled, the `trace len = ` branch becomes dormant.
  - `sniff.PATTERN_LF_TRACE_LEN = r'Reading (\d+) bytes from device memory'` (sniff.py) — iceman `cmddata.c:1873` emits `PrintAndLogEx(INFO, "Reading %u bytes from device memory", n)`. IDENTICAL on both firmwares.
- **Adapter still running iceman→legacy**:
  - No dedicated trace-len normalizer in pm3_compat.py (grep confirms no `_normalize_trace_len`). The `_RE_DOTTED_SEPARATOR` generic rewriter (pm3_compat.py:1070/1122) has no effect on these sentinels (they do not use dotted leaders).
- **Live symptom**: NONE — patterns match both firmware forms via alternation.
- **Phase 4 action**:
  - After adapter disable, the `"trace len = "` alternation branch becomes dead text. Optional: drop the alternation once iceman_output.json is re-captured and confirms no trace of the legacy string under iceman.

### Entry: sniff command forms (hf 14a/14b/iclass/topaz sniff, lf sniff, lf config, lf t55xx sniff)

- **Middleware now iceman-native**:
  - `sniff.sniff14AStart()` → `"hf 14a sniff"` (cmdhf14a.c:1079 CLIParser).
  - `sniff.sniff14BStart()` → `"hf 14b sniff"` (cmdhf14b.c:1038 CLIParser).
  - `sniff.sniffIClassAStart()` → `"hf iclass sniff"` (cmdhficlass.c:931 CLIParser).
  - `sniff.sniffTopazStart()` → `"hf topaz sniff"` (cmdhftopaz.c:829 CLIParser).
  - `sniff.sniff125KStart()` → `"lf sniff"` (cmdlf.c:955 CLIParser).
  - `sniff.sniffT5577Start()` → `"lf config -a 0 -t 20 -s 10000"` + `"lf t55xx sniff"` (cmdlf.c:626 / cmdlft55xx.c:4336, both CLIParser forms).
  - The `lf config` flag spelling `-a 0 -t 20 -s 10000` is iceman CLIParser form. Legacy used bare `a 0 t 20 s 10000` (param_getchar loop, cmdlf.c legacy fork). Matrix v2 L1418-1436 flags this as STRUCTURAL divergence requiring command-translate on the LEGACY direction.
- **Adapter running iceman→legacy**:
  - `_REVERSE_RULES` in pm3_compat.py — the `lf config` reverse rule IS WIRED at `pm3_compat.py:805-806`. Pattern: `re.compile(r'^lf config\s+-a\s+(\S+)\s+-t\s+(\S+)\s+-s\s+(\S+)$')` → replacement `r'lf config a \1 t \2 s \3'` rewrites iceman CLIParser flag form to legacy bare-char form for legacy-direction transmit. Verified directly during P3.8 fixer review (2026-04-17). Matrix v2 L1436's "NOT wired" claim is STALE — the rule was added at some prior refactor pass.
  - All other sniff commands have IDENTICAL spelling on both forks; no command-translate required.
- **Live symptom (iceman FW, current adapter)**: NONE. sniff.py emits iceman-native syntax; on iceman firmware the forward path is a no-op (no translation needed). On legacy firmware the reverse rule at :805-806 rewrites correctly. No breakage either direction.
- **Phase 4 action**:
  - Reverse rule wired and correct; no Phase 4 action required for `lf config`.
  - Sniff command forms do not need Phase 4 changes; middleware is already iceman-canonical.
  - Matrix v2 L1436 text should be updated during Phase 4 matrix reconciliation (already tracked under "Documentation debt" at the end of this gap log).

### Entry: P3.8 dormant / identical-both-firmwares (informational)

No live symptom but documented for Phase 4 audit cross-check:

- `hffelica.CMD = 'hf felica reader'` + `TIMEOUT = 10000` — iceman/legacy share the top-level command spelling. Only the SUCCESS sentinel differs (refactored above).
- `hf15read.CMD = 'hf 15 dump'` — dispatch table entry identical between iceman and legacy (cmdhf15.c:3629 / factory fork). CLI `-f` flag identical.
- `legicread.CMD = 'hf legic dump'` + `TIMEOUT = 5000` — iceman/legacy share the command spelling (cmdhflegic.c:1471 / factory fork). No output keyword parsed by middleware.
- `felicaread.CMD = 'hf felica litedump'` + `TIMEOUT = 5000` — identical command both firmwares; output parse semantics differ but middleware doesn't parse output content. See hf felica litedump entry above for the trace-vs-file gap deferred to Phase 4.
- All `sniff.PATTERN_T5577_*` regexes (sniff.py) — `'Default pwd write'`, `'Default write'`, `'Leading ... pwd write'` lines. Both iceman (cmdlft55xx.c:4336 handler) and legacy emit identical table format. Trace-parity test confirms extraction works on iceman-shape bodies.
- `sniff.PATTERN_M1_KEY = r'key\s+([A-Fa-f0-9]+)'` (sniff.py) — iceman `hf list mf` annotation lines emit `"key <hex>"` substring verbatim. Identical both firmwares.

---

## P3.4 Erase flow

### Entry: erase.py hf mf wrbl split-brain resolution (cross-module parity with P3.3)

- **Middleware now iceman-native**:
  - `erase._KW_WRBL_SUCCESS = r'Write \( ok \)'` (erase.py:88) — iceman `cmdhfmf.c:1389`, `:9677`, `:9760` emit `PrintAndLogEx(SUCCESS, "Write ( " _GREEN_("ok") " )")`. Three identical emission sites — all use the `Write ( ok )` literal. Matches the constant exported by `hfmfwrite._KW_WRBL_SUCCESS` (P3.3 refactor) — the two modules now agree on the post-flip success sentinel.
  - Five prior call sites (erase.py legacy L288, L296, L318, L326 in `_erase_std_m1` + L79 Gen1a probe alternation group) all carried the alternation `'isOk:01' in cache or 'Write ( ok )' in cache`. Post-refactor all five collapse to `re.search(_KW_WRBL_SUCCESS, wr_cache)`.
  - erase.py:79 Gen1a probe `_RE_CGETBLK_BLOCK_DATA` now drops `isOk:01` from the alternation group; iceman `cmdhfmf.c:6171` has zero `isOk:` emissions anywhere in the cgetblk path (matrix L817 grep confirmation).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1216-1234` `_normalize_wrbl_response()` rewrites iceman `"Write ( ok )"` → legacy `"isOk:01"` and `"Write ( fail )"` → legacy `"isOk:00"`. Wired for `hf mf wrbl` at `pm3_compat.py:1826` (`_RESPONSE_NORMALIZERS['hf mf wrbl'] = [_normalize_wrbl_response]`). SAME adapter flagged in P3.3 — one removal Phase 4 line item unblocks both hfmfwrite.py and erase.py.
- **Live symptom (iceman FW, with current adapter)**:
  - `erase._erase_std_m1()` returns `'error'` on the FIRST block write of every standard MF1K/MF4K erase: adapter rewrites iceman `Write ( ok )` → `isOk:01` before middleware sees it; iceman-native regex `Write \( ok \)` no longer finds either literal; both the 3× Key A retry and the Key B fallback trip `not written` → `return 'error'`.
  - Cascading failure: Erase flow UI shows "Erase Failed!" on every standard MF1K/MF4K card even when PM3 actually wrote every block successfully. Gen1a magic cards unaffected (they use `hf mf cwipe`, which has no `Write ( ok )` sentinel — see separate entry below).
  - Observable in test: `tests/phase3_trace_parity/test_erase_flow.py` — all 10 live `hf mf wrbl` samples carry adapter-normalised `isOk:00` tokens (trace captured post-adapter). Test `_test_hf_mf_wrbl` asserts iceman-native regex correctly MISSES these during transition; 2 synthetic iceman-native samples (`Write ( ok )` / `Write ( fail )`) exercise the post-Phase-4 target shape and PASS.
- **Phase 4 action**:
  - REMOVE `_normalize_wrbl_response` from `_RESPONSE_NORMALIZERS['hf mf wrbl']` (`pm3_compat.py:1826`). Same removal resolves P3.3 (`hfmfwrite.py`) and P3.4 (`erase.py`) simultaneously.
  - After adapter disable, iceman raw `Write ( ok )` / `Write ( fail )` reach both middleware modules verbatim; both use the identical regex constant.
  - **RESOLVES the P3.3 cross-module entry** ("erase.py cross-module wrbl split-brain", gap log L325-330) by construction: the alternation is gone from erase.py.

### Entry: erase.py hf mf cgetblk Gen1a probe regex — alternation tightening

- **Middleware now iceman-native**:
  - `erase._RE_CGETBLK_BLOCK_DATA = re.compile(r'(?:Block\s*0\s*:|data:|^\s*\d+\s*\|)\s*[A-Fa-f0-9 ]{16,}', re.MULTILINE)` (erase.py:93) — matches three shapes:
    - Iceman raw grid `  0 | XX XX ...| ascii` (cmdhfmf.c:570 `mf_print_block_one` block-0 branch, 3-space indent + `%3d | hex | ascii`);
    - Adapter-normalised `data: XX XX ...` (pm3_compat.py:1252 `_normalize_rdbl_response` rewrite, wired at `:1829` for `hf mf cgetblk`);
    - Device-trace-specific `Block 0: XX XX ...` synth shape (retained for backward compat).
  - Previous regex included `isOk:01` as a fourth alternation branch — iceman has zero `isOk:` emissions in any read path (matrix L817), so the branch was dead weight. Dropped per Option B.
  - Negative probe keywords `'wupC1 error'` and `"Can't read block"` are iceman-native verbatim (`armsrc/mifarecmd.c:103/116/2921` emits `wupC1 error`; `cmdhfmf.c:6171` emits `Can't read block. error=%d`). No adapter normalization needed.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1252-1268` `_normalize_rdbl_response()` rewrites iceman grid form `  N | hex | ascii` → `data: hex`. Wired for `hf mf cgetblk` at `pm3_compat.py:1829`. Currently DORMANT on the device's installed iceman build (which emits the grid shape verbatim with no adapter hit), but activates on a HEAD iceman flash. Same flagged-dormant adapter in P3.2 entry "hf mf rdbl / hf mf rdsc / hf mf cgetblk block-data regression".
- **Live symptom (iceman FW)**:
  - NONE — the alternation regex above tolerates both iceman raw and adapter-converted shapes. Test confirms 10/10 live `hf mf cgetblk` samples (all `wupC1 error` / `data: ...` bodies) classify correctly. Synthetic raw-grid `  0 | hex | ascii` and adapter-converted `data: hex` samples both PASS.
- **Phase 4 action**:
  - No adapter change required for erase.py alone. The P3.2 optional cleanup (remove `_normalize_wrbl_response` from `hf mf rdsc` wiring at pm3_compat.py:1828) still applies.
  - Optional middleware simplification: drop `^\s*\d+\s*\|` grid branch from `_RE_CGETBLK_BLOCK_DATA` once the device firmware guaranteed-converges on one shape (adapter on → `data:` only; adapter off → grid only). Currently keeping both guards against firmware-bump regressions.

### Entry: erase.py hf mf cwipe success — iceman-native text emission (no middleware regex consumer)

- **Middleware now iceman-native**:
  - `erase._erase_magic_m1()` checks only `ret = executor.startPM3Task('hf mf cwipe', 28888)` — `ret == -1` means timeout; otherwise assumed success. No keyword / regex parse of the body.
  - Iceman source: `cmdhfmf.c:5896` `PrintAndLogEx(SUCCESS, "Card wiped successfully")` on success; `:5892` `PrintAndLogEx(ERR, "Can't wipe card. error %d", res)` + `return PM3_ESOFT` on hardware failure. The `PM3_ESOFT` return is what `startPM3Task` sees — `ret != -1` for timeout-only semantics, so a hardware error still reads as success to erase.py.
- **Adapter still running iceman→legacy**:
  - `_RESPONSE_NORMALIZERS['hf mf cwipe']` — not explicitly wired (checked pm3_compat.py:1820-1860 range). Generic post-normalize dot-stripper `_RE_DOTTED_SEPARATOR` (pm3_compat.py:1070/1122) has no load-bearing dotted fields in the cwipe output. No adapter interference.
- **Live symptom**:
  - PARTIAL: if iceman's `mf_chinese_wipe()` returns a non-zero error code (`cmdhfmf.c:5891-5894`), cwipe emits `Can't wipe card. error %d` to the user log and returns `PM3_ESOFT` — middleware reads that as success, flow reports "Erase success" to UI, but card is actually NOT wiped. No regression introduced by P3.4 refactor — the pre-refactor middleware had the same behavior. Matrix L640-645 (implied by `hf mf cwipe` entry) makes this the activity-layer's responsibility to verify with a follow-up `hf mf cgetblk`. No Phase 4 action required at the erase.py layer.
- **Phase 4 action**:
  - NO-OP for erase.py. Consider strengthening the check to `hasKeyword('Card wiped successfully')` as a post-Phase-4 enhancement, but this is middleware-touching-legacy detection work — out of compat-flip scope.

### Entry: erase.py lf t55xx detect success sentinel — iceman `Chip type` lowercase tolerance

- **Middleware now iceman-native**:
  - `erase._RE_T55XX_CHIP_OK = re.compile(r'Chip\s+[Tt]ype')` (erase.py:106) — case-insensitive on `type` character, whitespace-flexible between `Chip` and `Type`. Matches both:
    - Iceman raw `Chip type......... T55x7` (`cmdlft55xx.c:1837` — lowercase `t`, 9 dots);
    - Adapter-normalized `     Chip Type      : T55x7` (pm3_compat.py:1572 `_normalize_t55xx_config` rewrite — capital `T`, colon).
  - Previously: `'Chip Type' in cache` — literal substring, capital T ONLY. Iceman emits lowercase, so without the adapter the legacy-style check would miss iceman FW responses entirely. Alternation tolerance added via the regex character class.
  - Negative sentinel `Could not detect modulation automatically` (`cmdlft55xx.c:1307`) is identical across both firmwares after prefix strip (legacy emits `[!] Could not detect...`, iceman emits same without prefix; executor.hasKeyword strips prefix).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1563-1581` `_normalize_t55xx_config()` + `_RE_T55XX_CHIP_NEW = re.compile(r'^\s*Chip type\.{3,}\s+(.*?)$', re.MULTILINE | re.IGNORECASE)` rewrites iceman `Chip type......... T55x7` → `     Chip Type      : T55x7`. Wired for `lf t55xx detect` at `pm3_compat.py:1861` (`_RESPONSE_NORMALIZERS['lf t55xx detect'] = [_normalize_t55xx_config]`).
  - Generic `_RE_DOTTED_SEPARATOR` (pm3_compat.py:1070/1122) runs in `_post_normalize` AFTER `_normalize_t55xx_config`, but the normalizer has already consumed the dotted form — no double-rewrite impact.
- **Live symptom (iceman FW, with current adapter)**:
  - NONE — adapter converts `Chip type` → `Chip Type`; erase regex tolerates both cases. Test confirms 10/10 live `lf t55xx detect` samples classify correctly (all are `Could not detect` or `No known` bodies; success-path synthetic samples PASS for both shapes).
- **Phase 4 action**:
  - Once `_normalize_t55xx_config` is disabled in Phase 4, iceman raw `Chip type` reaches erase.py verbatim; `_RE_T55XX_CHIP_OK` continues to match via the `[Tt]` character class. No regression on adapter removal.
  - Cross-reference: same `_normalize_t55xx_config` adapter affects `lft55xx.py:430/687` (P3.5 Read LF scope — separate refactor pass).

### Entry: erase.py lf t55xx wipe / lf t55xx chk — return-only semantics (no middleware regex)

- **Middleware now iceman-native**:
  - `erase.erase_t5577()` calls `lf t55xx wipe` (`:358`), `lf t55xx wipe -p 20206666` (`:371`), `lf t55xx chk -f <file>` (`:395`). For all three commands the middleware checks only `ret = executor.startPM3Task(...)` return code; no body text is parsed.
  - Iceman source: `cmdlft55xx.c:3229` `CmdT55xxWipe` returns `PM3_SUCCESS` on completion (internal writeblock errors reported via `PrintAndLogEx(WARNING, "Warning: error writing blk %d", blk)` at `:3306/3313` but do NOT alter the return code); `cmdlft55xx.c:3338` `CmdT55xxChkPwds` returns `PM3_SUCCESS` after brute force regardless of match (success-match logged via `PrintAndLogEx(SUCCESS, "Found valid password...")`, but again not load-bearing for erase's startPM3Task return).
  - The activity layer uses the follow-up `lf t55xx detect` sentinel (previous entry) as the actual success-check — wipe/chk are "attempt" steps, not verified steps.
- **Adapter still running iceman→legacy**:
  - `_RESPONSE_NORMALIZERS['lf t55xx wipe'] = []` (pm3_compat.py:1865) — empty, no interference.
  - `_RESPONSE_NORMALIZERS['lf t55xx chk'] = [_normalize_t55xx_chk_password]` (pm3_compat.py L1869 per Grep) — rewrites the `Found valid password: [ <hex> ]` bracket line to colon form. erase.py does NOT consume the password; normalizer is dead weight for erase but still runs. No live impact.
  - Forward/reverse command translators (pm3_compat.py:434/642 `lf t55xx wipe p` ↔ `lf t55xx wipe -p`; `:439/648` `lf t55xx chk -f` ↔ `lf t55xx chk f`) wired both directions; middleware now emits iceman form (`-p`, `-f`) directly.
- **Live symptom**: NONE — all three commands are return-code-only paths.
- **Phase 4 action**: NO-OP. Informational entry. `_normalize_t55xx_chk_password` remains wired for any downstream middleware that eventually consumes the password (e.g., a future password-aware erase flow).

### Entry: erase.py hf mf fchk / hf 14a info — passthrough (identical iceman shape)

- **Middleware now iceman-native**:
  - `erase._erase_std_m1()` uses these regexes on the response bodies:
    - `r'found\s+(\d+)/(\d+)\s+keys'` — iceman `cmdhfmf.c` fchk emits the literal `found N/M keys` line on completion (both firmwares identical; no adapter needed).
    - `r'\|\s*(\d+)\s*\|\s*([0-9a-fA-F]{12})\s*\|\s*(\d)\s*\|\s*([0-9a-fA-F]{12})\s*\|\s*(\d)\s*\|'` — 4-column pipe-bordered key table from iceman `printKeyTable`. P3.2 gap log ("hf mf fchk key-table regression (dormant)") confirms the device's installed iceman emits this shape verbatim (no adapter hit); a HEAD iceman flash would trigger the `_normalize_fchk_table()` adapter at pm3_compat.py:1160 to rewrite 5-column → 4-column.
    - `r'SAK:\s*([0-9a-fA-F]+)'`, `r'UID:\s*([0-9A-Fa-f ]+)'`, `r'ATQA:\s*([0-9A-Fa-f ]+)'` — hf 14a info colon form, iceman `cmdhf14a.c:653-655/770-774` emits these verbatim (identical to legacy after prefix strip).
- **Adapter still running iceman→legacy**: none on the critical erase paths. `_normalize_fchk_table` is dormant on the device build. `hf 14a info` has `_normalize_manufacturer` + `_normalize_magic_capabilities` wired (pm3_compat.py:1836) — neither affects the SAK/UID/ATQA parse.
- **Live symptom**: NONE — 10/10 live samples for both commands classify correctly.
- **Phase 4 action**: NO-OP. Cross-reference with P3.2 dormant entries.

---

## P3.6 Write LF flow

### Entry: lf <tag> clone commands — iceman-canonical send-side (zero SEND divergence)

- **Middleware now iceman-native** (inline citations added in `lfwrite.py`):
  - `write_em410x()` (lfwrite.py L157) → `lf em 410x clone --id <hex>`. CLI spec: `cmdlfem410x.c:625` CLIParserInit "lf em 410x clone", argtable `arg_str1(NULL, "id", ...)`. Dispatch `cmdlfem410x.c:896`.
  - `write_hid()` (lfwrite.py L173) → `lf hid clone -r <hex>` (short of `--raw`). CLI spec: `cmdlfhid.c:400` CmdHIDClone / CLIParserInit "lf hid clone", argtable `arg_str0("r", "raw", ...)`. Dispatch `cmdlfhid.c:724`.
  - `write_indala()` (lfwrite.py L189) → `lf indala clone -r <hex>`. CLI spec: `cmdlfindala.c:786` CmdIndalaClone / CLIParserInit "lf indala clone", argtable `arg_str0("r", "raw", ...)`. Dispatch `cmdlfindala.c:1103`.
  - `write_fdx_par()` (lfwrite.py L204) → `lf fdxb clone --country <dec> --national <dec>`. CLI spec: `cmdlffdxb.c:712` CLIParserInit "lf fdxb clone", argtable `arg_u64_1("c", "country", ...) + arg_u64_1("n", "national", ...)`. Dispatch `cmdlffdxb.c:909`. Namespace change: iceman `fdxb` (B-suffix) vs legacy `fdx`.
  - `RAW_CLONE_MAP` (lfwrite.py L138-143) → `lf <tag> clone -r <hex>` for securakey/gallagher/pac/paradox/nexwatch. All five CLI specs verified via `arg_str0/1("r", "raw", ...)`:
    - `cmdlfsecurakey.c:172/301`
    - `cmdlfgallagher.c:175/387`
    - `cmdlfpac.c:225/402`
    - `cmdlfparadox.c:296/478`
    - `cmdlfnexwatch.c:296/586`
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py` reverse translators (`_reverse_*`) rewrite iceman-native forms to legacy syntax when talking to legacy firmware. For `lf em 410x clone --id` → legacy `lf em 410x_write <id>`, `lf fdxb clone --country X --national Y` → legacy `lf fdx clone c X ...`, `lf <tag>_read` → `lf <tag> reader`, etc. These rules remain live in Phase 3 and are retained through Phase 4 — they implement the legacy-direction compat for legacy firmware support.
- **Live symptom (iceman FW, current adapter)**:
  - NONE observed. Middleware emits iceman CLIParser-native form; iceman firmware accepts natively. Reverse rules target the LEGACY direction only, so on iceman hardware the forward path is a no-op.
  - Live `tests/phase3_trace_parity/test_write_lf_flow.py::lf t55xx write` → 4 samples, 4 pass (iceman `Writing page N  block: NN  data: 0xHHHHHHHH` shape at `cmdlft55xx.c:1932`).
- **Phase 4 action**:
  - No adapter CHANGES required for the forward (iceman) direction of these commands. Reverse rules remain catalogued for legacy-fw compatibility.
  - During Phase 4 close-out: re-validate against iceman_output.json once the response normalizers upstream (e.g. `_normalize_fdxb_animal_id`, `_normalize_chipset_detection`) are disabled — P3.5 `lf search` refactor surfaces the downstream verify-path regressions; P3.6 has no send-side blockers.

### Entry: lf t55xx write / lf t55xx restore — iceman-canonical, response not parsed

- **Middleware now iceman-native**:
  - `write_raw_t55xx()` (lfwrite.py L249), `write_b0_need()` (lfwrite.py L257), `write_raw()` (lfwrite.py L276): all emit `lf t55xx write -b <N> -d <hex> [-p <hex>]`. CLI spec: `cmdlft55xx.c:1853` CmdT55xxWriteBlock / CLIParserInit "lf t55xx write", argtable `arg_int1("b", "blk", ...) + arg_str0("d", "data", ...) + arg_str0("p", "pwd", ...)`. Dispatch `cmdlft55xx.c:4794`. Iceman emits info line `Writing page %d  block: %02d  data: 0x%08X [pwd: 0x%08X]` at `cmdlft55xx.c:1932` — middleware does NOT parse this (relies on PM3 task return code).
  - `write_dump_t55xx()` (lfwrite.py L311): emits `lf t55xx restore -f <path>`. CLI spec: `cmdlft55xx.c:2775` CmdT55xxRestore / CLIParserInit "lf t55xx restore", argtable `arg_str0("f", "file", ...) + arg_str0("p", "pwd", ...)`. Dispatch `cmdlft55xx.c:4790`. Iceman emits `Done!` (`cmdlft55xx.c:2771`) on success; middleware does NOT parse this (return code only + dump-file compare).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py` trace-prefix canonicalisation (matrix Appendix B L1554-1555) strips `lf t55xx restore f` → `lf t55xx restore` and `lf t55xx write` has no prefix stripping (already bare). No behavioural impact on iceman forward path.
  - `_normalize_t55xx_config` runs on the `lf t55xx detect` response (P3.5 lft55xx scope), not on the write response — no interaction with P3.6 middleware.
- **Live symptom**: NONE. Live `lf t55xx write` samples (4 in iceman_output.json) all pass the trace-parity test's iceman-shape regex. `lf t55xx restore` has 0 live samples.
- **Phase 4 action**: No adapter changes required for lfwrite.py's t55xx code paths. Response-parsing audit complete (middleware is return-code-driven; no `Done!` / `Write OK` keyword dependencies in P3.6 scope).

### Entry: lf em 4x05 write / lf em 4x05 read — inline verify regex tightened

- **Middleware now iceman-native**:
  - `write_block_em4x05()` (lfwrite.py L384) → `lf em 4x05 write -a <dec> -d <hex> -p <hex>`. CLI spec: `cmdlfem4x05.c:1399` CmdEM4x05Write / CLIParserInit "lf em 4x05 write", argtable `arg_int0("a", "addr", ...) + arg_str1("d", "data", ...) + arg_str0("p", "pwd", ...)`.
  - `write_dump_em4x05()` (lfwrite.py L413) inline verify loop → `lf em 4x05 read -a <dec> [-p <hex>]` + response regex. CLI spec: `cmdlfem4x05.c:1352` CmdEM4x05Read / CLIParserInit "lf em 4x05 read", argtable `arg_int1("a", "addr", ...) + arg_str0("p", "pwd", ...)`.
  - **Regex tightening (P3.6 fix)**: previously `re.search(r'\|\s*([A-Fa-f0-9]+)\s*', content)` (lfwrite.py L430 pre-P3.6). This loose form matched ANY pipe-separated hex substring (could false-match unrelated pipe-tokens in the cache). Tightened to iceman-canonical targeting cmdlfem4x05.c:1391 emission `Address %02d | %08X - %s`:
    - Anchored: `re.search(r'Address\s+\d+\s+\|\s+([A-Fa-f0-9]{8})\s+-', content)`.
    - Fallback: `re.search(r'\|\s+([A-Fa-f0-9]{8})\s+-', content)` — tolerates executor-cleaned cache bodies where the `Address NN` prefix was stripped.
  - Test coverage (`test_write_lf_flow.py`): 3 positive + 1 negative shape validated. Negative (`Pipe | FF` bad body) correctly misses the anchored regex.
- **Adapter still running iceman→legacy**:
  - `_normalize_em4x05_info` (pm3_compat.py:1586) normalizes `lf em 4x05 info` response (dotted→colon). DOES NOT touch `lf em 4x05 read` response. No interaction with the tightened regex.
  - Matrix L1048-1053 (Phase 4 audit target): `lf em 4x05 read/write/dump` divergence table entries are informational; no adapter wired for `read` response format beyond the shared `_RE_DOTTED_SEPARATOR` generic stripper.
  - The generic `_RE_DOTTED_SEPARATOR` in `_post_normalize()` could in theory alter an `Address %02d` prefix if dots appeared; iceman emission has NO dots in this line — confirmed by source grep on `cmdlfem4x05.c:1391`. No conflict.
- **Live symptom**: 0 live samples in iceman_output.json for `lf em 4x05 write` / `lf em 4x05 read`. Synthetic test samples cover iceman raw shape, Lock suffix shape, prefix-stripped fallback, and negative (bad) shape — all pass.
- **Phase 4 action**: No adapter changes required. Regex is structurally correct for iceman-native emission; re-validate with real iceman samples once the write flow is exercised on iceman firmware during Phase 4 close-out.

### Entry: lf sea (short-prefix alias) — identical both firmwares, iceman-canonical

- **Middleware now iceman-native**:
  - `lfwrite._inline_verify()` (lfwrite.py L551) → `lf sea`.
  - `lfverify.verify()` scan-fallback branch (lfverify.py L219) → `lf sea`.
  - Both forks accept `lf sea` as a short-prefix alias for `lf search` (cmdlf.c:1890 CLIParserInit "lf search"). Divergence matrix Appendix B L1567: "kept as `lf sea` in middleware since both accept it."
- **Adapter still running iceman→legacy**:
  - No translation rule for `lf sea` in either direction — both firmwares canonicalise via the dispatcher. Pass-through.
- **Live symptom**: NONE. 10 live `lf sea` samples in iceman_output.json, all 10 pass the trace-parity test (`Couldn't identify a chipset` / `No data found` / `Searching for auth LF` shapes — iceman's normal no-tag emission via `cmdlf.c:1991` iterated demod loop + `graph.c` / `cmddata.c` debug paths).
- **Phase 4 action**: None. Short-prefix alias is stable iceman behaviour; no adapter-dependent shape to reconcile.

### Entry: P3.6 dormant / identical-both-firmwares (informational)

No live symptom but documented for Phase 4 audit cross-check:

- `write_nedap()` (lfwrite.py L216) delegates to `write_raw_t55xx()` — same T55xx write path as other B0+raw paths. No separate PM3 command emission.
- `PAR_CLONE_MAP` (lfwrite.py L225) — dispatch table only, no PM3 commands of its own.
- `B0_WRITE_MAP` (lfwrite.py L117-129) — T55xx block 0 config word literals. Source of truth: `lfwrite_strings.txt` exact extraction from Cython binary. 12 entries (VISA2000/VIKING/NORALSY/PRESCO/HID_PROX/AWID/PYRAMID/IO_PROX/KERI/JABLOTRON/GPROX_II/NEDAP). DATA, not divergence-sensitive.
- `LOCK_UNAVAILABLE_LIST` (lfwrite.py L147) — empty list in v1.0.90; placeholder for future expansion. Dormant.
- `check_detect()` (lfwrite.py L459) — delegates to `lft55xx.wipe_t()` / `detectT55XX()` / `chkT55xx()`. All PM3 command emission is inside `lft55xx` module (P3.5 scope). No direct emission from lfwrite.py.
- `lfverify.verify_t55xx()` (lfverify.py L94) / `verify_em4x05()` (lfverify.py L130) — delegate to `lft55xx` / `lfem4x05` (P3.5 scope). Only `lf sea` falls back to direct executor emission.

---

## P3.5 Read LF flow

### Entry: lft55xx.py — detect-output dotted-field regressions

- **Middleware now iceman-native**:
  - `lft55xx._RE_CHIP_TYPE = r'Chip [Tt]ype\.+\s+(\S+)'` (lft55xx.py) — iceman `cmdlft55xx.c:1837` `printConfiguration()` emits `" Chip type......... " _GREEN_("%s")` with 9 dots and LOWERCASE `type`. The `[Tt]` character class tolerates the legacy capital `Type` so adapter-processed bodies (`_normalize_t55xx_config` rewrites the dotted leader to colon-separator) still feed the same regex during the Option B transition window.
  - `lft55xx._RE_MODULATE = r'Modulation\.+\s+(\S+)'` (lft55xx.py) — iceman `cmdlft55xx.c:1838` 8-dotted form; same shape for `ASK`/`FSK1`/`FSK2a`/`PSK1`/`NRZ`.
  - `lft55xx._RE_BLOCK0 = r'Block0\.+\s+([A-Fa-f0-9]+)'` (lft55xx.py) — iceman `cmdlft55xx.c:1843` emits `" Block0............ %08X %s"` with 12 dots and NO `0x` prefix. Legacy had `"     Block0         : 0x000880E0"` with `0x`. Regex captures the raw 8-hex dword only.
  - `lft55xx._RE_PWD = r'[Pp]assword\.{8,}\s+([A-Fa-f0-9]+)'` (lft55xx.py) — iceman `cmdlft55xx.c:1847` `" Password.......... %08X"` (10 dots). The `{8,}` floor excludes the `Password set.` 6-dot counterpart at :1845 which emits `Yes`/`No` non-hex — regex engine would backtrack but the usepwd gate ensures callers only invoke when the password line is present.
  - `lft55xx._KW_CHIP_TYPE = 'Chip type'` (lft55xx.py) — substring keyword flipped lowercase; `executor.hasKeyword` uses `re.search` which is case-sensitive, so capital `Chip Type` on adapter-processed bodies will NOT match. Adapter reshapes iceman → legacy via `_normalize_t55xx_config`; post-flip the middleware keyword expects raw iceman shape.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1563-1581` `_normalize_t55xx_config()` + the companion regexes `_RE_T55XX_CHIP_NEW` / `_RE_T55XX_MOD_NEW` / `_RE_T55XX_BLOCK0_NEW` / `_RE_T55XX_PWD_SET_NEW` / `_RE_T55XX_PWD_NEW` collectively rewrite the iceman dotted shape to legacy colon/pipe shape (injecting `0x` prefix on Block0, capitalising `Type`, adding `:` separator). Wired for `lf t55xx detect` at `pm3_compat.py:1861` (`_RESPONSE_NORMALIZERS['lf t55xx detect'] = [_normalize_t55xx_config]`), for `lf t55xx dump` at `:1862`, and for `lf t55xx read` at `:1863`.
  - Each normalizer runs BEFORE middleware sees the body, so post-flip the middleware regex targeting iceman dotted form MISSES on adapter-processed bodies.
- **Live symptom (iceman FW, with current adapter)**:
  - `lft55xx.parser()` returns `{'chip': '', 'modulate': '', 'b0': ''}` (empty strings) on every successful detect: adapter rewrites iceman `Chip type......... T55x7` → `     Chip Type      : T55x7`; middleware regex `Chip [Tt]ype\.+\s+(\S+)` expects at least 1 dot via `\.+` which fails on colon-separator — regex misses; parser emits empty chip string. Cascading: `detectT55XX()` still returns 0 because `hasKeyword('Chip type')` MATCHES adapter-shape `     Chip Type      : T55x7` (substring `Chip type` is NOT present in adapter output because adapter capitalised `type` to `Type`); actually the adapter `_RE_T55XX_CHIP_NEW` pattern uses `re.IGNORECASE` and rewrites to `' Chip Type '` — the substring `Chip type` (lowercase `type`) DOES NOT appear in adapter output; `detectT55XX` returns -1 on iceman successful detect.
  - Read flow UI shows "Tag read failed" on every successful T55xx detect on iceman firmware until Phase 4 disables the adapter. This is a HIGH severity live regression.
  - Observable in test: `tests/phase3_trace_parity/test_read_lf_flow.py::lf t55xx detect` — 10 live samples are all `Could not detect` bodies (card absent during capture), so the positive-path breakage is not exercised in live fixtures. Synthetic iceman-native samples (4 at module-level) exercise T55x7/Q5/pwd/CASE1 and all PASS; these represent the Phase-4 target shape.
- **Phase 4 action**:
  - REMOVE `_normalize_t55xx_config` from `_RESPONSE_NORMALIZERS['lf t55xx detect']` / `['lf t55xx dump']` / `['lf t55xx read']` (pm3_compat.py:1861-1863).
  - After adapter disable, iceman raw dotted shape reaches middleware verbatim; `_RE_CHIP_TYPE`/`_RE_MODULATE`/`_RE_BLOCK0`/`_RE_PWD` capture directly and `_KW_CHIP_TYPE` matches.
  - Cross-reference: same adapter also affects `erase.py` T55xx detect check (gap log P3.4 entry "lf t55xx detect success sentinel"). One normalizer removal closes both P3.4 + P3.5 T55xx detect paths.

### Entry: lft55xx.py — dumpT55XX success sentinel flip (`Saved` vs `saved 12 blocks`)

- **Middleware now iceman-native**:
  - `lft55xx.dumpT55XX()` `hasKeyword(r'Saved \d+ bytes to binary file')` (lft55xx.py) — iceman `fileutils.c:293` emits `PrintAndLogEx(SUCCESS, "Saved %zu bytes to binary file \`%s\`", ...)` with capital `S`, invoked by `cmdlft55xx.c:2647` `pm3_save_dump(filename, ..., jsfT55x7)` on successful T55xx dump. Previous middleware checked for `'saved 12 blocks'` which iceman NEVER emits (grep `/tmp/rrg-pm3/client/src/` for `saved 12 blocks` returns zero matches).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py _normalize_save_messages()` lowercases `Saved` → `saved` (preserved with lowercase `b` in bytes). Wired for `lf t55xx dump` at `pm3_compat.py:1862`.
  - Legacy had `"saved 12 blocks"` (blocks not bytes) — iceman removed the legacy line entirely and consolidated all dump paths through `pm3_save_dump` which uses the `Saved N bytes` format.
- **Live symptom (iceman FW, with current adapter)**:
  - Middleware currently uses the tolerant `Saved \d+ bytes to binary file` regex. Adapter lowercases `Saved` → `saved`; capital-S regex misses the adapter-processed lowercase form; `dumpT55XX()` returns `-2` (failure) on every successful iceman dump through the adapter. Dump path never stored in `DUMP_FILE`; `readT55XX()` propagates the -2 through `chkAndDumpT55xx()` as `detect['dump_ret'] = -2` and `detect['return'] = -1`; UI shows "Read failed".
  - To tolerate the transition window the middleware currently uses `Saved ` verbatim (no `[Ss]` alternation) — this is intentionally iceman-strict per Option B. A Phase-4 adapter-disabled run flips to iceman capital verbatim and the regex matches.
  - Observable in test: synthetic `iceman Saved capital sentinel` PASS; `adapter-lowercase sentinel` PASS via the tolerant `[Ss]aved` regex used in the test harness (keyword-search context, not middleware-critical). Live `lf t55xx dump` has 0 samples in iceman_output.json.
- **Phase 4 action**:
  - REMOVE `_normalize_save_messages` from `_RESPONSE_NORMALIZERS['lf t55xx dump']` (pm3_compat.py:1862). After removal the iceman capital-S shape reaches middleware verbatim.
  - Cross-reference: `_normalize_save_messages` also wired for `lf em 4x05 dump` (:1870/:1871), `hf mfu dump`, `hf 15 dump`, `hf iclass dump`, `data save`. Single normalizer removal would affect all save-message sites; recommend gating on version detection or Phase 4 flip.

### Entry: lft55xx.py — chkT55xx `Found valid password` bracket shape

- **Middleware now iceman-native**:
  - `lft55xx.chkT55xx()` `_RE_FOUND_VALID = r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?'` (lft55xx.py) — iceman `cmdlft55xx.c:3658/3660/3816` emit `PrintAndLogEx(SUCCESS, "Found valid password: [ %08X ]", curr)` with spaces inside brackets. Legacy emitted `"Found valid password: %08X"` without brackets. Bracket tolerance via `\[?` + `\]?` lets the same pattern capture both shapes during the transition window.
  - Previous regex `Found valid.*?:\s*([A-Fa-f0-9]+)` FAILED on iceman output because `[` is not in the `[A-Fa-f0-9]` character class (verified: `python3 -c "import re; print(re.search(r'Found valid.*?:\s*([A-Fa-f0-9]+)', 'Found valid password: [ 51243648 ]'))"` returns `None`).
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1869` `_RESPONSE_NORMALIZERS['lf t55xx chk'] = [_normalize_t55xx_chk_password]` — the `_normalize_t55xx_chk_password` function rewrites iceman bracket form `Found valid password: [ XXXXXXXX ]` → legacy bare-hex `Found valid password: XXXXXXXX` so pre-refactor middleware could match. Post-refactor middleware tolerates both via the `\[?`/`\]?` alternation.
- **Live symptom (iceman FW, with current adapter)**: NONE during transition — both forms match. On iceman raw (adapter disabled) the bracket form matches directly.
- **Phase 4 action**:
  - REMOVE `_normalize_t55xx_chk_password` from `_RESPONSE_NORMALIZERS['lf t55xx chk']` (pm3_compat.py:1869). Optional: tighten middleware regex to bracket-only `r'Found valid password:\s*\[\s*([A-Fa-f0-9]+)\s*\]'` post-Phase-4.

### Entry: lfem4x05.py — info-output dotted fields + `Chip type` lowercase

- **Middleware now iceman-native**:
  - `lfem4x05._RE_CHIP = r'Chip [Tt]ype\.+\s+(\S+)'` (lfem4x05.py) — iceman `cmdlfem4x05.c:869` emits `PrintAndLogEx(SUCCESS, "Chip type..... " _YELLOW_("%s"), em_get_card_str(block0))` with 5 dots and lowercase `type`. Legacy had `" Chip Type:   9 | EM4305"` (pipe with decimal id-then-name). The dotted regex captures iceman shape; `[Tt]` tolerates legacy capital during transition.
  - `lfem4x05._RE_SERIAL = r'Serialno\.+\s+([A-Fa-f0-9]+)'` (lfem4x05.py) — iceman `cmdlfem4x05.c:871` `"Serialno...... %08X"` (6 dots, all-hex serial). Legacy emitted `"  Serial #: 1A2B3C4D"` with `#:` separator.
  - `lfem4x05._RE_CONFIG = r'Block0\.+\s+([A-Fa-f0-9]+)'` (lfem4x05.py) — SEMANTIC FLIP: iceman `printEM4x05Info` at `cmdlfem4x05.c:869-893` has NO `ConfigWord:` field emission (grep `cmdlfem4x05.c` for `ConfigWord` returns zero). Iceman folded config into `Block0........ %08x` at :873. Legacy emitted `ConfigWord: %08X (decoded)` as a separate structural line. `_RE_CONFIG` now targets the iceman `Block0........` dword — semantically "block 0 raw" not "config word decoded"; the downstream `result['cw']` key carries the raw dword which is a subset of what legacy provided.
  - `lfem4x05.parser()` detection keyword flipped from `hasKeyword('Chip Type')` (capital T) to `hasKeyword('Chip type')` (lowercase t) — same rationale as lft55xx: `re.search` is case-sensitive; adapter-processed bodies now carry the legacy capital so the lowercase keyword misses during transition.
- **Adapter still running iceman→legacy**:
  - `pm3_compat.py:1594-1615` `_normalize_em4x05_info()` rewrites iceman `Chip type..... EM4305` → legacy ` Chip Type:   0 | EM4305`, `Serialno...... 1A2B3C4D` → `  Serial #: 1A2B3C4D`, and injects a synthetic `ConfigWord: <hex> (<hex>)` line. Wired for `lf em 4x05 info` at `pm3_compat.py:1868` (and `lf em 4x05_info` / `lf em 4x05 dump` / `lf em 4x05_dump` at :1869-:1871).
- **Live symptom (iceman FW, with current adapter)**:
  - `lfem4x05.parser()` returns `{'found': False}` on every iceman-native EM4x05 detection: adapter rewrites `Chip type.....` → ` Chip Type:` (capital); middleware `hasKeyword('Chip type')` (lowercase) MISSES on the adapter-processed body; parser short-circuits with `found=False` at the keyword gate. Cascading: `info4X05()` returns `{'found': False}`; `infoAndDumpEM4x05ByKey()` marks `return: -1`; `readEM4X05()` returns dict-with-return=-1 to the activity layer; UI shows "Read failed" on every EM4x05 read on iceman firmware.
  - This is a HIGH severity live regression until Phase 4 disables the adapter.
  - Observable in test: `tests/phase3_trace_parity/test_read_lf_flow.py::lf em 4x05 info` — 10 live samples all-empty or `Could not detect`; 3 synthetic iceman-native samples (`iceman EM4305 full info`, `iceman EM4x69 chip variant`, `iceman no-tag empty`) all PASS — these represent the Phase-4 target shape.
- **Phase 4 action**:
  - REMOVE `_normalize_em4x05_info` from `_RESPONSE_NORMALIZERS['lf em 4x05 info']` / `['lf em 4x05_info']` / `['lf em 4x05 dump']` / `['lf em 4x05_dump']` (pm3_compat.py:1868-1871).
  - After adapter disable, iceman dotted shape reaches middleware verbatim; `_RE_CHIP` / `_RE_SERIAL` / `_RE_CONFIG` capture directly; `hasKeyword('Chip type')` matches the raw iceman emission.
  - **ACCEPT structural field loss**: iceman removed the `ConfigWord:` parenthetical descriptor. `result['cw']` now carries block-0 raw hex (a superset of config bits) rather than the legacy decoded `(ConfigWord <hex>)` text. Downstream consumers must adapt; catalogued under APPENDIX. If a decoded config descriptor is required, the middleware would need to run its own block-0 decoder — out of compat-flip scope.

### Entry: lfem4x05.py — dump save sentinel flip (same as T55xx)

- **Middleware now iceman-native**:
  - `lfem4x05.dump4X05()` `hasKeyword(r'[Ss]aved \d+ bytes to binary file')` + `getContentFromRegexG(r'[Ss]aved \d+ bytes to binary file\s*(.*)', 1)` (lfem4x05.py) — same iceman `fileutils.c:293` origin as T55xx dump; `lf em 4x05 dump` at `cmdlfem4x05.c:1343/1345` calls `pm3_save_dump(filename, ..., jsfEM4x69 | jsfEM4x05)` which emits the capital-S line.
  - Previous `'saved 64 bytes to binary file'` (lowercase, hardcoded byte count) depended on both adapter normalization AND exact byte-count match — iceman emits variable byte counts per block combination; regex-based `\d+` handles both shapes.
- **Adapter still running iceman→legacy**:
  - Same `_normalize_save_messages` as T55xx dump (pm3_compat.py:1870/1871 for `lf em 4x05 dump` / `lf em 4x05_dump`). Lowercases `Saved` → `saved`; tolerant regex matches both.
- **Live symptom**: NONE (tolerant regex `[Ss]aved`).
- **Phase 4 action**: same as T55xx dump — remove normalizer from the EM4x05 dump entries.

### Entry: lfread.py — per-tag reader FC/CN shape mismatches (lfsearch regex coverage gap)

- **Middleware now iceman-native**:
  - `lfread.readFCCNAndRaw(cmd)` uses `lfsearch.getFCCN()` (which parses via `lfsearch._RE_FC = r'FC:\s+([xX0-9a-fA-F]+)'` and `lfsearch._RE_CN = r'(CN|Card(?:\s+No\.)?)[\s:]+(\d+)'`) + `lfsearch.REGEX_RAW`. These regexes target the DOMINANT iceman per-tag reader emissions (AWID, Pyramid, GProx-II, Securakey, Paradox — all emit `FC: %d Card: %u`).
  - **Coverage gaps (per iceman source audit during P3.5)**:
    - **Gallagher** (`cmdlfgallagher.c:88`): emits `"GALLAGHER - Region: %u Facility: %u Card No.: %u Issue Level: %u"`. Uses `Facility:` not `FC:`. `_RE_FC` MISSES. `_RE_CN` MATCHES the `Card No.` alternate. Consequence: `parseFC()` returns empty; `getFCCN()` falls back to `'FC,CN: X,0'` partial-sentinel (zero-padded CN, X placeholder FC). `readGALLAGHER()` reports truthy uid → success with garbage FC field.
    - **KERI** (`cmdlfkeri.c:176`): emits `"KERI - Internal ID: %u, Raw: %08X%08X"`. Uses `Internal ID:` not `FC:`/`Card:`. Neither `_RE_FC` nor `_RE_CN` matches. `getFCCN()` returns `'FC,CN: X,X'` sentinel. Raw-only success path — middleware reports `{'return': 1, 'data': 'FC,CN: X,X', 'raw': '<hex>'}`; UI shows placeholder FC/CN for KERI tags.
    - **NEDAP** (`cmdlfnedap.c:146`): emits `"NEDAP (%s) - ID: %05u subtype: %1u customer code: %u / 0x%03X Raw: %s"`. Uses `ID:` which is NOT in `_RE_CN` (matches `CN|Card|Card No.` only). Uses `subtype:` + `customer code:` not `FC:`. Neither regex matches; raw-only success.
    - **Presco** (`cmdlfpresco.c:114`): emits `"Presco Site code: %u User code: %u Full code: %08X Raw: %s"`. Uses `Site code:`/`User code:` not `FC:`/`Card:`. `_RE_CN` does not match `Site code` or `User code`. Raw-only success.
    - **NexWatch** (`cmdlfnexwatch.c:247`): INFO-level emission `" Raw : %08X%08X%08X"` only — no FC/CN/ID emission at non-DEBUG level. `readNexWatch()` via `readCardIdAndRaw` — `REGEX_CARD_ID` misses; `REGEX_RAW` matches. Raw-only success with empty `data`.
  - `lfread.readNexWatch()` uses `readCardIdAndRaw` — consistent with iceman's `Raw:`-only reader emission (the Card-id-bearing line is at DEBUG level only, not visible to executor cache).
- **Adapter still running iceman→legacy**: No dedicated `_normalize_*` adapter wired per-tag in pm3_compat.py for Gallagher/KERI/NEDAP/Presco/NexWatch readers (middleware runs per-tag `lf <tag> reader` commands; the generic `_RE_DOTTED_SEPARATOR` has no load-bearing effect on these shapes). However `_normalize_gallagher_fields` (`pm3_compat.py _RESPONSE_NORMALIZERS['lf sea']`) rewrites the Gallagher fields when the emission is captured via `lf search` — not triggered on direct per-tag reader path.
- **Live symptom**:
  - Tags of these types yield a truthy return (Raw: is always captured) but `data` field contains placeholder `'FC,CN: X,X'` or `'FC,CN: X,0'` instead of decoded facility/card-number. Downstream UI that expects decoded FC/CN (Scan→Simulate prepopulation, result-screen labels) will display the placeholder.
  - Not a complete failure — middleware returns success — but degraded UX on these five specific tag types. Matrix L1213 flagged the consolidated 15-row section.
- **Phase 4 action**:
  - OPTION A: Broaden `lfsearch._RE_FC` to tolerant alternation — `r'(?:FC|Facility|Site code|Internal ID|ID):\s+(\S+)'`. Risk: picks up unrelated fields on other tags (e.g., legacy `UID:` on hf cards shares `ID:` substring). Needs careful per-regex scoping to `lf sea`-only paths.
  - OPTION B: Introduce per-tag dedicated regex in `lfread.py` (e.g., `_RE_GALLAGHER_FACILITY = r'Facility:\s+(\d+)'`, etc.) and override `readFCCNAndRaw` for the five affected protocols. Preserves lfsearch scoping but breaks the "shared regex pool" elegance.
  - OPTION C: Accept placeholder FC/CN for these five tags and document in UI spec. Raw: is captured; `read` success is preserved; only the decoded fields degrade.
  - Decision deferred. Phase 4 audit should prioritise based on which tag types are actually encountered in the user-facing flows (iCopy-X v1.0.90 had no Gallagher/KERI/NEDAP/Presco/NexWatch user-facing per-tag read paths — these were reachable only via `lf search` classification path; direct per-tag read is a P3.5 addition via the `READ` dispatch table).
  - Cross-reference: matrix L1213-1237 consolidated section documents the 15-row per-tag reader dispatch. Matrix row `lf gallagher reader / clone` (L1142) flags field-level divergence — same gap.

### Entry: lfread.py — identical-both-firmwares (informational)

No live symptom but documented for Phase 4 audit cross-check:

- `lfread.read()` / `readCardIdAndRaw()` / `readFCCNAndRaw()` helpers — helper-level iceman-agnostic; all dispatch to the shared lfsearch regex pool.
- Every `lf <tag> reader` dispatch form is **iceman-canonical post command-translate wiring** (pm3_compat.py:275-277 `lf <tag> read` → `lf <tag> reader` forward; pm3_compat.py:717-720 reverse). Matrix L1223-1237 consolidated section.
- `lfread.READ` dispatch table (lfread.py L234-257, 22 tag_type IDs) is unchanged by P3.5 refactor — preserves public API for `scan.py::onScanFinish` + `lfverify.py` + `lfwrite.py::_inline_verify`.
- `readT55XX()` / `readEM4X05()` delegate to lft55xx / lfem4x05 which went through the P3.5 regex flip.

### Entry: Matrix corrections surfaced during P3.5 audit

- **Matrix L1267** — "Chip Type" (capital T) in iceman column should be "Chip type" (lowercase). Source `cmdlft55xx.c:1837` emits `" Chip type........."`. Gap log + middleware regex corrected; matrix text TODO.
- **Matrix L1032** — "Chip type....." in iceman column already noted as lowercase. Same for Serialno. Matrix v4 was correct; lfem4x05 regex now matches.
- **Matrix L1034** — `ConfigWord` is listed as FORMAT divergence. Audit reveals iceman `cmdlfem4x05.c:869-893` emits NO `ConfigWord:` at all (structural removal). Matrix should be updated STRUCTURAL from FORMAT. Middleware `_RE_CONFIG` now targets `Block0........` as semantic substitute (matches the iceman-native emission shape).
- **Matrix L1213-1237 consolidated 15-row section** — Gallagher/KERI/NEDAP/Presco/NexWatch field-label divergence from `FC:`/`Card:` baseline is not called out in the table. Phase 4 matrix reconciliation should add per-protocol rows or annotate the consolidated-section action row with the alternate field labels (`Facility:`/`Internal ID:`/`ID: subtype:`/`Site code:`/DEBUG-only-raw).

All matrix-stale rows are already correctly refactored in middleware code and gap-logged. Source of truth for Phase 4: (a) post-refactor middleware code, (b) `/tmp/rrg-pm3/client/src/cmdlf*.c`, (c) this gap log. Matrix file will be reconciled during Phase 4 close-out.

---

## P3.9+ (placeholder)

_Add entries per subsequent flow refactor. Structure: same 4-section format as P3.1/P3.2/P3.3/P3.4/P3.5/P3.6/P3.7/P3.8 entries above._

---

_This log is the authoritative list of "work Phase 4 owes to close the compat-flip transition." When Phase 4 resolves an entry, mark it RESOLVED with the reconciling commit SHA._

---

## Documentation debt (matrix vs refactor)

**Status:** Logged for Phase 4 reconciliation — non-blocking for Phase 3 progression.

P3.1, P3.2, P3.7 Challenger + Auditor reports have consistently surfaced matrix rows that are stale relative to the refactored middleware. Specifically:

- **L702 / L779 / L801** (`hf mf rdbl` / `hf mf rdsc` / `hf mf cgetblk` sections) — matrix still documents legacy alternation regexes; middleware is now iceman-native with `data:` / bracketed-key shapes.
- **L1361 / L1363** (`hf iclass calcnewkey` section) — matrix claims iceman emits colon separator; iceman source `cmdhficlass.c:5419` emits `Xor div key.... ` (4 dots). Gap log + middleware regex already corrected; matrix text not yet edited.
- **L128** (`hf 14a info` Magic capabilities) — already corrected in matrix v4 (5 dots → 3).
- **L978** (`hf search` HID Prox) — already corrected in matrix v4 (`HID Prox -` → `raw:`).

All matrix-stale rows are **already correctly refactored in the middleware code and gap-logged**. The source of truth for any Phase 4 reconciliation work is: (a) the actual middleware code; (b) the iceman source at `/tmp/rrg-pm3/client/src/`; (c) this gap log. Matrix file itself is a snapshot artefact — it will be re-synchronised as a consolidated commit during Phase 4 close-out or dropped in favour of the gap log + code comments.

**Phase 4 action:** Either rebuild the matrix from post-Phase-3 middleware + iceman source, or deprecate the matrix file and promote the gap log + per-command code citations as the single source of truth.
