"""Tests for renaming dumps (Dump Files > Tag Info > DOWN).

Covers:
  * appfiles.rename_dump_set — whole-set rename, conflicts, validation,
    rollback on failure.
  * ReadFromHistoryActivity — renamed dumps still give the same Tag Info
    values (read from the dump files instead of the filename).
  * RenameDumpActivity — keyboard flow, Save/Cancel, blocked types.
"""

import json
import os
import tempfile

import pytest

import actstack
from tests.ui.conftest import MockCanvas
from _constants import KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR, KEY_RIGHT


@pytest.fixture(autouse=True)
def _setup():
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


@pytest.fixture
def root():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _write(directory, name, content):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, 'wb' if isinstance(content, bytes) else 'w') as f:
        f.write(content)
    return path


def _mf1_bin_1k(uid='DEADBEEF', sak=0x08, atqa=(0x04, 0x00)):
    u = bytes.fromhex(uid)
    block0 = u + bytes([u[0] ^ u[1] ^ u[2] ^ u[3], sak, atqa[0], atqa[1]]) + b'\x00' * 8
    return block0 + b'\x00' * (1024 - 16)


def _mf1_json(uid='DEADBEEF', sak='08', atqa_le='0400'):
    return json.dumps({'FileType': 'mfc v2',
                       'Card': {'UID': uid, 'ATQA': atqa_le, 'SAK': sak}})


def _mfu_bin(uid='04112233445566', pages=16):
    u = bytes.fromhex(uid)
    header = b'\x00' * 11 + bytes([pages - 1]) + b'\x00' * 44
    data = u[0:3] + bytes([0x88 ^ u[0] ^ u[1] ^ u[2]]) + u[3:7] + b'\x00'
    return header + data + b'\x00' * (pages * 4 - len(data))


def _cache_for(path):
    from activity_main import ReadFromHistoryActivity
    act = actstack.start_activity(ReadFromHistoryActivity, path)
    return act, act._scan_cache


def _type_on_keyboard(act, text):
    kb = act._keyboard
    for ch in text:
        for r, row in enumerate(kb._rows):
            for i, (k, _s) in enumerate(row):
                if k == ch:
                    kb._focus_row, kb._focus_idx = r, i
        act.onKeyEvent(KEY_OK)


# ======================================================================
# appfiles.rename_dump_set
# ======================================================================

class TestRenameDumpSet:
    def test_renames_whole_set_keeping_extensions(self, root):
        import appfiles
        d = os.path.join(root, 'mf1')
        p = _write(d, 'M1-1K-4B_DEADBEEF_1.bin', b'x')
        _write(d, 'M1-1K-4B_DEADBEEF_1.json', '{}')
        _write(d, 'M1-1K-4B_DEADBEEF_1.eml', 'x')
        _write(d, 'OTHER_1.bin', b'y')
        ret, new = appfiles.rename_dump_set(p, 'OFFICE', True)
        assert ret == appfiles.RENAME_OK
        assert new == os.path.join(d, 'OFFICE.bin')
        assert sorted(os.listdir(d)) == ['OFFICE.bin', 'OFFICE.eml', 'OFFICE.json', 'OTHER_1.bin']

    def test_single_file_mode(self, root):
        import appfiles
        d = os.path.join(root, 'em410x')
        p = _write(d, 'EM410x-ID_0F0368568B_1.txt', 'a\nb')
        _write(d, 'EM410x-ID_0F0368568B_1.bak', 'keep')
        ret, new = appfiles.rename_dump_set(p, 'FRONT', False)
        assert ret == appfiles.RENAME_OK
        assert sorted(os.listdir(d)) == ['EM410x-ID_0F0368568B_1.bak', 'FRONT.txt']

    def test_refuses_existing_name(self, root):
        import appfiles
        d = os.path.join(root, 'mf1')
        p = _write(d, 'A.bin', b'x')
        _write(d, 'b.eml', 'x')          # case-insensitive clash
        ret, new = appfiles.rename_dump_set(p, 'B', True)
        assert ret == appfiles.RENAME_EXISTS
        assert new == p
        assert os.path.exists(p)

    @pytest.mark.parametrize('name', ['', ' A', 'A/B', 'A:B', '..', '.HIDDEN'])
    def test_refuses_invalid_names(self, root, name):
        import appfiles
        p = _write(os.path.join(root, 'mf1'), 'A.bin', b'x')
        ret, _new = appfiles.rename_dump_set(p, name, True)
        assert ret == appfiles.RENAME_INVALID
        assert os.path.exists(p)

    def test_same_name_is_noop(self, root):
        import appfiles
        p = _write(os.path.join(root, 'mf1'), 'A.bin', b'x')
        assert appfiles.rename_dump_set(p, 'A', True) == (appfiles.RENAME_OK, p)

    def test_rollback_when_a_rename_fails(self, root, monkeypatch):
        import appfiles
        d = os.path.join(root, 'mf1')
        p = _write(d, 'A.bin', b'x')
        _write(d, 'A.json', '{}')
        real_rename = os.rename
        calls = {'n': 0}

        def flaky(src, dst):
            calls['n'] += 1
            if calls['n'] == 2:
                raise OSError('disk error')
            real_rename(src, dst)

        monkeypatch.setattr(appfiles.os, 'rename', flaky)
        ret, new = appfiles.rename_dump_set(p, 'NEW', True)
        assert ret == appfiles.RENAME_FAILED
        assert new == p
        assert sorted(os.listdir(d)) == ['A.bin', 'A.json']


# ======================================================================
# Tag Info values for renamed dumps
# ======================================================================

class TestRenamedTagInfo:
    def test_mf1_renamed_with_json(self, root):
        d = os.path.join(root, 'mf1')
        p = _write(d, 'OFFICE.bin', _mf1_bin_1k())
        _write(d, 'OFFICE.json', _mf1_json())
        _act, cache = _cache_for(p)
        assert cache['type'] == 1
        assert cache['uid'] == 'DEADBEEF'
        assert cache['len'] == 4
        assert (cache['sak'], cache['atqa']) == ('08', '0004')

    def test_mf1_renamed_bin_only_uses_block0(self, root):
        p = _write(os.path.join(root, 'mf1'), 'CARD.bin',
                   _mf1_bin_1k('11223344', sak=0x18, atqa=(0x02, 0x00))[:16] + b'\x00' * 4080)
        _act, cache = _cache_for(p)
        assert cache['type'] == 0                 # 4096 bytes -> 4K
        assert cache['uid'] == '11223344'
        assert (cache['sak'], cache['atqa']) == ('18', '0002')

    def test_mf1_renamed_mini_size_from_file(self, root):
        p = _write(os.path.join(root, 'mf1'), 'SMALL.bin', _mf1_bin_1k()[:320])
        _act, cache = _cache_for(p)
        assert cache['type'] == 25

    def test_mfu_renamed_uid_from_json(self, root):
        d = os.path.join(root, 'mfu')
        p = _write(d, 'TAG.bin', _mfu_bin('04AABBCCDDEEFF'))
        _write(d, 'TAG.json', json.dumps({'Card': {'UID': '04112233445566'}}))
        _act, cache = _cache_for(p)
        assert cache['uid'] == '04112233445566'

    def test_mfu_renamed_uid_from_bin(self, root):
        p = _write(os.path.join(root, 'mfu'), 'TAG.bin', _mfu_bin('04AABBCCDDEEFF', 135))
        _act, cache = _cache_for(p)
        assert cache['uid'] == '04AABBCCDDEEFF'

    def test_mfu_bad_bin_falls_back(self, root):
        p = _write(os.path.join(root, 'mfu'), 'TAG.bin', b'\x04' * 120)
        _act, cache = _cache_for(p)
        assert cache['uid'] == '00000000000000'   # previous default

    def test_t55xx_renamed_b0_from_bin(self, root):
        p = _write(os.path.join(root, 't55xx'), 'MY_OFFICE_DOOR_CARD_1.bin',
                   bytes.fromhex('00148040') + b'\x00' * 44)
        _act, cache = _cache_for(p)
        assert cache['b0'] == '00148040'

    def test_hf14a_renamed_uid_from_txt(self, root):
        p = _write(os.path.join(root, 'hf14a'), 'BANK.txt',
                   'UID: 08A1B2C3\nSAK: 20\nATQA: 0004\n')
        _act, cache = _cache_for(p)
        assert cache['uid'] == '08A1B2C3'

    def test_device_name_still_used_first(self, root):
        # Device-format name wins over file contents (unchanged behaviour)
        p = _write(os.path.join(root, 't55xx'), 'T55xx_000880E0_00000000_00000000_1.bin',
                   bytes.fromhex('00148040') + b'\x00' * 44)
        _act, cache = _cache_for(p)
        assert cache['b0'] == '000880E0'


# ======================================================================
# Rename flow
# ======================================================================

class TestRenameFlow:
    def _open(self, path):
        from activity_main import ReadFromHistoryActivity
        return actstack.start_activity(ReadFromHistoryActivity, path)

    def test_down_opens_keyboard_with_placeholder(self, root):
        from activity_main import RenameDumpActivity
        p = _write(os.path.join(root, 'mf1'), 'M1-1K-4B_DEADBEEF_1.bin', _mf1_bin_1k())
        self._open(p).onKeyEvent(KEY_DOWN)
        top = actstack.get_current_activity()
        assert isinstance(top, RenameDumpActivity)
        assert top._keyboard._placeholder == 'M1-1K-4B_DEADBEEF_1'
        assert top._whole_set is True

    def test_save_renames_and_refreshes_tag_info(self, root):
        d = os.path.join(root, 'mf1')
        p = _write(d, 'M1-1K-4B_DEADBEEF_1.bin', _mf1_bin_1k())
        _write(d, 'M1-1K-4B_DEADBEEF_1.json', _mf1_json())
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        kb_act = actstack.get_current_activity()
        _type_on_keyboard(kb_act, 'DOOR')
        kb_act.onKeyEvent(KEY_M2)
        assert actstack.get_current_activity() is info
        assert info._file_path == os.path.join(d, 'DOOR.bin')
        assert sorted(os.listdir(d)) == ['DOOR.bin', 'DOOR.json']
        assert info._scan_cache['uid'] == 'DEADBEEF'
        assert info._scan_cache['type'] == 1

    def test_save_with_nothing_typed_keeps_name(self, root):
        d = os.path.join(root, 'mf1')
        p = _write(d, 'M1-1K-4B_DEADBEEF_1.bin', _mf1_bin_1k())
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        actstack.get_current_activity().onKeyEvent(KEY_M2)
        assert actstack.get_current_activity() is info
        assert os.listdir(d) == ['M1-1K-4B_DEADBEEF_1.bin']

    def test_cancel_keeps_name(self, root):
        d = os.path.join(root, 'mf1')
        p = _write(d, 'M1-1K-4B_DEADBEEF_1.bin', _mf1_bin_1k())
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        kb_act = actstack.get_current_activity()
        _type_on_keyboard(kb_act, 'X')
        kb_act.onKeyEvent(KEY_M1)
        assert actstack.get_current_activity() is info
        assert os.listdir(d) == ['M1-1K-4B_DEADBEEF_1.bin']

    def test_existing_name_stays_on_keyboard(self, root):
        from activity_main import RenameDumpActivity
        d = os.path.join(root, 'mf1')
        p = _write(d, 'M1-1K-4B_DEADBEEF_1.bin', _mf1_bin_1k())
        _write(d, 'TAKEN.bin', _mf1_bin_1k())
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        kb_act = actstack.get_current_activity()
        _type_on_keyboard(kb_act, 'TAKEN')
        kb_act.onKeyEvent(KEY_M2)
        assert isinstance(actstack.get_current_activity(), RenameDumpActivity)
        assert kb_act._toast.isShow()
        assert kb_act._keyboard.getText() == 'TAKEN'

    def test_icode_not_offered(self, root):
        p = _write(os.path.join(root, 'icode'), 'ICODE_E004010012345678_1.bin', b'\x00' * 32)
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        assert actstack.get_current_activity() is info
        assert info._toast.isShow()

    def test_old_single_line_lf_refused(self, root):
        p = _write(os.path.join(root, 'em410x'), 'EM410x-ID_0F0368568B_1.txt', '0F0368568B')
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        assert actstack.get_current_activity() is info
        assert info._toast.isShow()

    def test_v2_lf_dump_can_be_renamed(self, root):
        from activity_main import RenameDumpActivity
        p = _write(os.path.join(root, 'em410x'), 'EM410x-ID_0F0368568B_1.txt',
                   '0F0368568B\n0F0368568B')
        self._open(p).onKeyEvent(KEY_DOWN)
        top = actstack.get_current_activity()
        assert isinstance(top, RenameDumpActivity)
        assert top._whole_set is True

    def test_em4305_bin_and_json_renamed_together(self, root):
        d = os.path.join(root, 'em4x05')
        p = _write(d, 'EM4305_AABBCCDD_1.bin', b'\x00' * 64)
        _write(d, 'EM4305_AABBCCDD_1.json', '{}')
        info = self._open(p)
        info.onKeyEvent(KEY_DOWN)
        kb_act = actstack.get_current_activity()
        _type_on_keyboard(kb_act, 'GATE')
        kb_act.onKeyEvent(KEY_M2)
        assert sorted(os.listdir(d)) == ['GATE.bin', 'GATE.json']
        assert info._file_path == os.path.join(d, 'GATE.bin')

    def test_keyboard_keys_do_not_leak(self, root):
        p = _write(os.path.join(root, 'mf1'), 'M1-1K-4B_DEADBEEF_1.bin', _mf1_bin_1k())
        self._open(p).onKeyEvent(KEY_DOWN)
        kb_act = actstack.get_current_activity()
        kb_act.onKeyEvent(KEY_RIGHT)
        kb_act.onKeyEvent(KEY_DOWN)
        assert kb_act._keyboard.getFocusKey() == 'J'
        kb_act.onKeyEvent(KEY_PWR)
        assert not isinstance(actstack.get_current_activity(), type(kb_act))


# ======================================================================
# Dump Files list labels
# ======================================================================

class TestListLabels:
    @pytest.mark.parametrize('name,label', [
        ('M1-1K-4B_DAEFB416_1.bin', '1K-4B-DAEFB416(1)'),
        ('T55xx_00148040_00000000_00000000_1.bin', '00148040(1)'),
        ('M0-UL_04DDEEFF001122_1.bin', '04DDEEFF001122(1)'),
        ('EM410x-ID_0F0368568B_1.txt', '0F0368568B(1)'),
        ('Paxton-ID_AABBCCDD_11223344_1.txt', 'AABBCCDD_11223344(1)'),
    ])
    def test_device_names_still_shortened(self, name, label):
        from activity_main import CardWalletActivity
        assert CardWalletActivity._formatFilename(name) == label

    @pytest.mark.parametrize('name', [
        'OFFICE', 'FRONT-DOOR_2', 'BACKUP_2_1', 'MY_OFFICE_DOOR_CARD_1',
        'GYM-CARD_CAFE_2',
    ])
    def test_renamed_names_shown_in_full(self, name):
        from activity_main import CardWalletActivity
        assert CardWalletActivity._formatFilename(name + '.bin') == name


# ======================================================================
# Plus 2K dumps (issue #31)
# ======================================================================

class TestPlus2K:
    def test_device_named_plus2k_is_type_26(self, root):
        p = _write(os.path.join(root, 'mf1'), 'M1-Plus-2K-4B_DEADBEEF_1.bin',
                   _mf1_bin_1k()[:16] + b'\x00' * 2032)
        _act, cache = _cache_for(p)
        assert cache['type'] == 26
        assert cache['uid'] == 'DEADBEEF'
        assert cache['nameStr'] == 'M1 Plus 2K (4B)'

    def test_renamed_2048_byte_dump_is_type_26(self, root):
        p = _write(os.path.join(root, 'mf1'), 'GARAGE.bin',
                   _mf1_bin_1k()[:16] + b'\x00' * 2032)
        _act, cache = _cache_for(p)
        assert cache['type'] == 26
        assert cache['uid'] == 'DEADBEEF'

    def test_write_size_is_2k(self, root):
        import hfmfread
        p = _write(os.path.join(root, 'mf1'), 'M1-Plus-2K-4B_DEADBEEF_1.bin',
                   _mf1_bin_1k()[:16] + b'\x00' * 2032)
        _act, cache = _cache_for(p)
        assert hfmfread.sizeGuess(cache['type']) == 2048

    def test_template_label(self):
        import template
        assert template.TYPE_TEMPLATE[26][1] == 'M1 Plus 2K'
