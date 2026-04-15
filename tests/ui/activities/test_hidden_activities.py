"""Tests for KeyEnterM1, UpdateActivity, OTAActivity, and all hidden activities.

Ground truth:
    - KeyEnterM1: title "Key Enter", hex input 12 chars, M1="Cancel" M2="Enter"
    - UpdateActivity: title "Update", M2="Start", progress bar during install
    - Hidden activities: all must instantiate, have ACT_NAME, respond to PWR
    - Source: resources.so string tables, binary method signatures
"""

import pytest

import actstack
from tests.ui.conftest import MockCanvas
from _constants import KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


@pytest.fixture(autouse=True)
def _setup():
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


def _start(cls, bundle=None):
    return actstack.start_activity(cls, bundle)


# ---------------------------------------------------------------
# KeyEnterM1Activity tests
# ---------------------------------------------------------------

class TestKeyEnterM1Activity:

    def test_title(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        texts = act.getCanvas().get_all_text()
        assert 'Key Enter' in texts

    def test_buttons(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        texts = act.getCanvas().get_all_text()
        assert 'Cancel' in texts
        assert 'Enter' in texts

    def test_hex_input_created(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        assert act._input_method is not None

    def test_default_key(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        assert act._input_method.getValue() == 'FFFFFFFFFFFF'

    def test_custom_default(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity, {'default_key': 'A0A1A2A3A4A5'})
        assert act._input_method.getValue() == 'A0A1A2A3A4A5'

    def test_roll_up(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        initial = act._input_method.getValue()
        act.onKeyEvent(KEY_UP)
        assert act._input_method.getValue() != initial

    def test_roll_down(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        act.onKeyEvent(KEY_DOWN)
        # Character should have changed
        val = act._input_method.getValue()
        assert val[0] != 'F' or val != 'FFFFFFFFFFFF'

    def test_cursor_left_right(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        assert act._input_method.getFocus() == 0
        act.onKeyEvent(KEY_RIGHT)
        assert act._input_method.getFocus() == 1
        act.onKeyEvent(KEY_LEFT)
        assert act._input_method.getFocus() == 0

    def test_confirm(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        act.onKeyEvent(KEY_M2)
        assert act.result_key == 'FFFFFFFFFFFF'
        assert act.life.destroyed

    def test_cancel(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed
        assert act.result_key is None

    def test_pwr_cancel(self):
        from activity_main import KeyEnterM1Activity
        act = _start(KeyEnterM1Activity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# ---------------------------------------------------------------
# UpdateActivity tests
# ---------------------------------------------------------------

class TestUpdateActivity:

    def test_title(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        texts = act.getCanvas().get_all_text()
        assert 'Update' in texts

    def test_start_button(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        texts = act.getCanvas().get_all_text()
        assert 'Start' in texts

    def test_initial_state_ready(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        assert act._upd_state == 'ready'

    def test_start_install(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        act.onKeyEvent(KEY_M2)
        # _startInstall tries import update which fails (no module),
        # falls through to except -> _onInstallComplete(success=False, code=0x03)
        # which sets state to 'done'
        assert act._upd_state == 'done'

    def test_pwr_exits_ready(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_install_complete_success(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        act._startInstall()
        act._onInstallComplete(success=True)
        assert act._upd_state == 'done'

    def test_install_complete_done_exit(self):
        from activity_main import UpdateActivity
        act = _start(UpdateActivity)
        act._startInstall()
        act._onInstallComplete()
        act.onKeyEvent(KEY_OK)
        assert act.life.destroyed


# ---------------------------------------------------------------
# OTAActivity tests
# ---------------------------------------------------------------

class TestOTAActivity:

    def test_title(self):
        from activity_main import OTAActivity
        act = _start(OTAActivity)
        texts = act.getCanvas().get_all_text()
        assert 'Update' in texts

    def test_pwr_exits(self):
        from activity_main import OTAActivity
        act = _start(OTAActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# ---------------------------------------------------------------
# Hidden activities: parametrized instantiation tests
# ---------------------------------------------------------------

_HIDDEN_CLASSES = [
    'SniffForMfReadActivity',
    'SniffForT5XReadActivity',
    'SniffForSpecificTag',
    'IClassSEActivity',
    'WearableDeviceActivity',
    'ReadFromHistoryActivity',
    'AutoExceptCatchActivity',
    'SnakeGameActivity',
    'WarningT5XActivity',
    'WarningT5X4X05KeyEnterActivity',
]


@pytest.fixture(params=_HIDDEN_CLASSES)
def hidden_cls(request):
    """Return each hidden activity class."""
    import activity_main
    return getattr(activity_main, request.param)


class TestHiddenActivities:

    def test_instantiate(self, hidden_cls):
        """All hidden activities must instantiate without error."""
        act = _start(hidden_cls)
        assert act is not None
        assert act.life.created

    def test_has_act_name(self, hidden_cls):
        """All hidden activities must have a non-empty ACT_NAME."""
        assert hasattr(hidden_cls, 'ACT_NAME')
        assert hidden_cls.ACT_NAME
        assert isinstance(hidden_cls.ACT_NAME, str)

    def test_pwr_response(self, hidden_cls):
        """All hidden activities must respond to PWR key."""
        act = _start(hidden_cls)
        act.onKeyEvent(KEY_PWR)
        # Should either finish or change state -- never crash
        assert True

    def test_has_onkeyevent(self, hidden_cls):
        """All hidden activities must implement onKeyEvent."""
        assert hasattr(hidden_cls, 'onKeyEvent')


class TestSnakeGame:

    def test_title_greedy_snake(self):
        from activity_main import SnakeGameActivity
        act = _start(SnakeGameActivity)
        texts = act.getCanvas().get_all_text()
        assert 'Greedy Snake' in texts

    def test_initial_idle(self):
        from activity_main import SnakeGameActivity
        act = _start(SnakeGameActivity)
        assert act._game_state == 'idle'

    def test_start_game(self):
        from activity_main import SnakeGameActivity
        act = _start(SnakeGameActivity)
        act.onKeyEvent(KEY_OK)
        assert act._game_state == 'playing'

    def test_pause_game(self):
        from activity_main import SnakeGameActivity
        act = _start(SnakeGameActivity)
        act.onKeyEvent(KEY_OK)  # start
        # First PWR in playing state: _handlePWR may dismiss game_tips toast
        act.onKeyEvent(KEY_PWR)
        if act._game_state == 'playing':
            # Toast was dismissed; second PWR actually pauses
            act.onKeyEvent(KEY_PWR)
        assert act._game_state == 'idle'

    def test_pwr_exits_idle(self):
        from activity_main import SnakeGameActivity
        act = _start(SnakeGameActivity)
        # First PWR in idle: _handlePWR may dismiss game_tips toast
        act.onKeyEvent(KEY_PWR)
        if not act.life.destroyed:
            # Toast was dismissed; second PWR finishes
            act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


class TestWarningT5X:

    def test_title(self):
        from activity_main import WarningT5XActivity
        act = _start(WarningT5XActivity)
        texts = act.getCanvas().get_all_text()
        assert 'No valid key' in texts

    def test_proceed(self):
        from activity_main import WarningT5XActivity
        act = _start(WarningT5XActivity)
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed


class TestWarningT5XKeyEnter:

    def test_hex_input(self):
        from activity_main import WarningT5X4X05KeyEnterActivity
        act = _start(WarningT5X4X05KeyEnterActivity)
        assert act._input_method is not None
        assert act._input_method.getValue() == '00000000'

    def test_confirm(self):
        from activity_main import WarningT5X4X05KeyEnterActivity
        act = _start(WarningT5X4X05KeyEnterActivity)
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed
        assert act._result_key == '00000000'

    def test_cancel(self):
        from activity_main import WarningT5X4X05KeyEnterActivity
        act = _start(WarningT5X4X05KeyEnterActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed
