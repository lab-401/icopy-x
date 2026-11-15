"""Screen Mirroring must apply when the toggle is flipped, not on next launch.

Field symptom: selecting Screen Mirroring persisted the setting but started
nothing — no ``g_serial``, no ``/dev/ttyGS0``, and therefore no COM port on the
host.  ``MirrorService`` was only ever started from ``application.py`` while
reading ``settings.getScreenMirror()`` at launch, so the toggle appeared dead
until the app was restarted.

Activity tests run with the ``activity_workers`` scheduler, which queues threads
instead of starting them; the queued worker is executed explicitly here.
"""

import sys
import types

import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_OK


class MirrorRecorder:
    """Stands in for MirrorService and records start/stop order."""

    def __init__(self):
        self._events = []

    def start(self):
        self._events.append('start')

    def stop(self):
        self._events.append('stop')

    def snapshot(self):
        return list(self._events)


@pytest.fixture(autouse=True)
def _setup_actstack():
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


@pytest.fixture
def mirror(monkeypatch):
    """Stub the persisted setting and the mirror service."""
    recorder = MirrorRecorder()
    state = {'on': 0}

    settings_mod = types.ModuleType('settings')
    settings_mod.getScreenMirror = lambda: state['on']
    settings_mod.setScreenMirror = lambda value: state.__setitem__('on', value)
    monkeypatch.setitem(sys.modules, 'settings', settings_mod)

    import lib.mirror_service as service_mod
    monkeypatch.setattr(service_mod, 'get_service', lambda: recorder)

    return recorder, state


def _open_settings():
    from activity_main import SettingsMenuActivity
    return actstack.start_activity(SettingsMenuActivity)


def test_enabling_starts_the_service_immediately(mirror, activity_workers):
    recorder, state = mirror
    activity = _open_settings()
    assert state['on'] == 0

    activity.onKeyEvent(KEY_OK)           # the mirror row is selected first

    assert activity._mirror_state is True
    assert state['on'] == 1, 'the choice must be persisted'
    assert len(activity_workers) == 1, 'toggling must schedule the service change'
    activity_workers[0].run()
    assert recorder.snapshot() == ['start']


def test_disabling_stops_the_service_immediately(mirror, activity_workers):
    recorder, state = mirror
    activity = _open_settings()

    activity.onKeyEvent(KEY_OK)
    activity_workers.pop().run()

    activity.onKeyEvent(KEY_OK)
    activity_workers.pop().run()

    assert recorder.snapshot() == ['start', 'stop']
    assert state['on'] == 0


def test_opening_the_menu_does_not_restart_the_service(mirror):
    recorder, state = mirror
    state['on'] = 1

    activity = _open_settings()

    assert activity._mirror_state is True
    assert recorder.snapshot() == [], 'application.py owns the launch-time start'
