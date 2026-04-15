"""Tests for VolumeActivity.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/10_volume/README.md and V1090_SETTINGS_FLOWS_COMPLETE.md.

Ground truth:
    - Title: "Volume" (resources.get_str('volume'))
    - Items: "Off", "Low", "Middle", "High" (valueline1..4)
    - M1: "" (empty), M2: "OK"
    - M2/OK: saveSetting() -- persist + audio preview, stay on screen
    - PWR: finish() -- exit WITHOUT reverting
    - Config key: "volume", values 0/1/2/3
"""

import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


# ---------------------------------------------------------------
# Mock infrastructure
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

    def __init__(self, config):
        self._config = config

    def getVolume(self):
        val = self._config.getValue('volume')
        return int(val)

    def setVolume(self, level):
        self._config.setKeyValue('volume', level)


class MockAudio:
    """Mock audio.so -- records all method calls."""

    def __init__(self):
        self.calls = []

    def setVolume(self, v):
        self.calls.append(('setVolume', v))

    def playVolumeExam(self):
        self.calls.append(('playVolumeExam',))

    def setKeyAudioEnable(self, enable):
        self.calls.append(('setKeyAudioEnable', enable))


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
    return MockConfig()


@pytest.fixture
def mock_audio():
    return MockAudio()


@pytest.fixture
def install_mocks(mock_config, mock_audio):
    """Install config, settings, and audio mocks into sys.modules."""
    config_mod = types.ModuleType('config')
    config_mod.getValue = mock_config.getValue
    config_mod.setKeyValue = mock_config.setKeyValue

    mock_settings = MockSettings(mock_config)
    settings_mod = types.ModuleType('settings')
    settings_mod.getVolume = mock_settings.getVolume
    settings_mod.setVolume = mock_settings.setVolume

    audio_mod = types.ModuleType('audio')
    audio_mod.setVolume = mock_audio.setVolume
    audio_mod.playVolumeExam = mock_audio.playVolumeExam
    audio_mod.setKeyAudioEnable = mock_audio.setKeyAudioEnable

    old_config = sys.modules.get('config')
    old_settings = sys.modules.get('settings')
    old_audio = sys.modules.get('audio')

    sys.modules['config'] = config_mod
    sys.modules['settings'] = settings_mod
    sys.modules['audio'] = audio_mod

    yield

    if old_config is not None:
        sys.modules['config'] = old_config
    else:
        sys.modules.pop('config', None)
    if old_settings is not None:
        sys.modules['settings'] = old_settings
    else:
        sys.modules.pop('settings', None)
    if old_audio is not None:
        sys.modules['audio'] = old_audio
    else:
        sys.modules.pop('audio', None)


def _create_volume(mock_config, level=2):
    """Start a VolumeActivity with config pre-set to *level*."""
    mock_config._store['volume'] = level
    from activity_main import VolumeActivity
    act = actstack.start_activity(VolumeActivity)
    return act


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestVolumeActivity:
    """VolumeActivity unit tests -- 12 scenarios covering all states."""

    def test_title_is_volume(self, install_mocks, mock_config):
        """Title bar must read 'Volume' (resources key: volume)."""
        act = _create_volume(mock_config)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Volume' in texts

    def test_buttons_empty_and_ok(self, install_mocks, mock_config):
        """Both M1 and M2 labels are empty (ground truth: buttons hidden)."""
        act = _create_volume(mock_config)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Ground truth: setRightButton('') -- no OK button visible
        assert 'OK' not in texts
        assert 'Back' not in texts

    def test_items_off_low_middle_high(self, install_mocks, mock_config):
        """Content must show exactly 4 items: Off, Low, Middle, High."""
        act = _create_volume(mock_config)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Off' in texts
        assert 'Low' in texts
        assert 'Middle' in texts
        assert 'High' in texts

    def test_initial_selection_from_config(self, install_mocks, mock_config):
        """Initial selection must match the config value."""
        act = _create_volume(mock_config, level=0)
        assert act._listview.selection() == 0
        assert 0 in act._listview.getCheckPosition()

    def test_initial_selection_high(self, install_mocks, mock_config):
        """Config level=3 -> High selected."""
        act = _create_volume(mock_config, level=3)
        assert act._listview.selection() == 3
        assert 3 in act._listview.getCheckPosition()

    def test_up_scrolls_up(self, install_mocks, mock_config):
        """UP key moves selection upward."""
        act = _create_volume(mock_config, level=2)
        assert act._listview.selection() == 2
        act.onKeyEvent(KEY_UP)
        assert act._listview.selection() == 1

    def test_down_scrolls_down(self, install_mocks, mock_config):
        """DOWN key moves selection downward."""
        act = _create_volume(mock_config, level=0)
        assert act._listview.selection() == 0
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 1

    def test_m2_saves_and_stays(self, install_mocks, mock_config, mock_audio):
        """M2 saves the selected level but does NOT finish the activity."""
        act = _create_volume(mock_config, level=0)
        # Navigate to High (3)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 3
        act.onKeyEvent(KEY_M2)
        # Verify saved
        assert mock_config._store['volume'] == 3
        # Verify audio calls
        assert ('setVolume', 3) in mock_audio.calls
        assert ('playVolumeExam',) in mock_audio.calls
        assert ('setKeyAudioEnable', True) in mock_audio.calls
        # Activity should still be alive
        assert not act.life.destroyed

    def test_ok_saves_and_stays(self, install_mocks, mock_config, mock_audio):
        """OK key has the same effect as M2 -- save but stay."""
        act = _create_volume(mock_config, level=3)
        act.onKeyEvent(KEY_UP)  # -> Middle (2)
        act.onKeyEvent(KEY_OK)
        assert mock_config._store['volume'] == 2
        assert not act.life.destroyed

    def test_pwr_exits_without_reverting(self, install_mocks, mock_config):
        """PWR finishes without restoring the original volume.

        Key difference from BacklightActivity: no recovery on cancel.
        """
        act = _create_volume(mock_config, level=1)
        # Navigate away
        act.onKeyEvent(KEY_DOWN)  # -> Middle (2)
        # PWR exits
        act.onKeyEvent(KEY_PWR)
        # Config should still have the ORIGINAL value (1) because
        # PWR does NOT save -- it just finishes
        assert mock_config._store['volume'] == 1
        assert act.life.destroyed

    def test_save_updates_config(self, install_mocks, mock_config):
        """After M2, config key 'volume' must hold the new level."""
        act = _create_volume(mock_config, level=3)
        act.onKeyEvent(KEY_UP)  # -> 2
        act.onKeyEvent(KEY_UP)  # -> 1
        act.onKeyEvent(KEY_UP)  # -> 0
        act.onKeyEvent(KEY_M2)
        assert mock_config._store['volume'] == 0

    def test_save_off_disables_key_audio(self, install_mocks, mock_config, mock_audio):
        """Saving level 0 (Off) calls setKeyAudioEnable(false)."""
        act = _create_volume(mock_config, level=1)
        act.onKeyEvent(KEY_UP)  # -> Off (0)
        act.onKeyEvent(KEY_M2)
        assert ('setKeyAudioEnable', False) in mock_audio.calls

    def test_default_selection_when_no_config(self, install_mocks, mock_config):
        """When config has no 'volume' key, default to level 2 (Middle)."""
        mock_config._store.clear()
        from activity_main import VolumeActivity
        act = actstack.start_activity(VolumeActivity)
        assert act._listview.selection() == 2
        assert 2 in act._listview.getCheckPosition()
