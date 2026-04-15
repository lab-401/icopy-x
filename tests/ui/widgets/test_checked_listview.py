"""Comprehensive tests for CheckedListView widget.

All coordinate and color assertions are derived from UI_SPEC.md and
verified against the original firmware rendering under QEMU.
"""

import sys
import os
import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import CheckedListView, ListView
from lib._constants import CHECK_COLOR

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
def clv(canvas):
    """A CheckedListView with 5 items, shown."""
    clv = CheckedListView(canvas, items=['A', 'B', 'C', 'D', 'E'])
    clv.show()
    return clv


def _find_by_tag(canvas, tag_substring):
    """Find canvas items whose tags contain a substring."""
    results = []
    for iid, item in canvas._items.items():
        for t in item['tags']:
            if tag_substring in t:
                results.append((iid, item))
                break
    return results


def _get_check_texts(canvas):
    """Return all text items that contain the checkmark character."""
    return [
        (iid, item)
        for iid, item in canvas._items.items()
        if item['type'] == 'text' and item['options'].get('text') == '\u2713'
    ]


# =================================================================
# Inheritance
# =================================================================

class TestCheckedListViewInheritance:

    def test_inherits_listview(self, canvas):
        """CheckedListView is a subclass of ListView."""
        clv = CheckedListView(canvas)
        assert isinstance(clv, ListView)


# =================================================================
# Check state management
# =================================================================

class TestCheckedListViewState:

    def test_initial_no_checks(self, clv):
        """Initially no items are checked."""
        assert clv.getCheckPosition() == set()

    def test_check_item(self, clv):
        """check(idx) marks an item as checked."""
        clv.check(1)
        assert 1 in clv.getCheckPosition()

    def test_uncheck_item(self, clv):
        """check(idx, False) unchecks an item."""
        clv.check(2)
        assert 2 in clv.getCheckPosition()
        clv.check(2, checked=False)
        assert 2 not in clv.getCheckPosition()

    def test_auto_show_chk_toggles(self, clv):
        """auto_show_chk toggles check on the current selection."""
        # Selection starts at 0
        assert 0 not in clv.getCheckPosition()
        clv.auto_show_chk()
        assert 0 in clv.getCheckPosition()
        clv.auto_show_chk()
        assert 0 not in clv.getCheckPosition()

    def test_get_check_position_empty(self, clv):
        """getCheckPosition returns empty set when nothing checked."""
        assert clv.getCheckPosition() == set()

    def test_get_check_position_one(self, clv):
        """getCheckPosition returns set with one index."""
        clv.check(3)
        assert clv.getCheckPosition() == {3}

    def test_get_check_position_multiple(self, clv):
        """getCheckPosition returns set with multiple indices."""
        clv.check(0)
        clv.check(2)
        clv.check(4)
        assert clv.getCheckPosition() == {0, 2, 4}


# =================================================================
# Check persistence across pages
# =================================================================

class TestCheckedListViewPagination:

    def test_check_survives_page_change(self, canvas):
        """Checked state persists when navigating to a different page."""
        items = [f'Item{i}' for i in range(8)]
        clv = CheckedListView(canvas, items=items)
        clv.show()
        # Check item 1 (on page 0)
        clv.check(1)
        # Navigate to page 1 (items 5-7): need 5 next() calls
        # (selection 0->1->2->3->4->5, page = 5//5 = 1)
        for _ in range(5):
            clv.next()
        assert clv.getPagePosition() == 1
        # Check still present in state
        assert 1 in clv.getCheckPosition()
        # Navigate back to page 0
        clv.setSelection(0)
        assert clv.getPagePosition() == 0
        # Verify checked item renders checkbox rectangles (not text glyphs)
        check_rects = _find_by_tag(canvas, 'check')
        assert len(check_rects) >= 1


# =================================================================
# Rendering
# =================================================================

class TestCheckedListViewRendering:

    def test_check_renders_checkbox_rectangles(self, clv, canvas):
        """Checking an item renders checkbox rectangles (blue border + fill)."""
        clv.check(0)
        check_items = _find_by_tag(canvas, 'check')
        # Checked item renders 2 rectangles: outer border + inner fill
        assert len(check_items) >= 2
        # At least one should have the checked fill color
        fills = [item['options'].get('fill') for _, item in check_items]
        from lib._constants import CHECK_COLOR_CHECKED_FILL
        assert CHECK_COLOR_CHECKED_FILL in fills
