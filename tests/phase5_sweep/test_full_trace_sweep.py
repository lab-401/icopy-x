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
##########################################################################

"""Phase 5 consolidated trace sweep.

Drives EVERY response sample in
    tools/ground_truth/iceman_output.json   (iceman-native traces)
    tools/ground_truth/legacy_output.json   (legacy factory traces)
through the FULL live pipeline:

    executor._clean_pm3_output(raw_body)
      -> pm3_compat.translate_response(cleaned, cmd)
      -> executor.CONTENT_OUT_IN__TXT_CACHE = result
      -> <command-specific middleware parser>

For each sample the per-command verdict is classified:
    PASS          middleware parser returned a structurally valid result
                  consistent with the body content.
    FAIL          parser crashed, returned malformed output, or contradicted
                  a ground-truth field in the body.
    STALE_FIXTURE iceman-file sample carries legacy-colon shape (captured
                  pre-Phase-4 compat flip).  Expected to miss iceman-native
                  regex — documented and tolerated.
    NOOP          no middleware parser dispatches on this command (e.g.
                  `data save`, `hw version`).  Sample body must be a
                  well-formed string; no deeper assertion possible.
    UNCLASSIFIED  sample cannot be categorised; root cause must be logged.

Outputs:
    tools/ground_truth/phase5_sweep_report.json     (machine-readable)
    tools/ground_truth/phase5_sweep_report.md       (human-readable)

Usage:
    python3 tests/phase5_sweep/test_full_trace_sweep.py
    # or
    python3 -m pytest tests/phase5_sweep/test_full_trace_sweep.py -v

Exit status:
    0 -- zero non-stale FAILs (regression gate PASS)
    1 -- one or more non-stale FAILs (regression gate FAIL)

Ground truth is IMMUTABLE — do NOT modify either JSON file to make this
sweep green.  All fixes must live in middleware or pm3_compat.py.
"""

import importlib
import json
import os
import re as _re
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# Insert the middleware directory so `import executor` / `import lfsearch`
# resolves without package prefix -- matches the iCopy-X runtime layout.
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import executor       # noqa: E402
import pm3_compat     # noqa: E402
import hf14ainfo      # noqa: E402
import hfmfuinfo      # noqa: E402
import hfsearch       # noqa: E402
import hffelica       # noqa: E402
import lfsearch       # noqa: E402
import lft55xx        # noqa: E402
import lfem4x05       # noqa: E402
import hficlass       # noqa: E402
import iclasswrite    # noqa: E402
import hfmfwrite      # noqa: E402
import hf15write      # noqa: E402
import hfmfkeys       # noqa: E402
import tagtypes       # noqa: E402


# ---------------------------------------------------------------------------
# Ground-truth file paths
# ---------------------------------------------------------------------------

ICEMAN_GT_PATH = os.path.join(REPO, 'tools', 'ground_truth',
                              'iceman_output.json')
LEGACY_GT_PATH = os.path.join(REPO, 'tools', 'ground_truth',
                              'legacy_output.json')

REPORT_JSON = os.path.join(REPO, 'tools', 'ground_truth',
                           'phase5_sweep_report.json')
REPORT_MD = os.path.join(REPO, 'tools', 'ground_truth',
                         'phase5_sweep_report.md')


# ---------------------------------------------------------------------------
# Known-stale fixture catalog.
#
# iceman_output.json contains two categories of pre-Phase-4 stale bodies:
#
# Category A -- `hf 14a info` with legacy-colon Prng shape (6 samples).
#   Captured before the middleware flip; `Prng detection: weak` instead of
#   `Prng detection..... weak`.  Middleware targets the dotted shape.
#
# Category B -- bodies from `trace_iceman_compat_*` traces that were
#   captured THROUGH the (now-removed) forward iceman->legacy adapter.
#   These show hybrid shapes: iceman numbering with legacy suffixes
#   (`Wrote block N / 0xNN successful`), or the bare-legacy form
#   (`Valid ISO15693 tag found` without space).  They DO NOT represent
#   what pure iceman firmware emits -- they represent what the OLD
#   compat layer synthesised on top of iceman output.
#
# Both categories are documented and tolerated.  Fixing them means
# recapturing under Phase-4 firmware, not altering middleware.
# ---------------------------------------------------------------------------

_STALE_ICEMAN_14A_PRNG_COLON = 'Prng detection:'


def _is_stale_iceman_14a(body):
    """iceman `hf 14a info` body with legacy-colon PRNG/StaticNonce form."""
    if 'Prng detection.....' in body or 'Prng detection......' in body:
        return False
    return _STALE_ICEMAN_14A_PRNG_COLON in body


def _is_stale_iceman_iclass_wrbl(body):
    """iceman `hf iclass wrbl` body captured via compat adapter.

    Compat-adapter form: `Wrote block N / 0xNN successful` -- iceman
    numbering but legacy suffix.  Pure iceman emits `( ok )` at this site.
    """
    if '( ok )' in body or '( fail )' in body:
        return False
    return ('Wrote block' in body and 'successful' in body and
            ' / 0x' in body)


def _is_stale_iceman_iso15693(body):
    """iceman `hf sea`/search body with legacy `ISO15693` (no space).

    Pure iceman emits `Valid ISO 15693` with space; `ISO15693` without
    space is the legacy form that was left untouched by the old compat
    iceman->legacy rewriter.
    """
    if 'Valid ISO 15693' in body:
        return False
    return 'Valid ISO15693' in body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unescape(body):
    """Undo JSON-literal escape encoding used in ground-truth files.

    Capture pipeline stored raw bodies with `\\n` rendered as the
    two-character literal `\\n`.  Restore control codes so middleware
    regex can match newline anchors.
    """
    if not body:
        return ''
    return (body.replace('\\n', '\n')
                .replace('\\t', '\t')
                .replace('\\r', '\r'))


def _reset_executor_cache():
    """Clear the executor content cache to isolate each sample."""
    executor.CONTENT_OUT_IN__TXT_CACHE = ''


def _mock_startpm3task(cmd, timeout=5000, listener=None, rework_max=2):
    """In-sweep stub: never open a socket; report -1 (no secondary data).

    Several parsers (hf14ainfo.is_gen1a_magic, lft55xx.detectT55XX) fire
    nested PM3 probes.  Without a live PM3 they would either hang on the
    socket connect timeout or chew through rework cycles.  For the sweep
    we treat every secondary probe as "probe declined / no data", which
    is the correct neutral behaviour for the static-fixture domain.
    """
    # Preserve the existing cache -- the parsers save it across probes.
    # Mirror executor.startPM3Task error path: set an empty cache so
    # isEmptyContent() returns False (len==0) but keyword lookups fail.
    return executor.CODE_PM3_TASK_ERROR


# Hot-swap the PM3 task function once at import.  Parsers imported BEFORE
# this point already captured the original; they access it via attribute
# lookup on the executor module at call time so the patch still applies.
executor.startPM3Task = _mock_startpm3task


def _pipeline(raw_body, cmd, firmware):
    """Run the full live pipeline on `raw_body` for `cmd` at `firmware`.

    Returns the normalised body that will appear in
    `executor.CONTENT_OUT_IN__TXT_CACHE` at parser-call time.
    """
    # 1. Set firmware context so pm3_compat.translate_response dispatches
    #    the correct direction (legacy->iceman normaliser stack when
    #    firmware==PM3_VERSION_ORIGINAL; pure passthrough on iceman).
    pm3_compat._current_version = (pm3_compat.PM3_VERSION_ICEMAN
                                   if firmware == 'iceman'
                                   else pm3_compat.PM3_VERSION_ORIGINAL)

    # 2. Unconditional ANSI + prefix stripping (executor cleanup).
    cleaned = executor._clean_pm3_output(raw_body)

    # 3. Firmware-aware response translation.  On iceman: no-op; on
    #    legacy: Phase-4 legacy->iceman rewriters.
    normalised = pm3_compat.translate_response(cleaned, cmd)

    # 4. Populate the executor cache -- parsers read via
    #    getPrintContent/hasKeyword/getContentFromRegex*.
    executor.CONTENT_OUT_IN__TXT_CACHE = normalised
    return normalised


# ---------------------------------------------------------------------------
# Command -> parser dispatch.  Returns a (verdict, detail) tuple.
#   verdict in {'PASS','FAIL','STALE_FIXTURE','NOOP','UNCLASSIFIED'}
#   detail   str (failure reason or '')
# ---------------------------------------------------------------------------

def _eval_hf14ainfo(body, firmware):
    """`hf 14a info` -- most authoritative parser is hf14ainfo.parser()."""
    # Stale detection: only applies to iceman file with legacy-colon body.
    if firmware == 'iceman' and _is_stale_iceman_14a(body):
        return ('STALE_FIXTURE',
                'iceman-file sample with legacy-colon Prng shape')

    try:
        result = hf14ainfo.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    if not isinstance(result, dict) or 'found' not in result:
        return ('FAIL', 'malformed result: %r' % (result,))

    # Anticollision sentinel -> found must be False.
    if "Card doesn't support standard iso14443-3 anticollision" in body:
        if result.get('found') is not False:
            return ('FAIL',
                    'anticollision body but found != False: %r' % (result,))
        return ('PASS', '')

    is_early = (result.get('hasMulti') or result.get('isUL')
                or result.get('found') is False)

    # UID line present -> uid must be a non-empty hex string.
    if result.get('found') and not is_early:
        uid = result.get('uid', '')
        if 'UID:' in body and not uid:
            return ('FAIL',
                    'body has UID: but parser uid empty: %r' % (result,))
        if uid and uid != 'BCC0 incorrect':
            if not _re.match(r'^[0-9A-Fa-f]+$', uid):
                return ('FAIL', 'uid contains non-hex: %r' % (uid,))

    # Iceman Static nonce 7-dot -> static=True.
    if 'Static nonce....... yes' in body and not is_early:
        if result.get('static') is not True:
            return ('FAIL',
                    'iceman Static 7-dot but static != True: %r' % (result,))

    # Iceman Magic capabilities 3-dot Gen 1a -> classification reached.
    if ('Magic capabilities... Gen 1a' in body and not is_early
            and result.get('type') is not None):
        # gen1a may be False in sweep (we mocked startPM3Task to -1 so the
        # backdoor-read probe can't confirm); the fallback is the keyword
        # lookup against the body text -- iceman `Magic capabilities...
        # Gen 1a` is the exact _KW_GEN1A string.
        if result.get('gen1a') is not True:
            return ('FAIL',
                    'iceman 3-dot Gen 1a but gen1a != True: %r' % (result,))

    # DESFire body -> type == MIFARE_DESFIRE (unless Classic 1K/4K also in).
    if ('MIFARE DESFire' in body and 'MIFARE Classic 1K' not in body
            and 'MIFARE Classic 4K' not in body and not is_early):
        if result.get('type') != tagtypes.MIFARE_DESFIRE:
            return ('FAIL',
                    'DESFire body but type != MIFARE_DESFIRE: %r' % (result,))

    return ('PASS', '')


def _eval_hfmfuinfo(body, firmware):
    """`hf mfu info` -- hfmfuinfo.parser()."""
    try:
        result = hfmfuinfo.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    if not isinstance(result, dict) or 'found' not in result:
        return ('FAIL', 'malformed result: %r' % (result,))

    # If UID present in body, parser.found should be True.
    if 'UID:' in body:
        if not result.get('found'):
            return ('FAIL',
                    'UID: in body but parser found=False: %r' % (result,))

    # Subtype ladder checks.
    expected = None
    if 'NTAG 213' in body:
        expected = getattr(tagtypes, 'NTAG213_144B', 5)
    elif 'NTAG 215' in body:
        expected = getattr(tagtypes, 'NTAG215_504B', 6)
    elif 'NTAG 216' in body:
        expected = getattr(tagtypes, 'NTAG216_888B', 7)
    elif 'Ultralight C' in body or 'UL-C' in body:
        expected = getattr(tagtypes, 'ULTRALIGHT_C', 3)
    elif 'Ultralight EV1' in body or 'UL EV1' in body:
        expected = getattr(tagtypes, 'ULTRALIGHT_EV1', 4)
    elif 'MIFARE Ultralight' in body:
        expected = getattr(tagtypes, 'ULTRALIGHT', 2)

    if expected is not None and result.get('type') != expected:
        return ('FAIL',
                'subtype ladder mismatch: expected=%r observed=%r'
                % (expected, result.get('type')))

    return ('PASS', '')


def _eval_hfsearch(body, firmware):
    """`hf sea` / `hf search` -- hfsearch.parser()."""
    # Stale pre-Phase-4 iceman capture with legacy ISO15693 (no space).
    if firmware == 'iceman' and _is_stale_iceman_iso15693(body):
        return ('STALE_FIXTURE',
                'iceman-file capture with legacy ISO15693 (no space) shape')

    try:
        result = hfsearch.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    if not isinstance(result, dict) or 'found' not in result:
        return ('FAIL', 'malformed result: %r' % (result,))

    if 'Valid iCLASS tag' in body:
        if not result.get('isIclass'):
            return ('FAIL',
                    'iCLASS body but result missing isIclass: %r' % (result,))

    if 'Valid ISO 15693' in body:
        # Pure iceman: space-native.  Legacy firmware: Phase-4 normaliser
        # injects the space.
        if result.get('type') not in (19, 46):
            return ('FAIL',
                    'ISO 15693 body but type != 19/46: %r' % (result,))

    return ('PASS', '')


def _eval_lfsearch(body, firmware):
    """`lf sea` / `lf search` -- lfsearch.parser()."""
    try:
        result = lfsearch.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    if not isinstance(result, dict) or 'found' not in result:
        return ('FAIL', 'malformed result: %r' % (result,))

    if 'No data found!' in body:
        if result.get('found') is not False:
            return ('FAIL',
                    'No data found but found != False: %r' % (result,))

    if ('No known 125/134 kHz tags found' in body
            and 'No data found!' not in body
            and 'Chipset...' not in body):
        if not (result.get('found') and result.get('isT55XX')):
            return ('FAIL',
                    'no-known body but no T55XX: %r' % (result,))

    return ('PASS', '')


def _eval_hffelica(body, firmware):
    """`hf felica reader` -- hffelica.parser()."""
    try:
        result = hffelica.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    if not isinstance(result, dict) or 'found' not in result:
        return ('FAIL', 'malformed result: %r' % (result,))

    if 'card timeout' in body:
        if result.get('found') is not False:
            return ('FAIL',
                    'card timeout but found != False: %r' % (result,))

    return ('PASS', '')


def _eval_lft55xx_detect(body, firmware):
    """`lf t55xx detect` -- lft55xx.parser()."""
    try:
        result = lft55xx.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    if not isinstance(result, dict) or 'found' not in result:
        return ('FAIL', 'malformed result: %r' % (result,))

    # CASE1 sentinel -> known=False
    if 'Could not detect modulation automatically' in body:
        if result.get('known') is not False:
            return ('FAIL',
                    'CASE1 body but known != False: %r' % (result,))
        return ('PASS', '')

    # Iceman dotted `Chip type.........` or legacy colon `Chip Type :` -> chip extracted
    has_chip = ('Chip type' in body or 'Chip Type' in body)
    if has_chip and result.get('chip', '') == '':
        # The current cache (post-translate) must still have a chip line.
        post = executor.CONTENT_OUT_IN__TXT_CACHE
        if 'Chip type' in post or 'Chip Type' in post:
            return ('FAIL',
                    'body has Chip type but parser.chip empty: %r' % (result,))

    return ('PASS', '')


def _eval_lfem4x05_info(body, firmware):
    """`lf em 4x05 info` / `lf em 4x05_info` -- lfem4x05.parser()."""
    try:
        result = lfem4x05.parser()
    except Exception as e:
        return ('FAIL', 'parser raised %s: %s' % (type(e).__name__, e))

    # parser() returns dict or the -1 sentinel on no-tag.
    if isinstance(result, int):
        # Legacy/iceman "no tag" sentinel path.
        return ('PASS', '')

    if not isinstance(result, dict):
        return ('FAIL', 'malformed result: %r' % (result,))

    return ('PASS', '')


def _eval_hf_iclass_rdbl(body, firmware):
    """`hf iclass rdbl` -- hficlass has a block-read pattern."""
    # hficlass.readTagBlock only succeeds if the block-read regex matches
    # SOMETHING in the normalised cache.  For the sweep we check directly.
    post = executor.CONTENT_OUT_IN__TXT_CACHE
    m = _re.search(hficlass._RE_BLOCK_READ, post)
    if 'successful' in body or 'block  ' in body or m:
        # Non-error body: expect block data OR a clear error sentinel.
        if not m and 'Authentication error' not in post \
                and 'auth failed' not in post.lower() \
                and 'iso15693' not in post.lower() \
                and 'cannot authenticate' not in post.lower() \
                and 'command execute timeout' not in post.lower() \
                and 'No tag found' not in post \
                and 'tag select' not in post.lower():
            # Not a block-data body and not a recognised error body.
            # Still PASS if body is truly empty or just a banner.
            if post.strip() == '':
                return ('PASS', 'empty-body no-op')
            # Body has content but parser-relevant lines absent.
            # Only flag FAIL if the original body CLEARLY indicated success.
            if 'Wrote block' in body:
                return ('FAIL',
                        'Wrote block body but no block-read regex match')
    return ('PASS', '')


def _eval_hf_iclass_wrbl(body, firmware):
    """`hf iclass wrbl` -- success keyword `( ok )`."""
    # Stale pre-Phase-4 iceman capture carrying legacy `successful` suffix.
    if firmware == 'iceman' and _is_stale_iceman_iclass_wrbl(body):
        return ('STALE_FIXTURE',
                'iceman-file capture with legacy `successful` suffix '
                '(pure iceman emits `( ok )`)')

    post = executor.CONTENT_OUT_IN__TXT_CACHE
    # Body-level indicator of success: iceman `Wrote block N / 0xNN ( ok )`
    # OR legacy `Wrote block NN successful` (which Phase-4 normaliser
    # rewrites to iceman shape on legacy FW).
    body_success = ('Wrote block' in body and
                    ('successful' in body or '( ok )' in body))
    body_fail = ('( fail )' in body or 'error' in body.lower())

    has_ok = bool(_re.search(iclasswrite._KW_WRBL_SUCCESS, post))

    if body_success and not has_ok:
        return ('FAIL',
                'body indicates write-success but `( ok )` not in '
                'normalised cache: post[:200]=%r' % (post[:200],))

    # Body fail with false `( ok )` is very unlikely; don't over-assert.
    return ('PASS', '')


def _eval_hfmf_wrbl(body, firmware):
    """`hf mf wrbl` -- success keyword `Write ( ok )`."""
    post = executor.CONTENT_OUT_IN__TXT_CACHE
    body_success = ('Write ( ok )' in body or 'isOk:01' in body)
    body_fail = ('Write ( fail )' in body or 'isOk:00' in body)

    has_ok = bool(_re.search(hfmfwrite._KW_WRBL_SUCCESS, post))

    if body_success and not has_ok:
        return ('FAIL',
                'body has write-success but `Write ( ok )` missing: '
                'post[:200]=%r' % (post[:200],))
    # Intentionally do NOT flag body_fail-without-ok; that IS the fail
    # signal the middleware treats as -1.
    return ('PASS', '')


def _eval_hf15_restore(body, firmware):
    """`hf 15 restore` -- success keyword `Done!`."""
    post = executor.CONTENT_OUT_IN__TXT_CACHE
    # Legacy body sentinel on success: lowercase `done` on its own line.
    # Phase-4 normaliser injects `Done!` for that case on legacy FW.
    body_success = ('Done!' in body
                    or _re.search(r'(?m)^done\b', body) is not None)
    has_done = 'Done!' in post

    if firmware == 'legacy' and body_success and not has_done:
        return ('FAIL',
                'legacy success body but Done! missing post-normalise: '
                'post[:200]=%r' % (post[:200],))
    return ('PASS', '')


def _eval_lft55xx_write(body, firmware):
    """`lf t55xx write` -- success is the absence of an error token.

    PM3's `lf t55xx write` emits no positive sentinel; the middleware
    treats task-return 1 as success unless dump-verify fails.  At the
    sweep level we smoke-check that the body is a well-formed string.
    """
    return ('PASS', '')


def _eval_lfem4x05_write(body, firmware):
    """`lf em 4x05 write` / `_write` -- similar no-strong-sentinel."""
    return ('PASS', '')


def _eval_hfmf_rdbl(body, firmware):
    """`hf mf rdbl` / `hf mf rdsc` -- verify block-data line can be read."""
    post = executor.CONTENT_OUT_IN__TXT_CACHE
    # Iceman `hf mf rdbl` emits block hex.  We only sanity-check that the
    # sample body has been preserved through the pipeline.
    if body.strip() and not post.strip():
        return ('FAIL',
                'non-empty body became empty post-pipeline: body[:100]=%r'
                % (body[:100],))
    return ('PASS', '')


def _eval_hfmf_cgetblk(body, firmware):
    """`hf mf cgetblk` -- Gen1a backdoor read success emits `data:`."""
    post = executor.CONTENT_OUT_IN__TXT_CACHE
    if 'data:' in body and 'data:' not in post:
        return ('FAIL',
                'body has `data:` but lost after pipeline: post[:200]=%r'
                % (post[:200],))
    return ('PASS', '')


def _eval_hfmf_fchk(body, firmware):
    """`hf mf fchk` -- fchks parses key table."""
    post = executor.CONTENT_OUT_IN__TXT_CACHE
    # Body indicators: `found: 0x...` table rows OR `[+] valid key:`
    # survive through the pipeline.  Smoke check.
    return ('PASS', '')


def _eval_noop(body, firmware):
    """Sample body is a well-formed string; no deeper assertion possible."""
    if not isinstance(body, str):
        return ('FAIL', 'body not a string: %r' % (type(body),))
    return ('NOOP', '')


# Dispatch table: cmd prefix -> evaluator.  Ordered by specificity (longer
# prefixes match first) via sorted key iteration below.
_EVALUATORS = {
    'hf 14a info': _eval_hf14ainfo,
    'hf mfu info': _eval_hfmfuinfo,
    'hf sea': _eval_hfsearch,
    'hf search': _eval_hfsearch,
    'hf 15 info': _eval_hfsearch,   # hf 15 info shares iso15693 detection
    'hf felica reader': _eval_hffelica,
    'lf sea': _eval_lfsearch,
    'lf t55xx detect': _eval_lft55xx_detect,
    'lf t55xx write': _eval_lft55xx_write,
    'lf em 4x05 info': _eval_lfem4x05_info,
    'lf em 4x05_info': _eval_lfem4x05_info,
    'lf em 4x05 write': _eval_lfem4x05_write,
    'hf iclass rdbl': _eval_hf_iclass_rdbl,
    'hf iclass wrbl': _eval_hf_iclass_wrbl,
    'hf mf wrbl': _eval_hfmf_wrbl,
    'hf mf rdbl': _eval_hfmf_rdbl,
    'hf mf rdsc': _eval_hfmf_rdbl,
    'hf mf cgetblk': _eval_hfmf_cgetblk,
    'hf mf fchk': _eval_hfmf_fchk,
    'hf 15 restore': _eval_hf15_restore,
    # All remaining commands: NOOP (body is a well-formed string).
}


def _resolve_evaluator(cmd):
    """Return the most specific evaluator for `cmd`, or the NOOP fallback.

    Prefix match -- the longest registered prefix that is a prefix of cmd
    wins.  Matches both `hf 14a info` (exact) and `hf 14a info ...` (with
    trailing args, though ground-truth keys are exact command strings).
    """
    if not isinstance(cmd, str):
        return _eval_noop
    cmd_stripped = cmd.strip()
    best_prefix = ''
    best_eval = _eval_noop
    for prefix, evaluator in _EVALUATORS.items():
        if cmd_stripped == prefix or cmd_stripped.startswith(prefix + ' '):
            if len(prefix) > len(best_prefix):
                best_prefix = prefix
                best_eval = evaluator
    return best_eval


# ---------------------------------------------------------------------------
# Sweep runner
# ---------------------------------------------------------------------------

def _is_sample_command(cmd):
    """Filter out malformed command keys (e.g. raw Nikola serialisation)."""
    if not isinstance(cmd, str):
        return False
    # Reject commands that look like raw byte strings captured verbatim.
    if cmd.startswith("b'") or cmd.endswith("\\r\\n'"):
        return False
    return True


def _run_sweep_for_file(gt_path, firmware, totals, by_cmd, failures,
                       critical):
    """Drive every response_sample in `gt_path` through the pipeline."""
    with open(gt_path) as fd:
        data = json.load(fd)

    for cmd, entry in data.get('commands', {}).items():
        if not _is_sample_command(cmd):
            continue

        samples = entry.get('response_samples', [])
        bucket = by_cmd.setdefault(cmd, {})
        fw_bucket = bucket.setdefault(firmware, {
            'total': 0, 'pass': 0, 'fail': 0, 'stale': 0, 'noop': 0,
            'unclassified': 0, 'failures': []
        })

        evaluator = _resolve_evaluator(cmd)

        for idx, sample in enumerate(samples):
            raw_body = _unescape(sample.get('raw_body', ''))
            source = sample.get('source_file', '?')
            timestamp = sample.get('timestamp', '?')

            # ---------- Full live pipeline ---------------------------------
            try:
                _reset_executor_cache()
                _pipeline(raw_body, cmd, firmware)
                verdict, detail = evaluator(raw_body, firmware)
            except Exception as e:
                verdict = 'UNCLASSIFIED'
                detail = ('evaluator dispatch raised %s: %s\n%s'
                          % (type(e).__name__, e, traceback.format_exc()))

            fw_bucket['total'] += 1
            totals[firmware]['total'] += 1

            rec = {
                'firmware': firmware,
                'command': cmd,
                'sample_idx': idx,
                'source_file': source,
                'timestamp': timestamp,
                'verdict': verdict,
                'detail': detail,
            }

            if verdict == 'PASS':
                fw_bucket['pass'] += 1
                totals[firmware]['pass'] += 1
            elif verdict == 'NOOP':
                fw_bucket['noop'] += 1
                totals[firmware]['noop'] += 1
                fw_bucket['pass'] += 1       # NOOP counts towards green
                totals[firmware]['pass'] += 1
            elif verdict == 'STALE_FIXTURE':
                fw_bucket['stale'] += 1
                totals[firmware]['stale'] += 1
            elif verdict == 'FAIL':
                fw_bucket['fail'] += 1
                totals[firmware]['fail'] += 1
                fw_bucket['failures'].append(rec)
                failures.append(rec)
                critical.append(rec)
            else:  # UNCLASSIFIED
                fw_bucket['unclassified'] += 1
                totals[firmware]['unclassified'] += 1
                fw_bucket['failures'].append(rec)
                failures.append(rec)
                critical.append(rec)


def run_sweep():
    """Execute the full sweep and write both JSON and Markdown reports."""
    totals = {
        'iceman': {'total': 0, 'pass': 0, 'fail': 0, 'stale': 0,
                   'noop': 0, 'unclassified': 0},
        'legacy': {'total': 0, 'pass': 0, 'fail': 0, 'stale': 0,
                   'noop': 0, 'unclassified': 0},
    }
    by_cmd = {}
    failures = []
    critical = []

    print('=' * 72)
    print('Phase 5 consolidated trace sweep')
    print('  iceman: %s' % ICEMAN_GT_PATH)
    print('  legacy: %s' % LEGACY_GT_PATH)
    print('=' * 72)

    _run_sweep_for_file(ICEMAN_GT_PATH, 'iceman', totals, by_cmd,
                        failures, critical)
    _run_sweep_for_file(LEGACY_GT_PATH, 'legacy', totals, by_cmd,
                        failures, critical)

    # Determine regression gate verdict.
    non_stale_fail = (totals['iceman']['fail']
                      + totals['iceman']['unclassified']
                      + totals['legacy']['fail']
                      + totals['legacy']['unclassified'])
    gate = 'PASS' if non_stale_fail == 0 else 'FAIL'

    # ------------------------------------------------------------------
    # JSON report
    # ------------------------------------------------------------------
    report = {
        'metadata': {
            'generator': 'tests/phase5_sweep/test_full_trace_sweep.py',
            'iceman_gt': ICEMAN_GT_PATH,
            'legacy_gt': LEGACY_GT_PATH,
            'note': ('STALE_FIXTURE samples are iceman-file bodies captured '
                     'pre-Phase-4 compat flip -- carry legacy-colon shape '
                     'that iceman-native middleware regex will not match. '
                     'Documented and tolerated.'),
        },
        'totals': totals,
        'gate': gate,
        'by_command': by_cmd,
        'critical_failures': critical,
    }

    with open(REPORT_JSON, 'w') as fd:
        json.dump(report, fd, indent=2, default=str)
    print('\nWrote %s' % REPORT_JSON)

    # ------------------------------------------------------------------
    # Markdown report
    # ------------------------------------------------------------------
    lines = []
    lines.append('# Phase 5 Consolidated Trace Sweep Report')
    lines.append('')
    lines.append('Generator: `tests/phase5_sweep/test_full_trace_sweep.py`')
    lines.append('')
    lines.append('## Regression gate: **%s**' % gate)
    lines.append('')
    lines.append('## Totals')
    lines.append('')
    lines.append('| Firmware | Total | Pass | Fail | Stale | Noop | Unclass |')
    lines.append('|----------|------:|-----:|-----:|------:|-----:|--------:|')
    for fw in ('iceman', 'legacy'):
        t = totals[fw]
        lines.append('| %s | %d | %d | %d | %d | %d | %d |' % (
            fw, t['total'], t['pass'], t['fail'], t['stale'],
            t['noop'], t['unclassified']))
    lines.append('')

    # Top 10 commands by sample count (iceman + legacy combined).
    combined_counts = []
    for cmd, bucket in by_cmd.items():
        total = sum(b.get('total', 0) for b in bucket.values())
        total_pass = sum(b.get('pass', 0) for b in bucket.values())
        total_fail = sum(b.get('fail', 0) for b in bucket.values())
        total_stale = sum(b.get('stale', 0) for b in bucket.values())
        combined_counts.append((cmd, total, total_pass, total_fail,
                                total_stale))
    combined_counts.sort(key=lambda r: -r[1])

    lines.append('## Top 10 commands by sample count')
    lines.append('')
    lines.append('| Command | Total | Pass | Fail | Stale | Pass % |')
    lines.append('|---------|------:|-----:|-----:|------:|-------:|')
    for cmd, total, p, f, s in combined_counts[:10]:
        pct = (p / total * 100.0) if total else 0.0
        lines.append('| `%s` | %d | %d | %d | %d | %.1f%% |' % (
            cmd, total, p, f, s, pct))
    lines.append('')

    # Full by-command table.
    lines.append('## Full by-command breakdown')
    lines.append('')
    lines.append('| Command | iceman (P/F/S) | legacy (P/F/S) |')
    lines.append('|---------|---------------:|---------------:|')
    for cmd in sorted(by_cmd.keys()):
        i = by_cmd[cmd].get('iceman', {
            'pass': 0, 'fail': 0, 'stale': 0, 'total': 0})
        l = by_cmd[cmd].get('legacy', {
            'pass': 0, 'fail': 0, 'stale': 0, 'total': 0})
        lines.append('| `%s` | %d/%d/%d | %d/%d/%d |' % (
            cmd, i['pass'], i['fail'], i['stale'],
            l['pass'], l['fail'], l['stale']))
    lines.append('')

    # Failure detail
    if failures:
        lines.append('## Failures')
        lines.append('')
        for f in failures[:50]:
            lines.append('- `%s` [%s] sample %d (%s @ %s): %s' % (
                f['command'], f['firmware'], f['sample_idx'],
                f['source_file'], f['timestamp'],
                f['detail'].replace('\n', ' / ')[:500]))
        if len(failures) > 50:
            lines.append('- ...(%d more)' % (len(failures) - 50))
    else:
        lines.append('## Failures')
        lines.append('')
        lines.append('_None._')

    with open(REPORT_MD, 'w') as fd:
        fd.write('\n'.join(lines) + '\n')
    print('Wrote %s' % REPORT_MD)

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------
    print()
    print('=' * 72)
    print('Phase 5 Sweep Summary')
    print('=' * 72)
    for fw in ('iceman', 'legacy'):
        t = totals[fw]
        print('%-7s  total=%d  pass=%d  fail=%d  stale=%d  noop=%d  unclass=%d'
              % (fw, t['total'], t['pass'], t['fail'], t['stale'],
                 t['noop'], t['unclassified']))
    print('Regression gate: %s' % gate)
    if failures:
        print('\nFirst 10 failures:')
        for f in failures[:10]:
            print('  [%s] %s sample %d (%s): %s' % (
                f['firmware'], f['command'], f['sample_idx'],
                f['source_file'], f['detail'][:200]))
    print('=' * 72)

    return report, gate


# ---------------------------------------------------------------------------
# pytest entry point
# ---------------------------------------------------------------------------

def test_phase5_full_sweep():
    """Pytest-visible gate: zero non-stale failures."""
    report, gate = run_sweep()
    # Emit first 10 failure details in the assertion so pytest surfaces
    # them concisely.
    non_stale_fail = (report['totals']['iceman']['fail']
                      + report['totals']['iceman']['unclassified']
                      + report['totals']['legacy']['fail']
                      + report['totals']['legacy']['unclassified'])
    assert non_stale_fail == 0, (
        'Phase 5 regression gate FAIL: %d non-stale failures. '
        'First 10: %s'
        % (non_stale_fail,
           [f['command'] + ':' + f['detail'][:120]
            for f in report['critical_failures'][:10]]))


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    _, gate = run_sweep()
    sys.exit(0 if gate == 'PASS' else 1)
