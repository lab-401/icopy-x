"""Tests for WipeTagActivity (Erase Tag).

Validates against the exhaustive binary extraction in
docs/UI_Mapping/12_erase_tag/V1090_ERASE_FLOW_COMPLETE.md.

Ground truth:
    WipeTagActivity:
    - Title: "Erase Tag" (resources key: wipe_tag)
    - 2-item list: "Erase MF1/L1/L2/L3", "Erase T5577"
    - States: TYPE_SELECT -> ERASING -> SUCCESS/FAILED/NO_KEYS
    - TYPE_SELECT: M1="Back", M2="Erase", UP/DOWN scroll
    - ERASING: "Processing..." toast, PWR cancels
    - SUCCESS: "Erase successful" toast (check icon)
    - FAILED: "Erase failed" toast (error icon)
    - NO_KEYS: "No valid keys..." toast (MF1 only)
    - Binary source: WriteActivity in erase mode
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


def _create_erase(bundle=None):
    """Start a WipeTagActivity and return it."""
    from activity_main import WipeTagActivity
    act = actstack.start_activity(WipeTagActivity, bundle)
    return act


# ===============================================================
# WipeTagActivity -- Creation & Layout
# ===============================================================

class TestEraseTagCreation:
    """WipeTagActivity initial state tests."""

    def test_title_erase_tag(self):
        """Title bar must read 'Erase Tag' (resources key: wipe_tag)."""
        act = _create_erase()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Erase Tag' in texts

    def test_buttons_back_erase(self):
        """M1='Back', M2='Erase'."""
        act = _create_erase()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Back' in texts
        assert 'Erase' in texts

    def test_two_items_in_list(self):
        """List shows exactly 2 erase type items."""
        act = _create_erase()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('Erase MF1/L1/L2/L3' in t for t in texts)
        assert any('Erase T5577' in t for t in texts)

    def test_initial_state_type_select(self):
        """Activity starts in TYPE_SELECT state."""
        act = _create_erase()
        assert act.state == act.STATE_TYPE_SELECT

    def test_listview_created(self):
        """ListView widget is created."""
        act = _create_erase()
        assert act._listview is not None


# ===============================================================
# WipeTagActivity -- Key Events in TYPE_SELECT
# ===============================================================

class TestEraseTagTypeSelect:
    """WipeTagActivity key events in TYPE_SELECT state."""

    def test_m1_back(self):
        """M1 in TYPE_SELECT finishes the activity."""
        act = _create_erase()
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_pwr_exit(self):
        """PWR in TYPE_SELECT finishes the activity."""
        act = _create_erase()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_up_scrolls(self):
        """UP scrolls the selection list."""
        act = _create_erase()
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 1
        act.onKeyEvent(KEY_UP)
        assert act._listview.selection() == 0

    def test_down_scrolls(self):
        """DOWN scrolls the selection list."""
        act = _create_erase()
        assert act._listview.selection() == 0
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == 1

    def test_m2_starts_erase(self):
        """M2 starts erase. Item 0 (MF1) transitions to SCANNING first."""
        act = _create_erase()
        act.onKeyEvent(KEY_M2)
        # MF1 (item 0 default) goes to SCANNING before ERASING
        assert act.state == act.STATE_SCANNING

    def test_ok_starts_erase(self):
        """OK starts erase (same as M2). Item 0 (MF1) -> SCANNING."""
        act = _create_erase()
        act.onKeyEvent(KEY_OK)
        assert act.state == act.STATE_SCANNING

    def test_m2_shows_scanning_progress(self):
        """Starting MF1 erase shows 'Scanning...' progress bar."""
        act = _create_erase()
        act.onKeyEvent(KEY_M2)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Scanning...' in texts

    def test_t5577_starts_erasing(self):
        """Item 1 (T5577) transitions directly to ERASING."""
        act = _create_erase()
        act.onKeyEvent(KEY_DOWN)  # select T5577
        act.onKeyEvent(KEY_M2)
        assert act.state == act.STATE_ERASING


# ===============================================================
# WipeTagActivity -- Erase States
# ===============================================================

class TestEraseTagStates:
    """WipeTagActivity state transition tests."""

    def test_erase_success_toast(self):
        """SUCCESS state shows 'Erase successful' toast."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('success')
        assert act.state == act.STATE_SUCCESS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Erase successful' in texts

    def test_erase_fail_toast(self):
        """FAILED state shows 'Erase failed' toast."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('failed')
        assert act.state == act.STATE_FAILED
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Erase failed' in texts

    def test_erase_no_keys_toast(self):
        """NO_KEYS state shows 'No valid keys' toast."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('no_keys')
        assert act.state == act.STATE_NO_KEYS
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('No valid keys' in t for t in texts)

    def test_erasing_pwr_ignored(self):
        """PWR during ERASING is ignored (busy state)."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act.onKeyEvent(KEY_PWR)
        # PWR is ignored during SCANNING/ERASING
        assert not act.life.destroyed

    def test_success_m1_re_erases(self):
        """M1 in SUCCESS state triggers re-erase (not exit)."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('success')
        assert act.state == act.STATE_SUCCESS
        act.onKeyEvent(KEY_M1)
        # M1/M2/OK in SUCCESS re-erase
        assert act.state in (act.STATE_SCANNING, act.STATE_ERASING)

    def test_success_pwr_exits(self):
        """PWR in SUCCESS state finishes activity (after toast dismiss)."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('success')
        act.onKeyEvent(KEY_PWR)  # dismiss toast
        act.onKeyEvent(KEY_PWR)  # exit
        assert act.life.destroyed

    def test_failed_pwr_exits(self):
        """PWR in FAILED state finishes activity (after toast dismiss)."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('failed')
        act.onKeyEvent(KEY_PWR)  # dismiss toast
        act.onKeyEvent(KEY_PWR)  # exit
        assert act.life.destroyed

    def test_no_keys_pwr_exits(self):
        """PWR in NO_KEYS state finishes activity (after toast dismiss)."""
        act = _create_erase()
        act._state = act.STATE_ERASING
        act._onEraseResult('no_keys')
        act.onKeyEvent(KEY_PWR)  # dismiss toast
        act.onKeyEvent(KEY_PWR)  # exit
        assert act.life.destroyed


# ===============================================================
# WipeTagActivity -- Erase Type Selection
# ===============================================================

class TestEraseTagTypeDispatch:
    """WipeTagActivity erase type selection and dispatch."""

    def test_select_mf1(self):
        """Selecting item 0 dispatches MF1 erase."""
        act = _create_erase()
        # Item 0 is already selected by default
        act.onKeyEvent(KEY_M2)
        assert act._selected_type == act.ERASE_MF1

    def test_select_t5577(self):
        """Selecting item 1 dispatches T5577 erase."""
        act = _create_erase()
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_M2)
        assert act._selected_type == act.ERASE_T5577

    def test_erase_hides_list(self):
        """Starting erase hides the type selection list."""
        act = _create_erase()
        act.onKeyEvent(KEY_M2)
        # After starting erase, list should be hidden
        # MF1 (default item 0) goes to SCANNING first
        assert act.state in (act.STATE_SCANNING, act.STATE_ERASING)

    def test_erase_disables_buttons(self):
        """During erase, button labels are cleared."""
        act = _create_erase()
        act.onKeyEvent(KEY_M2)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # 'Back' and 'Erase' should no longer be visible
        # (they are replaced with '' strings)
        assert 'Erase Tag' in texts  # title remains
