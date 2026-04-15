"""Tests for SleepModeActivity and WarningDiskFullActivity.

SleepModeActivity tests:
  - Backlight dimmed to 0 on create
  - Any key wakes (finishes activity)
  - Backlight restored on wake
  - No title bar, no buttons -- pure black screen

WarningDiskFullActivity tests:
  - Title is "Warning"
  - Buttons are "Ignore" (Cancel) / "Clear"
  - M1/PWR ignores (finishes)
  - M2/OK clears files and finishes
"""

import sys
import types
import pytest
from unittest import mock

from tests.ui.conftest import MockCanvas
import actstack
from _constants import (
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
    TAG_TITLE, TAG_BTN_LEFT, TAG_BTN_RIGHT,
)


# ── helpers ──────────────────────────────────────────────────────────

def _setup():
    """Reset actstack and wire MockCanvas factory."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()


def _teardown():
    actstack._reset()


def _push_root():
    """Push a dummy root activity so finish_activity has somewhere to go."""
    from actbase import BaseActivity
    return actstack.start_activity(BaseActivity)


# ═══════════════════════════════════════════════════════════════════════
# SleepModeActivity
# ═══════════════════════════════════════════════════════════════════════

class TestSleepDimsBacklight:
    def teardown_method(self):
        _teardown()

    def test_sleep_dims_backlight(self):
        """SleepModeActivity sets backlight to 0 on create."""
        _setup()
        _push_root()

        backlight_calls = []

        # Mock hmi_driver.setbaklight (both module name variants)
        mock_hmi = types.ModuleType('hmi_driver')
        mock_hmi.setbaklight = lambda level: backlight_calls.append(level)

        # Mock settings (for _read_backlight_level)
        mock_settings = types.ModuleType('settings')
        mock_settings.getBacklight = lambda: 3
        mock_settings.fromLevelGetBacklight = lambda lvl: {0: 20, 1: 50, 2: 100}.get(lvl, 100)

        with mock.patch.dict(sys.modules, {
            'settings': mock_settings,
            'hmi_driver': mock_hmi,
            'lib.hmi_driver': mock_hmi,
        }):
            from activity_main import SleepModeActivity
            act = actstack.start_activity(SleepModeActivity)

        # setbaklight(0) should have been called
        assert 0 in backlight_calls, f"Expected backlight set to 0, got calls: {backlight_calls}"


class TestSleepAnyKeyWakes:
    def teardown_method(self):
        _teardown()

    def test_sleep_any_key_wakes(self):
        """Any key press finishes the sleep activity."""
        _setup()
        _push_root()

        backlight_calls = []
        mock_hmi = types.ModuleType('hmi_driver')
        mock_hmi.setbaklight = lambda level: backlight_calls.append(level)
        mock_settings = types.ModuleType('settings')
        mock_settings.getBacklight = lambda: 2
        mock_settings.fromLevelGetBacklight = lambda lvl: {0: 20, 1: 50, 2: 100}.get(lvl, 100)

        with mock.patch.dict(sys.modules, {
            'settings': mock_settings,
            'hmi_driver': mock_hmi,
            'lib.hmi_driver': mock_hmi,
        }):
            from activity_main import SleepModeActivity
            act = actstack.start_activity(SleepModeActivity)
            stack_before = actstack.get_stack_size()

            # Press any key -- should wake and finish
            act.onKeyEvent(KEY_OK)

        assert actstack.get_stack_size() == stack_before - 1

    def test_sleep_wakes_on_various_keys(self):
        """Multiple key types all wake from sleep."""
        for key in [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_M1, KEY_M2, KEY_PWR]:
            _setup()
            _push_root()

            mock_hmi = types.ModuleType('hmi_driver')
            mock_hmi.setbaklight = lambda level: None
            mock_settings = types.ModuleType('settings')
            mock_settings.getBacklight = lambda: 3
            mock_settings.fromLevelGetBacklight = lambda lvl: {0: 20, 1: 50, 2: 100}.get(lvl, 100)

            with mock.patch.dict(sys.modules, {
                'settings': mock_settings,
                'hmi_driver': mock_hmi,
                'lib.hmi_driver': mock_hmi,
            }):
                from activity_main import SleepModeActivity
                act = actstack.start_activity(SleepModeActivity)
                stack_before = actstack.get_stack_size()
                act.onKeyEvent(key)

            assert actstack.get_stack_size() == stack_before - 1, \
                f"Key {key} should wake from sleep"


class TestSleepRestoresBacklight:
    def teardown_method(self):
        _teardown()

    def test_sleep_restores_backlight(self):
        """Backlight is restored to previous level when waking."""
        _setup()
        _push_root()

        backlight_calls = []
        mock_hmi = types.ModuleType('hmi_driver')
        mock_hmi.setbaklight = lambda level: backlight_calls.append(level)
        mock_settings = types.ModuleType('settings')
        mock_settings.getBacklight = lambda: 2  # previous level = 2
        mock_settings.fromLevelGetBacklight = lambda lvl: {0: 20, 1: 50, 2: 100}.get(lvl, 100)

        with mock.patch.dict(sys.modules, {
            'settings': mock_settings,
            'hmi_driver': mock_hmi,
            'lib.hmi_driver': mock_hmi,
        }):
            from activity_main import SleepModeActivity
            act = actstack.start_activity(SleepModeActivity)
            backlight_calls.clear()  # clear the initial setbaklight(0) call

            act.onKeyEvent(KEY_OK)

        # Should have called setbaklight(100) to restore (UI level 2 → HW 100)
        assert 100 in backlight_calls, f"Expected backlight restored to HW 100, got: {backlight_calls}"


class TestSleepNoTitleNoButtons:
    def teardown_method(self):
        _teardown()

    def test_sleep_no_title_no_buttons(self):
        """Sleep screen has no title bar and no button labels."""
        _setup()
        _push_root()

        mock_hmi = types.ModuleType('hmi_driver')
        mock_hmi.setbaklight = lambda level: None
        mock_settings = types.ModuleType('settings')
        mock_settings.getBacklight = lambda: 3
        mock_settings.fromLevelGetBacklight = lambda lvl: {0: 20, 1: 50, 2: 100}.get(lvl, 100)

        with mock.patch.dict(sys.modules, {
            'settings': mock_settings,
            'hmi_driver': mock_hmi,
            'lib.hmi_driver': mock_hmi,
        }):
            from activity_main import SleepModeActivity
            act = actstack.start_activity(SleepModeActivity)

        canvas = act.getCanvas()

        # No title bar items
        title_items = canvas.find_withtag(TAG_TITLE)
        assert len(title_items) == 0, "Sleep mode should have no title bar"

        # No button items
        btn_left = canvas.find_withtag(TAG_BTN_LEFT)
        btn_right = canvas.find_withtag(TAG_BTN_RIGHT)
        assert len(btn_left) == 0, "Sleep mode should have no left button"
        assert len(btn_right) == 0, "Sleep mode should have no right button"

        # Should have a black rectangle covering screen
        # Source uses COLOR_BLACK = '#000000', not the string 'black'
        rects = canvas.get_items_by_type('rectangle')
        has_black = any(
            item['options'].get('fill') in ('black', '#000000')
            for _, item in rects
        )
        assert has_black, "Sleep mode should have a black background rectangle"


# ═══════════════════════════════════════════════════════════════════════
# WarningDiskFullActivity
# ═══════════════════════════════════════════════════════════════════════

class TestDiskFullTitle:
    def teardown_method(self):
        _teardown()

    def test_diskfull_title_warning(self):
        """WarningDiskFullActivity title is 'Warning'."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Warning' in t for t in texts), f"Expected 'Warning' title, got: {texts}"


class TestDiskFullButtons:
    def teardown_method(self):
        _teardown()

    def test_diskfull_buttons(self):
        """WarningDiskFullActivity has Cancel/Ignore left, Clear right."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        # Right button should be "Clear"
        btn_right = canvas.find_withtag(TAG_BTN_RIGHT)
        assert len(btn_right) > 0, "Should have right button"
        right_text = canvas.itemcget(btn_right[0], 'text')
        assert 'Clear' in right_text, f"Expected 'Clear' in right button, got: {right_text}"

        # Left button should be Cancel or Ignore
        btn_left = canvas.find_withtag(TAG_BTN_LEFT)
        assert len(btn_left) > 0, "Should have left button"
        left_text = canvas.itemcget(btn_left[0], 'text')
        assert left_text in ('Cancel', 'Ignore'), \
            f"Expected 'Cancel' or 'Ignore' in left button, got: {left_text}"


class TestDiskFullM1Ignores:
    def teardown_method(self):
        _teardown()

    def test_diskfull_m1_ignores(self):
        """M1 finishes the activity (ignores warning)."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        stack_before = actstack.get_stack_size()

        act.onKeyEvent(KEY_M1)
        assert actstack.get_stack_size() == stack_before - 1

    def test_diskfull_pwr_ignores(self):
        """PWR also finishes the activity."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        stack_before = actstack.get_stack_size()

        act.onKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() == stack_before - 1


class TestDiskFullM2Clears:
    def teardown_method(self):
        _teardown()

    def test_diskfull_m2_clears(self):
        """M2 triggers file clearing and finishes."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)

        # Mock the filesystem operations
        with mock.patch('os.path.isdir', return_value=False):
            stack_before = actstack.get_stack_size()
            act.onKeyEvent(KEY_M2)

        assert actstack.get_stack_size() == stack_before - 1

    def test_diskfull_ok_clears(self):
        """OK also triggers file clearing and finishes."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)

        with mock.patch('os.path.isdir', return_value=False):
            stack_before = actstack.get_stack_size()
            act.onKeyEvent(KEY_OK)

        assert actstack.get_stack_size() == stack_before - 1

    def test_diskfull_clear_calls_rmtree(self):
        """Clearing actually calls shutil.rmtree on existing dump directories."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)

        rmtree_calls = []

        def mock_isdir(path):
            return 'dump' in path

        def mock_rmtree(path):
            rmtree_calls.append(path)

        with mock.patch('os.path.isdir', side_effect=mock_isdir), \
             mock.patch('shutil.rmtree', side_effect=mock_rmtree):
            act.onKeyEvent(KEY_M2)

        assert len(rmtree_calls) > 0, "Should have called rmtree at least once"
        assert any('dump' in p for p in rmtree_calls), \
            f"Should have cleared dump dirs, got: {rmtree_calls}"


class TestDiskFullWarningMessage:
    def teardown_method(self):
        _teardown()

    def test_diskfull_shows_warning_text(self):
        """Warning message text is displayed on creation."""
        _setup()
        _push_root()

        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        # The disk_full_tips resource contains "disk space is full" or similar
        assert 'disk' in all_text.lower() or 'full' in all_text.lower() or 'backup' in all_text.lower(), \
            f"Expected disk full warning text, got: {all_text}"
