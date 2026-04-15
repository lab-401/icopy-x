"""Tests for pm3_compat -- PM3 command syntax translation layer.

Covers:
  - strip_ansi: empty, plain, single code, nested codes, extended 256-color
  - _size_flag: all valid codes (0/1/2/4), unknown defaults to --1k, str vs int
  - _key_type_flag: A -> -a, B -> -b, lowercase
  - _target_key_type_flag: A -> --ta, B -> --tb, lowercase
  - detect_pm3_version: pm3_flash missing, exception, None ver, nikola, iceman
  - get_version / needs_translation: all states
  - translate: version=None (passthrough), version=original (passthrough),
               version=iceman (all 35 rules), empty, whitespace, unknown cmds
  - Idempotency: every translated command fed back through translate() unchanged
  - Edge cases: extra whitespace in input, partial matches, mixed case

All tests run headless.  External dependencies (pm3_flash) are fully mocked.
"""

import re
import pytest
from unittest import mock
from unittest.mock import MagicMock, patch

import pm3_compat
from pm3_compat import (
    strip_ansi,
    _size_flag,
    _key_type_flag,
    _target_key_type_flag,
    detect_pm3_version,
    get_version,
    needs_translation,
    translate,
    PM3_VERSION_ORIGINAL,
    PM3_VERSION_ICEMAN,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _reset_version():
    """Reset module-level _current_version before each test."""
    pm3_compat._current_version = None
    yield
    pm3_compat._current_version = None


@pytest.fixture
def iceman_mode():
    """Set pm3_compat to iceman mode for translation testing."""
    pm3_compat._current_version = PM3_VERSION_ICEMAN


@pytest.fixture
def original_mode():
    """Set pm3_compat to original mode (no translation)."""
    pm3_compat._current_version = PM3_VERSION_ORIGINAL


# =====================================================================
# strip_ansi
# =====================================================================

class TestStripAnsi:

    def test_none_returns_none(self):
        assert strip_ansi(None) is None

    def test_empty_returns_empty(self):
        assert strip_ansi('') == ''

    def test_plain_text_unchanged(self):
        assert strip_ansi('hello world') == 'hello world'

    def test_single_color_code(self):
        assert strip_ansi('\x1b[31mred\x1b[0m') == 'red'

    def test_bold_green(self):
        assert strip_ansi('\x1b[1;32mbold green\x1b[0m') == 'bold green'

    def test_extended_256_color(self):
        assert strip_ansi('\x1b[38;5;196mextended\x1b[0m') == 'extended'

    def test_multiple_codes_in_one_string(self):
        s = '\x1b[31mred\x1b[0m and \x1b[32mgreen\x1b[0m'
        assert strip_ansi(s) == 'red and green'

    def test_pm3_typical_output(self):
        s = '\x1b[32m[+]\x1b[0m Found valid key [ \x1b[33mFFFFFFFFFFFF\x1b[0m ]'
        assert strip_ansi(s) == '[+] Found valid key [ FFFFFFFFFFFF ]'

    def test_no_trailing_reset(self):
        assert strip_ansi('\x1b[1mstill bold') == 'still bold'


# =====================================================================
# Helper functions
# =====================================================================

class TestSizeFlag:

    def test_0_mini(self):
        assert _size_flag(0) == '--mini'
        assert _size_flag('0') == '--mini'

    def test_1_1k(self):
        assert _size_flag(1) == '--1k'
        assert _size_flag('1') == '--1k'

    def test_2_2k(self):
        assert _size_flag(2) == '--2k'
        assert _size_flag('2') == '--2k'

    def test_4_4k(self):
        assert _size_flag(4) == '--4k'
        assert _size_flag('4') == '--4k'

    def test_unknown_defaults_to_1k(self):
        assert _size_flag(3) == '--1k'
        assert _size_flag(99) == '--1k'
        assert _size_flag('foo') == '--1k'


class TestKeyTypeFlag:

    def test_a(self):
        assert _key_type_flag('A') == '-a'

    def test_b(self):
        assert _key_type_flag('B') == '-b'

    def test_lowercase_a(self):
        assert _key_type_flag('a') == '-a'

    def test_lowercase_b(self):
        assert _key_type_flag('b') == '-b'


class TestTargetKeyTypeFlag:

    def test_a(self):
        assert _target_key_type_flag('A') == '--ta'

    def test_b(self):
        assert _target_key_type_flag('B') == '--tb'

    def test_lowercase_a(self):
        assert _target_key_type_flag('a') == '--ta'

    def test_lowercase_b(self):
        assert _target_key_type_flag('b') == '--tb'


# =====================================================================
# detect_pm3_version
# =====================================================================

class TestDetectPM3Version:

    def test_pm3_flash_not_available(self):
        with patch.object(pm3_compat, 'pm3_flash', None):
            result = detect_pm3_version()
            assert result is None
            assert get_version() is None

    def test_get_running_version_exception(self):
        mock_flash = MagicMock()
        mock_flash.get_running_version.side_effect = RuntimeError('PM3 not found')
        with patch.object(pm3_compat, 'pm3_flash', mock_flash):
            result = detect_pm3_version()
            assert result is None
            assert get_version() is None

    def test_get_running_version_returns_none(self):
        mock_flash = MagicMock()
        mock_flash.get_running_version.return_value = None
        with patch.object(pm3_compat, 'pm3_flash', mock_flash):
            result = detect_pm3_version()
            assert result is None
            assert get_version() is None

    def test_nikola_present_means_original(self):
        mock_flash = MagicMock()
        mock_flash.get_running_version.return_value = {
            'nikola': 'NIKOLA:D=1234',
            'os': 'v3.1.0',
        }
        with patch.object(pm3_compat, 'pm3_flash', mock_flash):
            result = detect_pm3_version()
            assert result == PM3_VERSION_ORIGINAL
            assert get_version() == PM3_VERSION_ORIGINAL
            assert needs_translation() is False

    def test_no_nikola_means_iceman(self):
        mock_flash = MagicMock()
        mock_flash.get_running_version.return_value = {
            'nikola': '',
            'os': 'Iceman/master/v4.17768',
        }
        with patch.object(pm3_compat, 'pm3_flash', mock_flash):
            result = detect_pm3_version()
            assert result == PM3_VERSION_ICEMAN
            assert get_version() == PM3_VERSION_ICEMAN
            assert needs_translation() is True

    def test_empty_nikola_means_iceman(self):
        mock_flash = MagicMock()
        mock_flash.get_running_version.return_value = {'os': 'v4.17768'}
        with patch.object(pm3_compat, 'pm3_flash', mock_flash):
            result = detect_pm3_version()
            assert result == PM3_VERSION_ICEMAN


# =====================================================================
# get_version / needs_translation
# =====================================================================

class TestVersionAPI:

    def test_get_version_default_none(self):
        assert get_version() is None

    def test_needs_translation_when_none(self):
        assert needs_translation() is False

    def test_needs_translation_when_original(self, original_mode):
        assert needs_translation() is False

    def test_needs_translation_when_iceman(self, iceman_mode):
        assert needs_translation() is True


# =====================================================================
# translate -- passthrough cases
# =====================================================================

class TestTranslatePassthrough:
    """When version is None or original, commands pass through unchanged."""

    def test_empty_string_version_none(self):
        assert translate('') == ''

    def test_none_input(self):
        assert translate(None) is None

    def test_command_version_none(self):
        assert translate('hf mf rdbl 0 A FFFFFFFFFFFF') == 'hf mf rdbl 0 A FFFFFFFFFFFF'

    def test_command_version_original(self, original_mode):
        cmd = 'hf mf rdbl 0 A FFFFFFFFFFFF'
        assert translate(cmd) == cmd

    def test_empty_string_version_iceman(self, iceman_mode):
        assert translate('') == ''

    def test_unknown_command_passthrough_iceman(self, iceman_mode):
        cmd = 'hw tune'
        assert translate(cmd) == cmd

    def test_compatible_commands_passthrough_iceman(self, iceman_mode):
        """Commands that are identical in both versions pass through."""
        compatible = [
            'hf 14a info',
            'hf sea',
            'lf sea',
            'hf mf darkside',
            'hf mf cwipe',
            'hf mfu info',
            'hf 15 dump',
            # 'hf iclass info' is BLOCKED on iceman (hangs PM3 due to FPGA mismatch)
            'hf felica reader',
            'hf felica litedump',
            'lf t55xx detect',
            'lf t55xx dump',
            'lf t55xx wipe',
            'hw tune',
            'hw version',
            'hw ver',
            'hw connect',
        ]
        for cmd in compatible:
            assert translate(cmd) == cmd, f'Compatible command should pass through: {cmd}'


# =====================================================================
# translate -- Category 3: NAME CHANGES
# =====================================================================

class TestTranslateNameChanges:
    """EM command name changes (underscores to spaces, renames)."""

    def test_em410x_write(self, iceman_mode):
        assert translate('lf em 410x_write 1A2B3C4D5E 1') == 'lf em 410x clone --id 1A2B3C4D5E'

    def test_em410x_write_without_1_suffix(self, iceman_mode):
        assert translate('lf em 410x_write 1A2B3C4D5E') == 'lf em 410x clone --id 1A2B3C4D5E'

    def test_em410x_read(self, iceman_mode):
        assert translate('lf em 410x_read') == 'lf em 410x reader'

    def test_em410x_sim(self, iceman_mode):
        assert translate('lf em 410x_sim 1A2B3C4D5E') == 'lf em 410x sim --id 1A2B3C4D5E'

    def test_em4x05_write(self, iceman_mode):
        assert translate('lf em 4x05_write 1 DEADBEEF FFFFFFFF') == \
            'lf em 4x05 write -a 1 -d DEADBEEF -p FFFFFFFF'

    def test_em4x05_read(self, iceman_mode):
        assert translate('lf em 4x05_read 0 FFFFFFFF') == \
            'lf em 4x05 read -a 0 -p FFFFFFFF'

    def test_em4x05_info_with_pwd(self, iceman_mode):
        assert translate('lf em 4x05_info FFFFFFFF') == 'lf em 4x05 info -p FFFFFFFF'

    def test_em4x05_info_no_args(self, iceman_mode):
        assert translate('lf em 4x05_info') == 'lf em 4x05 info'

    def test_em4x05_dump(self, iceman_mode):
        assert translate('lf em 4x05_dump') == 'lf em 4x05 dump'


# =====================================================================
# translate -- Category 2: ARGUMENT CHANGES (complex)
# =====================================================================

class TestTranslateComplexArgs:

    # --- hf mf nested (most complex) ---

    def test_nested_key_a_target_a(self, iceman_mode):
        result = translate('hf mf nested o 0 A FFFFFFFFFFFF 4 A')
        assert result == 'hf mf nested --1k --blk 0 -a -k FFFFFFFFFFFF --tblk 4 --ta'

    def test_nested_key_b_target_b(self, iceman_mode):
        result = translate('hf mf nested o 0 B FFFFFFFFFFFF 4 B')
        assert result == 'hf mf nested --1k --blk 0 -b -k FFFFFFFFFFFF --tblk 4 --tb'

    def test_nested_key_a_target_b(self, iceman_mode):
        result = translate('hf mf nested o 3 A 000000000000 7 B')
        assert result == 'hf mf nested --1k --blk 3 -a -k 000000000000 --tblk 7 --tb'

    def test_nested_high_block(self, iceman_mode):
        result = translate('hf mf nested o 63 B AABBCCDDEEFF 32 A')
        assert result == 'hf mf nested --1k --blk 63 -b -k AABBCCDDEEFF --tblk 32 --ta'

    # --- hf mf staticnested ---

    def test_staticnested_1k(self, iceman_mode):
        result = translate('hf mf staticnested 1 0 A FFFFFFFFFFFF')
        assert result == 'hf mf staticnested --1k --blk 0 -a -k FFFFFFFFFFFF'

    def test_staticnested_4k(self, iceman_mode):
        result = translate('hf mf staticnested 4 0 B 000000000000')
        assert result == 'hf mf staticnested --4k --blk 0 -b -k 000000000000'

    def test_staticnested_mini(self, iceman_mode):
        result = translate('hf mf staticnested 0 0 A FFFFFFFFFFFF')
        assert result == 'hf mf staticnested --mini --blk 0 -a -k FFFFFFFFFFFF'

    # --- hf mf fchk (size flag mapping) ---

    def test_fchk_1k(self, iceman_mode):
        result = translate('hf mf fchk 1 /path/to/keys.dic')
        assert result == 'hf mf fchk --1k -f /path/to/keys.dic'

    def test_fchk_4k(self, iceman_mode):
        result = translate('hf mf fchk 4 /mnt/upan/keys.dic')
        assert result == 'hf mf fchk --4k -f /mnt/upan/keys.dic'

    def test_fchk_mini(self, iceman_mode):
        result = translate('hf mf fchk 0 keys.dic')
        assert result == 'hf mf fchk --mini -f keys.dic'

    def test_fchk_2k(self, iceman_mode):
        result = translate('hf mf fchk 2 keys.dic')
        assert result == 'hf mf fchk --2k -f keys.dic'

    # --- hf mf wrbl (4 positional args) ---

    def test_wrbl_key_a(self, iceman_mode):
        result = translate('hf mf wrbl 1 A FFFFFFFFFFFF 00112233445566778899AABBCCDDEEFF')
        assert result == 'hf mf wrbl --blk 1 -a -k FFFFFFFFFFFF -d 00112233445566778899AABBCCDDEEFF --force'

    def test_wrbl_key_b(self, iceman_mode):
        result = translate('hf mf wrbl 0 B 000000000000 AABBCCDD11223344AABBCCDD11223344')
        assert result == 'hf mf wrbl --blk 0 -b -k 000000000000 -d AABBCCDD11223344AABBCCDD11223344 --force'

    def test_wrbl_block_63(self, iceman_mode):
        result = translate('hf mf wrbl 63 A FFFFFFFFFFFF FF078069FFFFFFFFFFFF078069FFFFFFFF')
        assert result == 'hf mf wrbl --blk 63 -a -k FFFFFFFFFFFF -d FF078069FFFFFFFFFFFF078069FFFFFFFF --force'

    # --- hf mf rdbl ---

    def test_rdbl_key_a(self, iceman_mode):
        result = translate('hf mf rdbl 0 A FFFFFFFFFFFF')
        assert result == 'hf mf rdbl --blk 0 -a -k FFFFFFFFFFFF'

    def test_rdbl_key_b(self, iceman_mode):
        result = translate('hf mf rdbl 7 B 000000000000')
        assert result == 'hf mf rdbl --blk 7 -b -k 000000000000'

    # --- hf mf rdsc ---

    def test_rdsc_key_a(self, iceman_mode):
        result = translate('hf mf rdsc 0 A FFFFFFFFFFFF')
        assert result == 'hf mf rdsc -s 0 -a -k FFFFFFFFFFFF'

    def test_rdsc_key_b(self, iceman_mode):
        result = translate('hf mf rdsc 15 B 000000000000')
        assert result == 'hf mf rdsc -s 15 -b -k 000000000000'

    # --- hf mf csetuid (multiple positional args) ---

    def test_csetuid_with_wipe(self, iceman_mode):
        result = translate('hf mf csetuid 01020304 08 0004 w')
        assert result == 'hf mf csetuid -u 01020304 -s 08 -a 0004 -w'

    def test_csetuid_without_wipe(self, iceman_mode):
        result = translate('hf mf csetuid 01020304 08 0004')
        assert result == 'hf mf csetuid -u 01020304 -s 08 -a 0004'

    def test_csetuid_7byte_uid(self, iceman_mode):
        result = translate('hf mf csetuid 01020304050607 08 0044 w')
        assert result == 'hf mf csetuid -u 01020304050607 -s 08 -a 0044 -w'

    # --- hf mf csetblk ---

    def test_csetblk(self, iceman_mode):
        result = translate('hf mf csetblk 0 00112233445566778899AABBCCDDEEFF')
        assert result == 'hf mf csetblk --blk 0 -d 00112233445566778899AABBCCDDEEFF'

    # --- hf mf cgetblk ---

    def test_cgetblk(self, iceman_mode):
        assert translate('hf mf cgetblk 0') == 'hf mf cgetblk --blk 0'

    def test_cgetblk_high_block(self, iceman_mode):
        assert translate('hf mf cgetblk 63') == 'hf mf cgetblk --blk 63'

    # --- hf mf cload ---

    def test_cload(self, iceman_mode):
        result = translate('hf mf cload b /mnt/upan/dump.eml')
        assert result == 'hf mf cload -f /mnt/upan/dump.eml'

    # --- hf mf csave ---

    def test_csave(self, iceman_mode):
        result = translate('hf mf csave 1 o /mnt/upan/dump')
        assert result == 'hf mf csave --1k -f /mnt/upan/dump'

    def test_csave_ignores_type_arg(self, iceman_mode):
        """The {type} argument is ignored; always outputs --1k."""
        result = translate('hf mf csave 4 o /mnt/upan/dump')
        assert result == 'hf mf csave --1k -f /mnt/upan/dump'

    # --- hf mf dump / restore (bare) ---

    def test_dump_bare(self, iceman_mode):
        assert translate('hf mf dump') == 'hf mf dump --1k'

    def test_restore_bare(self, iceman_mode):
        assert translate('hf mf restore') == 'hf mf restore --1k'


# =====================================================================
# translate -- Category 2: ARGUMENT CHANGES (simple flag prefix)
# =====================================================================

class TestTranslateSimpleFlags:

    def test_mfu_dump(self, iceman_mode):
        assert translate('hf mfu dump f myfile') == 'hf mfu dump -f myfile'

    def test_mfu_restore(self, iceman_mode):
        result = translate('hf mfu restore s e f myfile')
        assert result == 'hf mfu restore -s -e -f myfile'

    def test_15_restore(self, iceman_mode):
        result = translate('hf 15 restore f myfile.bin')
        assert result == 'hf 15 restore -f myfile.bin'

    def test_15_csetuid(self, iceman_mode):
        result = translate('hf 15 csetuid E011223344556677')
        assert result == 'hf 15 csetuid -u E011223344556677'

    def test_iclass_dump(self, iceman_mode):
        result = translate('hf iclass dump k 001122334455667B')
        assert result == 'hf iclass dump -k 001122334455667B'

    def test_iclass_chk(self, iceman_mode):
        result = translate('hf iclass chk f dict.dic')
        assert result == 'hf iclass chk -f dict.dic'

    def test_iclass_rdbl(self, iceman_mode):
        result = translate('hf iclass rdbl b 7 k 001122334455667B')
        assert result == 'hf iclass rdbl --blk 7 -k 001122334455667B'

    def test_iclass_rdbl_elite(self, iceman_mode):
        result = translate('hf iclass rdbl b 1 k AFA785A7DAB33378 e')
        assert result == 'hf iclass rdbl --blk 1 -k AFA785A7DAB33378 --elite'

    def test_iclass_dump_elite(self, iceman_mode):
        result = translate('hf iclass dump k 001122334455667B e')
        assert result == 'hf iclass dump -k 001122334455667B --elite'

    def test_t55xx_detect_pwd(self, iceman_mode):
        result = translate('lf t55xx detect p FFFFFFFF')
        assert result == 'lf t55xx detect -p FFFFFFFF'

    def test_t55xx_read(self, iceman_mode):
        result = translate('lf t55xx read b 0')
        assert result == 'lf t55xx read -b 0'

    def test_t55xx_write(self, iceman_mode):
        result = translate('lf t55xx write b 0 d 11223344')
        assert result == 'lf t55xx write -b 0 -d 11223344'

    def test_t55xx_restore(self, iceman_mode):
        result = translate('lf t55xx restore f myfile')
        assert result == 'lf t55xx restore -f myfile'

    def test_t55xx_chk(self, iceman_mode):
        result = translate('lf t55xx chk f dict.dic')
        assert result == 'lf t55xx chk -f dict.dic'

    def test_hid_clone(self, iceman_mode):
        result = translate('lf hid clone 200670012F')
        assert result == 'lf hid clone -r 200670012F'

    def test_data_save(self, iceman_mode):
        result = translate('data save f /mnt/upan/capture')
        assert result == 'data save -f /mnt/upan/capture'


# =====================================================================
# translate -- hf 14a raw (-p -> -k flag swap)
# =====================================================================

class TestTranslate14aRaw:

    def test_basic_p_to_k(self, iceman_mode):
        result = translate('hf 14a raw -p -a -b 7 40')
        assert result == 'hf 14a raw -k -a -b 7 40'

    def test_p_at_end(self, iceman_mode):
        result = translate('hf 14a raw -a -b 7 40 -p')
        assert result == 'hf 14a raw -a -b 7 40 -k'

    def test_p_in_middle(self, iceman_mode):
        result = translate('hf 14a raw -a -p -b 7 40')
        assert result == 'hf 14a raw -a -k -b 7 40'

    def test_p_only_flag(self, iceman_mode):
        result = translate('hf 14a raw -p')
        assert result == 'hf 14a raw -k'

    def test_no_p_flag_passthrough(self, iceman_mode):
        """hf 14a raw without -p should pass through unchanged."""
        cmd = 'hf 14a raw -a -b 7 40'
        assert translate(cmd) == cmd

    def test_already_translated_k_passthrough(self, iceman_mode):
        """hf 14a raw with -k (already translated) should pass through."""
        cmd = 'hf 14a raw -k -a -b 7 40'
        assert translate(cmd) == cmd


# =====================================================================
# Idempotency -- already-translated commands must pass through unchanged
# =====================================================================

class TestIdempotency:
    """Every translated command fed back through translate() must be unchanged."""

    TRANSLATED_COMMANDS = [
        # NAME CHANGES
        'lf em 410x clone --id 1A2B3C4D5E',
        'lf em 410x reader',
        'lf em 410x sim --id 1A2B3C4D5E',
        'lf em 4x05 write -a 1 -d DEADBEEF -p FFFFFFFF',
        'lf em 4x05 read -a 0 -p FFFFFFFF',
        'lf em 4x05 info -p FFFFFFFF',
        'lf em 4x05 info',
        'lf em 4x05 dump',
        # COMPLEX ARG CHANGES
        'hf mf nested --1k --blk 0 -a -k FFFFFFFFFFFF --tblk 4 --ta',
        'hf mf staticnested --1k --blk 0 -a -k FFFFFFFFFFFF',
        'hf mf fchk --1k -f /path/to/keys.dic',
        'hf mf wrbl --blk 1 -a -k FFFFFFFFFFFF -d 00112233445566778899AABBCCDDEEFF --force',
        'hf mf rdbl --blk 0 -a -k FFFFFFFFFFFF',
        'hf mf rdsc -s 0 -a -k FFFFFFFFFFFF',
        'hf mf csetuid -u 01020304 -s 08 -a 0004 -w',
        'hf mf csetuid -u 01020304 -s 08 -a 0004',
        'hf mf csetblk --blk 0 -d 00112233445566778899AABBCCDDEEFF',
        'hf mf cgetblk --blk 0',
        'hf mf cload -f /mnt/upan/dump.eml',
        'hf mf csave --1k -f /mnt/upan/dump',
        'hf mf dump --1k',
        'hf mf restore --1k',
        # SIMPLE FLAG CHANGES
        'hf mfu dump -f myfile',
        'hf mfu restore -s -e -f myfile',
        'hf 15 restore -f myfile.bin',
        'hf 15 csetuid -u E011223344556677',
        'hf iclass dump -k 001122334455667B',
        'hf iclass chk -f dict.dic',
        'hf iclass rdbl --blk 7 -k 001122334455667B',
        'lf t55xx detect -p FFFFFFFF',
        'lf t55xx read -b 0',
        'lf t55xx write -b 0 -d 11223344',
        'lf t55xx restore -f myfile',
        'lf t55xx chk -f dict.dic',
        'lf hid clone -r 200670012F',
        'data save -f /mnt/upan/capture',
        # 14a RAW (already has -k not -p)
        'hf 14a raw -k -a -b 7 40',
    ]

    @pytest.mark.parametrize('cmd', TRANSLATED_COMMANDS)
    def test_already_translated_unchanged(self, iceman_mode, cmd):
        """An already-translated command fed through translate() must not change."""
        assert translate(cmd) == cmd


# =====================================================================
# Edge cases
# =====================================================================

class TestEdgeCases:

    def test_leading_trailing_whitespace_stripped(self, iceman_mode):
        """translate() strips input before matching, returns translated (no padding)."""
        result = translate('  hf mf rdbl 0 A FFFFFFFFFFFF  ')
        assert result == 'hf mf rdbl --blk 0 -a -k FFFFFFFFFFFF'

    def test_no_match_preserves_original_whitespace(self, iceman_mode):
        """Unmatched commands returned as-is, preserving original cmd."""
        cmd = '  hw tune  '
        assert translate(cmd) == cmd

    def test_partial_command_no_false_match(self, iceman_mode):
        """Partial/prefix commands must not falsely match a translation rule."""
        assert translate('hf mf rdbl') == 'hf mf rdbl'
        assert translate('hf mf wrbl') == 'hf mf wrbl'
        assert translate('hf mf nested') == 'hf mf nested'
        assert translate('hf mf fchk') == 'hf mf fchk'

    def test_extra_args_no_false_match(self, iceman_mode):
        """Commands with too many args must not match ($ anchor enforces)."""
        cmd = 'hf mf rdbl 0 A FFFFFFFFFFFF EXTRA'
        assert translate(cmd) == cmd

    def test_case_sensitive_key_type(self, iceman_mode):
        """Regex [AB] is uppercase only; lowercase a/b won't match the rule.
        This is correct behavior: .so binaries always emit uppercase."""
        cmd = 'hf mf rdbl 0 a FFFFFFFFFFFF'
        assert translate(cmd) == cmd  # passthrough (no match)

    def test_em410x_write_id_only_no_suffix(self, iceman_mode):
        """lf em 410x_write with ID but no '1' suffix still translates."""
        result = translate('lf em 410x_write AABBCCDDEE')
        assert result == 'lf em 410x clone --id AABBCCDDEE'

    def test_iclass_wrbl_fix_b_to_blk(self, iceman_mode):
        """iclass wrbl: -b is not valid on iceman, must become --blk."""
        cmd = 'hf iclass wrbl -b 7 -d 0102030405060708 -k 001122334455667B'
        assert translate(cmd) == 'hf iclass wrbl --blk 7 -d 0102030405060708 -k 001122334455667B'

    def test_t55xx_detect_no_pwd(self, iceman_mode):
        """lf t55xx detect without password is compatible -- passthrough."""
        cmd = 'lf t55xx detect'
        assert translate(cmd) == cmd

    def test_hf_mf_dump_with_args_no_match(self, iceman_mode):
        """Only bare 'hf mf dump' (no args) triggers the --1k addition."""
        cmd = 'hf mf dump --4k'
        assert translate(cmd) == cmd

    def test_hf_mf_restore_with_args_no_match(self, iceman_mode):
        """Only bare 'hf mf restore' (no args) triggers the --1k addition."""
        cmd = 'hf mf restore --4k'
        assert translate(cmd) == cmd

    def test_csetuid_w_not_partial_match(self, iceman_mode):
        """'w' suffix must be exactly 'w', not any word starting with w."""
        cmd = 'hf mf csetuid 01020304 08 0004 wipe'
        assert translate(cmd) == cmd  # 'wipe' != 'w', no match


# =====================================================================
# Full round-trip: original syntax -> translate -> expected RRG syntax
# (Comprehensive mapping from the 54-command compat table)
# =====================================================================

class TestFullCompatTable:
    """Test every ARGS CHANGED / NAME CHANGED row from PM3_COMMAND_COMPAT.md."""

    COMPAT_CASES = [
        # (old_syntax, expected_rrg_syntax)
        # Row 4: fchk
        ('hf mf fchk 1 /path/to/keys.dic', 'hf mf fchk --1k -f /path/to/keys.dic'),
        # Row 5: nested
        ('hf mf nested o 0 A FFFFFFFFFFFF 4 A',
         'hf mf nested --1k --blk 0 -a -k FFFFFFFFFFFF --tblk 4 --ta'),
        # Row 6: staticnested
        ('hf mf staticnested 1 0 A FFFFFFFFFFFF',
         'hf mf staticnested --1k --blk 0 -a -k FFFFFFFFFFFF'),
        # Row 8: dump
        ('hf mf dump', 'hf mf dump --1k'),
        # Row 9: restore
        ('hf mf restore', 'hf mf restore --1k'),
        # Row 10: cgetblk
        ('hf mf cgetblk 0', 'hf mf cgetblk --blk 0'),
        # Row 11: csetblk
        ('hf mf csetblk 0 00112233445566778899AABBCCDDEEFF',
         'hf mf csetblk --blk 0 -d 00112233445566778899AABBCCDDEEFF'),
        # Row 12: csetuid
        ('hf mf csetuid 01020304 08 0004 w',
         'hf mf csetuid -u 01020304 -s 08 -a 0004 -w'),
        # Row 13: cload
        ('hf mf cload b /path/to/dump', 'hf mf cload -f /path/to/dump'),
        # Row 14: csave
        ('hf mf csave 1 o myfile', 'hf mf csave --1k -f myfile'),
        # Row 16: rdbl
        ('hf mf rdbl 0 A FFFFFFFFFFFF',
         'hf mf rdbl --blk 0 -a -k FFFFFFFFFFFF'),
        # Row 17: wrbl
        ('hf mf wrbl 1 A FFFFFFFFFFFF 00112233445566778899AABBCCDDEEFF',
         'hf mf wrbl --blk 1 -a -k FFFFFFFFFFFF -d 00112233445566778899AABBCCDDEEFF --force'),
        # Row 18: rdsc
        ('hf mf rdsc 0 A FFFFFFFFFFFF',
         'hf mf rdsc -s 0 -a -k FFFFFFFFFFFF'),
        # Row 20: mfu dump
        ('hf mfu dump f myfile', 'hf mfu dump -f myfile'),
        # Row 21: mfu restore
        ('hf mfu restore s e f myfile', 'hf mfu restore -s -e -f myfile'),
        # Row 23: 15 restore
        ('hf 15 restore f myfile.bin', 'hf 15 restore -f myfile.bin'),
        # Row 24: 15 csetuid
        ('hf 15 csetuid E011223344556677', 'hf 15 csetuid -u E011223344556677'),
        # Row 26: iclass dump
        ('hf iclass dump k 001122334455667B', 'hf iclass dump -k 001122334455667B'),
        # Row 27: iclass chk
        ('hf iclass chk f dict.dic', 'hf iclass chk -f dict.dic'),
        # Row 28: iclass rdbl
        ('hf iclass rdbl b 7 k 001122334455667B',
         'hf iclass rdbl --blk 7 -k 001122334455667B'),
        # Row 32: t55xx detect with pwd
        ('lf t55xx detect p FFFFFFFF', 'lf t55xx detect -p FFFFFFFF'),
        # Row 35: t55xx read
        ('lf t55xx read b 0', 'lf t55xx read -b 0'),
        # Row 36: t55xx write
        ('lf t55xx write b 0 d 11223344', 'lf t55xx write -b 0 -d 11223344'),
        # Row 37: t55xx restore
        ('lf t55xx restore f myfile', 'lf t55xx restore -f myfile'),
        # Row 38: t55xx chk
        ('lf t55xx chk f dict.dic', 'lf t55xx chk -f dict.dic'),
        # Row 39: em 410x_read
        ('lf em 410x_read', 'lf em 410x reader'),
        # Row 40: em 410x_sim
        ('lf em 410x_sim 1A2B3C4D5E', 'lf em 410x sim --id 1A2B3C4D5E'),
        # Row 41: em 410x_write
        ('lf em 410x_write 1A2B3C4D5E 1', 'lf em 410x clone --id 1A2B3C4D5E'),
        # Row 42: em 4x05_info (no args)
        ('lf em 4x05_info', 'lf em 4x05 info'),
        # Row 42: em 4x05_info (with pwd)
        ('lf em 4x05_info FFFFFFFF', 'lf em 4x05 info -p FFFFFFFF'),
        # Row 43: em 4x05_dump
        ('lf em 4x05_dump', 'lf em 4x05 dump'),
        # Row 44: em 4x05_read
        ('lf em 4x05_read 0 FFFFFFFF', 'lf em 4x05 read -a 0 -p FFFFFFFF'),
        # Row 45: em 4x05_write
        ('lf em 4x05_write 1 DEADBEEF FFFFFFFF',
         'lf em 4x05 write -a 1 -d DEADBEEF -p FFFFFFFF'),
        # Row 46: hid clone
        ('lf hid clone 200670012F', 'lf hid clone -r 200670012F'),
        # Row 53: data save
        ('data save f /mnt/upan/capture', 'data save -f /mnt/upan/capture'),
        # Row 54: 14a raw -p -> -k
        ('hf 14a raw -p -a -b 7 40', 'hf 14a raw -k -a -b 7 40'),
    ]

    @pytest.mark.parametrize('old_cmd,expected', COMPAT_CASES,
                             ids=[c[0][:50] for c in COMPAT_CASES])
    def test_compat_table_translation(self, iceman_mode, old_cmd, expected):
        assert translate(old_cmd) == expected
