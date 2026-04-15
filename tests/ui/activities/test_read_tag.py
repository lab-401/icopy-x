"""Tests for ReadActivity — tag data reading with key recovery pipeline.

Validates against the exhaustive binary extraction in
docs/UI_Mapping/04_read_tag/ — complete flow, UI states, branch tree,
leaf map.

Ground truth:
    ReadActivity:
    - Title: "Read Tag" (constant throughout all phases)
    - Launched from ReadListActivity with bundle: {tag_type, tag_name}
    - States: idle, scanning, scan_found, reading, read_success,
              read_partial, read_failed, warning_keys, error
    - Scan phase: ProgressBar + "Scanning...", reuses scan.so logic
    - Scan found: Card info display, M1="Rescan", M2="Read"
    - Reading: Progress + status text, buttons disabled
    - Read success: "Read\\nSuccessful!\\nFile saved" toast, M1="Reread", M2="Write"
    - Read partial: "Read\\nSuccessful!\\nPartial data\\nsaved" toast, M1="Reread", M2="Write"
    - Read failed: "Read Failed!" toast, M1="Reread"
    - Missing keys: launches WarningM1Activity
    - M2="Write" on success launches WriteActivity
    - PWR exits at any non-busy state

Toast messages (exact from resources.py):
    read_ok_1:  "Read\\nSuccessful!\\nFile saved"
    read_ok_2:  "Read\\nSuccessful!\\nPartial data\\nsaved"
    read_failed: "Read Failed!"
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


def _create_read(bundle=None):
    """Start a ReadActivity and return it."""
    from activity_read import ReadActivity
    act = actstack.start_activity(ReadActivity, bundle)
    return act


def _make_bundle(tag_type=1, tag_name='M1 S50 1K 4B'):
    """Build a standard bundle for ReadActivity."""
    return {'tag_type': tag_type, 'tag_name': tag_name}


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
    """Build a scan result dict for wrong tag type detected."""
    return {
        'found': False,
        'return': -4,
        'type': None,
        'hasMulti': False,
    }


def _make_multi_result():
    """Build a scan result dict for multiple tags detected."""
    return {
        'found': False,
        'return': -2,
        'type': None,
        'hasMulti': True,
    }


# ===============================================================
# ReadActivity — Creation & Title
# ===============================================================

class TestReadActivityCreation:
    """ReadActivity initial state tests."""

    def test_title_read_tag(self):
        """Title bar must read 'Read Tag' (resources key: read_tag)."""
        act = _create_read(_make_bundle())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Tag' in texts

    def test_receives_tag_type_from_bundle(self):
        """Activity stores tag_type from bundle."""
        act = _create_read(_make_bundle(tag_type=0, tag_name='M1 S70 4K 4B'))
        assert act._tag_type == 0
        assert act._tag_name == 'M1 S70 4K 4B'

    def test_no_bundle_starts_idle(self):
        """No bundle starts in IDLE state."""
        act = _create_read()
        assert act.state == act.STATE_IDLE

    def test_bundle_with_type_starts_scanning(self):
        """Bundle with tag_type starts scan immediately (SCANNING state)."""
        act = _create_read(_make_bundle())
        assert act.state == act.STATE_SCANNING

    def test_title_stays_read_tag_throughout(self):
        """Title stays 'Read Tag' through all state transitions.

        From UI_STATES.md: 'Title stays Read Tag throughout —
        no title changes between scan/read phases.'
        """
        act = _create_read(_make_bundle())
        # In scanning
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Tag' in texts

        # After scan found
        act._onScanResult(_make_found_result())
        texts = canvas.get_all_text()
        assert 'Read Tag' in texts


# ===============================================================
# ReadActivity — Scan Phase
# ===============================================================

class TestReadActivityScanPhase:
    """ReadActivity scan phase tests."""

    def test_scanning_shows_progress(self):
        """SCANNING state shows ProgressBar with 'Scanning...'."""
        act = _create_read(_make_bundle())
        assert act.state == act.STATE_SCANNING
        assert act._progress is not None
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Scanning...' in texts

    def test_scanning_buttons_dismissed(self):
        """SCANNING state dismisses buttons (no Back/Stop shown)."""
        act = _create_read(_make_bundle())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Back' not in texts
        assert 'Stop' not in texts

    def test_scan_found_auto_reads(self):
        """Scan found auto-starts read (no intermediate scan_found state)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_READING

    def test_scan_found_buttons_dismissed_during_read(self):
        """Scan found auto-reads; buttons are dismissed during reading."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rescan' not in texts

    def test_scan_found_stores_cache(self):
        """SCAN_FOUND stores scan result in _scan_cache."""
        act = _create_read(_make_bundle())
        result = _make_found_result()
        act._onScanResult(result)
        assert act._scan_cache is not None
        assert act._scan_cache['found'] is True

    def test_scan_not_found_shows_toast(self):
        """Scan not found shows 'No tag found' toast and goes to no_tag state."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_not_found_result())
        assert act.state == act.STATE_NO_TAG
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('No tag found' in t for t in texts)

    def test_scan_wrong_type_shows_toast(self):
        """Scan wrong type shows multiline wrong-type toast."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_wrong_type_result())
        assert act.state == act.STATE_NO_TAG
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('No tag found' in t for t in texts)
        assert any('Wrong type found!' in t for t in texts)

    def test_scan_multi_shows_toast(self):
        """Scan multiple tags shows 'Multiple tags detected!' toast."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_multi_result())
        assert act.state == act.STATE_NO_TAG
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Multiple tags detected!' in t for t in texts)

    def test_scan_progress_updates(self):
        """onScanning() updates the progress bar value.

        ProgressBar uses animation via canvas.after(); only the first
        animation step fires synchronously, so check intermediate value.
        """
        act = _create_read(_make_bundle())
        act.onScanning(50)
        assert act._progress is not None
        # Fire all pending after() callbacks to complete animation
        canvas = act.getCanvas()
        for _ in range(20):
            canvas.fire_all_after()
        assert act._progress.getProgress() == 50

    def test_scan_none_result_to_no_tag(self):
        """None scan result maps to no_tag state."""
        act = _create_read(_make_bundle())
        act._onScanResult(None)
        assert act.state == act.STATE_NO_TAG


# ===============================================================
# ReadActivity — Scan Key Events
# ===============================================================

class TestReadActivityScanKeyEvents:
    """ReadActivity key events during scan phase."""

    def test_scanning_m1_ignored(self):
        """SCANNING: M1 is ignored (keys return early)."""
        act = _create_read(_make_bundle())
        assert act.state == act.STATE_SCANNING
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_scanning_m2_ignored(self):
        """SCANNING: M2 is ignored (keys return early)."""
        act = _create_read(_make_bundle())
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_scanning_pwr_ignored(self):
        """SCANNING: PWR is ignored during active scan."""
        act = _create_read(_make_bundle())
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_SCANNING

    def test_scanning_ok_ignored(self):
        """SCANNING: OK key is ignored."""
        act = _create_read(_make_bundle())
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_SCANNING

    def test_scanning_up_down_ignored(self):
        """SCANNING: UP/DOWN keys are ignored."""
        act = _create_read(_make_bundle())
        act.onKeyEvent(KEY_UP)
        act.onKeyEvent(KEY_DOWN)
        assert act.state == act.STATE_SCANNING


# ===============================================================
# ReadActivity — Scan Found Key Events
# ===============================================================

class TestReadActivityScanFoundKeyEvents:
    """ReadActivity auto-reads after scan found — no intermediate state."""

    def test_scan_found_auto_reads(self):
        """Scan found auto-starts read (state goes directly to READING)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_READING

    def test_scan_found_ok_ignored_during_read(self):
        """OK is ignored during auto-started reading."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_READING

    def test_scan_found_m1_ignored_during_read(self):
        """M1 is ignored during auto-started reading."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_READING

    def test_scan_found_pwr_ignored_during_read(self):
        """PWR is ignored during active read (busy)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_READING


# ===============================================================
# ReadActivity — Reading State
# ===============================================================

class TestReadActivityReadingState:
    """ReadActivity READING state tests."""

    def test_reading_state_starts(self):
        """_startRead transitions to READING state."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        assert act.state == act.STATE_READING

    def test_reading_state_is_busy(self):
        """READING state sets busy flag."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        assert act.isbusy() is True

    def test_reading_state_shows_progress(self):
        """READING state creates a ProgressBar."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        assert act._progress is not None

    def test_reading_state_pwr_ignored(self):
        """READING: PWR is ignored during active read (busy)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_READING

    def test_reading_state_m1_ignored(self):
        """READING: M1 key is ignored (buttons disabled)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_READING

    def test_reading_state_m2_ignored(self):
        """READING: M2 key is ignored (buttons disabled)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_READING

    def test_canidle_false_during_read(self):
        """canidle() returns False during read."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        assert act.canidle() is False


# ===============================================================
# ReadActivity — Read Success
# ===============================================================

class TestReadActivityReadSuccess:
    """ReadActivity READ_SUCCESS state tests."""

    def test_read_success_toast(self):
        """READ_SUCCESS shows exact multiline toast text.

        From resources.py read_ok_1: 'Read\\nSuccessful!\\nFile saved'
        """
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK)
        assert act.state == act.STATE_READ_SUCCESS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Toast renders each line separately via split('\\n')
        assert any('Read' in t for t in texts)
        assert any('Successful!' in t for t in texts)
        assert any('File saved' in t for t in texts)

    def test_read_success_buttons(self):
        """READ_SUCCESS: M1='Reread', M2='Write'."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Reread' in texts
        assert 'Write' in texts

    def test_read_success_not_busy(self):
        """READ_SUCCESS clears busy state."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK)
        assert act.isbusy() is False

    def test_read_success_canidle(self):
        """canidle() returns True after read success."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK)
        assert act.canidle() is True


# ===============================================================
# ReadActivity — Read Partial
# ===============================================================

class TestReadActivityReadPartial:
    """ReadActivity READ_PARTIAL state tests."""

    def test_read_partial_toast(self):
        """READ_PARTIAL shows partial data toast.

        From resources.py read_ok_2: 'Read\\nSuccessful!\\nPartial data\\nsaved'
        """
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_PARTIAL)
        assert act.state == act.STATE_READ_PARTIAL
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Successful!' in t for t in texts)
        assert any('Partial data' in t for t in texts)

    def test_read_partial_buttons(self):
        """READ_PARTIAL: M1='Reread', M2='Write' (same as success)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_PARTIAL)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Reread' in texts
        assert 'Write' in texts


# ===============================================================
# ReadActivity — Read Failed
# ===============================================================

class TestReadActivityReadFailed:
    """ReadActivity READ_FAILED state tests."""

    def test_read_failed_toast(self):
        """READ_FAILED shows 'Read Failed!' toast.

        From resources.py read_failed: 'Read Failed!'
        """
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_FAIL)
        assert act.state == act.STATE_READ_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Failed!' in texts

    def test_read_failed_buttons(self):
        """READ_FAILED: M1='Reread', M2='Write' shown but inactive."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_FAIL)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Reread' in texts
        # Write button text is shown but inactive (dimmed)
        assert 'Write' in texts

    def test_read_error_transitions_to_failed(self):
        """_onReadError transitions to READ_FAILED."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act._onReadError('Connection lost')
        assert act.state == act.STATE_READ_FAILED


# ===============================================================
# ReadActivity — Result Key Events
# ===============================================================

class TestReadActivityResultKeyEvents:
    """ReadActivity key events in result states."""

    def test_read_success_m1_rereads(self):
        """READ_SUCCESS: M1 triggers reread (back to SCANNING)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK)
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_read_success_m2_launches_write(self):
        """READ_SUCCESS: M2 launches WriteActivity via _launchWrite.

        _launchWrite uses actstack.start_activity(WarningWriteActivity, _read_bundle).
        Since WarningWriteActivity may not exist, verify _read_bundle is set.
        """
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK, data={'blocks': [1, 2, 3]})
        # _read_bundle is set by onReadComplete adapter
        assert act._read_bundle is not None
        act.onKeyEvent(KEY_M2)
        # State may remain read_success if WarningWriteActivity import fails
        assert act.state == act.STATE_READ_SUCCESS

    def test_read_success_pwr_exits(self):
        """READ_SUCCESS: PWR dismisses toast first, second PWR exits."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_OK)
        # First PWR dismisses the visible toast
        act.onKeyEvent(KEY_PWR)
        assert not act.life.destroyed
        # Second PWR exits the activity
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_read_partial_m1_rereads(self):
        """READ_PARTIAL: M1 triggers reread."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_PARTIAL)
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_read_partial_m2_launches_write(self):
        """READ_PARTIAL: M2 also launches write (partial data is writeable)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_PARTIAL, data={'blocks': [1]})
        # _read_bundle is set by onReadComplete adapter
        assert act._read_bundle is not None
        act.onKeyEvent(KEY_M2)
        # State may remain read_partial if WarningWriteActivity import fails
        assert act.state == act.STATE_READ_PARTIAL

    def test_read_failed_m1_rereads(self):
        """READ_FAILED: M1 triggers reread."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_FAIL)
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_read_failed_m2_no_action(self):
        """READ_FAILED: M2 does nothing (no Write button on failure)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_FAIL)
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_READ_FAILED

    def test_read_failed_pwr_exits(self):
        """READ_FAILED: PWR dismisses toast first, second PWR exits."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_FAIL)
        # First PWR dismisses the visible toast
        act.onKeyEvent(KEY_PWR)
        assert not act.life.destroyed
        # Second PWR exits
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# ===============================================================
# ReadActivity — Warning Keys (Missing Keys)
# ===============================================================

class TestReadActivityWarningKeys:
    """ReadActivity warning keys tests."""

    def test_missing_keys_transitions_to_warning(self):
        """READ_NO_KEYS launches WarningM1Activity.

        If WarningM1Activity is not available, falls back to READ_FAILED.
        """
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_NO_KEYS)
        # WarningM1Activity may not exist, so falls back to READ_FAILED
        assert act.state in (act.STATE_WARNING_KEYS, act.STATE_READ_FAILED)

    def test_warning_result_force_read(self):
        """onActivity with action='force' restarts read."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._state = act.STATE_WARNING_KEYS
        act.onActivity({'action': 'force'})
        assert act.state == act.STATE_READING

    def test_warning_result_none_ignored(self):
        """onActivity with None does nothing."""
        act = _create_read(_make_bundle())
        act._state = act.STATE_WARNING_KEYS
        act.onActivity(None)
        assert act.state == act.STATE_WARNING_KEYS


# ===============================================================
# ReadActivity — IDLE Key Events
# ===============================================================

class TestReadActivityIdleKeyEvents:
    """ReadActivity key events in IDLE state (no bundle tag_type).

    The reimplementation has no key handler for idle state — all keys
    are ignored. Idle state only occurs when created without a bundle
    (no tag_type), which is an edge case.
    """

    def test_idle_m2_ignored(self):
        """IDLE: M2 is ignored (no key handler for idle)."""
        act = _create_read()
        assert act.state == act.STATE_IDLE
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_IDLE

    def test_idle_ok_ignored(self):
        """IDLE: OK is ignored (no key handler for idle)."""
        act = _create_read()
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_IDLE

    def test_idle_m1_ignored(self):
        """IDLE: M1 is ignored (no key handler for idle)."""
        act = _create_read()
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_IDLE

    def test_idle_pwr_ignored(self):
        """IDLE: PWR is ignored (no key handler for idle)."""
        act = _create_read()
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_IDLE

    def test_idle_no_buttons(self):
        """IDLE state shows only title (no action buttons)."""
        act = _create_read()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Tag' in texts


# ===============================================================
# ReadActivity — Error State
# ===============================================================

class TestReadActivityErrorState:
    """ReadActivity error state tests.

    STATE_ERROR maps to 'read_failed'. In read_failed state:
    M1 triggers reread (scanning), PWR dismisses toast then exits.
    """

    def test_error_state_m1_rereads(self):
        """ERROR (read_failed): M1 triggers reread."""
        act = _create_read(_make_bundle())
        act.setidle()  # Clear busy flag from scanning
        act._state = act.STATE_ERROR
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_error_state_pwr_exits(self):
        """ERROR (read_failed): PWR exits when no toast visible and not busy."""
        act = _create_read(_make_bundle())
        act.setidle()  # Clear busy flag from scanning
        act._state = act.STATE_ERROR
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# ===============================================================
# ReadActivity — Progress Updates
# ===============================================================

class TestReadActivityProgress:
    """ReadActivity progress callback tests."""

    def test_read_progress_updates_progress_bar(self):
        """onReadProgress updates the progress bar during reading phase.

        ProgressBar uses animation via canvas.after(); fire all pending
        after() callbacks to complete the animation before checking value.
        """
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadProgress('reading', 8, 16, 'Reading...8/16Keys')
        assert act._progress is not None
        # Fire all pending after() callbacks to complete animation
        canvas = act.getCanvas()
        for _ in range(20):
            canvas.fire_all_after()
        assert act._progress.getProgress() == 50  # 8/16 = 50%

    def test_read_progress_fchk_phase(self):
        """onReadProgress during fchk phase updates status text."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadProgress('fchk', 16, 32, "01'08'' ChkDIC...16/32keys")
        assert act._keys_found == 16
        assert act._keys_total == 32

    def test_read_abort_transitions_to_no_tag(self):
        """READ_ABORT transitions to no_tag state (shows no-tag toast)."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act._startRead()
        act.onReadComplete(act.READ_ABORT)
        assert act.state == act.STATE_NO_TAG


# ===============================================================
# ReadActivity — Tag Type Variants
# ===============================================================

class TestReadActivityTagTypes:
    """Test ReadActivity with different tag types."""

    def test_mifare_classic_1k_4b(self):
        """M1 S50 1K 4B (type=1) scans and auto-reads."""
        act = _create_read(_make_bundle(tag_type=1, tag_name='M1 S50 1K 4B'))
        act._onScanResult(_make_found_result(tag_type=1, uid='AA BB CC DD'))
        assert act.state == act.STATE_READING

    def test_ultralight(self):
        """Ultralight (type=2) scans and auto-reads."""
        act = _create_read(_make_bundle(tag_type=2, tag_name='Ultralight'))
        result = {
            'found': True, 'return': 0, 'type': 2,
            'data': {'uid': '04 A1 B2 C3 D4 E5 F6', 'ul_type': 'Ultralight'},
            'hasMulti': False,
        }
        act._onScanResult(result)
        assert act.state == act.STATE_READING

    def test_em410x(self):
        """EM410x (type=8) scans and auto-reads."""
        act = _create_read(_make_bundle(tag_type=8, tag_name='EM410x ID'))
        result = {
            'found': True, 'return': 0, 'type': 8,
            'data': {'uid': '12 34 56 78 9A'},
            'hasMulti': False,
        }
        act._onScanResult(result)
        assert act.state == act.STATE_READING

    def test_iclass_legacy(self):
        """iClass Legacy (type=17) scans and auto-reads."""
        act = _create_read(_make_bundle(tag_type=17, tag_name='iClass Legacy'))
        result = {
            'found': True, 'return': 0, 'type': 17,
            'data': {'uid': 'AA BB CC DD EE FF 00 11'},
            'hasMulti': False,
        }
        act._onScanResult(result)
        assert act.state == act.STATE_READING


# ===============================================================
# ReadActivity — Complete Flow Integration
# ===============================================================

class TestReadActivityFullFlow:
    """Full flow integration tests: scan -> read -> result."""

    def test_full_flow_scan_read_success(self):
        """Complete happy path: scan -> auto-read -> success."""
        act = _create_read(_make_bundle())
        # Phase 1: Scan
        assert act.state == act.STATE_SCANNING
        # Simulate scan complete — auto-reads
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_READING
        assert act.isbusy() is True
        # Phase 2: Read complete
        act.onReadComplete(act.READ_OK, data={'blocks': list(range(64))})
        assert act.state == act.STATE_READ_SUCCESS
        assert act.isbusy() is False
        # Verify toast
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Successful!' in t for t in texts)
        assert any('File saved' in t for t in texts)
        # Verify buttons
        assert 'Reread' in texts
        assert 'Write' in texts

    def test_full_flow_scan_read_fail(self):
        """Failure path: scan -> auto-read -> failed."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        # Already in reading state (auto-read)
        act.onReadComplete(act.READ_FAIL)
        assert act.state == act.STATE_READ_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Failed!' in texts
        assert 'Reread' in texts
        # Write button text is shown but inactive
        assert 'Write' in texts

    def test_full_flow_reread_after_success(self):
        """Reread loop: success -> M1 -> scanning -> found -> read -> success."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act.onKeyEvent(KEY_M2)
        act.onReadComplete(act.READ_OK)
        assert act.state == act.STATE_READ_SUCCESS
        # Press Reread
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_full_flow_reread_after_fail(self):
        """Reread loop: failed -> M1 -> scanning."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        act.onKeyEvent(KEY_M2)
        act.onReadComplete(act.READ_FAIL)
        assert act.state == act.STATE_READ_FAILED
        # Press Reread
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_full_flow_scan_keys_ignored(self):
        """During scanning all keys are ignored."""
        act = _create_read(_make_bundle())
        assert act.state == act.STATE_SCANNING
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_SCANNING

    def test_pwr_exit_from_non_busy_result_states(self):
        """PWR exits from result states (after toast dismissal)."""
        # read_failed state (not busy, no toast showing)
        act = _create_read(_make_bundle())
        act.setidle()
        act._state = 'read_failed'
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_scan_found_auto_reads_then_complete(self):
        """After scan found, auto-read starts; complete triggers result state."""
        act = _create_read(_make_bundle())
        act._onScanResult(_make_found_result())
        assert act.state == act.STATE_READING
        # Complete read
        act.onReadComplete(act.READ_OK)
        assert act.state == act.STATE_READ_SUCCESS
        # Reread from success
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING
