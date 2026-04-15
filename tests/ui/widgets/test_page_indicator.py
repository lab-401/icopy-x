"""Tests for PageIndicator widget.

Covers: arrow enable/disable, show/hide, color verification,
update behavior, and setupBottomIndicator.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import PageIndicator
from lib._constants import (
    SCREEN_W,
    CONTENT_Y0,
    CONTENT_H,
    PAGE_INDICATOR_COLOR,
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
def pi(canvas):
    """A PageIndicator shown on the canvas."""
    pi = PageIndicator(canvas)
    return pi


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


def _get_arrows(canvas):
    """Return text items that are up or down arrow glyphs."""
    texts = _get_text_items(canvas)
    return [
        (iid, t) for iid, t in texts
        if t['options'].get('text') in ('\u25b2', '\u25bc')
    ]


def _get_up_arrows(canvas):
    return [
        (iid, t) for iid, t in _get_text_items(canvas)
        if t['options'].get('text') == '\u25b2'
    ]


def _get_down_arrows(canvas):
    return [
        (iid, t) for iid, t in _get_text_items(canvas)
        if t['options'].get('text') == '\u25bc'
    ]


# =================================================================
# No arrows on single page
# =================================================================

class TestPageIndicatorNoArrows:

    def test_no_arrows_single_page(self, canvas, pi):
        """No arrows when both indicators are disabled (default)."""
        pi.show()
        assert len(_get_arrows(canvas)) == 0

    def test_no_arrows_after_disable(self, canvas, pi):
        """Arrows disappear when disabled after being enabled."""
        pi.setTopIndicatorEnable(True)
        pi.setBottomIndicatorEnable(True)
        pi.show()
        assert len(_get_arrows(canvas)) == 2
        pi.setTopIndicatorEnable(False)
        pi.setBottomIndicatorEnable(False)
        assert len(_get_arrows(canvas)) == 0


# =================================================================
# Arrow rendering
# =================================================================

class TestPageIndicatorArrows:

    def test_down_arrow_on_first_page(self, canvas, pi):
        """Only down arrow when on first page with more pages below."""
        pi.setBottomIndicatorEnable(True)
        pi.show()
        assert len(_get_down_arrows(canvas)) == 1
        assert len(_get_up_arrows(canvas)) == 0

    def test_up_arrow_on_last_page(self, canvas, pi):
        """Only up arrow when on last page with pages above."""
        pi.setTopIndicatorEnable(True)
        pi.show()
        assert len(_get_up_arrows(canvas)) == 1
        assert len(_get_down_arrows(canvas)) == 0

    def test_both_arrows_middle_page(self, canvas, pi):
        """Both arrows shown when in the middle of pages."""
        pi.setTopIndicatorEnable(True)
        pi.setBottomIndicatorEnable(True)
        pi.show()
        assert len(_get_up_arrows(canvas)) == 1
        assert len(_get_down_arrows(canvas)) == 1

    def test_arrow_color(self, canvas, pi):
        """Arrow color must be PAGE_INDICATOR_COLOR (#1C6AEB)."""
        pi.setTopIndicatorEnable(True)
        pi.setBottomIndicatorEnable(True)
        pi.show()
        arrows = _get_arrows(canvas)
        for _, t in arrows:
            assert t['options']['fill'] == PAGE_INDICATOR_COLOR


# =================================================================
# Update and state
# =================================================================

class TestPageIndicatorUpdate:

    def test_update_arrows(self, canvas, pi):
        """update() redraws arrows after state changes."""
        pi.show()
        assert len(_get_arrows(canvas)) == 0
        pi.setBottomIndicatorEnable(True)
        # update() was called by setBottomIndicatorEnable since showing
        assert len(_get_down_arrows(canvas)) == 1

    def test_show_hide(self, canvas, pi):
        """show() makes indicators visible, hide() removes them."""
        pi.setTopIndicatorEnable(True)
        pi.setBottomIndicatorEnable(True)
        pi.show()
        assert pi.showing() is True
        assert len(_get_arrows(canvas)) == 2
        pi.hide()
        assert pi.showing() is False
        assert len(canvas.find_all()) == 0

    def test_setup_bottom_indicator(self, canvas, pi):
        """setupBottomIndicator stores total and current."""
        pi.setupBottomIndicator(total=10, current=5)
        assert pi._bottom_total == 10
        assert pi._bottom_current == 5
