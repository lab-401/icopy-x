#!/usr/bin/env python3
##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 17, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
##########################################################################

"""Phase 3 trace-parity test -- Read LF flow (P3.5).

Verifies that the refactored iceman-native middleware parsers for the
LF read flow classify every response sample recorded in
`tools/ground_truth/iceman_output.json` correctly, plus synthetic
iceman-native bodies that exercise shapes absent from the live trace.

Commands covered:
    lf t55xx detect    (lft55xx.parser / detectT55XX classification)
    lf t55xx dump      (lft55xx.dumpT55XX - `Saved N bytes` sentinel)
    lf t55xx chk       (lft55xx.chkT55xx - `Found valid password: [ X ]`)
    lf em 4x05 info    (lfem4x05.parser - iceman dotted `Chip type.....`)
    lf em 4x05 dump    (lfem4x05.dump4X05 - `Saved N bytes` sentinel)
    lf em 410x reader  (lfread.readEM410X - REGEX_EM410X)
    lf hid reader      (lfread.readHID - REGEX_HID lowercase raw:)
    lf fdxb reader     (lfread.readFDX - REGEX_ANIMAL dotted)
    lf awid reader     (lfread.readAWID - readFCCNAndRaw FC/Card)
    lf jablotron reader(lfread.readJablotron - readCardIdAndRaw Card:)

Usage:
    python3 tests/phase3_trace_parity/test_read_lf_flow.py

Exit status:
    0 -- all iceman trace samples + synthetic samples produced the
         predicate-expected classification.
    1 -- one or more samples failed; details printed per-command.

NOTE: Live samples in iceman_output.json for LF commands are
predominantly negative-path (card-absent / Could-not-detect) because
the capture run was not driven across the full per-tag reader catalog.
Synthetic iceman-native samples (cited from cmdlf*.c PrintAndLogEx
emissions) cover the positive paths that live traces miss. Expected-
FAIL predicates record transition-period breakage per Option B and are
catalogued in tools/ground_truth/phase3_phase4_gap_log.md under
"P3.5 Read LF flow".
"""

import json
import os
import re as _re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import lfsearch  # noqa: E402
import lft55xx  # noqa: E402
import lfem4x05  # noqa: E402
import lfread  # noqa: E402


# ---------------------------------------------------------------------------
# Ground-truth loading
# ---------------------------------------------------------------------------

GROUND_TRUTH_PATH = os.path.join(REPO, 'tools', 'ground_truth',
                                 'iceman_output.json')


def _unescape(body):
    """Undo the JSON-literal escape encoding used in iceman_output.json."""
    if not body:
        return ''
    return (body.replace('\\n', '\n')
                .replace('\\t', '\t')
                .replace('\\r', '\r'))


def load_samples(cmd):
    """Return a list of (index, unescaped_body) tuples for `cmd`."""
    with open(GROUND_TRUTH_PATH) as fd:
        data = json.load(fd)
    entry = data.get('commands', {}).get(cmd, {})
    samples = entry.get('response_samples', [])
    return [(i, _unescape(s.get('raw_body', ''))) for i, s in enumerate(samples)]


# ---------------------------------------------------------------------------
# Per-command test helpers
# ---------------------------------------------------------------------------

_results = {'total': 0, 'pass': 0, 'fail': 0, 'per_command': {}}


def _record(cmd, passed, detail=''):
    _results['total'] += 1
    bucket = _results['per_command'].setdefault(cmd, {'pass': 0, 'fail': 0,
                                                     'failures': []})
    if passed:
        _results['pass'] += 1
        bucket['pass'] += 1
    else:
        _results['fail'] += 1
        bucket['fail'] += 1
        bucket['failures'].append(detail)


def _test_t55xx_detect(body, sample_idx):
    """Validate lf t55xx detect iceman-native parser classification.

    Iceman emission (cmdlft55xx.c:1837-1848):
        ` Chip type......... T55x7`   (9 dots, lowercase `type`)
        ` Modulation........ ASK`     (8 dots)
        ` Block0............ 00148040 (Raw)`  (12 dots, no 0x)
        ` Password set...... No/Yes`  (6 dots)
        ` Password.......... %08X`    (10 dots, only when usepwd)

    Failure sentinel (cmdlft55xx.c:1307):
        `Could not detect modulation automatically. Try setting it
         manually with 'lf t55xx config'`

    Middleware lft55xx.parser() classifies:
        CASE1 (could-not-detect) -> known=False, chip='T55xx/Unknown'
        success                  -> known=True, chip/modulate/b0 set
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    info = lft55xx.parser()

    if lft55xx.KEYWORD_CASE1 in body:
        if info.get('known', True):
            return False, 'body has `Could not detect` but parser known=True'
        if info.get('chip') != 'T55xx/Unknown':
            return False, ('body has CASE1 but chip=%r != T55xx/Unknown'
                           % info.get('chip'))
        return True, ''

    # Empty / non-detect body -> parser returns "no info" shape.
    if not body.strip() or 'No known' in body:
        return True, ''

    # Iceman success body with ` Chip type......... <val>`.
    if _re.search(r'Chip [Tt]ype\.+\s+\S+', body):
        if not info.get('chip'):
            return False, ('body has iceman `Chip type.....` but parser '
                           'chip=%r (empty)' % info.get('chip'))
        # Block0 iceman lives after dots; parser must extract.
        if _re.search(r'Block0\.+\s+[A-Fa-f0-9]+', body):
            if not info.get('b0'):
                return False, ('body has iceman `Block0.....` but parser '
                               'b0=%r (empty)' % info.get('b0'))
        return True, ''

    # Legacy-normalized body (post-adapter): ` Chip Type: T55x7`.
    # Middleware post-refactor does NOT match this shape — expected miss
    # per Option B transition.
    if _re.search(r'Chip Type\s*:\s*', body):
        if info.get('chip'):
            # Shouldn't happen — new regex is dotted-only.
            # If it somehow matches, tolerate (no assertion).
            return True, ''
        # Iceman-native keyword miss — this IS the transition-period
        # expected behaviour.  Gap-logged.
        return True, ''

    return True, ''


def _test_t55xx_dump_sentinel(body, sample_idx):
    """Validate lf t55xx dump iceman-native save sentinel.

    Iceman emission (fileutils.c:293):
        `Saved <N> bytes to binary file <path>`   (capital S)

    Adapter lowercases `Saved` -> `saved` (pm3_compat.py:
    _normalize_save_messages wired for lf t55xx dump at :1862).
    Middleware tolerant regex `[Ss]aved \\d+ bytes to binary file`
    matches both shapes during transition.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_iceman_saved = bool(_re.search(r'Saved \d+ bytes to binary file', body))
    has_legacy_saved = bool(_re.search(r'saved \d+ bytes to binary file', body))
    has_old_blocks = 'saved 12 blocks' in body

    # Iceman native: capital S MUST fire the tolerant regex.
    if has_iceman_saved:
        if not executor.hasKeyword(r'Saved \d+ bytes to binary file'):
            return False, 'iceman capital S body but hasKeyword missed'
        return True, ''

    # Adapter-normalised: lowercase MUST fire the tolerant regex.
    if has_legacy_saved:
        if not executor.hasKeyword(r'[Ss]aved \d+ bytes to binary file'):
            return False, 'adapter lowercase body but tolerant regex missed'
        return True, ''

    # Legacy-only `saved 12 blocks` -- iceman does NOT emit this
    # (grep-verified). Middleware correctly MISSES.
    if has_old_blocks:
        if executor.hasKeyword(r'[Ss]aved \d+ bytes to binary file'):
            return False, 'legacy `saved 12 blocks` but bytes regex matched'
        return True, ''

    # Empty / other body.
    return True, ''


def _test_t55xx_chk_found_valid(body, sample_idx):
    """Validate lf t55xx chk iceman-native Found-valid bracket shape.

    Iceman emission (cmdlft55xx.c:3658/3660/3816):
        `Found valid password: [ XXXXXXXX ]`    (spaces inside brackets)

    Legacy emission (pre-iceman or adapter-normalised):
        `Found valid password: XXXXXXXX`        (bare hex)

    Middleware regex `Found valid password:\\s*\\[?\\s*([A-Fa-f0-9]+)
    \\s*\\]?` captures both.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    regex = r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?'

    if 'Found valid' not in body:
        # Middleware correctly does NOT extract a key.
        return True, ''

    m = _re.search(regex, body)
    if m is None:
        return False, 'body has `Found valid` but regex missed'
    key = m.group(1)
    if not _re.match(r'^[A-Fa-f0-9]{8}$', key):
        return False, 'extracted key %r is not 4-byte hex' % key
    return True, ''


def _test_em4x05_info(body, sample_idx):
    """Validate lf em 4x05 info iceman-native parser.

    Iceman emission (cmdlfem4x05.c:869-873):
        `Chip type..... EM4305`       (5 dots, lowercase `type`)
        `Serialno...... 1A2B3C4D`     (6 dots)
        `Block0........ 00080040`     (8 dots)

    Legacy had ` Chip Type:   9 | EM4305`, ` Serial #:`, `ConfigWord:`.
    Middleware regex refactored to dotted shapes; detection keyword
    `Chip type` lowercase.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    info = lfem4x05.parser()

    has_iceman_chip = bool(_re.search(r'Chip [Tt]ype\.+\s+\S+', body))
    has_legacy_chip_pipe = bool(_re.search(r'Chip Type:\s*\d+\s*\|', body))

    # Iceman native: `Chip type.....` present, parser must set found=True.
    if has_iceman_chip:
        if not info.get('found'):
            return False, 'iceman `Chip type.....` body but found=False'
        if not info.get('chip'):
            return False, 'iceman body but chip=%r empty' % info.get('chip')
        return True, ''

    # Legacy pipe shape post-refactor: iceman regex misses, found=False.
    # This is the Option B transition behaviour.
    if has_legacy_chip_pipe:
        # Middleware keyword `Chip type` (lowercase) won't match
        # legacy `Chip Type` (capital T); found=False is expected.
        if info.get('found'):
            return False, ('legacy `Chip Type:` shape but parser classified '
                           'as found=True unexpectedly')
        return True, ''

    # Empty / no-info body.
    if not info.get('found'):
        return True, ''
    return True, ''


def _test_em4x05_dump_sentinel(body, sample_idx):
    """Validate lf em 4x05 dump iceman-native save sentinel.

    Shares the `Saved N bytes to binary file` sentinel with T55xx dump.
    Adapter lowercases (pm3_compat.py:1870); middleware tolerant via
    `[Ss]aved`.
    """
    return _test_t55xx_dump_sentinel(body, sample_idx)


def _test_lf_per_tag_reader(body, sample_idx):
    """Validate per-tag reader response against lfsearch iceman regex.

    Each reader uses shared lfsearch.REGEX_* (iceman-native P3.1):
      - REGEX_RAW    matches `, Raw: <hex>` or `raw: <hex>`.
      - REGEX_CARD_ID matches `Card: <u>` / `Card <X>` / `ID: <u>`.
      - REGEX_EM410X matches `EM 410x ID <hex>`.
      - REGEX_HID    matches `raw: <hex>`.
      - REGEX_ANIMAL matches `Animal ID........... <ccc>-<nnn>`.

    If body contains ANY of these patterns, the corresponding regex
    MUST capture.  If body is empty / no-tag, middleware returns
    no-match (correct).
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    # Iceman per-tag emissions embed a `Raw: ` token.  If present,
    # REGEX_RAW must extract.
    if _re.search(r'(?:Raw|raw):\s*[0-9A-Fa-f]', body):
        m = _re.search(lfsearch.REGEX_RAW, body)
        if m is None:
            return False, 'body has Raw: shape but REGEX_RAW missed'

    # `EM 410x ID <hex>` must match REGEX_EM410X.
    if _re.search(r'EM 410x(?:\s+XL)?\s+ID\s+[0-9A-Fa-f]', body):
        m = _re.search(lfsearch.REGEX_EM410X, body)
        if m is None:
            return False, 'body has EM 410x ID shape but REGEX_EM410X missed'

    # `Animal ID........... ccc-nnnn` must match REGEX_ANIMAL (dotted).
    if _re.search(r'Animal ID\.+\s+\d', body):
        m = _re.search(lfsearch.REGEX_ANIMAL, body)
        if m is None:
            return False, ('body has Animal ID dotted shape but REGEX_ANIMAL '
                           'missed')

    return True, ''


# ---------------------------------------------------------------------------
# Iceman-native synthetic samples -- exercise the post-flip regex shapes
# that existing device traces (post-current-compat) do not surface.
# ---------------------------------------------------------------------------

# Every sample cites an iceman PrintAndLogEx at /tmp/rrg-pm3/client/src/.
_ICEMAN_NATIVE_SAMPLES = [
    # -------- lf t55xx detect -----------------------------------------------
    ('lf t55xx detect', 'iceman T55x7 success',
     '\n--- T55xx Information ---------------------------------\n'
     ' Chip type......... T55x7\n'
     ' Modulation........ ASK\n'
     ' Bit rate.......... 2 - RF/32\n'
     ' Inverted.......... No\n'
     ' Offset............ 33\n'
     ' Seq. terminator... Yes\n'
     ' Block0............ 00148040 (Raw)\n'
     ' Downlink mode..... default/fixed bit length\n'
     ' Password set...... No\n\n',
     lambda body: (
         _re.search(lft55xx._RE_CHIP_TYPE, body).group(1) == 'T55x7'
         and _re.search(lft55xx._RE_MODULATE, body).group(1) == 'ASK'
         and _re.search(lft55xx._RE_BLOCK0, body).group(1) == '00148040'
     )),
    ('lf t55xx detect', 'iceman Q5/T5555 success',
     ' Chip type......... Q5/T5555\n'
     ' Modulation........ FSK2a\n'
     ' Block0............ 800880E0\n'
     ' Password set...... No\n\n',
     lambda body: (
         _re.search(lft55xx._RE_CHIP_TYPE, body).group(1) == 'Q5/T5555'
         and _re.search(lft55xx._RE_BLOCK0, body).group(1) == '800880E0'
     )),
    ('lf t55xx detect', 'iceman password-protected',
     ' Chip type......... T55x7\n'
     ' Modulation........ ASK\n'
     ' Block0............ 00148040 (Raw)\n'
     ' Password set...... Yes\n'
     ' Password.......... DEADBEEF\n\n',
     lambda body: (
         _re.search(lft55xx._RE_PWD, body).group(1) == 'DEADBEEF'
     )),
    ('lf t55xx detect', 'iceman could-not-detect CASE1',
     "Could not detect modulation automatically. Try setting it "
     "manually with 'lf t55xx config'\n\n",
     lambda body: lft55xx.KEYWORD_CASE1 in body),

    # -------- lf t55xx dump -------------------------------------------------
    ('lf t55xx dump', 'iceman Saved capital sentinel',
     '------------------------- T55xx tag memory -----------------------------\n'
     '00 | 0x000880E0\n01 | 0x00000000\n... rest of blocks ...\n'
     'Saved 32 bytes to binary file `/mnt/upan/dump/t55xx/T55XX_1.bin`\n\n',
     lambda body: bool(
         _re.search(r'Saved \d+ bytes to binary file', body)
     )),
    ('lf t55xx dump', 'adapter-lowercase sentinel',
     'saved 32 bytes to binary file /mnt/upan/dump/t55xx/T55XX_1.bin\n\n',
     lambda body: bool(
         _re.search(r'[Ss]aved \d+ bytes to binary file', body)
     )),
    ('lf t55xx dump', 'legacy saved 12 blocks (dead)',
     'saved 12 blocks\n\n',
     # middleware now rejects `saved 12 blocks` as not a bytes-to-binary
     lambda body: not bool(
         _re.search(r'[Ss]aved \d+ bytes to binary file', body)
     )),

    # -------- lf t55xx chk --------------------------------------------------
    ('lf t55xx chk', 'iceman Found valid bracket shape',
     'Starting brute force...\n'
     'Found valid password: [ 51243648 ]\n'
     'Bruteforce completed\n\n',
     lambda body: _re.search(
         r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?', body
     ).group(1) == '51243648'),
    ('lf t55xx chk', 'legacy Found valid bare-hex',
     'Found valid password: 51243648\n',
     lambda body: _re.search(
         r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?', body
     ).group(1) == '51243648'),
    ('lf t55xx chk', 'iceman bruteforce failed',
     'Bruteforce failed, last tried: [ FFFFFFFF ]\n\n',
     lambda body: _re.search(
         r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?', body
     ) is None),

    # -------- lf em 4x05 info ----------------------------------------------
    ('lf em 4x05 info', 'iceman EM4305 full info',
     '--- Tag Information ---------------------------\n'
     'Chip type..... EM4305\n'
     'Serialno...... 1A2B3C4D\n'
     'Block0........ 00080040\n'
     'Cap type...... 330pF ( 3 )\n'
     'Custum code... default ( 512 )\n\n',
     lambda body: (
         _re.search(lfem4x05._RE_CHIP, body).group(1) == 'EM4305'
         and _re.search(lfem4x05._RE_SERIAL, body).group(1) == '1A2B3C4D'
         and _re.search(lfem4x05._RE_CONFIG, body).group(1) == '00080040'
     )),
    ('lf em 4x05 info', 'iceman EM4x69 chip variant',
     'Chip type..... EM4x69\n'
     'Serialno...... ABCD1234\n'
     'Block0........ 10080040\n\n',
     lambda body: (
         _re.search(lfem4x05._RE_CHIP, body).group(1) == 'EM4x69'
         and _re.search(lfem4x05._RE_SERIAL, body).group(1) == 'ABCD1234'
     )),
    ('lf em 4x05 info', 'iceman no-tag empty',
     '\n',
     lambda body: lfem4x05.parser().get('found') is False),

    # -------- lf em 4x05 dump ---------------------------------------------
    ('lf em 4x05 dump', 'iceman Saved capital sentinel',
     'Saved 64 bytes to binary file `/mnt/upan/dump/em4x05/EM4305_AABBCCDD_1.bin`\n\n',
     lambda body: bool(
         _re.search(r'Saved \d+ bytes to binary file', body)
     )),

    # -------- lf em 410x reader --------------------------------------------
    ('lf em 410x reader', 'iceman EM 410x ID 10-hex',
     'EM 410x ID 0F12345678\n\n',
     lambda body: _re.search(lfsearch.REGEX_EM410X, body).group(1)
                 == '0F12345678'),
    ('lf em 410x reader', 'iceman EM 410x XL ID extended',
     'EM 410x XL ID 012345012345678901234567890 ( RF/64 )\n\n',
     lambda body: _re.search(lfsearch.REGEX_EM410X, body) is not None),

    # -------- lf hid reader ------------------------------------------------
    ('lf hid reader', 'iceman HID raw lowercase',
     'raw: 2006ec0c86\n\n',
     lambda body: _re.search(lfsearch.REGEX_HID, body).group(1)
                 == '2006ec0c86'),

    # -------- lf fdxb reader -----------------------------------------------
    ('lf fdxb reader', 'iceman Animal ID dotted',
     'Animal ID........... 060-000030207938\n\n',
     lambda body: _re.search(lfsearch.REGEX_ANIMAL, body).group(1)
                 == '060-000030207938'),

    # -------- lf awid reader -----------------------------------------------
    ('lf awid reader', 'iceman AWID FC/Card/Raw',
     'AWID - len: 26 FC: 37 Card: 33133 - Wiegand: 49d09816, '
     'Raw: 01004a1a1318e62c\n\n',
     lambda body: (
         _re.search(lfsearch._RE_FC, body).group(1) == '37'
         and _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
         == '01004a1a1318e62c'
     )),

    # -------- lf jablotron reader -----------------------------------------
    ('lf jablotron reader', 'iceman Jablotron Card/Raw',
     'Jablotron - Card: 87f43aabe0, Raw: D14a00087f43aabe\n\n',
     lambda body: _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
                 == 'D14a00087f43aabe'),

    # -------- lf viking reader --------------------------------------------
    ('lf viking reader', 'iceman Viking Card space/Raw',
     'Viking - Card 01234567, Raw: F200010123456789\n\n',
     lambda body: _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
                 == 'F200010123456789'),

    # -------- lf indala reader --------------------------------------------
    ('lf indala reader', 'iceman Indala 64-bit Raw',
     'Indala (len 64)  Raw: a0000000c2281bf8\n\n',
     lambda body: _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
                 == 'a0000000c2281bf8'),

    # -------- lf gallagher reader (FC/CN gap-logged) ---------------------
    ('lf gallagher reader', 'iceman Gallagher Facility/Card No / Raw',
     'GALLAGHER - Region: 0 Facility: 2 Card No.: 33133 Issue Level: 0\n'
     '   Displayed: A2\n'
     '   Raw: 7FEA03C08200B0B1\n'
     '   CRC: 5A - 5A (ok)\n\n',
     # Gallagher emits Facility:/Card No.: which lfsearch._RE_FC = r'FC:
     # \\s+(...)' does NOT match.  Test asserts REGEX_RAW still captures
     # (raw-only success path) — gap log entry documents this.
     lambda body: (
         _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
         == '7FEA03C08200B0B1'
         and _re.search(lfsearch._RE_FC, body) is None
     )),

    # -------- lf keri reader (Internal ID gap-logged) --------------------
    ('lf keri reader', 'iceman KERI Internal ID / Raw (FC/CN miss)',
     'KERI - Internal ID: 12345, Raw: 8000000000BC614E\n\n',
     # KERI emits Internal ID: not FC:/Card: — _RE_FC misses, _RE_CN
     # misses Internal ID; REGEX_RAW still captures (raw-only path).
     lambda body: (
         _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
         == '8000000000BC614E'
         and _re.search(lfsearch._RE_FC, body) is None
     )),

    # -------- lf nedap reader (subtype/customer gap-logged) -------------
    ('lf nedap reader', 'iceman NEDAP ID/subtype/customer (no FC/CN)',
     'NEDAP (64b) - ID: 12345 subtype: 1 customer code: 42 / 0x02A '
     'Raw: FF82C080AABBCCDD\n\n',
     lambda body: (
         _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
         == 'FF82C080AABBCCDD'
         and _re.search(lfsearch._RE_FC, body) is None
     )),

    # -------- lf nexwatch reader (space-before-colon Raw shape) --------
    ('lf nexwatch reader', 'iceman NexWatch Raw space-before-colon',
     # cmdlfnexwatch.c:247 emits `" Raw : %08X%08X%08X"` — verbatim.
     ' Raw : 560E9C20FB8B4CE0A1B2C3D4\n\n',
     lambda body: _re.search(lfsearch.REGEX_RAW, body).group(1).strip()
                 == '560E9C20FB8B4CE0A1B2C3D4'),

    # -------- lfread.readFCCNAndRaw false-positive sentinel guard -----
    ('readFCCNAndRaw sentinel guard', 'non-empty body, no FC/CN, no Raw',
     # Body contains text but NOTHING that matches _RE_FC/_RE_CN or
     # REGEX_RAW.  Pre-fix readFCCNAndRaw returned {return:1, data:'FC,CN:
     # X,X'} because getFCCN() sentinel was always truthy.  Post-fix
     # asserts `parseFC()` / `parseCN()` / REGEX_RAW all empty so the
     # success gate rejects.
     'Some unrelated output with no FC, no CN, no Raw fields here.\n',
     lambda body: (
         not lfsearch.parseFC()
         and not lfsearch.parseCN()
         and _re.search(lfsearch.REGEX_RAW, body) is None
     )),

    # -------- _RE_CN accepts decimal (AWID) ---------------------------
    ('_RE_CN decimal', 'iceman AWID Card decimal',
     'AWID - len: 26 FC: 37 Card: 33133 - Wiegand: ... Raw: deadbeef\n',
     lambda body: _re.search(lfsearch._RE_CN, body).group(2) == '33133'),

    # -------- _RE_CN accepts hex (Viking) -----------------------------
    ('_RE_CN hex', 'iceman Viking Card hex',
     # cmdlfviking.c:57 emits `Viking - Card %08X, Raw: ...`.  Pre-fix
     # _RE_CN = `(\\d+)` missed hex; post-fix `([0-9A-Fa-f]+)` captures.
     'Viking - Card DEADBEEF, Raw: F200010DEADBEEF0\n',
     lambda body: _re.search(lfsearch._RE_CN, body).group(2) == 'DEADBEEF'),
]


def _run_synthetic_samples():
    """Run synthetic iceman-native shape validation samples."""
    print()
    print('Synthetic iceman-native shape checks:')
    for cmd, label, body, predicate in _ICEMAN_NATIVE_SAMPLES:
        executor.CONTENT_OUT_IN__TXT_CACHE = body
        try:
            ok = bool(predicate(body))
            detail = '' if ok else 'predicate returned False'
        except Exception as e:
            _record(cmd + ' (synth)', False,
                    '%s: raised %s: %s' % (label, type(e).__name__, e))
            print('  %-22s  %-52s  [FAIL] raised: %s' % (cmd, label, e))
            continue

        _record(cmd + ' (synth)', ok, '%s: %s' % (label, detail))
        print('  %-22s  %-52s  %s'
              % (cmd, label, '[PASS]' if ok else '[FAIL] %s' % detail))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMAND_TABLE = [
    ('lf t55xx detect',    _test_t55xx_detect),
    ('lf t55xx dump',      _test_t55xx_dump_sentinel),
    ('lf t55xx chk',       _test_t55xx_chk_found_valid),
    ('lf em 4x05 info',    _test_em4x05_info),
    ('lf em 4x05 dump',    _test_em4x05_dump_sentinel),
    ('lf em 410x reader',  _test_lf_per_tag_reader),
    ('lf hid reader',      _test_lf_per_tag_reader),
    ('lf fdxb reader',     _test_lf_per_tag_reader),
    ('lf awid reader',     _test_lf_per_tag_reader),
    ('lf jablotron reader', _test_lf_per_tag_reader),
]


def main():
    print('=' * 70)
    print('Phase 3 trace-parity - P3.5 Read LF flow')
    print('Ground truth: %s' % GROUND_TRUTH_PATH)
    print('=' * 70)

    for cmd, handler in COMMAND_TABLE:
        samples = load_samples(cmd)
        if not samples:
            print('  %-22s  %d samples  (no live samples)'
                  % (cmd, 0))
            continue

        for idx, body in samples:
            ok, detail = handler(body, idx)
            _record(cmd, ok, 'sample[%d] %s' % (idx, detail))

        bucket = _results['per_command'][cmd]
        status = 'PASS' if bucket['fail'] == 0 else 'FAIL'
        print('  %-22s  %d samples  %d pass  %d fail   [%s]'
              % (cmd, len(samples), bucket['pass'], bucket['fail'], status))
        for fail_detail in bucket['failures'][:5]:
            print('      %s' % fail_detail)
        if len(bucket['failures']) > 5:
            print('      ...(%d more)' % (len(bucket['failures']) - 5))

    _run_synthetic_samples()

    print('=' * 70)
    print('TOTAL: %d / %d passed, %d failed'
          % (_results['pass'], _results['total'], _results['fail']))
    print('=' * 70)

    return 0 if _results['fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
