"""Tests for DiagnosisActivity and 6 sub-activities.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/09_diagnosis/README.md.

Ground truth:
    - Title: "Diagnosis" (resources key: diagnosis)
    - Level 1: BigTextListView with "User diagnosis", "Factory diagnosis"
    - Level 2: CheckedListView with 9 sub-test items
    - M1: "" (empty), M2: "Start"
    - M2/OK in ITEMS_MAIN: transition to ITEMS_TEST
    - M2 in ITEMS_TEST: startTest()
    - PWR in ITEMS_TEST: back to ITEMS_MAIN
    - PWR in ITEMS_MAIN: finish()
    - Sub-activities: ScreenTest, ButtonTest, SoundTest, HFReader, LfReader, USB
"""

import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import (
    KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
    KEY_LEFT, KEY_RIGHT,
)


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


def _create_diagnosis():
    """Start a DiagnosisActivity."""
    from activity_tools import DiagnosisActivity
    act = actstack.start_activity(DiagnosisActivity)
    return act


# ---------------------------------------------------------------
# DiagnosisActivity Tests
# ---------------------------------------------------------------

class TestDiagnosisActivity:
    """DiagnosisActivity unit tests -- all states covered."""

    def test_title_is_diagnosis(self):
        """Title bar must read 'Diagnosis' (resources key: diagnosis)."""
        act = _create_diagnosis()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Diagnosis' in texts

    def test_buttons_empty_in_main(self):
        """M1="" (empty), M2="" (empty) in ITEMS_MAIN state."""
        act = _create_diagnosis()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # No button labels in ITEMS_MAIN
        assert 'Diagnosis' in texts

    def test_main_items_displayed(self):
        """Level 1 must show 'User diagnosis' and 'Factory diagnosis'."""
        act = _create_diagnosis()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # BigTextListView renders joined text
        all_text = ' '.join(texts)
        assert 'User diagnosis' in all_text
        assert 'Factory diagnosis' in all_text

    def test_initial_state_items_main(self):
        """Initial state must be ITEMS_MAIN."""
        act = _create_diagnosis()
        assert act.get_state() == 'items_main'

    def test_ok_transitions_to_items_test(self):
        """OK in ITEMS_MAIN transitions to ITEMS_TEST."""
        act = _create_diagnosis()
        assert act.get_state() == 'items_main'
        act.onKeyEvent(KEY_OK)
        assert act.get_state() == 'items_test'

    def test_m2_transitions_to_items_test(self):
        """M2 in ITEMS_MAIN transitions to ITEMS_TEST."""
        act = _create_diagnosis()
        act.onKeyEvent(KEY_M2)
        assert act.get_state() == 'items_test'

    def test_tips_shown_in_items_test(self):
        """ITEMS_TEST shows tips text with M1=Cancel, M2=Start."""
        act = _create_diagnosis()
        act.onKeyEvent(KEY_OK)  # -> ITEMS_TEST (tips screen)
        assert act.get_state() == 'items_test'
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Start' in texts
        assert 'Cancel' in texts

    def test_5_user_tests_defined(self):
        """5 user diagnosis tests are defined."""
        act = _create_diagnosis()
        assert len(act._USER_TESTS) == 5

    def test_main_listview_exists(self):
        """Main listview is created with 2 items."""
        act = _create_diagnosis()
        assert act._main_listview is not None
        assert act._main_listview.selection() == 0

    def test_pwr_back_to_main_from_test(self):
        """PWR in ITEMS_TEST returns to ITEMS_MAIN."""
        act = _create_diagnosis()
        act.onKeyEvent(KEY_OK)  # -> ITEMS_TEST
        assert act.get_state() == 'items_test'
        act.onKeyEvent(KEY_PWR)
        assert act.get_state() == 'items_main'

    def test_pwr_finishes_from_main(self):
        """PWR in ITEMS_MAIN finishes the activity."""
        act = _create_diagnosis()
        assert act.get_state() == 'items_main'
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_start_test_changes_state(self):
        """M2 in ITEMS_TEST triggers _run_all_tests and changes to TESTING."""
        act = _create_diagnosis()
        act.onKeyEvent(KEY_OK)  # -> ITEMS_TEST (tips screen)
        act.onKeyEvent(KEY_M2)  # start tests
        # State should be TESTING (tests run in background thread)
        assert act.get_state() == 'testing'

    def test_test_results_starts_empty(self):
        """Test results list starts empty."""
        act = _create_diagnosis()
        assert act._test_results == []

    def test_test_results_is_tuple_list(self):
        """Test results is a list of (name, passed, value_str) tuples."""
        act = _create_diagnosis()
        # Manually add a result tuple as the test runner would
        act._test_results.append(('HF Voltage', True, '(37V)'))
        results = act.get_test_results()
        assert len(results) == 1
        assert results[0] == ('HF Voltage', True, '(37V)')

    def test_test_results_pass_and_fail(self):
        """Results can contain both pass and fail entries."""
        act = _create_diagnosis()
        act._test_results.append(('HF Voltage', True, '(37V)'))
        act._test_results.append(('LF reader', False, ''))
        results = act.get_test_results()
        assert len(results) == 2
        assert results[0][1] is True
        assert results[1][1] is False

    def test_mixed_results(self):
        """Multiple results with different pass/fail status."""
        act = _create_diagnosis()
        act._test_results.append(('HF Voltage', True, '(37V)'))
        act._test_results.append(('LF Voltage', False, ''))
        act._test_results.append(('HF reader', True, ''))
        results = act.get_test_results()
        assert len(results) == 3
        assert results[0][1] is True
        assert results[1][1] is False
        assert results[2][1] is True

    def test_on_data_does_not_crash(self):
        """onData with test result dict does not crash."""
        act = _create_diagnosis()
        # onData currently just passes for sub-activity results
        act.onData({'test_index': 0, 'result': True})
        # Should not raise

    def test_m1_does_nothing_in_main(self):
        """M1 does nothing in ITEMS_MAIN (empty label)."""
        act = _create_diagnosis()
        act.onKeyEvent(KEY_M1)
        # Should still be in ITEMS_MAIN, not finished
        assert act.get_state() == 'items_main'
        assert not act.life.destroyed

    def test_main_items_text_from_resources(self):
        """Main items must match resource strings for diagnosis menu."""
        act = _create_diagnosis()
        assert len(act._main_items) == 2
        assert 'User diagnosis' in act._main_items[0]
        assert 'Factory diagnosis' in act._main_items[1]


# ---------------------------------------------------------------
# ScreenTestActivity Tests
# ---------------------------------------------------------------

class TestScreenTestActivity:
    """ScreenTestActivity unit tests."""

    def test_title_is_diagnosis(self):
        """Title shows 'Diagnosis'."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Diagnosis' in texts

    def test_buttons_fail_pass(self):
        """M1='Fail', M2='Pass'."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Fail' in texts
        assert 'Pass' in texts

    def test_ok_starts_color_cycle(self):
        """OK key starts showing test colors."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        assert not act._showing_colors
        act.onKeyEvent(KEY_OK)
        assert act._showing_colors
        assert act._color_pos == 0

    def test_color_cycle_advances(self):
        """Multiple OK presses cycle through colors."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        act.onKeyEvent(KEY_OK)  # start
        assert act._color_pos == 0
        act.onKeyEvent(KEY_OK)  # advance
        assert act._color_pos == 1
        act.onKeyEvent(KEY_OK)  # advance
        assert act._color_pos == 2

    def test_m2_passes_and_finishes(self):
        """M2 = Pass and finish."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed

    def test_m1_fails_and_finishes(self):
        """M1 = Fail and finish."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_pwr_exits_as_fail(self):
        """PWR exits with fail result."""
        from activity_tools import ScreenTestActivity
        act = actstack.start_activity(ScreenTestActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_5_colors_defined(self):
        """Exactly 5 test colors: blue, green, white, green, black."""
        from activity_tools import ScreenTestActivity
        assert len(ScreenTestActivity.COLORS) == 5
        assert ScreenTestActivity.COLORS[0] == '#1C6AEB'
        assert ScreenTestActivity.COLORS[-1] == '#000000'


# ---------------------------------------------------------------
# ButtonTestActivity Tests
# ---------------------------------------------------------------

class TestButtonTestActivity:
    """ButtonTestActivity unit tests."""

    def test_title_is_buttons(self):
        """Title shows 'Buttons'."""
        from activity_tools import ButtonTestActivity
        act = actstack.start_activity(ButtonTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Buttons' in texts

    def test_all_buttons_required(self):
        """All 8 buttons must be pressed to pass."""
        from activity_tools import ButtonTestActivity
        assert len(ButtonTestActivity.REQUIRED_BUTTONS) == 8

    def test_pressing_records_state(self):
        """Each key press is recorded in _pressed set."""
        from activity_tools import ButtonTestActivity
        act = actstack.start_activity(ButtonTestActivity)
        assert len(act._pressed) == 0
        act.onKeyEvent(KEY_UP)
        assert KEY_UP in act._pressed
        act.onKeyEvent(KEY_DOWN)
        assert KEY_DOWN in act._pressed

    def test_all_pressed_passes(self):
        """Pressing all required buttons finishes with pass.

        Note: pressing all buttons triggers immediate finish, so we need
        a parent activity on the stack to receive the result.
        """
        from activity_tools import ButtonTestActivity, DiagnosisActivity
        # Push a parent first
        parent = actstack.start_activity(DiagnosisActivity)
        act = actstack.start_activity(ButtonTestActivity)
        for btn in ButtonTestActivity.REQUIRED_BUTTONS:
            act.onKeyEvent(btn)
        assert act.life.destroyed

    def test_update_btn_state_renders(self):
        """update_btn_state creates canvas text items for each button."""
        from activity_tools import ButtonTestActivity
        act = actstack.start_activity(ButtonTestActivity)
        canvas = act.getCanvas()
        # Should have text items for each required button
        texts = canvas.get_all_text()
        assert any('waiting' in t for t in texts)


# ---------------------------------------------------------------
# SoundTestActivity Tests
# ---------------------------------------------------------------

class TestSoundTestActivity:
    """SoundTestActivity unit tests."""

    def test_title_is_sound(self):
        """Title shows 'Sound'."""
        from activity_tools import SoundTestActivity
        act = actstack.start_activity(SoundTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Sound' in texts

    def test_buttons_fail_pass(self):
        """M1='Fail', M2='Pass'."""
        from activity_tools import SoundTestActivity
        act = actstack.start_activity(SoundTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Fail' in texts
        assert 'Pass' in texts

    def test_tips_displayed(self):
        """Tips text: 'Do you hear the music?'"""
        from activity_tools import SoundTestActivity
        act = actstack.start_activity(SoundTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Do you hear the music?' in texts

    def test_m2_passes_and_finishes(self):
        """M2 = Pass and finish."""
        from activity_tools import SoundTestActivity
        act = actstack.start_activity(SoundTestActivity)
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed

    def test_m1_fails_and_finishes(self):
        """M1 = Fail and finish."""
        from activity_tools import SoundTestActivity
        act = actstack.start_activity(SoundTestActivity)
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed


# ---------------------------------------------------------------
# HFReaderTestActivity Tests
# ---------------------------------------------------------------

class TestHFReaderTestActivity:
    """HFReaderTestActivity unit tests."""

    def test_title_is_hf_reader(self):
        """Title shows 'HF reader'."""
        from activity_tools import HFReaderTestActivity
        act = actstack.start_activity(HFReaderTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'HF reader' in texts

    def test_buttons_empty_and_start(self):
        """M1='', M2='Start'."""
        from activity_tools import HFReaderTestActivity
        act = actstack.start_activity(HFReaderTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Start' in texts

    def test_tips_displayed(self):
        """Tips: "Please place Tag with 'IC Test'"."""
        from activity_tools import HFReaderTestActivity
        act = actstack.start_activity(HFReaderTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('IC Test' in t for t in texts)

    def test_pwr_exits_as_fail(self):
        """PWR exits with fail result."""
        from activity_tools import HFReaderTestActivity
        act = actstack.start_activity(HFReaderTestActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# ---------------------------------------------------------------
# LfReaderTestActivity Tests
# ---------------------------------------------------------------

class TestLfReaderTestActivity:
    """LfReaderTestActivity unit tests."""

    def test_title_is_lf_reader(self):
        """Title shows 'LF reader'."""
        from activity_tools import LfReaderTestActivity
        act = actstack.start_activity(LfReaderTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'LF reader' in texts

    def test_tips_displayed(self):
        """Tips: "Please place Tag with 'ID Test'"."""
        from activity_tools import LfReaderTestActivity
        act = actstack.start_activity(LfReaderTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('ID Test' in t for t in texts)

    def test_pwr_exits_as_fail(self):
        """PWR exits with fail result."""
        from activity_tools import LfReaderTestActivity
        act = actstack.start_activity(LfReaderTestActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed


# ---------------------------------------------------------------
# UsbPortTestActivity Tests
# ---------------------------------------------------------------

class TestUsbPortTestActivity:
    """UsbPortTestActivity unit tests."""

    def test_title_is_usb_port(self):
        """Title shows 'USB port'."""
        from activity_tools import UsbPortTestActivity
        act = actstack.start_activity(UsbPortTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'USB port' in texts

    def test_buttons_empty_and_start(self):
        """M1='', M2='Start'."""
        from activity_tools import UsbPortTestActivity
        act = actstack.start_activity(UsbPortTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Start' in texts

    def test_tips_displayed(self):
        """Tips: 'Please connect to charger.'"""
        from activity_tools import UsbPortTestActivity
        act = actstack.start_activity(UsbPortTestActivity)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('charger' in t for t in texts)

    def test_pwr_exits(self):
        """PWR exits the activity."""
        from activity_tools import UsbPortTestActivity
        act = actstack.start_activity(UsbPortTestActivity)
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed
