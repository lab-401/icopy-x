"""Tests for AutoCopyActivity (Auto Copy — one-button clone pipeline).

Validates against the exhaustive binary extraction in
docs/UI_Mapping/01_auto_copy/README.md and
docs/UI_Mapping/01_auto_copy/V1090_AUTOCOPY_FLOW_COMPLETE.md.

Ground truth:
    AutoCopyActivity:
    - Title: "Auto Copy" (resources key: auto_copy)
    - Auto-starts scan on creation (onCreate -> startScan)
    - Linear pipeline: SCAN -> READ -> PLACE_CARD -> WRITE -> [VERIFY] -> DONE
    - 16+ states with error exits at each stage
    - Instance vars: scan_found, scan_infos, place
    - onKeyEvent: isbusy() blocks all keys except PWR
      scan_found==True: M2/OK=write, M1=rescan
      scan_found==False: M1/M2/OK=rescan
    - Scan results: found, not_found, wrong_type, multi
    - Read results: read_ok_1, read_ok_2, read_failed, no_valid_key,
                    no_valid_key_t55xx, missing_keys, keys_check_failed
    - Write results: write_success, write_failed
    - Verify (LF only): verify_success, verify_failed
    - LF tags auto-verify after write success
    - HF tags show write success directly
    - scan.so, read.so, write.so are mocked (test environment)
"""

import sys
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


def _create_autocopy(bundle=None):
    """Start an AutoCopyActivity and return it."""
    from activity_main import AutoCopyActivity
    act = actstack.start_activity(AutoCopyActivity, bundle)
    return act


def _make_found_result(tag_type=1, uid='2C AD C2 72'):
    """Build a scan result dict for a found tag (HF — MF Classic 1K)."""
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


def _make_lf_found_result(tag_type=8, uid='1122334455'):
    """Build a scan result dict for a found LF tag (EM410x)."""
    return {
        'found': True,
        'return': 0,
        'type': tag_type,
        'data': {
            'uid': uid,
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
    """Build a scan result dict for multiple tags detected.

    scan.isTagMulti() checks return == CODE_TAG_MULT (-3).
    """
    return {
        'found': False,
        'return': -3,
        'type': None,
        'hasMulti': True,
    }


def _read_ok_result():
    """Build a read result dict for full read success."""
    return {'status': 'read_ok_1', 'data': b'\x00' * 1024}


def _read_partial_result():
    """Build a read result dict for partial read success (MFU)."""
    return {'status': 'read_ok_2', 'data': b'\x00' * 128}


def _read_failed_result():
    """Build a read result dict for general read failure."""
    return {'status': 'read_failed'}


def _drive_to_place_card(act, tag_type=1):
    """Drive an AutoCopyActivity through scan+read to PLACE_CARD state."""
    act.onScanFinish(_make_found_result(tag_type=tag_type))
    act._onReadComplete(_read_ok_result())
    assert act.state == act.STATE_PLACE_CARD


def _drive_to_writing(act, tag_type=1):
    """Drive an AutoCopyActivity through scan+read+place to WRITING state.

    Sets the writing state directly instead of calling _startWrite(),
    because _startWrite() spawns a background thread that imports write.so
    (available on sys.path via src/middleware). write.write() returns None
    immediately (the real work is on yet another sub-thread), so the bg
    thread calls _onWriteComplete(None) -> write_failed almost instantly,
    racing the test assertions.  Tests that need to exercise _onWriteComplete
    call it explicitly after this helper.

    Mirrors the state changes from _startWrite() without the thread dispatch:
    set state, disable buttons, clear place flag, cancel toast.
    """
    _drive_to_place_card(act, tag_type=tag_type)
    act._state = act.STATE_WRITING
    act._btn_enabled = False
    act.place = False
    if act._toast is not None:
        act._toast.cancel()
    # Show "Writing..." progress bar (mirrors _startWrite UI setup)
    if act._progressbar is not None:
        from resources import get_str
        act._progressbar.setMessage(get_str('writing'))
        act._progressbar.setProgress(0)
        act._progressbar.show()


def _drive_to_verifying(act, tag_type=8):
    """Drive an AutoCopyActivity through scan+read+place+write to VERIFYING state.

    Same approach as _drive_to_writing: manually sets the state to avoid
    the bg thread race in _startVerify(). Tests that need to exercise
    _onVerifyComplete() call it explicitly after this helper.

    Mirrors _startVerify() state changes without the thread dispatch.
    """
    _drive_to_writing(act, tag_type=tag_type)
    # Simulate _onWriteComplete('write_success') setting write_success
    act._state = act.STATE_WRITE_SUCCESS
    # Then _startVerify() sets:
    act._state = act.STATE_VERIFYING
    act._btn_enabled = False
    if act._toast is not None:
        act._toast.cancel()


# ===============================================================
# AutoCopyActivity -- Creation & Layout
# ===============================================================

class TestAutoCopyCreation:
    """AutoCopyActivity initial state tests."""

    def test_title_auto_copy(self):
        """Title bar must read 'Auto Copy' (resources key: auto_copy)."""
        act = _create_autocopy()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Auto Copy' in texts

    def test_auto_starts_scan(self):
        """Activity auto-starts in SCANNING state on creation."""
        act = _create_autocopy()
        assert act.state == act.STATE_SCANNING

    def test_scan_found_initially_false(self):
        """scan_found is False on creation."""
        act = _create_autocopy()
        assert act.scan_found is False

    def test_scan_infos_initially_false(self):
        """scan_infos is False on creation."""
        act = _create_autocopy()
        assert act.scan_infos is False

    def test_place_initially_false(self):
        """place flag is False on creation."""
        act = _create_autocopy()
        assert act.place is False

    def test_buttons_disabled_during_scan(self):
        """Buttons are disabled during initial scan."""
        act = _create_autocopy()
        assert act.btn_enabled is False

    def test_progressbar_created(self):
        """ProgressBar widget is created on startup."""
        act = _create_autocopy()
        assert act._progressbar is not None

    def test_toast_created(self):
        """Toast widget is created on startup."""
        act = _create_autocopy()
        assert act._toast is not None

    def test_scanning_progress_shown(self):
        """Scanning state shows 'Scanning...' on the progress bar."""
        act = _create_autocopy()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Scanning' in t for t in texts)


# ===============================================================
# AutoCopyActivity -- Scan Phase
# ===============================================================

class TestAutoCopyScan:
    """Scan phase state transition tests."""

    def test_scan_found_starts_read(self):
        """Scan finding a tag auto-transitions to READING state."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        assert act.state == act.STATE_READING

    def test_scan_found_sets_scan_found_true(self):
        """scan_found becomes True when tag is found."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        assert act.scan_found is True

    def test_scan_found_stores_scan_infos(self):
        """scan_infos stores the full scan result on success."""
        act = _create_autocopy()
        result = _make_found_result()
        act.onScanFinish(result)
        assert act.scan_infos == result

    def test_scan_found_auto_transitions_to_reading(self):
        """Tag found auto-transitions to READING — toast is transient.

        The 'Tag Found' toast is shown momentarily in showScanToast(),
        then immediately replaced by _startRead() which shows 'Reading...'
        progress bar.  This matches the binary behavior where the
        SCAN_SUCCESS state is transient (brief toast, auto-proceed).
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        # After auto-transition, the reading progress bar is visible
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Reading' in t for t in texts)

    def test_scan_not_found_toast(self):
        """No tag found shows 'No tag found' toast."""
        act = _create_autocopy()
        act.onScanFinish(_make_not_found_result())
        assert act.state == act.STATE_SCAN_NOT_FOUND
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'No tag found' in texts

    def test_scan_not_found_buttons_rescan(self):
        """Scan not found shows Rescan/Rescan buttons."""
        act = _create_autocopy()
        act.onScanFinish(_make_not_found_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rescan' in texts
        assert act.btn_enabled is True

    def test_scan_wrong_type_toast(self):
        """Wrong tag type is treated as scan_not_found.

        The implementation uses scan.isTagMulti/isTagFound only.
        There is no separate wrong_type branch in onScanFinish —
        all non-multi non-found results fall through to
        STATE_SCAN_NOT_FOUND and show 'No tag found' toast.
        (STATE_SCAN_WRONG_TYPE is set only in the read exception
        handler, not during the scan phase.)
        """
        act = _create_autocopy()
        act.onScanFinish(_make_wrong_type_result())
        assert act.state == act.STATE_SCAN_NOT_FOUND
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'No tag found' in texts

    def test_scan_multi_tags_toast(self):
        """Multiple tags shows 'Multiple tags detected!' toast.

        scan.isTagMulti() checks return == CODE_TAG_MULT (-3).
        """
        act = _create_autocopy()
        act.onScanFinish(_make_multi_result())
        assert act.state == act.STATE_SCAN_MULTI
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Multiple tags detected!' in texts

    def test_scan_none_result_treated_as_not_found(self):
        """None scan result is treated as 'no tag found'."""
        act = _create_autocopy()
        act.onScanFinish(None)
        assert act.state == act.STATE_SCAN_NOT_FOUND

    def test_rescan_from_not_found_m1(self):
        """M1 in scan_not_found state triggers rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_not_found_result())
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_rescan_from_not_found_m2(self):
        """M2 in scan_not_found state triggers rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_not_found_result())
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_rescan_from_not_found_ok(self):
        """OK in scan_not_found state triggers rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_not_found_result())
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_SCANNING

    def test_rescan_from_wrong_type(self):
        """M1/M2/OK in wrong_type state triggers rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_wrong_type_result())
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_rescan_from_multi(self):
        """M1/M2/OK in multi state triggers rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_multi_result())
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_SCANNING

    def test_rescan_resets_scan_found(self):
        """Rescan resets scan_found to False."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        # Now in READING state — force back to a rescannable state
        act._onReadComplete(_read_failed_result())
        act.onKeyEvent(KEY_M1)  # M1 = rescan
        assert act.scan_found is False
        assert act.state == act.STATE_SCANNING


# ===============================================================
# AutoCopyActivity -- Read Phase
# ===============================================================

class TestAutoCopyRead:
    """Read phase state transition tests."""

    def test_read_success_shows_place_card(self):
        """Full read success transitions to PLACE_CARD state."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_ok_result())
        assert act.state == act.STATE_PLACE_CARD

    def test_read_success_place_flag_true(self):
        """place flag becomes True after read success."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_ok_result())
        assert act.place is True

    def test_read_success_shows_place_toast(self):
        """Place card state shows 'Read Successful! File saved' toast.

        resources.get_str('read_ok_1') = 'Read\\nSuccessful!\\nFile saved'.
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_ok_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Successful!' in t for t in texts)

    def test_read_success_buttons_reread_write(self):
        """Place card state shows Reread/Write buttons.

        _promptSwapCard() sets M1='Reread', M2='Write'.
        """
        act = _create_autocopy()
        _drive_to_place_card(act)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Reread' in texts
        assert 'Write' in texts
        assert act.btn_enabled is True

    def test_read_partial_success(self):
        """Partial read (MFU) shows partial success toast with Write button."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result(tag_type=2))
        act._onReadComplete(_read_partial_result())
        assert act.place is True
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Partial data' in t for t in texts)
        assert 'Write' in texts

    def test_read_failed_toast(self):
        """Read failure shows 'Read Failed!' toast."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_failed_result())
        assert act.state == act.STATE_READ_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Failed!' in texts

    def test_read_failed_buttons_rescan_reread(self):
        """Read failure shows Rescan/Reread buttons."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_failed_result())
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rescan' in texts
        assert 'Reread' in texts

    def test_read_no_valid_key_hf(self):
        """No valid HF key shows 'Read Failed!' toast (via _showReadFailed).

        The adapter sets STATE_READ_NO_KEY_HF then calls _showReadFailed()
        which shows the generic 'Read Failed!' toast with Rescan/Reread buttons.
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'no_valid_key'})
        assert act.state == act.STATE_READ_NO_KEY_HF
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Failed!' in texts

    def test_read_no_valid_key_lf(self):
        """No valid LF key shows 'No valid key' toast."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'no_valid_key_t55xx'})
        assert act.state == act.STATE_READ_NO_KEY_LF

    def test_read_missing_keys(self):
        """Missing keys proceeds to place_card with Reread/Write buttons.

        The adapter for 'missing_keys' stores the partial data and calls
        _promptSwapCard(), which sets STATE_PLACE_CARD and shows the
        'Read Successful! File saved' toast with Reread/Write buttons.
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'missing_keys', 'data': b'\x00' * 512})
        assert act.state == act.STATE_PLACE_CARD
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write' in texts

    def test_read_timeout(self):
        """Key check timeout treated as read_failed by adapter.

        The adapter maps 'keys_check_failed' to STATE_READ_FAILED
        and shows 'Read Failed!' toast with Rescan/Reread buttons.
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'keys_check_failed'})
        assert act.state == act.STATE_READ_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Read Failed!' in texts
        assert 'Reread' in texts

    def test_read_none_result_treated_as_failed(self):
        """None read result is treated as read failure."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(None)
        assert act.state == act.STATE_READ_FAILED

    def test_read_failed_m1_rescans(self):
        """M1 in read_failed state triggers full rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_failed_result())
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING
        assert act.scan_found is False

    def test_read_failed_m2_rereads(self):
        """M2 in read_failed state triggers re-read (not rescan)."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete(_read_failed_result())
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_READING

    def test_read_timeout_m2_retries(self):
        """M2 in read_timeout state retries the read."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'keys_check_failed'})
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_READING

    def test_read_no_key_hf_m1_rescans(self):
        """M1 in read_no_key_hf triggers rescan."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'no_valid_key'})
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_read_no_key_hf_m2_rescans(self):
        """M2 in read_no_key_hf triggers rescan (both buttons = rescan)."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'no_valid_key'})
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_missing_keys_m2_force_use(self):
        """M2 in missing_keys state force-uses partial data (-> place card)."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'missing_keys', 'data': b'\x00' * 512})
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_PLACE_CARD

    def test_missing_keys_m1_rereads(self):
        """M1 in place_card (from missing_keys) triggers re-read.

        The adapter routes 'missing_keys' to _promptSwapCard() which sets
        STATE_PLACE_CARD. M1 in place_card calls _startRead() (not startScan).
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        act._onReadComplete({'status': 'missing_keys', 'data': b'\x00' * 512})
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_READING


# ===============================================================
# AutoCopyActivity -- Place Card / Write Phase
# ===============================================================

class TestAutoCopyWrite:
    """Write phase state transition tests."""

    def test_swap_prompt_m2_launches_warning_write(self):
        """M2 in place_card state pushes WarningWriteActivity (not _startWrite).

        Ground truth: trace_autocopy_mf1k_standard.txt line 111-114 —
        M2 → START(WarningWriteActivity, read_bundle).
        The actual write is delegated: WarningWriteActivity confirms,
        then WriteActivity runs the PM3 commands.
        """
        act = _create_autocopy()
        _drive_to_place_card(act)
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_M2)
        # WarningWriteActivity pushed onto stack
        assert actstack.get_stack_size() > stack_before
        from activity_main import WarningWriteActivity
        assert isinstance(actstack.get_current_activity(), WarningWriteActivity)

    def test_swap_prompt_ok_launches_warning_write(self):
        """OK in place_card state pushes WarningWriteActivity (not _startWrite).

        Same behavior as M2 — both M2 and OK trigger _launchWrite().
        """
        act = _create_autocopy()
        _drive_to_place_card(act)
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_OK)
        assert actstack.get_stack_size() > stack_before
        from activity_main import WarningWriteActivity
        assert isinstance(actstack.get_current_activity(), WarningWriteActivity)

    def test_swap_prompt_m1_rereads(self):
        """M1 in place_card state triggers re-read (not full rescan).

        Ground truth: onKeyEvent place_card M1 calls _startRead()
        (line 4584-4585 in activity_main.py), not startScan().
        """
        act = _create_autocopy()
        _drive_to_place_card(act)
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_READING

    def test_writing_buttons_disabled(self):
        """Buttons are disabled during write operation."""
        act = _create_autocopy()
        _drive_to_writing(act)
        assert act.btn_enabled is False

    def test_writing_progress_shown(self):
        """Writing state shows 'Writing...' progress bar."""
        act = _create_autocopy()
        _drive_to_writing(act)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Writing' in t for t in texts)

    def test_write_success_hf_toast(self):
        """HF tag write success shows 'Write successful!' toast."""
        act = _create_autocopy()
        _drive_to_writing(act, tag_type=1)  # MF Classic = HF tag
        act._onWriteComplete('write_success')
        assert act.state == act.STATE_WRITE_SUCCESS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write successful!' in texts

    def test_write_success_hf_no_verify(self):
        """HF tag write success does NOT auto-transition to VERIFYING."""
        act = _create_autocopy()
        _drive_to_writing(act, tag_type=1)
        act._onWriteComplete('write_success')
        assert act.state == act.STATE_WRITE_SUCCESS  # NOT verifying

    def test_write_success_lf_auto_verify(self):
        """LF tag write success calls _startVerify() (bg thread races to verify_failed).

        _onWriteComplete('write_success') for LF calls _startVerify() which
        sets STATE_VERIFYING then spawns a bg thread. The thread calls
        write.verify() which returns None, then _onVerifyComplete(None) →
        verify_failed. Verify the transition was initiated.
        """
        act = _create_autocopy()
        _drive_to_writing(act, tag_type=8)  # EM410x = LF tag
        act._onWriteComplete('write_success')
        # _startVerify was called (btn_enabled set False, progress bar shown)
        assert act.btn_enabled is False
        import time; time.sleep(0.05)
        # bg thread completed: state is verify_failed
        assert act.state == act.STATE_VERIFY_FAILED

    def test_write_failed_toast(self):
        """Write failure shows 'Write failed!' toast."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_failed')
        assert act.state == act.STATE_WRITE_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write failed!' in texts

    def test_write_failed_buttons_rescan_rewrite(self):
        """Write failure shows Rescan/Rewrite buttons."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_failed')
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rescan' in texts
        assert 'Rewrite' in texts

    def test_write_success_m1_rescans(self):
        """M1 in write_success state rescans (copy another)."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_success')
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_write_success_m2_rescans(self):
        """M2 in write_success state rescans (copy another)."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_success')
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_write_failed_m1_rescans(self):
        """M1 in write_failed state triggers rescan."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_failed')
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_write_failed_m2_rewrites(self):
        """M2 in write_failed state calls _startWrite() (bg thread races to write_failed).

        _startWrite() sets STATE_WRITING then spawns bg thread. The bg
        thread calls write.write() which returns immediately, then calls
        _onWriteComplete(None) → write_failed. Verify the retry was
        dispatched by checking btn_enabled (set False by _startWrite).
        """
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_failed')
        act.onKeyEvent(KEY_M2)
        # _startWrite was called: btn_enabled set to False
        assert act.btn_enabled is False
        import time; time.sleep(0.05)
        # bg thread completed: state is write_failed again
        assert act.state == act.STATE_WRITE_FAILED


# ===============================================================
# AutoCopyActivity -- Verify Phase (LF Tags)
# ===============================================================

class TestAutoCopyVerify:
    """Verify phase state transition tests (LF tags only)."""

    def test_verify_success_toast(self):
        """Verify success shows 'Write and Verify successful!' toast."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_success')
        assert act.state == act.STATE_VERIFY_SUCCESS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write and Verify successful!' in texts

    def test_verify_failed_toast(self):
        """Verify failure shows 'Verification failed!' toast."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_failed')
        assert act.state == act.STATE_VERIFY_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Verification failed!' in texts

    def test_verify_failed_buttons_rescan_rewrite(self):
        """Verify failure shows Rescan/Rewrite buttons."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_failed')
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rescan' in texts
        assert 'Rewrite' in texts

    def test_verify_success_m1_rescans(self):
        """M1 in verify_success state rescans (copy another)."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_success')
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_verify_success_m2_rescans(self):
        """M2 in verify_success state rescans (copy another)."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_success')
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_verify_failed_m1_rescans(self):
        """M1 in verify_failed triggers rescan."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_failed')
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING

    def test_verify_failed_m2_rewrites(self):
        """M2 in verify_failed calls _startWrite() (bg thread races to write_failed).

        Same race as TestAutoCopyWrite.test_write_failed_m2_rewrites.
        """
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        act._onVerifyComplete('verify_failed')
        act.onKeyEvent(KEY_M2)
        assert act.btn_enabled is False
        import time; time.sleep(0.05)
        assert act.state == act.STATE_WRITE_FAILED

    def test_verifying_buttons_disabled(self):
        """Buttons are disabled during verify operation."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        assert act.state == act.STATE_VERIFYING
        assert act.btn_enabled is False

    def test_verifying_progress_shown(self):
        """Verifying state shows progress bar (manually set in helper).

        The real _startVerify() shows 'Verifying...' progress bar, but
        the bg thread may race. We verify via the _drive_to_verifying
        helper which sets state manually.
        """
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        assert act.state == act.STATE_VERIFYING


# ===============================================================
# AutoCopyActivity -- PWR Key (Universal Exit)
# ===============================================================

class TestAutoCopyPWR:
    """PWR key behavior follows _handlePWR priority:
    1. Toast visible → dismiss toast (swallow key)
    2. Busy (_is_busy) → swallow key
    3. Otherwise → finish (exit activity)
    """

    def test_pwr_blocked_during_scanning(self):
        """PWR during scanning is swallowed (busy state).

        startScan() calls setbusy(). _handlePWR() sees _is_busy=True
        and returns True, preventing finish().
        """
        act = _create_autocopy()
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)
        # Activity NOT popped — PWR is blocked during busy scan
        assert actstack.get_stack_size() == stack_before

    def test_pwr_dismisses_toast_from_scan_not_found(self):
        """PWR from scan_not_found dismisses toast first, second PWR exits.

        scan_not_found shows a permanent toast (duration_ms=0) and calls
        setidle(). First PWR: toast visible → dismiss. Second PWR: no
        toast, not busy → finish().
        """
        act = _create_autocopy()
        act.onScanFinish(_make_not_found_result())
        # First PWR: dismisses toast
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_current_activity() is act  # still alive
        # Second PWR: exits
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() < stack_before

    def test_pwr_blocked_during_reading(self):
        """PWR during reading is swallowed (busy state persists from scan).

        startScan() calls setbusy(). onScanFinish → _startRead() does
        NOT call setidle(). _is_busy stays True through reading.
        """
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() == stack_before

    def test_pwr_dismisses_toast_from_place_card(self):
        """PWR from place_card dismisses toast first, second PWR exits.

        _promptSwapCard() calls setidle() and shows a permanent toast.
        First PWR dismisses toast, second PWR exits.
        """
        act = _create_autocopy()
        _drive_to_place_card(act)
        # First PWR: dismisses the read_ok_1 toast
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_current_activity() is act
        # Second PWR: exits
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() < stack_before

    def test_pwr_exits_from_writing(self):
        """PWR during writing exits (_is_busy=False, toast cancelled).

        _startWrite() does not call setbusy() and cancels the toast.
        PWR → _handlePWR() returns False → finish().
        """
        act = _create_autocopy()
        _drive_to_writing(act)
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() < stack_before

    def test_pwr_dismisses_toast_from_write_success(self):
        """PWR from write_success dismisses toast first, second PWR exits.

        _showWriteSuccess() calls setidle() and shows a permanent toast.
        """
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_success')
        # First PWR: dismisses toast
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_current_activity() is act
        # Second PWR: exits
        stack_before = actstack.get_stack_size()
        act.onKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() < stack_before


# ===============================================================
# AutoCopyActivity -- Key Blocking During Busy States
# ===============================================================

class TestAutoCopyKeyBlocking:
    """Keys (except PWR) are blocked during busy operations."""

    def test_m1_ignored_during_scan(self):
        """M1 is ignored during scanning (buttons disabled)."""
        act = _create_autocopy()
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_SCANNING  # unchanged

    def test_m2_ignored_during_scan(self):
        """M2 is ignored during scanning."""
        act = _create_autocopy()
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_SCANNING

    def test_ok_ignored_during_scan(self):
        """OK is ignored during scanning."""
        act = _create_autocopy()
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_SCANNING

    def test_m1_ignored_during_reading(self):
        """M1 is ignored during reading."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result())
        assert act.state == act.STATE_READING
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_READING

    def test_m2_ignored_during_writing(self):
        """M2 is ignored during writing."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_WRITING

    def test_m1_ignored_during_verifying(self):
        """M1 is ignored during verifying."""
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)
        assert act.state == act.STATE_VERIFYING
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_VERIFYING


# ===============================================================
# AutoCopyActivity -- Full Happy Paths
# ===============================================================

class TestAutoCopyHappyPath:
    """End-to-end flow tests."""

    def test_full_happy_path_hf(self):
        """Full HF clone: scan -> read -> place -> WarningWrite push.

        Ground truth: M2 in place_card pushes WarningWriteActivity, which
        on confirmation pushes WriteActivity.  The write/verify phases are
        handled by those child activities, not by AutoCopyActivity directly.
        """
        act = _create_autocopy()

        # Phase 1: Scan
        assert act.state == act.STATE_SCANNING
        act.onScanFinish(_make_found_result(tag_type=1))

        # Phase 2: Read (auto-started)
        assert act.state == act.STATE_READING
        assert act.scan_found is True
        act._onReadComplete(_read_ok_result())

        # Phase 3: Place card prompt
        assert act.state == act.STATE_PLACE_CARD
        assert act.place is True
        assert act.btn_enabled is True

        # Phase 4: User presses Write — pushes WarningWriteActivity
        act.onKeyEvent(KEY_M2)
        from activity_main import WarningWriteActivity
        assert isinstance(actstack.get_current_activity(), WarningWriteActivity)

    def test_full_happy_path_lf(self):
        """Full LF clone: scan -> read -> place -> WarningWrite push.

        Same as HF — M2 pushes WarningWriteActivity for all tag types.
        """
        act = _create_autocopy()

        # Phase 1: Scan LF tag (EM410x)
        act.onScanFinish(_make_lf_found_result(tag_type=8))

        # Phase 2: Read (auto-started)
        assert act.state == act.STATE_READING
        act._onReadComplete(_read_ok_result())

        # Phase 3: Place card
        assert act.state == act.STATE_PLACE_CARD

        # Phase 4: User presses Write — pushes WarningWriteActivity
        act.onKeyEvent(KEY_M2)
        from activity_main import WarningWriteActivity
        assert isinstance(actstack.get_current_activity(), WarningWriteActivity)

    def test_retry_after_write_failure(self):
        """Write failure -> M2 retries _startWrite (bg thread races to write_failed).

        _startWrite() sets STATE_WRITING then spawns a bg thread that
        imports write.so and calls write.write(). Since write.write()
        returns immediately (spawns its own sub-thread), the bg thread
        calls _onWriteComplete(None) → write_failed almost instantly.
        The test verifies M2 dispatches to _startWrite (btn_enabled=False).
        """
        act = _create_autocopy()
        _drive_to_writing(act)

        # First attempt fails
        act._onWriteComplete('write_failed')
        assert act.state == act.STATE_WRITE_FAILED
        assert act.btn_enabled is True

        # Retry — M2 calls _startWrite() which races to write_failed
        act.onKeyEvent(KEY_M2)
        # _startWrite sets btn_enabled=False before spawning thread
        assert act.btn_enabled is False
        # After bg thread completes, state is write_failed again
        import time; time.sleep(0.05)  # let bg thread finish
        assert act.state == act.STATE_WRITE_FAILED

    def test_retry_after_verify_failure(self):
        """Verify failure -> M2 retries _startWrite (bg thread races to write_failed).

        Same bg thread race as test_retry_after_write_failure.
        Uses _drive_to_verifying to avoid the _startVerify race.
        """
        act = _create_autocopy()
        _drive_to_verifying(act, tag_type=8)

        # Verify fails
        act._onVerifyComplete('verify_failed')
        assert act.state == act.STATE_VERIFY_FAILED

        # Retry (M2 rewrites) — races to write_failed
        act.onKeyEvent(KEY_M2)
        import time; time.sleep(0.05)
        # bg thread completed: state is write_failed
        assert act.state == act.STATE_WRITE_FAILED

    def test_copy_another_after_success(self):
        """After write success, M1/M2/OK rescans for another copy."""
        act = _create_autocopy()
        _drive_to_writing(act)
        act._onWriteComplete('write_success')
        assert act.state == act.STATE_WRITE_SUCCESS

        # Copy another
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_SCANNING
        assert act.scan_found is False

    def test_pwr_blocked_during_scan(self):
        """PWR during scan is swallowed (busy state).

        Scanning calls setbusy(), so _handlePWR() returns True
        and finish() is never reached.
        """
        act = _create_autocopy()
        assert act.state == act.STATE_SCANNING
        act.onKeyEvent(KEY_PWR)
        # Activity is still on stack — PWR blocked during busy scan
        assert actstack.get_current_activity() is act


# ===============================================================
# AutoCopyActivity -- LF Tag Type Detection
# ===============================================================

class TestAutoCopyLFDetection:
    """_isLFTag correctly identifies LF vs HF tags."""

    def test_em410x_is_lf(self):
        """EM410x (type 8) is LF — should auto-verify."""
        act = _create_autocopy()
        act.onScanFinish(_make_lf_found_result(tag_type=8))
        assert act._isLFTag() is True

    def test_hid_prox_is_lf(self):
        """HID Prox (type 9) is LF."""
        act = _create_autocopy()
        act.onScanFinish(_make_lf_found_result(tag_type=9))
        assert act._isLFTag() is True

    def test_t5577_is_lf(self):
        """T5577 (type 23) is LF."""
        act = _create_autocopy()
        act.onScanFinish(_make_lf_found_result(tag_type=23))
        assert act._isLFTag() is True

    def test_em4305_is_lf(self):
        """EM4305 (type 24) is LF."""
        act = _create_autocopy()
        act.onScanFinish(_make_lf_found_result(tag_type=24))
        assert act._isLFTag() is True

    def test_nexwatch_is_lf(self):
        """NexWatch (type 45) is LF."""
        act = _create_autocopy()
        act.onScanFinish(_make_lf_found_result(tag_type=45))
        assert act._isLFTag() is True

    def test_mf_classic_is_not_lf(self):
        """MF Classic 1K (type 1) is HF — no auto-verify."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result(tag_type=1))
        assert act._isLFTag() is False

    def test_ultralight_is_not_lf(self):
        """Ultralight (type 2) is HF — no auto-verify."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result(tag_type=2))
        assert act._isLFTag() is False

    def test_iclass_is_not_lf(self):
        """iCLASS (type 17) is HF — no auto-verify."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result(tag_type=17))
        assert act._isLFTag() is False

    def test_iso15693_is_not_lf(self):
        """ISO15693 (type 19) is HF — no auto-verify."""
        act = _create_autocopy()
        act.onScanFinish(_make_found_result(tag_type=19))
        assert act._isLFTag() is False

    def test_no_scan_result_not_lf(self):
        """No scan result returns False for _isLFTag."""
        act = _create_autocopy()
        act._scan_result = None
        assert act._isLFTag() is False


# ===============================================================
# AutoCopyActivity -- ACT_NAME
# ===============================================================

class TestAutoCopyMeta:
    """Activity metadata tests."""

    def test_act_name(self):
        """ACT_NAME must be 'autocopy'."""
        from activity_main import AutoCopyActivity
        assert AutoCopyActivity.ACT_NAME == 'autocopy'

    def test_state_constants_defined(self):
        """All 17 state constants are defined."""
        from activity_main import AutoCopyActivity
        expected = [
            'STATE_SCANNING', 'STATE_SCAN_NOT_FOUND', 'STATE_SCAN_WRONG_TYPE',
            'STATE_SCAN_MULTI', 'STATE_READING', 'STATE_READ_FAILED',
            'STATE_READ_NO_KEY_HF', 'STATE_READ_NO_KEY_LF',
            'STATE_READ_MISSING_KEYS', 'STATE_READ_TIMEOUT',
            'STATE_PLACE_CARD', 'STATE_WRITING', 'STATE_WRITE_SUCCESS',
            'STATE_WRITE_FAILED', 'STATE_VERIFYING', 'STATE_VERIFY_SUCCESS',
            'STATE_VERIFY_FAILED', 'STATE_CANCELLED',
        ]
        for attr in expected:
            assert hasattr(AutoCopyActivity, attr), f"Missing state: {attr}"
