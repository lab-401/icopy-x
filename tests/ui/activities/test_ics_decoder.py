import base64
import json
from pathlib import Path

import pytest

import actstack
import ics_credentials
import ics_decoder
from _constants import BTN_BAR_Y0, KEY_DOWN, KEY_LEFT, KEY_M1, KEY_M2, KEY_OK, KEY_PWR, KEY_RIGHT, KEY_UP
from activity_main import ICSDecoderActivity
from lib.actmain import MainActivity
from tests.ui.conftest import MockCanvas


class LayerCanvas(MockCanvas):
    def tag_lower(self, tag_or_id, below=None):
        lowered = set(self._resolve_ids(tag_or_id))
        self._items = {
            **{key: value for key, value in self._items.items() if key in lowered},
            **{key: value for key, value in self._items.items() if key not in lowered},
        }


class MeasuredCanvas(MockCanvas):
    def bbox(self, *args):
        if len(args) == 1 and self.type(args[0]) == 'text':
            x, y = self.coords(args[0])
            return x, y, x + 8 * len(self.itemcget(args[0], 'text')), y + 18
        return super().bbox(*args)


def assert_all_info_scroll_positions(activity):
    view = activity._info_view
    canvas = activity.getCanvas()
    left, top, right, bottom = view._clip_rect
    assert (left, top, right, bottom) == (0, 40, 240, 192)
    assert bottom < BTN_BAR_Y0
    assert view._bottom_padding >= view._line_height
    assert view._content_bottom <= bottom - view._line_height
    maximum = max(0, len(view._lines) - view._max_visible)
    reached = set()
    for offset in range(maximum + 1):
        view._scroll_offset = offset
        view._redraw()
        rows = canvas.find_withtag(view._tag_line)
        assert len(rows) == min(view._max_visible, len(view._lines) - offset)
        for row in rows:
            bounds = canvas.bbox(row)
            assert top <= bounds[1] < bounds[3] <= view._content_bottom
            assert bounds[3] < bottom < BTN_BAR_Y0
            reached.add(canvas.itemcget(row, 'text'))
    assert set(view._lines) <= reached
    if view._lines:
        assert view._lines[-1] == canvas.itemcget(rows[-1], 'text')
        assert canvas.bbox(rows[-1])[3] + view._bottom_padding <= bottom


@pytest.fixture(autouse=True)
def activity_stack():
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


@pytest.fixture
def store(tmp_path, monkeypatch):
    saved = ics_credentials.SavedCredentials(str(tmp_path / 'credentials'))
    monkeypatch.setattr(ics_credentials, 'SavedCredentials', lambda: saved)
    return saved


def captured():
    frame = ics_decoder.calculate_wiegand26_parity(165, 1551)
    pacs = '06' + (frame << 6).to_bytes(4, 'big').hex().upper()
    text = ('$A_CARD_START$\r\nBit#:26\r\nPACS#:{}\r\n'
            'Blk7#:1122334455667788\r\n$A_CARD_STOP$\r\n').format(pacs)
    return ics_decoder.parse_block(text)


def validated_capture():
    frame = ics_decoder.calculate_wiegand26_parity(165, 1551)
    return ics_decoder.parse_block(
        '$A_CARD_START$\nBit#:26\nFC#:165\nID#:1551\nwiedata#:{}\n$A_CARD_STOP$'.format(
            format(frame, '026b'))
    )


def captured_lines():
    return [line + b'\r\n' for line in captured()['raw_response_text'].encode().splitlines()]


class ScriptedSerial:
    is_open = True

    def __init__(self, transactions):
        self.transactions = iter(transactions)
        self.lines = iter(())
        self.commands = []

    def write(self, command):
        assert command == b'RD\r\n'
        self.commands.append(command)
        self.lines = iter(next(self.transactions))

    def readline(self):
        return next(self.lines, b'')

    def close(self):
        self.is_open = False


def start():
    return actstack.start_activity(ICSDecoderActivity)


def test_h10301_parses_known_identity_and_keeps_source():
    result = captured()
    assert result['status'] == 'decoded'
    assert result['format'] == 'H10301 (26-bit)'
    assert (result['fc'], result['id']) == (165, 1551)
    assert result['bit_length'] == 26
    assert base64.b64decode(result['raw_response_b64']).decode() == result['raw_response_text']
    assert result['derived_legacy']['blk7'] == '1122334455667788'
    assert result['raw_fields']['blk7'] == '1122334455667788'


def test_write_eligibility_requires_validated_wiegand_or_decoder_reported_blk7():
    direct = validated_capture()
    assert ics_credentials.validated_h10301(direct)
    assert ics_credentials.can_write(direct)
    fallback = captured()
    assert fallback['status'] == 'decoded'
    assert not ics_credentials.validated_h10301(fallback)
    assert ics_credentials.legacy_block(fallback) == '1122334455667788'
    assert ics_credentials.can_write(fallback)
    without_legacy = dict(fallback)
    without_legacy.pop('derived_legacy')
    without_legacy.pop('blk7')
    assert not ics_credentials.can_write(without_legacy)
    forged = dict(direct, raw_fields={'fc': '165', 'id': '1551'})
    assert not ics_credentials.can_write(forged)
    unsupported = dict(direct, status='unsupported')
    assert not ics_credentials.can_write(unsupported)
    changed_source = dict(direct, raw_response_text='changed')
    assert not ics_credentials.can_write(changed_source)
    changed_identity = dict(direct, fc=12)
    assert not ics_credentials.can_write(changed_identity)
    arbitrary_block = dict(fallback, derived_legacy={'blk7': '1122334455667788'},
                           raw_fields={'blk7': '1122334455667788'})
    assert ics_credentials.legacy_block(arbitrary_block) is None
    assert not ics_credentials.can_write(arbitrary_block)
    changed_legacy = dict(fallback, derived_legacy={'blk7': '1122334455667788',
                                                    'source': 'decoder_reported'},
                          raw_response_text='changed')
    assert not ics_credentials.can_write(changed_legacy)


def test_write_result_only_offers_verify_after_success(store):
    activity = start()
    activity._source_data = captured()
    activity._write_blocked_reason = None
    activity._verify_success = None
    activity._last_write_ok = False
    activity._render_result_state()
    assert 'verify' not in activity._menu_actions
    assert activity._menu_actions == ['write_again', 'back']
    activity._last_write_ok = True
    activity._render_result_state()
    assert activity._menu_actions == ['verify', 'write_again', 'back']


@pytest.mark.parametrize('origin', ['decoded', 'saved_actions'])
def test_write_again_back_preserves_original_entry_context(store, monkeypatch, origin):
    activity = start()
    activity._source_data = captured()
    if origin == 'saved_actions':
        activity._selected_record = store.save(captured(), 'Synthetic saved')
        activity._show_saved_actions()
        expected = activity.STATE_SAVED_ACTIONS
    else:
        activity._show_decoded()
        expected = activity.STATE_DECODED
    monkeypatch.setattr(activity, '_start_target_poll', lambda: None)
    activity._start_write()
    assert activity._write_origin == expected
    activity._last_write_ok = True
    activity._write_blocked_reason = None
    activity._verify_success = None
    activity._render_result_state()
    activity._menu.setSelection(activity._menu_actions.index('write_again'))
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_WAIT_BLANK
    assert activity._write_origin == expected
    activity.onKeyEvent(KEY_M1)
    assert activity._state == expected


def test_long_format_keeps_sio_without_inventing_identity_or_legacy():
    text = ('$A_CARD_START$\nBit#:56\nSIO#:061B7D0040\n'
            'FC#:0\nID#:0\nBlk7#:0000000000000000\n$A_CARD_STOP$')
    result = ics_decoder.parse_block(text)
    assert result['status'] == 'unsupported'
    assert result['format'] == 'Unknown/Unsupported'
    assert result['bit_length'] == 56
    assert result['sio_pacs'] == '061B7D0040'
    assert result['reported_fc'] == '0'
    assert 'fc' not in result and 'id' not in result and 'blk7' not in result
    assert base64.b64decode(result['raw_response_b64']).decode() == text
    assert not ics_credentials.can_write(result)


def test_binary_and_malformed_raw_responses_survive():
    raw = b'$A_CARD_START$\nBit#:56\nSIO#:\xff\x00\n$A_CARD_STOP$'
    result = ics_decoder.parse_block(raw.decode('utf-8', errors='replace'), raw)
    assert result['status'] == 'unsupported'
    assert base64.b64decode(result['raw_response_b64']) == raw
    malformed = ics_decoder.parse_block('OK\n$A_CARD_START$\nSIO#:AABB')
    assert malformed['status'] == 'malformed'
    assert malformed['raw_response_text'].endswith('AABB')


def test_read_card_distinguishes_no_card_from_unsupported_capture():
    class Serial:
        is_open = True

        def __init__(self, lines):
            self.lines = iter(lines)

        def write(self, command):
            assert command == b'RD\r\n'

        def readline(self):
            return next(self.lines, b'')

    assert ics_decoder.read_card(Serial([b'OK\r\n', b'??\r\n'])) is None
    result = ics_decoder.read_card(Serial([
        b'$A_CARD_START$\r\n', b'Bit#:56\r\n', b'SIO#:AABB\r\n', b'$A_CARD_STOP$\r\n',
    ]))
    assert result['status'] == 'unsupported'
    assert result['sio_pacs'] == 'AABB'


@pytest.mark.parametrize('status', [b'\x00OK\r\n', b'\x00??\r\n'])
def test_status_only_reply_is_not_a_malformed_credential(status):
    serial = ScriptedSerial([[status]])
    assert ics_decoder.read_card(serial) is None
    assert serial.commands == [b'RD\r\n']


def test_credential_present_before_read_decodes_after_status_reply():
    serial = ScriptedSerial([[b'\x00??\r\n'] + captured_lines()])
    result = ics_decoder.read_card(serial)
    assert result['status'] == 'decoded'
    assert (result['fc'], result['id']) == (165, 1551)


def test_credential_presented_after_read_begins_decodes_on_retry():
    serial = ScriptedSerial([[b'\x00??\r\n'], [b'\x00OK\r\n'] + captured_lines()])
    assert ics_decoder.read_card(serial) is None
    result = ics_decoder.read_card(serial)
    assert result['status'] == 'decoded'
    assert (result['fc'], result['id']) == (165, 1551)
    assert len(serial.commands) == 2


def test_orphan_stop_does_not_preempt_valid_credential_frame():
    serial = ScriptedSerial([[b'\x00$A_CARD_STOP$\r\n', b'\x00OK\r\n'] + captured_lines()])
    result = ics_decoder.read_card(serial)
    assert result['status'] == 'decoded'
    assert (result['fc'], result['id']) == (165, 1551)


def test_incomplete_credential_frame_remains_malformed():
    serial = ScriptedSerial([[b'\x00OK\r\n', b'$A_CARD_START$\r\n', b'Bit#:26\r\n']])
    result = ics_decoder.read_card(serial)
    assert result['status'] == 'malformed'
    assert '$A_CARD_START$' in result['raw_response_text']


def test_embedded_or_nested_markers_do_not_complete_a_credential():
    serial = ScriptedSerial([[
        b'$A_CARD_START$\r\n', b'SIO#:$A_CARD_STOP$\r\n',
        b'$A_CARD_START$\r\n', b'Bit#:26\r\n', b'$A_CARD_STOP$\r\n',
    ]])
    result = ics_decoder.read_card(serial)
    assert result['status'] == 'malformed'
    assert not ics_credentials.can_write(result)


def test_framed_unsupported_credential_remains_raw():
    serial = ScriptedSerial([[
        b'\x00OK\r\n', b'$A_CARD_START$\r\n', b'Bit#:56\r\n',
        b'SIO#:AABB\r\n', b'$A_CARD_STOP$\r\n',
    ]])
    result = ics_decoder.read_card(serial)
    assert result['status'] == 'unsupported'
    assert result['sio_pacs'] == 'AABB'
    assert base64.b64decode(result['raw_response_b64']).startswith(b'\x00OK')


def test_save_reload_preserves_full_capture_and_duplicate_identity(store):
    capture = captured()
    first = store.save(capture, 'Front gate')
    second = store.save(capture, 'Spare')
    assert first['id'] != second['id']
    assert first['source']['sio_pacs'] == capture['sio_pacs']
    assert first['source']['raw_response_b64'] == capture['raw_response_b64']
    assert first['decoded']['fc'] == 165
    assert first['derived_legacy']['blk7'] == '1122334455667788'
    reloaded = type(store)(store.directory).all()
    assert {record['id'] for record in reloaded} == {first['id'], second['id']}
    assert all(record['capture'] == capture for record in reloaded)


def test_unsupported_capture_persists_without_write_data(store):
    capture = ics_decoder.parse_block('$A_CARD_START$\nBit#:56\nSIO#:AABB\n$A_CARD_STOP$')
    record = store.save(capture, 'Long format')
    assert record['decoded']['format'] == 'Unknown/Unsupported'
    assert record['source']['sio_pacs'] == 'AABB'
    assert not ics_credentials.can_write(record['capture'])


def test_unsupported_live_and_saved_capture_have_no_write_action(store):
    capture = ics_decoder.parse_block(
        '$A_CARD_START$\nBit#:56\nSIO_CONTAINER#:85050102030405\n$A_CARD_STOP$'
    )
    activity = start()
    activity._source_data = capture
    activity._show_decoded()
    assert 'write' not in activity._menu_actions
    record = store.save(capture, 'Raw capture')
    activity._selected_record = record
    activity._show_saved_actions()
    assert 'write' not in activity._menu_actions


def test_malformed_saved_file_does_not_hide_valid_credentials(store):
    valid = store.save(captured(), 'Office')
    (Path(store.directory) / 'malformed.json').write_text('[]')
    assert [record['id'] for record in store.all()] == [valid['id']]


def test_decode_and_details_never_start_target_poll(store, monkeypatch):
    activity = start()
    assert activity._state == activity.STATE_HOME
    calls = []
    monkeypatch.setattr(activity, '_start_target_poll', lambda: calls.append('poll'))
    activity._source_data = captured()
    activity._show_decoded()
    assert activity._state == activity.STATE_DECODED and calls == []
    original = json.dumps(activity._source_data, sort_keys=True)
    activity._menu.setSelection(2)
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_DETAILS
    assert json.dumps(activity._source_data, sort_keys=True) == original
    activity.onKeyEvent(KEY_M1)
    assert activity._state == activity.STATE_DECODED and calls == []


def test_live_read_callback_stops_on_results_without_blank_poll(store, monkeypatch):
    activity = start()
    activity._state = activity.STATE_READING
    activity._ser = object()
    monkeypatch.setattr(ics_decoder, 'read_card', lambda serial: captured())
    calls = []
    monkeypatch.setattr(activity, '_start_target_poll', lambda: calls.append('poll'))
    activity._poll_decoder()
    assert activity._state == activity.STATE_DECODED
    assert activity._source_data['fc'] == 165
    assert calls == []


def test_incompatible_target_cannot_start_writer(store, monkeypatch):
    activity = start()
    capture = validated_capture()
    activity._source_data = capture
    activity._show_decoded()
    monkeypatch.setattr(activity, '_start_target_poll', lambda: None)
    jobs = []
    monkeypatch.setattr(activity, 'startBGTask', lambda job: jobs.append(job))
    activity._menu.setSelection(1)
    activity.onKeyEvent(KEY_OK)
    activity._target_type = activity.TARGET_HF_ICLASS
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_WAIT_BLANK and jobs == []
    activity._target_type = activity.TARGET_LF_T5577
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_WRITING and len(jobs) == 1


def test_write_selection_is_only_transition_to_blank_poll(store, monkeypatch):
    activity = start()
    activity._source_data = captured()
    activity._show_decoded()
    calls = []
    monkeypatch.setattr(activity, '_start_target_poll', lambda: calls.append('poll'))
    activity._menu.setSelection(1)
    activity.onKeyEvent(KEY_M2)
    assert activity._state == activity.STATE_WAIT_BLANK and calls == ['poll']
    activity.onKeyEvent(KEY_M1)
    assert activity._state == activity.STATE_DECODED
    assert activity._target_poll_timer is None


def test_saved_selection_does_not_write_and_delete_needs_confirmation(store, monkeypatch):
    record = store.save(captured(), 'Office')
    activity = start()
    calls = []
    monkeypatch.setattr(activity, '_start_target_poll', lambda: calls.append('poll'))
    activity._show_saved()
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_SAVED_ACTIONS and calls == []
    activity._menu.setSelection(2)
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_DELETE
    assert store.all()[0]['id'] == record['id']
    activity.onKeyEvent(KEY_M1)
    assert len(store.all()) == 1
    activity._menu.setSelection(2)
    activity.onKeyEvent(KEY_OK)
    activity.onKeyEvent(KEY_M2)
    assert store.all() == []


def test_save_name_and_back_cancel_keep_workflow_clean(store):
    activity = start()
    activity._source_data = captured()
    activity._show_decoded()
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_NAMING
    activity.onKeyEvent(KEY_M1)
    assert store.all() == []
    activity.onKeyEvent(KEY_OK)
    activity.onKeyEvent(KEY_M2)
    assert len(store.all()) == 1
    assert activity._state == activity.STATE_DECODED
    activity.onKeyEvent(KEY_PWR)
    activity.onKeyEvent(KEY_PWR)
    assert activity._state == activity.STATE_HOME


def test_read_back_ignores_late_decoder(store):
    activity = start()
    activity._state = activity.STATE_READING
    activity._ser = type('Port', (), {'close': lambda self: None})()
    activity.onKeyEvent(KEY_M1)
    assert activity._state == activity.STATE_HOME

    class LatePort:
        closed = False

        def close(self):
            self.closed = True

    late = LatePort()
    activity._on_decoder_found(late, activity._read_generation)
    assert late.closed and activity._state == activity.STATE_HOME


def test_menu_icon_is_asset_47():
    from PIL import Image
    root = Path(__file__).parents[3]
    menu = json.loads((root / 'src/screens/main_menu.json').read_text())
    assert '"label": "ICS Decoder", "icon": "47"' in json.dumps(menu)
    assert (root / 'res/img/47.png').is_file()
    with Image.open(root / 'res/img/47.png') as icon:
        assert icon.size == (20, 20)
        assert icon.mode == 'RGBA'
        assert icon.getchannel('A').getextrema() == (0, 255)
        assert icon.getbbox() == (2, 2, 18, 18)
    assert MainActivity()._getActivityClass('iclass_se') is ICSDecoderActivity


def test_landing_highlight_follows_all_rows_on_layered_canvas(store):
    actstack._canvas_factory = lambda: LayerCanvas()
    activity = start()
    canvas = activity.getCanvas()
    for target in (0, 1, 2, 3, 0):
        if target:
            activity.onKeyEvent(KEY_DOWN)
        elif activity._menu.selection() == 3:
            activity.onKeyEvent(KEY_DOWN)
        assert activity._menu.selection() == target
        background = canvas.find_withtag('_ics_bg_clear')[0]
        selected = canvas.find_withtag(activity._menu._tag_bg)
        assert len(selected) == 1
        assert list(canvas._items).index(selected[0]) > list(canvas._items).index(background)
        assert canvas.coords(selected[0])[1] == 40 + target * 40
        texts = canvas.find_withtag(activity._menu._tag_text)
        for row, item in enumerate(texts):
            assert canvas.itemcget(item, 'fill') == 'black'
    activity.onKeyEvent(KEY_UP)
    assert activity._menu.selection() == 3


def test_about_text_scrolls_vertically_and_horizontally_and_back_returns_home(store):
    actstack._canvas_factory = lambda: MeasuredCanvas()
    activity = start()
    activity._show_about()
    assert activity._info_view._lines == [
        'iCS Decoder v1.1',
        'iCLASS SE/SEOS credential decoder',
        'Contributors:',
        '@Dysonian',
        '@PhantomPlanet',
    ]
    view = activity._info_view
    assert view._lines.index('Contributors:') == view._lines.index('iCLASS SE/SEOS credential decoder') + 1
    assert '@PhantomPlanet' in view._lines[:view._max_visible]
    assert not any('Original iCS Decoder' in line or 'Nikola' in line or '56-bit supported' in line
                   for line in view._lines)
    assert_all_info_scroll_positions(activity)
    view._scroll_offset = 0
    view._redraw()
    for _ in range(20):
        activity.onKeyEvent(KEY_DOWN)
    assert view._scroll_offset == max(0, len(view._lines) - view._max_visible)
    assert view._lines[-1] in view._lines[view._scroll_offset:view._scroll_offset + view._max_visible]
    for _ in range(20):
        activity.onKeyEvent(KEY_RIGHT)
    assert view._h_offset == view._get_max_h_offset()
    for _ in range(20):
        activity.onKeyEvent(KEY_LEFT)
    assert view._h_offset == 0
    for _ in range(20):
        activity.onKeyEvent(KEY_UP)
    assert view._scroll_offset == 0
    activity.onKeyEvent(KEY_M1)
    assert activity._state == activity.STATE_HOME
    assert activity._info_view is None


def test_long_details_scroll_both_directions_without_changing_capture(store):
    actstack._canvas_factory = lambda: MeasuredCanvas()
    activity = start()
    capture = captured()
    capture['sio_pacs'] = 'AB' * 140
    capture['sio_container'] = 'CD' * 160
    capture['raw_response_text'] = 'SOURCE\n' + 'EF' * 200
    capture['raw_response_b64'] = base64.b64encode(capture['raw_response_text'].encode()).decode()
    original = json.dumps(capture, sort_keys=True)
    activity._source_data = capture
    activity._show_decoded()
    activity._show_details(activity.STATE_DECODED)
    view = activity._info_view
    assert any(capture['sio_pacs'] in line for line in view._lines)
    assert any(capture['sio_container'] in line for line in view._lines)
    assert capture['raw_response_b64'] in view._lines
    assert_all_info_scroll_positions(activity)
    view._scroll_offset = 0
    view._redraw()
    for _ in range(500):
        activity.onKeyEvent(KEY_DOWN)
        activity.onKeyEvent(KEY_RIGHT)
    assert view._scroll_offset == len(view._lines) - view._max_visible
    assert view._h_offset == view._get_max_h_offset()
    for _ in range(500):
        activity.onKeyEvent(KEY_UP)
        activity.onKeyEvent(KEY_LEFT)
    assert view._scroll_offset == 0
    assert view._h_offset == 0
    assert json.dumps(activity._source_data, sort_keys=True) == original
    activity.onKeyEvent(KEY_M1)
    assert activity._state == activity.STATE_DECODED


def test_short_information_does_not_scroll_and_result_menu_still_selects(store):
    activity = start()
    activity._show_info(activity.STATE_ABOUT, 'About', ['Short'])
    for key in (KEY_DOWN, KEY_UP, KEY_RIGHT, KEY_LEFT):
        activity.onKeyEvent(key)
    assert activity._info_view._scroll_offset == 0
    assert activity._info_view._h_offset == 0
    activity._source_data = captured()
    activity._show_decoded()
    assert activity._info_view is not None
    selection = activity._menu.selection()
    activity.onKeyEvent(KEY_RIGHT)
    assert activity._menu.selection() == selection
    activity.onKeyEvent(KEY_DOWN)
    assert activity._menu.selection() == selection + 1


def test_saved_unsupported_details_keep_full_raw_capture_scrollable(store):
    actstack._canvas_factory = lambda: MeasuredCanvas()
    source = 'EF' * 180
    capture = ics_decoder.parse_block(
        '$A_CARD_START$\nBit#:56\nSIO#:' + source + '\n$A_CARD_STOP$'
    )
    record = store.save(capture, 'Long format')
    activity = start()
    activity._show_saved()
    activity.onKeyEvent(KEY_OK)
    activity.onKeyEvent(KEY_OK)
    assert activity._state == activity.STATE_DETAILS
    assert capture['sio_pacs'] in '\n'.join(activity._info_view._lines)
    assert capture['raw_response_b64'] in activity._info_view._lines
    assert_all_info_scroll_positions(activity)
    for _ in range(200):
        activity.onKeyEvent(KEY_RIGHT)
    assert activity._info_view._h_offset == activity._info_view._get_max_h_offset()
    activity.onKeyEvent(KEY_M1)
    assert activity._state == activity.STATE_SAVED_ACTIONS
    assert store.all()[0] == record


@pytest.mark.parametrize('confirmed,actual', [
    ('hf_iclass', 'lf_t5577'),
    ('lf_t5577', 'hf_iclass'),
    ('hf_iclass', None),
    ('hf_iclass', 'unsupported'),
])
def test_final_write_recheck_rejects_changed_missing_or_unknown_target(store, monkeypatch, confirmed, actual):
    activity = start()
    activity._source_data = captured()
    activity._target_type = confirmed
    calls = []
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: actual)
    monkeypatch.setattr(ics_decoder, 'write_to_card', lambda *args: calls.append('hf'))
    monkeypatch.setattr(ics_decoder, 'write_to_t5577', lambda *args: calls.append('lf'))
    activity._do_write()
    assert calls == []
    assert activity._last_write_ok is False
    assert activity._state == activity.STATE_RESULT
    assert activity._write_blocked_reason == 'target_not_compatible'


@pytest.mark.parametrize('target', ['hf_iclass', 'lf_t5577'])
def test_final_write_recheck_rejects_unsupported_source(store, monkeypatch, target):
    activity = start()
    activity._source_data = {'format': 'Unknown/Unsupported', 'status': 'unsupported',
                             'bit_length': 56, 'fc': 165, 'id': 1551}
    activity._target_type = target
    calls = []
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: target)
    monkeypatch.setattr(ics_decoder, 'write_to_card', lambda *args: calls.append('hf'))
    monkeypatch.setattr(ics_decoder, 'write_to_t5577', lambda *args: calls.append('lf'))
    activity._do_write()
    assert calls == []
    assert activity._last_write_ok is False
    assert activity._write_blocked_reason == 'target_not_compatible'


@pytest.mark.parametrize('target,writer', [('hf_iclass', 'hf'), ('lf_t5577', 'lf')])
def test_final_write_recheck_dispatches_only_confirmed_compatible_target(store, monkeypatch, target, writer):
    activity = start()
    activity._source_data = captured() if target == 'hf_iclass' else validated_capture()
    activity._target_type = target
    calls = []
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: target)
    monkeypatch.setattr(ics_decoder, 'write_to_card', lambda *args: calls.append('hf') or True)
    monkeypatch.setattr(ics_decoder, 'write_to_t5577', lambda *args: calls.append('lf') or True)
    activity._do_write()
    assert calls == [writer]
    assert activity._last_write_ok is True
    assert activity._state == activity.STATE_RESULT


@pytest.mark.parametrize('text', [
    '$A_CARD_STOP$\nBit#:26\nFC#:12\nID#:34\n$A_CARD_START$',
    '$A_CARD_START$\nBit#:26\nFC#:12\nID#:34',
    'Bit#:26\nFC#:12\nID#:34\n$A_CARD_STOP$',
])
def test_incomplete_or_reversed_frames_preserve_raw_without_decoding(text):
    capture = ics_decoder.parse_block(text)
    assert capture['status'] == 'malformed'
    assert base64.b64decode(capture['raw_response_b64']).decode() == text
    assert 'fc' not in capture and 'id' not in capture
    assert not ics_credentials.can_write(capture)


def test_invalid_h10301_parity_is_not_decoded_or_writeable():
    invalid_frame = ics_decoder.calculate_wiegand26_parity(12, 34) ^ 1
    pacs = '06' + (invalid_frame << 6).to_bytes(4, 'big').hex()
    capture = ics_decoder.parse_block(
        '$A_CARD_START$\nBit#:26\nPACS#:' + pacs + '\n$A_CARD_STOP$'
    )
    assert capture['status'] == 'unsupported'
    assert capture['sio_pacs'] == pacs
    assert 'fc' not in capture and 'id' not in capture
    assert not ics_credentials.can_write(capture)


@pytest.mark.parametrize('fields', [
    'Bit#:26',
    'Bit#:26\nFC#:256\nID#:34',
    'Bit#:26\nFC#:12\nID#:65536',
    'Bit#:26\nFC#:0\nID#:0',
    'PACS#:0011223344',
])
def test_missing_or_out_of_range_h10301_evidence_does_not_fabricate_identity(fields):
    capture = ics_decoder.parse_block('$A_CARD_START$\n' + fields + '\n$A_CARD_STOP$')
    assert capture['format'] == 'Unknown/Unsupported'
    assert 'fc' not in capture and 'id' not in capture
    assert not ics_credentials.can_write(capture)


@pytest.mark.parametrize('field,value', [('name', None), ('name', []), ('saved_at', 1), ('saved_at', {})])
def test_corrupt_saved_metadata_does_not_hide_valid_records(store, field, value):
    valid = store.save(captured(), 'Synthetic valid')
    corrupt = store.save(captured(), 'Synthetic corrupt')
    corrupt[field] = value
    (Path(store.directory) / (corrupt['id'] + '.json')).write_text(json.dumps(corrupt))
    assert [record['id'] for record in store.all()] == [valid['id']]


@pytest.mark.parametrize('status', ['malformed', 'decoder_error'])
def test_failed_capture_cannot_write_even_with_apparently_valid_fields(status):
    capture = captured()
    capture['status'] = status
    assert ics_credentials.legacy_block(capture) is None
    assert not ics_credentials.can_write(capture)


def test_tlv_declared_length_must_match_payload():
    frame = ics_decoder.calculate_wiegand26_parity(12, 34)
    payload = bytes([6]) + (frame << 6).to_bytes(4, 'big')
    valid = bytes([0x85, len(payload)]) + payload
    assert ics_decoder.parse_sio_pacs(valid.hex(), bit_length=26)['valid']
    for malformed in (bytes([0x85, len(payload) + 1]) + payload,
                      bytes([0x85, len(payload) - 1]) + payload,
                      valid + b'\x00'):
        assert not ics_decoder.parse_sio_pacs(malformed.hex(), bit_length=26)['valid']


def test_old_decoder_detection_cannot_claim_restarted_read(store, monkeypatch):
    import threading
    jobs = []

    class DeferredThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            jobs.append((self.target, self.args))

    class Port:
        closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(threading, 'Thread', DeferredThread)
    activity = start()
    activity._start_read()
    first_generation = activity._read_generation
    activity._back()
    activity._start_read()
    assert activity._read_generation != first_generation
    assert activity._state == activity.STATE_DETECTING
    stale, current = Port(), Port()
    ports = iter([stale, current])
    monkeypatch.setattr(ics_decoder, 'detect_decoder', lambda: next(ports))
    jobs[0][0](*jobs[0][1])
    assert stale.closed
    assert activity._state == activity.STATE_DETECTING
    assert activity._ser is None
    jobs[1][0](*jobs[1][1])
    assert not current.closed
    assert activity._state == activity.STATE_READING
    assert activity._ser is current
    activity._on_decoder_found(None, first_generation)
    assert activity._ser is current
    assert activity._state == activity.STATE_READING


def test_cancel_then_retry_does_not_reuse_previous_serial_response(store, monkeypatch):
    import threading
    jobs = []

    class DeferredThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            jobs.append((self.target, self.args))

    monkeypatch.setattr(threading, 'Thread', DeferredThread)
    activity = start()
    old = ScriptedSerial([[b'\x00??\r\n'], captured_lines()])
    activity._state = activity.STATE_READING
    activity._ser = old
    monkeypatch.setattr(activity, '_start_poll', lambda: None)
    activity._poll_decoder()
    assert activity._state == activity.STATE_READING
    activity._back()
    assert not old.is_open
    activity._start_read()
    current = ScriptedSerial([[b'\x00OK\r\n'] + captured_lines()])
    activity._on_decoder_found(current, activity._read_generation)
    assert activity._ser is current
    activity._poll_decoder()
    assert activity._state == activity.STATE_DECODED
    assert (activity._source_data['fc'], activity._source_data['id']) == (165, 1551)
    assert len(old.commands) == 1
    assert len(current.commands) == 1


@pytest.mark.parametrize('bit_length', [26, 56, None])
def test_source_container_remains_raw_without_credential_provenance(bit_length):
    frame = ics_decoder.calculate_wiegand26_parity(12, 34)
    payload = bytes([6]) + (frame << 6).to_bytes(4, 'big')
    container = (bytes([0x85, len(payload)]) + payload).hex()
    bit_field = '' if bit_length is None else 'Bit#:{}\n'.format(bit_length)
    capture = ics_decoder.parse_block(
        '$A_CARD_START$\n' + bit_field + 'SIO_CONTAINER#:' + container + '\n$A_CARD_STOP$'
    )
    assert capture['status'] == 'unsupported'
    assert capture['sio_container'] == container
    assert 'fc' not in capture and 'id' not in capture
    assert not ics_credentials.can_write(capture)


def test_reported_identity_needs_matching_parity_checked_frame():
    frame = ics_decoder.calculate_wiegand26_parity(12, 34)
    prefix = '$A_CARD_START$\nBit#:26\nFC#:12\nID#:34\nwiedata#:{}\n$A_CARD_STOP$'
    valid = ics_decoder.parse_block(prefix.format(format(frame, '026b')))
    invalid = ics_decoder.parse_block(prefix.format(format(frame ^ 1, '026b')))
    assert valid['status'] == 'decoded'
    assert (valid['fc'], valid['id']) == (12, 34)
    assert invalid['status'] == 'unsupported'
    assert not ics_credentials.can_write(invalid)


@pytest.mark.parametrize('line', [b'\x00OK\r\n', b'noise\r\n'])
def test_continuous_decoder_input_is_bounded(line):
    class NoisySerial:
        is_open = True
        timeout = 1.2
        calls = 0

        def write(self, command):
            assert command == b'RD\r\n'

        def readline(self):
            self.calls += 1
            return line

    serial = NoisySerial()
    result = ics_decoder.read_card(serial)
    assert serial.calls <= 65536 // len(line) + 1
    if line.startswith(b'\x00OK'):
        assert result is None
    else:
        assert result['status'] == 'malformed'


def test_continuous_status_input_respects_serial_timeout_budget(monkeypatch):
    from types import SimpleNamespace
    ticks = iter(index / 10 for index in range(1000))
    monkeypatch.setattr(ics_decoder, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))

    class StatusSerial:
        is_open = True
        timeout = 1.2
        calls = 0

        def write(self, command):
            assert command == b'RD\r\n'

        def readline(self):
            self.calls += 1
            return b'\x00OK\r\n'

    serial = StatusSerial()
    assert ics_decoder.read_card(serial) is None
    assert 45 <= serial.calls <= 50


def test_cancelled_background_read_cannot_claim_retried_session(store, monkeypatch):
    import threading
    jobs = []
    callbacks = []

    class DeferredThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            jobs.append((self.target, self.args))

    class Root:
        def after(self, delay, callback, *args):
            callbacks.append((callback, args))

    monkeypatch.setattr(threading, 'Thread', DeferredThread)
    activity = start()
    monkeypatch.setattr(actstack, '_root', Root())
    old = ScriptedSerial([[b'\x00OK\r\n'] + captured_lines()])
    activity._state = activity.STATE_READING
    activity._ser = old
    activity._poll_decoder()
    assert activity._read_in_flight
    activity._back()
    assert not old.is_open

    current = ScriptedSerial([[b'\x00OK\r\n'] + captured_lines()])
    activity._ser = current
    activity._state = activity.STATE_READING
    activity._poll_decoder()
    assert len(jobs) == 2
    jobs[0][0](*jobs[0][1])
    stale_callback, stale_args = callbacks.pop(0)
    stale_callback(*stale_args)
    assert activity._state == activity.STATE_READING
    assert activity._source_data is None
    jobs[1][0](*jobs[1][1])
    current_callback, current_args = callbacks.pop(0)
    current_callback(*current_args)
    assert activity._state == activity.STATE_DECODED
    assert activity._source_data['fc'] == 165
