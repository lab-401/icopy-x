"""Regressions for scan-result classification and ReadActivity cancellation."""

import threading
from threading import Thread as RealThread
from unittest.mock import Mock

import pytest
import actstack
import scan
from scan import Scanner as RealScanner
from activity_read import ReadActivity
from _constants import KEY_M2, KEY_PWR
from tests.ui.conftest import MockCanvas


HF = {'found': True, 'return': 0, 'type': 1, 'uid': '9C750884',
      'len': 4, 'sak': '08', 'atqa': '0004'}


def start_read():
    return actstack.start_activity(ReadActivity, {'tag_type': 1})


@pytest.mark.parametrize('result', [
    # This is scan.createTagMulti()'s actual contract: found is True.
    {'progress': 100, 'return': -3, 'found': True, 'type': -1},
    {'return': -3, 'found': False, 'type': -1},
    # Preserve the legacy callback shape too.
    {'found': False, 'hasMulti': True},
    {'found': True, 'hasMulti': True},
])
def test_multiple_tags_never_start_a_reader(read_flow, result):
    activity = start_read()
    read_flow.scan_result(activity, result)
    read_flow.reader.start.assert_not_called()
    assert activity.state == 'no_tag'
    assert 'Multiple tags detected!' in activity.getCanvas().get_all_text()
    assert 'Rescan' in activity.getCanvas().get_all_text()
    assert not activity.isbusy()


def test_scan_multi_fixture_matches_middleware_contract():
    assert scan.createTagMulti(100) == {
        'progress': 100, 'return': -3, 'found': True, 'type': -1,
    }


def test_power_cancels_scanner_using_its_public_api(read_flow):
    activity = start_read()
    activity.callKeyEvent(KEY_PWR)
    read_flow.scanner.scan_stop.assert_called_once_with()
    read_flow.stop_pm3.assert_called_once_with(wait=False)
    assert activity._scanner is None
    assert actstack.get_current_activity() is None


def test_repeated_scan_cancellation_is_idempotent(read_flow):
    activity = start_read()
    activity._cancelScan()
    activity._cancelScan()
    read_flow.scanner.scan_stop.assert_called_once_with()
    assert activity._scanner is None


def test_scan_cancellation_error_still_releases_activity(read_flow):
    read_flow.scanner.scan_stop.side_effect = RuntimeError('scanner disconnected')
    activity = start_read()
    activity.callKeyEvent(KEY_PWR)
    read_flow.scanner.scan_stop.assert_called_once_with()
    assert activity._scanner is None
    assert actstack.get_current_activity() is None
    read_flow.scanner.call_resulted(HF.copy())
    activity.getCanvas().advance(250)
    read_flow.reader.start.assert_not_called()
    assert activity.getCanvas().get_all_text() == []


@pytest.mark.parametrize('result', [
    {'progress': 0, 'return': -4, 'found': False, 'type': -1},
    {'progress': 0, 'return': -3, 'found': True, 'type': -1},
    HF,
    RuntimeError('command interrupted'),
])
def test_real_scanner_callbacks_after_power_exit_are_ignored(read_flow, monkeypatch, result):
    scanner = RealScanner()
    monkeypatch.setattr(scan, 'Scanner', Mock(return_value=scanner))
    activity = start_read()
    canvas = activity.getCanvas()
    late_progress = Mock(wraps=scanner.call_progress)
    late_result = Mock(wraps=scanner.call_resulted)
    late_exception = Mock(wraps=scanner.call_exception)
    scanner.call_progress = late_progress
    scanner.call_resulted = late_result
    scanner.call_exception = late_exception
    lf_scan = Mock(side_effect=AssertionError('cancelled scan continued to LF'))
    monkeypatch.setattr(scan, 'scan_lfsea', lf_scan)

    def finish_in_flight_command():
        activity.callKeyEvent(KEY_PWR)
        assert activity.life.destroyed
        assert actstack.get_current_activity() is None
        assert scanner._stop_label
        late_progress.reset_mock()
        if isinstance(result, Exception):
            raise result
        return result.copy()

    monkeypatch.setattr(scan, 'scan_14a', finish_in_flight_command)
    read_flow.workers[0].run()
    # Cancellation now unwinds before caching/delivering the late result.
    lf_scan.assert_not_called()
    if isinstance(result, Exception):
        late_exception.assert_called_once()
    else:
        late_progress.assert_not_called()
        late_result.assert_not_called()
    canvas.advance(250)
    assert canvas.get_all_text() == []
    read_flow.reader.start.assert_not_called()


@pytest.mark.parametrize('abort_boundary', ['presspm3', 'stopPM3Task'])
def test_result_during_hardware_abort_cannot_start_reader(read_flow, monkeypatch, abort_boundary):
    import executor
    import hmi_driver
    activity = start_read()
    read_flow.scanner.call_progress((100, 100))
    activity.getCanvas().advance(250)
    stop_counts_at_abort = []

    def abort(**kwargs):
        stop_counts_at_abort.append(read_flow.scanner.scan_stop.call_count)
        read_flow.scanner.call_resulted(HF.copy())

    module = hmi_driver if abort_boundary == 'presspm3' else executor
    monkeypatch.setattr(module, abort_boundary, abort)
    activity.callKeyEvent(KEY_PWR)
    assert stop_counts_at_abort == [1]
    read_flow.reader.start.assert_not_called()


@pytest.mark.parametrize('result', [HF, None])
def test_cancel_during_completion_animation_prevents_transition(read_flow, result):
    activity = start_read()
    read_flow.scanner.call_resulted(result)
    read_flow.reader.start.assert_not_called()
    activity.callKeyEvent(KEY_PWR)
    activity.getCanvas().advance(250)
    read_flow.reader.start.assert_not_called()
    assert activity.getCanvas().get_all_text() == []


@pytest.mark.parametrize('callback,argument', [
    ('call_progress', (100, 100)),
    ('call_resulted', HF),
    ('call_exception', 'scanner disconnected'),
])
def test_queued_callback_is_ignored_after_exit(read_flow, monkeypatch, callback, argument):
    activity = start_read()
    ui_queue = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui_queue)
    getattr(read_flow.scanner, callback)(argument)
    assert ui_queue._timers, 'scanner callbacks must be dispatched to the UI queue'
    activity.callKeyEvent(KEY_PWR)
    ui_queue.advance(250)
    activity.getCanvas().advance(250)
    read_flow.reader.start.assert_not_called()
    assert activity.getCanvas().get_all_text() == []


def test_callbacks_from_previous_scan_cannot_affect_rescan(read_flow):
    activity = start_read()
    old_progress = read_flow.scanner.call_progress
    old_result = read_flow.scanner.call_resulted
    old_exception = read_flow.scanner.call_exception
    read_flow.scan_result(activity, scan.createTagNoFound(100))
    activity.callKeyEvent(KEY_M2)
    before = activity.getCanvas().snapshot()
    old_progress((100, 100))
    old_result(HF.copy())
    old_exception('old scan failed')
    assert activity.getCanvas().snapshot() == before
    activity.getCanvas().advance(250)
    assert activity.state == 'scanning'
    read_flow.reader.start.assert_not_called()
    read_flow.scan_result(activity, HF.copy())
    read_flow.reader.start.assert_called_once_with(1, {'infos': HF, 'force': False})


def test_queued_old_result_cannot_replace_new_scan(read_flow, monkeypatch):
    activity = start_read()
    ui_queue = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui_queue)
    old_result = read_flow.scanner.call_resulted
    old_result(scan.createTagNoFound(100))
    old_result(HF.copy())
    # Deliver the first completion, then rescan before the queued duplicate runs.
    ui_queue.fire_after(next(iter(ui_queue._timers)))
    assert activity.state == 'no_tag'
    activity.callKeyEvent(KEY_M2)
    ui_queue.advance(250)
    activity.getCanvas().advance(250)
    assert activity.state == 'scanning'
    read_flow.reader.start.assert_not_called()


def test_duplicate_completion_starts_only_one_reader(read_flow):
    activity = start_read()
    scan.setScanCache(HF.copy())
    read_flow.scanner.call_resulted(HF.copy())
    read_flow.scanner.call_resulted(HF.copy())
    activity.getCanvas().advance(250)
    read_flow.reader.start.assert_called_once_with(1, {'infos': HF, 'force': False})


def test_normal_scan_updates_run_through_ui_queue(read_flow, monkeypatch):
    activity = start_read()
    ui_queue = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui_queue)
    before = activity.getCanvas().snapshot()
    read_flow.scanner.call_progress((100, 100))
    read_flow.scanner.call_resulted(HF.copy())
    assert activity.getCanvas().snapshot() == before
    read_flow.reader.start.assert_not_called()
    ui_queue.advance(0)
    activity.getCanvas().advance(250)
    assert activity.state == 'reading'
    read_flow.reader.start.assert_called_once_with(1, {'infos': HF, 'force': False})


def test_read_uses_accepted_result_if_global_cache_changes(read_flow):
    activity = start_read()
    read_flow.scanner.call_resulted(HF.copy())
    # A previous Scanner may finish and update its global cache while the
    # current activity waits for the scan-completion animation.
    scan.setScanCache({'found': True, 'return': 0, 'type': 8, 'data': '1122334455'})
    activity.getCanvas().advance(250)
    read_flow.reader.start.assert_called_once_with(1, {'infos': HF, 'force': False})


def test_worker_callback_only_updates_progress_when_ui_queue_runs(read_flow, monkeypatch):
    activity = start_read()
    ui_queue = MockCanvas()
    monkeypatch.setattr(actstack, '_root', ui_queue)
    ui_thread = threading.get_ident()
    updated_on = []
    original_update = activity._progress.setProgress

    def record_update(value):
        updated_on.append(threading.get_ident())
        original_update(value)

    monkeypatch.setattr(activity._progress, 'setProgress', record_update)
    worker = RealThread(target=read_flow.scanner.call_progress, args=((75, 100),),
                        daemon=True)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert updated_on == []
    ui_queue.advance(0)
    assert updated_on == [ui_thread]


@pytest.mark.parametrize('stage', ['scanning', 'completing', 'reading', 'multiple', 'no_tag'])
def test_exit_removes_widget_timers_before_destroying_canvas(read_flow, stage):
    activity = start_read()
    if stage == 'completing':
        read_flow.scanner.call_resulted(HF.copy())
    elif stage == 'reading':
        read_flow.scan_result(activity, HF.copy())
        read_flow.reader.call_reading({'progress': 75})
    elif stage in ('multiple', 'no_tag'):
        result = scan.createTagMulti(100) if stage == 'multiple' else scan.createTagNoFound(100)
        read_flow.scan_result(activity, result)
    canvas = activity.getCanvas()
    assert canvas._timers
    activity.callKeyEvent(KEY_PWR)
    # Real Tk deletes the callback's Tcl command when destroying the canvas.
    # Leaving its timer queued then raises 'invalid command name'.
    assert canvas._timers == {}
