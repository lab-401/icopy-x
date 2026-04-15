"""Tests for LUAScriptCMDActivity.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/14_lua_script/README.md and V1090_CONSOLE_RECONSTRUCTION.md.

Ground truth:
    - Title: "LUA Script" (paginated as "LUA Script X/Y")
    - Content: ListView of .lua file names from /mnt/upan/luascripts/
    - M1: "" (empty), M2: "OK"
    - UP/DOWN: scroll, LEFT/RIGHT: page, M2/OK: run script, PWR: exit
    - On run: launches ConsolePrinterActivity with "script run <name>"
    - No files: shows "No scripts found" toast
"""

import os
import sys
import types
import tempfile
import shutil
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import (
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture(autouse=True)
def _setup_actstack():
    """Reset actstack and install MockCanvas factory for each test."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


@pytest.fixture
def script_dir():
    """Create a temporary directory with .lua script files for testing."""
    tmpdir = tempfile.mkdtemp(prefix='lua_test_')
    # Create some .lua files
    script_names = [
        'hf_read.lua',
        'dumptoemul.lua',
        'legic.lua',
        'mifareplus.lua',
        'test_t55x7_bi.lua',
        'mfu_magic.lua',
        'calypso.lua',
        'cmdline.lua',
        'didump.lua',
        'formatMifare.lua',
        'hf_bruteforce.lua',
    ]
    for name in script_names:
        with open(os.path.join(tmpdir, name), 'w') as f:
            f.write('-- lua script\n')
    # Also create a non-.lua file that should be filtered out
    with open(os.path.join(tmpdir, 'README.txt'), 'w') as f:
        f.write('not a script\n')
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def empty_script_dir():
    """Create an empty temporary directory (no .lua files)."""
    tmpdir = tempfile.mkdtemp(prefix='lua_empty_')
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _create_lua_activity(script_dir_path):
    """Start a LUAScriptCMDActivity with the given script directory."""
    from activity_main import LUAScriptCMDActivity
    # Override the script directory
    LUAScriptCMDActivity.SCRIPT_DIR = script_dir_path
    act = actstack.start_activity(LUAScriptCMDActivity)
    return act


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestLUAScriptCMDActivity:
    """LUAScriptCMDActivity unit tests -- 12 scenarios."""

    def test_title_is_lua_script(self, script_dir):
        """Title bar must read 'LUA Script' (resources key: lua_script)."""
        act = _create_lua_activity(script_dir)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('LUA Script' in t for t in texts)

    def test_file_list_from_directory(self, script_dir):
        """Activity should list .lua files from the script directory."""
        act = _create_lua_activity(script_dir)
        scripts = act.get_scripts()
        assert len(scripts) == 11  # 11 .lua files created
        # Files should be sorted alphabetically
        assert scripts == sorted(scripts)

    def test_lua_extension_stripped(self, script_dir):
        """Script names should have .lua extension removed."""
        act = _create_lua_activity(script_dir)
        scripts = act.get_scripts()
        for name in scripts:
            assert not name.endswith('.lua')
        assert 'hf_read' in scripts
        assert 'legic' in scripts

    def test_non_lua_files_filtered(self, script_dir):
        """Non-.lua files (like README.txt) should be filtered out."""
        act = _create_lua_activity(script_dir)
        scripts = act.get_scripts()
        assert 'README' not in scripts
        assert 'README.txt' not in scripts

    def test_no_files_shows_toast(self, empty_script_dir):
        """When no .lua files exist, a toast message should appear."""
        act = _create_lua_activity(empty_script_dir)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('No scripts found' in t for t in texts)

    def test_no_files_listview_is_none(self, empty_script_dir):
        """When no files, the internal listview should be None."""
        act = _create_lua_activity(empty_script_dir)
        assert act.get_listview() is None

    def test_ok_runs_selected_script(self, script_dir):
        """OK/M2 should launch ConsolePrinterActivity with the selected script."""
        act = _create_lua_activity(script_dir)
        # Get the first script name
        scripts = act.get_scripts()
        first_script = scripts[0]

        # Press OK to run the selected script
        act.onKeyEvent(KEY_OK)

        # Check that a ConsolePrinterActivity was pushed onto the stack
        assert len(actstack._ACTIVITY_STACK) >= 2
        from activity_main import ConsolePrinterActivity
        top_act = actstack._ACTIVITY_STACK[-1]
        assert isinstance(top_act, ConsolePrinterActivity)

    def test_launches_console_with_correct_cmd(self, script_dir):
        """ConsolePrinterActivity should receive 'script run <name>' in bundle."""
        act = _create_lua_activity(script_dir)
        scripts = act.get_scripts()
        first_script = scripts[0]

        act.onKeyEvent(KEY_M2)

        top_act = actstack._ACTIVITY_STACK[-1]
        # ConsolePrinterActivity stores the bundle (which contains 'cmd')
        assert hasattr(top_act, '_bundle')
        assert top_act._bundle['cmd'] == 'script run %s' % first_script

    def test_m1_does_nothing(self, script_dir):
        """M1 has no label and no action (back is via PWR)."""
        act = _create_lua_activity(script_dir)
        # M1 should not finish or crash
        act.onKeyEvent(KEY_M1)
        # Activity should still be alive (M1 not mapped to finish in this activity)
        # PWR exits, not M1
        # Check activity is still the top
        assert actstack._ACTIVITY_STACK[-1] is act

    def test_pwr_exits(self, script_dir):
        """PWR finishes the activity."""
        act = _create_lua_activity(script_dir)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_up_down_scroll(self, script_dir):
        """UP/DOWN keys scroll through the file list."""
        act = _create_lua_activity(script_dir)
        lv = act.get_listview()
        assert lv is not None
        assert lv.selection() == 0

        act.onKeyEvent(KEY_DOWN)
        assert lv.selection() == 1

        act.onKeyEvent(KEY_DOWN)
        assert lv.selection() == 2

        act.onKeyEvent(KEY_UP)
        assert lv.selection() == 1

    def test_title_pagination(self, script_dir):
        """Title should show pagination when multiple pages exist."""
        act = _create_lua_activity(script_dir)
        # 11 scripts, 5 per page = 3 pages
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # setTitle splits "LUA Script 1/3" into base title + page indicator
        assert any('LUA Script' in t for t in texts)
        assert any('1/3' in t for t in texts)

    def test_right_changes_page(self, script_dir):
        """RIGHT key advances to the next page."""
        act = _create_lua_activity(script_dir)
        lv = act.get_listview()
        assert lv.getPagePosition() == 0

        act.onKeyEvent(KEY_RIGHT)
        assert lv.getPagePosition() == 1

    def test_left_changes_page_back(self, script_dir):
        """LEFT key goes to the previous page."""
        act = _create_lua_activity(script_dir)
        lv = act.get_listview()

        # Go to page 1 first
        act.onKeyEvent(KEY_RIGHT)
        assert lv.getPagePosition() == 1

        # Then go back
        act.onKeyEvent(KEY_LEFT)
        assert lv.getPagePosition() == 0

    def test_left_at_first_page_stays(self, script_dir):
        """LEFT at page 0 stays at page 0 (no wrap)."""
        act = _create_lua_activity(script_dir)
        lv = act.get_listview()
        assert lv.getPagePosition() == 0

        act.onKeyEvent(KEY_LEFT)
        assert lv.getPagePosition() == 0

    def test_buttons_empty_and_ok(self, script_dir):
        """Both M1 and M2 are empty (ground truth: buttons hidden)."""
        act = _create_lua_activity(script_dir)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Ground truth: setRightButton('') -- no OK button visible
        assert 'OK' not in texts
