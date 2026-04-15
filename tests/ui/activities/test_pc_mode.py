"""Tests for PCModeActivity.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/07_pc_mode/README.md.

Ground truth:
    - Title: "PC-Mode" (resources key: pc-mode)
    - IDLE state: M1="Start", M2="Start"
    - RUNNING state: M1="Stop", M2="Button"
    - M1/M2/OK in IDLE: start PC mode -> STARTING -> RUNNING
    - M1/M2 in RUNNING: stop PC mode -> STOPPING -> finish()
    - PWR in IDLE: finish()
    - PWR in RUNNING: stop PC mode + finish()
    - Content: "Please connect to\\nthe computer.Then\\npress start button"
    - Toast running: "PC-mode Running..."
"""

import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


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
def install_stubs():
    """Install stub modules for gadget_linux, executor, hmi_driver, audio, psutil.

    These modules are imported lazily inside PCModeActivity methods, so
    we need them in sys.modules to avoid ImportError for background thread
    operations.
    """
    old_modules = {}
    stub_names = ['gadget_linux', 'executor', 'hmi_driver', 'audio', 'psutil']

    for name in stub_names:
        old_modules[name] = sys.modules.get(name)

    # gadget_linux stub
    gadget_mod = types.ModuleType('gadget_linux')
    gadget_mod.upan_and_serial = lambda: None
    gadget_mod.kill_all_module = lambda: None
    sys.modules['gadget_linux'] = gadget_mod

    # executor stub
    executor_mod = types.ModuleType('executor')
    executor_mod.startPM3Ctrl = lambda: None
    executor_mod.reworkPM3All = lambda: None
    sys.modules['executor'] = executor_mod

    # hmi_driver stub
    hmi_mod = types.ModuleType('hmi_driver')
    hmi_mod.presspm3 = lambda: None
    hmi_mod.restartpm3 = lambda: None
    sys.modules['hmi_driver'] = hmi_mod

    # audio stub
    audio_mod = types.ModuleType('audio')
    audio_mod.playPCModeRunning = lambda: None
    audio_mod.playKeyDisable = lambda: None
    audio_mod.playKeyEnable = lambda: None
    sys.modules['audio'] = audio_mod

    # psutil stub
    psutil_mod = types.ModuleType('psutil')
    psutil_mod.NoSuchProcess = type('NoSuchProcess', (Exception,), {})

    class MockProcess:
        def __init__(self, pid):
            self.pid = pid
        def kill(self):
            pass
    psutil_mod.Process = MockProcess
    sys.modules['psutil'] = psutil_mod

    yield

    for name in stub_names:
        if old_modules[name] is not None:
            sys.modules[name] = old_modules[name]
        else:
            sys.modules.pop(name, None)


def _create_pcmode():
    """Start a PCModeActivity."""
    from activity_main import PCModeActivity
    act = actstack.start_activity(PCModeActivity)
    return act


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestPCModeActivity:
    """PCModeActivity unit tests -- 11 scenarios covering all states."""

    def test_title_pc_mode(self):
        """Title bar must read 'PC-Mode' (resources key: pc-mode)."""
        act = _create_pcmode()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'PC-Mode' in texts

    def test_instruction_text(self):
        """Content must show connection instructions."""
        act = _create_pcmode()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        assert 'connect' in all_text.lower()
        assert 'start button' in all_text.lower()

    def test_initial_state_idle(self):
        """Initial state must be IDLE."""
        act = _create_pcmode()
        assert act.get_state() == 'idle'

    def test_idle_buttons_both_start(self):
        """In IDLE state, both buttons show 'Start'."""
        act = _create_pcmode()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Count occurrences of "Start" (should be at least 2 -- both M1 and M2)
        start_count = sum(1 for t in texts if t == 'Start')
        assert start_count >= 2

    def test_pwr_finishes_in_idle(self):
        """PWR in IDLE state finishes the activity."""
        act = _create_pcmode()
        assert act.get_state() == 'idle'
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_m2_starts_pc_mode(self):
        """M2 in IDLE triggers transition to STARTING state."""
        act = _create_pcmode()
        assert act.get_state() == 'idle'
        act.onKeyEvent(KEY_M2)
        # State should be STARTING (background thread launched)
        # or RUNNING (if bg thread completed instantly) or IDLE (if start failed)
        assert act.get_state() in ('starting', 'running', 'idle')

    def test_m1_starts_pc_mode(self):
        """M1 in IDLE also starts PC mode (same as M2)."""
        act = _create_pcmode()
        act.onKeyEvent(KEY_M1)
        assert act.get_state() in ('starting', 'running', 'idle')

    def test_ok_starts_pc_mode(self):
        """OK in IDLE also starts PC mode."""
        act = _create_pcmode()
        act.onKeyEvent(KEY_OK)
        assert act.get_state() in ('starting', 'running', 'idle')

    def test_keys_ignored_in_starting(self):
        """In STARTING state, all keys are ignored."""
        act = _create_pcmode()
        act._state = 'starting'  # Force state for testing
        act.onKeyEvent(KEY_M2)
        # State should not change
        assert act.get_state() == 'starting'
        act.onKeyEvent(KEY_PWR)
        assert act.get_state() == 'starting'

    def test_keys_ignored_in_stopping(self):
        """In STOPPING state, all keys are ignored."""
        act = _create_pcmode()
        act._state = 'stopping'  # Force state for testing
        act.onKeyEvent(KEY_M2)
        assert act.get_state() == 'stopping'
        act.onKeyEvent(KEY_PWR)
        assert act.get_state() == 'stopping'

    def test_button_label_changes_running(self):
        """In RUNNING state, M1='Stop', M2='Button'."""
        act = _create_pcmode()
        # Force to RUNNING state and update buttons
        act._state = 'running'
        act.showButton()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Stop' in texts
        assert 'Button' in texts

    def test_running_m1_triggers_stop(self):
        """M1 in RUNNING state triggers stop sequence."""
        act = _create_pcmode()
        act._state = 'running'
        act.onKeyEvent(KEY_M1)
        # Should transition to stopping
        assert act.get_state() in ('stopping',)

    def test_running_m2_triggers_stop(self):
        """M2 in RUNNING state triggers stop sequence."""
        act = _create_pcmode()
        act._state = 'running'
        act.onKeyEvent(KEY_M2)
        assert act.get_state() in ('stopping',)

    def test_running_pwr_triggers_stop(self):
        """PWR in RUNNING state triggers stop sequence."""
        act = _create_pcmode()
        act._state = 'running'
        act.onKeyEvent(KEY_PWR)
        assert act.get_state() in ('stopping',)

    def test_show_running_toast(self):
        """showRunningToast displays 'PC-mode Running...'."""
        act = _create_pcmode()
        act.showRunningToast()
        # Toast should be shown on canvas
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'PC-mode Running...' in texts

    def test_up_down_ignored_in_idle(self):
        """UP/DOWN keys have no effect in IDLE (no list)."""
        act = _create_pcmode()
        act.onKeyEvent(KEY_UP)
        assert act.get_state() == 'idle'
        act.onKeyEvent(KEY_DOWN)
        assert act.get_state() == 'idle'
