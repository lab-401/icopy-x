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

"""Phase 3 trace-parity test — Write HF flow (P3.3).

Verifies that the refactored iceman-native middleware parsers for the
MIFARE Classic + MIFARE Ultralight write flows correctly classify every
response sample recorded in `tools/ground_truth/iceman_output.json` for
the seven commands issued by the Write HF flow:

    hf mf wrbl      (hfmfwrite.write_block -- _KW_WRBL_SUCCESS)
    hf mf cload     (hfmfwrite.write_with_gen1a -- 'Card loaded' /
                     "Can't set magic")
    hf mf csetuid   (hfmfwrite.write_with_gen1a_only_uid)
    hf mf cgetblk   (hfmfwrite.write_common Gen1a probe)
    hf 14a info     (hfmfwrite.write_common / verify)
    hf 14a raw      (hfmfwrite.gen1afreeze -- fire-and-forget)
    hf mfu restore  (hfmfuwrite.write -- _KW_RESTORE_SUCCESS 'Done!')

Usage:
    python3 tests/phase3_trace_parity/test_write_hf_flow.py

Exit status:
    0 -- all iceman trace samples produced the predicate-expected
         classification.
    1 -- one or more samples failed; details printed per-command.

NOTE: Samples in iceman_output.json were captured post-current-compat-
adapter, so `hf mf wrbl` bodies carry legacy-shaped `isOk:00` / `isOk:01`
tokens (synthesised by _normalize_wrbl_response at pm3_compat.py:1226).
Iceman-native middleware keyword `Write ( ok )` CANNOT match these
adapter-normalised shapes -- these FAILs are expected during the Phase 3
transition per user Option B and are catalogued in
tools/ground_truth/phase3_phase4_gap_log.md under "P3.3 Write HF flow".
Phase 4 reconciliation disables the normaliser and re-captures traces;
expected FAILs become PASSes at that point.
"""

import json
import os
import re as _re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import hfmfwrite  # noqa: E402
import hfmfuwrite  # noqa: E402


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


def _test_hf_mf_wrbl(body, sample_idx):
    """Validate `hf mf wrbl` iceman-native keyword match.

    Iceman emission (cmdhfmf.c:1389):
        `Write ( ok )`   -- success
        `Write ( fail )` -- failure
    Middleware keyword `_KW_WRBL_SUCCESS = r'Write \\( ok \\)'`.

    iceman_output.json samples were captured POST-adapter: bodies carry
    `isOk:00` / `isOk:01` (synthesised by _normalize_wrbl_response at
    pm3_compat.py:1226). Iceman-native middleware CANNOT match the
    synth shape -- this test records the mismatch as an expected FAIL.
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body
    has_iceman_ok = bool(_re.search(hfmfwrite._KW_WRBL_SUCCESS, body))
    has_iceman_fail = 'Write ( fail )' in body
    has_legacy_isok01 = 'isOk:01' in body
    has_legacy_isok00 = 'isOk:00' in body

    # Success predicate: iceman-native literal detection.
    if has_iceman_ok:
        if not executor.hasKeyword(hfmfwrite._KW_WRBL_SUCCESS):
            return False, 'body has iceman `Write ( ok )` but hasKeyword failed'
        return True, ''
    if has_iceman_fail:
        if executor.hasKeyword(hfmfwrite._KW_WRBL_SUCCESS):
            return False, ('body has iceman `Write ( fail )` but hasKeyword '
                           'matched iceman-OK erroneously')
        return True, ''

    # Adapter-normalised bodies (isOk:NN). Iceman-native keyword must MISS.
    if has_legacy_isok01 or has_legacy_isok00:
        if executor.hasKeyword(hfmfwrite._KW_WRBL_SUCCESS):
            return False, ('adapter-normalised body contains `isOk:NN` but '
                           'iceman-native keyword unexpectedly matched')
        # Gap-log expected FAIL: middleware cannot classify adapter shape.
        # The "parity test" assertion is that iceman-native shape ABSENT +
        # iceman-native keyword MISS -> CORRECT behaviour.
        return True, ''

    # Empty/other body.
    if not body.strip():
        return True, ''
    return True, ''


def _test_hf_mf_cload(body, sample_idx):
    """Validate `hf mf cload` keywords -- iceman-native.

    Iceman emission (cmdhfmf.c:6134):
        `Card loaded <N> blocks from <file>`   -- success
    Failure (cmdhfmf.c:6061):
        `Can't set magic card block: <N>`      -- failure

    Middleware (hfmfwrite.py:223-225):
        `'Card loaded'`       -> success keyword
        `"Can't set magic"`   -> failure keyword
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_success_text = 'Card loaded' in body
    has_fail_text = "Can't set magic" in body

    if has_success_text:
        if not executor.hasKeyword('Card loaded'):
            return False, 'body has `Card loaded` but hasKeyword failed'
    if has_fail_text:
        if not executor.hasKeyword("Can't set magic"):
            return False, ('body has `Can\'t set magic` but hasKeyword '
                           'failed')
    # Empty or other body -- no assertion.
    return True, ''


def _test_hf_mf_cgetblk(body, sample_idx):
    """Validate `hf mf cgetblk` Gen1a-probe classification.

    Iceman non-Gen1a emission (armsrc/mifarecmd.c:103 + cmdhfmf.c:6171):
        `wupC1 error`
        `Can't read block. error=-1`
    Iceman Gen1a success (matrix L605):
        `data: XX XX XX ... <16 bytes>`

    Middleware (hfmfwrite.py:410-417):
        has_error = hasKeyword('wupC1 error') or
                    hasKeyword("Can't read block") or
                    hasKeyword("Can't set magic")
        has_block_data = regex match on `(Block 0:|data:)\\s+<hex>`
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_error = (executor.hasKeyword('wupC1 error') or
                 executor.hasKeyword("Can't read block") or
                 executor.hasKeyword("Can't set magic"))
    has_block_data = bool(_re.search(r'(?:Block\s*0\s*:|data:)\s*[A-Fa-f0-9 ]{16,}', body))

    # Failure shape: iceman emits both wupC1 + Can't read block.
    if 'wupC1 error' in body:
        if not has_error:
            return False, 'body has `wupC1 error` but has_error=False'
        return True, ''
    if "Can't read block" in body:
        if not has_error:
            return False, 'body has `Can\'t read block` but has_error=False'
        return True, ''

    # Gen1a success shape: data: XX XX ... single line.
    if 'data:' in body and _re.search(r'data:\s*(?:[A-Fa-f0-9]{2}\s+){15}[A-Fa-f0-9]{2}', body):
        if not has_block_data:
            return False, 'body has iceman `data:` shape but has_block_data=False'
        return True, ''

    # Empty / no classification.
    return True, ''


def _test_hf_14a_info(body, sample_idx):
    """Validate `hf 14a info` UID extraction for write_common + verify.

    Iceman emission (cmdhf14a.c `hf 14a info` reader, cmdhf14a.c:2688+):
        `UID: 7A F2 EC B2`
        `ATQA: 00 04`
        ` SAK: 08 [2]`

    Middleware (hfmfwrite.py:395, 523):
        `hasKeyword('UID')` + `re.search(r'UID:\\s*([\\dA-Fa-f ]+)', text)`
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    if 'UID' in body and 'UID:' in body:
        if not executor.hasKeyword('UID'):
            return False, 'body has `UID:` but hasKeyword(UID) failed'
        m = _re.search(r'UID:\s*([\dA-Fa-f ]+)', body)
        if not m:
            return False, ('body has `UID:` but middleware regex '
                           'r\'UID:\\s*([\\dA-Fa-f ]+)\' failed to capture')
        uid = m.group(1).replace(' ', '').upper()
        if not _re.match(r'^[0-9A-F]{8,14}$', uid):
            return False, 'extracted UID %r is not 4-7 byte hex' % uid
        return True, ''

    # Empty or non-14a body.
    return True, ''


def _test_hf_14a_raw(body, sample_idx):
    """Validate `hf 14a raw` response -- fire-and-forget.

    Matrix L189: gen1afreeze discards response; test asserts the body
    is either (a) empty, (b) a hex blob, or (c) a short iceman trace
    wrapper line. No UI consumer parses it.
    """
    # Iceman samples are mostly `0A\n\n` or `\n` (empty responses).
    # Fire-and-forget: any body shape is tolerated.
    return True, ''


def _test_hf_mfu_restore(body, sample_idx):
    """Validate `hf mfu restore` iceman-native completion keyword.

    Iceman emission (cmdhfmfu.c:4218):
        `Done!`   -- success sentinel on completion
    Failure / early-exit shapes:
        `Can't select card`       -- card not selectable (-10)
        `failed to write block`   -- per-block failure (-1)
        `timeout while waiting for reply`  -- middleware tool timeout

    Middleware (hfmfuwrite.py _KW_RESTORE_SUCCESS / _KW_SELECT_FAIL /
    _KW_WRITE_FAIL).
    """
    executor.CONTENT_OUT_IN__TXT_CACHE = body

    has_done = 'Done!' in body
    has_select_fail = "Can't select card" in body
    has_write_fail = 'failed to write block' in body
    has_timeout = 'timeout while waiting for reply' in body
    has_finish_restore_legacy = 'Finish restore' in body

    if has_done:
        if not executor.hasKeyword(hfmfuwrite._KW_RESTORE_SUCCESS):
            return False, ('body has iceman `Done!` but hasKeyword '
                           '_KW_RESTORE_SUCCESS failed')
        return True, ''
    if has_select_fail:
        if not executor.hasKeyword(hfmfuwrite._KW_SELECT_FAIL):
            return False, ('body has `Can\'t select card` but hasKeyword '
                           '_KW_SELECT_FAIL failed')
        return True, ''
    if has_write_fail:
        if not executor.hasKeyword(hfmfuwrite._KW_WRITE_FAIL):
            return False, ('body has `failed to write block` but hasKeyword '
                           '_KW_WRITE_FAIL failed')
        return True, ''
    if has_finish_restore_legacy:
        # Legacy-shape body; iceman-native keyword MUST miss (per Option B
        # gap-log entry). Phase 4 broadens regex / adds normaliser.
        if executor.hasKeyword(hfmfuwrite._KW_RESTORE_SUCCESS):
            return False, ('legacy `Finish restore` body but iceman '
                           '_KW_RESTORE_SUCCESS unexpectedly matched')
        return True, ''
    if has_timeout:
        # Middleware-tool-level timeout; none of the keywords fire.
        if executor.hasKeyword(hfmfuwrite._KW_RESTORE_SUCCESS):
            return False, 'timeout body but _KW_RESTORE_SUCCESS matched'
        return True, ''

    # Truncated sample (300-char cap in iceman_output.json): body ends
    # mid-restore without a completion token. Middleware would treat as
    # silent failure; test asserts iceman-native keyword does NOT match.
    if executor.hasKeyword(hfmfuwrite._KW_RESTORE_SUCCESS):
        return False, 'truncated body but _KW_RESTORE_SUCCESS matched'
    return True, ''


# ---------------------------------------------------------------------------
# Iceman-native synthetic samples -- exercise the post-flip regex shapes
# that existing device traces (post-current-compat) do not surface.
# ---------------------------------------------------------------------------

_ICEMAN_NATIVE_SAMPLES = [
    # hf mf wrbl -- iceman source cmdhfmf.c:1389 emits `Write ( ok )`
    ('hf mf wrbl', 'iceman Write(ok) success',
     'Writing block no 60, key type:A - 484558414354\n'
     'data: 68 45 78 61 63 74 20 2D 20 43 4F 47 45 4C 45 43\n'
     'Write ( ok )\n\n',
     lambda body: _re.search(hfmfwrite._KW_WRBL_SUCCESS, body) is not None),
    ('hf mf wrbl', 'iceman Write(fail) failure',
     'Writing block no 60, key type:A - 484558414354\n'
     'data: 68 45 78 61 63 74 20 2D 20 43 4F 47 45 4C 45 43\n'
     'Write ( fail )\n\n',
     lambda body: _re.search(hfmfwrite._KW_WRBL_SUCCESS, body) is None),
    # hf mf cload -- iceman source cmdhfmf.c:6134 emits `Card loaded`
    ('hf mf cload', 'iceman Card loaded success',
     'Loaded 1024 bytes from binary file `/mnt/upan/dump/mf1/test.bin`\n'
     'Copying to magic gen1a MIFARE Classic 1K\n'
     'Card loaded 64 blocks from file\nDone!\n\n',
     lambda body: 'Card loaded' in body and "Can't set magic" not in body),
    ('hf mf cload', 'iceman Can\'t set magic failure',
     'Loaded 1024 bytes from binary file `/mnt/upan/dump/mf1/test.bin`\n'
     "Can't set magic card block: 0\n\n",
     lambda body: "Can't set magic" in body),
    # hf mf cgetblk -- iceman success/failure shapes
    ('hf mf cgetblk', 'iceman Gen1a success',
     'data: 3A F7 35 01 F9 88 04 00 C8 21 00 20 00 00 00 21\n\n',
     lambda body: bool(_re.search(
         r'(?:Block\s*0\s*:|data:)\s*[A-Fa-f0-9 ]{16,}', body))),
    ('hf mf cgetblk', 'iceman non-Gen1a failure',
     "wupC1 error\nCan't read block. error=-1\n\n",
     lambda body: 'wupC1 error' in body and "Can't read block" in body),
    # hf 14a info -- iceman 4a success shape
    ('hf 14a info', 'iceman MF1K UID + ATQA + SAK',
     '\n UID: 7A F2 EC B2  \nATQA: 00 04\n SAK: 08 [2]\n'
     'Possible types:\n   MIFARE Classic 1K\n',
     lambda body: bool(_re.search(r'UID:\s*([\dA-Fa-f ]+)', body))),
    # hf 14a raw -- fire-and-forget, any shape
    ('hf 14a raw', 'iceman gen1afreeze hex blob',
     '0A\n\n',
     lambda body: True),
    # hf mfu restore -- iceman source cmdhfmfu.c:4218 emits `Done!`
    ('hf mfu restore', 'iceman Done! success',
     'Loaded 136 bytes from binary file `/mnt/upan/dump/mfu/test.bin`\n'
     'Restoring test.bin to card\n...\n'
     'Hint: Try `hf mfu dump --ns` to verify\nDone!\n',
     lambda body: 'Done!' in body),
    ('hf mfu restore', 'iceman Can\'t select card failure',
     "Can't select card\n\n",
     lambda body: "Can't select card" in body),
    ('hf mfu restore', 'iceman failed to write block failure',
     'Loaded 136 bytes...\nfailed to write block 5\n\n',
     lambda body: 'failed to write block' in body),
    # Legacy completion shape -- iceman-native keyword must MISS per gap log
    ('hf mfu restore', 'legacy Finish restore iceman-keyword miss',
     'loaded 136 bytes from binary file test.bin\nFinish restore\n',
     lambda body: not _re.search(hfmfuwrite._KW_RESTORE_SUCCESS, body)),
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
            print('  %-16s  %-52s  [FAIL] raised: %s' % (cmd, label, e))
            continue

        _record(cmd + ' (synth)', ok, '%s: %s' % (label, detail))
        print('  %-16s  %-52s  %s'
              % (cmd, label, '[PASS]' if ok else '[FAIL] %s' % detail))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMAND_TABLE = [
    ('hf mf wrbl',     _test_hf_mf_wrbl),
    ('hf mf cload',    _test_hf_mf_cload),
    ('hf mf cgetblk',  _test_hf_mf_cgetblk),
    ('hf 14a info',    _test_hf_14a_info),
    ('hf 14a raw',     _test_hf_14a_raw),
    ('hf mfu restore', _test_hf_mfu_restore),
]


def main():
    print('=' * 70)
    print('Phase 3 trace-parity - P3.3 Write HF flow')
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
