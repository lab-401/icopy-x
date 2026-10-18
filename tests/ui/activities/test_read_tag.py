"""Host tests of the real ReadActivity callback contract.

The Reader.start/call_reading and write-screen handoff are documented in
Real_Hardware_Intel/trace_read_flow_20260401.txt and
full_read_write_trace_20260327.txt. No activity methods are patched here.
Device operations and fallback polling are outside these callback tests.
"""

import pytest
import actstack
from activity_read import ReadActivity
from activity_main import WarningM1Activity, WarningWriteActivity, WriteActivity
from _constants import KEY_M1, KEY_M2, KEY_OK, KEY_PWR, KEY_UP, KEY_DOWN


HF = {'found': True, 'return': 0, 'type': 1, 'uid': '9C750884',
      'len': 4, 'sak': '08', 'atqa': '0004'}
LF = {'found': True, 'return': 0, 'type': 8,
      'data': '1122334455', 'raw': 'FF80605028180F09'}


def start(read_flow, tag_type=1):
    return actstack.start_activity(ReadActivity,
                                   {'tag_type': tag_type, 'tag_name': 'Test card'})


def reading(read_flow, infos=None):
    infos = HF.copy() if infos is None else infos
    activity = start(read_flow, infos['type'])
    read_flow.scan_result(activity, infos)
    assert activity.state == 'reading'
    return activity


def test_no_bundle_remains_idle(read_flow):
    activity = actstack.start_activity(ReadActivity)
    assert activity.state == 'idle'
    read_flow.scanner.scan_all_asynchronous.assert_not_called()


def test_partial_ultralight_is_not_presented_as_full_read(read_flow):
    activity = reading(read_flow, {'found': True, 'type': 2, 'uid': '04112233445566'})
    read_flow.read_result(activity, {'success': True, 'force': False, 'partial': True,
                                     'bundle': '/mnt/upan/dump/mfu/partial.bin'})
    assert activity.state == 'read_partial'
    assert any('Partial data' in t for t in activity.getCanvas().get_all_text())
    assert activity._read_bundle == '/mnt/upan/dump/mfu/partial.bin'


@pytest.mark.parametrize('tag_type', [1, 8, 23, 24])
def test_starts_correct_scanner(read_flow, tag_type):
    activity = start(read_flow, tag_type)
    assert activity.state == 'scanning'
    assert 'Read Tag' in activity.getCanvas().get_all_text()
    assert activity.isbusy()
    # Registration captures this scan's identity; callback behavior is tested
    # through the registered callable below rather than bound-method identity.
    assert callable(read_flow.scanner.call_resulted)
    if tag_type in (23, 24):
        read_flow.scanner.scan_type_asynchronous.assert_called_once_with(tag_type)
        read_flow.scanner.scan_all_asynchronous.assert_not_called()
    else:
        read_flow.scanner.scan_all_asynchronous.assert_called_once_with()


def test_scan_completion_waits_for_animation_then_starts_reader(read_flow):
    import scan
    activity = start(read_flow)
    scan.setScanCache(HF.copy())
    read_flow.scanner.call_resulted(HF.copy())
    assert activity.state == 'scanning'
    read_flow.reader.start.assert_not_called()
    activity.getCanvas().advance(250)
    assert activity.state == 'reading'
    assert activity.isbusy()
    assert read_flow.reader.call_reading.__self__ is activity
    assert read_flow.reader.call_exception.__self__ is activity
    read_flow.reader.start.assert_called_once_with(1, {'infos': HF, 'force': False})


@pytest.mark.parametrize('result', [None,
    {'found': False, 'return': -1, 'type': -1},
    {'found': False, 'return': -4, 'type': -1},
    {'found': False, 'return': -5, 'type': -1}])
def test_unsuccessful_scan_offers_only_rescan(read_flow, result):
    activity = start(read_flow)
    read_flow.scan_result(activity, result)
    assert activity.state == 'no_tag'
    assert not activity.isbusy()
    assert 'Rescan' in activity.getCanvas().get_all_text()
    read_flow.reader.start.assert_not_called()
    read_flow.scanner.scan_all_asynchronous.reset_mock()
    for key in (KEY_M1, KEY_OK):
        activity.callKeyEvent(key)
        read_flow.scanner.scan_all_asynchronous.assert_not_called()
    activity.callKeyEvent(KEY_M2)
    read_flow.scanner.scan_all_asynchronous.assert_called_once_with()
    assert activity.state == 'scanning'


@pytest.mark.parametrize('infos,bundle', [(HF, '/mnt/upan/dump/mf1/card.bin'),
                                       (LF, {'return': 1, 'data': '1122334455'})])
@pytest.mark.parametrize('partial', [False, True])
def test_success_keeps_write_bundle_and_shows_result(read_flow, infos, bundle, partial):
    activity = reading(read_flow, infos.copy())
    read_flow.read_result(activity, {'success': True, 'return': 1,
                                     'bundle': bundle, 'force': partial})
    assert activity.state == ('read_partial' if partial else 'read_success')
    assert activity._read_bundle == bundle
    assert not activity.isbusy()
    texts = activity.getCanvas().get_all_text()
    assert 'Read Tag' in texts
    assert 'Reread' in texts and 'Write' in texts
    assert any(('Partial data' if partial else 'File saved') in text for text in texts)
    activity.callKeyEvent(KEY_M2)
    warning = actstack.get_current_activity()
    assert isinstance(warning, WarningWriteActivity)
    # Confirm through the actual warning screen; the bundle must reach WriteActivity.
    warning.callKeyEvent(KEY_M2)
    writer = actstack.get_current_activity()
    assert isinstance(writer, WriteActivity)
    assert writer._read_bundle == bundle


@pytest.mark.parametrize('ret_code', [-2, 0, -99])
def test_read_failure_never_offers_a_write(read_flow, ret_code):
    activity = reading(read_flow)
    read_flow.read_result(activity, {'success': False, 'return': ret_code})
    assert activity.state == 'read_failed'
    assert not activity.isbusy()
    assert 'Read Failed!' in activity.getCanvas().get_all_text()
    for key in (KEY_M2, KEY_OK):
        activity.callKeyEvent(key)
        assert actstack.get_current_activity() is activity
    activity.callKeyEvent(KEY_M1)
    assert activity.state == 'scanning'


@pytest.mark.parametrize('ret_code', [-3, -4])
def test_key_recovery_failure_opens_warning_and_force_retries(read_flow, ret_code):
    activity = reading(read_flow)
    read_flow.read_result(activity, {'success': False, 'return': ret_code})
    assert activity.state == 'warning_keys'
    warning = actstack.get_current_activity()
    assert isinstance(warning, WarningM1Activity)
    activity.onActivity({'action': 'force'})
    read_flow.reader.start.assert_called_with(1, {'infos': HF, 'force': True})
    assert activity.state == 'reading'


@pytest.mark.parametrize('infos,state', [(HF, 'read_failed'), (LF, 'no_tag')])
def test_unconfirmed_read_result_uses_scan_context(read_flow, infos, state):
    activity = reading(read_flow, infos.copy())
    read_flow.read_result(activity, {'success': False, 'return': -1})
    assert activity.state == state


@pytest.mark.parametrize('progress,state,message', [
    (False, 'no_tag', 'Wrong type'),
    (True, 'read_failed', 'Read Failed!'),
])
def test_reader_exception_distinguishes_unsupported_tag_from_failed_read(read_flow, progress, state, message):
    activity = reading(read_flow)
    if progress:
        read_flow.reader.call_reading({'progress': 25})
    read_flow.reader.call_exception(RuntimeError('reader disconnected'))
    activity.getCanvas().advance(250)
    assert activity.state == state
    assert any(message in text for text in activity.getCanvas().get_all_text())


def test_progress_dict_renders_keys_timer_and_percentage(read_flow):
    activity = reading(read_flow)
    read_flow.reader.call_reading({'progress': 75, 'action': 'ChkDIC',
                                   'keyIndex': 16, 'keyCountMax': 32, 'seconds': 68})
    activity.getCanvas().advance(250)
    assert activity._progress.getProgress() == 75
    texts = activity.getCanvas().get_all_text()
    assert 'ChkDIC...16/32keys' in texts
    assert '01:08' in texts
    assert activity.state == 'reading'


@pytest.mark.parametrize('phase', ['scanning', 'reading'])
@pytest.mark.parametrize('key', [KEY_UP, KEY_DOWN, KEY_M1, KEY_M2, KEY_OK])
def test_busy_keys_cannot_start_another_operation(read_flow, phase, key):
    activity = start(read_flow) if phase == 'scanning' else reading(read_flow)
    before = read_flow.reader.start.call_count
    activity.callKeyEvent(key)
    assert activity.state == phase
    assert read_flow.reader.start.call_count == before
    read_flow.scanner.scan_all_asynchronous.assert_called_once_with()


@pytest.mark.parametrize('phase', ['scanning', 'reading', 'read_success', 'read_failed'])
def test_power_exits_including_busy_and_toast_states(read_flow, phase):
    activity = start(read_flow) if phase == 'scanning' else reading(read_flow)
    if phase in ('read_success', 'read_failed'):
        read_flow.read_result(activity, {'success': phase == 'read_success', 'return': -2})
    activity.callKeyEvent(KEY_PWR)
    assert actstack.get_current_activity() is None
    if phase in ('scanning', 'reading'):
        read_flow.stop_pm3.assert_called_once_with(wait=False)
