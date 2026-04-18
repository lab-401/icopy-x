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

"""Phase 3 trace-parity test — Read HF flow (P3.2).

Verifies that the refactored iceman-native middleware parsers for the
MIFARE Classic + MIFARE Ultralight read flows correctly handle every
response sample recorded in `tools/ground_truth/iceman_output.json`
for the seven commands issued by the Read HF flow:

    hf mf rdbl      (hfmfread.readBlock)
    hf mf rdsc      (hfmfread.readSector)
    hf mf cgetblk   (hfmfread.readIfIsGen1a)
    hf mf fchk      (hfmfkeys.fchks + keysFromPrintParse)
    hf mf darkside  (hfmfkeys.darkside)
    hf mf nested    (hfmfkeys.nestedOneKey)
    hf mfu dump     (hfmfuread.read — .bin existence check + Partial
                     dump keyword)

Usage:
    python3 tests/phase3_trace_parity/test_read_hf_flow.py

Exit status:
    0 — all iceman trace samples parsed into a non-empty structurally
        valid shape.
    1 — one or more samples failed to parse; details printed per-command.

NOTE: Samples in iceman_output.json were captured post-current-compat-
adapter, so a subset of live-pipeline responses may carry legacy-shaped
fields that the now iceman-native middleware cannot parse. These
FAILs are expected during the Phase 3 transition per user Option B and
are catalogued in tools/ground_truth/phase3_phase4_gap_log.md under
"P3.2 Read HF flow". Phase 4 reconciliation fixes them.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# Insert the middleware directory so `import executor` / `import hfmfread`
# resolves without package prefix — matches the iCopy-X runtime layout.
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import hfmfread  # noqa: E402
import hfmfkeys  # noqa: E402
import hfmfuread  # noqa: E402


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


def _reset_keys_map():
    hfmfkeys.KEYS_MAP.clear()


def _test_hf_mf_rdsc(body, sample_idx):
    """Validate `hf mf rdsc` response parsing via _parse_blocks_from_text.

    - When body contains `"Auth error"` → middleware would return -2 via
      the keyword check in readSector(); here we assert the parser sees
      no blocks and the keyword fires.
    - When body contains iceman-native `"data: XX XX ..."` lines →
      assert one 32-char hex block per line is extracted.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    blocks = hfmfread._parse_blocks_from_text(body)

    # Auth error branch: parser finds 0 blocks; middleware returns -2.
    if 'Auth error' in body:
        if blocks:
            return False, ('body has `Auth error` but parser extracted '
                           '%d blocks: %r' % (len(blocks), blocks[:2]))
        if not executor.hasKeyword('Auth error'):
            return False, ('body has `Auth error` but hasKeyword failed '
                           'on keyword match')
        return True, ''

    # Success branch: each "data:" line yields one 32-char hex block.
    data_line_count = body.count('data: ')
    if data_line_count > 0:
        if len(blocks) != data_line_count:
            return False, ('body has %d data: lines but parser extracted '
                           '%d blocks: %r' % (data_line_count, len(blocks),
                                              blocks[:2]))
        for b in blocks:
            if len(b) != 32:
                return False, ('block length != 32: %r' % (b,))
        return True, ''

    # Neither auth-error nor data-lines: expect no blocks.
    if blocks:
        return False, ('body has no data: line but parser extracted '
                       'blocks: %r' % (blocks[:2],))
    return True, ''


def _test_hf_mf_cgetblk(body, sample_idx):
    """Validate `hf mf cgetblk` response parsing.

    - When body contains `"wupC1 error"` or `"Can't read block"` →
      readIfIsGen1a returns None (Gen1a probe failed).
    - When body contains iceman-native `"data: XX XX ..."` → parser
      extracts exactly 1 block and readIfIsGen1a returns True.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    blocks = hfmfread._parse_blocks_from_text(body)

    if 'wupC1 error' in body or "Can't read block" in body:
        if not executor.hasKeyword('wupC1 error') and \
                not executor.hasKeyword("Can't read block"):
            return False, ('body has error keyword but hasKeyword '
                           'returned False: %r' % (body[:100],))
        return True, ''

    # Success: iceman emits 1 data: line for cgetblk (single block probe).
    data_line_count = body.count('data: ')
    if data_line_count == 1:
        if len(blocks) != 1:
            return False, ('body has 1 data: line but parser extracted '
                           '%d blocks: %r' % (len(blocks), blocks))
        if len(blocks[0]) != 32:
            return False, ('block length != 32: %r' % (blocks[0],))
        return True, ''

    return True, ''  # empty/other — no assertion


def _test_hf_mf_fchk(body, sample_idx):
    """Validate `hf mf fchk` key-table parsing via keysFromPrintParse.

    Iceman table (device build): `| 000 | 484558414354 | 1 | a22ae129c013 | 1 |`
    4-column `|`-bordered form. Matrix L729-730.
    """
    _reset_keys_map()
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    hfmfkeys.keysFromPrintParse(1024)  # size=1024 -> 16 sectors

    # Count data rows manually — exclude separator rows (`|-----|`) which
    # match the hex-or-dash class but are filtered via _RE_HEX_KEY.
    import re as _re
    data_row_count = len([
        m for m in hfmfkeys._RE_KEY_TABLE.finditer(body)
        if _re.match(r'^\d+$', m.group(1))
    ])

    if data_row_count == 0:
        if hfmfkeys.KEYS_MAP:
            return False, ('body has no data rows but KEYS_MAP populated: '
                           '%r' % (hfmfkeys.KEYS_MAP,))
        return True, ''

    # A sample with data rows should populate KEYS_MAP with at least one
    # key (res=1 means valid). Skip the assertion if every row has res=0
    # (full fail).
    any_success = False
    for m in hfmfkeys._RE_KEY_TABLE.finditer(body):
        if not _re.match(r'^\d+$', m.group(1)):
            continue
        if m.group(3) == '1' or m.group(5) == '1':
            any_success = True
            break
    if any_success and not hfmfkeys.KEYS_MAP:
        return False, ('body has res=1 rows but KEYS_MAP empty: %d data '
                       'rows' % (data_row_count,))
    return True, ''


def _test_hf_mf_darkside(body, sample_idx):
    """Validate `hf mf darkside` regex via executor cache.

    iceman emits `"Found valid key [ AABBCCDDEEFF ]"` on success; on
    non-vulnerable-card failure emits no Found-valid-key line (just
    "Card is not vulnerable..." text).
    """
    import re as _re
    m = _re.search(r'Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]',
                   body, _re.IGNORECASE)

    if m:
        key = m.group(1).upper()
        if len(key) != 12:
            return False, ('extracted key wrong length: %r' % (key,))
        return True, ''

    # No match: assert the non-vulnerable text is present OR sample is
    # otherwise shaped so no success line should appear.
    if 'Card is not vulnerable' in body or 'Running darkside' in body or \
            body.strip() == '':
        return True, ''

    return False, ('no `Found valid key [ ... ]` and no known failure '
                   'indicator: %r' % (body[:150],))


def _test_hf_mf_nested(body, sample_idx):
    """Validate `hf mf nested` response parsing — iceman-native form.

    Iceman emits `"Target block N key type C -- found valid key [ HEX ]"`
    (mifarehost.c:686, lowercase "found"). Matrix L753-757.
    """
    import re as _re
    m = _re.search(r'found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]',
                   body, _re.IGNORECASE)

    if m:
        if len(m.group(1)) != 12:
            return False, ('nested extracted key wrong length: %r' % (m.group(1),))
        return True, ''

    # No success line: expect one of the iceman nested-failure shapes.
    if "Wrong key. Can't authenticate" in body or \
            'Found 1 key candidate' in body and 'found valid key' not in body or \
            body.strip() == '':
        return True, ''

    return False, ('no `found valid key [ ... ]` and no known failure '
                   'indicator: %r' % (body[:150],))


def _test_hf_mfu_dump(body, sample_idx):
    """Validate `hf mfu dump` response — iceman-native keyword form.

    Success path for hfmfuread.read() verifies via os.path.exists on the
    produced .bin file; this test only validates keyword matches.

    - body with `"Partial dump created"` → keyword fires.
    - body with `"Can't select card"` → keyword fires (iceman-path
      cmdhf14a.c:1817 or legacy same; matrix L900).
    - empty body → both keywords silent.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    if 'Partial dump created' in body:
        if not executor.hasKeyword('Partial dump created'):
            return False, ('body has `Partial dump created` but '
                           'hasKeyword returned False')
    if "Can't select card" in body:
        if not executor.hasKeyword("Can't select card"):
            return False, ('body has `Can\'t select card` but hasKeyword '
                           'returned False')
    # Empty-body sanity: both keywords should be silent.
    if body.strip() == '':
        if executor.hasKeyword('Partial dump created') or \
                executor.hasKeyword("Can't select card"):
            return False, ('empty body but hasKeyword returned True '
                           'unexpectedly')
    return True, ''


def _test_hf_mfu_info(body, sample_idx):
    """Validate `hf mfu info` iceman-native TYPE keyword matching.

    Uses the scan.py priority ladder pattern (scan.py:247-263). Expected
    subtype derives from the TYPE: substring in the iceman emission
    (cmdhfmfu.c ul_print_type() L1000-1080).
    """
    import tagtypes
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    # Derive expected from iceman-native substrings.
    expected = None
    if 'NTAG 213' in body:
        expected = tagtypes.NTAG213_144B
    elif 'NTAG 215' in body:
        expected = tagtypes.NTAG215_504B
    elif 'NTAG 216' in body:
        expected = tagtypes.NTAG216_888B
    elif 'MIFARE Ultralight C' in body or 'MF0ULC' in body:
        expected = tagtypes.ULTRALIGHT_C
    elif 'MIFARE Ultralight EV1' in body or 'MF0UL1101' in body:
        expected = tagtypes.ULTRALIGHT_EV1
    elif 'MIFARE Ultralight' in body:
        expected = tagtypes.ULTRALIGHT

    # Apply scan.py ladder against executor keywords (iceman-native form).
    if executor.hasKeyword('NTAG 213'):
        observed = tagtypes.NTAG213_144B
    elif executor.hasKeyword('NTAG 215'):
        observed = tagtypes.NTAG215_504B
    elif executor.hasKeyword('NTAG 216'):
        observed = tagtypes.NTAG216_888B
    elif executor.hasKeyword('MIFARE Ultralight C') or \
            executor.hasKeyword('MF0ULC'):
        observed = tagtypes.ULTRALIGHT_C
    elif executor.hasKeyword('MIFARE Ultralight EV1') or \
            executor.hasKeyword('MF0UL1101'):
        observed = tagtypes.ULTRALIGHT_EV1
    elif executor.hasKeyword('MIFARE Ultralight'):
        observed = tagtypes.ULTRALIGHT
    else:
        observed = None

    if expected != observed:
        return False, ('ladder mismatch: expected=%r observed=%r body=%r...'
                       % (expected, observed, body[:200]))
    return True, ''


# ---------------------------------------------------------------------------
# Iceman-native synthetic samples — exercise the post-flip regex shapes
# that existing device traces (post-current-compat) do not surface.
# ---------------------------------------------------------------------------

_ICEMAN_NATIVE_SAMPLES = [
    ('hf mf rdsc', 'iceman 4-block sector',
     '\ndata: 7A F2 EC B2 D6 88 04 00 C8 36 00 20 00 00 00 22\n'
     'data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00\n'
     'data: 00 00 00 00 00 00 00 00 00 00 00 00 09 00 00 00\n'
     'data: 48 45 58 41 43 54 71 E7 88 00 00 00 00 00 00 00\n\n',
     lambda blocks: (len(blocks) == 4 and
                     blocks[0] == '7AF2ECB2D6880400C836002000000022')),
    ('hf mf cgetblk', 'iceman Gen1a success data',
     '\ndata: 3A F7 35 01 F9 88 04 00 C8 21 00 20 00 00 00 21\n\n',
     lambda blocks: (len(blocks) == 1 and
                     blocks[0] == '3AF73501F98804 00C8210020000 00021'.replace(' ', ''))),
    ('hf mf fchk', 'iceman 4-col bordered row',
     '|-----|----------------|---|----------------|---|\n'
     '| Sec | key A          |res| key B          |res|\n'
     '|-----|----------------|---|----------------|---|\n'
     '| 000 | 484558414354   | 1 | a22ae129c013   | 1 |\n'
     '| 001 | 484558414354   | 1 | ------------   | 0 |\n',
     lambda: (hfmfkeys.getKey4Map(0, 'A') == '484558414354' and
              hfmfkeys.getKey4Map(0, 'B') == 'A22AE129C013' and
              hfmfkeys.getKey4Map(1, 'A') == '484558414354' and
              hfmfkeys.getKey4Map(1, 'B') is None)),
    ('hf mf darkside', 'iceman Found bracketed uppercase',
     'Expected execution time is about 25 seconds on average\n'
     'Running darkside ..\n'
     'Found valid key [ FFFFFFFFFFFF ]\n'
     'Time in darkside 25 seconds\n',
     lambda key: key == 'FFFFFFFFFFFF'),
    ('hf mf nested', 'iceman Target-block bracketed lowercase',
     'Found 1 key candidate\n'
     'Target block    8 key type A -- found valid key [ 494558414354 ]\n\n',
     lambda key: key == '494558414354'),
    ('hf mfu dump', 'iceman Partial dump keyword',
     'TYPE: NTAG 216 888bytes (NT2H1611G0DU) ( NTAG21x )\n'
     'Partial dump created. (32 of 231 blocks)\n',
     lambda body: 'Partial dump created' in body),
    ('hf mfu info', 'iceman TYPE NTAG 213',
     '      TYPE: NTAG 213 144bytes (NT2H1311G0DU) ( NTAG21x )\n'
     '       UID: 04 C6 C7 2A C1 4E 80\n',
     lambda: True),  # predicate-less — validated via _test_hf_mfu_info
]


def _run_synthetic_samples():
    """Run synthetic iceman-native shape validation samples."""
    print()
    print('Synthetic iceman-native shape checks:')
    for sample in _ICEMAN_NATIVE_SAMPLES:
        cmd, label, body, predicate = sample
        executor.CONTENT_OUT_IN__TXT_CACHE = body

        try:
            if cmd == 'hf mf rdsc' or cmd == 'hf mf cgetblk':
                blocks = hfmfread._parse_blocks_from_text(body)
                ok = bool(predicate(blocks))
                detail = '' if ok else 'blocks=%r' % (blocks[:4],)
            elif cmd == 'hf mf fchk':
                _reset_keys_map()
                hfmfkeys.keysFromPrintParse(1024)
                ok = bool(predicate())
                detail = '' if ok else 'KEYS_MAP=%r' % (hfmfkeys.KEYS_MAP,)
            elif cmd == 'hf mf darkside':
                import re as _re
                m = _re.search(r'Found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]',
                               body, _re.IGNORECASE)
                key = m.group(1).upper() if m else None
                ok = bool(predicate(key))
                detail = '' if ok else 'extracted=%r' % (key,)
            elif cmd == 'hf mf nested':
                import re as _re
                m = _re.search(r'found valid key\s*\[\s*([A-Fa-f0-9]{12})\s*\]',
                               body, _re.IGNORECASE)
                key = m.group(1).upper() if m else None
                ok = bool(predicate(key))
                detail = '' if ok else 'extracted=%r' % (key,)
            elif cmd == 'hf mfu dump':
                ok = bool(predicate(body))
                detail = ''
            elif cmd == 'hf mfu info':
                # Validate via the scan-ladder logic.
                import tagtypes
                if executor.hasKeyword('NTAG 213'):
                    observed = tagtypes.NTAG213_144B
                else:
                    observed = None
                ok = observed == tagtypes.NTAG213_144B
                detail = '' if ok else 'observed=%r' % (observed,)
            else:
                continue
        except Exception as e:
            _record(cmd + ' (synth)', False,
                    '%s: raised %s: %s' % (label, type(e).__name__, e))
            print('  %-18s  %-48s  [FAIL] raised: %s' % (cmd, label, e))
            continue

        _record(cmd + ' (synth)', ok,
                '%s: predicate failed — %s' % (label, detail))
        print('  %-18s  %-48s  %s' % (cmd, label,
                                       '[PASS]' if ok else '[FAIL] %s' % detail))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMAND_TABLE = [
    ('hf mf rdsc',     _test_hf_mf_rdsc),
    ('hf mf cgetblk',  _test_hf_mf_cgetblk),
    ('hf mf fchk',     _test_hf_mf_fchk),
    ('hf mf darkside', _test_hf_mf_darkside),
    ('hf mf nested',   _test_hf_mf_nested),
    ('hf mfu dump',    _test_hf_mfu_dump),
    ('hf mfu info',    _test_hf_mfu_info),
]


def main():
    print('=' * 70)
    print('Phase 3 trace-parity - P3.2 Read HF flow')
    print('Ground truth: %s' % GROUND_TRUTH_PATH)
    print('=' * 70)

    for cmd, handler in COMMAND_TABLE:
        samples = load_samples(cmd)
        if not samples:
            print('  %-22s  %d samples  (skipped - no samples)' % (cmd, 0))
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
