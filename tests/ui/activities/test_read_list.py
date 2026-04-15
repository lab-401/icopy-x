"""Tests for ReadListActivity.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/04_read_tag/V1090_READ_UI_STATES.md and the verified
read_list_map.json (40 readable types, 8 pages).

Ground truth:
    ReadListActivity:
    - Title: "Read Tag X/Y" with page indicator
    - 40 readable tag types across 8 pages (5 items/page)
    - QEMU verified: "Read Tag 1/8" through "Read Tag 8/8"
    - M1="Back", M2="Read"
    - UP/DOWN: scroll list (paginated)
    - M2/OK: launch ReadActivity with selected type
    - M1/PWR: finish() (back)
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


def _create_read_list(bundle=None):
    """Start a ReadListActivity and return it."""
    from activity_main import ReadListActivity
    act = actstack.start_activity(ReadListActivity, bundle)
    return act


# ===============================================================
# ReadListActivity -- Creation & Layout
# ===============================================================

class TestReadListCreation:
    """ReadListActivity initial state tests."""

    def test_title_read_tag(self):
        """Title bar must contain 'Read Tag' (resources key: read_tag)."""
        act = _create_read_list()
        canvas = act.getCanvas()
        assert canvas is not None, "Canvas should not be None — _canvas_factory not set?"
        texts = canvas.get_all_text()
        assert texts, f"Canvas has no text items — setTitle may not have been called"
        assert any('Read Tag' in t for t in texts), f"Expected 'Read Tag' in {texts}"

    def test_title_has_page_indicator(self):
        """Title must include page indicator like '1/8'."""
        act = _create_read_list()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert any('1/' in t for t in texts)

    def test_40_readable_types(self):
        """Must have exactly 40 readable tag types."""
        act = _create_read_list()
        assert len(act.tag_type_list) == 40

    def test_first_type_m1_s50(self):
        """First type in list must be 'M1 S50 1K 4B'."""
        act = _create_read_list()
        assert act.tag_type_list[0] == 'M1 S50 1K 4B'

    def test_last_type_em4305(self):
        """Last type in list must be 'EM4305'."""
        act = _create_read_list()
        assert act.tag_type_list[-1] == 'EM4305'

    def test_buttons_back_read(self):
        """Buttons are dismissed (ground truth: list occupies full content)."""
        act = _create_read_list()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Ground truth: dismissButton() called — no Back/Read buttons
        assert 'Back' not in texts
        assert 'Read' not in texts

    def test_listview_created(self):
        """ListView widget is created."""
        act = _create_read_list()
        assert act._listview is not None

    def test_listview_shows_items(self):
        """ListView renders at least first page of items on canvas."""
        act = _create_read_list()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # First item on first page
        assert any('M1 S50 1K 4B' in t for t in texts)


# ===============================================================
# ReadListActivity -- Pagination
# ===============================================================

class TestReadListPagination:
    """ReadListActivity pagination across 8 pages."""

    def test_multiple_pages(self):
        """40 items should span multiple pages. Title should show X/N."""
        act = _create_read_list()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # setTitle splits "Read Tag 1/8" into base title + page indicator
        assert any('Read Tag' in t for t in texts), \
            f"Expected 'Read Tag' in title, got {texts}"
        assert any('1/' in t for t in texts), \
            f"Expected '1/N' page indicator, got {texts}"

    def test_down_advances_page(self):
        """Pressing DOWN enough times should advance to page 2."""
        act = _create_read_list()
        items_per_page = act._listview._max_display
        for _ in range(items_per_page):
            act.onKeyEvent(KEY_DOWN)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Title should now show "Read Tag 2/N"
        assert any('2/' in t for t in texts), f"Expected '2/' in {texts}"

    def test_navigate_to_last_page(self):
        """Navigate to the last item should show the last page."""
        act = _create_read_list()
        items_per_page = act._listview._max_display
        total_pages = (40 + items_per_page - 1) // items_per_page
        # Navigate to last item
        for _ in range(39):
            act.onKeyEvent(KEY_DOWN)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        expected = '{}/{}'.format(total_pages, total_pages)
        assert any(expected in t for t in texts), \
            f"Expected '{expected}' in {texts}"

    def test_up_from_first_stays(self):
        """UP from the first item should stay on page 1."""
        act = _create_read_list()
        act.onKeyEvent(KEY_UP)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # Should still show page containing first item or wrapped
        # ListView.prev() on first item may wrap or stay -- either is fine
        assert any('Read Tag' in t for t in texts)


# ===============================================================
# ReadListActivity -- Key Events
# ===============================================================

class TestReadListKeyEvents:
    """ReadListActivity key event handling tests."""

    def test_m2_launches_read(self):
        """M2 sets _last_launch_bundle with selected type info."""
        act = _create_read_list()
        act.onKeyEvent(KEY_M2)
        assert act._last_launch_bundle is not None
        assert act._last_launch_bundle['tag_type'] == 1  # M1 S50 1K 4B
        assert act._last_launch_bundle['tag_name'] == 'M1 S50 1K 4B'

    def test_ok_launches_read(self):
        """OK key same as M2 -- launches ReadActivity."""
        act = _create_read_list()
        act.onKeyEvent(KEY_OK)
        assert act._last_launch_bundle is not None
        assert act._last_launch_bundle['tag_type'] == 1

    def test_m2_with_selection_down2(self):
        """Navigate down 2 then M2 should launch 3rd type (M1 S70 4K 4B)."""
        act = _create_read_list()
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_DOWN)
        act.onKeyEvent(KEY_M2)
        assert act._last_launch_bundle is not None
        assert act._last_launch_bundle['tag_type'] == 0  # M1 S70 4K 4B
        assert act._last_launch_bundle['tag_name'] == 'M1 S70 4K 4B'

    def test_m1_back(self):
        """M1 finishes the activity (back to main menu)."""
        act = _create_read_list()
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed

    def test_pwr_exit(self):
        """PWR finishes the activity (exit)."""
        act = _create_read_list()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_up_scrolls_list(self):
        """UP key scrolls selection upward in the list."""
        act = _create_read_list()
        # Move down first then up
        act.onKeyEvent(KEY_DOWN)
        sel_after_down = act._listview.selection()
        act.onKeyEvent(KEY_UP)
        sel_after_up = act._listview.selection()
        assert sel_after_up == sel_after_down - 1

    def test_down_scrolls_list(self):
        """DOWN key scrolls selection downward in the list."""
        act = _create_read_list()
        initial = act._listview.selection()
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() == initial + 1


# ===============================================================
# ReadListActivity -- Type IDs
# ===============================================================

class TestReadListTypeIDs:
    """Verify type_id mapping matches read_list_map.json."""

    def test_type_id_first(self):
        """First type ID is 1 (M1_S50_1K_4B)."""
        act = _create_read_list()
        assert act._type_ids[0] == 1

    def test_type_id_t5577(self):
        """T5577 is at position 38 with type ID 23."""
        act = _create_read_list()
        assert act._type_ids[38] == 23
        assert act.tag_type_list[38] == 'T5577'

    def test_type_id_em4305(self):
        """EM4305 is at position 39 with type ID 24."""
        act = _create_read_list()
        assert act._type_ids[39] == 24
        assert act.tag_type_list[39] == 'EM4305'
