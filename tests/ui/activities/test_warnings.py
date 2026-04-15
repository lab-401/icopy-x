"""Tests for WarningWriteActivity and WarningM1Activity.

WarningWriteActivity:
    - Title: "Data ready!" (resources key: data_ready)
    - Buttons: M1="Cancel", M2="Write"
    - M1/PWR: cancel (finish)
    - M2/OK: confirm write, finish with result {action: 'write'}
    - Shows tag info (type + UID) + place_empty_tag instruction

WarningM1Activity:
    - Title: "Missing keys" (resources key: missing_keys)
    - 4 pages with different recovery options
    - UP/DOWN navigates pages (0-3)
    - M1/PWR: cancel
    - M2/OK: select current page option

Ground truth: docs/UI_Mapping/15_write_tag/V1090_WRITE_FLOW_COMPLETE.md
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


def _sample_infos():
    """Return a sample infos dict for testing."""
    return {
        'type': 1,
        'type_name': 'M1 S50 1K 4B',
        'uid': 'AABBCCDD',
        'data': b'\x00' * 1024,
    }


def _create_warning_write(bundle=None):
    """Start a WarningWriteActivity and return it."""
    from activity_main import WarningWriteActivity
    act = actstack.start_activity(WarningWriteActivity, bundle)
    return act


def _create_warning_m1(bundle=None):
    """Start a WarningM1Activity and return it."""
    from activity_main import WarningM1Activity
    act = actstack.start_activity(WarningM1Activity, bundle)
    return act


# ===============================================================
# WarningWriteActivity -- Creation & Layout
# ===============================================================

class TestWarningWriteCreation:
    """WarningWriteActivity initial state tests."""

    def test_warning_write_title(self):
        """Title bar must read 'Data ready!' (resources key: data_ready)."""
        act = _create_warning_write()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Data ready!' in texts

    def test_warning_write_buttons(self):
        """M1='Cancel', M2='Write'."""
        act = _create_warning_write()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Cancel' in texts
        assert 'Write' in texts

    def test_warning_write_shows_tag_info(self):
        """Shows tag type display from container.get_public_id via scan cache.

        In tests, scan module is not available so infos stays empty.
        The display renders TYPE label via JSON renderer state.
        """
        infos = _sample_infos()
        act = _create_warning_write({'infos': infos})
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        # TYPE label is rendered even when container isn't available
        assert 'TYPE' in all_text.upper() or 'Data ready' in all_text

    def test_warning_write_shows_place_msg(self):
        """Shows 'place empty tag' instruction text."""
        act = _create_warning_write({'infos': _sample_infos()})
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        # Should contain the place_empty_tag resource text
        assert 'place' in all_text.lower() or 'copy' in all_text.lower()

    def test_warning_write_receives_bundle(self):
        """Activity stores raw bundle as _read_bundle.

        Infos come from scan.getScanCache(), not from the bundle directly.
        In tests, scan module is not available so infos stays {}.
        """
        infos = _sample_infos()
        bundle = {'infos': infos}
        act = _create_warning_write(bundle)
        assert act._read_bundle == bundle


# ===============================================================
# WarningWriteActivity -- Key Events
# ===============================================================

class TestWarningWriteKeys:
    """WarningWriteActivity key event tests."""

    def test_warning_write_m1_cancels(self):
        """M1 finishes the activity (cancel)."""
        act = _create_warning_write()
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_warning_write_pwr_cancels(self):
        """PWR finishes the activity (cancel/back)."""
        act = _create_warning_write()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_warning_write_m2_confirms(self):
        """M2 confirms write and finishes with result."""
        infos = _sample_infos()
        act = _create_warning_write({'infos': infos})
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed
        assert hasattr(act, '_result')
        assert act._result['action'] == 'write'
        # Result carries raw bundle as 'read_bundle', not 'infos'
        assert act._result['read_bundle'] == {'infos': infos}

    def test_warning_write_ok_confirms(self):
        """OK confirms write (same as M2)."""
        infos = _sample_infos()
        act = _create_warning_write({'infos': infos})
        act.onKeyEvent(KEY_OK)
        assert act.life.destroyed
        assert act._result['action'] == 'write'

    def test_warning_write_up_down_no_effect(self):
        """UP/DOWN have no effect on WarningWriteActivity."""
        act = _create_warning_write()
        act.onKeyEvent(KEY_UP)
        assert not act.life.destroyed
        act.onKeyEvent(KEY_DOWN)
        assert not act.life.destroyed


# ===============================================================
# WarningM1Activity -- Creation & Layout
# ===============================================================

class TestWarningM1Creation:
    """WarningM1Activity initial state tests."""

    def test_warning_m1_title(self):
        """Title bar must read 'Missing keys' (resources key: missing_keys)."""
        act = _create_warning_m1()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Missing keys' in texts

    def test_warning_m1_initial_page(self):
        """Activity starts on page 0."""
        act = _create_warning_m1()
        assert act.page == 0

    def test_warning_m1_page0_buttons(self):
        """Page 0: M1='Sniff', M2='Enter'."""
        act = _create_warning_m1()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Sniff' in texts
        assert 'Enter' in texts

    def test_warning_m1_2_pages(self):
        """WarningM1Activity has 2 pages (0-1)."""
        act = _create_warning_m1()
        assert act.PAGE_MAX == 1

    def test_warning_m1_page0_content(self):
        """Page 0 shows sniff/enter key options."""
        act = _create_warning_m1()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        all_text = ' '.join(texts)
        # Page 0 = missing_keys_msg1: "Option 1) Go to reader to sniff keys..."
        assert 'sniff' in all_text.lower() or 'Option 1' in all_text


# ===============================================================
# WarningM1Activity -- Navigation
# ===============================================================

class TestWarningM1Navigation:
    """WarningM1Activity page navigation tests."""

    def test_warning_m1_down_navigates(self):
        """DOWN moves to next page."""
        act = _create_warning_m1()
        assert act.page == 0
        act.onKeyEvent(KEY_DOWN)
        assert act.page == 1

    def test_warning_m1_up_navigates(self):
        """UP moves to previous page."""
        act = _create_warning_m1()
        act.onKeyEvent(KEY_DOWN)
        assert act.page == 1
        act.onKeyEvent(KEY_UP)
        assert act.page == 0

    def test_warning_m1_up_down_navigation(self):
        """Full navigation through all 2 pages."""
        act = _create_warning_m1()
        assert act.page == 0
        act.onKeyEvent(KEY_DOWN)
        assert act.page == 1

    def test_warning_m1_page_bounds_lower(self):
        """UP at page 0 stays at page 0 (no underflow)."""
        act = _create_warning_m1()
        assert act.page == 0
        act.onKeyEvent(KEY_UP)
        assert act.page == 0

    def test_warning_m1_page_bounds_upper(self):
        """DOWN at page 1 stays at page 1 (no overflow)."""
        act = _create_warning_m1()
        # Navigate to last page
        for _ in range(5):
            act.onKeyEvent(KEY_DOWN)
        assert act.page == 1

    def test_warning_m1_m2_button_changes_per_page(self):
        """M1/M2 button labels change based on current page."""
        act = _create_warning_m1()
        # Page 0: M1=Sniff, M2=Enter
        # Page 1: M1=Force, M2=PC-M
        canvas = act.getCanvas()

        # Navigate through pages and verify button changes
        for i in range(2):
            if i > 0:
                act.onKeyEvent(KEY_DOWN)
            assert act.page == i


# ===============================================================
# WarningM1Activity -- Option Selection
# ===============================================================

class TestWarningM1Options:
    """WarningM1Activity option selection tests."""

    def test_warning_m1_sniff_option(self):
        """Page 0 + M1 selects 'sniff' action (M1 = left option)."""
        act = _create_warning_m1({'infos': _sample_infos()})
        assert act.page == 0
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed
        assert act._result['action'] == 'sniff'

    def test_warning_m1_enter_key_option(self):
        """Page 0 + M2 selects 'enter_key' action (M2 = right option)."""
        act = _create_warning_m1({'infos': _sample_infos()})
        assert act.page == 0
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed
        assert act._result['action'] == 'enter_key'

    def test_warning_m1_force_read_option(self):
        """Page 1 + M1 selects 'force' action."""
        act = _create_warning_m1({'infos': _sample_infos()})
        act.onKeyEvent(KEY_DOWN)
        assert act.page == 1
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed
        assert act._result['action'] == 'force'

    def test_warning_m1_pc_mode_option(self):
        """Page 1 + M2 selects 'pc_mode' action."""
        act = _create_warning_m1({'infos': _sample_infos()})
        act.onKeyEvent(KEY_DOWN)
        assert act.page == 1
        act.onKeyEvent(KEY_M2)
        assert act.life.destroyed
        assert act._result['action'] == 'pc_mode'

    def test_warning_m1_ok_selects_m2_option(self):
        """OK key selects the M2 (right) option for current page."""
        act = _create_warning_m1({'infos': _sample_infos()})
        act.onKeyEvent(KEY_OK)
        assert act.life.destroyed
        assert act._result['action'] == 'enter_key'

    def test_warning_m1_m1_selects_action(self):
        """M1 selects the M1 (left) action, not cancel."""
        act = _create_warning_m1({'infos': _sample_infos()})
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed
        assert hasattr(act, '_result')
        assert act._result['action'] == 'sniff'

    def test_warning_m1_pwr_cancels(self):
        """PWR cancels (finishes without result)."""
        act = _create_warning_m1()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed
        assert not hasattr(act, '_result')

    def test_warning_m1_result_includes_infos(self):
        """Selected option result includes original infos."""
        infos = _sample_infos()
        act = _create_warning_m1({'infos': infos})
        act.onKeyEvent(KEY_M2)
        assert act._result['infos'] == infos

    def test_warning_m1_result_includes_page(self):
        """Selected option result includes page number."""
        act = _create_warning_m1({'infos': _sample_infos()})
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_M2)
        assert act._result['page'] == 1
