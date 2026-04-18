# Phase 6 Command Translation Audit

Adversarial audit of the iceman→legacy PM3 translator in
`src/middleware/pm3_compat.py::_COMMAND_TRANSLATION_RULES` against factory
source (`/tmp/factory_pm3/client/src/*.c`) and the real-device trace corpus
under `docs/Real_Hardware_Intel/`.

## Summary

- Rules audited: **77**
- Clean: **65**
- Divergent: **12** (listed below, priority order)

Divergences break into three classes:

1. **Flag-rename miss** — translator left iceman flags in place where legacy
   wants positional tokens (e.g. `hf iclass wrbl` keeps `-b/-d/-k`).
2. **Wrong positional order or value** — translator swapped an arg (csetuid
   SAK↔ATQA) or appended the wrong token (t55xx `--page1` → `o 1` instead of
   `1`).
3. **Missing rule / pass-through** — iceman command emitted by middleware
   has no matching rule, so it reaches legacy verbatim and is rejected.

The two most consequential (P0) are **Rule 10 csetuid** (write-path;
swapped SAK/ATQA causes factory to reject the ATQA param) and
**Rules 24/25 hf iclass wrbl** (write-path; kept iceman `-b/-d/-k` that
factory parses `-` as unknown parameter).

## Divergences (sorted by severity: P0 = Read/Write/Erase, P1 = Scan/Auxiliary, P2 = dead or rare)

---

### Rule 10 | `hf mf csetuid` — ATQA/SAK args swapped

- **Iceman input example**: `hf mf csetuid -u 01020304 -s 08 -a 0004 -w`
- **Translator output**:    `hf mf csetuid 01020304 08 0004 w`
  (UID, SAK, ATQA, w)
- **Legacy PM3 expects**:   `hf mf csetuid <UID> <ATQA 4hex> <SAK 2hex> [w]`
  Factory usage: `cmdhfmf.c:411` — `Usage:  hf mf csetuid [h] <UID 8 hex symbols> [ATQA 4 hex symbols] [SAK 2 hex symbols] [w]`.
  Factory example `cmdhfmf.c:420`: `hf mf csetuid 01020304 0004 08 w` (ATQA before SAK).
  Handler `cmdhfmf.c:4077-4088` reads ATQA first (`param_gethex(Cmd, argi, atqa, 4)` — 4 hex digits required), then SAK (`param_gethex(Cmd, argi, sak, 2)` — 2 hex digits).
- **Failure mode**: handler tries to parse `08` as 4-hex ATQA, `param_gethex`
  returns nonzero → prints `ATQA must include 4 HEX symbols` and returns
  `PM3_ESOFT`. Gen1a UID set fails.
- **Corpus evidence**: no legacy traces of `hf mf csetuid` exist (csetuid is
  triggered by write-after-scan; pre-flip middleware used the same broken
  form, so the flow likely has always been failing silently when a Gen1a
  clone is presented).
- **Suggested fix**: `_reverse_mf_csetuid` should emit
  `hf mf csetuid {uid} {atqa} {sak}[ w]` (swap args 2 and 3).
  The parity test at `tests/test_pm3_compat_parity.py:150-153` and
  `tests/ui/test_pm3_compat.py:420-421` assert the current (wrong) order
  and will need updating.
- **Severity**: **P0** (Gen1a write path; wipe-write-verify sequence).

---

### Rules 24, 25 | `hf iclass wrbl` — keeps iceman `-b/-d/-k` flags instead of positional

- **Iceman input example**: `hf iclass wrbl --blk 6 -d 030303030003E017 -k 2020666666668888` (and `--elite` variant)
- **Translator output**:    `hf iclass wrbl -b 6 -d 030303030003E017 -k 2020666666668888 [--elite]`
- **Legacy PM3 expects**:   `hf iclass wrbl b <block> d <data> k <key> [e]`
  Factory usage: `cmdhficlass.c:192` — `Usage:  hf iclass wrbl b <block> d <data> k <key> [c|e|r|v]`.
  Handler `cmdhficlass.c:2082-2140`: switch over `tolower(param_getchar(Cmd, cmdp))`; no `-` case. When it encounters `-b`, it reads `-` → `default: PrintAndLogEx(WARNING, "unknown parameter '%c'", ...); errors = true`.
- **Corpus evidence**: same failure mode is observed for `hf iclass rdbl`
  in `trace_phase6_iclass_rdbl_regression_20260417.txt:215-216` where a
  command that *did* reach PM3 unchanged produced:
  > `unknown parameter '-'\n\nRead a iCLASS block from tag\nUsage:  hf iclass rdbl b <block> k <key> [c|e|r|v]`

  That rdbl regression is the diagnostic twin of the wrbl divergence — the
  wrbl translator output has the same shape (`-b 6 -d ... -k ...`).
- **Suggested fix**: emit positional tokens:
  `hf iclass wrbl b {blk} d {data} k {key}` and
  `hf iclass wrbl b {blk} d {data} k {key} e` for the elite variant, matching
  the existing rdbl rules (15, 16) that already do this correctly.
- **Severity**: **P0** (iCLASS write path).

---

### Rule 22 | `hf iclass calcnewkey` — leaves literal `--elite` in output

- **Iceman input example**: `hf iclass calcnewkey --old 1122334455667788 --new 2233445566778899 --elite`
- **Translator output**:    `hf iclass calcnewkey o 1122334455667788 n 2233445566778899 --elite`
- **Legacy PM3 expects**:   `hf iclass calcnewkey o <oldkey> n <newkey> [e|ee]`
  Factory usage: `cmdhficlass.c:244` — `Usage:  hf iclass calc_newkey o <old key> n <new key> s [csn] e`.
  Example `cmdhficlass.c:256`: `hf iclass calcnewkey o 1122334455667788 n 2233445566778899 e`.
  Handler `cmdhficlass.c:2803-2859`: single-char switch, no `-` case. The leading `-` in `--elite` triggers `default: "unknown parameter '-'"` + `errors = true`.
- **Corpus evidence**: no legacy traces of calcnewkey in the corpus (this
  command is rare; only runs when re-keying an iCLASS tag with a new elite
  key).
- **Suggested fix**: replacement should be
  `hf iclass calcnewkey o \1 n \2 e` (single-char `e` token instead of
  `--elite`). Note rule 23 (no `--elite`) is already correct.
- **Severity**: **P0** (iCLASS re-key path; writes derived keys to blocks
  3/4). In practice only hit in advanced write flows, but when hit,
  silently fails.

---

### Rule 50 | `lf indala clone` — duplicates raw as positional argument

- **Iceman input example**: `lf indala clone -r a0000000a0002021`
- **Translator output**:    `lf indala clone a0000000a0002021 -r a0000000a0002021`
- **Legacy PM3 expects**:   `lf indala clone -r <hex>` (CLIParser-based)
  Factory source `cmdlfindala.c:558-577`: handler uses `CLIParserInit` with
  argtable `arg_strx0("rR", "raw", "<hex>", "raw bytes")`. There is
  **no positional `<hex>` argument declared**, so a leading hex is treated
  as an unknown trailing positional. `cliparser.c:66-72` reports this via
  `arg_end` → returns `3` → command is rejected with
  `Try 'lf indala clone --help' for more information`.
- **Corpus evidence**: no legacy traces of `lf indala clone` in the corpus
  (clone paths exercised in
  `trace_lf_hf_write_autocopy_20260402.txt` but not indala specifically).
- **Suggested fix**: the factory legacy `lf indala clone` already accepts
  `-r <hex>` natively (CLIParser-based, same spelling as iceman). The rule
  is unnecessary — remove rule 50 entirely (helper `_reverse_indala_clone`
  plus its regex entry). Let the command pass through.
- **Severity**: **P0** (LF indala clone write path).

---

### Rule 42 | `lf t55xx read --page1` — silently enables `override` safety flag

- **Iceman input example**: `lf t55xx read -b 0 -p 20206666 --page1`
- **Translator output**:    `lf t55xx read b 0 p 20206666 o 1`
- **Legacy PM3 expects**:   `lf t55xx read b 0 p 20206666 1`
  Factory handler `cmdlft55xx.c:896-931` parses `o` as a **no-arg safety
  override** (line 904: `override = 1`), and `1` as a separate no-arg
  page-1 flag (line 913: `page1 = true`). These are unrelated flags.
  Factory usage `cmdlft55xx.c:107-108`:
  > `o            - OPTIONAL override safety check`
  > `1            - OPTIONAL 0|1  read Page 1 instead of Page 0`

  and the warning block `cmdlft55xx.c:110-113`:
  > `**** WARNING ****`
  > `Use of read with password on a tag not configured`
  > `for a password can damage the tag`
- **Corpus evidence**: `trace_t55_to_t55_write_trace_20260328.txt:51-57`
  shows legacy pre-flip middleware emitting `lf t55xx read b 0 1`,
  `lf t55xx read b 1 1`, etc. — just the trailing `1` with no `o`:
  > `[  63.682] PM3> lf t55xx read b 0 1`
  > `[  63.963] PM3> lf t55xx read b 1 1`
  That's ground truth for legacy page-1 reads.
- **Suggested fix**: `_reverse_t55xx_read_page1` should return
  `lf t55xx read b {blk} p {key} 1` (drop the `o`). Iceman `--page1`
  does not imply safety-override; translator should not enable it.
- **Severity**: **P0** (read path; silent behavioural divergence — may
  damage tags per factory warning).

---

### Rule 17 | `hf iclass chk --vb6kdf` — strips to bare command → usage-error

- **Iceman input example**: `hf iclass chk --vb6kdf`
- **Translator output**:    `hf iclass chk`
- **Legacy PM3 expects**:   `hf iclass chk f <dict.dic> [e]` (legacy has no
  built-in VB6 elite KDF).
  Factory handler `cmdhficlass.c:3041-3044`:
  ```
  if (strlen(Cmd) == 0) return usage_hf_iclass_chk();
  ```
  With the flag stripped and nothing appended, `strlen(Cmd) == 0` → usage
  printed, no key check run.
- **Corpus evidence**: `trace_phase6_iclass_rdbl_regression_20260417.txt:219-220`
  captures this exact failure path on-device:
  > `[ 575.416] PM3> hf iclass chk --vb6kdf (timeout=30000)`
  > `PM3< ret=1 ... unknown parameter '-' ... Usage: hf iclass chk [h|e|r] [f  (*.dic)]`

  (That trace shows the untranslated form reaching PM3; a working
  translator would strip `--vb6kdf` but legacy would still emit usage
  because no dictionary file was provided.)
- **Suggested fix**: VB6 elite KDF is an iceman-only built-in keyset;
  legacy needs a dictionary file on disk. Options:
  - Rewrite to `hf iclass chk f /tmp/iclass_default_keys.dic e` provided
    the middleware stages that file before the call.
  - Or fall back to `hf iclass rdbl` brute-force probing (which the
    middleware already does via `chkKeys_1`/`chkKeys_2` — the `--vb6kdf`
    call is a *fallback* after those miss, so silent no-op is arguably
    acceptable as long as the upstream `chkKeys` returns `None`).
- **Severity**: **P1** (iCLASS elite key search fallback; upstream
  `chkKeys_1/2` usually succeed first).

---

### MISSING RULE | `hf iclass chk -f <file>` — pass-through unchanged

- **Iceman input example**: `hf iclass chk -f /tmp/iclass_keys.dic`
- **Translator output** (pass-through): `hf iclass chk -f /tmp/iclass_keys.dic`
- **Legacy PM3 expects**: `hf iclass chk f <file>` (positional).
  Factory handler `cmdhficlass.c:3064-3092`: single-char switch, no `-`
  case. Leading `-` triggers `default: "unknown parameter '-'"` → `errors = true`.
- **Corpus evidence**: `hficlass.py:57` defines
  `_CMD_CHK = 'hf iclass chk -f '` and emits this string when the caller
  supplies a dictionary path. With no matching rule the command is sent
  verbatim to legacy.
- **Suggested fix**: add rule
  `(re.compile(r'^hf iclass chk\s+-f\s+(\S+)$'), r'hf iclass chk f \1')`.
  Consider also `hf iclass chk -f <file> --elite` → `hf iclass chk f <file> e`.
- **Severity**: **P1** (iCLASS file-based key check path).

---

### Rule 55-59 | `hf <proto> list` rewrites — redundant dead code

- **Iceman input**: `hf mf list` / `hf 14a list` / `hf 14b list` /
  `hf iclass list` / `hf topaz list`
- **Translator output**: `hf list mf` / `hf list 14a` / etc.
- **Legacy PM3 already accepts** the iceman-style `hf <proto> list`:
  - `cmdhf14a.c:1430  {"list", CmdHF14AList, ...}` calls `CmdTraceList("14a")` at `:273`.
  - `cmdhf14b.c:1089  {"list", CmdHF14BList, ...}` calls `CmdTraceList("14b")` at `:170`.
  - `cmdhficlass.c:3560 {"list", CmdHFiClassList, ...}` calls `CmdTraceList("iclass")` at `:635`.
  - `cmdhftopaz.c:493 {"list", CmdHFTopazList, ...}`.
  - `cmdhfmf.c:5251 {"list", CmdHF14AMfList, ...}` calls `CmdTraceList("mf")` at `:5184`.
  So the translation is functionally identical. `hf list <proto>` is the
  aggregate form registered in `cmdhf.c:372`.
- **Suggested fix**: remove rules 55–59 (dead code, runs on every
  `hf * list` command). Not harmful, but also not needed.
- **Severity**: **P2** (dead code).

---

### MISSING RULES | sim commands for protocols with CLI-flag iceman form

- **Iceman inputs** (middleware doesn't currently emit these, but they
  appear in the iceman client's argtables):
  - `lf pac sim --cn <id>`
  - `lf keri sim --cn <id>`
  - `lf visa2000 sim --cn <id>`
  - `lf presco sim -d <id>`
  - `lf paradox sim --raw <hex>`
  - `lf noralsy sim --cn <id>`
  - `lf securakey sim --raw <hex>`
  - `lf gallagher sim --raw <hex>`
- **Translator output**: pass-through (no rule matches).
- **Legacy PM3 expects** (positional): see `cmdlfpac.c:34`, `cmdlfkeri.c:34`,
  `cmdlfvisa2000.c:49`, `cmdlfpresco.c:33`, `cmdlfparadox.c:34`,
  `cmdlfnoralsy.c:46`, `cmdlfsecurakey.c:31`, `cmdlfgallagher.c:33`.
- **Corpus evidence**: none — middleware currently doesn't call these sim
  commands. Flagging for completeness since `reader` cousins are already
  rewritten in rule 31 (18-protocol regex).
- **Suggested fix**: only add rules if/when middleware starts emitting them.
- **Severity**: **P2** (dead code / future-proofing).

---

## Clean rules (one-line per rule for confidence)

- Rule 0 `data save -f` → `data save f` ✓ (`cmddata.c:43` + trace
  `trace_lf_scan_flow_20260331.txt:63`: `data save f /tmp/lf_trace_tmp`).
- Rule 1 `hf mf cgetblk --blk` → positional ✓ (`cmdhfmf.c:456`, trace
  `trace_autocopy_scan_dumps_20260410.txt:50`: `hf mf cgetblk 0`).
- Rule 2 `hf mf rdbl --blk -a/-b -k` → positional ✓ (`cmdhfmf.c:731`).
- Rule 3 `hf mf rdsc -s -a/-b -k` → positional ✓ (`cmdhfmf.c:789`).
- Rule 4 `hf mf fchk --size -f` → `hf mf fchk N f` ✓ (`cmdhfmf.c:250`,
  `cmdhfmf.c:2762-2777`; trace `autocopy_mf4k_mf1k7b_t55_trace_20260329.txt:11`:
  `hf mf fchk 4 /tmp/.keys/mf_tmp_keys`).
- Rule 5 `hf mf nested --size --blk -a/-b -k --tblk --ta/--tb` → `nested o …` ✓
  (`cmdhfmf.c:120-121`, handler `cmdhfmf.c:1318-1360`; the archetype
  bug the user pointed to, now emits `o` prefix with one-sector form).
- Rule 6 `hf mfu dump -f` → `hf mfu dump f` ✓ (`cmdhfmfu.c:69`).
- Rule 7 `hf mf wrbl --blk -a/-b -k -d --force` → positional ✓
  (`cmdhfmf.c:678`; trace `trace_original_full_20260410.txt:25`:
  `hf mf wrbl 60 A 000000000000 <32hex>`).
- Rule 8 `hf 14a raw … -k …` → `-p` flag rename ✓ (iceman `-k` =
  keep-field, factory `-p` = same semantics per `cmdhf14a.c:253`
  and iceman `rrg-pm3/cmdhf14a.c:1670`).
- Rule 9 `hf mf cload -f` → `hf mf cload b` ✓ (`cmdhfmf.c:441-450` +
  `cmdhfmf.c:4204`; trace `trace_lf_hf_write_autocopy_20260402.txt:102`:
  `hf mf cload b /mnt/upan/dump/mf1/M1-1K-4B_567F2F19_1.bin`).
- Rule 11 `hf mfu restore -s -e -f` → positional ✓ (`cmdhfmfu.c:88`,
  handler `cmdhfmfu.c:2143-2192`).
- Rule 12 `lf t55xx wipe -p` → `wipe p` ✓ (`cmdlft55xx.c:310`; trace
  `trace_original_write_newtag_20260410.txt:18`: `lf t55xx wipe p 20206666`).
- Rule 13 `lf t55xx detect -p` → `detect p` ✓ (`cmdlft55xx.c:212`; trace
  `trace_original_backlight_volume_20260410.txt:56`: `lf t55xx detect p 20206666`).
- Rule 14 `lf t55xx chk -f` → `chk f` ✓ (`cmdlft55xx.c:257`,
  `cmdlft55xx.c:3023-3030`; trace `trace_original_backlight_volume_20260410.txt:58`:
  `lf t55xx chk f /tmp/.keys/t5577_tmp_keys`).
- Rule 15 `hf iclass rdbl --blk -k --elite` → `hf iclass rdbl b k e` ✓
  (`cmdhficlass.c:211`; corpus `trace_iclass_elite_read_20260401.txt:48`:
  `hf iclass rdbl b 01 k 2020666666668888 e`).
- Rule 16 `hf iclass rdbl --blk -k` → `hf iclass rdbl b k` ✓ (corpus
  `trace_iclass_scan_20260331.txt:12`: `hf iclass rdbl b 01 k AFA785A7DAB33378`).
- Rule 18 `hf iclass dump -k -f --elite` → positional ✓ (`cmdhficlass.c:153`,
  corpus `trace_iclass_elite_read_20260401.txt:53`:
  `hf iclass dump k 2020666666668888 f /mnt/upan/dump/iclass/... e`).
- Rule 19 `hf iclass dump -k -f` → positional ✓ (handler `cmdhficlass.c:1696-1763`).
- Rule 20 `hf iclass dump -k --elite` → positional ✓.
- Rule 21 `hf iclass dump -k` → `hf iclass dump k` ✓.
- Rule 23 `hf iclass calcnewkey --old --new` (no elite) → `calcnewkey o n` ✓.
- Rule 26 `hf 15 dump -f` → `hf 15 dump f` ✓ (`cmdhf15.c:289`).
- Rule 27 `hf 15 restore -f` → `hf 15 restore f` ✓ (`cmdhf15.c:309`).
- Rule 28 `hf 15 csetuid -u` → `hf 15 csetuid <uid>` ✓ (`cmdhf15.c:364`).
- Rule 29 `lf em 410x reader` → `lf em 410x_read` ✓ (`cmdlfem4x.c:1381`).
- Rule 30 `lf fdxb reader` → `lf fdx read` ✓ (namespace change; `cmdlffdx.c:566`).
- Rule 31 18-protocol `<proto> reader` → `<proto> read` ✓ (all 18 protocols
  register `read`; corpus `trace_lf_hf_write_autocopy_20260402.txt:7`:
  `lf awid read`).
- Rule 32 `lf em 4x05 info -p` → `lf em 4x05_info <pwd>` ✓ (`cmdlfem4x.c:178`).
- Rule 33 `lf em 4x05 info` → `lf em 4x05_info` ✓.
- Rule 34 `lf em 4x05 read -a -p` → `lf em 4x05_read <blk> <pwd>` ✓
  (`cmdlfem4x.c:151`).
- Rule 35 `lf em 4x05 read -a` → `lf em 4x05_read <blk>` ✓.
- Rule 36 `lf em 4x05 dump -f` → `lf em 4x05_dump f <file>` ✓
  (`cmdlfem4x.c:123`).
- Rule 37 `lf em 4x05 dump` → `lf em 4x05_dump` ✓.
- Rule 38 `lf em 4x05 write -a -d -p` → `lf em 4x05_write <blk> <data> <pwd>` ✓
  (`cmdlfem4x.c:164`).
- Rule 39 `lf em 4x05 write -a -d` → `lf em 4x05_write <blk> <data>` ✓.
- Rule 40 `lf t55xx dump -f -p` → `lf t55xx dump f p` ✓ (`cmdlft55xx.c:184`,
  handler `cmdlft55xx.c:2289-2319`).
- Rule 41 `lf t55xx dump -f` → `lf t55xx dump f` ✓.
- Rule 43 `lf t55xx read -b -p` → `lf t55xx read b p` ✓ (handler
  `cmdlft55xx.c:896-931`).
- Rule 44 `lf t55xx read -b` → `lf t55xx read b` ✓ (trace
  `t55_to_t55_write_trace_20260328.txt:11`: `lf t55xx read b 0`).
- Rule 45 `lf t55xx write -b -d -p` → positional ✓ (trace
  `trace_original_write_newtag_20260410.txt:26`: `lf t55xx write b 7 d 20206666`).
- Rule 46 `lf t55xx write -b -d` → positional ✓.
- Rule 47 `lf t55xx restore -f` → `lf t55xx restore f` ✓ (`cmdlft55xx.c:198`,
  handler `cmdlft55xx.c:2382-2401`).
- Rule 48 `lf em 410x clone --id` → `lf em 410x_write <id> 1` ✓
  (`cmdlfem4x.c:69`).
- Rule 49 `lf hid clone -r` → `lf hid clone <raw>` ✓ (`cmdlfhid.c:73`,
  handler `cmdlfhid.c:330-363`).
- Rule 51 `lf fdxb clone --country --national` → `lf fdx clone c n` ✓
  (`cmdlffdx.c:53`; handler uses `case 'n'` at `cmdlffdx.c:411` despite
  usage string saying `a <national>`; trace
  `autocopy_mf4k_mf1k7b_t55_trace_20260329.txt:725`: `lf fdx clone c 0060 n 030207938416`).
- Rule 52 securakey/gallagher/pac/paradox `clone -r` → `clone b <raw>` ✓
  (`cmdlfsecurakey.c:31`, `cmdlfgallagher.c:33`, `cmdlfpac.c:34`,
  `cmdlfparadox.c:34`).
- Rule 53 `lf nexwatch clone -r` → `lf nexwatch clone r <raw>` ✓
  (`cmdlfnexwatch.c:39`).
- Rule 54 `lf config -a -t -s` → positional `a t s` ✓ (`cmdlf.c:144`).
- Rule 60 `hf 14a sim -t --uid|-u` → `hf 14a sim t u` ✓ (`cmdhf14a.c:213`).
- Rule 61 `hf mf csave --1k -f` → `hf mf csave 1 o <file>` ✓
  (`cmdhfmf.c:479-484`; trace `mf4k_read_trace_20260328.txt:28`:
  `hf mf csave 4 o /mnt/upan/dump/mf1/M1-4K-4B_E9784E21_2`).
- Rule 62 `hf mf csave --4k -f` → `hf mf csave 4 o <file>` ✓.
- Rule 63 `hf mf csave --mini -f` → `hf mf csave 0 o <file>` ✓.
- Rule 64 `hf mf csave --2k -f` → `hf mf csave 2 o <file>` ✓.
- Rule 65 `lf em 410x sim --id` → `lf em 410x_sim <id>` ✓ (`cmdlfem4x.c:92`).
- Rule 66 `lf em 410x watch` → `lf em 410x_watch` ✓ (`cmdlfem4x.c:59`).
- Rule 67 `lf hid sim -r` → `lf hid sim <raw>` ✓ (`cmdlfhid.c:61`).
- Rule 68 `lf awid sim --fmt --fc --cn` → 3 positional ✓ (`cmdlfawid.c:49`).
- Rule 69 `lf io sim --vn --fc --cn` → 3 positional ✓ (`cmdlfio.c:48`).
- Rule 70 `lf gproxii sim --xor --fmt --fc --cn` → 3 positional (drops xor) ✓
  (`cmdlfguard.c:52`; factory namespace is `gproxii` not `gprox` per
  `cmdlf.c:1531`).
- Rule 71 `lf viking sim --cn` → positional ✓ (`cmdlfviking.c:47`).
- Rule 72 `lf pyramid sim --fc --cn` → 2 positional ✓ (`cmdlfpyramid.c:56`).
- Rule 73 `lf jablotron sim --cn` → positional ✓ (`cmdlfjablotron.c:50`).
- Rule 74 `lf nedap sim --st --cc --id` → `s c i` positional ✓
  (`cmdlfnedap.c:74`).
- Rule 75 `lf fdxb sim --country --national --animal` → `lf fdx sim c n s` ✓
  (`cmdlffdx.c:83`).
- Rule 76 `lf fdxb sim --country --national --extended` → `lf fdx sim c n e <hex>` ✓.

## Notes on methodology

- **Enumeration**: dumped `_COMMAND_TRANSLATION_RULES` via a stub-import
  Python script to get all 77 rules, then drove each through `translate()`
  with a concrete input to observe the actual output (not just re-read the
  regex). That caught the bugs that hide in helper functions and
  multi-stage replacements.
- **Factory source cross-reference**: for every rule, located the
  `usage_*` text in `/tmp/factory_pm3/client/src/cmdhfmf.c`,
  `cmdhficlass.c`, `cmdlft55xx.c`, etc., and — where the usage string was
  ambiguous or misleading — read the actual command handler to confirm
  which single-char tokens the legacy parser accepts. For example
  `cmdlffdx.c:53` advertises `a <national>` but `cmdlffdx.c:411` parses
  `case 'n'` — the handler wins.
- **Corpus evidence**: restricted to legacy traces only (excluded
  `iceman*` filenames and `20260412+` captures per the audit charter).
  Strong evidence for: `hf mf wrbl`, `hf mf fchk`, `hf mf cload`,
  `hf mf csave`, `hf iclass rdbl`, `hf iclass dump`, `lf t55xx read/write/
  detect/wipe/chk`, `lf fdx clone`, `lf awid read`, `data save`. Absent
  from legacy corpus (but reasoned from factory source + iceman source):
  `hf mf csetuid`, `hf mf nested o`, `hf iclass wrbl`, `hf iclass calcnewkey`,
  `lf indala clone`, LF sim commands, `hf 14a sim`. These are the
  write-side paths that the current (broken) translator has never
  exercised successfully on real legacy hardware; the translator errors
  likely present as "write failed" in the UI.
- **Ambiguous cases** I couldn't confirm with corpus alone:
  - Rule 17 (`hf iclass chk --vb6kdf`): the translator's current "strip
    the flag" behavior has no legacy-trace equivalent because legacy
    never had a VB6 built-in dictionary. Left as P1 pending a product
    decision on whether to synthesize a `f <default_dict>.dic e` form
    or let the upstream key-probing flow handle the no-op silently.
  - Rule 50 (`lf indala clone`): factory uses `CLIParser` which by default
    rejects unknown positional args. Verified via `cliparser.c:66-72`
    (`nerrors > 0` returns `3`) but did not run an end-to-end experiment
    to see if an obscure fallback in `arg_parse_rest` accepts leading
    extra args. The clean fix is to remove the rule (iceman and legacy
    indala clone speak the same `-r` dialect).
