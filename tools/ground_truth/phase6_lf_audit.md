# Phase 6 LF Protocol Audit (Device-Binary Ground Truth)

Auditor: focused read-only audit, 2026-04-17.

Authoritative sources used:
- `/tmp/icopyx-community-pm3/client/src/` — iCopy-X Community fork (device PM3)
- `/tmp/pm3_strings.txt` — `strings(1)` of the on-device `/home/pi/ipk_app_main/pm3/proxmark3`
- `/tmp/rrg-pm3/client/src/` — iceman master (what middleware currently targets)

Middleware sources audited:
- `/home/qx/icopy-x-reimpl/src/middleware/lfread.py`
- `/home/qx/icopy-x-reimpl/src/middleware/lfwrite.py`
- `/home/qx/icopy-x-reimpl/src/middleware/lfsearch.py`
- `/home/qx/icopy-x-reimpl/src/middleware/pm3_compat.py`
- `/home/qx/icopy-x-reimpl/src/middleware/pm3_flash.py`

---

## Summary

- LF protocols audited: 22 (readers in `lfread.py` + writers in `lfwrite.py`)
- Clean (no divergence): 1 (Indala clone, CLIParser-native)
- Command divergences: 21 readers + 15 writers (see root-cause gate below)
- Response divergences: 3 (EM410x read, HID read, FDX read — all gated on legacy path and never fire on this device)

### Root-cause gate (affects EVERY subsequent finding)

**The translation layer in `pm3_compat.py` never fires on this device.**

- `pm3_compat.py:262-581` defines `_COMMAND_TRANSLATION_RULES` including the 19 reverse rules for `lf <proto> reader -> lf <proto> read`, `lf em 410x clone --id X -> lf em 410x_write X 1`, `lf t55xx write -b -d -> b d`, `-f -> f`, `-r` drops, `lf fdxb -> lf fdx`, etc.
- `pm3_compat.py:697-731` (`translate()`) gates those rules on `_current_version == PM3_VERSION_ORIGINAL`.
- `pm3_compat.py:1346-1366` (`translate_response()`) and the `_RESPONSE_NORMALIZERS` registry at `pm3_compat.py:1311-1313` gate all response normalizers on the same flag.
- `pm3_compat.py:624-632` sets `_current_version = PM3_VERSION_ORIGINAL` **only** when `hw version` parses a non-empty `NIKOLA:` line; otherwise `_current_version = PM3_VERSION_ICEMAN`.
- The regex at `pm3_flash.py:137` (`NIKOLA:\s*(.+)`) looks for an uppercase `NIKOLA:` marker. `pm3_version()` in the community fork (`cmdhw.c:706-800`) emits only lowercase `  client:` and compiler/host lines — no `NIKOLA:`, no `bootrom:` line. Device strings confirm: `grep -n "NIKOLA" /tmp/pm3_strings.txt` returns zero matches; only the unrelated CLI print `Nikola.D: %d` (from `proxmark3.c:417`) which is not part of `hw version`'s handler output.
- Net effect: on this device `_current_version == PM3_VERSION_ICEMAN`; `translate()` becomes pass-through at `pm3_compat.py:711`; `translate_response()` short-circuits at `pm3_compat.py:1349`.

**Result**: every middleware emission goes verbatim to a community-fork PM3 whose CommandTables and response strings are the legacy (classic) shape, not iceman. The rules are correctly written but never activated.

### Top 3 highest-severity divergences

1. **All 19 per-tag LF readers send an unknown subcommand.** `lfread.py` L218-315 emits `lf <proto> reader`; community fork CommandTables register `"read"` only (e.g. `cmdlfhid.c:547`, `cmdlfawid.c:535`, `cmdlfviking.c:175`, ... every `cmdlf*.c` except `cmdlfhitag.c:798` which does keep `reader`). PM3 prints `Unknown parameter` / help.
2. **EM410x read/write namespace is underscore-joined, not space-split.** `lfread.py:218` sends `lf em 410x reader`; `lfwrite.py:185` sends `lf em 410x clone --id <hex>`. Community registers only `410x_read` / `410x_write` as subcommands of `lf em` (`cmdlfem4x.c:1381`, `:1386`) and `410x_write` takes positional `<id> <card> [clock]` (`cmdlfem4x.c:594-651`), not `--id`.
3. **T55xx / EM4x05 flag-style commands are rejected by the legacy bare-char parser.** `lfwrite.py:288/310/377/521/533` emit `-b N`, `-d HEX`, `-f FILE`, `-p PWD`, `-a N`. Community fork `CmdT55xxWriteBlock` (`cmdlft55xx.c:1685-1732`), `CmdT55xxRestore` (`cmdlft55xx.c:2382-2401`) and `CmdEM4x05*` handlers use `while (param_getchar...)` + `switch(tolower(...))` on single characters; a leading `-` hits the default case and the command aborts with `Unknown parameter '-'`.

### Report path

`tools/ground_truth/phase6_lf_audit.md` (this file).

---

## Shared facts (apply to every per-protocol entry below)

- Middleware translation toggle: `pm3_compat.py:88 LEGACY_COMPAT = True`. Does NOT help because version is misdetected (see root-cause gate).
- Per-tag demod "Valid XXX ID" keyword strings are only emitted by `lf search` itself (`cmdlf.c:1448-1468`), not by per-tag `read`. `lfsearch.py:435-662` relies on them; `lfread.py` does not (uses regex-only extraction). Per-tag readers therefore don't fail on keyword gating.
- Every community-fork per-tag `read` handler is simply `lf_read(...)` + `demod*()`; the demod emits the `... Raw: <hex>` line that middleware REGEX_RAW (`lfsearch.py:122`) parses. So **response shapes for per-tag reads match iceman on most protocols** — the break is on the command spelling (send side), not parsing, except for HID, EM410x, and FDX.

---

## Per-protocol findings

### em410x

- **Command emitted by middleware** — `lfread.py:218` `'lf em 410x reader'`
- **Translation rule** — `pm3_compat.py:415` `'lf em 410x reader' -> 'lf em 410x_read'`
- **Device accepts** — `lf em 410x_read` per `cmdlfem4x.c:1381`; device strings `/tmp/pm3_strings.txt` line containing `410x_read` confirms presence.
- **Verdict**: missing translation (rule exists but gated off by version detection; see root-cause gate).

- **Reader response (device legacy)** — `cmdlfem4x.c:266-269`:
  - 64-bit form: `\nEM TAG ID      : <10-hex>`
  - 128-bit form: `\nEM TAG ID      : <6-hex><16-hex>`
- **Middleware regex expected** — `lfsearch.py:94` `REGEX_EM410X = r'EM 410x(?:\s+XL)?\s+ID\s+([0-9A-Fa-f]+)'`
- **Normalizer in place** — `pm3_compat.py:919-946` `_normalize_em410x_id` rewrites `EM TAG ID    : <hex>` -> `EM 410x ID <hex>`, registered at `pm3_compat.py:1311-1312` for both `lf em 410x reader` and `lf em 410x_read`. **However, also gated on legacy path**, so it never fires here.
- **Verdict**: shape mismatch + normalizer present-but-gated.

- **Clone command middleware emits** — `lfwrite.py:185` `'lf em 410x clone --id <hex>'`
- **Device accepts** — `lf em 410x_write <id-hex> <card-type> [<clock>]` per `cmdlfem4x.c:594-651` (positional, no `--id`).
- **Translation rule** — `pm3_compat.py:484` `'lf em 410x clone --id X' -> 'lf em 410x_write X 1'` (exists but gated off).
- **Verdict**: wrong (translation gated off).

### hid

- **Command emitted** — `lfread.py:223` `'lf hid reader'`
- **Device accepts** — `lf hid read` per `cmdlfhid.c:547` (no `reader`).
- **Translation rule** — `pm3_compat.py:421-423` `lf hid reader -> lf hid read` (gated off).
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfhid.c:202`: `HID Prox - <hex>%08x%08x (<dec>)` (single emission via `demodHID()`). No `raw:` line.
- **Middleware regex expected** — `lfsearch.py:102` `REGEX_HID = r'raw:\s+([0-9A-Fa-f]+)'`
- **Normalizer in place** — `pm3_compat.py:994-1001` `_normalize_hid_prox` appends `raw: <hex>` line from the legacy `HID Prox - <hex> (<dec>)` match; registered at `pm3_compat.py:1299-1300` for `lf hid reader` and `lf hid read`. Gated off.
- **Verdict**: shape mismatch (normalizer exists, gated off).

- **Clone command** — `lfwrite.py:201` `'lf hid clone -r <hex>'`
- **Device accepts** — `lf hid clone <hex>` (optional `l` prefix for long ID) per `cmdlfhid.c:330-362`. First token is the ID itself; a leading `-` char triggers `sscanf("%1x")` failure / treats `-` as hex fail.
- **Translation rule** — `pm3_compat.py:487` `lf hid clone -r X -> lf hid clone X` (gated off).
- **Verdict**: wrong (gated off).

### indala

- **Command emitted** — `lfread.py:228` `'lf indala reader'`
- **Device accepts** — `lf indala read` per `cmdlfindala.c:679` (bare-char parser inside `CmdIndalaRead`).
- **Translation rule** — `pm3_compat.py:421-423` (gated off).
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfindala.c:198` `Indala - len %zu, Raw: %x%08x`. REGEX_RAW matches `, Raw:` natively.
- **Verdict**: clean on response side (once the command is translated).

- **Clone command** — `lfwrite.py:216` `'lf indala clone -r <hex>'`
- **Device accepts** — `lf indala clone ...` uses CLIParser (`cmdlfindala.c:558-598`) with `arg_strx0("rR", "raw", ...)`. `-r <hex>` is native.
- **Verdict**: clean.

### awid

- **Command emitted** — `lfread.py:233` `readFCCNAndRaw('lf awid reader')`
- **Device accepts** — `lf awid read` per `cmdlfawid.c:535`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfawid.c:293/300/307/316` emits `AWID - len: %d FC: %d Card: %u - Wiegand: %x, Raw: %08x%08x%08x`. _RE_FC (`lfsearch.py:131`) matches `FC: %d`; _RE_CN (`lfsearch.py:158`) matches `Card: %u`; REGEX_RAW matches `, Raw: ...`.
- **Verdict**: clean on response side (once command is translated).

- **Clone command** — N/A in `lfwrite.py` (AWID is in `B0_WRITE_MAP` at `lfwrite.py:138` with block0 `00107060`; `write_raw()` path emits `lf t55xx write -b N -d HEX` sequence). See t55xx section below.
- **Verdict**: AWID's clone path delegates to t55xx — see t55xx divergences.

### io (ProxIO)

- **Command emitted** — `lfread.py:237` `readCardIdAndRaw('lf io reader')`
- **Device accepts** — `lf io read` per `cmdlfio.c:296`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfio.c:181` `IO Prox - XSF(%02d)%02x:%05d, Raw: %08x%08x %s`. REGEX_PROX_ID_XSF + REGEX_RAW match natively.
- **Verdict**: clean on response side.

- **Clone command** — N/A (IO in `B0_WRITE_MAP` at `lfwrite.py:140` with `00147040`). t55xx delegation.

### gproxii

- **Command emitted** — `lfread.py:241` `readFCCNAndRaw('lf gproxii reader')`
- **Device accepts** — `lf gproxii read` per `cmdlfguard.c:248`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfguard.c:146/148` `G-Prox-II - len: %u FC: %u Card: %u, Raw: %08x%08x%08x`. FC/Card/Raw all match.
- **Verdict**: clean on response side.

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:143` with `00150060`). t55xx delegation.

### securakey

- **Command emitted** — `lfread.py:245` `readFCCNAndRaw('lf securakey reader')`
- **Device accepts** — `lf securakey read` per `cmdlfsecurakey.c:189`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfsecurakey.c:121` `Securakey - len: %u FC: 0x%X Card: %u, Raw: %08X%08X%08X`. FC (hex `0x<hex>`), Card (dec), Raw all match.
- **Verdict**: clean on response side.

- **Clone command** — `lfwrite.py:160` (RAW_CLONE_MAP) `'lf securakey clone -r <hex>'`
- **Device accepts** — `lf securakey clone b <hex>` per `cmdlfsecurakey.c:143-167` (bare-char `b`, no `-r` / `--raw`).
- **Translation rule** — `pm3_compat.py:501-502` `(securakey|gallagher|pac|paradox) clone -r X -> X clone b X` (gated off).
- **Verdict**: wrong (gated off).

### viking

- **Command emitted** — `lfread.py:249` `readCardIdAndRaw('lf viking reader')`
- **Device accepts** — `lf viking read` per `cmdlfviking.c:175`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfviking.c:80` `Viking - Card %08X, Raw: %08X%08X`. "Card" followed by space + 8-hex. `REGEX_CARD_ID = r'(?:Card|ID|UID)[\s:]+([xX0-9a-fA-F ]+)'` matches "Card " with space; REGEX_RAW matches `, Raw: ...`.
- **Verdict**: clean on response side.

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:133` with `00088040`). t55xx delegation. Community Viking clone (`cmdlfviking.c:93-131`) takes positional `<id-hex> [q]`.

### pyramid

- **Command emitted** — `lfread.py:253` `readFCCNAndRaw('lf pyramid reader')`
- **Device accepts** — `lf pyramid read` per `cmdlfpyramid.c:311`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfpyramid.c:184` `Pyramid - len: %d, FC: %d Card: %d - Wiegand: %x, Raw: ...`. FC/Card/Raw all match.
- **Verdict**: clean on response side.

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:139` with `00107080`). Community Pyramid clone (`cmdlfpyramid.c:221-226`) takes positional `<fc> <cn>`.

### fdxb / fdx

- **Command emitted** — `lfread.py:274` `'lf fdxb reader'`
- **Device accepts** — **`lf fdx read`** (note: namespace is `fdx`, not `fdxb`). `cmdlf.c:1529` dispatches `fdx`; `cmdlffdx.c:566` registers `read`.
- **Translation rule** — `pm3_compat.py:418` `'lf fdxb reader' -> 'lf fdx read'` (gated off).
- **Verdict**: missing translation, namespace mismatch (gated off).

- **Reader response** — `cmdlffdx.c:200`: `Animal ID:     %04u-%012u` (colon + spaces) in `demodFDX`, and `cmdlffdx.c:282/286`: `Animal ID          %04u-%012u` (10 spaces, no colon, no dots) in the verbose path.
- **Middleware regex expected** — `lfsearch.py:83` `REGEX_ANIMAL = r'Animal ID\.+\s+([0-9\-]+)'` (requires literal dots).
- **Normalizer in place** — `pm3_compat.py:961-969` `_normalize_fdxb_animal_id` rewrites both colon and space-padded forms to dotted. Registered **only** at `pm3_compat.py:1292-1295` for `lf sea` / `lf search`, **not** for `lf fdxb reader` / `lf fdx read`. Additionally gated on legacy path.
- **Verdict**: shape mismatch; normalizer exists but not registered for per-tag FDX read.

- **Clone command** — `lfwrite.py:238` `'lf fdxb clone --country X --national Y'`
- **Device accepts** — `lf fdx clone c <country-dec> n <national-dec> [s] [e <hex>] [q]` per `cmdlffdx.c:395-439` (bare-char).
- **Translation rule** — `pm3_compat.py:497-498` `'lf fdxb clone --country X --national Y' -> 'lf fdx clone c X n Y'` (gated off).
- **Verdict**: wrong — both namespace (`fdxb` vs `fdx`) and flag form (`--country` vs `c`).

### gallagher

- **Command emitted** — `lfread.py:279` `readFCCNAndRaw('lf gallagher reader')`
- **Device accepts** — `lf gallagher read` per `cmdlfgallagher.c:196`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfgallagher.c:130` `GALLAGHER - Region: %u FC: %u CN: %u Issue Level: %u`. **No `Raw:` line**. FC matches via _RE_FC; "CN: %u" matches _RE_CN via the `CN` alternate.
- **Middleware regex expected** — REGEX_RAW will find nothing; FC/CN captured. `readFCCNAndRaw` success condition is `fc or cn or raw` (`lfread.py:207`), so FC+CN capture alone succeeds.
- **Verdict**: clean on response side (raw field absent but not required for success).

- **Clone command** — `lfwrite.py:161` `'lf gallagher clone -r <hex>'`
- **Device accepts** — `lf gallagher clone b <hex>` per `cmdlfgallagher.c:142-171` (bare-char `b`, no `-r`).
- **Translation rule** — `pm3_compat.py:501-502` (gated off).
- **Verdict**: wrong (gated off).

### jablotron

- **Command emitted** — `lfread.py:283` `readCardIdAndRaw('lf jablotron reader')`
- **Device accepts** — `lf jablotron read` per `cmdlfjablotron.c:237`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfjablotron.c:123` `Jablotron - Card: %<PRIx64>, Raw: %08X%08X`. Card + Raw both match.
- **Verdict**: clean on response side.

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:142` with `00158040`). Community clone (`cmdlfjablotron.c:145-184`) takes positional `<fullcode-hex> [q]`.

### keri

- **Command emitted** — `lfread.py:287` `readFCCNAndRaw('lf keri reader')`
- **Device accepts** — `lf keri read` per `cmdlfkeri.c:346`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfkeri.c:193` `KERI - Internal ID: %u, Raw: %08X%08X`. **No `FC:` or `Card:` label** — only `Internal ID:` (not matched by _RE_FC or _RE_CN) and `Raw:` (matches REGEX_RAW).
- **Middleware regex expected** — FC/CN extraction returns empty; REGEX_RAW captures raw. `readFCCNAndRaw` success via raw-only branch at `lfread.py:207`.
- **Verdict**: clean on response side (FC/CN absent but raw present; middleware status OK). Note: `data` field returned will be the sentinel `'FC,CN: X,X'` since both FC and CN are empty (`lfsearch.py:287-288`).

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:141` with `603E1040`). Community clone (`cmdlfkeri.c:220-269`) takes positional `<cid>` + optional `t <type> f <fc> c <cid> q`.

### nedap

- **Command emitted** — `lfread.py:291` `readCardIdAndRaw('lf nedap reader')`
- **Device accepts** — `lf nedap read` per `cmdlfnedap.c:541`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfnedap.c:201` `NEDAP - Card: %05u subtype: %1u customer code: %03x, Raw: %s`. Card + Raw match; subtype/customer code via `lfsearch._RE_SUBTYPE/_RE_CUSTOMER_CODE` (line 172-173) match natively when invoked via `lf search`.
- **Verdict**: clean on response side (though NEDAP's `lfread.readCardIdAndRaw` path only captures Card+Raw; subtype/customer extraction only fires in `lfsearch.parser()` Check 10).

- **Clone command** — N/A; `write_nedap` at `lfwrite.py:247-252` delegates to `write_raw_t55xx`. Community `CmdLFNedapClone` (`cmdlfnedap.c:440-490`) calls `CmdLfNedapGen(Cmd)` then clones — middleware's raw-write path bypasses this entirely.

### noralsy

- **Command emitted** — `lfread.py:295` `readCardIdAndRaw('lf noralsy reader')`
- **Device accepts** — `lf noralsy read` per `cmdlfnoralsy.c:225`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfnoralsy.c:127` `Noralsy - Card: %u, Year: %u, Raw: %08X%08X%08X`. Card + Raw match.
- **Verdict**: clean on response side.

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:135` with `00088C6A`). Community clone (`cmdlfnoralsy.c:140-177`) takes positional `<id> [<year>] [q]`.

### pac

- **Command emitted** — `lfread.py:299` `readCardIdAndRaw('lf pac reader')`
- **Device accepts** — `lf pac read` per `cmdlfpac.c:300`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfpac.c:186` `PAC/Stanley - Card: %s, Raw: %08X%08X%08X%08X`. Card + Raw match.
- **Verdict**: clean on response side.

- **Clone command** — `lfwrite.py:162` `'lf pac clone -r <hex>'`
- **Device accepts** — `lf pac clone b <hex>` OR `lf pac clone c <cardid-string>` per `cmdlfpac.c:196-246` (bare-char).
- **Translation rule** — `pm3_compat.py:501-502` (gated off).
- **Verdict**: wrong (gated off).

### paradox

- **Command emitted** — `lfread.py:303` `readFCCNAndRaw('lf paradox reader')`
- **Device accepts** — `lf paradox read` per `cmdlfparadox.c:307`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfparadox.c:187` `Paradox - ID: %x%08x FC: %d Card: %d, Checksum: %02x, Raw: %08x%08x%08x`. ID + FC + Card + Raw all match middleware regex.
- **Verdict**: clean on response side.

- **Clone command** — `lfwrite.py:163` `'lf paradox clone -r <hex>'`
- **Device accepts** — `lf paradox clone b <hex>` per `cmdlfparadox.c:211-242` (bare-char `b`, no `-r`).
- **Translation rule** — `pm3_compat.py:501-502` (gated off).
- **Verdict**: wrong (gated off).

### presco

- **Command emitted** — `lfread.py:307` `readCardIdAndRaw('lf presco reader')`
- **Device accepts** — `lf presco read` per `cmdlfpresco.c:181`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfpresco.c:89` `Presco - Card: %08X, Raw: %08X%08X%08X%08X`. Card + Raw match.
- **Verdict**: clean on response side. (Note: middleware doc string at `lfread.py:61` claims Presco emits `Site code:/User code:` — this cites iceman `cmdlfpresco.c:114` (iceman master), but the community fork emits `Card: ... Raw:` like the other legacy demods. Don't re-flag middleware; Presco read works once the command is translated.)

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:136` with `00088088`). Community clone (`cmdlfpresco.c:109-157`) takes Wiegand via `getWiegandFromPresco(Cmd, ...)` — positional format.

### visa2000

- **Command emitted** — `lfread.py:311` `readCardIdAndRaw('lf visa2000 reader')`
- **Device accepts** — `lf visa2000 read` per `cmdlfvisa2000.c:237`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfvisa2000.c:159` `Visa2000 - Card %u, Raw: %08X%08X%08X`. "Card " with space (no colon) + Raw match.
- **Verdict**: clean on response side.

- **Clone command** — N/A (in `B0_WRITE_MAP` at `lfwrite.py:132` with `00148068`). Community clone (`cmdlfvisa2000.c:169-195`) takes positional `<id-dec> [q]`.

### nexwatch

- **Command emitted** — `lfread.py:315` `readCardIdAndRaw('lf nexwatch reader')`
- **Device accepts** — `lf nexwatch read` per `cmdlfnexwatch.c:450`.
- **Verdict**: missing translation (gated off).

- **Reader response** — `cmdlfnexwatch.c:240-256`:
  - ` NexWatch raw id : 0x<hex>`
  - `        88bit id : <dec> (0x<hex>)`
  - ` Raw : <8hex><8hex><8hex>` (note: space-before-colon, single `Raw :`).
- **Middleware regex expected** — `REGEX_CARD_ID = r'(?:Card|ID|UID)[\s:]+...'` is case-sensitive and requires capital `ID`; community emits lowercase `raw id` and lowercase `id` → does NOT match. REGEX_RAW (`lfsearch.py:122`) uses `\s*:` which tolerates the space in ` Raw :` → matches.
- **Verdict**: partial shape mismatch. `readCardIdAndRaw` will set `uid=None` but `raw=<hex>`. Middleware success gate: `if uid or raw:` — succeeds with raw-only. Data field empty (uid is None) — caller expecting a card-ID string may see the raw hex in `raw` but nothing in `data`. Downstream screens may need to display raw-only.

- **Clone command** — `lfwrite.py:164` `'lf nexwatch clone -r <hex>'`
- **Device accepts** — `lf nexwatch clone r <hex>` per `cmdlfnexwatch.c:284-320` (bare-char `r`, NOT dash-prefixed).
- **Translation rule** — `pm3_compat.py:505` `'lf nexwatch clone -r X' -> 'lf nexwatch clone r X'` (gated off).
- **Verdict**: wrong (gated off).

### t55xx

- **Commands emitted** — `lfwrite.py:288` `'lf t55xx write -b N -d HEX'`, `lfwrite.py:310/337` `'lf t55xx write -b N -d HEX -p PWD'`, `lfwrite.py:377` `'lf t55xx restore -f FILE'`.
- **Device accepts** — per `cmdlft55xx.c:1685-1732` (write) and `cmdlft55xx.c:2382-2401` (restore):
  - write: `lf t55xx write b <N> d <HEX> [p <PWD>] [1] [t] [r N] [v]` (bare-char, leading `-` rejected at line 1727-1730).
  - restore: `lf t55xx restore f <FILE> [p <PWD>]` (bare-char).
  - read: `lf t55xx read b <N> [p <PWD>] [1] [o]` per `cmdlft55xx.c:896-929`.
- **Translation rules** — `pm3_compat.py:461-479` cover `read`/`write`/`restore` with correct reverse mappings (gated off).
- **Verdict**: wrong — every `-b`/`-d`/`-f`/`-p` flag is rejected by the legacy bare-char parser.

- **Response shape (write)** — `cmdlft55xx.c:1738` emits `Writing page %d  block: %02d  data: 0x%08X %s`. Middleware only checks return code (`lfwrite.py:289-291`), so this response is not parsed. **Clean on response side**.

- **Response shape (read)** — `cmdlft55xx.c:1831` `PrintAndLogEx(NORMAL, "%02d | 0x%08X | %s", ...)` — same shape as iceman, middleware regex in `lfwrite.py:438-440` is anchored on `\d+\s*\|\s*0x([A-Fa-f0-9]{8})\s*\|` and matches natively.
- **Verdict**: response clean once command is translated.

### em4x05

- **Commands emitted** — `lfwrite.py:469/521` `'lf em 4x05 write -a N -d HEX -p PWD'`; `lfwrite.py:533` `'lf em 4x05 read -a N'`; plus `lfem4x05.py` likely sends `'lf em 4x05 info'` and `'lf em 4x05 dump'` (not re-opened here; out of scope).
- **Device accepts** per `cmdlfem4x.c:1381-1402`:
  - `lf em 4x05_info <pwd>` (positional pwd, no `-p`).
  - `lf em 4x05_read <addr> [<pwd>]` (positional).
  - `lf em 4x05_write <addr> <data> [<pwd>]` (positional).
  - `lf em 4x05_dump [f <prefix>] [<pwd>]` (bare-char `f` + positional pwd).
- **Translation rules** — `pm3_compat.py:427-451` cover `info -p`, `info`, `read -a -p`, `read -a`, `dump -f`, `dump`, `write -a -d -p`, `write -a -d` (gated off).
- **Verdict**: wrong (gated off). Separate response normalizer `_normalize_em4x05_info` at `pm3_compat.py:1304-1310` exists and is registered for both `info` and `info_dump` shapes; also gated off.

### nedap write

As noted above, `write_nedap` at `lfwrite.py:247-252` routes through `write_raw_t55xx` — it does not emit `lf nedap clone`. So community's `lf nedap clone` signature is not directly exercised by middleware. T55xx divergence applies.

### motorola

Not in `lfread.py` / `lfwrite.py` dispatch tables; out of scope.

### idteck, hitag2

Idteck is referenced by `lfsearch.parser()` detection only through chipset fallback; no reader or writer. `lfsearch.py:656-662` references `Hitag2_ID` but there's no per-tag reader or writer in this middleware. Out of scope.

---

## Recommended fixes (priority order)

All fixes are gated on a single correction: make `pm3_compat.py` translations fire on this device.

1. **Fix version detection for the iCopy-X Community fork.**
   - Symptom: `pm3_flash.py:137` looks for `NIKOLA:` (uppercase colon form) which the community fork never emits.
   - Root cause: community `pm3_version()` at `/tmp/icopyx-community-pm3/client/src/cmdhw.c:641-800` emits `  client: <version>` plus compiler/host lines; no `NIKOLA:`, no `bootrom:`, no `os:` matching the existing regex.
   - Fix: in `pm3_compat.py:624-632`, add a third detection path: when `nikola == ''` AND the response contains a recognisable community marker (e.g. `Proxmark3 RFID instrument` + `AT91SAM7S512 Rev B` or lowercase `client:`), classify as `PM3_VERSION_ORIGINAL` (the device IS the legacy-style firmware, not iceman). Alternatively, introduce a third enum value `PM3_VERSION_COMMUNITY` and route it through the same legacy translation tables (since every rule already written is correct for this fork). Cite: `cmdhw.c:706-800` for the shape of the response.
   - Once this flips, every other divergence below is already covered by existing rules.

2. **Register `_normalize_fdxb_animal_id` for per-tag FDX reader paths.**
   - `pm3_compat.py:1292-1295` registers the normalizer for `lf sea` / `lf search` only. `lfread.readFDX` at `lfread.py:274` sends `lf fdxb reader` which translates to `lf fdx read`; the Animal ID rewriter never runs, so REGEX_ANIMAL won't match.
   - Fix: add keys `'lf fdxb reader': [_normalize_fdxb_animal_id]` and `'lf fdx read': [_normalize_fdxb_animal_id]` to the `_RESPONSE_NORMALIZERS` dict at `pm3_compat.py:1278-1313`. Cite: `cmdlffdx.c:200` (colon) and `cmdlffdx.c:282/286` (space-padded) for the two legacy shapes.

3. **NexWatch reader: handle `88bit id : %d` as a legitimate card-ID source.**
   - Community `cmdlfnexwatch.c:245` emits `        88bit id : %d (0x%x)`; middleware `REGEX_CARD_ID` is case-sensitive on `(?:Card|ID|UID)` and does not match lowercase `id`. Raw extraction works (REGEX_RAW tolerates the space-before-colon form), so `readNexWatch` still returns success, but `data` is empty.
   - Fix: either widen `REGEX_CARD_ID` to case-insensitive (`(?i:Card|ID|UID)` or add an alternate `|88bit id`) or add a NexWatch-specific normalizer that rewrites `        88bit id : N (0x<hex>)` to `Card: N, ` so the existing regex matches. Low priority relative to the command-translation gate.

4. **Consider unifying `_BLOCKED_CMDS_ICEMAN` handling.**
   - Unrelated to LF protocols, but once (1) is done and the community fork is classified as ORIGINAL, the iceman-specific `hf iclass info` block at `pm3_compat.py:140-142` no longer runs — verify that's OK on this device (community fork's `cmdhficlass.c` may or may not have the same FPGA-hang). Out of LF scope.

5. **Housekeeping (no code change required):**
   - `lfread.py:61` docstring notes for Presco, NexWatch, Gallagher cite iceman source paths; the community fork has different label shapes on some of these. Docstring is informational only; leave as-is until the compat-flip direction is confirmed.
   - `lfwrite.py:227-244 write_fdx_par` docstring cites `cmdlffdxb.c:712/909` — iceman paths. On this device the target is `cmdlffdx.c:395` (community) via the existing `lf fdxb -> lf fdx` translation rule. Docstring-only, no code fix.

---

## Notes on items explicitly out-of-scope per task

- `/tmp/factory_pm3/` not examined (stale snapshot per task instructions).
- Motorola, Idteck, Hitag2, COTAG, PCF7931 not audited (not in `lfread.py` / `lfwrite.py` dispatch maps).
- `lfem4x05.py` internals not re-opened; `lfwrite.py:469/521/533` commands represent the surface that this audit can confirm.
- Tests/fixtures, response output-log fixtures, and QEMU traces not modified (read-only scope).
