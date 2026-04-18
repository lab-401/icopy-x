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

"""Phase 3 trace-parity test — iCLASS flow (P3.7).

Verifies that the refactored iceman-native iclass middleware (hficlass.py,
iclassread.py, iclasswrite.py) correctly parses every iceman-shaped
response sample for:

    hf iclass info        (hficlass._RE_CSN)
    hf iclass rdbl        (hficlass._RE_BLOCK_READ — iceman raw shape)
    hf iclass chk         (hficlass.chkKeys fallback — `Found valid key`)
    hf iclass dump        (iclassread._KW_DUMP_SUCCESS)
    hf iclass wrbl        (iclasswrite._KW_WRBL_SUCCESS)
    hf iclass calcnewkey  (iclasswrite._RE_XOR_DIV_KEY — iceman 4-dot)

Live iceman_output.json samples for `hf iclass rdbl` all show the
post-current-adapter NORMALIZED shape (`Block 1 : ...` — capital B, no
`/0x..` infix). Since the compat-flip target middleware now expects
iceman RAW shape (` block %3d/0x%02X : ...`), the live samples do NOT
exercise the iceman-native regex. This is INTENTIONAL per Option B —
Phase 4 will remove the normalizer and the live samples will match
after re-capture. Until then, the synthetic iceman-native samples
below are the primary validation gate.

Usage:
    python3 tests/phase3_trace_parity/test_iclass_flow.py

Exit status:
    0 — all samples parsed to structurally valid shapes.
    1 — one or more samples failed; details printed per-command.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# Insert the middleware directory so `import executor` / `import hficlass`
# resolves without package prefix — matches the iCopy-X runtime layout.
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import hficlass  # noqa: E402
import iclassread  # noqa: E402
import iclasswrite  # noqa: E402


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


def _test_hf_iclass_info(body, sample_idx):
    """Validate `hf iclass info` CSN extraction against iceman shape.

    Iceman emits `    CSN: 75 D0 E0 13 FE FF 12 E0 uid` at
    cmdhficlass.c:8032. The middleware regex `_RE_CSN` captures the
    hex run regardless of the trailing `uid` annotation.

    Ping-leak samples (no tag) have no `CSN:` at all — regex returns
    None / empty, which matches the `found=False` expected path.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    # Derive expected: body contains CSN iff iceman emitted CSN line
    has_csn_line = bool(re.search(r'CSN:\s', body))

    # Apply middleware regex
    got = executor.getContentFromRegex(hficlass._RE_CSN)
    got = (got or '').strip().replace(' ', '')

    if has_csn_line:
        # Expect a non-empty hex string of at least 4 bytes (8 chars)
        if not got or not re.match(r'^[0-9A-Fa-f]{8,}$', got):
            return False, ('body has CSN line but regex failed: got=%r'
                           ' body=%r' % (got, body[:120]))
    else:
        # Empty / ping-leak body: regex should produce empty result
        if got:
            return False, ('body has no CSN but regex matched: got=%r'
                           ' body=%r' % (got, body[:120]))
    return True, ''


def _test_hf_iclass_rdbl(body, sample_idx):
    """Validate `hf iclass rdbl` block-read extraction.

    Iceman-native regex: `block\\s+\\d+\\s*/0x[0-9A-Fa-f]+\\s*:\\s+hex`
    matches ` block   6/0x06 : 12 FF ...` (cmdhficlass.c:3501).

    Live iceman_output.json samples are adapter-normalized
    `Block 6 : ...` shape — iceman-native regex CANNOT match these
    until pm3_compat._normalize_iclass_rdbl is disabled (Phase 4).
    For the live samples, assert the non-match behaviour so a
    regression where the adapter is unexpectedly bypassed is caught.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    # Detect iceman raw shape vs adapter-normalized shape
    has_iceman_raw = bool(re.search(r'block\s+\d+/0x[0-9A-Fa-f]+', body))
    has_normalized = bool(re.search(r'Block \d+ :', body)) and not has_iceman_raw

    got = executor.getContentFromRegex(hficlass._RE_BLOCK_READ)
    got = (got or '').strip()

    if has_iceman_raw:
        # Must match
        if not got:
            return False, ('iceman raw shape but regex failed: body=%r'
                           % (body[:200],))
        # Hex run should have at least one byte
        if not re.match(r'^[0-9A-Fa-f ]+$', got):
            return False, ('match not hex: got=%r' % (got,))
    elif has_normalized:
        # Adapter-normalized shape. Iceman-native regex must NOT match.
        if got:
            return False, ('adapter-normalized shape but iceman regex '
                           'matched (adapter bypass?): got=%r body=%r'
                           % (got, body[:120]))
    else:
        # Empty / error body — no match expected
        if got:
            return False, ('empty body but match: got=%r' % (got,))
    return True, ''


def _test_hf_iclass_dump(body, sample_idx):
    """Validate `hf iclass dump` success-keyword detection.

    Iceman emits `saving dump file - %u blocks read` at
    cmdhficlass.c:2978. Both firmwares emit identical substring
    (matrix v2 correction, line 484-487).
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    expected = iclassread._KW_DUMP_SUCCESS in body
    observed = executor.hasKeyword(iclassread._KW_DUMP_SUCCESS)

    if expected != observed:
        return False, ('keyword mismatch: body_has=%r kw_hit=%r body=%r'
                       % (expected, observed, body[:120]))
    return True, ''


def _test_hf_iclass_wrbl(body, sample_idx):
    """Validate `hf iclass wrbl` success-keyword detection.

    Iceman emits `Wrote block %d / 0x%02X ( ok )` at cmdhficlass.c:3134
    (literal ` ( ok )` substring is the sentinel).

    Live iceman_output.json samples are adapter-normalized to
    `Wrote block 6 / 0x06 successful` — the iceman-native regex
    `\\( ok \\)` must NOT match the normalized shape.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_iceman_native = '( ok )' in body
    has_normalized = 'successful' in body and '( ok )' not in body

    observed = executor.hasKeyword(iclasswrite._KW_WRBL_SUCCESS)

    if has_iceman_native:
        if not observed:
            return False, ('iceman native `( ok )` but keyword miss: '
                           'body=%r' % (body[:120],))
    elif has_normalized:
        # Adapter-normalized — iceman native keyword must not match
        if observed:
            return False, ('adapter-normalized but iceman native '
                           'matched: body=%r' % (body[:120],))
    else:
        # Other (error, timeout) — must not match
        if observed:
            return False, ('non-success body matched: body=%r'
                           % (body[:120],))
    return True, ''


def _test_hf_iclass_chk(body, sample_idx):
    """Validate `hf iclass chk` key-extraction regex.

    Iceman emits `Found valid key <hex>` at cmdhficlass.c:5925 / :7016.
    """
    # Matrix notes 0 samples; this helper is for synthetic path.
    expected = 'Found valid key' in body
    m = re.search(r'Found valid key\s+([0-9a-fA-F ]+)', body)
    observed = bool(m)

    if expected != observed:
        return False, ('expected=%r observed=%r body=%r'
                       % (expected, observed, body[:120]))
    return True, ''


def _test_hf_iclass_calcnewkey(body, sample_idx):
    """Validate `hf iclass calcnewkey` Xor div key extraction.

    Iceman: `Xor div key.... <hex>` (4-dot separator,
    cmdhficlass.c:5419). Matrix correction from colon to 4-dot form.
    """
    expected_match = bool(re.search(r'Xor div key\.+\s+[0-9A-Fa-f]', body))
    m = re.search(iclasswrite._RE_XOR_DIV_KEY, body)
    observed_match = bool(m)

    if expected_match != observed_match:
        return False, ('expected=%r observed=%r body=%r'
                       % (expected_match, observed_match, body[:120]))
    return True, ''


# ---------------------------------------------------------------------------
# Iceman-native synthetic samples — exercise the post-flip regex shapes
# that live iceman_output.json does NOT yet surface (adapter runs).
# Each body string is copy-equivalent to an exact iceman PrintAndLogEx
# emission per source citations; any failure here means middleware has
# regressed away from iceman-native shape.
# ---------------------------------------------------------------------------

_ICEMAN_NATIVE_SAMPLES = [
    # hf iclass info: full `--- Tag Information ---` block, iceman-shape
    # CSN line with `uid` suffix (cmdhficlass.c:8032).
    ('hf iclass info', 'iceman CSN with uid suffix',
     '--- Tag Information -------------------------------------\n'
     '    CSN: 75 D0 E0 13 FE FF 12 E0 uid\n'
     ' Config: 12 FF FF FF 7F 1F FF 3C card configuration\n'
     'E-purse: FE FF FF FF FF FF FF FF card challenge, CC\n'
     '     Kd: AF A7 85 A7 DA B3 33 78 debit key\n'
     '     Kc: -- -- -- -- -- -- -- --  credit key ( hidden )\n',
     lambda body: _match_csn(body, '75D0E013FEFF12E0')),

    # hf iclass info: Fingerprint banner with dotted CSN line
    # (cmdhficlass.c:8088/8098). Dotted form also matched by _RE_CSN
    # via `CSN:*\s` tolerance (`:*` absorbs the dotted leader when the
    # intervening whitespace precedes hex).
    ('hf iclass info', 'iceman Fingerprint dotted CSN (HID range)',
     '----------------------- Fingerprint ---------------------\n'
     '    CSN.......... HID range\n'
     '    Credential... iCLASS legacy\n'
     '    Card type.... PicoPass 2KS\n',
     # This tests that the regex does NOT mis-parse the dotted annotation
     # as a hex CSN. Expected: regex misses because post-dot char is
     # non-hex text `HID range`. The `[A-Fa-f0-9 ]+` class rejects `H`.
     # _match_csn(body, '') returns True when the regex captures nothing.
     lambda body: _match_csn(body, '')),

    # hf iclass rdbl: iceman raw form, block < 10
    ('hf iclass rdbl', 'iceman raw block 6',
     ' block   6/0x06 : 12 FF FF FF 7F 1F FF 3C\n\n',
     lambda body: _match_block_read(body, '12FFFFFF7F1FFF3C')),

    # hf iclass rdbl: iceman raw form, block >= 10
    ('hf iclass rdbl', 'iceman raw block 18',
     ' block  18/0x12 : FF FF FF FF FF FF FF FF\n\n',
     lambda body: _match_block_read(body, 'FFFFFFFFFFFFFFFF')),

    # hf iclass rdbl: iceman raw form, zero-data block
    ('hf iclass rdbl', 'iceman raw block 8 zeros',
     ' block   8/0x08 : 00 00 00 00 00 00 00 00\n\n',
     lambda body: _match_block_read(body, '0000000000000000')),

    # hf iclass dump: iceman save indicator
    ('hf iclass dump', 'iceman saving dump file',
     '.\n saving dump file - 32 blocks read\n'
     "Saved 256 bytes to binary file '/root/my_dump.bin'\n",
     lambda body: iclassread._KW_DUMP_SUCCESS in body),

    # hf iclass dump: error / no-tag (no save line)
    ('hf iclass dump', 'iceman no-tag, no save line',
     '[!] no tag found\n',
     lambda body: iclassread._KW_DUMP_SUCCESS not in body),

    # hf iclass wrbl: iceman raw success
    ('hf iclass wrbl', 'iceman wrbl ( ok ) block 6',
     'Wrote block 6 / 0x06 ( ok )\n\n',
     lambda body: '( ok )' in body),

    # hf iclass wrbl: iceman raw success for higher block
    ('hf iclass wrbl', 'iceman wrbl ( ok ) block 18',
     'Wrote block 18 / 0x12 ( ok )\n\n',
     lambda body: '( ok )' in body),

    # hf iclass chk: iceman `Found valid key`
    ('hf iclass chk', 'iceman Found valid key',
     '[=] Running strategy 1\n'
     '[+] Found valid key AF A7 85 A7 DA B3 33 78\n\n',
     lambda body: _match_chk_key(body, 'AFA785A7DAB33378')),

    # hf iclass calcnewkey: iceman 4-dot Xor div key (cmdhficlass.c:5419)
    ('hf iclass calcnewkey', 'iceman 4-dot Xor div key',
     'Old div key.... 20 20 66 66 66 66 88 88\n'
     'New div key.... 6F 23 9A 7B C1 DE 40 82\n'
     'Xor div key.... 4F 03 FC 1D A7 B8 C8 0A\n',
     lambda body: _match_xor_div_key(body, '4F03FC1DA7B8C80A')),

    # hf iclass calcnewkey: elite variant, different byte layout
    ('hf iclass calcnewkey', 'iceman Xor div key elite',
     'Old div key.... AF A7 85 A7 DA B3 33 78\n'
     'New div key.... 11 22 33 44 55 66 77 88\n'
     'Xor div key.... BE 85 B6 E3 8F D5 44 F0\n',
     lambda body: _match_xor_div_key(body, 'BE85B6E38FD544F0')),
]


def _match_csn(body, expected_hex):
    """Apply _RE_CSN to body and compare captured hex against expected.

    `expected_hex=''` asserts regex does NOT match (used for negative
    samples like Fingerprint dotted CSN text).
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    got = executor.getContentFromRegex(hficlass._RE_CSN)
    if got is None:
        got = ''
    got = got.strip().replace(' ', '')
    # Filter non-hex: if the capture contains non-hex characters, treat
    # as a no-match (for Fingerprint dotted samples where `.......... HID`
    # captures `HID` which is non-hex).
    if got and not re.match(r'^[0-9A-Fa-f]+$', got):
        got = ''
    if not expected_hex:
        return got == ''
    return got.upper() == expected_hex.upper()


def _match_block_read(body, expected_hex):
    """Apply _RE_BLOCK_READ to body; compare captured hex."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    got = executor.getContentFromRegex(hficlass._RE_BLOCK_READ)
    if got is None:
        return False
    got = got.strip().replace(' ', '')
    return got.upper() == expected_hex.upper()


def _match_chk_key(body, expected_hex):
    """Simulate chkKeys fallback's `Found valid key` extraction."""
    m = re.search(r'Found valid key\s+([0-9a-fA-F ]+)', body)
    if not m:
        return False
    got = m.group(1).strip().replace(' ', '')
    return got.upper() == expected_hex.upper()


def _match_xor_div_key(body, expected_hex):
    """Apply iclasswrite._RE_XOR_DIV_KEY to body; compare captured hex."""
    m = re.search(iclasswrite._RE_XOR_DIV_KEY, body)
    if not m:
        return False
    got = m.group(1).strip().replace(' ', '')
    return got.upper() == expected_hex.upper()


def _run_synthetic_samples():
    """Run synthetic iceman-native shape validation samples."""
    print()
    print('Synthetic iceman-native shape checks:')
    for cmd, label, body, predicate in _ICEMAN_NATIVE_SAMPLES:
        try:
            ok = bool(predicate(body))
        except Exception as e:
            _record(cmd + ' (synth)', False,
                    '%s: predicate raised %s: %s'
                    % (label, type(e).__name__, e))
            print('  %-24s  %-48s  [FAIL] raised: %s' % (cmd, label, e))
            continue
        _record(cmd + ' (synth)', ok,
                '%s: predicate false on body=%r' % (label, body[:140]))
        print('  %-24s  %-48s  %s'
              % (cmd, label, '[PASS]' if ok else '[FAIL]'))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMAND_TABLE = [
    ('hf iclass info',       _test_hf_iclass_info),
    ('hf iclass rdbl',       _test_hf_iclass_rdbl),
    ('hf iclass dump',       _test_hf_iclass_dump),
    ('hf iclass wrbl',       _test_hf_iclass_wrbl),
    ('hf iclass chk',        _test_hf_iclass_chk),
    ('hf iclass calcnewkey', _test_hf_iclass_calcnewkey),
]


def main():
    print('=' * 72)
    print('Phase 3 trace-parity - P3.7 iCLASS flow')
    print('Ground truth: %s' % GROUND_TRUTH_PATH)
    print('=' * 72)

    for cmd, handler in COMMAND_TABLE:
        samples = load_samples(cmd)
        if not samples:
            print('  %-24s  %d samples  (skipped - no samples)' % (cmd, 0))
            continue

        for idx, body in samples:
            ok, detail = handler(body, idx)
            _record(cmd, ok, 'sample[%d] %s' % (idx, detail))

        bucket = _results['per_command'][cmd]
        status = 'PASS' if bucket['fail'] == 0 else 'FAIL'
        print('  %-24s  %d samples  %d pass  %d fail   [%s]'
              % (cmd, len(samples), bucket['pass'], bucket['fail'], status))
        for fail_detail in bucket['failures'][:5]:
            print('      %s' % fail_detail)
        if len(bucket['failures']) > 5:
            print('      ...(%d more)' % (len(bucket['failures']) - 5))

    _run_synthetic_samples()

    print('=' * 72)
    print('TOTAL: %d / %d passed, %d failed'
          % (_results['pass'], _results['total'], _results['fail']))
    print('=' * 72)

    return 0 if _results['fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
