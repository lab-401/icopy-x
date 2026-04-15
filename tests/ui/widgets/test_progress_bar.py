"""Comprehensive tests for ProgressBar widget.

All coordinate and color assertions are derived from UI_SPEC.md and
verified against the original firmware rendering under QEMU.
"""

import sys
import os
import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import ProgressBar, createTag
from lib._constants import (
    PROGRESS_X,
    PROGRESS_Y,
    PROGRESS_W,
    PROGRESS_H,
    PROGRESS_BG,
    PROGRESS_FG,
    PROGRESS_MSG_COLOR,
    PROGRESS_MSG_ANCHOR,
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
def pb(canvas):
    """A default ProgressBar, shown."""
    pb = ProgressBar(canvas)
    pb.show()
    return pb


def _get_rects(canvas):
    """Return all rectangle items as list of (id, item_dict)."""
    return canvas.get_items_by_type('rectangle')


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


def _find_by_tag(canvas, tag_substring):
    """Find canvas items whose tags contain a substring."""
    results = []
    for iid, item in canvas._items.items():
        for t in item['tags']:
            if tag_substring in t:
                results.append((iid, item))
                break
    return results


# =================================================================
# Position and defaults
# =================================================================

class TestProgressBarDefaults:

    def test_default_position(self, canvas):
        """Default position is x=20, y=100."""
        pb = ProgressBar(canvas)
        assert pb._x == PROGRESS_X  # 20
        assert pb._y == PROGRESS_Y  # 100

    def test_custom_position(self, canvas):
        """Custom x, y, width, height are stored correctly."""
        pb = ProgressBar(canvas, x=10, y=50, width=100, height=10, max_v=50)
        assert pb._x == 10
        assert pb._y == 50
        assert pb._width == 100
        assert pb._height == 10
        assert pb._max == 50

    def test_initial_fill_zero(self, canvas):
        """Initial progress is 0, so no fill rect should be drawn."""
        pb = ProgressBar(canvas)
        pb.show()
        # Should have bg rect but no fill rect (progress=0 means fill_width=0)
        fill_items = _find_by_tag(canvas, ':fill')
        assert len(fill_items) == 0


# =================================================================
# Background rect
# =================================================================

class TestProgressBarBackground:

    def test_background_rect_color(self, pb, canvas):
        """Background rect uses fill=#eeeeee."""
        bg_items = _find_by_tag(canvas, ':bg')
        assert len(bg_items) >= 1
        _, item = bg_items[0]
        assert item['type'] == 'rectangle'
        assert item['options']['fill'] == PROGRESS_BG  # '#eeeeee'

    def test_background_rect_coords(self, pb, canvas):
        """Background rect is at (20, 100, 220, 120)."""
        bg_items = _find_by_tag(canvas, ':bg')
        _, item = bg_items[0]
        assert item['coords'] == [PROGRESS_X, PROGRESS_Y,
                                   PROGRESS_X + PROGRESS_W,
                                   PROGRESS_Y + PROGRESS_H]


# =================================================================
# Fill rect
# =================================================================

class TestProgressBarFill:

    def test_fill_color(self, canvas):
        """Fill rect uses fill=#1C6AEB."""
        pb = ProgressBar(canvas)
        pb.setProgress(50)
        pb.show()
        fill_items = _find_by_tag(canvas, ':fill')
        assert len(fill_items) == 1
        _, item = fill_items[0]
        assert item['options']['fill'] == PROGRESS_FG  # '#1C6AEB'

    def test_set_progress_50_percent(self, canvas):
        """50% progress on 200px bar = 100px fill width."""
        pb = ProgressBar(canvas)
        pb.setProgress(50)
        pb.show()
        fill_items = _find_by_tag(canvas, ':fill')
        assert len(fill_items) == 1
        _, item = fill_items[0]
        # fill_width = (50/100) * 200 = 100
        # coords: (20, 210, 20+100, 230) = (20, 210, 120, 230)
        assert item['coords'] == [PROGRESS_X, PROGRESS_Y,
                                   PROGRESS_X + 100, PROGRESS_Y + PROGRESS_H]

    def test_set_progress_100_percent(self, canvas):
        """100% progress on 200px bar = 200px fill width (full bar)."""
        pb = ProgressBar(canvas)
        pb.setProgress(100)
        pb.show()
        fill_items = _find_by_tag(canvas, ':fill')
        assert len(fill_items) == 1
        _, item = fill_items[0]
        # fill_width = (100/100) * 200 = 200
        # coords: (20, 210, 220, 230)
        assert item['coords'] == [PROGRESS_X, PROGRESS_Y,
                                   PROGRESS_X + PROGRESS_W,
                                   PROGRESS_Y + PROGRESS_H]

    def test_set_progress_clamp_above_max(self, canvas):
        """Progress above max is clamped to max."""
        pb = ProgressBar(canvas, max_v=100)
        pb.setProgress(200)
        assert pb.getProgress() == 100

    def test_set_progress_clamp_below_zero(self, canvas):
        """Progress below 0 is clamped to 0."""
        pb = ProgressBar(canvas, max_v=100)
        pb.setProgress(-10)
        assert pb.getProgress() == 0


# =================================================================
# Message
# =================================================================

class TestProgressBarMessage:

    def test_message_position(self, canvas):
        """Message text is at (120, y-2) — center-x of bar, 2px above top."""
        pb = ProgressBar(canvas)
        pb.setMessage('Reading...')
        pb.show()
        msg_items = _find_by_tag(canvas, ':msg')
        assert len(msg_items) == 1
        _, item = msg_items[0]
        # (x + width//2, y - 2) = (20 + 100, 210 - 2) = (120, 208)
        assert item['coords'] == [PROGRESS_X + PROGRESS_W // 2,
                                   PROGRESS_Y - 2]

    def test_message_color(self, canvas):
        """Message text color is #1C6AEB."""
        pb = ProgressBar(canvas)
        pb.setMessage('Writing...')
        pb.show()
        msg_items = _find_by_tag(canvas, ':msg')
        _, item = msg_items[0]
        assert item['options']['fill'] == PROGRESS_MSG_COLOR  # '#1C6AEB'

    def test_message_anchor_south(self, canvas):
        """Message text anchor is 's' (south — bottom of text touches y=98)."""
        pb = ProgressBar(canvas)
        pb.setMessage('Test')
        pb.show()
        msg_items = _find_by_tag(canvas, ':msg')
        _, item = msg_items[0]
        assert item['options']['anchor'] == PROGRESS_MSG_ANCHOR  # 's'


# =================================================================
# Value management
# =================================================================

class TestProgressBarValues:

    def test_set_max(self, canvas):
        """setMax changes the maximum value."""
        pb = ProgressBar(canvas, max_v=50)
        assert pb.getMax() == 50
        pb.setMax(200)
        assert pb.getMax() == 200

    def test_increment(self, canvas):
        """increment adds to progress."""
        pb = ProgressBar(canvas, max_v=100)
        pb.setProgress(10)
        pb.increment(5)
        assert pb.getProgress() == 15

    def test_decrement(self, canvas):
        """decrement subtracts from progress."""
        pb = ProgressBar(canvas, max_v=100)
        pb.setProgress(10)
        pb.decrement(3)
        assert pb.getProgress() == 7


# =================================================================
# Visibility
# =================================================================

class TestProgressBarVisibility:

    def test_show_creates_items(self, canvas):
        """show() creates canvas items."""
        pb = ProgressBar(canvas)
        assert len(canvas.find_all()) == 0
        pb.show()
        assert len(canvas.find_all()) > 0

    def test_hide_removes_items(self, canvas):
        """hide() removes all progress bar items from canvas."""
        pb = ProgressBar(canvas)
        pb.setProgress(50)
        pb.setMessage('Test')
        pb.show()
        assert len(canvas.find_all()) > 0
        pb.hide()
        assert len(canvas.find_all()) == 0


# =================================================================
# Percentage text
# =================================================================

class TestProgressBarPercentage:

    def test_percentage_text_not_shown_by_default(self, canvas):
        """Percentage text is NOT rendered by default (ground truth: scan screenshots)."""
        pb = ProgressBar(canvas)
        pb.setProgress(50)
        pb.show()
        pct_items = _find_by_tag(canvas, ':pct')
        assert len(pct_items) == 0
