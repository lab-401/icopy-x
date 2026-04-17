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

### Entry: erase.py cross-module wrbl split-brain

- **Finding**: `src/middleware/erase.py` lines 79, 288, 296, 318, 326 still use the legacy alternation pattern `'isOk:01' in wr_cache or 'Write ( ok )' in wr_cache` (and the Gen1a block-0 regex at :79 still includes `isOk:01` in the alternation group). `hfmfwrite.py` is now iceman-strict (`_KW_WRBL_SUCCESS = r'Write \( ok \)'`) after P3.3 refactor. The two modules parse the SAME `hf mf wrbl` PM3 response with DIFFERENT expectations — a split-brain state: erase still tolerates adapter-synth `isOk:01`, write does not.
- **Raised during**: P3.3 Challenger + Auditor review (cross-module consistency check).
- **Scope boundary**: erase.py is P3.4's scope (scheduled next flow refactor). No edit made during P3.3 fixer — logged here for traceability only.
- **Phase 4 action**: NONE beyond P3.4 completing. When P3.4 refactors erase.py to iceman-native, all five alternation sites (79/288/296/318/326) collapse to the iceman literal `Write ( ok )` and this entry resolves by construction.

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

## P3.4+ (placeholder)

_Add entries per subsequent flow refactor. Structure: same 4-section format as P3.1/P3.2/P3.3/P3.7/P3.8 entries above._

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
