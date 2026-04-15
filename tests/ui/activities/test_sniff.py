"""Tests for SniffActivity.

Validates against the exhaustive binary extraction in
docs/UI_Mapping/05_sniff/V1090_SNIFF_FLOW_COMPLETE.md.

Ground truth:
    SniffActivity:
    - Title: "Sniff TRF" + "1/1" (separate text items, resources key: sniff_notag)
    - 5 sniff types on 1 page:
        1. 14A Sniff   -> hf 14a sniff
        2. 14B Sniff   -> hf 14b sniff
        3. iclass Sniff -> hf iclass sniff
        4. Topaz Sniff  -> hf topaz sniff
        5. T5577 Sniff  -> lf t55xx sniff
    - States: TYPE_SELECT -> INSTRUCTION -> SNIFFING -> RESULT
    - TYPE_SELECT: no softkey labels, UP/DOWN scroll, M2/OK -> INSTRUCTION
    - INSTRUCTION: M1="Start", M2="Finish" (dimmed), UP/DOWN pages, M1 -> SNIFFING
    - SNIFFING: M1="Start"(dimmed) M2="Finish"(active), toast overlay
    - RESULT: M1="Start" M2="Save", trace display
    - T5577 auto-finishes on data from lf t55xx sniff
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


def _create_sniff(bundle=None):
    """Start a SniffActivity and return it."""
    from activity_main import SniffActivity
    act = actstack.start_activity(SniffActivity, bundle)
    return act


# ===============================================================
# SniffActivity -- Creation & Layout
# ===============================================================

class TestSniffCreation:
    """SniffActivity initial state tests."""

    def test_title_sniff_trf(self):
        """Title bar must contain 'Sniff TRF' (resources key: sniff_notag)."""
        act = _create_sniff()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Sniff TRF' in t for t in texts)

    def test_title_has_page_indicator(self):
        """Title shows page indicator as separate text item (setTitle splits 'Sniff TRF 1/1')."""
        act = _create_sniff()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # setTitle splits "Sniff TRF 1/1" into "Sniff TRF" + "1/1" as separate text items
        assert any('1/' in t for t in texts)

    def test_5_sniff_types(self):
        """List has exactly 5 sniff type items (may span 2 pages)."""
        act = _create_sniff()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # First page shows at least the first 4 items
        assert any('14A Sniff' in t for t in texts)
        assert any('14B Sniff' in t for t in texts)
        assert any('iclass Sniff' in t for t in texts)
        assert any('Topaz Sniff' in t for t in texts)
        # 5th item may be on page 2 if 4 items/page -- scroll to it
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        canvas2 = act.getCanvas()
        texts2 = canvas2.get_all_text()
        assert any('T5577 Sniff' in t for t in texts2)

    def test_type_labels_numbered(self):
        """Each type label has a number prefix: 1., 2., 3., 4."""
        act = _create_sniff()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('1.' in t for t in texts)
        assert any('2.' in t for t in texts)
        assert any('3.' in t for t in texts)
        assert any('4.' in t for t in texts)

    def test_buttons_no_labels_in_type_select(self):
        """TYPE_SELECT has no softkey labels (empty strings)."""
        act = _create_sniff()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Ground truth: TYPE_SELECT has setLeftButton('') and setRightButton('')
        # No "Back" or "Start" labels in this state
        assert 'Back' not in texts
        assert 'Start' not in texts

    def test_initial_state_type_select(self):
        """Activity starts in TYPE_SELECT state."""
        act = _create_sniff()
        assert act.state == act.STATE_TYPE_SELECT

    def test_listview_created(self):
        """ListView widget is created."""
        act = _create_sniff()
        assert act._listview is not None


# ===============================================================
# SniffActivity -- Key Events in TYPE_SELECT
# ===============================================================

class TestSniffTypeSelect:
    """SniffActivity key events in TYPE_SELECT state."""

    def test_m1_back(self):
        """M1 in TYPE_SELECT finishes the activity."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_pwr_exit(self):
        """PWR in TYPE_SELECT finishes the activity."""
        act = _create_sniff()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_down_scrolls(self):
        """DOWN scrolls selection in type list."""
        act = _create_sniff()
        assert act._listview.selection() == 0
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 1

    def test_up_scrolls(self):
        """UP scrolls selection in type list."""
        act = _create_sniff()
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_UP)
        assert act._listview.selection() == 1

    def test_m2_shows_instruction(self):
        """M2 transitions to INSTRUCTION state (not directly to SNIFFING)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_INSTRUCTION

    def test_ok_shows_instruction(self):
        """OK transitions to INSTRUCTION state (same as M2)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_INSTRUCTION


# ===============================================================
# SniffActivity -- INSTRUCTION state
# ===============================================================

class TestSniffInstructionState:
    """SniffActivity INSTRUCTION state tests."""

    def test_instruction_buttons_start_finish(self):
        """INSTRUCTION state shows M1='Start', M2='Finish'."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # TYPE_SELECT -> INSTRUCTION
        assert act.state == act.STATE_INSTRUCTION
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Start' in texts
        assert 'Finish' in texts

    def test_instruction_pwr_back_to_select(self):
        """PWR during INSTRUCTION returns to TYPE_SELECT."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_TYPE_SELECT

    def test_instruction_shows_step_text(self):
        """INSTRUCTION state shows step instruction text."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Step 1' in t for t in texts)

    def test_instruction_title_page_indicator(self):
        """INSTRUCTION title shows page indicator (1/4 for HF, 1/1 for T5577)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION (HF: 4 pages)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('1/4' in t for t in texts)

    def test_selected_type_14a(self):
        """Default selection (0) maps to type '14a'."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        assert act._selected_type_id == '14a'

    def test_selected_type_t5577(self):
        """Selecting item 4 maps to type '125k'."""
        act = _create_sniff()
        for _ in range(4):
            act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        assert act._selected_type_id == '125k'


# ===============================================================
# SniffActivity -- SNIFFING state
# ===============================================================

class TestSniffSniffingState:
    """SniffActivity SNIFFING state tests.

    Reaching SNIFFING: M2 (TYPE_SELECT->INSTRUCTION) then M1 (INSTRUCTION->SNIFFING).
    """

    def test_sniffing_state_shows_toast(self):
        """SNIFFING state shows 'Sniffing in progress...' toast."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING (M1="Start" in INSTRUCTION)
        assert act.state == act.STATE_SNIFFING
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Sniffing in progress...' in texts

    def test_sniffing_sets_flag(self):
        """sniffing property is True during sniff."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        assert act.sniffing is True

    def test_sniffing_buttons_start_finish(self):
        """During sniff: M1='Start'(inactive), M2='Finish'(active)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Start' in texts
        assert 'Finish' in texts

    def test_sniffing_m2_goes_to_result(self):
        """M2 during SNIFFING stops and shows result."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        assert act.state == act.STATE_SNIFFING
        act.onKeyEvent(KEY_M2)  # finish sniff -> RESULT
        assert act.state == act.STATE_RESULT

    def test_sniffing_m1_exits(self):
        """M1 during SNIFFING stops and exits."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        assert act.state == act.STATE_SNIFFING
        act.onKeyEvent(KEY_M1)  # M1 in SNIFFING -> stopSniff + finish
        assert act.life.destroyed

    def test_sniffing_pwr_blocked_by_busy(self):
        """PWR during SNIFFING is blocked (busy state + toast dismiss)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        # PWR first dismisses toast, then blocked by busy state
        act.onKeyEvent(KEY_PWR)
        assert act.state == act.STATE_SNIFFING

    def test_sniffing_hides_list(self):
        """Entering SNIFFING sets sniffing flag (list was already hidden in INSTRUCTION)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        assert act.sniffing is True

    def test_sniffing_title_no_page(self):
        """During sniff, title is 'Sniff TRF' (no page indicator change from instruction)."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Title should contain "Sniff TRF"
        assert any('Sniff TRF' in t for t in texts)


# ===============================================================
# SniffActivity -- RESULT state
# ===============================================================

class TestSniffResultState:
    """SniffActivity RESULT state tests.

    HF path: M2->M1->M2 reaches RESULT, but buttons/TraceLen are set
    asynchronously via BG thread (_do_hf_parse -> _finishHfResult).
    T5577 path: _showT5577Result is synchronous — buttons/TraceLen set immediately.

    Tests that need to verify buttons/text use the T5577 path (synchronous).
    Tests that only check state transitions use the HF path.
    """

    def _reach_result_hf(self):
        """Navigate to RESULT via HF 14A (default selection). Returns activity."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        act.onKeyEvent(KEY_M2)  # -> RESULT (HF: async render)
        return act

    def _reach_result_t5577(self):
        """Navigate to RESULT via T5577 onData (synchronous render). Returns activity."""
        act = _create_sniff()
        for _ in range(4):
            act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION (T5577: 1 page)
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        # T5577 auto-finishes via onData; simulate it
        act.onData('lf t55xx sniff', 'Reading 0 bytes from device memory')
        return act

    def test_result_state_buttons(self):
        """RESULT state shows M1='Start', M2='Save' (via T5577 synchronous path)."""
        act = self._reach_result_t5577()
        assert act.state == act.STATE_RESULT
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Start' in texts
        assert 'Save' in texts

    def test_result_display_trace_len(self):
        """RESULT state shows trace length text (via T5577 synchronous path)."""
        act = self._reach_result_t5577()
        assert act.state == act.STATE_RESULT
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('TraceLen' in t for t in texts)

    def test_result_pwr_back_to_select(self):
        """PWR in RESULT returns to TYPE_SELECT."""
        act = self._reach_result_t5577()
        act.onKeyEvent(KEY_PWR)  # back
        assert act.state == act.STATE_TYPE_SELECT

    def test_result_m2_saves(self):
        """M2 in RESULT shows 'Trace file saved' toast."""
        act = self._reach_result_t5577()
        act.onKeyEvent(KEY_M2)  # save
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Trace file' in t for t in texts)

    def test_result_ok_saves(self):
        """OK in RESULT saves (same as M2)."""
        act = self._reach_result_t5577()
        act.onKeyEvent(KEY_OK)  # save
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Trace file' in t for t in texts)

    def test_hf_result_state_transition(self):
        """HF M2 during SNIFFING transitions to RESULT state."""
        act = self._reach_result_hf()
        assert act.state == act.STATE_RESULT


# ===============================================================
# SniffActivity -- onData callback (T5577 auto-finish)
# ===============================================================

class TestSniffOnData:
    """SniffActivity onData callback tests."""

    def test_125k_finished_auto_stops(self):
        """T5577 data in onData auto-stops and shows result."""
        act = _create_sniff()
        # Select T5577 (index 4)
        for _ in range(4):
            act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        assert act.state == act.STATE_SNIFFING

        # Simulate PM3 data callback with T5577 data
        act.onData('lf t55xx sniff', 'Reading 42259 bytes from device memory')
        assert act.state == act.STATE_RESULT
        assert act.sniffing is False

    def test_normal_data_stays_sniffing(self):
        """Normal HF data during sniff does not change state."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_M1)  # -> SNIFFING
        assert act.state == act.STATE_SNIFFING
        act.onData('hf 14a sniff', 'some trace data')
        assert act.state == act.STATE_SNIFFING


# ===============================================================
# SniffActivity -- State restoration
# ===============================================================

class TestSniffStateRestore:
    """SniffActivity state restoration after sniff."""

    def test_back_to_select_restores_title(self):
        """Returning to TYPE_SELECT restores title 'Sniff TRF' and page indicator."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_PWR)  # back to TYPE_SELECT
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # setTitle splits into "Sniff TRF" + "N/N" as separate items
        assert any('Sniff TRF' in t for t in texts)
        assert any('/' in t for t in texts)

    def test_back_to_select_restores_no_labels(self):
        """Returning to TYPE_SELECT restores empty softkey labels."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_PWR)  # back to TYPE_SELECT
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # TYPE_SELECT has no softkey labels (ground truth: setLeftButton(''))
        assert 'Start' not in texts
        assert 'Back' not in texts

    def test_back_to_select_restores_list(self):
        """Returning to TYPE_SELECT shows the type list again."""
        act = _create_sniff()
        act.onKeyEvent(KEY_M2)  # -> INSTRUCTION
        act.onKeyEvent(KEY_PWR)  # back to TYPE_SELECT
        assert act.state == act.STATE_TYPE_SELECT
        # List should be shown again
        assert act._listview is not None
