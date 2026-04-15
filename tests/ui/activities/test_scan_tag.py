"""Tests for ScanActivity and ConsolePrinterActivity.

Validates against the reimplemented behavior in src/lib/activity_main.py.

Ground truth (from reimplementation):
    ScanActivity:
    - Title: "Scan Tag" (resources key: scan_tag)
    - onCreate() calls _startScan() immediately — starts in STATE_SCANNING
    - There is NO idle state with a type list on initial creation
    - 6 states: idle, scanning, found, not_found, wrong_type, multi_tags
    - SCANNING: ALL keys are ignored (key handler returns early)
    - Result states (FOUND/NOT_FOUND/WRONG_TYPE/MULTI):
        M1/M2/OK: rescan (_clearContent + _startScan)
        PWR: dismiss toast first (if visible), then finish
    - Scan cache stored on FOUND result
    - Return codes: CODE_TAG_LOST=-2, CODE_TAG_MULT=-3,
      CODE_TAG_NO=-4, CODE_TAG_TYPE_WRONG=-5, CODE_TIMEOUT=-1

    ConsolePrinterActivity:
    - onCreate uses dismissButton(keep_bindings=True) — NO title bar, NO buttons
    - Full-screen ConsoleView for monospace output
    - M1: zoom out (textfontsizedown)
    - M2: zoom in (textfontsizeup)
    - UP/DOWN: scroll ConsoleView
    - PWR: exit console (finish activity)
    - No explicit completion tracking — poll thread runs until activity finishes
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


def _create_scan(bundle=None):
    """Start a ScanActivity and return it."""
    from activity_main import ScanActivity
    act = actstack.start_activity(ScanActivity, bundle)
    return act


def _create_console(bundle=None):
    """Start a ConsolePrinterActivity and return it."""
    from activity_main import ConsolePrinterActivity
    act = actstack.start_activity(ConsolePrinterActivity, bundle)
    return act


def _make_found_result(tag_type=1, uid='2C AD C2 72'):
    """Build a scan result dict for a found tag."""
    return {
        'found': True,
        'return': 0,
        'type': tag_type,
        'data': {
            'uid': uid,
            'atqa': '00 04',
            'sak': '08',
        },
        'hasMulti': False,
    }


def _make_not_found_result():
    """Build a scan result dict for no tag found."""
    return {
        'found': False,
        'return': -1,
        'type': None,
        'hasMulti': False,
    }


def _make_wrong_type_result():
    """Build a scan result dict for wrong tag type detected.

    CODE_TAG_TYPE_WRONG = -5 (from ScanActivity constants).
    """
    return {
        'found': False,
        'return': -5,
        'type': None,
        'hasMulti': False,
    }


def _make_multi_result():
    """Build a scan result dict for multiple tags detected.

    CODE_TAG_MULT = -3 (from ScanActivity constants).
    hasMulti=True is the primary trigger.
    """
    return {
        'found': False,
        'return': -3,
        'type': None,
        'hasMulti': True,
    }


# ===============================================================
# ScanActivity — Creation & Layout
# ===============================================================

class TestScanActivityCreation:
    """ScanActivity initial state tests.

    The reimplemented ScanActivity calls _startScan() in onCreate(),
    so the activity starts directly in STATE_SCANNING with no idle
    type-list phase.
    """

    def test_title_scan_tag(self):
        """Title bar must read 'Scan Tag' (resources key: scan_tag)."""
        act = _create_scan()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Scan Tag' in texts

    def test_initial_state_scanning(self):
        """Activity starts in SCANNING state (onCreate calls _startScan)."""
        act = _create_scan()
        assert act.state == act.STATE_SCANNING

    def test_scanning_no_buttons(self):
        """SCANNING state: no M1/M2 buttons visible (dismissButton called)."""
        act = _create_scan()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Back' not in texts
        assert 'Scan' not in texts

    def test_scanning_shows_scanning_text(self):
        """SCANNING state shows 'Scanning...' message."""
        act = _create_scan()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Scanning...' in texts

    def test_directed_scan_also_scanning(self):
        """Bundle with 'tag_type' also starts in SCANNING state."""
        act = _create_scan({'tag_type': 1})
        assert act.state == act.STATE_SCANNING


# ===============================================================
# ScanActivity — States
# ===============================================================

class TestScanActivityStates:
    """ScanActivity state transition tests.

    Activity starts in SCANNING (onCreate calls _startScan with no args).
    _onScanResult transitions to the appropriate result state.
    """

    def test_scanning_state_on_create(self):
        """Activity starts in SCANNING state with 'Scanning...' message."""
        act = _create_scan()
        assert act.state == act.STATE_SCANNING
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Scanning...' in texts

    def test_found_state_transitions(self):
        """FOUND result transitions state to FOUND."""
        act = _create_scan()
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_FOUND

    def test_not_found_state_shows_toast(self):
        """NOT_FOUND state shows 'No tag found' toast."""
        act = _create_scan()
        act._onScanResult(_make_not_found_result())
        assert act.state == act.STATE_NOT_FOUND
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'No tag found' in texts

    def test_wrong_type_state_shows_toast(self):
        """WRONG_TYPE state shows the multiline wrong-type toast."""
        act = _create_scan()
        act._onScanResult(_make_wrong_type_result())
        assert act.state == act.STATE_WRONG_TYPE
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # The toast is multiline: "No tag found ", "Or", " Wrong type found!"
        assert any('No tag found' in t for t in texts)
        assert any('Wrong type found!' in t for t in texts)

    def test_multi_tags_state_shows_toast(self):
        """MULTI state shows 'Multiple tags detected!' toast."""
        act = _create_scan()
        act._onScanResult(_make_multi_result())
        assert act.state == act.STATE_MULTI
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Multiple tags detected!' in texts


# ===============================================================
# ScanActivity — Key Events
# ===============================================================

class TestScanActivityKeyEvents:
    """ScanActivity key event handling tests.

    Key behavior from reimplementation:
    - SCANNING: ALL keys return early (ignored)
    - Result states: M1/M2/OK → rescan, PWR → dismiss toast then finish
    """

    def test_scanning_all_keys_ignored(self):
        """In SCANNING, ALL keys are ignored (handler returns early)."""
        act = _create_scan()
        assert act.state == act.STATE_SCANNING
        for key in (KEY_M1, KEY_M2, KEY_OK, KEY_UP, KEY_DOWN, KEY_PWR):
            act.onKeyEvent(key)
        # Still scanning — none of the keys had any effect
        assert act.state == act.STATE_SCANNING

    def test_found_m1_rescans(self):
        """In FOUND, M1 triggers a rescan."""
        act = _create_scan()
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_FOUND
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_found_m2_rescans(self):
        """In FOUND, M2 triggers a rescan."""
        act = _create_scan()
        act._onScanResult(_make_found_result())
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_found_pwr_dismisses_toast_then_exits(self):
        """In FOUND, first PWR dismisses toast, second PWR exits.

        Must also clear busy state (set by _startScan in onCreate)
        since _onScanResult alone does not call setidle(). In real
        usage, onScanFinish calls setidle() before _onScanResult.
        """
        act = _create_scan()
        # Simulate full scan completion: clear scanning/busy flags
        act._is_scanning = False
        act.setidle()
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_FOUND
        # First PWR: _handlePWR dismisses the visible toast
        act.onKeyEvent(KEY_PWR)
        assert not act.life.destroyed
        # Second PWR: toast gone, so finish() is called
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_not_found_m1_rescans(self):
        """In NOT_FOUND, M1 triggers a rescan."""
        act = _create_scan()
        act._onScanResult(_make_not_found_result())
        assert act.state == act.STATE_NOT_FOUND
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_not_found_m2_rescans(self):
        """In NOT_FOUND, M2 triggers a rescan."""
        act = _create_scan()
        act._onScanResult(_make_not_found_result())
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_wrong_type_m1_rescans(self):
        """In WRONG_TYPE, M1 triggers a rescan."""
        act = _create_scan()
        act._onScanResult(_make_wrong_type_result())
        assert act.state == act.STATE_WRONG_TYPE
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_multi_m2_rescans(self):
        """In MULTI, M2 triggers a rescan."""
        act = _create_scan()
        act._onScanResult(_make_multi_result())
        assert act.state == act.STATE_MULTI
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING


# ===============================================================
# ScanActivity — Toasts (exact text match)
# ===============================================================

class TestScanActivityToasts:
    """ScanActivity toast message exact text verification."""

    def test_toast_tag_found(self):
        """Found toast must show exact text 'Tag Found'."""
        act = _create_scan()
        act._onScanResult(_make_found_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Tag Found' in texts

    def test_toast_no_tag_found(self):
        """Not-found toast must show exact text 'No tag found'."""
        act = _create_scan()
        act._onScanResult(_make_not_found_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'No tag found' in texts

    def test_toast_wrong_type(self):
        """Wrong-type toast shows multiline text from resources.
        Resource key no_tag_found2 = 'No tag found \\nOr\\n Wrong type found!'
        The toast renders each line separately.
        """
        act = _create_scan()
        act._onScanResult(_make_wrong_type_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Multiline toast renders each line as separate text item
        assert any('No tag found' in t for t in texts)
        assert any('Or' in t for t in texts)
        assert any('Wrong type found!' in t for t in texts)

    def test_toast_multi_tags(self):
        """Multi-tags toast must show exact text 'Multiple tags detected!'."""
        act = _create_scan()
        act._onScanResult(_make_multi_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Multiple tags detected!' in texts


# ===============================================================
# ScanActivity — Middleware & Cache
# ===============================================================

class TestScanActivityMiddleware:
    """ScanActivity middleware integration and scan cache tests.

    _startScan() takes no arguments (scans all types).
    onCreate() already calls _startScan(), so activity starts scanning.
    """

    def test_starts_in_scanning_state(self):
        """onCreate calls _startScan — state is SCANNING, _is_scanning True."""
        act = _create_scan()
        assert act.state == act.STATE_SCANNING
        assert act._is_scanning is True

    def test_scan_result_found_transitions_state(self):
        """Found result transitions state to FOUND."""
        act = _create_scan()
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_FOUND

    def test_scan_result_not_found_transitions(self):
        """Not-found result transitions state to NOT_FOUND."""
        act = _create_scan()
        act._onScanResult(_make_not_found_result())
        assert act.state == act.STATE_NOT_FOUND

    def test_scan_result_wrong_type_transitions(self):
        """Wrong-type result transitions to WRONG_TYPE."""
        act = _create_scan()
        act._onScanResult(_make_wrong_type_result())
        assert act.state == act.STATE_WRONG_TYPE

    def test_scan_result_multi_transitions(self):
        """Multi-tag result transitions to MULTI."""
        act = _create_scan()
        act._onScanResult(_make_multi_result())
        assert act.state == act.STATE_MULTI

    def test_scan_cache_stored(self):
        """Scan cache is stored on FOUND result."""
        act = _create_scan()
        result = _make_found_result()
        act._onScanResult(result)
        cache = act.getScanCache()
        assert cache is not None
        assert cache['found'] is True
        assert cache['data']['uid'] == '2C AD C2 72'

    def test_scan_cache_not_stored_on_not_found(self):
        """Scan cache is NOT updated on NOT_FOUND result."""
        act = _create_scan()
        act._onScanResult(_make_not_found_result())
        assert act.getScanCache() is None

    def test_canidle_false_when_scanning(self):
        """canidle() returns False during scan (activity starts scanning)."""
        act = _create_scan()
        assert act.canidle() is False

    def test_canidle_true_after_cancel(self):
        """canidle() returns True after _cancelScan clears scanning flag."""
        act = _create_scan()
        assert act.canidle() is False  # scanning in progress
        act._cancelScan()
        assert act.canidle() is True

    def test_cancel_scan_resets_scanning_flag(self):
        """_cancelScan sets _is_scanning to False."""
        act = _create_scan()
        assert act._is_scanning is True
        act._cancelScan()
        assert act._is_scanning is False


# ===============================================================
# ScanActivity — Return codes
# ===============================================================

class TestScanActivityReturnCodes:
    """Verify return code to state mapping.

    Constants from ScanActivity:
        CODE_TIMEOUT = -1
        CODE_TAG_LOST = -2
        CODE_TAG_MULT = -3
        CODE_TAG_NO = -4
        CODE_TAG_TYPE_WRONG = -5
    """

    def test_code_tag_lost_maps_to_not_found(self):
        """CODE_TAG_LOST (-2) maps to NOT_FOUND state."""
        act = _create_scan()
        act._onScanResult({
            'found': False,
            'return': -2,
            'hasMulti': False,
        })
        assert act.state == act.STATE_NOT_FOUND

    def test_code_timeout_maps_to_not_found(self):
        """CODE_TIMEOUT (-1) maps to NOT_FOUND state."""
        act = _create_scan()
        act._onScanResult({
            'found': False,
            'return': -1,
            'hasMulti': False,
        })
        assert act.state == act.STATE_NOT_FOUND

    def test_code_tag_mult_maps_to_multi(self):
        """CODE_TAG_MULT (-3) maps to MULTI state."""
        act = _create_scan()
        act._onScanResult({
            'found': False,
            'return': -3,
            'hasMulti': True,
        })
        assert act.state == act.STATE_MULTI

    def test_code_tag_mult_without_hasMulti_maps_to_multi(self):
        """CODE_TAG_MULT (-3) without hasMulti still maps to MULTI state.

        _onScanResult checks: has_multi OR ret_code == CODE_TAG_MULT.
        """
        act = _create_scan()
        act._onScanResult({
            'found': False,
            'return': -3,
            'hasMulti': False,
        })
        assert act.state == act.STATE_MULTI

    def test_code_tag_type_wrong_maps_to_wrong_type(self):
        """CODE_TAG_TYPE_WRONG (-5) maps to WRONG_TYPE state."""
        act = _create_scan()
        act._onScanResult({
            'found': False,
            'return': -5,
            'hasMulti': False,
        })
        assert act.state == act.STATE_WRONG_TYPE

    def test_code_tag_no_maps_to_not_found(self):
        """CODE_TAG_NO (-4) maps to NOT_FOUND state."""
        act = _create_scan()
        act._onScanResult({
            'found': False,
            'return': -4,
            'hasMulti': False,
        })
        assert act.state == act.STATE_NOT_FOUND

    def test_none_result_maps_to_not_found(self):
        """None result maps to NOT_FOUND state."""
        act = _create_scan()
        act._onScanResult(None)
        assert act.state == act.STATE_NOT_FOUND


# ===============================================================
# ConsolePrinterActivity
# ===============================================================

class TestConsolePrinterActivity:
    """ConsolePrinterActivity unit tests.

    Ground truth (from reimplementation):
    - onCreate uses dismissButton(keep_bindings=True) — no visible title/buttons
    - Full-screen ConsoleView for monospace output
    - M1: zoom out, M2: zoom in, UP/DOWN: scroll, PWR: exit
    - No explicit completion tracking or is_complete/is_running attributes
    """

    def test_no_title_shown(self):
        """No title text on canvas (dismissButton hides title bar)."""
        act = _create_console()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Full-screen console: no title bar text visible
        assert 'Console' not in texts

    def test_no_buttons_shown(self):
        """No button text on canvas (dismissButton hides button bar)."""
        act = _create_console()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Cancel' not in texts
        assert 'OK' not in texts

    def test_console_view_created(self):
        """ConsoleView widget is created on canvas."""
        act = _create_console()
        assert hasattr(act, '_console')
        assert act._console is not None

    def test_console_add_lines(self):
        """addLine adds text to the ConsoleView."""
        act = _create_console()
        act._console.addLine('hf 14a info')
        act._console.addLine('[+] UID: AA BB CC DD')
        assert act._console.getLineCount() == 2

    def test_console_add_text_multiline(self):
        """addText splits on newlines and adds all lines."""
        act = _create_console()
        act._console.addText('line1\nline2\nline3')
        assert act._console.getLineCount() == 3

    def test_m1_zooms_out(self):
        """M1 key zooms out (textfontsizedown), does NOT finish activity."""
        act = _create_console()
        act.onKeyEvent(KEY_M1)
        assert not act.life.destroyed

    def test_m2_zooms_in(self):
        """M2 key zooms in (textfontsizeup), does NOT finish activity."""
        act = _create_console()
        act.onKeyEvent(KEY_M2)
        assert not act.life.destroyed

    def test_pwr_finishes(self):
        """PWR key exits the console activity."""
        act = _create_console()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_scroll_up_down(self):
        """UP/DOWN keys scroll the ConsoleView."""
        act = _create_console()
        # Add many lines to make scrolling possible
        for i in range(30):
            act._console.addLine(f'Line {i}')
        # Should not crash
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_UP)
        # Verify ConsoleView still functional
        assert act._console.getLineCount() == 30

    def test_ok_does_not_finish(self):
        """OK key has no handler in console — does not finish."""
        act = _create_console()
        act.onKeyEvent(KEY_OK)
        assert not act.life.destroyed
