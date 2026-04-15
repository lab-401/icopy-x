"""Tests for WriteActivity (Write Tag).

Validates against the exhaustive binary extraction in
docs/UI_Mapping/15_write_tag/V1090_WRITE_FLOW_COMPLETE.md.

Ground truth:
    WriteActivity:
    - Title: "Write Tag" (resources key: write_tag)
    - States: IDLE -> WRITING -> WRITE_SUCCESS/WRITE_FAILED
              IDLE -> VERIFYING -> VERIFY_SUCCESS/VERIFY_FAILED
    - IDLE: M1="Write", M2="Verify"
    - WRITING: "Writing..." progress bar, buttons disabled
    - WRITE_SUCCESS: "Write successful!" toast, M1="Rewrite", M2="Verify"
    - WRITE_FAILED: "Write failed!" toast, M1="Rewrite", M2="Verify"
    - VERIFYING: "Verifying..." progress bar, buttons disabled
    - VERIFY_SUCCESS: "Verification successful!" toast
    - VERIFY_FAILED: "Verification failed!" toast
    - write.so handles ALL write logic (mocked in tests)
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


def _create_write(bundle=None):
    """Start a WriteActivity and return it."""
    from activity_main import WriteActivity
    act = actstack.start_activity(WriteActivity, bundle)
    return act


def _sample_infos():
    """Return a sample infos dict for testing."""
    return {
        'type': 1,
        'type_name': 'M1 S50 1K 4B',
        'uid': 'AABBCCDD',
        'data': b'\x00' * 1024,
    }


# ===============================================================
# WriteActivity -- Creation & Layout
# ===============================================================

class TestWriteTagCreation:
    """WriteActivity initial state tests."""

    def test_title_write_tag(self):
        """Title bar must read 'Write Tag' (resources key: write_tag)."""
        act = _create_write()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write Tag' in texts

    def test_idle_buttons_write_verify(self):
        """IDLE state: M1='Write', M2='Verify'."""
        act = _create_write()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write' in texts
        assert 'Verify' in texts

    def test_initial_state_idle(self):
        """Activity starts in IDLE state."""
        act = _create_write()
        assert act.state == act.STATE_IDLE

    def test_receives_data_from_bundle(self):
        """Activity stores bundle as _read_bundle.

        infos comes from scan.getScanCache(), not directly from bundle.
        """
        infos = _sample_infos()
        act = _create_write({'infos': infos})
        assert act._read_bundle == {'infos': infos}

    def test_progressbar_created(self):
        """ProgressBar widget is created."""
        act = _create_write()
        assert act._write_progressbar is not None

    def test_toast_created(self):
        """Toast widget is created."""
        act = _create_write()
        assert act._write_toast is not None

    def test_buttons_enabled_initially(self):
        """Buttons are enabled in IDLE state."""
        act = _create_write()
        assert act.btn_enabled is True


# ===============================================================
# WriteActivity -- Write Operations
# ===============================================================

class TestWriteTagWriteOps:
    """WriteActivity write operation tests."""

    def test_m1_starts_write(self):
        """M1 in IDLE starts write (transitions to WRITING)."""
        act = _create_write({'infos': _sample_infos()})
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_WRITING

    def test_ok_starts_write(self):
        """OK in IDLE starts write (same as M1)."""
        act = _create_write({'infos': _sample_infos()})
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_WRITING

    def test_write_progress_shown(self):
        """Starting write shows 'Writing...' progress bar."""
        act = _create_write({'infos': _sample_infos()})
        act.onKeyEvent(KEY_M1)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Writing' in t for t in texts)

    def test_buttons_disabled_during_write(self):
        """Buttons are disabled during write operation."""
        act = _create_write({'infos': _sample_infos()})
        act.onKeyEvent(KEY_M1)
        assert act.btn_enabled is False

    def test_write_success_toast(self):
        """Write success shows 'Write successful!' toast."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_success')
        assert act.state == act.STATE_WRITE_SUCCESS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write successful!' in texts

    def test_write_failed_toast(self):
        """Write failure shows 'Write failed!' toast."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_failed')
        assert act.state == act.STATE_WRITE_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Write failed!' in texts

    def test_write_success_buttons(self):
        """After write success: M1='Rewrite', M2='Verify'."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_success')
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rewrite' in texts
        assert 'Verify' in texts

    def test_write_failed_buttons(self):
        """After write failure: M1='Rewrite', M2='Verify'."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_failed')
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rewrite' in texts
        assert 'Verify' in texts

    def test_buttons_reenabled_after_success(self):
        """Buttons are re-enabled after write completes."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_success')
        assert act.btn_enabled is True

    def test_buttons_reenabled_after_failure(self):
        """Buttons are re-enabled after write failure."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_failed')
        assert act.btn_enabled is True


# ===============================================================
# WriteActivity -- Verify Operations
# ===============================================================

class TestWriteTagVerifyOps:
    """WriteActivity verify operation tests."""

    def test_m2_starts_verify(self):
        """M2 in IDLE starts verify (transitions to VERIFYING)."""
        # Create without bundle so auto-write does not trigger
        act = _create_write()
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_VERIFYING

    def test_verify_progress_shown(self):
        """Starting verify shows 'Verifying...' progress bar."""
        act = _create_write()
        act.onKeyEvent(KEY_M2)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Verifying' in t for t in texts)

    def test_buttons_disabled_during_verify(self):
        """Buttons are disabled during verify operation."""
        act = _create_write({'infos': _sample_infos()})
        act.onKeyEvent(KEY_M2)
        assert act.btn_enabled is False

    def test_verify_success_toast(self):
        """Verify success shows 'Verification successful!' toast."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_success')
        assert act.state == act.STATE_VERIFY_SUCCESS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Verification successful!' in texts

    def test_verify_failed_toast(self):
        """Verify failure shows 'Verification failed!' toast."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_failed')
        assert act.state == act.STATE_VERIFY_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Verification failed!' in texts

    def test_verify_success_buttons(self):
        """After verify success: M1='Rewrite', M2='Verify'."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_success')
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rewrite' in texts
        assert 'Verify' in texts

    def test_verify_failed_buttons(self):
        """After verify failure: M1='Rewrite', M2='Verify'."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_failed')
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Rewrite' in texts
        assert 'Verify' in texts


# ===============================================================
# WriteActivity -- Rewrite / Re-verify
# ===============================================================

class TestWriteTagRewrite:
    """WriteActivity rewrite and re-verify tests."""

    def test_rewrite_after_success(self):
        """M2 after write success triggers rewrite (back to WRITING).

        After completion: M1=Verify, M2=Rewrite (swapped from IDLE).
        """
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_success')
        assert act.state == act.STATE_WRITE_SUCCESS

        # Press M2 (Rewrite)
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_WRITING

    def test_rewrite_after_failure(self):
        """M2 after write failure triggers rewrite."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_failed')
        assert act.state == act.STATE_WRITE_FAILED

        # Press M2 (Rewrite)
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_WRITING

    def test_verify_after_write_success(self):
        """M1 after write success triggers verify.

        After completion: M1=Verify, M2=Rewrite (swapped from IDLE).
        """
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_success')

        # Press M1 (Verify)
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_VERIFYING

    def test_rewrite_after_verify_success(self):
        """M2 after verify success triggers rewrite."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_success')

        # Press M2 (Rewrite)
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_WRITING

    def test_rewrite_after_verify_failure(self):
        """M2 after verify failure triggers rewrite."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_failed')

        # Press M2 (Rewrite)
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_WRITING


# ===============================================================
# WriteActivity -- Exit / PWR
# ===============================================================

class TestWriteTagExit:
    """WriteActivity exit and navigation tests."""

    def test_pwr_exits_idle(self):
        """PWR in IDLE finishes the activity."""
        act = _create_write()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_pwr_exits_during_write(self):
        """PWR during WRITING still finishes (user can abort)."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_pwr_exits_after_success(self):
        """PWR after write success finishes the activity.

        First PWR dismisses the toast, second PWR exits.
        """
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        act._onWriteComplete('write_success')
        act.onKeyEvent(KEY_PWR)  # dismiss toast
        act.onKeyEvent(KEY_PWR)  # exit
        assert act.life.destroyed

    def test_pwr_exits_after_verify_fail(self):
        """PWR after verify failure finishes the activity.

        First PWR dismisses the toast, second PWR exits.
        """
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        act._onVerifyComplete('verify_failed')
        act.onKeyEvent(KEY_PWR)  # dismiss toast
        act.onKeyEvent(KEY_PWR)  # exit
        assert act.life.destroyed

    def test_keys_blocked_during_write(self):
        """M1/M2/OK are blocked during WRITING (except PWR)."""
        act = _create_write({'infos': _sample_infos()})
        act.startWrite()
        # These should NOT change state
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_WRITING
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_WRITING

    def test_keys_blocked_during_verify(self):
        """M1/M2/OK are blocked during VERIFYING (except PWR)."""
        act = _create_write({'infos': _sample_infos()})
        act.startVerify()
        # These should NOT change state
        act.onKeyEvent(KEY_M1)
        assert act.state == act.STATE_VERIFYING
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_VERIFYING
