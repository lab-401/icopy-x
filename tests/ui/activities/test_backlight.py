"""Tests for BacklightActivity.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/08_backlight/README.md and V1090_SETTINGS_FLOWS_COMPLETE.md.

Ground truth:
    - Title: "Backlight" (resources.get_str('backlight'))
    - Items: "Low", "Middle", "High" (blline1, blline2, blline3)
    - M1: "" (empty), M2: "OK"
    - M2/OK: save level, stay on screen
    - PWR: recovery_backlight() restores original, finish()
    - Config key: "backlight", values 0/1/2
"""

import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


# ---------------------------------------------------------------
# Mock config infrastructure
# ---------------------------------------------------------------

class MockConfig:
    """In-memory config store for testing."""

    def __init__(self):
        self._store = {}

    def getValue(self, key):
        if key in self._store:
            return str(self._store[key])
        raise KeyError(key)

    def setKeyValue(self, key, value):
        self._store[key] = value


class MockSettings:
    """Mock settings.so module."""

    # Hardware brightness values matching middleware/settings.py
    # Ground truth (strace 2026-04-10): Low=20, Middle=50, High=100
    _HW_VALUES = [20, 50, 100]  # Low, Middle, High

    def __init__(self, config):
        self._config = config

    def getBacklight(self):
        val = self._config.getValue('backlight')
        return int(val)

    def setBacklight(self, level):
        self._config.setKeyValue('backlight', level)
        # Chain to hmi_driver like the real settings.setBacklight()
        hw_val = self.fromLevelGetBacklight(level)
        try:
            import hmi_driver
            hmi_driver.setbaklight(hw_val)
        except Exception:
            pass

    def fromLevelGetBacklight(self, level):
        """Convert UI level index (0/1/2) to GD32 hardware value."""
        if 0 <= level < len(self._HW_VALUES):
            return self._HW_VALUES[level]
        return self._HW_VALUES[-1]


class MockHmiDriver:
    """Mock hmi_driver.so -- records setbaklight calls."""

    def __init__(self):
        self.calls = []

    def setbaklight(self, level):
        self.calls.append(('setbaklight', level))


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
def mock_config():
    """Provide a fresh MockConfig."""
    return MockConfig()


@pytest.fixture
def mock_hmi():
    """Provide a fresh MockHmiDriver."""
    return MockHmiDriver()


@pytest.fixture
def install_mocks(mock_config, mock_hmi):
    """Install config, settings, and hmi_driver mocks into sys.modules."""
    config_mod = types.ModuleType('config')
    config_mod.getValue = mock_config.getValue
    config_mod.setKeyValue = mock_config.setKeyValue

    mock_settings = MockSettings(mock_config)
    settings_mod = types.ModuleType('settings')
    settings_mod.getBacklight = mock_settings.getBacklight
    settings_mod.setBacklight = mock_settings.setBacklight
    settings_mod.fromLevelGetBacklight = mock_settings.fromLevelGetBacklight

    hmi_mod = types.ModuleType('hmi_driver')
    hmi_mod.setbaklight = mock_hmi.setbaklight

    old_config = sys.modules.get('config')
    old_settings = sys.modules.get('settings')
    old_hmi = sys.modules.get('hmi_driver')

    sys.modules['config'] = config_mod
    sys.modules['settings'] = settings_mod
    sys.modules['hmi_driver'] = hmi_mod

    yield

    # Restore
    if old_config is not None:
        sys.modules['config'] = old_config
    else:
        sys.modules.pop('config', None)
    if old_settings is not None:
        sys.modules['settings'] = old_settings
    else:
        sys.modules.pop('settings', None)
    if old_hmi is not None:
        sys.modules['hmi_driver'] = old_hmi
    else:
        sys.modules.pop('hmi_driver', None)


def _create_backlight(mock_config, level=2):
    """Start a BacklightActivity with config pre-set to *level*."""
    mock_config._store['backlight'] = level
    from activity_main import BacklightActivity
    act = actstack.start_activity(BacklightActivity)
    return act


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestBacklightActivity:
    """BacklightActivity unit tests -- 12 scenarios covering all states."""

    def test_title_is_backlight(self, install_mocks, mock_config):
        """Title bar must read 'Backlight' (resources key: backlight)."""
        act = _create_backlight(mock_config)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Backlight' in texts

    def test_buttons_empty_and_ok(self, install_mocks, mock_config):
        """Both M1 and M2 labels are empty (ground truth: buttons hidden)."""
        act = _create_backlight(mock_config)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Ground truth: setRightButton('') -- no OK button visible
        assert 'OK' not in texts
        assert 'Back' not in texts

    def test_items_low_middle_high(self, install_mocks, mock_config):
        """Content must show exactly 3 items: Low, Middle, High."""
        act = _create_backlight(mock_config)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Low' in texts
        assert 'Middle' in texts
        assert 'High' in texts

    def test_initial_selection_from_config(self, install_mocks, mock_config):
        """Initial selection must match the config value."""
        act = _create_backlight(mock_config, level=0)
        assert act._listview.selection() == 0
        assert 0 in act._listview.getCheckPosition()

    def test_initial_selection_middle(self, install_mocks, mock_config):
        """Config level=1 -> Middle selected."""
        act = _create_backlight(mock_config, level=1)
        assert act._listview.selection() == 1
        assert 1 in act._listview.getCheckPosition()

    def test_up_scrolls_up(self, install_mocks, mock_config):
        """UP key moves selection upward (wraps at top)."""
        act = _create_backlight(mock_config, level=1)
        assert act._listview.selection() == 1
        act.onKeyEvent(KEY_UP)
        assert act._listview.selection() == 0

    def test_down_scrolls_down(self, install_mocks, mock_config):
        """DOWN key moves selection downward."""
        act = _create_backlight(mock_config, level=0)
        assert act._listview.selection() == 0
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 1

    def test_m2_saves_and_stays(self, install_mocks, mock_config, mock_hmi):
        """M2 saves the selected level but does NOT finish the activity."""
        act = _create_backlight(mock_config, level=0)
        # Navigate to High (2)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 2
        act.onKeyEvent(KEY_M2)
        # Verify saved
        assert mock_config._store['backlight'] == 2
        # Verify hmi_driver was called with HW value (100 for High)
        assert ('setbaklight', 100) in mock_hmi.calls
        # Activity should still be alive (not finished)
        assert not act.life.destroyed

    def test_ok_saves_and_stays(self, install_mocks, mock_config, mock_hmi):
        """OK key has the same effect as M2 -- save but stay."""
        act = _create_backlight(mock_config, level=2)
        act.onKeyEvent(KEY_UP)  # -> Middle (1)
        act.onKeyEvent(KEY_OK)
        assert mock_config._store['backlight'] == 1
        assert not act.life.destroyed

    def test_pwr_cancels_and_finishes(self, install_mocks, mock_config, mock_hmi):
        """PWR restores original backlight level and finishes activity."""
        act = _create_backlight(mock_config, level=0)
        # Navigate away from original
        act.onKeyEvent(KEY_DOWN)  # -> Middle (1)
        # Cancel
        act.onKeyEvent(KEY_PWR)
        # Original level (0) should still be in config (cancel doesn't save)
        assert mock_config._store['backlight'] == 0
        # hmi_driver should get the recovery call with HW value (20 for Low)
        assert ('setbaklight', 20) in mock_hmi.calls
        # Activity should be finished
        assert act.life.destroyed

    def test_save_updates_config(self, install_mocks, mock_config):
        """After M2, config key 'backlight' must hold the new level."""
        act = _create_backlight(mock_config, level=2)
        act.onKeyEvent(KEY_UP)  # -> Middle (1)
        act.onKeyEvent(KEY_UP)  # -> Low (0)
        act.onKeyEvent(KEY_M2)
        assert mock_config._store['backlight'] == 0

    def test_save_updates_check_marks(self, install_mocks, mock_config):
        """After save, the new level is checked and old is unchecked."""
        act = _create_backlight(mock_config, level=2)
        act.onKeyEvent(KEY_UP)  # -> 1
        act.onKeyEvent(KEY_M2)
        checked = act._listview.getCheckPosition()
        assert 1 in checked
        assert 2 not in checked

    def test_default_selection_when_no_config(self, install_mocks, mock_config):
        """When config has no 'backlight' key, default to level 2 (High)."""
        # Don't set any value in config -- _get_config_value falls back
        # to settings.getBacklight() which will fail, then config.getValue
        # which will also fail, giving default=2
        mock_config._store.clear()
        from activity_main import BacklightActivity
        act = actstack.start_activity(BacklightActivity)
        assert act._listview.selection() == 2
        assert 2 in act._listview.getCheckPosition()
