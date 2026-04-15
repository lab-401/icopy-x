"""Comprehensive tests for ListView, BigTextListView, and createTag.

Target: ~35 tests covering item management, selection, pagination,
rendering coordinates/colors, callbacks, and BigTextListView.

All coordinate and color assertions are derived from UI_SPEC.md and
verified against the original firmware rendering under QEMU.
"""

import sys
import os
import math
import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import ListView, BigTextListView, createTag
from lib._constants import (
    SCREEN_W,
    CONTENT_Y0,
    LIST_ITEM_H,
    LIST_TEXT_X_NO_ICON,
    LIST_TEXT_X_WITH_ICON,
    LIST_TEXT_ANCHOR,
    SELECT_BG,
    SELECT_OUTLINE,
    SELECT_TEXT_COLOR,
    NORMAL_TEXT_COLOR,
)

# Import the MockCanvas from the UI conftest
from tests.ui.conftest import MockCanvas


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

@pytest.fixture
def canvas():
    """Fresh 240x240 MockCanvas."""
    return MockCanvas(width=240, height=240, bg='#222222')


@pytest.fixture
def lv(canvas):
    """A basic ListView shown with 5 items (fits on 1 page at 5-per-page)."""
    lv = ListView(canvas, items=['A', 'B', 'C', 'D', 'E'])
    lv.show()
    return lv


def _get_texts(canvas):
    """Extract all text strings currently on the canvas."""
    return canvas.get_all_text()


def _get_rects(canvas):
    """Return all rectangle items as list of (id, item_dict)."""
    return canvas.get_items_by_type('rectangle')


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


# =================================================================
# createTag
# =================================================================

class TestCreateTag:

    def test_format(self):
        """Tag format is 'ID:{classname}-{id}:{suffix}'."""

        class Dummy:
            pass

        obj = Dummy()
        tag = createTag(obj, 'bg')
        assert tag == f'ID:Dummy-{id(obj)}:bg'

    def test_unique_per_instance(self):
        """Different instances produce different tags."""

        class Dummy:
            pass

        a = Dummy()
        b = Dummy()
        assert createTag(a, 'text') != createTag(b, 'text')

    def test_empty_suffix(self):
        """Empty suffix is valid (used as uid prefix)."""

        class Dummy:
            pass

        obj = Dummy()
        tag = createTag(obj, '')
        assert tag == f'ID:Dummy-{id(obj)}:'


# =================================================================
# Item Management
# =================================================================

class TestListViewItemManagement:

    def test_set_items(self, canvas):
        lv = ListView(canvas)
        lv.setItems(['X', 'Y', 'Z'])
        assert lv.getSelection() == 'X'

    def test_add_item(self, canvas):
        lv = ListView(canvas)
        lv.setItems(['A'])
        lv.addItem('B')
        lv.setSelection(1)
        assert lv.getSelection() == 'B'

    def test_get_item_count(self, canvas):
        lv = ListView(canvas, items=['A', 'B', 'C'])
        assert lv.getPageCount() == 1  # 3 items, 4 per page -> 1 page
        assert lv.getItemCountOnPage(0) == 3

    def test_empty_list(self, canvas):
        lv = ListView(canvas)
        assert lv.selection() == 0
        assert lv.getSelection() is None
        assert lv.getPageCount() == 0

    def test_set_items_clears_previous(self, canvas):
        lv = ListView(canvas, items=['Old1', 'Old2'])
        lv.setSelection(1)
        lv.setItems(['New1', 'New2', 'New3'])
        # Selection resets to 0
        assert lv.selection() == 0
        assert lv.getSelection() == 'New1'


# =================================================================
# Selection
# =================================================================

class TestListViewSelection:

    def test_initial_selection_is_zero(self, canvas):
        lv = ListView(canvas, items=['A', 'B'])
        assert lv.selection() == 0

    def test_next_moves_down(self, lv):
        lv.next()
        assert lv.selection() == 1

    def test_prev_moves_up(self, lv):
        lv.next()
        lv.next()
        lv.prev()
        assert lv.selection() == 1

    def test_next_wraps_to_start(self, canvas):
        lv = ListView(canvas, items=['A', 'B', 'C'])
        lv.show()
        lv.next()  # -> 1
        lv.next()  # -> 2
        lv.next()  # -> 0 (wrap)
        assert lv.selection() == 0

    def test_prev_wraps_to_end(self, canvas):
        lv = ListView(canvas, items=['A', 'B', 'C'])
        lv.show()
        lv.prev()  # wrap -> 2
        assert lv.selection() == 2

    def test_selection_returns_index(self, lv):
        lv.next()
        assert lv.selection() == 1

    def test_get_selection_returns_text(self, lv):
        assert lv.getSelection() == 'A'
        lv.next()
        assert lv.getSelection() == 'B'

    def test_set_selection(self, lv):
        lv.setSelection(3)
        assert lv.selection() == 3
        assert lv.getSelection() == 'D'

    def test_selection_highlight_color_eeeeee(self, canvas):
        """Selected item rectangle uses fill=#EEEEEE."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.show()
        rects = _get_rects(canvas)
        # There should be exactly 1 selection rectangle (for item 0)
        assert len(rects) == 1
        _, rect = rects[0]
        assert rect['options']['fill'] == SELECT_BG  # '#EEEEEE'

    def test_selected_text_color_black(self, canvas):
        """Selected item text color is 'black'."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.show()
        texts = _get_text_items(canvas)
        # Find text for item 'A' (selected)
        selected_text = [t for _, t in texts if t['options'].get('text') == 'A']
        assert len(selected_text) == 1
        assert selected_text[0]['options']['fill'] == SELECT_TEXT_COLOR  # 'black'


# =================================================================
# Pagination
# =================================================================

class TestListViewPagination:

    def test_items_per_page_default_4(self, canvas):
        lv = ListView(canvas, items=['A', 'B', 'C', 'D'])
        assert lv.getItemCountOnPage(0) == 4

    def test_page_count(self, canvas):
        """14 items at 5 per page = 3 pages."""
        items = [f'Item{i}' for i in range(14)]
        lv = ListView(canvas, items=items)
        assert lv.getPageCount() == 3  # ceil(14/5)

    def test_page_position(self, canvas):
        items = [f'Item{i}' for i in range(14)]
        lv = ListView(canvas, items=items)
        lv.show()
        assert lv.getPagePosition() == 0
        # Move to item 5 -> page 1
        for _ in range(5):
            lv.next()
        assert lv.getPagePosition() == 1

    def test_next_crosses_page_boundary(self, canvas):
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.show()
        # Items 0-4 on page 0, items 5-9 on page 1
        for _ in range(5):
            lv.next()
        assert lv.selection() == 5
        assert lv.getPagePosition() == 1

    def test_prev_crosses_page_boundary(self, canvas):
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.show()
        lv.setSelection(5)
        assert lv.getPagePosition() == 1
        lv.prev()
        assert lv.selection() == 4
        assert lv.getPagePosition() == 0

    def test_goto_page(self, canvas):
        items = [f'Item{i}' for i in range(12)]
        lv = ListView(canvas, items=items)
        lv.show()
        lv.goto_page(2)
        assert lv.getPagePosition() == 2
        assert lv.selection() == 10  # first item on page 2 (5 per page)

    def test_partial_last_page(self, canvas):
        """Last page may have fewer items than max_display."""
        items = [f'Item{i}' for i in range(7)]
        lv = ListView(canvas, items=items)
        # Page 0: 5 items, Page 1: 2 items
        assert lv.getItemCountOnPage(0) == 5
        assert lv.getItemCountOnPage(1) == 2

    def test_page_change_callback(self, canvas):
        pages_received = []
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.setOnPageChangeCall(lambda p: pages_received.append(p))
        lv.show()
        # Navigate from page 0 to page 1 (5 items per page)
        for _ in range(5):
            lv.next()
        assert 1 in pages_received

    def test_get_page_position_from_item(self, canvas):
        items = [f'Item{i}' for i in range(12)]
        lv = ListView(canvas, items=items)
        assert lv.getPagePositionFromItem(0) == 0
        assert lv.getPagePositionFromItem(4) == 0
        assert lv.getPagePositionFromItem(5) == 1
        assert lv.getPagePositionFromItem(11) == 2

    def test_get_item_index_in_page(self, canvas):
        items = [f'Item{i}' for i in range(12)]
        lv = ListView(canvas, items=items)
        assert lv.getItemIndexInPage(0) == 0
        assert lv.getItemIndexInPage(4) == 4
        assert lv.getItemIndexInPage(5) == 0
        assert lv.getItemIndexInPage(6) == 1

    def test_is_item_position_in_page(self, canvas):
        items = [f'Item{i}' for i in range(12)]
        lv = ListView(canvas, items=items)
        lv.show()
        assert lv.isItemPositionInPage(0) is True
        assert lv.isItemPositionInPage(4) is True
        assert lv.isItemPositionInPage(5) is False

    def test_goto_first_page(self, canvas):
        items = [f'Item{i}' for i in range(12)]
        lv = ListView(canvas, items=items)
        lv.show()
        lv.goto_page(2)
        lv.goto_first_page()
        assert lv.getPagePosition() == 0
        assert lv.selection() == 0

    def test_goto_last_page(self, canvas):
        items = [f'Item{i}' for i in range(12)]
        lv = ListView(canvas, items=items)
        lv.show()
        lv.goto_last_page()
        assert lv.getPagePosition() == 2
        assert lv.selection() == 10


# =================================================================
# Rendering
# =================================================================

class TestListViewRendering:

    def test_item_height_40px(self, canvas):
        """Default item height is 40px — verified from SPEC."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.show()
        rects = _get_rects(canvas)
        assert len(rects) == 1  # only selected item has a rectangle
        _, rect = rects[0]
        coords = rect['coords']
        # Height = y2 - y1
        assert coords[3] - coords[1] == LIST_ITEM_H  # 40

    def test_text_x_no_icon(self, canvas):
        """Text x position is 19 when no icons are set."""
        lv = ListView(canvas, items=['Hello'])
        lv.show()
        texts = _get_text_items(canvas)
        assert len(texts) >= 1
        _, t = texts[0]
        assert t['coords'][0] == LIST_TEXT_X_NO_ICON  # 19

    def test_text_x_with_icon(self, canvas):
        """Text x position is 50 when icon image is available.

        PIL + actual PNGs are available in the test environment, so
        setIcons loads the image and text shifts to LIST_TEXT_X_WITH_ICON.
        """
        lv = ListView(canvas, items=['Hello'])
        lv.setIcons(['1'])
        lv.show()
        texts = _get_text_items(canvas)
        _, t = texts[0]
        assert t['coords'][0] == LIST_TEXT_X_WITH_ICON

    def test_text_y_centered_in_item(self, canvas):
        """Text y is vertically centered: y = content_y0 + item_height//2."""
        lv = ListView(canvas, items=['A'])
        lv.show()
        texts = _get_text_items(canvas)
        _, t = texts[0]
        expected_y = CONTENT_Y0 + LIST_ITEM_H // 2  # 40 + 20 = 60
        assert t['coords'][1] == expected_y

    def test_show_creates_canvas_items(self, canvas):
        """show() creates text items on the canvas."""
        lv = ListView(canvas, items=['A', 'B', 'C'])
        assert len(canvas.find_all()) == 0
        lv.show()
        assert len(canvas.find_all()) > 0

    def test_hide_removes_canvas_items(self, canvas):
        """hide() removes all items belonging to this ListView."""
        lv = ListView(canvas, items=['A', 'B', 'C'])
        lv.show()
        assert len(canvas.find_all()) > 0
        lv.hide()
        assert len(canvas.find_all()) == 0

    def test_only_current_page_visible(self, canvas):
        """Only items for the current page are drawn."""
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.show()
        texts = _get_texts(canvas)
        # Page 0: items 0-4 (5 per page)
        assert 'Item0' in texts
        assert 'Item4' in texts
        assert 'Item5' not in texts

    def test_selection_rect_full_width(self, canvas):
        """Selection rectangle spans full screen width (0 to 240)."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.show()
        rects = _get_rects(canvas)
        _, rect = rects[0]
        assert rect['coords'][0] == 0
        assert rect['coords'][2] == SCREEN_W  # 240

    def test_page_arrow_down_when_multiple_pages(self, canvas):
        """Real device does NOT show arrows — pagination is via title bar counter.

        [Source: real device screenshots show no arrows]
        """
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.show()
        texts = _get_text_items(canvas)
        arrows = [t for _, t in texts if t['options'].get('text') == '\u25bc']
        assert len(arrows) == 0

    def test_no_arrows_single_page(self, canvas):
        """No page arrows when all items fit on one page."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.show()
        texts = _get_text_items(canvas)
        arrows = [t for _, t in texts
                  if t['options'].get('text') in ('\u25b2', '\u25bc')]
        assert len(arrows) == 0


# =================================================================
# Callbacks
# =================================================================

class TestListViewCallbacks:

    def test_selection_change_callback(self, canvas):
        selections = []
        lv = ListView(canvas, items=['A', 'B', 'C'])
        lv.setOnSelectionChangeCall(lambda s: selections.append(s))
        lv.show()
        lv.next()
        lv.next()
        assert selections == [1, 2]

    def test_page_change_callback(self, canvas):
        pages = []
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.setOnPageChangeCall(lambda p: pages.append(p))
        lv.show()
        for _ in range(5):
            lv.next()
        assert 1 in pages

    def test_callback_receives_correct_value(self, canvas):
        results = []
        items = [f'Item{i}' for i in range(6)]
        lv = ListView(canvas, items=items)
        lv.setOnSelectionChangeCall(lambda s: results.append(('sel', s)))
        lv.setOnPageChangeCall(lambda p: results.append(('page', p)))
        lv.show()

        lv.next()  # sel 1, same page
        lv.next()  # sel 2, same page
        lv.next()  # sel 3, same page
        lv.next()  # sel 4, same page
        lv.next()  # sel 5, new page 1

        assert ('sel', 1) in results
        assert ('sel', 5) in results
        assert ('page', 1) in results


# =================================================================
# BigTextListView
# =================================================================

class TestBigTextListView:

    def test_draw_str(self, canvas):
        btlv = BigTextListView(canvas)
        btlv.drawStr('Hello World')
        texts = _get_texts(canvas)
        assert 'Hello World' in texts

    def test_selection_always_zero(self, canvas):
        btlv = BigTextListView(canvas)
        assert btlv.selection() == 0
        btlv.drawStr('anything')
        assert btlv.selection() == 0

    def test_draw_str_replaces_previous(self, canvas):
        btlv = BigTextListView(canvas)
        btlv.drawStr('First')
        btlv.drawStr('Second')
        texts = _get_texts(canvas)
        assert 'First' not in texts
        assert 'Second' in texts

    def test_hide(self, canvas):
        btlv = BigTextListView(canvas)
        btlv.drawStr('Visible')
        assert len(canvas.find_all()) > 0
        btlv.hide()
        assert len(canvas.find_all()) == 0


# =================================================================
# Additional edge cases
# =================================================================

class TestListViewEdgeCases:

    def test_set_display_item_max(self, canvas):
        """setDisplayItemMax overrides items per page."""
        items = [f'Item{i}' for i in range(10)]
        lv = ListView(canvas, items=items)
        lv.setDisplayItemMax(5)
        assert lv.getPageCount() == 2  # ceil(10/5) = 2

    def test_set_ui(self, canvas):
        """setUI changes position and recalculates max display."""
        lv = ListView(canvas, items=[f'Item{i}' for i in range(10)])
        lv.setUI(0, 40, 240, 200)  # h=200, item_h=40 -> 5 per page
        assert lv.getPageCount() == 2  # ceil(10/5) = 2

    def test_is_showing(self, canvas):
        lv = ListView(canvas, items=['A'])
        assert lv.isShowing() is False
        lv.show()
        assert lv.isShowing() is True
        lv.hide()
        assert lv.isShowing() is False

    def test_next_on_empty_list(self, canvas):
        """next() on empty list does not crash."""
        lv = ListView(canvas)
        lv.show()
        lv.next()  # should not raise
        assert lv.selection() == 0

    def test_prev_on_empty_list(self, canvas):
        """prev() on empty list does not crash."""
        lv = ListView(canvas)
        lv.show()
        lv.prev()  # should not raise
        assert lv.selection() == 0

    def test_draw_str_updates_item(self, canvas):
        """drawStr updates a specific item's text."""
        lv = ListView(canvas, items=['A', 'B', 'C'])
        lv.show()
        lv.drawStr(1, 'BB')
        texts = _get_texts(canvas)
        assert 'BB' in texts
        assert 'B' not in texts

    def test_draw_multi_replaces_all(self, canvas):
        """drawMulti replaces all items."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.show()
        lv.drawMulti(['X', 'Y', 'Z'])
        texts = _get_texts(canvas)
        assert 'X' in texts
        assert 'A' not in texts

    def test_setup_select_bg(self, canvas):
        """setupSelectBG changes the highlight color."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.setupSelectBG('#FF0000')
        lv.show()
        rects = _get_rects(canvas)
        _, rect = rects[0]
        assert rect['options']['fill'] == '#FF0000'

    def test_set_title_color(self, canvas):
        """setTitleColor changes non-selected text color."""
        lv = ListView(canvas, items=['A', 'B'])
        lv.setTitleColor('white')
        lv.show()
        texts = _get_text_items(canvas)
        # Find text for item 'B' (not selected)
        non_selected = [t for _, t in texts if t['options'].get('text') == 'B']
        assert len(non_selected) == 1
        assert non_selected[0]['options']['fill'] == 'white'
