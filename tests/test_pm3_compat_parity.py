#!/usr/bin/env python3
"""Parity test suite for pm3_compat after Phase 4 inversion.

Agent 6 (Test Builder) — PM3 compatibility flip verification pipeline.

Phase 4 state:
  - Middleware is iceman-native (Phase 3 complete).
  - pm3_compat.translate() runs only on LEGACY (factory) FW, converting
    iceman CLI-flag commands down to legacy positional syntax.
  - pm3_compat.translate_response() runs only on LEGACY FW, converting
    legacy output UP to iceman shape for iceman-native middleware regex.
  - On iceman FW both are pass-through (except _BLOCKED_CMDS_ICEMAN
    hardware workaround).
  - Forward (legacy->iceman) translation rules were deleted since all
    middleware now emits iceman form directly.

Categories:
  1. Iceman FW pass-through (forward direction is a no-op)
  2. Legacy FW translation (iceman cmd -> factory cmd)
  3. LEGACY_COMPAT gate
  4. _clean_pm3_output independence
"""

import sys
import os

# Insert src/middleware into path so we can import pm3_compat and executor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'middleware'))

import pm3_compat
from executor import _clean_pm3_output

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

_results = {'total': 0, 'pass': 0, 'fail': 0, 'failures': []}


def _test(name, actual, expected):
    _results['total'] += 1
    if actual == expected:
        _results['pass'] += 1
    else:
        _results['fail'] += 1
        _results['failures'].append(
            '  FAIL: %s\n    expected: %r\n    actual:   %r' % (name, expected, actual))


def _set_version(ver):
    """Set pm3_compat internal version for testing."""
    pm3_compat._current_version = ver


def _ensure_legacy_on():
    pm3_compat.LEGACY_COMPAT = True


# ---------------------------------------------------------------------------
# Category 1: Iceman-FW pass-through + Legacy-FW reverse translation.
#
# Phase 4 changed the semantics:
#   - ICEMAN FW: translate() returns the input unchanged (forward rules
#     deleted; middleware is iceman-native).  Exception: _BLOCKED_CMDS_ICEMAN
#     commands are substituted with 'hw ping'.
#   - ORIGINAL (factory) FW: translate() converts iceman CLI-flag syntax
#     down to legacy positional syntax.
#
# For each (factory_cmd, iceman_cmd) pair we test:
#   1. FWD_ICE: translate(iceman_cmd) on ICEMAN == iceman_cmd (pass-through)
#   2. FWD_FAC: translate(factory_cmd) on ICEMAN == factory_cmd (pass-through)
#   3. REV:     translate(iceman_cmd) on ORIGINAL == factory_cmd (reverse)
#   4. IDEM_ICE: translate(iceman_cmd) on ICEMAN == iceman_cmd (alias of 1)
#   5. IDEM_FAC: translate(factory_cmd) on ORIGINAL == factory_cmd (idempotent)
# ---------------------------------------------------------------------------

# Each entry: (factory_cmd, expected_iceman_cmd, has_reverse_rule)
# has_reverse_rule=True means _COMMAND_TRANSLATION_RULES will convert
# iceman_cmd back to factory_cmd on LEGACY FW (property 3 tested).
# has_reverse_rule=False means the reverse is one-way (property 3 skipped).

BIDIRECTIONAL_PAIRS = [
    # -- Name changes --
    ('lf em 410x_write DEADBEEF 1', 'lf em 410x clone --id DEADBEEF', True),
    ('lf em 410x_write DEADBEEF', 'lf em 410x clone --id DEADBEEF', True,
     'lf em 410x_write DEADBEEF 1'),  # reverse adds the '1'
    ('lf em 410x_read', 'lf em 410x reader', True),
    ('lf fdx read', 'lf fdxb reader', True),
    ('lf hid read', 'lf hid reader', True),
    ('lf indala read', 'lf indala reader', True),
    ('lf awid read', 'lf awid reader', True),
    ('lf io read', 'lf io reader', True),
    ('lf gproxii read', 'lf gproxii reader', True),
    ('lf securakey read', 'lf securakey reader', True),
    ('lf viking read', 'lf viking reader', True),
    ('lf pyramid read', 'lf pyramid reader', True),
    ('lf gallagher read', 'lf gallagher reader', True),
    ('lf jablotron read', 'lf jablotron reader', True),
    ('lf keri read', 'lf keri reader', True),
    ('lf nedap read', 'lf nedap reader', True),
    ('lf noralsy read', 'lf noralsy reader', True),
    ('lf pac read', 'lf pac reader', True),
    ('lf paradox read', 'lf paradox reader', True),
    ('lf presco read', 'lf presco reader', True),
    ('lf visa2000 read', 'lf visa2000 reader', True),
    ('lf nexwatch read', 'lf nexwatch reader', True),

    ('lf em 410x_sim ABCDEF0123', 'lf em 410x sim --id ABCDEF0123', False),

    ('lf em 4x05_write 3 AABBCCDD 11223344', 'lf em 4x05 write -a 3 -d AABBCCDD -p 11223344', True),
    ('lf em 4x05_read 5 DEADBEEF', 'lf em 4x05 read -a 5 -p DEADBEEF', True),
    ('lf em 4x05_info AABB1122', 'lf em 4x05 info -p AABB1122', True),
    ('lf em 4x05_info', 'lf em 4x05 info', True),
    ('lf em 4x05_dump f /tmp/em4x05', 'lf em 4x05 dump -f /tmp/em4x05', True),
    ('lf em 4x05_dump', 'lf em 4x05 dump', True),
    ('lf em 4x05_read 7', 'lf em 4x05 read -a 7', True),

    # -- Argument changes: complex --
    # Note: 'nested o' (one-sector) forward-translates identically to 'nested 1'
    # (size-code).  The reverse is lossy: --1k maps back to size '1', not 'o'.
    ('hf mf nested o 0 A FFFFFFFFFFFF 4 B',
     'hf mf nested --1k --blk 0 -a -k FFFFFFFFFFFF --tblk 4 --tb', True,
     'hf mf nested 1 0 A FFFFFFFFFFFF 4 B'),  # reverse produces size-code form
    ('hf mf nested 1 0 A FFFFFFFFFFFF 4 A',
     'hf mf nested --1k --blk 0 -a -k FFFFFFFFFFFF --tblk 4 --ta', True),
    ('hf mf nested 2 0 B AABBCCDDEEFF 8 A',
     'hf mf nested --2k --blk 0 -b -k AABBCCDDEEFF --tblk 8 --ta', True),
    ('hf mf nested 4 3 A 112233445566 12 B',
     'hf mf nested --4k --blk 3 -a -k 112233445566 --tblk 12 --tb', True),

    ('hf mf staticnested 1 0 A FFFFFFFFFFFF',
     'hf mf staticnested --1k --blk 0 -a -k FFFFFFFFFFFF', False),

    ('hf mf fchk 1 /tmp/keys.dic', 'hf mf fchk --1k -f /tmp/keys.dic', True),
    ('hf mf fchk 2 /tmp/keys.dic', 'hf mf fchk --2k -f /tmp/keys.dic', True),
    ('hf mf fchk 4 /tmp/keys.dic', 'hf mf fchk --4k -f /tmp/keys.dic', True),
    ('hf mf fchk 0 /tmp/keys.dic', 'hf mf fchk --mini -f /tmp/keys.dic', True),

    ('hf mf wrbl 0 A FFFFFFFFFFFF 0102030405060708090A0B0C0D0E0F10',
     'hf mf wrbl --blk 0 -a -k FFFFFFFFFFFF -d 0102030405060708090A0B0C0D0E0F10 --force', True),
    ('hf mf wrbl 63 B AABBCCDDEEFF DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
     'hf mf wrbl --blk 63 -b -k AABBCCDDEEFF -d DEADBEEFDEADBEEFDEADBEEFDEADBEEF --force', True),

    ('hf mf rdbl 0 A FFFFFFFFFFFF', 'hf mf rdbl --blk 0 -a -k FFFFFFFFFFFF', True),
    ('hf mf rdbl 7 B AABBCCDDEEFF', 'hf mf rdbl --blk 7 -b -k AABBCCDDEEFF', True),

    ('hf mf rdsc 0 A FFFFFFFFFFFF', 'hf mf rdsc -s 0 -a -k FFFFFFFFFFFF', True),
    ('hf mf rdsc 15 B AABBCCDDEEFF', 'hf mf rdsc -s 15 -b -k AABBCCDDEEFF', True),

    ('hf mf csetuid AABBCCDD 08 0004 w',
     'hf mf csetuid -u AABBCCDD -s 08 -a 0004 -w', True),
    ('hf mf csetuid AABBCCDD 08 0004',
     'hf mf csetuid -u AABBCCDD -s 08 -a 0004', True),

    ('hf mf csetblk 0 AABBCCDDEEFF00112233445566778899',
     'hf mf csetblk --blk 0 -d AABBCCDDEEFF00112233445566778899', False),
    ('hf mf cgetblk 3', 'hf mf cgetblk --blk 3', True),

    ('hf mf cload b /tmp/dump.eml', 'hf mf cload -f /tmp/dump.eml', True),
    ('hf mf csave 1 o /tmp/dump', 'hf mf csave --1k -f /tmp/dump', False),

    ('hf mf dump', 'hf mf dump --1k', False),
    ('hf mf restore', 'hf mf restore --1k', False),

    # -- Argument changes: simple flag prefix --
    ('hf mfu dump f /tmp/mfu.bin', 'hf mfu dump -f /tmp/mfu.bin', True),
    ('hf mfu restore s e f /tmp/mfu.bin', 'hf mfu restore -s -e -f /tmp/mfu.bin', True),

    ('hf 15 dump f /tmp/15.bin', 'hf 15 dump -f /tmp/15.bin', True),
    ('hf 15 restore f /tmp/15.bin', 'hf 15 restore -f /tmp/15.bin', True),
    ('hf 15 csetuid E004012233445566', 'hf 15 csetuid -u E004012233445566', True),

    ('hf iclass dump k AABBCCDDEEFF0011 f /tmp/ic.bin e',
     'hf iclass dump -k AABBCCDDEEFF0011 -f /tmp/ic.bin --elite', True),
    ('hf iclass dump k AABBCCDDEEFF0011 f /tmp/ic.bin',
     'hf iclass dump -k AABBCCDDEEFF0011 -f /tmp/ic.bin', True),
    ('hf iclass dump k AABBCCDDEEFF0011 e',
     'hf iclass dump -k AABBCCDDEEFF0011 --elite', True),
    ('hf iclass dump k AABBCCDDEEFF0011',
     'hf iclass dump -k AABBCCDDEEFF0011', True),

    # Note: no reverse rule for 'hf iclass chk -f {file}' -- reverse table
    # only has '--vb6kdf' -> bare 'chk'.  The -f form passes through on original.
    ('hf iclass chk f /tmp/iclass_keys.dic',
     'hf iclass chk -f /tmp/iclass_keys.dic', False),
    ('hf iclass chk', 'hf iclass chk --vb6kdf', True),

    ('hf iclass rdbl b 6 k AABBCCDDEEFF0011 e',
     'hf iclass rdbl --blk 6 -k AABBCCDDEEFF0011 --elite', True),
    ('hf iclass rdbl b 6 k AABBCCDDEEFF0011',
     'hf iclass rdbl --blk 6 -k AABBCCDDEEFF0011', True),

    # iclass wrbl: forward uses -b -> --blk; reverse uses --blk -> -b
    ('hf iclass wrbl -b 7 -d AABBCCDD -k 0011223344556677',
     'hf iclass wrbl --blk 7 -d AABBCCDD -k 0011223344556677', True),

    ('hf iclass calcnewkey o AABBCCDDEEFF0011 n 1122334455667788 --elite',
     'hf iclass calcnewkey --old AABBCCDDEEFF0011 --new 1122334455667788 --elite', True),
    ('hf iclass calcnewkey o AABBCCDDEEFF0011 n 1122334455667788',
     'hf iclass calcnewkey --old AABBCCDDEEFF0011 --new 1122334455667788', True),

    ('lf t55xx detect p AABBCCDD', 'lf t55xx detect -p AABBCCDD', True),

    ('lf t55xx dump f /tmp/t55.bin p AABBCCDD',
     'lf t55xx dump -f /tmp/t55.bin -p AABBCCDD', True),
    ('lf t55xx dump f /tmp/t55.bin', 'lf t55xx dump -f /tmp/t55.bin', True),

    ('lf t55xx read b 0 p AABBCCDD o 1',
     'lf t55xx read -b 0 -p AABBCCDD --page1', True),
    ('lf t55xx read b 0 p AABBCCDD', 'lf t55xx read -b 0 -p AABBCCDD', True),
    ('lf t55xx read b 3', 'lf t55xx read -b 3', True),

    ('lf t55xx write b 0 d AABBCCDD p 11223344',
     'lf t55xx write -b 0 -d AABBCCDD -p 11223344', True),
    ('lf t55xx write b 0 d AABBCCDD', 'lf t55xx write -b 0 -d AABBCCDD', True),

    ('lf t55xx wipe p AABBCCDD', 'lf t55xx wipe -p AABBCCDD', True),

    ('lf t55xx restore f /tmp/t55.bin', 'lf t55xx restore -f /tmp/t55.bin', True),
    ('lf t55xx chk f /tmp/t55_pwd.dic', 'lf t55xx chk -f /tmp/t55_pwd.dic', True),

    ('lf hid clone 2006222332', 'lf hid clone -r 2006222332', True),

    ('lf indala clone 1234 -r AABBCCDD', 'lf indala clone -r AABBCCDD', True,
     'lf indala clone AABBCCDD -r AABBCCDD'),  # reverse produces different factory form

    ('lf fdx clone c 999 n 12345678', 'lf fdxb clone --country 999 --national 12345678', True),

    ('lf securakey clone b AABB', 'lf securakey clone -r AABB', True),
    ('lf gallagher clone b CCDD', 'lf gallagher clone -r CCDD', True),
    ('lf pac clone b EEFF', 'lf pac clone -r EEFF', True),
    ('lf paradox clone b 1122', 'lf paradox clone -r 1122', True),

    ('lf nexwatch clone r AABBCCDD', 'lf nexwatch clone -r AABBCCDD', True),

    ('data save f /tmp/data.pm3', 'data save -f /tmp/data.pm3', True),

    # hf 14a raw with -p flag -> -k
    ('hf 14a raw -sc -p 6000', 'hf 14a raw -sc -k 6000', True),
    ('hf 14a raw -p -sc 6000', 'hf 14a raw -k -sc 6000', True),

    ('hf 14a sim t 1 u AABBCCDD', 'hf 14a sim -t 1 -u AABBCCDD', False),

    ('hf list 14a', 'hf list -t 14a', False),
    ('lf list 14a', 'lf list -t 14a', False),

    ('lf config a 1 t 55 s 200', 'lf config -a 1 -t 55 -s 200', True),

    ('mem spiffs load f /tmp/file.bin o /flash/lf_t55xx_mypwds.dic',
     'mem spiffs upload -s /tmp/file.bin -d /flash/lf_t55xx_mypwds.dic', False),
]


def run_category1():
    """Run iceman-FW pass-through + legacy-FW reverse translation tests."""
    _ensure_legacy_on()

    for entry in BIDIRECTIONAL_PAIRS:
        if len(entry) == 3:
            factory_cmd, iceman_cmd, has_reverse = entry
            reverse_factory = factory_cmd
        elif len(entry) == 4:
            factory_cmd, iceman_cmd, has_reverse, reverse_factory = entry
        else:
            raise ValueError('Bad entry: %r' % (entry,))

        label = factory_cmd[:60]

        # Property 1: iceman-FW pass-through for iceman command.
        # Post-flip translate() is a no-op on iceman (forward rules deleted).
        _set_version(pm3_compat.PM3_VERSION_ICEMAN)
        idem_ice = pm3_compat.translate(iceman_cmd)
        _test('ICE_PASSTHRU_ICE [%s]' % label, idem_ice, iceman_cmd)

        # Property 2: iceman-FW pass-through for factory command.
        # Legacy input on iceman now passes through (no forward translation).
        _set_version(pm3_compat.PM3_VERSION_ICEMAN)
        fwd = pm3_compat.translate(factory_cmd)
        _test('ICE_PASSTHRU_FAC [%s]' % label, fwd, factory_cmd)

        # Property 5: Factory idempotency (factory_cmd unchanged on original).
        # Factory syntax on legacy FW is native — no rule should rewrite.
        _set_version(pm3_compat.PM3_VERSION_ORIGINAL)
        idem_fac = pm3_compat.translate(factory_cmd)
        _test('IDEM_FAC [%s]' % label, idem_fac, factory_cmd)

        if has_reverse:
            # Property 3: Reverse translation (iceman cmd -> factory) on legacy.
            _set_version(pm3_compat.PM3_VERSION_ORIGINAL)
            rev = pm3_compat.translate(iceman_cmd)
            _test('REV [%s]' % label, rev, reverse_factory)


# ---------------------------------------------------------------------------
# Category 1 supplement: blocked commands
# ---------------------------------------------------------------------------

def run_blocked_commands():
    """Test that blocked iceman commands translate to hw ping."""
    _ensure_legacy_on()
    _set_version(pm3_compat.PM3_VERSION_ICEMAN)

    _test('BLOCKED hf iclass info',
          pm3_compat.translate('hf iclass info'), 'hw ping')


# ---------------------------------------------------------------------------
# Category 1 supplement: empty/None edge cases
# ---------------------------------------------------------------------------

def run_edge_cases():
    """Test translate() with edge-case inputs."""
    _ensure_legacy_on()
    _set_version(pm3_compat.PM3_VERSION_ICEMAN)

    _test('EDGE empty string', pm3_compat.translate(''), '')
    _test('EDGE None', pm3_compat.translate(None), None)

    # Unknown command passes through unchanged
    _test('EDGE unknown cmd', pm3_compat.translate('hw ping'), 'hw ping')
    _test('EDGE hw version', pm3_compat.translate('hw version'), 'hw version')

    # Version not set -> pass through
    _set_version(None)
    _test('EDGE version_none', pm3_compat.translate('hf mf rdbl 0 A FFFFFFFFFFFF'),
          'hf mf rdbl 0 A FFFFFFFFFFFF')


# ---------------------------------------------------------------------------
# Category 2: LEGACY_COMPAT gate
# ---------------------------------------------------------------------------

def run_category2():
    """Test that LEGACY_COMPAT=False disables all translation."""
    pm3_compat.LEGACY_COMPAT = False

    # translate() should return input unchanged regardless of version
    for ver in (pm3_compat.PM3_VERSION_ICEMAN, pm3_compat.PM3_VERSION_ORIGINAL, None):
        _set_version(ver)
        ver_label = ver or 'None'

        cmd = 'hf mf rdbl 0 A FFFFFFFFFFFF'
        _test('LEGACY_OFF translate(%s) factory_cmd' % ver_label,
              pm3_compat.translate(cmd), cmd)

        cmd2 = 'hf mf rdbl --blk 0 -a -k FFFFFFFFFFFF'
        _test('LEGACY_OFF translate(%s) iceman_cmd' % ver_label,
              pm3_compat.translate(cmd2), cmd2)

    # translate_response() should return input unchanged
    for ver in (pm3_compat.PM3_VERSION_ICEMAN, pm3_compat.PM3_VERSION_ORIGINAL, None):
        _set_version(ver)
        ver_label = ver or 'None'

        resp = 'Write ( ok )\nSome data here'
        _test('LEGACY_OFF translate_response(%s)' % ver_label,
              pm3_compat.translate_response(resp, 'hf mf wrbl'), resp)

    # needs_translation() should return False
    for ver in (pm3_compat.PM3_VERSION_ICEMAN, pm3_compat.PM3_VERSION_ORIGINAL, None):
        _set_version(ver)
        ver_label = ver or 'None'
        _test('LEGACY_OFF needs_translation(%s)' % ver_label,
              pm3_compat.needs_translation(), False)

    # Restore
    pm3_compat.LEGACY_COMPAT = True


# ---------------------------------------------------------------------------
# Category 3: _clean_pm3_output independence
# ---------------------------------------------------------------------------

def run_category3():
    """Test executor._clean_pm3_output() independently of pm3_compat."""

    # ANSI code stripping
    ansi_input = '\x1b[32m[+] Found tag\x1b[0m'
    _test('CLEAN ansi_strip', _clean_pm3_output(ansi_input), 'Found tag')

    # [+] prefix stripping
    _test('CLEAN plus_prefix', _clean_pm3_output('[+] Found tag'), 'Found tag')

    # [=] prefix stripping
    _test('CLEAN eq_prefix', _clean_pm3_output('[=] Info line'), 'Info line')

    # [#] prefix stripping
    _test('CLEAN hash_prefix', _clean_pm3_output('[#] Debug line'), 'Debug line')

    # [!!] prefix stripping
    _test('CLEAN bang_prefix', _clean_pm3_output('[!!] Error line'), 'Error line')

    # [-] prefix stripping
    _test('CLEAN minus_prefix', _clean_pm3_output('[-] Warning'), 'Warning')

    # Echo line stripping
    echo_input = '[usb|script] pm3 --> hf search\nFound tag'
    _test('CLEAN echo_strip', _clean_pm3_output(echo_input), 'Found tag')

    # EOR marker stripping
    eor_input = 'Found tag\npm3 -->\n'
    _test('CLEAN eor_strip', _clean_pm3_output(eor_input).strip(), 'Found tag')

    # Section header stripping
    sec_input = '[=] ---------- Section ----------\nData here'
    _test('CLEAN section_strip', _clean_pm3_output(sec_input), 'Data here')

    # Bare [=] line stripping
    bare_input = '[=]\nData here'
    _test('CLEAN bare_eq_strip', _clean_pm3_output(bare_input), 'Data here')

    # Empty input
    _test('CLEAN empty_string', _clean_pm3_output(''), '')
    _test('CLEAN none', _clean_pm3_output(None), None)

    # Combined: ANSI + prefix + echo
    combined = '\x1b[33m[usb|script] pm3 --> hf mf fchk\n\x1b[32m[+] Found keys\x1b[0m\npm3 -->\n'
    result = _clean_pm3_output(combined)
    _test('CLEAN combined_has_found', 'Found keys' in result, True)
    _test('CLEAN combined_no_ansi', '\x1b' not in result, True)
    _test('CLEAN combined_no_echo', 'usb|script' not in result, True)
    _test('CLEAN combined_no_eor', 'pm3 -->' not in result.strip(), True)

    # Independence from pm3_compat: _clean_pm3_output works even if
    # pm3_compat is in any state
    pm3_compat.LEGACY_COMPAT = False
    _set_version(None)
    _test('CLEAN independent_legacy_off',
          _clean_pm3_output('[+] Data'), 'Data')
    pm3_compat.LEGACY_COMPAT = True

    # Multi-prefix lines
    multi = '[+] Line 1\n[=] Line 2\n[#] Line 3'
    cleaned = _clean_pm3_output(multi)
    _test('CLEAN multi_prefix_line1', 'Line 1' in cleaned, True)
    _test('CLEAN multi_prefix_line2', 'Line 2' in cleaned, True)
    _test('CLEAN multi_prefix_line3', 'Line 3' in cleaned, True)
    _test('CLEAN multi_no_brackets', '[+]' not in cleaned and '[=]' not in cleaned, True)


# ---------------------------------------------------------------------------
# Category 1 supplement: Reverse-only rules coverage
# Test reverse rules that don't have a matching forward entry above.
# ---------------------------------------------------------------------------

def run_reverse_only():
    """Test reverse rules that cover commands not in forward table."""
    _ensure_legacy_on()
    _set_version(pm3_compat.PM3_VERSION_ORIGINAL)

    # iclass wrbl with --elite
    _test('REV_ONLY iclass_wrbl_elite',
          pm3_compat.translate('hf iclass wrbl --blk 7 -d AABB -k 0011223344556677 --elite'),
          'hf iclass wrbl -b 7 -d AABB -k 0011223344556677 --elite')

    # iclass wrbl without elite
    _test('REV_ONLY iclass_wrbl_plain',
          pm3_compat.translate('hf iclass wrbl --blk 7 -d AABB -k 0011223344556677'),
          'hf iclass wrbl -b 7 -d AABB -k 0011223344556677')

    # Note: 'hf iclass chk -f' has no reverse rule (only --vb6kdf does).
    # The -f form passes through unchanged on original firmware.
    _test('REV_ONLY iclass_chk_f_passthrough',
          pm3_compat.translate('hf iclass chk -f /tmp/keys.dic'),
          'hf iclass chk -f /tmp/keys.dic')

    # em4x05 write with 2 args (no key)
    _test('REV_ONLY em4x05_write_nokey',
          pm3_compat.translate('lf em 4x05 write -a 3 -d AABBCCDD'),
          'lf em 4x05_write 3 AABBCCDD')

    # lf config reverse
    _test('REV_ONLY lf_config',
          pm3_compat.translate('lf config -a 1 -t 55 -s 200'),
          'lf config a 1 t 55 s 200')


# ---------------------------------------------------------------------------
# Category 2 supplement: needs_translation() with LEGACY_COMPAT=True
# ---------------------------------------------------------------------------

def run_needs_translation():
    """Test needs_translation() with LEGACY_COMPAT=True and various versions.

    Phase 4 tightened needs_translation() to ORIGINAL-only.  Iceman FW
    translate()/translate_response() are no-ops so needs_translation()
    returns False for ICEMAN.  _BLOCKED_CMDS_ICEMAN substitution is
    handled inside translate() without relying on this predicate.
    """
    _ensure_legacy_on()

    _set_version(pm3_compat.PM3_VERSION_ICEMAN)
    _test('NEEDS_TRANS iceman', pm3_compat.needs_translation(), False)

    _set_version(pm3_compat.PM3_VERSION_ORIGINAL)
    _test('NEEDS_TRANS original', pm3_compat.needs_translation(), True)

    _set_version(None)
    _test('NEEDS_TRANS none', pm3_compat.needs_translation(), False)


# ---------------------------------------------------------------------------
# Category 2 supplement: translate_response with LEGACY_COMPAT=True
# ---------------------------------------------------------------------------

def run_translate_response():
    """Test translate_response behavior with LEGACY_COMPAT=True.

    Phase 4 flipped the gate: translate_response runs only on LEGACY FW now.
    On iceman FW it is a pass-through.  On original FW it rewrites legacy
    output UP to iceman shape so iceman-native middleware regex matches.
    """
    _ensure_legacy_on()

    # On iceman firmware, translate_response is a pass-through no-op.
    _set_version(pm3_compat.PM3_VERSION_ICEMAN)
    resp = 'Write ( ok )\nSome data'
    _test('RESP iceman_noop',
          pm3_compat.translate_response(resp, 'hf mf wrbl'), resp)
    _test('RESP iceman_noop_prng',
          pm3_compat.translate_response('Prng detection..... weak\n', 'hf 14a info'),
          'Prng detection..... weak\n')

    # On original (legacy) firmware, legacy->iceman normalization applies.
    _set_version(pm3_compat.PM3_VERSION_ORIGINAL)
    _test('RESP original_wrbl_isOk01_to_iceman',
          'Write ( ok )' in pm3_compat.translate_response('isOk:01\n', 'hf mf wrbl'),
          True)
    _test('RESP original_wrbl_isOk00_to_iceman',
          'Write ( fail )' in pm3_compat.translate_response('isOk:00\n', 'hf mf wrbl'),
          True)
    _test('RESP original_prng_colon_to_dotted',
          'Prng detection..... weak' in pm3_compat.translate_response(
              'Prng detection: weak\n', 'hf 14a info'),
          True)

    # Empty text
    _test('RESP empty', pm3_compat.translate_response('', 'hf mf wrbl'), '')
    _test('RESP none', pm3_compat.translate_response(None, 'hf mf wrbl'), None)

    # Version not set -> no-op
    _set_version(None)
    _test('RESP version_none_noop',
          pm3_compat.translate_response('Write ( ok )', 'hf mf wrbl'),
          'Write ( ok )')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=' * 70)
    print('PM3 Compat Parity Test Suite — Agent 6')
    print('=' * 70)

    run_category1()
    print('  Category 1 (bidirectional): done (%d tests so far)' % _results['total'])

    run_blocked_commands()
    print('  Category 1 (blocked cmds): done (%d tests so far)' % _results['total'])

    run_edge_cases()
    print('  Category 1 (edge cases): done (%d tests so far)' % _results['total'])

    run_reverse_only()
    print('  Category 1 (reverse-only): done (%d tests so far)' % _results['total'])

    run_category2()
    print('  Category 2 (LEGACY_COMPAT gate): done (%d tests so far)' % _results['total'])

    run_needs_translation()
    print('  Category 2 (needs_translation): done (%d tests so far)' % _results['total'])

    run_translate_response()
    print('  Category 2 (translate_response): done (%d tests so far)' % _results['total'])

    run_category3()
    print('  Category 3 (_clean_pm3_output): done (%d tests so far)' % _results['total'])

    print()
    print('=' * 70)
    print('RESULTS: %d total, %d pass, %d fail' % (
        _results['total'], _results['pass'], _results['fail']))
    print('=' * 70)

    if _results['failures']:
        print()
        print('FAILURES:')
        for f in _results['failures']:
            print(f)
        print()

    # Exit with appropriate code
    sys.exit(0 if _results['fail'] == 0 else 1)


if __name__ == '__main__':
    main()
