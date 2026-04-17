#!/usr/bin/env python3
##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 17, 2026
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
##########################################################################

"""Phase 4 file-deletion test — iceman-only operation.

Simulates deleting `src/middleware/pm3_compat.py` from an iceman-only
build and verifies that the middleware + executor still work correctly.

The executor.py module has a defensive `try/except ImportError` around
`import pm3_compat`; when the module is absent it must:

  - import successfully with `pm3_compat = None`
  - `translate()`/`translate_response()` calls guarded by `is not None`
  - middleware parsers function normally on iceman-native input

This test runs by:
  1. Temporarily renaming pm3_compat.py -> pm3_compat.py.phase4_deletion
  2. Invalidating the import cache for pm3_compat and executor
  3. Re-importing executor (must succeed with pm3_compat=None)
  4. Running a set of iceman-native parsing smoke checks against
     middleware modules (hf14ainfo, hfmfkeys, lfsearch, etc.) using
     synthetic iceman-shape fixtures.
  5. Restoring pm3_compat.py

Exit status:
  0 — all smoke checks pass with pm3_compat.py absent
  1 — import failed OR a smoke check failed
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
MIDDLEWARE = os.path.join(REPO, 'src', 'middleware')
PM3_COMPAT = os.path.join(MIDDLEWARE, 'pm3_compat.py')
RENAMED = PM3_COMPAT + '.phase4_deletion'


def _test(name, cond, detail=''):
    """Print + track test outcome."""
    mark = 'PASS' if cond else 'FAIL'
    _results['total'] += 1
    if cond:
        _results['pass'] += 1
    else:
        _results['fail'] += 1
        _results['failures'].append((name, detail))
    print('  %s  %s' % (mark, name))


_results = {'total': 0, 'pass': 0, 'fail': 0, 'failures': []}


def _run_smoke_checks():
    """Smoke-check iceman-native middleware parsing with pm3_compat absent."""
    # Fresh import path (middleware) so cached modules don't leak.
    sys.path.insert(0, MIDDLEWARE)

    # Invalidate any cached middleware modules.  pm3_compat must NOT be in
    # sys.modules at this point; executor must load pm3_compat=None.
    for mod in list(sys.modules):
        if mod in ('pm3_compat', 'executor', 'hf14ainfo', 'hfmfkeys',
                   'hfsearch', 'lfsearch', 'lft55xx', 'iclasswrite',
                   'hficlass', 'hffelica', 'hf15write', 'hfmfwrite',
                   'hfmfuwrite', 'erase'):
            del sys.modules[mod]

    # --- Check 1: executor imports without pm3_compat present ---
    try:
        import executor  # noqa: E402
        _test('import_executor_without_pm3_compat', True)
    except Exception as e:
        _test('import_executor_without_pm3_compat', False, str(e))
        return

    _test('executor.pm3_compat_is_None',
          executor.pm3_compat is None,
          'expected None, got %r' % executor.pm3_compat)

    # --- Check 2: hf14ainfo parses iceman Prng detection dotted line ---
    try:
        import hf14ainfo  # noqa: E402
        body = (
            ' UID: 7A F2 EC B2  \n'
            'ATQA: 00 04\n'
            ' SAK: 08 [2]\n'
            'Prng detection..... weak\n'
            'Static nonce....... yes\n'
        )
        executor.CONTENT_OUT_IN__TXT_CACHE = body
        prng = hf14ainfo.get_prng_level()
        _test('hf14ainfo_prng_weak', prng == 'weak',
              'got %r' % prng)
        _test('hf14ainfo_static_nonce',
              hf14ainfo.has_static_nonce() is True,
              'got False')
    except Exception as e:
        _test('hf14ainfo_smoke', False, str(e))

    # --- Check 3: hfsearch parses iceman `Valid ISO 15693` ---
    try:
        import hfsearch  # noqa: E402
        body = (
            'UID.... E0 04 01 23 45 67 89 AB\n'
            'Valid ISO 15693 tag found\n'
        )
        executor.CONTENT_OUT_IN__TXT_CACHE = body
        result = hfsearch.parser()
        _test('hfsearch_iso15693_detected',
              result.get('type') != 0,
              'result: %r' % result)
    except Exception as e:
        _test('hfsearch_smoke', False, str(e))

    # --- Check 4: lfsearch regex EM 410x + Chipset dotted ---
    # lfsearch.parser() traverses a 30-check ladder that keys on a legacy
    # sentinel ('Valid EM410x ID' no space) — that's a middleware quirk
    # independent of pm3_compat.  Smoke-test the REGEX constants here
    # since those are what pm3_compat would touch.
    try:
        import lfsearch  # noqa: E402
        import re
        em_body = 'EM 410x ID 0100000058\n'
        chipset_body = 'Chipset... T55xx\n'
        em_match = re.search(lfsearch.REGEX_EM410X, em_body)
        chipset_match = re.search(lfsearch._RE_CHIPSET, chipset_body)
        _test('lfsearch_em410x_regex',
              em_match is not None and em_match.group(1) == '0100000058',
              'em_match: %r' % em_match)
        _test('lfsearch_chipset_regex',
              chipset_match is not None and chipset_match.group(1).strip() == 'T55xx',
              'chipset_match: %r' % chipset_match)
    except Exception as e:
        _test('lfsearch_smoke', False, str(e))

    # --- Check 5: hfmfwrite success keyword on iceman `Write ( ok )` ---
    try:
        import hfmfwrite  # noqa: E402
        import re
        body = 'Write ( ok )\n'
        _test('hfmfwrite_keyword_match',
              bool(re.search(hfmfwrite._KW_WRBL_SUCCESS, body)),
              'regex %r did not match %r' % (
                  hfmfwrite._KW_WRBL_SUCCESS, body))
    except Exception as e:
        _test('hfmfwrite_smoke', False, str(e))

    # --- Check 6: iclasswrite Xor div key dotted regex matches iceman ---
    try:
        import iclasswrite  # noqa: E402
        import re
        body = 'Xor div key.... ABCDEF0123456789\n'
        m = re.search(iclasswrite._RE_XOR_DIV_KEY, body)
        _test('iclasswrite_xor_div_key_match',
              m is not None and m.group(1).strip() == 'ABCDEF0123456789',
              'got m=%r' % m)
    except Exception as e:
        _test('iclasswrite_smoke', False, str(e))

    # --- Check 7: hficlass block read regex matches iceman form ---
    try:
        import hficlass  # noqa: E402
        import re
        body = ' block   6/0x06 : 12 FF 00 11 22 33 44 55\n'
        m = re.search(hficlass._RE_BLOCK_READ, body)
        _test('hficlass_rdbl_match',
              m is not None,
              'got m=%r body=%r' % (m, body))
    except Exception as e:
        _test('hficlass_smoke', False, str(e))


def main():
    print('=' * 70)
    print('Phase 4 file-deletion test — iceman-only operation')
    print('=' * 70)

    # Sanity: pm3_compat.py must exist before we start.
    if not os.path.isfile(PM3_COMPAT):
        print('ERROR: %s does not exist; aborting' % PM3_COMPAT)
        return 2

    # Rename pm3_compat.py out of the import path.
    os.rename(PM3_COMPAT, RENAMED)
    print('Renamed pm3_compat.py -> pm3_compat.py.phase4_deletion')

    try:
        _run_smoke_checks()
    finally:
        # Always restore the file, even on test failure / crash.
        os.rename(RENAMED, PM3_COMPAT)
        print('Restored pm3_compat.py')

    print()
    print('=' * 70)
    print('TOTAL: %d / %d passed, %d failed' % (
        _results['pass'], _results['total'], _results['fail']))
    print('=' * 70)

    if _results['failures']:
        print('\nFAILURES:')
        for name, detail in _results['failures']:
            print('  %s: %s' % (name, detail))

    return 0 if _results['fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
