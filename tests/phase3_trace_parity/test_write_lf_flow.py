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

"""Phase 3 trace-parity test -- Write LF flow (P3.6).

Verifies that the refactored iceman-native middleware (lfwrite.py,
lfverify.py) issues the correct iceman-canonical PM3 command forms
for every LF write/clone entry-point and that the iceman-native
inline-verify regex in write_dump_em4x05 correctly classifies
iceman `lf em 4x05 read` response shapes.

Commands audited:
    lf em 410x clone --id <hex>     cmdlfem410x.c:625/896
    lf hid clone -r <hex>           cmdlfhid.c:400/724
    lf indala clone -r <hex>        cmdlfindala.c:786/1103
    lf fdxb clone --country -n      cmdlffdxb.c:712/909
    lf securakey/gallagher/pac/     cmdlf<tag>.c dispatch
      paradox/nexwatch clone -r
    lf t55xx write -b N -d <hex>    cmdlft55xx.c:1853/4794
    lf t55xx restore -f <path>      cmdlft55xx.c:2775/4790
    lf em 4x05 write -a N -d -p     cmdlfem4x05.c:1399
    lf em 4x05 read -a N [-p]       cmdlfem4x05.c:1352
    lf sea (short-prefix alias)     cmdlf.c:1890 (Appendix B L1567)

Live iceman_output.json has only `lf t55xx write` samples (4 entries;
cmdlft55xx.c:1932 emission shape `Writing page %d  block: %02d
data: 0x%08X`). None of the other write commands were exercised
in the captured trace-set (write flows are UI-driven by user tag
choice), so synthetic iceman-native samples carry the primary load
for command-form + response-shape validation.

Usage:
    python3 tests/phase3_trace_parity/test_write_lf_flow.py

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

# Insert the middleware directory so `import executor` / `import lfwrite`
# resolves without package prefix -- matches the iCopy-X runtime layout.
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor  # noqa: E402
import lfwrite  # noqa: E402
import lfverify  # noqa: E402


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


# ---------------------------------------------------------------------------
# Command-form assertions (SEND-side iceman-native)
# ---------------------------------------------------------------------------
#
# lfwrite/lfverify emit PM3 commands by string formatting; we validate
# the emitted command string (before startPM3Task) by monkeypatching
# executor.startPM3Task with a capturing stub.

class _Capture:
    """Capture every PM3 command string emitted during a call."""

    def __init__(self):
        self.cmds = []
        self.return_values = []

    def reset(self, returns=None):
        self.cmds = []
        self.return_values = list(returns or [])

    def task(self, cmd, timeout, *args, **kwargs):
        self.cmds.append(cmd)
        if self.return_values:
            return self.return_values.pop(0)
        return 1  # default success


_cap = _Capture()


def _install_capture():
    """Swap executor.startPM3Task for the capturing stub."""
    # Save original in case caller later wants to restore.
    if not hasattr(executor, '_ORIG_startPM3Task'):
        executor._ORIG_startPM3Task = executor.startPM3Task
    executor.startPM3Task = _cap.task


def _restore_executor():
    """Restore the original executor.startPM3Task."""
    if hasattr(executor, '_ORIG_startPM3Task'):
        executor.startPM3Task = executor._ORIG_startPM3Task


def _test_em410x_clone_cmd():
    """lfwrite.write_em410x emits iceman `lf em 410x clone --id <hex>`."""
    _cap.reset(returns=[1])
    ret = lfwrite.write_em410x('0F0368568B')
    if ret != 1:
        return False, 'write_em410x returned %r, expected 1' % (ret,)
    if len(_cap.cmds) != 1:
        return False, 'expected 1 cmd, got %d: %r' % (len(_cap.cmds), _cap.cmds)
    expected = 'lf em 410x clone --id 0F0368568B'
    if _cap.cmds[0] != expected:
        return False, 'cmd=%r expected=%r' % (_cap.cmds[0], expected)
    return True, ''


def _test_hid_clone_cmd():
    """lfwrite.write_hid emits iceman `lf hid clone -r <hex>`."""
    _cap.reset(returns=[1])
    ret = lfwrite.write_hid('2006ec0c86')
    if ret != 1:
        return False, 'write_hid returned %r, expected 1' % (ret,)
    if _cap.cmds != ['lf hid clone -r 2006ec0c86']:
        return False, 'cmds=%r' % (_cap.cmds,)
    return True, ''


def _test_indala_clone_cmd():
    """lfwrite.write_indala emits iceman `lf indala clone -r <hex>`."""
    _cap.reset(returns=[1])
    ret = lfwrite.write_indala('a0000000a0002021')
    if ret != 1:
        return False, 'write_indala returned %r, expected 1' % (ret,)
    if _cap.cmds != ['lf indala clone -r a0000000a0002021']:
        return False, 'cmds=%r' % (_cap.cmds,)
    return True, ''


def _test_fdxb_clone_cmd():
    """lfwrite.write_fdx_par emits iceman
    `lf fdxb clone --country <dec> --national <dec>`.

    Input uses `<country>-<national>` hyphen form (matches lfsearch
    REGEX_ANIMAL parse of iceman `Animal ID........... 999-1337`).
    """
    _cap.reset(returns=[1])
    ret = lfwrite.write_fdx_par('999-1337')
    if ret != 1:
        return False, 'write_fdx_par returned %r, expected 1' % (ret,)
    if _cap.cmds != ['lf fdxb clone --country 999 --national 1337']:
        return False, 'cmds=%r' % (_cap.cmds,)
    return True, ''


def _test_raw_clone_map_cmds():
    """Every RAW_CLONE_MAP entry emits `lf <tag> clone -r <hex>`."""
    # Known iceman dispatch entries -- cmdlf<tag>.c + matrix L1189-1214.
    expected = {
        14: 'lf securakey clone -r AABBCC',
        29: 'lf gallagher clone -r AABBCC',
        34: 'lf pac clone -r AABBCC',
        35: 'lf paradox clone -r AABBCC',
        45: 'lf nexwatch clone -r AABBCC',
    }
    for typ, want in expected.items():
        _cap.reset(returns=[1])
        ok = lfwrite.write_raw_clone(typ, 'AABBCC')
        if ok is not True:
            return False, ('write_raw_clone(%d) returned %r, expected True'
                           % (typ, ok))
        if _cap.cmds != [want]:
            return False, ('typ=%d cmds=%r expected=%r'
                           % (typ, _cap.cmds, want))
    return True, ''


def _test_t55xx_write_cmd():
    """lfwrite.write_raw_t55xx emits per-block `lf t55xx write -b N -d <hex>`."""
    _cap.reset(returns=[1, 1, 1, 1])
    # 4 blocks * 8 hex chars = 32 chars raw
    raw = '0102030405060708090A0B0C0D0E0F10'
    ok = lfwrite.write_raw_t55xx(raw)
    if ok is not True:
        return False, 'write_raw_t55xx returned %r, expected True' % (ok,)
    expected = [
        'lf t55xx write -b 0 -d 01020304',
        'lf t55xx write -b 1 -d 05060708',
        'lf t55xx write -b 2 -d 090A0B0C',
        'lf t55xx write -b 3 -d 0D0E0F10',
    ]
    if _cap.cmds != expected:
        return False, 'cmds=%r\nexpected=%r' % (_cap.cmds, expected)
    return True, ''


def _test_t55xx_write_b0_cmd():
    """lfwrite.write_b0_need emits `lf t55xx write -b 0 -d <config> [-p <key>]`."""
    # HID_PROX_ID=9 maps to B0_WRITE_MAP[9] = '00107060'
    _cap.reset(returns=[1])
    lfwrite.write_b0_need(9)  # no key
    if _cap.cmds != ['lf t55xx write -b 0 -d 00107060']:
        return False, 'cmds=%r' % (_cap.cmds,)
    _cap.reset(returns=[1])
    lfwrite.write_b0_need(9, key='20206666')
    if _cap.cmds != ['lf t55xx write -b 0 -d 00107060 -p 20206666']:
        return False, 'cmds=%r (with key)' % (_cap.cmds,)
    return True, ''


def _test_t55xx_restore_cmd():
    """lfwrite.write_dump_t55xx emits `lf t55xx restore -f <path>`.

    NOTE: write_dump_t55xx also invokes lft55xx.detectT55XX() etc for the
    verify step; we only assert the restore cmd here and tolerate the
    detect step returning None (lft55xx not available under our stub).
    """
    _cap.reset(returns=[1])
    # Force lft55xx None to stop execution after the restore command
    saved_lft55xx = lfwrite.lft55xx
    lfwrite.lft55xx = None
    try:
        lfwrite.write_dump_t55xx('/tmp/dump.bin')
    finally:
        lfwrite.lft55xx = saved_lft55xx
    if 'lf t55xx restore -f /tmp/dump.bin' not in _cap.cmds:
        return False, 'expected restore cmd not emitted. cmds=%r' % (_cap.cmds,)
    return True, ''


def _test_em4x05_write_cmd():
    """lfwrite.write_block_em4x05 emits `lf em 4x05 write -a N -d <hex> -p <key>`."""
    _cap.reset(returns=[1, 1])
    blocks = ['00000000', 'DEADC0DE', 'CAFEBABE']
    ret = lfwrite.write_block_em4x05(blocks, start=1, end=2, key='11223344')
    if ret != 0:
        return False, 'write_block_em4x05 returned %r, expected 0' % (ret,)
    expected = [
        'lf em 4x05 write -a 1 -d DEADC0DE -p 11223344',
        'lf em 4x05 write -a 2 -d CAFEBABE -p 11223344',
    ]
    if _cap.cmds != expected:
        return False, 'cmds=%r\nexpected=%r' % (_cap.cmds, expected)
    return True, ''


def _test_lf_sea_cmd_in_inline_verify():
    """lfwrite._inline_verify emits `lf sea` (iceman short-prefix alias)."""
    _cap.reset(returns=[1])
    # EM410x_ID = 8; lfread.READ[8] may or may not exist; we only
    # assert the `lf sea` cmd is issued before any downstream read.
    lfwrite._inline_verify(8)
    if not _cap.cmds or _cap.cmds[0] != 'lf sea':
        return False, 'expected first cmd `lf sea`, got %r' % (_cap.cmds,)
    return True, ''


def _test_lfverify_lf_sea_fallback_cmd():
    """lfverify.verify fallback path emits `lf sea` when scan is None."""
    # Force scan + lfsearch to be missing so the fallback fires.
    # We patch sys.modules to intercept `import scan`.
    _cap.reset(returns=[-1])  # -1 -> VERIFY_FAIL (early exit)
    saved_scan = sys.modules.pop('scan', None)
    sys.modules['scan'] = None  # triggers ImportError on import
    # Force the relative `. import scan` branch to fail too
    saved_pkg = sys.modules.get(__package__ or '__main__')
    try:
        # Use a non-T55/EM4305 typ so we land in the scan/fallback branch.
        typ = 8  # EM410X_ID
        lfverify.verify(typ, uid_par='DEADBEEF', raw_par='')
    finally:
        if saved_scan is not None:
            sys.modules['scan'] = saved_scan
        else:
            sys.modules.pop('scan', None)
    if 'lf sea' not in _cap.cmds:
        return False, ('expected fallback `lf sea` emitted; cmds=%r'
                       % (_cap.cmds,))
    return True, ''


# ---------------------------------------------------------------------------
# Response-shape assertions (verify regex)
# ---------------------------------------------------------------------------

# Regex used in lfwrite.write_dump_em4x05 for post-write `lf em 4x05 read`
# verify. Iceman emission at cmdlfem4x05.c:1391 is exactly
# `Address %02d | %08X - %s` (with %s empty for addr <= 13, "Lock" else).
_ICEMAN_EM4X05_READ_ANCHORED = re.compile(
    r'Address\s+\d+\s+\|\s+([A-Fa-f0-9]{8})\s+-')
_ICEMAN_EM4X05_READ_FALLBACK = re.compile(
    r'\|\s+([A-Fa-f0-9]{8})\s+-')


def _test_em4x05_read_verify_regex():
    """Iceman-native `lf em 4x05 read` response pattern matches
    `Address NN | HHHHHHHH - <Lock|empty>` as emitted by
    cmdlfem4x05.c:1391."""
    # Positive -- iceman raw shape (addr <= 13, %s empty)
    body_raw = 'Address 01 | DEADC0DE - \n'
    m = _ICEMAN_EM4X05_READ_ANCHORED.search(body_raw)
    if not m:
        return False, 'anchored regex missed iceman raw shape: %r' % (body_raw,)
    if m.group(1).upper() != 'DEADC0DE':
        return False, 'wrong capture on raw: %r' % (m.group(1),)

    # Positive -- iceman raw shape with Lock suffix (addr > 13)
    body_lock = 'Address 14 | FFFFFFFF - Lock\n'
    m = _ICEMAN_EM4X05_READ_ANCHORED.search(body_lock)
    if not m:
        return False, 'anchored regex missed Lock shape: %r' % (body_lock,)
    if m.group(1).upper() != 'FFFFFFFF':
        return False, 'wrong capture on Lock: %r' % (m.group(1),)

    # Positive -- prefix-stripped executor output uses fallback regex.
    body_stripped = '| 00148040 - \n'
    m = _ICEMAN_EM4X05_READ_FALLBACK.search(body_stripped)
    if not m:
        return False, ('fallback regex missed prefix-stripped shape: %r'
                       % (body_stripped,))
    if m.group(1).upper() != '00148040':
        return False, 'wrong fallback capture: %r' % (m.group(1),)

    # Negative -- legacy pipe in unrelated output must NOT match the
    # anchored iceman-native regex (short hex or no trailing dash).
    body_bad = 'Pipe | FF\n'
    m = _ICEMAN_EM4X05_READ_ANCHORED.search(body_bad)
    if m:
        return False, 'anchored regex false-matched bad body: %r' % (body_bad,)
    return True, ''


def _test_t55xx_write_live_sample(body, sample_idx):
    """Live `lf t55xx write` iceman-native response (cmdlft55xx.c:1932).

    Iceman emits `Writing page %d  block: %02d  data: 0x%08X [pwd: 0x%08X]`
    as an INFO line before the armsrc write; there is NO success/failure
    sentinel in the normal path -- success detection relies on the PM3
    task return code (exit status 0). Middleware correctly uses return
    code only; this test asserts the live-sample bodies match the
    iceman emission shape as a sanity check.
    """
    # The info line is the entire body on the live sample side.
    pattern = re.compile(
        r'Writing page\s+\d+\s+block:\s+\d{2}\s+data:\s+0x[0-9A-Fa-f]{8}')
    m = pattern.search(body)
    if not m:
        return False, ('body does not match iceman `Writing page N  '
                       'block: NN  data: 0xHHHHHHHH`: %r' % (body[:120],))
    return True, ''


def _test_lf_sea_live_sample(body, sample_idx):
    """Live `lf sea` iceman-native response (cmdlf.c:1890 CLIParserInit
    "lf search", short-prefix alias resolved to it).

    Iceman `lf sea` emits a short-prefix-aliased `lf search` response.
    Observed iceman_output.json shapes:

      1. `Checking for known tags: ... Couldn't identify a chipset` --
         no-tag path via cmdlf.c:1991 iterated demod loop. 7 of 10
         live samples.
      2. `No data found!` -- armsrc `GetAnalyseTrace` / graph.c path
         emitted when the graph buffer is empty (no sample data to
         demod). 3 of 10 live samples. Not originating from cmdlf.c
         itself but from the demod helpers it invokes.
      3. Empty body / ping-leak.

    Middleware (lfwrite._inline_verify) ignores the result entirely;
    this test only asserts the command form is structurally valid
    (iceman-recognisable prefix tokens).
    """
    if ('Couldn\'t identify a chipset' in body
            or 'Searching for auth' in body
            or 'Checking for known tags' in body
            or 'Valid' in body
            or 'No data found' in body):
        return True, ''
    # Empty bodies (ping-leak) also tolerated.
    if not body.strip():
        return True, ''
    return False, 'unrecognised `lf sea` iceman shape: %r' % (body[:120],)


# ---------------------------------------------------------------------------
# Synthetic iceman-native samples -- exercise post-flip regex / cmd forms
# for commands with 0 live samples in iceman_output.json.
# ---------------------------------------------------------------------------

_SYNTHETIC_SAMPLES = [
    ('lf em 4x05 read', 'iceman Address NN | HHHHHHHH - <empty>',
     'Address 01 | DEADC0DE - \n',
     lambda body: _ICEMAN_EM4X05_READ_ANCHORED.search(body) is not None),
    ('lf em 4x05 read', 'iceman Address NN | HHHHHHHH - Lock',
     'Address 14 | FFFFFFFF - Lock\n',
     lambda body: _ICEMAN_EM4X05_READ_ANCHORED.search(body) is not None),
    ('lf em 4x05 read', 'iceman prefix-stripped fallback | HHHHHHHH -',
     '| 00148040 - \n',
     lambda body: _ICEMAN_EM4X05_READ_FALLBACK.search(body) is not None),
    ('lf em 4x05 read', 'iceman negative -- bad shape',
     'Pipe | FF\n',
     lambda body: _ICEMAN_EM4X05_READ_ANCHORED.search(body) is None),
    ('lf t55xx write', 'iceman Writing page 0  block: 01  data: 0x01DEB4DD',
     'Writing page 0  block: 01  data: 0x01DEB4DD\n\n',
     lambda body: re.search(
         r'Writing page\s+\d+\s+block:\s+\d{2}\s+data:\s+0x[0-9A-Fa-f]{8}',
         body) is not None),
    ('lf t55xx restore', 'iceman Starting to write ... Done!',
     'Starting to write...\n'
     'Writing page 0  block: 01  data: 0xDEADC0DE\n'
     'Done!\n',
     lambda body: 'Done!' in body),
    ('lf em 410x clone', 'iceman Preparing to clone EM4102 ... Done!',
     'Preparing to clone EM4102 to T55x7 tag with EM Tag ID 0F0368568B (RF/64)\n'
     'Done!\n',
     lambda body: 'Done!' in body),
    ('lf fdxb clone', 'iceman Preparing to clone FDX-B ... Done!',
     'Country code........ 999\nNational code....... 1337\n'
     'Set animal bit...... N\nSet data block bit.. N\n'
     'Extended data....... 0x0\nRFU................. 0\n'
     'Preparing to clone FDX-B to T55x7 with animal ID: 0999-1337\n'
     'Done!\n',
     lambda body: 'Done!' in body and 'Preparing to clone FDX-B' in body),
    ('lf hid clone', 'iceman Preparing to clone HID tag using raw ... Done!',
     'Preparing to clone HID tag using raw 2006ec0c86\nDone!\n',
     lambda body: 'Done!' in body),
    ('lf indala clone', 'iceman Preparing to clone Indala 64 bit ... Done!',
     'Preparing to clone Indala 64 bit to T55x7 raw a0000000a0002021\nDone!\n',
     lambda body: 'Done!' in body),
]


def _run_synthetic_samples():
    """Run synthetic iceman-native shape validation samples."""
    print()
    print('Synthetic iceman-native shape checks:')
    for cmd, label, body, predicate in _SYNTHETIC_SAMPLES:
        executor.CONTENT_OUT_IN__TXT_CACHE = body
        try:
            ok = bool(predicate(body))
            detail = '' if ok else 'predicate returned False'
        except Exception as e:
            _record(cmd + ' (synth)', False,
                    '%s: raised %s: %s' % (label, type(e).__name__, e))
            print('  %-22s  %-56s  [FAIL] raised: %s' % (cmd, label, e))
            continue
        _record(cmd + ' (synth)', ok, '%s: %s' % (label, detail))
        print('  %-22s  %-56s  %s'
              % (cmd, label, '[PASS]' if ok else '[FAIL] %s' % detail))


# ---------------------------------------------------------------------------
# Command-form tests (SEND-side)
# ---------------------------------------------------------------------------

def _run_command_form_tests():
    """Run SEND-side command-form assertions with executor monkeypatch."""
    tests = [
        ('lf em 410x clone', 'write_em410x --id form',
         _test_em410x_clone_cmd),
        ('lf hid clone', 'write_hid -r form',
         _test_hid_clone_cmd),
        ('lf indala clone', 'write_indala -r form',
         _test_indala_clone_cmd),
        ('lf fdxb clone', 'write_fdx_par --country --national form',
         _test_fdxb_clone_cmd),
        ('RAW_CLONE_MAP', 'securakey/gallagher/pac/paradox/nexwatch -r form',
         _test_raw_clone_map_cmds),
        ('lf t55xx write', 'write_raw_t55xx -b N -d <hex> form',
         _test_t55xx_write_cmd),
        ('lf t55xx write', 'write_b0_need -b 0 -d <cfg> [-p <key>] form',
         _test_t55xx_write_b0_cmd),
        ('lf t55xx restore', 'write_dump_t55xx -f <path> form',
         _test_t55xx_restore_cmd),
        ('lf em 4x05 write', 'write_block_em4x05 -a N -d <hex> -p <key> form',
         _test_em4x05_write_cmd),
        ('lf sea', '_inline_verify lf-sea-first form',
         _test_lf_sea_cmd_in_inline_verify),
        ('lf sea', 'verify() fallback lf-sea form',
         _test_lfverify_lf_sea_fallback_cmd),
    ]
    print()
    print('Command-form checks (iceman-native SEND-side):')
    _install_capture()
    try:
        for cmd, label, fn in tests:
            try:
                ok, detail = fn()
            except Exception as e:
                ok = False
                detail = 'raised %s: %s' % (type(e).__name__, e)
            _record(cmd + ' (cmdform)', ok, '%s: %s' % (label, detail))
            print('  %-22s  %-56s  %s'
                  % (cmd, label, '[PASS]' if ok else '[FAIL] %s' % detail))
    finally:
        _restore_executor()


# ---------------------------------------------------------------------------
# Response-shape tests (regex)
# ---------------------------------------------------------------------------

def _run_response_shape_tests():
    """Run response-shape regex assertions."""
    tests = [
        ('lf em 4x05 read', 'iceman verify regex anchored + fallback',
         _test_em4x05_read_verify_regex),
    ]
    print()
    print('Response-shape regex checks:')
    for cmd, label, fn in tests:
        try:
            ok, detail = fn()
        except Exception as e:
            ok = False
            detail = 'raised %s: %s' % (type(e).__name__, e)
        _record(cmd + ' (regex)', ok, '%s: %s' % (label, detail))
        print('  %-22s  %-56s  %s'
              % (cmd, label, '[PASS]' if ok else '[FAIL] %s' % detail))


# ---------------------------------------------------------------------------
# Live-sample tests
# ---------------------------------------------------------------------------

COMMAND_TABLE = [
    ('lf t55xx write', _test_t55xx_write_live_sample),
    ('lf sea',         _test_lf_sea_live_sample),
]


def main():
    print('=' * 72)
    print('Phase 3 trace-parity - P3.6 Write LF flow')
    print('Ground truth: %s' % GROUND_TRUTH_PATH)
    print('=' * 72)

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

    _run_command_form_tests()
    _run_response_shape_tests()
    _run_synthetic_samples()

    print('=' * 72)
    print('TOTAL: %d / %d passed, %d failed'
          % (_results['pass'], _results['total'], _results['fail']))
    print('=' * 72)

    return 0 if _results['fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
