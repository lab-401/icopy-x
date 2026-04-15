"""Tests for ConsoleView widget.

Covers: addLine, addText multiline, auto-scroll, scroll up/down,
max visible lines, clear, show/hide, and font verification.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import ConsoleView
from lib._constants import (
    CONTENT_Y0,
    CONTENT_H,
    CONSOLE_TEXT_COLOR,
)

from tests.ui.conftest import MockCanvas


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

@pytest.fixture
def canvas():
    """Fresh 240x240 MockCanvas."""
    return MockCanvas(width=240, height=240, bg='#222222')


@pytest.fixture
def cv(canvas):
    """A ConsoleView shown on the canvas."""
    cv = ConsoleView(canvas)
    cv.show()
    return cv


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


def _get_texts(canvas):
    """Extract all text strings currently on the canvas."""
    return canvas.get_all_text()


# =================================================================
# addLine
# =================================================================

class TestConsoleViewAddLine:

    def test_add_line(self, canvas, cv):
        """addLine adds a single line visible on canvas."""
        cv.addLine('hello world')
        texts = _get_texts(canvas)
        assert 'hello world' in texts

    def test_add_line_increments_count(self, canvas, cv):
        """Each addLine increments line count."""
        cv.addLine('line 1')
        cv.addLine('line 2')
        cv.addLine('line 3')
        assert cv.getLineCount() == 3


# =================================================================
# addText multiline
# =================================================================

class TestConsoleViewAddText:

    def test_add_text_multiline(self, canvas, cv):
        """addText splits text on newlines into separate lines."""
        cv.addText('alpha\nbeta\ngamma')
        assert cv.getLineCount() == 3
        texts = _get_texts(canvas)
        assert 'alpha' in texts
        assert 'beta' in texts
        assert 'gamma' in texts


# =================================================================
# Auto-scroll
# =================================================================

class TestConsoleViewAutoScroll:

    def test_auto_scroll_to_bottom(self, canvas, cv):
        """When at bottom, adding lines keeps showing the newest lines."""
        # Add more lines than max_visible (13)
        for i in range(20):
            cv.addLine(f'line {i}')

        texts = _get_texts(canvas)
        # Should see the last max_visible lines, not the first ones
        assert 'line 19' in texts
        assert 'line 0' not in texts


# =================================================================
# Manual scrolling
# =================================================================

class TestConsoleViewScrolling:

    def test_scroll_up_down(self, canvas, cv):
        """scrollUp/scrollDown adjust visible window."""
        for i in range(20):
            cv.addLine(f'line {i}')

        # Now at bottom, showing lines 7-19
        assert 'line 0' not in _get_texts(canvas)

        # Scroll up enough to see line 0
        for _ in range(20):
            cv.scrollUp()

        texts = _get_texts(canvas)
        assert 'line 0' in texts
        assert 'line 19' not in texts

        # Scroll back down
        for _ in range(20):
            cv.scrollDown()

        texts = _get_texts(canvas)
        assert 'line 19' in texts

    def test_scroll_up_clamps_at_zero(self, canvas, cv):
        """scrollUp does nothing when already at top."""
        cv.addLine('only line')
        cv.scrollUp()  # should not raise
        assert 'only line' in _get_texts(canvas)


# =================================================================
# Max visible lines
# =================================================================

class TestConsoleViewMaxVisible:

    def test_max_visible_lines(self, canvas, cv):
        """Only height // line_height lines are rendered at once.

        Default font_size=14, line_height=16, height=240 -> 15 visible lines.
        """
        max_vis = cv._max_visible  # 240 // 16 = 15
        for i in range(max_vis + 5):
            cv.addLine(f'line {i}')

        text_items = _get_text_items(canvas)
        assert len(text_items) == max_vis


# =================================================================
# Clear
# =================================================================

class TestConsoleViewClear:

    def test_clear(self, canvas, cv):
        """clear() removes all lines. Background rect persists while showing."""
        cv.addLine('hello')
        cv.addLine('world')
        cv.clear()
        assert cv.getLineCount() == 0
        # Background rect remains (console is still showing), but text lines are gone
        text_items = _get_text_items(canvas)
        assert len(text_items) == 0


# =================================================================
# Show / hide
# =================================================================

class TestConsoleViewShowHide:

    def test_show_hide(self, canvas):
        """show() renders lines, hide() removes them."""
        cv = ConsoleView(canvas)
        cv.addLine('test')
        # Not yet showing -- addLine stores but no canvas items
        assert len(canvas.find_all()) == 0

        cv.show()
        assert len(canvas.find_all()) > 0

        cv.hide()
        assert len(canvas.find_all()) == 0


# =================================================================
# Font
# =================================================================

class TestConsoleViewFont:

    def test_font_monospace(self, canvas, cv):
        """ConsoleView uses mononoki 14 font (default, max size)."""
        cv.addLine('test font')
        text_items = _get_text_items(canvas)
        assert len(text_items) >= 1
        _, t = text_items[0]
        font = t['options']['font']
        assert 'mononoki' in font
        assert '14' in font

    def test_text_color_white(self, canvas, cv):
        """ConsoleView text color is white."""
        cv.addLine('color check')
        text_items = _get_text_items(canvas)
        _, t = text_items[0]
        assert t['options']['fill'] == CONSOLE_TEXT_COLOR
