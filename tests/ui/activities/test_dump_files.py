"""Tests for CardWalletActivity (Dump Files).

Ground truth:
    - Title: "Dump Files" (resources key: card_wallet)
    - Modes: TYPE_LIST -> FILE_LIST -> DELETE_CONFIRM
    - TYPE_LIST: 28 dump types, UP/DOWN scroll, OK selects type
    - FILE_LIST: M1=Details(toggle date), M2=Delete
    - DELETE_CONFIRM: M1=No, M2=Yes
    - PWR in FILE_LIST: back to TYPE_LIST
    - PWR in TYPE_LIST: finish
    - Source: docs/UI_Mapping/02_dump_files/README.md
"""

import os
import tempfile
import pytest

import actstack
from tests.ui.conftest import MockCanvas
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


@pytest.fixture(autouse=True)
def _setup():
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


@pytest.fixture
def dump_dir():
    """Create a temp directory with test dump files."""
    with tempfile.TemporaryDirectory() as d:
        # Create some test dump files
        for name in ['AABBCCDD_001.bin', 'EEFF0011_002.eml', '11223344_003.txt']:
            with open(os.path.join(d, name), 'w') as f:
                f.write('test dump data')
        yield d


@pytest.fixture
def empty_dir():
    """Create a temp empty directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _create_wallet(bundle=None):
    from activity_main import CardWalletActivity
    return actstack.start_activity(CardWalletActivity, bundle)


def _create_wallet_with_files(dump_dir):
    """Create wallet and manually navigate to file list for dump_dir."""
    act = _create_wallet()
    # Manually set dump_dir and show file list (bypasses type selection)
    act._dump_dir = dump_dir
    act._showFileList()
    return act


class TestCardWalletActivity:
    """CardWalletActivity unit tests."""

    def test_title_dump_files(self):
        """Title must be 'Dump Files'."""
        act = _create_wallet()
        texts = act.getCanvas().get_all_text()
        assert 'Dump Files' in texts

    def test_starts_in_type_list(self):
        """Activity starts in TYPE_LIST mode."""
        act = _create_wallet()
        assert act._mode == 'type_list'

    def test_type_list_has_28_items(self):
        """Type list shows 28 dump type items."""
        act = _create_wallet()
        from activity_main import DUMP_TYPE_ORDER
        assert act._listview is not None
        assert len(DUMP_TYPE_ORDER) == 28

    def test_empty_directory(self, empty_dir):
        """Empty dump directory shows empty state tips."""
        act = _create_wallet()
        act._dump_dir = empty_dir
        act._showFileList()
        assert act._is_dump_list_empty is True

    def test_file_list(self, dump_dir):
        """Non-empty directory shows file list."""
        act = _create_wallet_with_files(dump_dir)
        assert act._is_dump_list_empty is False
        assert len(act._file_list) == 3

    def test_file_list_sorted(self, dump_dir):
        """File list must be sorted."""
        act = _create_wallet_with_files(dump_dir)
        assert act._file_list == sorted(act._file_list)

    def test_file_list_mode_buttons(self, dump_dir):
        """File list mode has M1=Details, M2=Delete."""
        act = _create_wallet_with_files(dump_dir)
        texts = act.getCanvas().get_all_text()
        assert 'Details' in texts
        assert 'Delete' in texts

    def test_delete_confirm_mode(self, dump_dir):
        """M2 in file list shows delete confirmation."""
        act = _create_wallet_with_files(dump_dir)
        act.onKeyEvent(KEY_M2)  # show delete confirm
        assert act._mode == 'delete_confirm'
        assert act._selected_file is not None

    def test_delete_file(self, dump_dir):
        """Confirming delete removes the file."""
        act = _create_wallet_with_files(dump_dir)
        initial_count = len(act._file_list)
        selected_file = act._file_list[0]
        act.onKeyEvent(KEY_M2)  # show delete confirm
        act.onKeyEvent(KEY_M2)  # confirm (Yes)
        assert not os.path.exists(os.path.join(dump_dir, selected_file))

    def test_cancel_delete(self, dump_dir):
        """M1 in delete confirm cancels."""
        act = _create_wallet_with_files(dump_dir)
        initial_count = len(act._file_list)
        act.onKeyEvent(KEY_M2)  # show delete confirm
        act.onKeyEvent(KEY_M1)  # cancel (No)
        assert act._mode == 'file_list'
        assert len(act._file_list) == initial_count

    def test_pwr_back_to_type_list(self, dump_dir):
        """PWR in file list returns to type list."""
        act = _create_wallet_with_files(dump_dir)
        assert act._mode == 'file_list'
        act.onKeyEvent(KEY_PWR)
        assert act._mode == 'type_list'
        assert not act.life.destroyed

    def test_pwr_exits_type_list(self):
        """PWR in type list finishes activity."""
        act = _create_wallet()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_no_dump_dir(self):
        """No dump_dir set means empty state."""
        act = _create_wallet()
        assert act._is_dump_list_empty is True

    def test_format_filename_mf1(self):
        """_formatFilename transforms MF1 filename correctly."""
        from activity_main import CardWalletActivity
        result = CardWalletActivity._formatFilename('M1-1K-4B_DAEFB416_1.bin')
        assert result == '1K-4B-DAEFB416(1)'

    def test_scroll_type_list(self):
        """UP/DOWN navigate the type list."""
        act = _create_wallet()
        assert act._listview.selection() == 0
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 1
        act.onKeyEvent(KEY_UP)
        assert act._listview.selection() == 0
