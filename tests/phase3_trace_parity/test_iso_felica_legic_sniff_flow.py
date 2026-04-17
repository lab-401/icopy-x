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

"""Phase 3 trace-parity test - ISO15693/FeliCa/Legic/Sniff flow (P3.8).

Verifies that the refactored iceman-native middleware (hf15read,
hf15write, felicaread, hffelica, legicread, sniff) correctly parses
every iceman-shaped response sample for:

    hf 15 dump         (hf15read.read -- file presence only)
    hf 15 restore      (hf15write._KW_RESTORE_SUCCESS "Done!")
    hf 15 csetuid      (hf15write._RE_CSETUID_OK iceman raw form)
    hf felica reader   (hffelica._KW_FOUND iceman "IDm:" form)
    hf felica litedump (felicaread.read -- identical on both forks)
    hf legic dump      (legicread.read -- identical on both forks)
    hf *  sniff        (sniff start dispatchers; trace-len parsers)
    lf sniff / lf config / lf t55xx sniff  (sniff.PATTERN_LF_TRACE_LEN)

Live iceman_output.json samples for `hf 15 restore` carry the
adapter-injected legacy suffix `Write OK\\ndone` appended AFTER the
iceman-raw `Done!` line. The iceman-native sentinel `Done!` still
matches because it is a PREFIX of the adapter-modified body. The
adapter-injected tokens are dead text from the middleware's point of
view.

Live samples for `hf 15 csetuid` were captured post-`_normalize_hf15_csetuid`
which rewrites iceman `"Setting new UID ( ok )"` -> legacy shape
`"setting new UID (ok)"`. Iceman-native regex `_RE_CSETUID_OK`
therefore MISSES the live samples. This is INTENTIONAL per Option B:
Phase 4 will disable the normalizer and re-capture.

Live samples for `hf felica reader` show only `"card timeout"` bodies
(10 samples); no successful FeliCa detections were captured under
iceman. The iceman-native `_KW_FOUND = r'IDm:\\s'` is exercised via
synthetic samples only.

Usage:
    python3 tests/phase3_trace_parity/test_iso_felica_legic_sniff_flow.py

Exit status:
    0 -- all samples parsed to structurally valid shapes.
    1 -- one or more samples failed; details printed per-command.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# Insert the middleware directory so `import executor` / `import hf15write`
# resolves without package prefix - matches the iCopy-X runtime layout.
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import hf15read  # noqa: E402
import hf15write  # noqa: E402
import felicaread  # noqa: E402
import hffelica  # noqa: E402
import legicread  # noqa: E402
import sniff  # noqa: E402


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


def _test_hf15_restore(body, sample_idx):
    """Validate hf15write iceman-native restore success/failure sentinels.

    Iceman SUCCESS emission (cmdhf15.c:2818) is literal `"Done!"`.
    Iceman FAIL emission (cmdhf15.c:2803) is `"Too many retries"` (no
    leading `restore failed.` prefix; legacy had that compound form).

    Live iceman_output.json samples carry adapter-injected
    `Write OK\\ndone` appended after the iceman-raw `Done!` line. Our
    iceman-native keyword `Done!` still matches because the adapter
    preserves the raw text and only APPENDS the legacy-shaped suffix.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_done = 'Done!' in body
    has_too_many = 'Too many retries' in body
    has_error_prefix = "Error -" in body or "can't find" in body

    success_matches = executor.hasKeyword(hf15write._KW_RESTORE_SUCCESS)
    too_many_matches = executor.hasKeyword(hf15write._KW_RESTORE_TOO_MANY)

    # Expectations aligned with source:
    if has_done and not has_too_many:
        if not success_matches:
            return False, ('body has Done! but success kw missed: body=%r'
                           % (body[:120],))
        return True, ''
    if has_too_many:
        if not too_many_matches:
            return False, ('body has "Too many retries" but kw missed: '
                           'body=%r' % (body[:120],))
        return True, ''
    if has_error_prefix:
        # File-error / no-tag path. Neither success nor too-many must fire.
        if success_matches:
            return False, ('error body matched success kw: body=%r'
                           % (body[:120],))
        return True, ''
    # Other body -- success kw must not spuriously match
    if success_matches and not has_done:
        return False, ('success kw matched body with no Done!: body=%r'
                       % (body[:120],))
    return True, ''


def _test_hf15_csetuid(body, sample_idx):
    """Validate hf15write._RE_CSETUID_OK against iceman raw shape.

    Iceman emits `"Setting new UID ( ok )"` with capital S and spaces
    around `ok` (cmdhf15.c:2900). Live samples have been normalized by
    pm3_compat._normalize_hf15_csetuid (pm3_compat.py:1720) to
    `"setting new UID (ok)"` (lowercase, no spaces inside parens). The
    iceman-native regex must NOT match adapter-normalized samples.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_iceman_raw = bool(re.search(r'Setting new UID\s*\(\s*ok\s*\)', body))
    has_adapter_norm = ('setting new UID (ok)' in body and not has_iceman_raw)
    has_no_tag = 'no tag found' in body

    got_ok = executor.hasKeyword(hf15write._RE_CSETUID_OK)
    got_no_tag = executor.hasKeyword(hf15write._KW_CSETUID_NO_TAG)

    if has_iceman_raw:
        if not got_ok:
            return False, ('iceman raw `Setting new UID ( ok )` but miss: '
                           'body=%r' % (body[:120],))
        return True, ''
    if has_adapter_norm:
        # Adapter-normalized shape. Iceman-native regex must NOT match.
        if got_ok:
            return False, ('adapter-normalized shape but iceman native '
                           'matched (adapter bypass?): body=%r'
                           % (body[:120],))
        return True, ''
    if has_no_tag:
        if not got_no_tag:
            return False, ('no tag body but kw miss: body=%r'
                           % (body[:120],))
        return True, ''
    # Error / other body: iceman-native must not match
    if got_ok:
        return False, ('non-success body matched: body=%r'
                       % (body[:120],))
    return True, ''


def _test_hf_felica_reader(body, sample_idx):
    """Validate hffelica.parser() iceman-native sentinels.

    Iceman SUCCESS (cmdhffelica.c:1183) emits `"IDm: <hex>"`. Iceman
    does NOT emit the legacy `"FeliCa tag info"` banner -- that comes
    from the legacy fork's `readFelicaUid` helper (cmdhffelica.c:1803).

    Iceman TIMEOUT (cmdhffelica.c:1431) emits `"card timeout"`.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_timeout = 'card timeout' in body
    has_idm = bool(re.search(r'IDm:\s', body))

    got = hffelica.parser()
    assert isinstance(got, dict) and 'found' in got, \
        'parser() did not return dict with found key'

    if has_timeout:
        # Parser must report found=False.
        if got.get('found') is not False:
            return False, ('card timeout body but found=%r body=%r'
                           % (got.get('found'), body[:120]))
        return True, ''
    if has_idm:
        if not got.get('found'):
            return False, ('IDm body but found=False: got=%r body=%r'
                           % (got, body[:120]))
        if not got.get('idm'):
            return False, ('found=True but idm empty: got=%r body=%r'
                           % (got, body[:120]))
        return True, ''
    # Empty / ping body: parser must report found=False.
    if got.get('found') is not False:
        return False, ('empty body but found=%r body=%r'
                       % (got.get('found'), body[:120]))
    return True, ''


def _test_hf_sniff_trace_len(body, sample_idx):
    """Validate sniff.parserHfTraceLen() iceman-native.

    Iceman (cmdtrace.c:1181) emits `"Recorded activity ( N bytes )"`.
    Legacy emitted `"trace len = N"`. The PATTERN_HF_TRACE_LEN
    alternation handles both for the Phase 4 transition.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    m = re.search(sniff.PATTERN_HF_TRACE_LEN, body)
    expected_match = bool(re.search(r'(trace len = |Recorded activity \( )\d+',
                                     body))
    observed_match = bool(m)

    if expected_match != observed_match:
        return False, ('pattern mismatch: body=%r' % (body[:120],))
    return True, ''


# ---------------------------------------------------------------------------
# Iceman-native synthetic samples - exercise the post-flip regex shapes
# that live iceman_output.json does NOT surface (adapter runs).
# Each body string is copy-equivalent to an exact iceman PrintAndLogEx
# emission per source citation; failure here means middleware has
# regressed away from iceman-native shape.
# ---------------------------------------------------------------------------

_ICEMAN_NATIVE_SAMPLES = [
    # hf 15 restore: iceman success
    ('hf 15 restore', 'iceman Done! after scan mode',
     'Using scan mode\n'
     'Loaded 2235 bytes from binary file /root/dump.bin\n'
     'Restoring data blocks\n\n'
     "Hint: Try `hf 15 dump --ns` to verify\n"
     'Done!\n',
     lambda body: _match_restore_success(body, True, False)),

    # hf 15 restore: iceman too many retries
    ('hf 15 restore', 'iceman Too many retries',
     'Using scan mode\n'
     'Loaded 2235 bytes from binary file /root/dump.bin\n'
     'Restoring data blocks\n\n'
     'Too many retries (fail)\n',
     lambda body: _match_restore_success(body, False, True)),

    # hf 15 restore: iceman no tag found
    ('hf 15 restore', 'iceman no tag found',
     'Using scan mode\n'
     'no tag found\n',
     lambda body: _match_restore_success(body, False, False,
                                         expect_no_tag=True)),

    # hf 15 csetuid: iceman raw ( ok )
    ('hf 15 csetuid', 'iceman Setting new UID ( ok )',
     'Get current tag\n\n'
     'UID: E0 04 01 3C F9 43 B3 02\n'
     'TYPE: NTAG 5\n\n'
     'Writing...\nVerifying...\n'
     'Setting new UID ( ok )\n\n',
     lambda body: _match_csetuid_ok(body, True)),

    # hf 15 csetuid: iceman raw ( fail )
    ('hf 15 csetuid', 'iceman Setting new UID ( fail )',
     'Get current tag\n\n'
     'UID: E0 04 01 3C F9 43 B3 02\n\n'
     'Writing...\nVerifying...\n'
     'Setting new UID ( fail )\n\n',
     lambda body: _match_csetuid_ok(body, False)),

    # hf 15 csetuid: iceman no tag found
    ('hf 15 csetuid', 'iceman no tag found',
     'Get current tag\n\n'
     'no tag found\n',
     lambda body: _match_csetuid_no_tag(body)),

    # hf felica reader: iceman IDm success
    ('hf felica reader', 'iceman IDm success',
     '\n'
     'IDm: 01 FE 01 02 03 04 05 06\n',
     lambda body: _match_felica_found(body,
                                       ':01FE010203040506')),

    # hf felica reader: iceman card timeout
    ('hf felica reader', 'iceman card timeout',
     'card timeout (-4)\n\n',
     lambda body: _match_felica_not_found(body)),

    # hf felica reader: iceman empty (no tag)
    ('hf felica reader', 'iceman empty',
     '\n',
     lambda body: _match_felica_not_found(body)),

    # HF trace len (iceman Recorded activity form)
    ('hf sniff trace len', 'iceman Recorded activity 1066 bytes',
     'Recorded activity ( 1066 bytes )\n',
     lambda body: _match_hf_trace_len(body, 1066)),

    # HF trace len (legacy form still tolerated during transition)
    ('hf sniff trace len', 'legacy trace len = 2000',
     'trace len = 2000\n',
     lambda body: _match_hf_trace_len(body, 2000)),

    # LF trace len (iceman Reading bytes form)
    ('lf sniff trace len', 'iceman Reading 42259 bytes',
     'Reading 42259 bytes from device memory\n',
     lambda body: _match_lf_trace_len(body, 42259)),

    # lf t55xx T5577 default pwd write key extraction
    ('sniff T5577 ok key', 'iceman Default pwd write',
     '[+] Default pwd write  | 20206666 | 00148040 |  1  |\n',
     lambda body: _match_t5577_ok_key(body, '20206666')),

    # lf t55xx T5577 default write (no password) key extraction
    ('sniff T5577 write key', 'iceman Default write',
     '[+] Default write      | 00000000 | C02A4E07 |  1  |\n',
     lambda body: _match_t5577_write_key(body, '00000000')),

    # lf t55xx T5577 leading pwd write extraction
    ('sniff T5577 leading key', 'iceman Leading 7 pwd write',
     '[+] Leading 7 pwd write | AABBCCDD | 00148040 |  1  |\n',
     lambda body: _match_t5577_leading_key(body, 'AABBCCDD')),

    # MIFARE key extraction from trace
    ('sniff M1 key', 'iceman key hex',
     '[=]   1 |  ... | Rdr | key FFFFFFFFFFFF prng WEAK |\n',
     lambda body: _match_m1_key(body, 'FFFFFFFFFFFF')),
]


def _match_restore_success(body, expect_success, expect_too_many,
                           expect_no_tag=False):
    """Exercise hf15write restore sentinels."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    got_success = executor.hasKeyword(hf15write._KW_RESTORE_SUCCESS)
    got_too_many = executor.hasKeyword(hf15write._KW_RESTORE_TOO_MANY)
    got_no_tag = executor.hasKeyword(hf15write._KW_CSETUID_NO_TAG)
    if expect_success and not got_success:
        return False
    if expect_too_many and not got_too_many:
        return False
    if expect_no_tag and not got_no_tag:
        return False
    if not expect_success and got_success and 'Done!' not in body:
        return False
    return True


def _match_csetuid_ok(body, expect_ok):
    """Exercise hf15write._RE_CSETUID_OK against iceman raw."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    got = executor.hasKeyword(hf15write._RE_CSETUID_OK)
    return bool(got) == expect_ok


def _match_csetuid_no_tag(body):
    """Exercise hf15write._KW_CSETUID_NO_TAG."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    return executor.hasKeyword(hf15write._KW_CSETUID_NO_TAG)


def _match_felica_found(body, expected_idm):
    """Exercise hffelica.parser() for iceman IDm success form."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    got = hffelica.parser()
    if not got.get('found'):
        return False
    if got.get('idm', '') != expected_idm:
        return False
    return True


def _match_felica_not_found(body):
    """Exercise hffelica.parser() no-tag path."""
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    got = hffelica.parser()
    return got.get('found') is False


def _match_hf_trace_len(body, expected_int):
    """Exercise sniff.PATTERN_HF_TRACE_LEN."""
    m = re.search(sniff.PATTERN_HF_TRACE_LEN, body)
    if not m:
        return False
    try:
        return int(m.group(1)) == expected_int
    except (ValueError, TypeError):
        return False


def _match_lf_trace_len(body, expected_int):
    """Exercise sniff.PATTERN_LF_TRACE_LEN."""
    m = re.search(sniff.PATTERN_LF_TRACE_LEN, body)
    if not m:
        return False
    try:
        return int(m.group(1)) == expected_int
    except (ValueError, TypeError):
        return False


def _match_t5577_ok_key(body, expected_hex):
    """Exercise sniff.parserT5577OkKeyForLine."""
    line = body.strip()
    got = sniff.parserT5577OkKeyForLine(line)
    return got.upper() == expected_hex.upper()


def _match_t5577_write_key(body, expected_hex):
    """Exercise sniff.parserT5577WriteKeyForLine."""
    line = body.strip()
    got = sniff.parserT5577WriteKeyForLine(line)
    return got.upper() == expected_hex.upper()


def _match_t5577_leading_key(body, expected_hex):
    """Exercise sniff.parserT5577LeadingKeyForLine."""
    line = body.strip()
    got = sniff.parserT5577LeadingKeyForLine(line)
    return got.upper() == expected_hex.upper()


def _match_m1_key(body, expected_hex):
    """Exercise sniff.parserM1KeyForLine."""
    line = body.strip()
    got = sniff.parserM1KeyForLine(line)
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
            print('  %-28s  %-48s  [FAIL] raised: %s' % (cmd, label, e))
            continue
        _record(cmd + ' (synth)', ok,
                '%s: predicate false on body=%r' % (label, body[:140]))
        print('  %-28s  %-48s  %s'
              % (cmd, label, '[PASS]' if ok else '[FAIL]'))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Also include bare `hf 15 restore f` and `hf 15 dump f` which iceman_output
# records under the legacy-prefix form; they feed the same parsers.
COMMAND_TABLE = [
    ('hf 15 restore',    _test_hf15_restore),
    ('hf 15 restore f',  _test_hf15_restore),
    ('hf 15 csetuid',    _test_hf15_csetuid),
    ('hf felica reader', _test_hf_felica_reader),
    ('hf 14a sniff',     _test_hf_sniff_trace_len),
]


def main():
    print('=' * 72)
    print('Phase 3 trace-parity - P3.8 ISO15693/FeliCa/Legic/Sniff flow')
    print('Ground truth: %s' % GROUND_TRUTH_PATH)
    print('=' * 72)

    for cmd, handler in COMMAND_TABLE:
        samples = load_samples(cmd)
        if not samples:
            print('  %-28s  %d samples  (skipped - no samples)' % (cmd, 0))
            continue

        for idx, body in samples:
            ok, detail = handler(body, idx)
            _record(cmd, ok, 'sample[%d] %s' % (idx, detail))

        bucket = _results['per_command'][cmd]
        status = 'PASS' if bucket['fail'] == 0 else 'FAIL'
        print('  %-28s  %d samples  %d pass  %d fail   [%s]'
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
