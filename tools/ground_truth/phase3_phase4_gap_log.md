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

## P3.2+ (placeholder)

_Add entries per subsequent flow refactor. Structure: same 4-section format as P3.1 entries above._

---

_This log is the authoritative list of "work Phase 4 owes to close the compat-flip transition." When Phase 4 resolves an entry, mark it RESOLVED with the reconciling commit SHA._
