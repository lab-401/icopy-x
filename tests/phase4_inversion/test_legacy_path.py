#!/usr/bin/env python3
##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 17, 2026
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
##########################################################################

"""Phase 4 legacy-path parity test.

After the compat flip (Phase 4), `translate_response()` runs only when
`_current_version == PM3_VERSION_ORIGINAL` (legacy factory firmware).
Normalizers now rewrite LEGACY FW output UP to iceman shape so the
iceman-native middleware regex matches on legacy PM3.

This test synthesises legacy-shape response bodies (derived from
/tmp/factory_pm3/client/src/ source citations) and verifies that
`translate_response()` on PM3_VERSION_ORIGINAL produces iceman-shape
output.

Ground truth citations per fixture.

Exit status:
  0 — all parity fixtures pass
  1 — one or more produce unexpected output
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'src', 'middleware'))

import pm3_compat  # noqa: E402


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

_results = {'total': 0, 'pass': 0, 'fail': 0, 'failures': []}


def _test(name, cond, detail=''):
    mark = 'PASS' if cond else 'FAIL'
    _results['total'] += 1
    if cond:
        _results['pass'] += 1
    else:
        _results['fail'] += 1
        _results['failures'].append((name, detail))
    print('  %s  %s' % (mark, name))


def _set_legacy():
    """Set _current_version to PM3_VERSION_ORIGINAL (legacy factory FW)."""
    pm3_compat._current_version = pm3_compat.PM3_VERSION_ORIGINAL


def _set_iceman():
    """Set _current_version to PM3_VERSION_ICEMAN."""
    pm3_compat._current_version = pm3_compat.PM3_VERSION_ICEMAN


def _contains(s, needle):
    return needle in s


# ---------------------------------------------------------------------------
# Legacy-path fixtures — each entry cites legacy emission line + iceman
# counterpart so the parity check is traceable to ground truth.
# ---------------------------------------------------------------------------

FIXTURES = [
    # --- hf mf wrbl isOk -> Write ( ok ) ---
    # LEGACY: cmdhfmf.c:716,825,1307 `"isOk:%02x", isOK`.
    # ICEMAN: cmdhfmf.c:1389,9677,9760 `"Write ( ok )"`.
    # Middleware hfmfwrite._KW_WRBL_SUCCESS = r'Write \( ok \)'.
    {
        'name': 'wrbl_ok_legacy_to_iceman',
        'cmd': 'hf mf wrbl',
        'input': 'isOk:01\n',
        'must_contain': 'Write ( ok )',
    },
    {
        'name': 'wrbl_fail_legacy_to_iceman',
        'cmd': 'hf mf wrbl',
        'input': 'isOk:00\n',
        'must_contain': 'Write ( fail )',
    },

    # --- EM 410x ID rewrite ---
    # LEGACY: cmdlfem4x.c:266 `"\nEM TAG ID      : %s"`.
    # ICEMAN: cmdlfem410x.c:115 `"EM 410x ID <hex>"`.
    {
        'name': 'em410x_tag_id_legacy_to_iceman',
        'cmd': 'lf sea',
        'input': 'EM TAG ID      : 0100000058\n',
        'must_contain': 'EM 410x ID 0100000058',
    },

    # --- Chipset detection rewrite ---
    # LEGACY: cmdlf.c:1349/1357/1365 `"Chipset detection: <name>"`.
    # ICEMAN: cmdlf.c:1601-1655 `"Chipset... <name>"` (3 dots).
    {
        'name': 'chipset_detection_legacy_to_iceman',
        'cmd': 'lf sea',
        'input': 'Chipset detection: T55xx\n',
        'must_contain': 'Chipset... T55xx',
    },

    # --- FDX-B Animal ID dotted rewrite (colon form) ---
    # LEGACY: cmdlffdx.c:200 `"Animal ID:     %04u-%012u"`.
    # ICEMAN: cmdlffdxb.c:572/578 `"Animal ID........... <c>-<n>"`.
    {
        'name': 'fdxb_animal_id_colon_legacy_to_iceman',
        'cmd': 'lf sea',
        'input': 'Animal ID:     0060-030207938416\n',
        'must_contain': 'Animal ID........... 0060-030207938416',
    },

    # --- T55xx Chip Type dotted rewrite ---
    # LEGACY: cmdlft55xx.c:1606 `"     Chip Type      : T55x7"`.
    # ICEMAN: cmdlft55xx.c:1837 `" Chip type......... T55x7"`.
    # Middleware lft55xx._RE_CHIP_TYPE = r'Chip [Tt]ype\.+\s+(\S+)'.
    {
        'name': 't55xx_chip_type_legacy_to_iceman',
        'cmd': 'lf t55xx detect',
        'input': '     Chip Type      : T55x7\n',
        'must_contain': 'Chip type......... T55x7',
    },

    # --- T55xx Block0 dotted rewrite (strip 0x prefix) ---
    # LEGACY: cmdlft55xx.c:1612 `"     Block0         : 0x%08X"`.
    # ICEMAN: cmdlft55xx.c:1843 `" Block0............ %08X"`.
    {
        'name': 't55xx_block0_legacy_to_iceman',
        'cmd': 'lf t55xx detect',
        'input': '     Block0         : 0x000880E0\n',
        'must_contain': 'Block0............ 000880E0',
    },

    # --- EM4x05 info: ConfigWord -> Block0 (structural) ---
    # LEGACY: cmdlfem4x.c:1242 `"ConfigWord: %08X (Word 4)"`.
    # ICEMAN: cmdlfem4x05.c:873 `"Block0........ %08x"`.
    {
        'name': 'em4x05_configword_legacy_to_block0_iceman',
        'cmd': 'lf em 4x05 info',
        'input': 'ConfigWord: 00080040 (Word 4)\n',
        'must_contain': 'Block0........ 00080040',
    },

    # --- EM4x05 Chip Type pipe -> dotted ---
    # LEGACY: cmdlfem4x.c:1266 `"\n Chip Type:   %u | EM4305"`.
    # ICEMAN: cmdlfem4x05.c:869 `"Chip type..... EM4305"`.
    {
        'name': 'em4x05_chip_type_legacy_to_iceman',
        'cmd': 'lf em 4x05 info',
        'input': ' Chip Type:   9 | EM4305\n',
        'must_contain': 'Chip type..... EM4305',
    },

    # --- hf iclass wrbl legacy 'successful' -> iceman '( ok )' ---
    # LEGACY: cmdhficlass.c:2149 `"Wrote block %02X successful"`.
    # ICEMAN: cmdhficlass.c:3134 `"Wrote block %d / 0x%02X ( ok )"`.
    {
        'name': 'iclass_wrbl_legacy_to_iceman',
        'cmd': 'hf iclass wrbl',
        'input': 'Wrote block 07 successful\n',
        'must_contain': '( ok )',
    },

    # --- hf iclass rdbl legacy ' block NN : ' -> iceman ' block N/0x : ' ---
    # LEGACY: cmdhficlass.c:2399 `" block %02X : <hex>"`.
    # ICEMAN: cmdhficlass.c:3501 `" block %3d/0x%02X : <hex>"`.
    {
        'name': 'iclass_rdbl_legacy_to_iceman',
        'cmd': 'hf iclass rdbl',
        'input': ' block 07 : 12 FF 00 11 22 33 44 55\n',
        'must_contain': '/0x07 :',
    },

    # --- hf 15 csetuid legacy lowercase (ok) -> iceman capital + spaces ---
    # LEGACY: cmdhf15.c:1811 `"setting new UID (" _GREEN_("ok") ")"`.
    # ICEMAN: cmdhf15.c:2900 `"Setting new UID ( " _GREEN_("ok") " )"`.
    {
        'name': 'hf15_csetuid_legacy_to_iceman',
        'cmd': 'hf 15 csetuid',
        'input': 'setting new UID (ok)\n',
        'must_contain': 'Setting new UID ( ok )',
    },

    # --- hf 15 restore legacy 'done' -> iceman 'Done!' ---
    # LEGACY: cmdhf15.c:1744 `"done"`.
    # ICEMAN: cmdhf15.c:2818 `"Done!"`.
    {
        'name': 'hf15_restore_legacy_to_iceman',
        'cmd': 'hf 15 restore',
        'input': 'done\n',
        'must_contain': 'Done!',
    },

    # --- hf felica reader legacy 'IDm  ' -> iceman 'IDm: ' ---
    # LEGACY: cmdhffelica.c:1837 `"IDm  %s"` (two spaces, no colon).
    # ICEMAN: cmdhffelica.c:1183 `"IDm: %s"` (colon-space).
    {
        'name': 'felica_reader_legacy_to_iceman',
        'cmd': 'hf felica reader',
        'input': 'IDm  01 02 03 04 05 06 07 08\n',
        'must_contain': 'IDm: 01',
    },

    # --- lf t55xx chk password bracket rewrite ---
    # LEGACY: cmdlft55xx.c factory fork `"Found valid password: %08X"`.
    # ICEMAN: cmdlft55xx.c:3658/3660/3816 `"Found valid password: [ %08X ]"`.
    {
        'name': 't55xx_chk_password_legacy_to_iceman',
        'cmd': 'lf t55xx chk',
        'input': 'Found valid password: 51243648\n',
        'must_contain': '[ 51243648 ]',
    },

    # --- Post-normalize Prng detection colon -> dotted ---
    # LEGACY: cmdhf14a.c:1999 `"Prng detection: weak"`.
    # ICEMAN: cmdhf14a.c:3326 `"Prng detection..... weak"`.
    {
        'name': 'prng_detection_legacy_to_iceman_post',
        'cmd': 'hf 14a info',
        'input': 'Prng detection: weak\n',
        'must_contain': 'Prng detection..... weak',
    },

    # --- Static nonce colon -> dotted ---
    # LEGACY: cmdhf14a.c:1989 `"Static nonce: yes"`.
    # ICEMAN: cmdhf14a.c:3319 `"Static nonce....... yes"`.
    {
        'name': 'static_nonce_legacy_to_iceman_post',
        'cmd': 'hf 14a info',
        'input': 'Static nonce: yes\n',
        'must_contain': 'Static nonce....... yes',
    },

    # --- Magic capabilities colon -> dotted ---
    # LEGACY: mifarehost.c:1171 `"Magic capabilities : Gen 1a"`.
    # ICEMAN: mifarehost.c:1710 `"Magic capabilities... Gen 1a"`.
    {
        'name': 'magic_capabilities_legacy_to_iceman_post',
        'cmd': 'hf 14a info',
        'input': 'Magic capabilities : Gen 1a\n',
        'must_contain': 'Magic capabilities... Gen 1a',
    },

    # --- Xor div key colon -> dotted ---
    # LEGACY: cmdhficlass.c:2784 `"Xor div key : <hex>"`.
    # ICEMAN: cmdhficlass.c:5419 `"Xor div key.... <hex>"`.
    {
        'name': 'xor_div_key_legacy_to_iceman_post',
        'cmd': 'hf iclass calcnewkey',
        'input': 'Xor div key : ABCDEF0123456789\n',
        'must_contain': 'Xor div key.... ABCDEF0123456789',
    },

    # --- ISO space injection ---
    # LEGACY emits 'ISO15693' / 'ISO14443-B' without space (compat marker).
    # ICEMAN emits 'ISO 15693' / 'ISO 14443-B' with space.
    {
        'name': 'iso15693_space_inject_legacy_to_iceman',
        'cmd': 'hf sea',
        'input': 'Valid ISO15693 tag found\n',
        'must_contain': 'Valid ISO 15693',
    },
]


# ---------------------------------------------------------------------------
# Iceman-path no-op fixtures: on iceman FW translate_response is inert.
# ---------------------------------------------------------------------------

ICEMAN_NOOP_FIXTURES = [
    {
        'name': 'iceman_wrbl_passthrough',
        'cmd': 'hf mf wrbl',
        'input': 'Write ( ok )\n',
        'expect_equal': True,
    },
    {
        'name': 'iceman_prng_dotted_passthrough',
        'cmd': 'hf 14a info',
        'input': 'Prng detection..... weak\n',
        'expect_equal': True,
    },
    {
        'name': 'iceman_iso15693_space_passthrough',
        'cmd': 'hf sea',
        'input': 'Valid ISO 15693 tag found\n',
        'expect_equal': True,
    },
    {
        'name': 'iceman_t55xx_dotted_passthrough',
        'cmd': 'lf t55xx detect',
        'input': ' Chip type......... T55x7\n Block0............ 000880E0\n',
        'expect_equal': True,
    },
]


def main():
    print('=' * 70)
    print('Phase 4 legacy-path parity test')
    print('=' * 70)

    print('\nLegacy FW direction (PM3_VERSION_ORIGINAL):')
    _set_legacy()
    for fx in FIXTURES:
        out = pm3_compat.translate_response(fx['input'], fx['cmd'])
        ok = _contains(out, fx['must_contain'])
        _test(fx['name'], ok,
              'input=%r, output=%r, expected to contain %r' % (
                  fx['input'], out, fx['must_contain']))

    print('\nIceman FW direction (PM3_VERSION_ICEMAN) — must be pass-through:')
    _set_iceman()
    for fx in ICEMAN_NOOP_FIXTURES:
        out = pm3_compat.translate_response(fx['input'], fx['cmd'])
        ok = (out == fx['input'])
        _test(fx['name'], ok,
              'input=%r changed to %r' % (fx['input'], out))

    print()
    print('=' * 70)
    print('TOTAL: %d / %d passed, %d failed' % (
        _results['pass'], _results['total'], _results['fail']))
    print('=' * 70)

    if _results['failures']:
        print('\nFAILURES:')
        for name, detail in _results['failures']:
            print('  %s:\n    %s' % (name, detail))

    return 0 if _results['fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
