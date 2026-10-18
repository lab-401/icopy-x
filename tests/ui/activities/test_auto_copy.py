"""Auto Copy's real scan/read callbacks and handoff to the write activity.

The historical tests recreated removed _onReadComplete/_onWriteComplete and
_isLFTag methods in conftest. They also forced write/verify states that the
normal Auto Copy flow no longer enters. These tests follow the callback and
WarningWriteActivity handoff recorded in
Real_Hardware_Intel/trace_autocopy_mf1k_standard.txt. Write/verify outcomes
belong to test_write_tag.py; no activity decision logic is mocked here.
"""

import pytest
import actstack
from activity_main import AutoCopyActivity, WarningM1Activity, WarningWriteActivity, WriteActivity
from _constants import KEY_M1, KEY_M2, KEY_OK, KEY_PWR, KEY_UP, KEY_DOWN


HF = {'found': True, 'return': 0, 'type': 1, 'uid': '9C750884',
      'len': 4, 'sak': '08', 'atqa': '0004'}
LF = {'found': True, 'return': 0, 'type': 8,
      'data': '1122334455', 'raw': 'FF80605028180F09'}


def start(read_flow):
    return actstack.start_activity(AutoCopyActivity)


def reading(read_flow, infos=None):
    activity = start(read_flow)
    read_flow.scan_result(activity, HF.copy() if infos is None else infos)
    assert activity.state == 'reading'
    return activity


def test_creation_starts_scan(read_flow):
    activity = start(read_flow)
    assert activity.state == 'scanning'
    assert 'Auto Copy' in activity.getCanvas().get_all_text()
    assert activity.isbusy()
    assert not activity.btn_enabled
    assert not activity.scan_found
    assert read_flow.scanner.call_resulted == activity.onScanFinish
    read_flow.scanner.scan_all_asynchronous.assert_called_once_with()


def test_partial_ultralight_uses_partial_toast_and_preserves_bundle(read_flow):
    activity = reading(read_flow, {'found': True, 'type': 2, 'uid': '04112233445566'})
    read_flow.read_result(activity, {'success': True, 'force': False, 'partial': True,
                                     'bundle': '/mnt/upan/dump/mfu/partial.bin'})
    assert activity.state == 'place_card'
    assert any('Partial data' in t for t in activity.getCanvas().get_all_text())
    assert activity._read_bundle == '/mnt/upan/dump/mfu/partial.bin'


def test_scan_waits_for_animation_and_delivers_cache_to_reader(read_flow):
    import scan
    activity = start(read_flow)
    scan.setScanCache(HF.copy())
    read_flow.scanner.call_resulted(HF.copy())
    assert activity.state == 'scanning'
    read_flow.reader.start.assert_not_called()
    activity.getCanvas().advance(250)
    assert activity.state == 'reading'
    assert activity.scan_found
    assert activity.scan_infos == HF
    assert read_flow.reader.call_reading == activity.onReading
    assert read_flow.reader.call_exception == activity._onReadException
    read_flow.reader.start.assert_called_once_with(1, {'infos': HF, 'force': False})


@pytest.mark.parametrize('result,state,message', [
    (None, 'scan_not_found', 'No tag found'),
    ({'found': False, 'return': -4, 'type': -1}, 'scan_not_found', 'No tag found'),
    ({'found': True, 'return': -3, 'type': -1}, 'scan_multi', 'Multiple tags detected!'),
    (-4, 'scan_not_found', 'No tag found'),
    ('CODE_TAG_MULT', 'scan_multi', 'Multiple tags detected!'),
])
@pytest.mark.parametrize('key', [KEY_M1, KEY_M2, KEY_OK])
def test_scan_failure_allows_rescan_but_never_read(read_flow, result, state, message, key):
    activity = start(read_flow)
    read_flow.scan_result(activity, result)
    assert activity.state == state
    assert not activity.isbusy()
    assert activity.btn_enabled
    assert message in activity.getCanvas().get_all_text()
    read_flow.reader.start.assert_not_called()
    activity.callKeyEvent(key)
    assert activity.state == 'scanning'
    assert read_flow.scanner.scan_all_asynchronous.call_count == 2


@pytest.mark.parametrize('infos,bundle', [(HF, '/mnt/upan/dump/mf1/card.bin'),
                                       (LF, {'return': 1, 'data': '1122334455'})])
@pytest.mark.parametrize('partial', [False, True])
@pytest.mark.parametrize('key', [KEY_M2, KEY_OK])
def test_success_hands_exact_bundle_to_warning_then_writer(read_flow, infos, bundle, partial, key):
    activity = reading(read_flow, infos.copy())
    read_flow.read_result(activity, {'success': True, 'return': 1,
                                     'bundle': bundle, 'force': partial})
    assert activity.state == 'place_card'
    assert activity.place and activity.btn_enabled
    assert not activity.isbusy()
    texts = activity.getCanvas().get_all_text()
    assert 'Reread' in texts and 'Write' in texts
    assert any(('Partial data' if partial else 'File saved') in text for text in texts)
    activity.callKeyEvent(key)
    warning = actstack.get_current_activity()
    assert isinstance(warning, WarningWriteActivity)
    warning.callKeyEvent(KEY_M2)
    writer = actstack.get_current_activity()
    assert isinstance(writer, WriteActivity)
    assert writer._read_bundle == bundle


@pytest.mark.parametrize('ret_code', [-2, 0, -99])
def test_failure_displays_result_then_rereads(read_flow, ret_code):
    activity = reading(read_flow)
    read_flow.read_result(activity, {'success': False, 'return': ret_code})
    assert activity.state == 'read_failed'
    assert not activity.isbusy()
    texts = activity.getCanvas().get_all_text()
    assert 'Read Failed!' in texts
    assert 'Rescan' in texts and 'Reread' in texts
    activity.callKeyEvent(KEY_M2)
    assert activity.state == 'reading'
    assert read_flow.reader.start.call_count == 2


@pytest.mark.parametrize('ret_code', [-3, -4])
def test_key_failure_opens_warning_and_force_retries(read_flow, ret_code):
    activity = reading(read_flow)
    read_flow.read_result(activity, {'success': False, 'return': ret_code})
    assert activity.state == 'read_no_key_hf'
    assert isinstance(actstack.get_current_activity(), WarningM1Activity)
    activity.onActivity({'action': 'force'})
    read_flow.reader.start.assert_called_with(1, {'infos': HF, 'force': True})
    assert activity.state == 'reading'


@pytest.mark.parametrize('infos,state', [(HF, 'read_failed'), (LF, 'scan_wrong_type')])
def test_unconfirmed_result_uses_scan_context(read_flow, infos, state):
    activity = reading(read_flow, infos.copy())
    read_flow.read_result(activity, {'success': False, 'return': -1})
    assert activity.state == state
    assert activity.btn_enabled


def test_reader_exception_reports_failure(read_flow):
    activity = reading(read_flow)
    read_flow.reader.call_exception(RuntimeError('reader disconnected'))
    activity.getCanvas().advance(250)
    assert activity.state == 'read_failed'
    assert 'Read Failed!' in activity.getCanvas().get_all_text()


def test_progress_renders_real_callback_fields(read_flow):
    activity = reading(read_flow)
    read_flow.reader.call_reading({'progress': 75, 'action': 'ChkDIC',
                                   'keyIndex': 16, 'keyCountMax': 32, 'seconds': 68})
    activity.getCanvas().advance(250)
    assert activity._progressbar.getProgress() == 75
    texts = activity.getCanvas().get_all_text()
    assert 'ChkDIC...16/32keys' in texts
    assert '01:08' in texts
    assert activity.state == 'reading'


@pytest.mark.parametrize('phase', ['scanning', 'reading'])
@pytest.mark.parametrize('key', [KEY_UP, KEY_DOWN, KEY_M1, KEY_M2, KEY_OK])
def test_busy_keys_do_not_start_another_operation(read_flow, phase, key):
    activity = start(read_flow) if phase == 'scanning' else reading(read_flow)
    before = read_flow.reader.start.call_count
    activity.callKeyEvent(key)
    assert activity.state == phase
    assert read_flow.reader.start.call_count == before
    read_flow.scanner.scan_all_asynchronous.assert_called_once_with()


@pytest.mark.parametrize('phase', ['scanning', 'reading', 'place_card', 'read_failed'])
def test_power_exits_including_busy_and_toast_states(read_flow, phase):
    activity = start(read_flow) if phase == 'scanning' else reading(read_flow)
    if phase in ('place_card', 'read_failed'):
        read_flow.read_result(activity, {'success': phase == 'place_card', 'return': -2})
    activity.callKeyEvent(KEY_PWR)
    assert actstack.get_current_activity() is None
    read_flow.stop_pm3.assert_called_once_with()


def test_success_reread_keeps_original_scan(read_flow):
    activity = reading(read_flow)
    read_flow.read_result(activity, {'success': True, 'bundle': '/mnt/upan/dump/card.bin'})
    activity.callKeyEvent(KEY_M1)
    assert activity.state == 'reading'
    assert read_flow.reader.start.call_count == 2
    read_flow.scanner.scan_all_asynchronous.assert_called_once_with()
