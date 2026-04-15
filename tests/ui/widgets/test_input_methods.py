"""Tests for InputMethods widget.

Covers: initial placeholder, set/get value, focus navigation,
roll up/down for hex, wrapping, isComplete, show/hide rendering.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import InputMethods
from lib._constants import (
    INPUT_BG_COLOR,
    INPUT_DATA_COLOR,
    INPUT_HIGHLIGHT_COLOR,
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
def im(canvas):
    """A default hex InputMethods (12 chars, placeholder FFFFFFFFFFFF)."""
    return InputMethods(canvas)


def _get_rects(canvas):
    """Return all rectangle items as list of (id, item_dict)."""
    return canvas.get_items_by_type('rectangle')


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


def _get_texts(canvas):
    """Extract all text strings currently on the canvas."""
    return canvas.get_all_text()


# =================================================================
# Initial state
# =================================================================

class TestInputMethodsInitial:

    def test_initial_placeholder(self, im):
        """Default value is the placeholder 'FFFFFFFFFFFF'."""
        assert im.getValue() == 'FFFFFFFFFFFF'

    def test_initial_focus_zero(self, im):
        """Initial focus position is 0."""
        assert im.getFocus() == 0

    def test_initial_complete(self, im):
        """Default placeholder FFFFFFFFFFFF is valid hex, so isComplete=True."""
        assert im.isComplete() is True


# =================================================================
# Value management
# =================================================================

class TestInputMethodsValue:

    def test_set_value(self, im):
        """setValue replaces the current value."""
        im.setValue('AABBCCDDEEFF')
        assert im.getValue() == 'AABBCCDDEEFF'

    def test_set_value_uppercases(self, im):
        """setValue converts hex to uppercase."""
        im.setValue('aabbccddeeff')
        assert im.getValue() == 'AABBCCDDEEFF'

    def test_get_value(self, im):
        """getValue returns the full character string."""
        im.setValue('112233445566')
        assert im.getValue() == '112233445566'

    def test_set_value_pads_short(self, im):
        """Short values are zero-padded to length."""
        im.setValue('AABB')
        assert im.getValue() == 'AABB00000000'

    def test_set_value_truncates_long(self, im):
        """Long values are truncated to length."""
        im.setValue('AABBCCDDEEFF1234')
        assert im.getValue() == 'AABBCCDDEEFF'


# =================================================================
# Focus navigation
# =================================================================

class TestInputMethodsFocus:

    def test_focus_navigation(self, im):
        """nextChar/prevChar move focus through characters."""
        assert im.getFocus() == 0
        im.nextChar()
        assert im.getFocus() == 1
        im.nextChar()
        assert im.getFocus() == 2
        im.prevChar()
        assert im.getFocus() == 1

    def test_focus_wraps_forward(self, im):
        """nextChar wraps from last position to 0."""
        im.setFocus(11)  # last char (0-indexed, length=12)
        im.nextChar()
        assert im.getFocus() == 0

    def test_focus_wraps_backward(self, im):
        """prevChar wraps from 0 to last position."""
        assert im.getFocus() == 0
        im.prevChar()
        assert im.getFocus() == 11

    def test_set_focus_clamps(self, im):
        """setFocus clamps to valid range."""
        im.setFocus(99)
        assert im.getFocus() == 11
        im.setFocus(-5)
        assert im.getFocus() == 0


# =================================================================
# Roll up/down (hex)
# =================================================================

class TestInputMethodsRollHex:

    def test_roll_up_hex(self, canvas):
        """rollUp increments hex digit: F -> 0."""
        im = InputMethods(canvas, placeholder='F00000000000')
        im.setFocus(0)
        im.rollUp()
        # F -> 0 (wraps around hex set)
        assert im.getValue()[0] == '0'

    def test_roll_down_hex(self, canvas):
        """rollDown decrements hex digit: 0 -> F."""
        im = InputMethods(canvas, placeholder='000000000000')
        im.setFocus(0)
        im.rollDown()
        assert im.getValue()[0] == 'F'

    def test_roll_up_sequence(self, canvas):
        """Rolling up from 0 goes through 1,2,...,9,A,...,F."""
        im = InputMethods(canvas, placeholder='000000000000')
        im.setFocus(0)
        results = []
        for _ in range(16):
            im.rollUp()
            results.append(im.getValue()[0])
        # 0->1->2->...->9->A->B->C->D->E->F->0
        expected = list('123456789ABCDEF0')
        assert results == expected

    def test_roll_wraps(self, canvas):
        """rollUp from F wraps to 0, rollDown from 0 wraps to F."""
        im = InputMethods(canvas, placeholder='F00000000000')
        im.setFocus(0)
        im.rollUp()
        assert im.getValue()[0] == '0'
        im.rollDown()
        assert im.getValue()[0] == 'F'


# =================================================================
# isComplete
# =================================================================

class TestInputMethodsComplete:

    def test_is_complete(self, im):
        """All hex chars => complete."""
        im.setValue('AABBCCDDEEFF')
        assert im.isComplete() is True

    def test_is_complete_with_zeros(self, im):
        """All zeros is still valid hex, so complete."""
        im.setValue('000000000000')
        assert im.isComplete() is True

    def test_text_mode_incomplete(self, canvas):
        """Text mode: spaces mean incomplete."""
        im = InputMethods(canvas, format='text', length=6, placeholder='      ')
        assert im.isComplete() is False
        im.setValue('HELLO ')
        assert im.isComplete() is False
        im.setValue('HELLOO')
        assert im.isComplete() is True


# =================================================================
# Show / hide rendering
# =================================================================

class TestInputMethodsRendering:

    def test_show_renders_boxes(self, canvas, im):
        """show() creates rectangle boxes for each character."""
        im.show()
        rects = _get_rects(canvas)
        # 12 boxes for 12 hex characters
        assert len(rects) == 12

    def test_show_renders_chars(self, canvas, im):
        """show() creates text items for each character."""
        im.show()
        text_items = _get_text_items(canvas)
        assert len(text_items) == 12

    def test_hide_removes(self, canvas, im):
        """hide() removes all canvas items."""
        im.show()
        assert len(canvas.find_all()) > 0
        im.hide()
        assert len(canvas.find_all()) == 0

    def test_focused_box_highlighted(self, canvas, im):
        """The focused character box uses the highlight color."""
        im.show()
        rects = _get_rects(canvas)
        # First box (index 0) should be highlighted
        _, first_rect = rects[0]
        assert first_rect['options']['fill'] == INPUT_HIGHLIGHT_COLOR
        # Second box should be normal bg
        _, second_rect = rects[1]
        assert second_rect['options']['fill'] == INPUT_BG_COLOR

    def test_char_text_color(self, canvas, im):
        """Character text uses INPUT_DATA_COLOR (#000000)."""
        im.show()
        text_items = _get_text_items(canvas)
        _, t = text_items[0]
        assert t['options']['fill'] == INPUT_DATA_COLOR
