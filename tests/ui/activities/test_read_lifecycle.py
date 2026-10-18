"""Read callbacks must belong to the live operation and run on the UI thread."""
import threading
from threading import Thread as RealThread

import pytest

import actstack
import hmi_driver
import scan
from activity_read import ReadActivity
from _constants import KEY_M1, KEY_PWR
from tests.ui.conftest import MockCanvas


HF = {'found': True, 'return': 0, 'type': 1, 'uid': '9C750884',
      'len': 4, 'sak': '08', 'atqa': '0004'}
EVENTS = [
    ('call_reading', {'success': True, 'return': 1, 'bundle': 'old.bin'}),
    ('call_reading', {'success': False, 'return': -3}),
    ('call_reading', {'success': False, 'return': -2}),
    ('call_reading', {'progress': 99, 'action': 'old progress'}),
    ('call_exception', 'old read disconnected'),
]


def reading(flow):
    activity = actstack.start_activity(ReadActivity, {'tag_type': 1})
    flow.scan_result(activity, HF.copy())
    return activity


@pytest.mark.parametrize('callback,value', EVENTS)
def test_late_read_event_cannot_revive_destroyed_activity(read_flow, callback, value):
    activity = reading(read_flow)
    emit = getattr(read_flow.reader, callback)
    activity.callKeyEvent(KEY_PWR)
    emit(value)
    activity.getCanvas().advance(250)
    assert activity.life.destroyed
    assert actstack.get_current_activity() is None
    assert activity.getCanvas().get_all_text() == []
    assert activity._read_bundle is None


@pytest.mark.parametrize('callback,value', EVENTS)
def test_previous_read_cannot_complete_a_retry(read_flow, callback, value):
    activity = reading(read_flow)
    emit = getattr(read_flow.reader, callback)
    read_flow.read_result(activity, {'success': False, 'return': -2})
    activity.callKeyEvent(KEY_M1)
    read_flow.scan_result(activity, HF.copy())
    before = activity.getCanvas().snapshot()
    emit(value)
    assert activity.state == 'reading'
    assert activity._read_bundle is None
    assert activity.getCanvas().snapshot() == before
    read_flow.read_result(activity, {'success': True, 'bundle': 'current.bin'})
    assert activity._read_bundle == 'current.bin'


def test_invalidate_reader_before_hardware_abort(read_flow, monkeypatch):
    activity = reading(read_flow)
    emit = read_flow.reader.call_reading
    observed = []

    def abort():
        observed.append(read_flow.reader.stop.call_count)
        emit({'success': False, 'return': -3})
        observed.append(actstack.get_current_activity() is activity)

    monkeypatch.setattr(hmi_driver, 'presspm3', abort)
    activity.callKeyEvent(KEY_PWR)
    assert observed == [1, True]
    assert actstack.get_current_activity() is None
    read_flow.reader.stop.assert_called_once_with()


def test_retry_resets_progress_used_for_exception_classification(read_flow):
    activity = reading(read_flow)
    read_flow.reader.call_reading({'progress': 20})
    read_flow.read_result(activity, {'success': False, 'return': -2})
    activity.callKeyEvent(KEY_M1)
    read_flow.scan_result(activity, HF.copy())
    read_flow.reader.call_exception('unsupported before any progress')
    activity.getCanvas().advance(250)
    assert activity.state == 'no_tag'


def test_stop_error_cannot_restore_callbacks_or_prevent_exit(read_flow):
    activity = reading(read_flow)
    emit = read_flow.reader.call_reading

    def broken_stop():
        emit({'success': False, 'return': -3})
        raise RuntimeError('reader disconnected')

    read_flow.reader.stop.side_effect = broken_stop
    activity.callKeyEvent(KEY_PWR)
    assert activity.life.destroyed
    assert actstack.get_current_activity() is None
    read_flow.reader.stop.assert_called_once_with()


@pytest.mark.parametrize('callback,value', EVENTS)
def test_queued_read_event_is_discarded_after_exit(read_flow, monkeypatch, callback, value):
    activity = reading(read_flow)
    # Start a fresh read with the real UI-queue boundary present.
    ui = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui)
    activity._startRead()
    getattr(read_flow.reader, callback)(value)
    assert activity.state == 'reading'
    activity.callKeyEvent(KEY_PWR)
    ui.advance(250)
    activity.getCanvas().advance(250)
    assert not ui._timers
    assert actstack.get_current_activity() is None
    assert activity.getCanvas().get_all_text() == []


def test_worker_queues_without_calling_tk_and_ui_delivers_result(read_flow, monkeypatch):
    activity = reading(read_flow)
    ui = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui)
    activity._startRead()
    owner = threading.get_ident()
    original_after = ui.after

    def main_thread_after(*args):
        assert threading.get_ident() == owner, 'worker called Tk.after'
        return original_after(*args)

    monkeypatch.setattr(ui, 'after', main_thread_after)
    emit = read_flow.reader.call_reading
    assert emit.__self__ is activity  # Preserve the legacy read.so callback ABI.
    worker = RealThread(target=emit, args=({'success': True, 'bundle': 'new.bin'},))
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert activity.state == 'reading'
    ui.advance(50)
    activity.getCanvas().advance(250)
    assert activity.state == 'read_success'
    assert activity._read_bundle == 'new.bin'


def test_failed_read_uses_its_accepted_scan_context(read_flow):
    activity = reading(read_flow)
    scan.setScanCache({'found': True, 'type': 8, 'data': '1122334455'})
    read_flow.read_result(activity, {'success': False, 'return': -1})
    assert activity.state == 'read_failed'


def test_first_terminal_event_wins(read_flow):
    activity = reading(read_flow)
    read_flow.reader.call_exception('unsupported reader')
    read_flow.read_result(activity, {'success': False, 'return': -1})
    assert activity.state == 'no_tag'


def test_legacy_completion_poll_runs_on_ui_and_stops_after_exit(read_flow, monkeypatch):
    import activity_read
    activity = reading(read_flow)
    ui = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui)
    monkeypatch.setattr(activity_read.time, 'monotonic', lambda: ui._now_ms / 1000)
    read_flow.reader.is_reading.return_value = False
    activity._startRead()
    ui.advance(1999)
    assert activity.state == 'reading'
    ui.advance(1)
    activity.getCanvas().advance(250)
    assert activity.state == 'read_failed'
    activity.callKeyEvent(KEY_PWR)
    assert not ui._timers


def test_old_poll_cannot_consume_retry_or_lose_its_timer(read_flow, monkeypatch):
    activity = reading(read_flow)
    ui = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui)
    activity._startRead()
    _ms, old_poll, args = ui._timers[activity._read_timer]
    activity._startRead()
    current_timer = activity._read_timer
    old_poll(*args)  # Already dispatched when cancellation happened.
    assert activity._read_timer == current_timer
    assert activity.state == 'reading'
    activity.callKeyEvent(KEY_PWR)
    assert not ui._timers


def test_progress_backlog_cannot_hide_a_queued_failure(read_flow, monkeypatch):
    import activity_read
    activity = reading(read_flow)
    ui = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui)
    monkeypatch.setattr(activity_read.time, 'monotonic', lambda: ui._now_ms / 1000)
    read_flow.reader.is_reading.return_value = False
    activity._startRead()
    # More than two seconds of bounded queue draining: a completed worker's
    # result must win over the legacy progress-based completion fallback.
    for _ in range(5000):
        read_flow.reader.call_reading({'progress': 50})
    read_flow.reader.call_reading({'success': False, 'return': -2})
    ui.advance(2000)
    assert activity.state == 'reading'
    assert activity._read_bundle is None
    ui.advance(1000)
    activity.getCanvas().advance(250)
    assert activity.state == 'read_failed'
