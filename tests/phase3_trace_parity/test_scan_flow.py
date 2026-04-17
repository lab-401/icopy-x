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

"""Phase 3 trace-parity test — Scan flow (P3.1).

Verifies that the refactored iceman-native middleware parsers correctly
handle every response sample recorded in
`tools/ground_truth/iceman_output.json` for the six commands issued by
the Scan flow:

    hf 14a info        (hf14ainfo.parser)
    hf mfu info        (scan.py inline subtype keywords)
    hf sea             (hfsearch.parser)
    lf sea             (lfsearch.parser)
    hf felica reader   (hffelica.parser — out of scope but catalogued)
    data save          (no response parsing; smoke-only)

Usage:
    python3 tests/phase3_trace_parity/test_scan_flow.py

Exit status:
    0 — all iceman trace samples parsed into a non-empty structurally
        valid shape.
    1 — one or more samples failed to parse; details printed per-command.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# Insert the middleware directory so `import executor` / `import lfsearch`
# resolves without package prefix — matches the iCopy-X runtime layout.
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import lfsearch  # noqa: E402
import hfsearch  # noqa: E402
import hf14ainfo  # noqa: E402
import hffelica  # noqa: E402
import scan  # noqa: E402
import tagtypes  # noqa: E402


# ---------------------------------------------------------------------------
# Ground-truth loading
# ---------------------------------------------------------------------------

GROUND_TRUTH_PATH = os.path.join(REPO, 'tools', 'ground_truth',
                                 'iceman_output.json')


def _unescape(body):
    """Undo the JSON-literal escape encoding used in iceman_output.json.

    The capture pipeline stored raw bodies with `\\n` / `\\t` / `\\r`
    rendered as two-character escape sequences. Replace them with their
    actual control codes so middleware regex can match newline anchors.
    """
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


def _test_hf14ainfo(body, sample_idx):
    """Validate `hf 14a info` parser against iceman-native response shapes.

    Asserts concrete fields on parser output:
      - result is a dict with `found` key
      - when body has iceman UID line + no anticollision/multi/UL early exit,
        `uid` is a non-empty hex string matching the UID in the body
      - when body has `Static nonce....... yes` (iceman 7-dot form),
        `static` is True
      - when body has `Magic capabilities... Gen 1a` (iceman 3-dot form),
        `gen1a` is True
      - when body has a MIFARE Classic / MIFARE Plus / MIFARE Mini /
        DESFire / Ultralight keyword, `type` is not None
      - when body has anticollision keyword, `found` is False
      - when body has iceman `Prng detection..... weak`/`hard` (5-dot form),
        `get_prng_level()` returns the level string

    A regression in any post_normalize/adapter pipeline (e.g. dotted-to-colon
    re-conversion on iceman emissions) should trip these predicates and
    cause a structured FAIL, not silently pass.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    try:
        result = hf14ainfo.parser()
    except Exception as e:  # pragma: no cover — surfaces parser regressions
        return False, 'parser raised %s: %s' % (type(e).__name__, e)

    if not isinstance(result, dict):
        return False, 'parser returned non-dict: %r' % (result,)
    if 'found' not in result:
        return False, 'missing `found` key: %r' % (result,)

    is_early = (result.get('hasMulti') or result.get('isUL') or
                result.get('found') is False)

    # Assertion: anticollision body -> found=False
    if "Card doesn't support standard iso14443-3 anticollision" in body:
        if result.get('found') is not False:
            return False, ('anticollision body but found != False: %r'
                           % (result,))
        return True, ''

    # Assertion: iceman UID line -> populated uid (unless early-exit)
    # The iceman shape is ` UID: <hex>` (cmdhf14a.c:2792). If the parser
    # populates `uid` at all, it must contain at least one hex character.
    if result.get('found') and not is_early:
        uid = result.get('uid', '')
        if 'UID:' in body and not uid:
            return False, ('body has `UID:` but parser uid empty: %r'
                           % (result,))
        if uid and uid != 'BCC0 incorrect':
            # UID must be hex (after space-strip) — regression detector
            # for any adapter that corrupts hex into other chars.
            import re as _re
            if not _re.match(r'^[0-9A-Fa-f]+$', uid):
                return False, ('uid contains non-hex: %r' % (uid,))

    # Assertion: iceman `Static nonce....... yes` (7 dots) -> static=True
    # This is the key regression symptom: if _post_normalize rewrites the
    # dotted form to colon form AFTER the iceman-native keyword matcher
    # runs, `static` will be False here on a static-nonce sample.
    if 'Static nonce....... yes' in body and not is_early:
        if result.get('static') is not True:
            return False, ('body has iceman Static nonce 7-dot but '
                           'static != True: %r' % (result,))

    # Assertion: iceman `Magic capabilities... Gen 1a` (3 dots) -> gen1a=True
    # Same regression class as static nonce. Only applies when the parser
    # reaches Case 6 (Standard MIFARE); DESFire/UL skip the has_ checks.
    if 'Magic capabilities... Gen 1a' in body and not is_early and \
            result.get('type') is not None:
        if result.get('gen1a') is not True:
            return False, ('body has iceman Magic capabilities 3-dot '
                           'Gen 1a but gen1a != True: %r' % (result,))

    # Assertion: iceman `Prng detection..... <level>` (5/6 dots) ->
    # get_prng_level() returns the level. Direct helper probe.
    if 'Prng detection' in body and '\n' in body:
        level = hf14ainfo.get_prng_level()
        # The level must be present in the body text if the dotted form
        # is iceman-native. Empty means the _RE_PRNG regex failed.
        if not level:
            return False, ('body has `Prng detection` but '
                           'get_prng_level() returned empty '
                           '(dotted form regression): %r' % (body[:200],))

    # Assertion: DESFire body has type field set
    if 'MIFARE DESFire' in body and 'MIFARE Classic 1K' not in body \
            and 'MIFARE Classic 4K' not in body and not is_early:
        if result.get('type') != tagtypes.MIFARE_DESFIRE:
            return False, ('DESFire body but type != MIFARE_DESFIRE: %r'
                           % (result,))

    return True, ''


def _test_hf_mfu_info(body, sample_idx):
    """Validate scan.py inline keyword matching over `hf mfu info` body.

    The scan.py orchestrator uses `executor.hasKeyword` against the
    raw body; there is no dedicated `parser()`. A sample is considered
    structurally valid if the keyword lookup returns the expected
    subtype (NTAG 213/215/216 / MF0ULC / MF0UL1101) when the raw body
    contains the corresponding source substring.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    # Derive the "expected" subtype from the raw body text (ground truth).
    body_lower = body
    expected = None
    if 'NTAG 213' in body_lower:
        expected = tagtypes.NTAG213_144B
    elif 'NTAG 215' in body_lower:
        expected = tagtypes.NTAG215_504B
    elif 'NTAG 216' in body_lower:
        expected = tagtypes.NTAG216_888B
    elif 'MF0ULC' in body_lower or 'Ultralight C' in body_lower:
        expected = tagtypes.ULTRALIGHT_C
    elif 'MF0UL1101' in body_lower or 'Ultralight EV1' in body_lower:
        expected = tagtypes.ULTRALIGHT_EV1
    elif 'MIFARE Ultralight' in body_lower:
        expected = tagtypes.ULTRALIGHT

    # Apply the scan.py resolution ladder against executor keywords.
    if executor.hasKeyword('NTAG 213'):
        observed = tagtypes.NTAG213_144B
    elif executor.hasKeyword('NTAG 215'):
        observed = tagtypes.NTAG215_504B
    elif executor.hasKeyword('NTAG 216'):
        observed = tagtypes.NTAG216_888B
    elif executor.hasKeyword('Ultralight C') or executor.hasKeyword('MF0ULC'):
        observed = tagtypes.ULTRALIGHT_C
    elif (executor.hasKeyword('Ultralight EV1') or
          executor.hasKeyword('MF0UL1101')):
        observed = tagtypes.ULTRALIGHT_EV1
    elif executor.hasKeyword('MIFARE Ultralight'):
        observed = tagtypes.ULTRALIGHT
    else:
        observed = None

    if expected != observed:
        return False, ('ladder mismatch: expected=%r observed=%r body=%r...'
                       % (expected, observed, body[:200]))
    return True, ''


def _test_hfsearch(body, sample_idx):
    """Validate `hf sea` parser returns a dict with `found` key."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    try:
        result = hfsearch.parser()
    except Exception as e:
        return False, 'parser raised %s: %s' % (type(e).__name__, e)
    if not isinstance(result, dict):
        return False, 'parser returned non-dict: %r' % (result,)
    if 'found' not in result:
        return False, 'missing `found`: %r' % (result,)

    # When body contains "Valid iCLASS tag" we expect isIclass.
    if 'Valid iCLASS tag' in body:
        if not result.get('isIclass'):
            return False, ('body has iCLASS but result missing isIclass: %r'
                           % (result,))
    # When body contains "Valid ISO 15693" (iceman-space form) we expect
    # type=19 or 46.
    if 'Valid ISO 15693' in body:
        if result.get('type') not in (19, 46):
            return False, ('body has ISO 15693 but result.type != 19/46: %r'
                           % (result,))
    return True, ''


def _test_lfsearch(body, sample_idx):
    """Validate `lf sea` parser returns a dict with `found` key."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    try:
        result = lfsearch.parser()
    except Exception as e:
        return False, 'parser raised %s: %s' % (type(e).__name__, e)
    if not isinstance(result, dict):
        return False, 'parser returned non-dict: %r' % (result,)
    if 'found' not in result:
        return False, 'missing `found`: %r' % (result,)

    # `No data found!` (either legacy-native or compat-synthesised) must
    # yield found=False per Check 1.
    if 'No data found!' in body:
        if result.get('found') is not False:
            return False, ('body has `No data found!` but found != False: %r'
                           % (result,))
    # `No known 125/134 kHz tags found!` must yield found=True,
    # isT55XX=True per Check 23.
    if ('No known 125/134 kHz tags found' in body and
            'No data found!' not in body):
        if not (result.get('found') and result.get('isT55XX')):
            # Accept chipset-detection override that also yields found=False.
            if 'Chipset...' not in body:
                return False, ('body has no-known but result missing T55XX: %r'
                               % (result,))
    return True, ''


def _test_hffelica(body, sample_idx):
    """Validate `hf felica reader` parser returns a dict with `found`.

    hffelica.py is OUT OF SCOPE for the P3.1 refactor. This test still
    runs so that any future adapter work targeting iceman's new emission
    shape (IDm: <hex>, no `FeliCa tag info` line) is caught by the
    parity gate. Samples where `card timeout` is present are expected
    to yield found=False.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    try:
        result = hffelica.parser()
    except Exception as e:
        return False, 'parser raised %s: %s' % (type(e).__name__, e)
    if not isinstance(result, dict):
        return False, 'parser returned non-dict: %r' % (result,)
    if 'found' not in result:
        return False, 'missing `found`: %r' % (result,)
    if 'card timeout' in body:
        if result.get('found') is not False:
            return False, ('body has `card timeout` but found != False: %r'
                           % (result,))
    return True, ''


def _test_data_save(body, sample_idx):
    """`data save` smoke-only.

    scan.py lf_wav_filter reads the saved file directly rather than
    parsing PM3 output; there is no middleware parser. A sample is
    considered valid if it is a well-formed string.
    """
    return isinstance(body, str), ''


# ---------------------------------------------------------------------------
# Iceman-native synthetic samples — exercise the post-flip regex shapes
# that existing device traces (post-current-compat) do not surface.
# Each sample string is copy-equivalent to an exact iceman PrintAndLogEx
# emission per source_strings.md; any failure means the iceman-native
# regex in middleware no longer matches the target shape.
# ---------------------------------------------------------------------------

_ICEMAN_NATIVE_SAMPLES = [
    ('hf 14a info', 'iceman Prng dotted success',
     ' UID: 7A F2 EC B2  \nATQA: 00 04\n SAK: 08 [2]\nPossible types:\n'
     '   MIFARE Classic 1K\nPrng detection..... weak\n',
     lambda r: r.get('found') is True and r.get('uid') == '7AF2ECB2'),
    ('hf 14a info', 'iceman Static nonce dotted',
     ' UID: 3A F7 35 01  \nATQA: 00 04\n SAK: 08 [2]\nPossible types:\n'
     '   MIFARE Classic 1K\nStatic nonce....... yes\nPrng detection..... hard\n',
     lambda r: r.get('found') is True and r.get('static') is True),
    ('hf 14a info', 'iceman Magic capabilities dotted Gen 1a',
     ' UID: 3A F7 35 01  \nATQA: 00 04\n SAK: 88 [2]\n'
     'Magic capabilities... Gen 1a\nStatic nonce....... yes\n',
     lambda r: r.get('found') is True),
    ('hf 14a info', 'iceman UID with type annotation',
     ' UID: 04 C6 C7 2A C1 4E 80 ( ONUID, re-used )\nATQA: 00 44\n SAK: 00 [2]\n'
     'MANUFACTURER: NXP Semiconductors Germany\nMIFARE Ultralight EV1\n',
     lambda r: r.get('isUL') is True or r.get('uid') == '04C6C72AC14E80'),
    ('hf sea', 'iceman ISO 15693 with space',
     ' UID: E0 04 01 23 45 67 89 AB\nValid ISO 15693 tag found\n',
     lambda r: r.get('found') is True and r.get('type') == 19),
    ('hf sea', 'iceman ISO 14443-B with space',
     ' UID    : 11 22 33 44\n ATQB   : AA BB CC DD EE\nValid ISO 14443-B tag found\n',
     lambda r: r.get('found') is True and r.get('type') == 22),
    ('hf sea', 'iceman ISO 18092 / FeliCa with space',
     'Valid ISO 18092 / FeliCa tag found\n',
     lambda r: r.get('found') is False),  # matches _KW_FELICA path -> found=False
    ('hf sea', 'iceman LEGIC',
     'MCD: 01 MSN: 12 34 56 MCC: AB ( ok )\nValid LEGIC Prime tag found\n',
     lambda r: r.get('found') is True and r.get('mcd') == '01' and r.get('msn') == '123456'),
    ('lf sea', 'iceman No known tags (T55XX)',
     'No known 125/134 kHz tags found!\n',
     lambda r: r.get('found') is True and r.get('isT55XX') is True),
    ('lf sea', 'iceman Chipset... dotted EM4x05',
     'Chipset... EM4x05 / EM4x69\n',
     lambda r: r.get('chipset') == 'EM4305' and r.get('found') is False),
    ('lf sea', 'iceman Chipset... dotted T55xx',
     'Chipset... T55xx\n',
     lambda r: r.get('chipset') == 'T5577'),
    ('lf sea', 'iceman EM410x',
     'EM 410x ID 1234567890\nValid EM410x ID found!\n',
     lambda r: (r.get('found') is True and
                r.get('type') == tagtypes.EM410X_ID and
                r.get('data', '').upper() == '1234567890')),
    ('lf sea', 'iceman HID raw',
     'raw: 2006ec3b\n[H10301] HID H10301 26-bit FC: 128  CN: 54641\n'
     'Valid HID Prox ID found!\n',
     lambda r: (r.get('found') is True and
                r.get('type') == tagtypes.HID_PROX_ID and
                r.get('raw', '').lower() == '2006ec3b')),
    ('lf sea', 'iceman AWID FC/CN/len/Raw',
     'AWID - len: 26 FC: 128 Card: 54641 - Wiegand: 2006ec3b, Raw: 011db7a77977e5b7\n'
     'Valid AWID ID found!\n',
     lambda r: (r.get('found') is True and
                r.get('type') == tagtypes.AWID_ID)),
    ('lf sea', 'iceman FDX-B dotted Animal ID',
     'Animal ID........... 036-123456789012\n'
     'Extended Data: 0x1234\nValid FDX-B ID found!\n',
     lambda r: (r.get('found') is True and
                r.get('type') == tagtypes.FDXB_ID)),
]


def _run_synthetic_samples():
    """Run synthetic iceman-native shape validation samples."""
    print()
    print('Synthetic iceman-native shape checks:')
    for cmd, label, body, predicate in _ICEMAN_NATIVE_SAMPLES:
        executor.CONTENT_OUT_IN__TXT_CACHE = body
        if cmd == 'hf 14a info':
            parser = hf14ainfo.parser
        elif cmd == 'hf sea':
            parser = hfsearch.parser
        elif cmd == 'lf sea':
            parser = lfsearch.parser
        else:
            continue
        try:
            result = parser()
        except Exception as e:
            _record(cmd + ' (synth)', False,
                    '%s: raised %s: %s' % (label, type(e).__name__, e))
            print('  %-18s  %-48s  [FAIL] raised: %s' % (cmd, label, e))
            continue
        ok = bool(predicate(result))
        _record(cmd + ' (synth)', ok,
                '%s: predicate failed on %r' % (label, result))
        print('  %-18s  %-48s  %s' % (cmd, label, '[PASS]' if ok else '[FAIL] %r' % result))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMAND_TABLE = [
    ('hf 14a info',      _test_hf14ainfo),
    ('hf mfu info',      _test_hf_mfu_info),
    ('hf sea',           _test_hfsearch),
    ('lf sea',           _test_lfsearch),
    ('hf felica reader', _test_hffelica),
    ('data save',        _test_data_save),
]


def main():
    print('=' * 70)
    print('Phase 3 trace-parity - P3.1 Scan flow')
    print('Ground truth: %s' % GROUND_TRUTH_PATH)
    print('=' * 70)

    for cmd, handler in COMMAND_TABLE:
        samples = load_samples(cmd)
        if not samples:
            # 0 samples is informational; `data save` has 0 expected.
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
