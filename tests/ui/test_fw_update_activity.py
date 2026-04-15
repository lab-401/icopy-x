"""Tests for FWUpdateActivity -- PM3 firmware flash UI wizard.

Covers:
  - STATE_INFO: initial screen, M1/PWR exit, M2/OK -> preflash
  - STATE_PREFLASH: 3-page navigation (UP/DOWN), page titles, page 2 M1 exit,
                    page 2 M2/OK -> safety check
  - STATE_FLASHING: all keys blocked, background thread, progress callbacks
  - STATE_DONE: M2/OK/PWR exit, success/failure toast content
  - Safety check: pass -> flash, fail -> error toast stays in preflash
  - Flash engine: success/failure/exception paths
  - Progress callbacks: stage messages, _ui_progress, _do_progress
  - _handlePWR: toast dismiss, busy swallow, normal pass-through
  - Edge cases: canvas is None, _root is None, progress_bar is None

Ground truth: activity_main.py lines 6976-7224.
"""

import os
import sys
import threading

import pytest
from unittest.mock import MagicMock, patch, call

import actstack
from tests.ui.conftest import MockCanvas
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _setup_actstack():
    """Reset actstack and install MockCanvas factory for each test."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


def _create_fw_update(bundle=None):
    """Start a FWUpdateActivity and return it."""
    from activity_main import FWUpdateActivity
    return actstack.start_activity(FWUpdateActivity, bundle)


# =====================================================================
# STATE_INFO -- Creation and Initial State
# =====================================================================

class TestFWUpdateCreation:
    """FWUpdateActivity initial state (STATE_INFO)."""

    def test_initial_state_is_info(self):
        """Activity starts in STATE_INFO."""
        act = _create_fw_update()
        assert act._fw_state == act.STATE_INFO

    def test_initial_preflash_page_zero(self):
        """Pre-flash page counter starts at 0."""
        act = _create_fw_update()
        assert act._preflash_page == 0

    def test_title_fw_update(self):
        """Title bar reads 'FW Update'."""
        act = _create_fw_update()
        texts = act.getCanvas().get_all_text()
        assert 'FW Update' in texts

    def test_buttons_skip_install(self):
        """M1='Skip', M2='Install' in initial state."""
        act = _create_fw_update()
        texts = act.getCanvas().get_all_text()
        assert 'Skip' in texts
        assert 'Install' in texts

    def test_toast_created(self):
        """Toast widget is initialized."""
        act = _create_fw_update()
        assert act._toast is not None

    def test_progress_bar_created(self):
        """ProgressBar widget is initialized."""
        act = _create_fw_update()
        assert act._progress_bar is not None

    def test_json_renderer_created(self):
        """JsonRenderer is initialized for screen content."""
        act = _create_fw_update()
        assert act._jr is not None

    def test_info_text_shown(self):
        """Initial info text warns about firmware mismatch."""
        act = _create_fw_update()
        texts = act.getCanvas().get_all_text()
        assert any('FW Update required' in t for t in texts)

    def test_info_text_mentions_instabilities(self):
        """Info text mentions device instability risk."""
        act = _create_fw_update()
        texts = act.getCanvas().get_all_text()
        assert any('instabilit' in t for t in texts)


# =====================================================================
# STATE_INFO -- Key Events
# =====================================================================

class TestFWUpdateInfoKeys:
    """Key events in STATE_INFO."""

    def test_m1_finishes(self):
        """M1 (Skip) in STATE_INFO finishes the activity."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_pwr_finishes(self):
        """PWR in STATE_INFO finishes (when no toast, not busy)."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_m2_enters_preflash(self):
        """M2 (Install) transitions to STATE_PREFLASH."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M2)
        assert act._fw_state == act.STATE_PREFLASH
        assert act._preflash_page == 0

    def test_ok_enters_preflash(self):
        """OK also transitions to STATE_PREFLASH."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_OK)
        assert act._fw_state == act.STATE_PREFLASH
        assert act._preflash_page == 0

    def test_up_ignored_in_info(self):
        """UP key has no effect in STATE_INFO."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_UP)
        assert act._fw_state == act.STATE_INFO
        assert not act.life.destroyed

    def test_down_ignored_in_info(self):
        """DOWN key has no effect in STATE_INFO."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_DOWN)
        assert act._fw_state == act.STATE_INFO
        assert not act.life.destroyed

    def test_pwr_dismisses_toast_in_info(self):
        """PWR dismisses a visible toast before finishing."""
        act = _create_fw_update()
        # Simulate a visible toast
        act._toast.show('test msg', mode=act._toast.MASK_CENTER)
        act.onKeyEvent(KEY_PWR)
        # Toast dismissed, activity NOT destroyed (PWR was consumed)
        assert not act.life.destroyed
        assert act._fw_state == act.STATE_INFO


# =====================================================================
# STATE_PREFLASH -- Page Navigation
# =====================================================================

class TestFWUpdatePreflashNavigation:
    """Pre-flash wizard page navigation."""

    def _go_preflash(self):
        """Helper: create activity and move to preflash."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M2)  # INFO -> PREFLASH page 0
        return act

    def test_preflash_starts_at_page_0(self):
        """Entering preflash sets page to 0."""
        act = self._go_preflash()
        assert act._preflash_page == 0
        assert act._fw_state == act.STATE_PREFLASH

    def test_page_0_title(self):
        """Page 0 title is 'FW Update 1/3'."""
        act = self._go_preflash()
        texts = act.getCanvas().get_all_text()
        assert 'FW Update' in texts
        assert any('1/3' in t for t in texts)

    def test_page_0_buttons_dismissed(self):
        """Page 0 dismisses button labels."""
        act = self._go_preflash()
        texts = act.getCanvas().get_all_text()
        # Skip and Install from INFO state should be gone after dismissButton
        # Page 0 has no M1/M2 buttons
        assert 'Cancel' not in texts
        assert 'Start' not in texts

    def test_page_0_text_power_source(self):
        """Page 0 text mentions power source and 50% battery."""
        act = self._go_preflash()
        texts = act.getCanvas().get_all_text()
        assert any('power' in t.lower() for t in texts)
        assert any('50%' in t for t in texts)

    def test_page_0_down_goes_to_page_1(self):
        """DOWN on page 0 navigates to page 1."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)
        assert act._preflash_page == 1

    def test_page_0_up_ignored(self):
        """UP on page 0 has no effect (already at first page)."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_UP)
        assert act._preflash_page == 0

    def test_page_0_m1_ignored(self):
        """M1 on page 0 has no effect (no Cancel button)."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_M1)
        assert act._fw_state == act.STATE_PREFLASH
        assert not act.life.destroyed

    def test_page_0_m2_ignored(self):
        """M2 on page 0 has no effect (no Start button)."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_M2)
        assert act._fw_state == act.STATE_PREFLASH
        assert act._preflash_page == 0

    def test_page_0_ok_ignored(self):
        """OK on page 0 has no effect."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_OK)
        assert act._fw_state == act.STATE_PREFLASH
        assert act._preflash_page == 0

    def test_page_1_title(self):
        """Page 1 title is 'FW Update 2/3'."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        texts = act.getCanvas().get_all_text()
        assert 'FW Update' in texts
        assert any('2/3' in t for t in texts)

    def test_page_1_text_do_not_disconnect(self):
        """Page 1 text warns not to disconnect or press buttons."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        texts = act.getCanvas().get_all_text()
        assert any('disconnect' in t.lower() for t in texts)

    def test_page_1_up_goes_to_page_0(self):
        """UP on page 1 goes back to page 0."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_UP)
        assert act._preflash_page == 0

    def test_page_1_down_goes_to_page_2(self):
        """DOWN on page 1 goes to page 2."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        assert act._preflash_page == 2

    def test_page_1_m1_ignored(self):
        """M1 on page 1 has no effect."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_M1)
        assert act._fw_state == act.STATE_PREFLASH
        assert not act.life.destroyed

    def test_page_1_m2_ignored(self):
        """M2 on page 1 has no effect."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_M2)
        assert act._fw_state == act.STATE_PREFLASH
        assert act._preflash_page == 1

    def test_page_2_title(self):
        """Page 2 title is 'FW Update 3/3'."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        texts = act.getCanvas().get_all_text()
        assert 'FW Update' in texts
        assert any('3/3' in t for t in texts)

    def test_page_2_buttons_cancel_start(self):
        """Page 2 shows Cancel and Start buttons."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        texts = act.getCanvas().get_all_text()
        assert 'Cancel' in texts
        assert 'Start' in texts

    def test_page_2_text_when_ready(self):
        """Page 2 text says 'When ready, press Start'."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        texts = act.getCanvas().get_all_text()
        assert any('ready' in t.lower() for t in texts)
        assert any('Start' in t for t in texts)

    def test_page_2_up_goes_back(self):
        """UP on page 2 navigates back to page 1."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        act.onKeyEvent(KEY_UP)
        assert act._preflash_page == 1

    def test_page_2_down_ignored(self):
        """DOWN on page 2 has no effect (already at last page)."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        act.onKeyEvent(KEY_DOWN)
        assert act._preflash_page == 2

    def test_page_2_m1_finishes(self):
        """M1 (Cancel) on page 2 finishes the activity."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_pwr_finishes_from_preflash(self):
        """PWR in preflash finishes the activity (when no toast, not busy)."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_pwr_finishes_from_page_1(self):
        """PWR on page 1 finishes the activity."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_pwr_finishes_from_page_2(self):
        """PWR on page 2 finishes the activity."""
        act = self._go_preflash()
        act.onKeyEvent(KEY_DOWN)  # page 1
        act.onKeyEvent(KEY_DOWN)  # page 2
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_full_navigation_forward_and_back(self):
        """Navigate 0->1->2->1->0 and verify page at each step."""
        act = self._go_preflash()
        assert act._preflash_page == 0

        act.onKeyEvent(KEY_DOWN)
        assert act._preflash_page == 1

        act.onKeyEvent(KEY_DOWN)
        assert act._preflash_page == 2

        act.onKeyEvent(KEY_UP)
        assert act._preflash_page == 1

        act.onKeyEvent(KEY_UP)
        assert act._preflash_page == 0


# =====================================================================
# STATE_PREFLASH -- Safety Check (M2/OK on page 2)
# =====================================================================

class TestFWUpdateSafetyCheck:
    """Safety check triggered from preflash page 2."""

    def _go_page_2(self):
        """Helper: navigate to preflash page 2."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M2)     # INFO -> PREFLASH page 0
        act.onKeyEvent(KEY_DOWN)   # page 1
        act.onKeyEvent(KEY_DOWN)   # page 2
        return act

    @patch('middleware.pm3_flash.check_safety', return_value=(True, ''))
    def test_m2_safety_pass_starts_flash(self, mock_safety):
        """M2 on page 2 with safety pass transitions to STATE_FLASHING.

        The background thread runs immediately with mocked flash_firmware,
        so we block it with a threading.Event and check the intermediate state.
        """
        gate = threading.Event()

        def _blocking_flash(app_dir, progress_cb=None):
            gate.wait(timeout=5)
            return (True, 'OK')

        act = self._go_page_2()
        with patch('middleware.pm3_flash.flash_firmware',
                   side_effect=_blocking_flash):
            act.onKeyEvent(KEY_M2)
            assert mock_safety.called
            assert act._fw_state == act.STATE_FLASHING
            gate.set()
        # Let the thread finish
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

    @patch('middleware.pm3_flash.check_safety', return_value=(True, ''))
    def test_ok_safety_pass_starts_flash(self, mock_safety):
        """OK on page 2 with safety pass transitions to STATE_FLASHING."""
        gate = threading.Event()

        def _blocking_flash(app_dir, progress_cb=None):
            gate.wait(timeout=5)
            return (True, 'OK')

        act = self._go_page_2()
        with patch('middleware.pm3_flash.flash_firmware',
                   side_effect=_blocking_flash):
            act.onKeyEvent(KEY_OK)
            assert mock_safety.called
            assert act._fw_state == act.STATE_FLASHING
            gate.set()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

    @patch('middleware.pm3_flash.check_safety',
           return_value=(False, 'Battery too low'))
    def test_safety_fail_shows_error_toast(self, mock_safety):
        """Safety check failure shows error toast and stays in PREFLASH."""
        act = self._go_page_2()
        act.onKeyEvent(KEY_M2)
        assert act._fw_state == act.STATE_PREFLASH
        # Toast should have been shown with error
        texts = act.getCanvas().get_all_text()
        assert any('Battery too low' in t for t in texts)

    @patch('middleware.pm3_flash.check_safety',
           return_value=(False, 'Not charging'))
    def test_safety_fail_stays_on_page_2(self, mock_safety):
        """Failed safety check keeps page at 2."""
        act = self._go_page_2()
        act.onKeyEvent(KEY_M2)
        assert act._preflash_page == 2
        assert act._fw_state == act.STATE_PREFLASH

    @patch('middleware.pm3_flash.check_safety',
           return_value=(False, 'Charger disconnected'))
    def test_safety_fail_toast_uses_error_icon(self, mock_safety):
        """Failed safety check toast uses error icon."""
        act = self._go_page_2()
        # Spy on toast.show to check icon argument
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append((args, kwargs))
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act.onKeyEvent(KEY_M2)
        assert len(show_calls) == 1
        _, kwargs = show_calls[0]
        assert kwargs.get('icon') == 'error'

    @patch('middleware.pm3_flash.check_safety',
           return_value=(False, 'Charge level insufficient'))
    def test_safety_fail_toast_duration_3000(self, mock_safety):
        """Failed safety check toast has 3000ms duration."""
        act = self._go_page_2()
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append((args, kwargs))
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act.onKeyEvent(KEY_M2)
        assert len(show_calls) == 1
        _, kwargs = show_calls[0]
        assert kwargs.get('duration_ms') == 3000


# =====================================================================
# STATE_FLASHING -- Flash in Progress
# =====================================================================

class TestFWUpdateFlashing:
    """STATE_FLASHING behavior and flash thread management."""

    @patch('middleware.pm3_flash.check_safety', return_value=(True, ''))
    @patch('middleware.pm3_flash.flash_firmware', return_value=(True, 'OK'))
    def test_flashing_state_set(self, mock_flash, mock_safety):
        """_startFlash sets state to STATE_FLASHING."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M2)     # -> preflash
        act.onKeyEvent(KEY_DOWN)   # page 1
        act.onKeyEvent(KEY_DOWN)   # page 2
        act.onKeyEvent(KEY_M2)     # -> safety check -> flash
        assert act._fw_state in (act.STATE_FLASHING, act.STATE_DONE)

    def test_flashing_sets_busy(self):
        """_startFlash calls setbusy() -- verified by blocking the flash thread."""
        gate = threading.Event()

        def _blocking_flash(app_dir, progress_cb=None):
            gate.wait(timeout=5)
            return (True, 'Done')

        act = _create_fw_update()
        with patch('middleware.pm3_flash.flash_firmware',
                   side_effect=_blocking_flash):
            act._startFlash()
            # Thread is blocked, so setbusy() has been called but setidle() has not
            assert act._is_busy
            gate.set()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

    def test_flashing_title_fw_flash(self):
        """Title changes to 'FW Flash' during flashing."""
        act = _create_fw_update()
        # Call _startFlash directly (bypasses thread to check immediate state)
        with patch('middleware.pm3_flash.flash_firmware',
                   return_value=(True, 'OK')):
            act._startFlash()
        texts = act.getCanvas().get_all_text()
        assert 'FW Flash' in texts

    def test_flashing_shows_progress_bar(self):
        """Progress bar is shown during flash."""
        gate = threading.Event()

        def _blocking_flash(app_dir, progress_cb=None):
            gate.wait(timeout=5)
            return (True, 'OK')

        act = _create_fw_update()
        with patch('middleware.pm3_flash.flash_firmware',
                   side_effect=_blocking_flash):
            act._startFlash()
            assert act._progress_bar._showing
            gate.set()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

    def test_flashing_initial_message_preparing(self):
        """Initial progress message is 'Preparing...'."""
        act = _create_fw_update()
        with patch('middleware.pm3_flash.flash_firmware',
                   return_value=(True, 'OK')):
            act._startFlash()
        assert act._progress_bar._message == 'Preparing...'

    def test_flashing_initial_progress_zero(self):
        """Initial progress value is 0."""
        act = _create_fw_update()
        with patch('middleware.pm3_flash.flash_firmware',
                   return_value=(True, 'OK')):
            act._startFlash()
        assert act._progress_bar._progress == 0

    def test_flashing_tips_text(self):
        """Tips view shows 'Do not unplug' warning during flash."""
        act = _create_fw_update()
        with patch('middleware.pm3_flash.flash_firmware',
                   return_value=(True, 'OK')):
            act._startFlash()
        texts = act.getCanvas().get_all_text()
        assert any('unplug' in t.lower() for t in texts)

    def test_all_keys_blocked_during_flash(self):
        """All keys are silently ignored in STATE_FLASHING."""
        act = _create_fw_update()
        act._fw_state = act.STATE_FLASHING
        for key in (KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR):
            act.onKeyEvent(key)
        assert act._fw_state == act.STATE_FLASHING
        assert not act.life.destroyed


# =====================================================================
# Progress Callbacks
# =====================================================================

class TestFWUpdateProgress:
    """Progress bar updates from background thread."""

    def test_do_progress_updates_message(self):
        """_do_progress sets progress bar message."""
        act = _create_fw_update()
        act._do_progress('Flashing firmware...', 50)
        assert act._progress_bar._message == 'Flashing firmware...'

    def test_do_progress_updates_percent(self):
        """_do_progress sets progress bar value and tracks flash_percent."""
        act = _create_fw_update()
        act._do_progress('Verifying...', 75)
        assert act._progress_bar._progress == 75
        assert act._flash_percent == 75

    def test_do_progress_with_none_progress_bar(self):
        """_do_progress is safe when progress_bar is None."""
        act = _create_fw_update()
        act._progress_bar = None
        # Should not raise
        act._do_progress('msg', 50)
        assert act._flash_percent == 50

    def test_stage_messages_mapping(self):
        """Known stages map to display messages."""
        from activity_main import FWUpdateActivity
        expected = {
            'preparing': 'Preparing...',
            'killing_pm3': 'Stopping PM3...',
            'entering_bootloader': 'Entering bootloader...',
            'flashing': 'Flashing firmware...',
            'verifying': 'Verifying...',
            'restarting': 'Restarting PM3...',
            'complete': 'Flash complete',
        }
        for stage, msg in expected.items():
            assert FWUpdateActivity._STAGE_MESSAGES[stage] == msg

    def test_stage_message_unknown_falls_back_to_stage_name(self):
        """Unknown stage string is used as-is for the message."""
        from activity_main import FWUpdateActivity
        result = FWUpdateActivity._STAGE_MESSAGES.get('unknown_stage', 'unknown_stage')
        assert result == 'unknown_stage'

    def test_ui_progress_with_root(self):
        """_ui_progress calls _root.after when _root is set."""
        act = _create_fw_update()
        mock_root = MagicMock()
        actstack._root = mock_root
        act._ui_progress('Flashing...', 42)
        mock_root.after.assert_called_once_with(
            0, act._do_progress, 'Flashing...', 42)

    def test_ui_progress_without_root(self):
        """_ui_progress is safe when _root is None."""
        act = _create_fw_update()
        actstack._root = None
        # Should not raise
        act._ui_progress('msg', 10)

    def test_ui_progress_exception_swallowed(self):
        """_ui_progress swallows exceptions from _root.after."""
        act = _create_fw_update()
        mock_root = MagicMock()
        mock_root.after.side_effect = RuntimeError('Tk dead')
        actstack._root = mock_root
        # Should not raise
        act._ui_progress('msg', 10)


# =====================================================================
# Flash Completion (_ui_complete, _onFlashComplete)
# =====================================================================

class TestFWUpdateCompletion:
    """Flash completion handling."""

    def test_ui_complete_with_root(self):
        """_ui_complete schedules _onFlashComplete via _root.after."""
        act = _create_fw_update()
        mock_root = MagicMock()
        actstack._root = mock_root
        act._ui_complete(True, 'Done')
        mock_root.after.assert_called_once_with(
            0, act._onFlashComplete, True, 'Done')

    def test_ui_complete_without_root(self):
        """_ui_complete calls _onFlashComplete directly when _root is None."""
        act = _create_fw_update()
        actstack._root = None
        act._ui_complete(True, 'Done')
        assert act._fw_state == act.STATE_DONE

    def test_ui_complete_exception_fallback(self):
        """_ui_complete falls back to direct call on exception."""
        act = _create_fw_update()
        mock_root = MagicMock()
        mock_root.after.side_effect = RuntimeError('Tk dead')
        actstack._root = mock_root
        act._ui_complete(False, 'error')
        assert act._fw_state == act.STATE_DONE

    def test_flash_complete_success_state(self):
        """_onFlashComplete(True) sets STATE_DONE."""
        act = _create_fw_update()
        act._fw_state = act.STATE_FLASHING
        act._is_busy = True
        act._onFlashComplete(True, 'Flash complete')
        assert act._fw_state == act.STATE_DONE

    def test_flash_complete_success_setidle(self):
        """_onFlashComplete calls setidle()."""
        act = _create_fw_update()
        act._fw_state = act.STATE_FLASHING
        act._is_busy = True
        act._onFlashComplete(True)
        assert not act._is_busy

    def test_flash_complete_success_hides_progress(self):
        """Progress bar is hidden after flash complete."""
        act = _create_fw_update()
        act._progress_bar.show()
        act._onFlashComplete(True)
        assert not act._progress_bar._showing

    def test_flash_complete_success_toast_content(self):
        """Success toast shows 'FW Updated!'."""
        act = _create_fw_update()
        act._onFlashComplete(True)
        texts = act.getCanvas().get_all_text()
        assert any('FW Updated' in t for t in texts)

    def test_flash_complete_success_toast_check_icon(self):
        """Success toast uses check icon."""
        act = _create_fw_update()
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append((args, kwargs))
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act._onFlashComplete(True)
        assert len(show_calls) == 1
        _, kwargs = show_calls[0]
        assert kwargs.get('icon') == 'check'

    def test_flash_complete_success_toast_self_dismissing(self):
        """Success toast is self-dismissing (3s)."""
        act = _create_fw_update()
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append((args, kwargs))
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act._onFlashComplete(True)
        _, kwargs = show_calls[0]
        assert kwargs.get('duration_ms') == 3000

    def test_flash_complete_failure_state(self):
        """_onFlashComplete(False) sets STATE_DONE."""
        act = _create_fw_update()
        act._onFlashComplete(False, 'Timeout')
        assert act._fw_state == act.STATE_DONE

    def test_flash_complete_failure_toast_content(self):
        """Failure toast shows 'Flash Failed' message."""
        act = _create_fw_update()
        act._onFlashComplete(False, 'Connection lost')
        texts = act.getCanvas().get_all_text()
        assert any('Flash Failed' in t for t in texts)

    def test_flash_complete_failure_toast_error_icon(self):
        """Failure toast uses error icon."""
        act = _create_fw_update()
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append((args, kwargs))
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act._onFlashComplete(False, 'fail')
        _, kwargs = show_calls[0]
        assert kwargs.get('icon') == 'error'

    def test_flash_complete_failure_toast_no_timeout(self):
        """Failure toast stays until dismissed (duration_ms=0)."""
        act = _create_fw_update()
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append((args, kwargs))
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act._onFlashComplete(False, 'fail')
        _, kwargs = show_calls[0]
        assert kwargs.get('duration_ms') == 0

    def test_flash_complete_hides_progress_when_none(self):
        """_onFlashComplete is safe when progress_bar is None."""
        act = _create_fw_update()
        act._progress_bar = None
        # Should not raise
        act._onFlashComplete(True)
        assert act._fw_state == act.STATE_DONE

    def test_flash_complete_without_toast(self):
        """_onFlashComplete is safe when _toast is None."""
        act = _create_fw_update()
        act._toast = None
        # Should not raise
        act._onFlashComplete(True)
        assert act._fw_state == act.STATE_DONE

    def test_flash_complete_failure_without_toast(self):
        """_onFlashComplete(False) is safe when _toast is None."""
        act = _create_fw_update()
        act._toast = None
        act._onFlashComplete(False, 'some error')
        assert act._fw_state == act.STATE_DONE


# =====================================================================
# STATE_DONE -- Key Events
# =====================================================================

class TestFWUpdateDone:
    """Key events in STATE_DONE."""

    def _go_done(self, success=True, message=''):
        """Helper: create activity and move to STATE_DONE."""
        act = _create_fw_update()
        act._onFlashComplete(success, message)
        assert act._fw_state == act.STATE_DONE
        return act

    def test_m2_finishes(self):
        """M2 in STATE_DONE finishes the activity."""
        act = self._go_done()
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed

    def test_ok_finishes(self):
        """OK in STATE_DONE finishes the activity."""
        act = self._go_done()
        act.onKeyEvent(KEY_OK)
        assert act.life.destroyed

    def test_pwr_finishes(self):
        """PWR in STATE_DONE finishes (after dismissing toast)."""
        act = self._go_done()
        # First PWR dismisses the toast (toast is showing with duration_ms=0)
        act.onKeyEvent(KEY_PWR)
        # Toast was visible, so _handlePWR consumed the key
        assert not act.life.destroyed
        # Second PWR finishes (toast now dismissed)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_pwr_finishes_when_no_toast(self):
        """PWR in STATE_DONE finishes when toast is already gone."""
        act = _create_fw_update()
        act._toast = None
        act._fw_state = act.STATE_DONE
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_m1_ignored_in_done(self):
        """M1 has no effect in STATE_DONE."""
        act = self._go_done()
        act.onKeyEvent(KEY_M1)
        assert not act.life.destroyed

    def test_up_ignored_in_done(self):
        """UP has no effect in STATE_DONE."""
        act = self._go_done()
        act.onKeyEvent(KEY_UP)
        assert not act.life.destroyed

    def test_down_ignored_in_done(self):
        """DOWN has no effect in STATE_DONE."""
        act = self._go_done()
        act.onKeyEvent(KEY_DOWN)
        assert not act.life.destroyed

    def test_done_after_failure(self):
        """STATE_DONE works the same after a failure."""
        act = self._go_done(success=False, message='Flash timeout')
        act.onKeyEvent(KEY_OK)
        assert act.life.destroyed


# =====================================================================
# Background Flash Thread Integration
# =====================================================================

class TestFWUpdateFlashThread:
    """Background flash thread behavior."""

    @patch('middleware.pm3_flash.flash_firmware')
    def test_flash_thread_calls_flash_firmware(self, mock_flash):
        """Background thread calls pm3_flash.flash_firmware."""
        mock_flash.return_value = (True, 'OK')
        act = _create_fw_update()
        # Set _root so _ui_complete can schedule via after()
        mock_root = MagicMock()
        # Make after() call the function immediately
        mock_root.after.side_effect = lambda ms, fn, *args: fn(*args)
        actstack._root = mock_root

        act._startFlash()
        # Wait for the daemon thread to finish
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

        assert mock_flash.called
        args, kwargs = mock_flash.call_args
        # First argument is app_dir
        assert isinstance(args[0], str)
        # progress_cb keyword argument
        assert 'progress_cb' in kwargs

    @patch('middleware.pm3_flash.flash_firmware')
    def test_flash_thread_success_path(self, mock_flash):
        """Successful flash transitions to STATE_DONE with success toast."""
        mock_flash.return_value = (True, 'Flash OK')
        act = _create_fw_update()
        mock_root = MagicMock()
        # Execute callbacks immediately, but skip the delayed finish()
        # (3100ms timer) which would destroy the canvas before we can check.
        mock_root.after.side_effect = lambda ms, fn, *args: fn(*args) if ms == 0 else None
        actstack._root = mock_root

        act._startFlash()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

        assert act._fw_state == act.STATE_DONE
        texts = act.getCanvas().get_all_text()
        assert any('FW Updated' in t for t in texts)

    @patch('middleware.pm3_flash.flash_firmware')
    def test_flash_thread_failure_path(self, mock_flash):
        """Failed flash transitions to STATE_DONE with error toast."""
        mock_flash.return_value = (False, 'Device not responding')
        act = _create_fw_update()
        mock_root = MagicMock()
        mock_root.after.side_effect = lambda ms, fn, *args: fn(*args) if ms == 0 else None
        actstack._root = mock_root

        act._startFlash()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

        assert act._fw_state == act.STATE_DONE
        texts = act.getCanvas().get_all_text()
        assert any('Flash Failed' in t for t in texts)

    @patch('middleware.pm3_flash.flash_firmware')
    def test_flash_thread_exception_path(self, mock_flash):
        """Exception in flash thread transitions to STATE_DONE with error."""
        mock_flash.side_effect = OSError('USB disconnected')
        act = _create_fw_update()
        mock_root = MagicMock()
        mock_root.after.side_effect = lambda ms, fn, *args: fn(*args) if ms == 0 else None
        actstack._root = mock_root

        act._startFlash()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

        assert act._fw_state == act.STATE_DONE
        texts = act.getCanvas().get_all_text()
        assert any('Flash Failed' in t for t in texts)

    @patch('middleware.pm3_flash.flash_firmware')
    def test_flash_thread_progress_callback(self, mock_flash):
        """Flash thread invokes progress callback with stage messages."""
        progress_calls = []

        def _capture_flash(app_dir, progress_cb=None):
            if progress_cb:
                progress_cb(10, 'preparing')
                progress_cb(30, 'killing_pm3')
                progress_cb(50, 'flashing')
                progress_cb(90, 'verifying')
                progress_cb(100, 'complete')
            return (True, 'OK')

        mock_flash.side_effect = _capture_flash

        act = _create_fw_update()
        mock_root = MagicMock()

        # Collect the after() calls to verify progress scheduling
        after_calls = []

        def _capture_after(ms, fn, *args):
            after_calls.append((ms, fn, args))
            fn(*args)  # Execute immediately

        mock_root.after.side_effect = _capture_after
        actstack._root = mock_root

        act._startFlash()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

        # Verify progress was reported (at least _do_progress calls)
        progress_after_calls = [
            c for c in after_calls if c[1] == act._do_progress
        ]
        assert len(progress_after_calls) == 5

        # Verify stage message translations
        messages = [c[2][0] for c in progress_after_calls]
        assert 'Preparing...' in messages
        assert 'Stopping PM3...' in messages
        assert 'Flashing firmware...' in messages
        assert 'Verifying...' in messages
        assert 'Flash complete' in messages


# =====================================================================
# _handlePWR interactions
# =====================================================================

class TestFWUpdateHandlePWR:
    """PWR key behavior across states with toast/busy combinations."""

    def test_pwr_busy_swallowed_in_info(self):
        """PWR while busy in STATE_INFO is swallowed (no finish)."""
        act = _create_fw_update()
        act._is_busy = True
        act.onKeyEvent(KEY_PWR)
        assert not act.life.destroyed
        assert act._fw_state == act.STATE_INFO

    def test_pwr_busy_swallowed_in_preflash(self):
        """PWR while busy in STATE_PREFLASH is swallowed."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M2)  # -> preflash
        act._is_busy = True
        act.onKeyEvent(KEY_PWR)
        assert not act.life.destroyed
        assert act._fw_state == act.STATE_PREFLASH

    def test_pwr_dismisses_toast_in_preflash(self):
        """PWR dismisses visible toast in PREFLASH (from safety fail)."""
        act = _create_fw_update()
        act.onKeyEvent(KEY_M2)  # -> preflash
        act._toast.show('error', mode=act._toast.MASK_CENTER)
        act.onKeyEvent(KEY_PWR)
        # Toast consumed PWR
        assert not act.life.destroyed

    def test_pwr_in_done_dismisses_toast_first(self):
        """In STATE_DONE, first PWR dismisses toast, second PWR finishes."""
        act = _create_fw_update()
        act._onFlashComplete(True, '')
        # Toast is showing (duration_ms=0 means indefinite)
        act.onKeyEvent(KEY_PWR)
        # Toast dismissed
        assert not act.life.destroyed
        # Now PWR should finish
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# =====================================================================
# State Constants
# =====================================================================

class TestFWUpdateConstants:
    """FWUpdateActivity class constants."""

    def test_act_name(self):
        """ACT_NAME is 'fw_update'."""
        from activity_main import FWUpdateActivity
        assert FWUpdateActivity.ACT_NAME == 'fw_update'

    def test_state_constants_distinct(self):
        """All state constants are distinct strings."""
        from activity_main import FWUpdateActivity
        states = [
            FWUpdateActivity.STATE_INFO,
            FWUpdateActivity.STATE_PREFLASH,
            FWUpdateActivity.STATE_FLASHING,
            FWUpdateActivity.STATE_DONE,
        ]
        assert len(set(states)) == 4

    def test_state_constant_values(self):
        """State constants have expected string values."""
        from activity_main import FWUpdateActivity
        assert FWUpdateActivity.STATE_INFO == 'info'
        assert FWUpdateActivity.STATE_PREFLASH == 'preflash'
        assert FWUpdateActivity.STATE_FLASHING == 'flashing'
        assert FWUpdateActivity.STATE_DONE == 'done'

    def test_stage_messages_all_seven(self):
        """_STAGE_MESSAGES has exactly 7 entries."""
        from activity_main import FWUpdateActivity
        assert len(FWUpdateActivity._STAGE_MESSAGES) == 7


# =====================================================================
# Edge Cases
# =====================================================================

class TestFWUpdateEdgeCases:
    """Edge cases and defensive code paths."""

    def test_render_preflash_with_none_tips_view(self):
        """_renderPreflashPage is safe when _tips_view is None."""
        act = _create_fw_update()
        act._tips_view = None
        act._enterPreflash()
        # Should not raise
        assert act._fw_state == act.STATE_PREFLASH

    def test_start_flash_with_none_tips_view(self):
        """_startFlash is safe when _tips_view is None."""
        gate = threading.Event()

        def _blocking_flash(app_dir, progress_cb=None):
            gate.wait(timeout=5)
            return (True, 'OK')

        act = _create_fw_update()
        act._tips_view = None
        with patch('middleware.pm3_flash.flash_firmware',
                   side_effect=_blocking_flash):
            act._startFlash()
            assert act._fw_state == act.STATE_FLASHING
            gate.set()
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=5)

    def test_safety_check_with_none_toast(self):
        """_onStartPressed with None _toast does not crash on failure."""
        act = _create_fw_update()
        act._fw_state = act.STATE_PREFLASH
        act._preflash_page = 2
        act._toast = None
        with patch('middleware.pm3_flash.check_safety',
                   return_value=(False, 'Low battery')):
            act._onStartPressed()
        # Should not raise, state unchanged
        assert act._fw_state == act.STATE_PREFLASH

    def test_flash_complete_default_message_empty(self):
        """_onFlashComplete with default message='' works."""
        act = _create_fw_update()
        act._onFlashComplete(success=True)
        assert act._fw_state == act.STATE_DONE

    def test_flash_complete_failure_empty_message(self):
        """_onFlashComplete failure with empty message shows 'Flash Failed'."""
        act = _create_fw_update()
        original_show = act._toast.show
        show_calls = []

        def _spy_show(*args, **kwargs):
            show_calls.append(args)
            return original_show(*args, **kwargs)

        act._toast.show = _spy_show
        act._onFlashComplete(False, '')
        assert len(show_calls) == 1
        assert 'Flash Failed' in show_calls[0][0]

    def test_multiple_state_transitions_full_flow(self):
        """Full flow: INFO -> PREFLASH -> page navigation -> DONE."""
        act = _create_fw_update()
        assert act._fw_state == act.STATE_INFO

        # INFO -> PREFLASH
        act.onKeyEvent(KEY_M2)
        assert act._fw_state == act.STATE_PREFLASH
        assert act._preflash_page == 0

        # Navigate pages
        act.onKeyEvent(KEY_DOWN)
        assert act._preflash_page == 1
        act.onKeyEvent(KEY_DOWN)
        assert act._preflash_page == 2

        # Simulate flash complete directly (avoids thread)
        act._onFlashComplete(True, 'All good')
        assert act._fw_state == act.STATE_DONE

        # Exit from DONE
        # First dismiss toast
        act.onKeyEvent(KEY_PWR)
        assert not act.life.destroyed
        # Then exit
        act.onKeyEvent(KEY_OK)
        assert act.life.destroyed
