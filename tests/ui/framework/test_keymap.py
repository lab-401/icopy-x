"""Tests for lib.keymap — KeyEvent dispatcher, key translation, PWR handling.

Covers:
  - Module-level key constant re-exports
  - Module-level ``key`` singleton
  - _compat translation for v1.0.90, legacy, and direct formats
  - PWR special formats (_PWR_CAN_PRES!, KEYPWR_PRES!)
  - bind / unbind / dispatch flow
  - PWR key triggers finish_activity
  - Thread-safe bind
  - Unknown keys are silently ignored
"""

import sys
import os
import threading
from unittest import mock

import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib import keymap
from lib.keymap import KeyEvent, key
from lib._constants import (
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
    KEY_SHUTDOWN, KEY_ALL, KEY_APO,
)


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

class FakeActivity:
    """Minimal activity mock with callKeyEvent recording."""

    def __init__(self):
        self.received = []

    def callKeyEvent(self, key_code):
        self.received.append(key_code)


# =================================================================
# TestKeyConstants
# =================================================================

class TestKeyConstants:
    """Verify that module-level re-exports match _constants.py."""

    def test_constants_defined(self):
        assert keymap.UP == KEY_UP
        assert keymap.DOWN == KEY_DOWN
        assert keymap.LEFT == KEY_LEFT
        assert keymap.RIGHT == KEY_RIGHT
        assert keymap.OK == KEY_OK
        assert keymap.M1 == KEY_M1
        assert keymap.M2 == KEY_M2
        assert keymap.POWER == KEY_PWR
        assert keymap.SHUTDOWN == KEY_SHUTDOWN
        assert keymap.ALL == KEY_ALL
        assert keymap.APO == KEY_APO

    def test_module_level_key_singleton(self):
        """keymap.key is a KeyEvent instance, usable as a singleton."""
        assert isinstance(key, KeyEvent)
        # Same object on repeated access
        assert keymap.key is key


# =================================================================
# TestKeyEventCompat
# =================================================================

class TestKeyEventCompat:
    """_compat translates hardware codes to logical key constants."""

    def setup_method(self):
        self.ke = KeyEvent()

    def test_compat_v1090_format(self):
        """v1.0.90 hardware format: KEYOK_PRES! -> OK, etc."""
        assert self.ke._compat('KEYOK_PRES!') == 'OK'
        assert self.ke._compat('KEYM1_PRES!') == 'M1'
        assert self.ke._compat('KEYM2_PRES!') == 'M2'
        assert self.ke._compat('KEYUP_PRES!') == 'UP'
        assert self.ke._compat('KEYDOWN_PRES!') == 'DOWN'
        assert self.ke._compat('KEYLEFT_PRES!') == 'LEFT'
        assert self.ke._compat('KEYRIGHT_PRES!') == 'RIGHT'
        assert self.ke._compat('KEYPWR_PRES!') == 'PWR'

    def test_compat_legacy_format(self):
        """Legacy hardware format: OK_PRES! -> OK, etc."""
        assert self.ke._compat('OK_PRES!') == 'OK'
        assert self.ke._compat('M1_PRES!') == 'M1'
        assert self.ke._compat('M2_PRES!') == 'M2'
        assert self.ke._compat('UP_PRES!') == 'UP'
        assert self.ke._compat('DOWN_PRES!') == 'DOWN'
        assert self.ke._compat('LEFT_PRES!') == 'LEFT'
        assert self.ke._compat('RIGHT_PRES!') == 'RIGHT'

    def test_compat_direct_format(self):
        """Direct format: already-translated codes pass through."""
        assert self.ke._compat('OK') == 'OK'
        assert self.ke._compat('M1') == 'M1'
        assert self.ke._compat('M2') == 'M2'
        assert self.ke._compat('UP') == 'UP'
        assert self.ke._compat('DOWN') == 'DOWN'
        assert self.ke._compat('LEFT') == 'LEFT'
        assert self.ke._compat('RIGHT') == 'RIGHT'
        assert self.ke._compat('PWR') == 'PWR'

    def test_compat_pwr_formats(self):
        """PWR has multiple hardware representations."""
        assert self.ke._compat('_PWR_CAN_PRES!') == 'PWR'
        assert self.ke._compat('PWR_CAN_PRES!') == 'PWR'
        assert self.ke._compat('KEYPWR_PRES!') == 'PWR'
        assert self.ke._compat('PWR') == 'PWR'

    def test_compat_all_keys(self):
        """Every logical key has at least one hardware mapping."""
        all_logical = {KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
                       KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
                       KEY_SHUTDOWN, KEY_ALL, KEY_APO}
        mapped_values = set(keymap._COMPAT_MAP.values())
        assert all_logical == mapped_values

    def test_compat_unknown_returns_none(self):
        """Unrecognised raw codes return None."""
        assert self.ke._compat('GARBAGE') is None
        assert self.ke._compat('') is None
        assert self.ke._compat('KEYFOO_PRES!') is None


# =================================================================
# TestKeyEventDispatch
# =================================================================

class TestKeyEventDispatch:
    """onKey dispatches to bound activity via callKeyEvent."""

    def setup_method(self):
        self.ke = KeyEvent()

    def test_bind_and_dispatch(self):
        """Bound activity receives translated key via callKeyEvent."""
        act = FakeActivity()
        self.ke.bind(act)
        self.ke.onKey('OK')
        assert act.received == ['OK']

    def test_dispatch_multiple_keys(self):
        """Multiple key events dispatched in order."""
        act = FakeActivity()
        self.ke.bind(act)
        self.ke.onKey('UP')
        self.ke.onKey('DOWN')
        self.ke.onKey('KEYOK_PRES!')
        assert act.received == ['UP', 'DOWN', 'OK']

    def test_unbind_stops_dispatch(self):
        """After unbind, key events are not dispatched."""
        act = FakeActivity()
        self.ke.bind(act)
        self.ke.onKey('OK')
        assert len(act.received) == 1

        self.ke.unbind()
        self.ke.onKey('DOWN')
        assert len(act.received) == 1  # no new events

    def test_pwr_dispatched_to_activity(self):
        """PWR key is dispatched to bound activity via callKeyEvent.

        Each activity handles PWR in its own onKeyEvent (finish, cancel, etc.).
        """
        act = FakeActivity()
        self.ke.bind(act)
        self.ke.onKey('PWR')
        assert 'PWR' in act.received

    def test_pwr_run_shutdown_calls_os_system(self):
        """_run_shutdown calls os.system('sudo shutdown -t 0')."""
        with mock.patch('os.system') as mock_sys:
            self.ke._run_shutdown()
            mock_sys.assert_called_once_with('sudo shutdown -t 0')

    def test_thread_safe_bind(self):
        """bind/unbind are thread-safe — no crashes under concurrency."""
        act1 = FakeActivity()
        act2 = FakeActivity()
        errors = []

        def bind_loop(target, count):
            try:
                for _ in range(count):
                    self.ke.bind(target)
                    self.ke.onKey('OK')
                    self.ke.unbind()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=bind_loop, args=(act1, 50))
        t2 = threading.Thread(target=bind_loop, args=(act2, 50))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        # Total dispatches should equal total binds that got an OK
        total = len(act1.received) + len(act2.received)
        assert total > 0  # at least some dispatches went through

    def test_unknown_key_ignored(self):
        """Unknown key codes are silently dropped."""
        act = FakeActivity()
        self.ke.bind(act)
        self.ke.onKey('GARBAGE_KEY')
        assert act.received == []

    def test_no_target_no_crash(self):
        """Dispatching with no bound target does not crash."""
        self.ke.onKey('OK')  # should not raise
