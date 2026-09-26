"""Tests for KeyboardInput widget (Dump Files rename keyboard).

Covers: default layout + DEL, placeholder, typing, delete, max length,
navigation wrapping, language-pack layouts, grid scrolling, rendering.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import KeyboardInput
from lib._constants import INPUT_DATA_COLOR, INPUT_HIGHLIGHT_COLOR

from tests.ui.conftest import MockCanvas


@pytest.fixture
def canvas():
    return MockCanvas(width=240, height=240, bg='#222222')


def _press_key(kb, key):
    """Move the highlight to *key* (searching the grid) and press it."""
    for r, row in enumerate(kb._rows):
        for i, (k, _span) in enumerate(row):
            if k == key:
                kb._focus_row, kb._focus_idx = r, i
                kb.press()
                return
    raise AssertionError('key %r not on keyboard' % key)


class TestLayout:
    def test_default_rows_from_language_pack(self, canvas):
        kb = KeyboardInput(canvas)
        keys = [k for row in kb._rows for k, _s in row]
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_':
            assert ch in keys
        assert keys[-1] == KeyboardInput.DEL

    def test_del_fills_last_row(self, canvas):
        kb = KeyboardInput(canvas)
        assert kb._cols == 8
        last = kb._rows[-1]
        assert last[-1][0] == KeyboardInput.DEL
        assert sum(span for _k, span in last) == 8

    def test_custom_rows(self, canvas):
        kb = KeyboardInput(canvas, rows=('AB', 'CD'))
        assert [k for k, _s in kb._rows[0]] == ['A', 'B']
        # Last row full -> DEL gets its own row
        assert kb._rows[-1][0][0] == KeyboardInput.DEL

    def test_grid_fits_content_area(self, canvas):
        kb = KeyboardInput(canvas)
        bottom = kb._grid_y0 + kb._visible_rows * kb._cell_h
        assert bottom <= 200          # above the button bar
        assert kb._grid_x0 >= 0
        assert kb._grid_x0 + kb._cols * kb._cell_w <= 240


class TestText:
    def test_placeholder_until_typing(self, canvas):
        kb = KeyboardInput(canvas, placeholder='M1-1K-4B_DEADBEEF_1')
        assert kb.getText() == ''
        assert kb.isPlaceholderShown()
        kb.press()                    # 'A' is focused first
        assert kb.getText() == 'A'
        assert not kb.isPlaceholderShown()

    def test_delete_back_to_placeholder(self, canvas):
        kb = KeyboardInput(canvas, placeholder='OLD')
        _press_key(kb, 'X')
        _press_key(kb, KeyboardInput.DEL)
        assert kb.getText() == ''
        assert kb.isPlaceholderShown()

    def test_delete_on_empty_is_harmless(self, canvas):
        kb = KeyboardInput(canvas)
        _press_key(kb, KeyboardInput.DEL)
        assert kb.getText() == ''

    def test_typing_builds_name(self, canvas):
        kb = KeyboardInput(canvas)
        for ch in 'CARD_01':
            _press_key(kb, ch)
        assert kb.getText() == 'CARD_01'

    def test_max_len(self, canvas):
        kb = KeyboardInput(canvas, max_len=3)
        for _ in range(5):
            kb.press()
        assert kb.getText() == 'AAA'


class TestNavigation:
    def test_right_wraps_in_row(self, canvas):
        kb = KeyboardInput(canvas)
        for _ in range(8):
            kb.moveRight()
        assert kb.getFocusKey() == 'A'

    def test_left_wraps_in_row(self, canvas):
        kb = KeyboardInput(canvas)
        kb.moveLeft()
        assert kb.getFocusKey() == 'H'

    def test_down_keeps_column(self, canvas):
        kb = KeyboardInput(canvas)
        kb.moveRight()                # B
        kb.moveDown()
        assert kb.getFocusKey() == 'J'

    def test_up_wraps_to_last_row(self, canvas):
        kb = KeyboardInput(canvas)
        kb.moveUp()
        assert kb.getFocusKey() == '6'

    def test_down_into_del_span(self, canvas):
        kb = KeyboardInput(canvas)
        for _ in range(7):
            kb.moveRight()            # H (last column)
        for _ in range(4):
            kb.moveDown()
        assert kb.getFocusKey() == KeyboardInput.DEL

    def test_scrolls_when_rows_do_not_fit(self, canvas):
        rows = tuple('ABCDEFGH' for _ in range(10))
        kb = KeyboardInput(canvas, rows=rows)
        assert kb._visible_rows < len(kb._rows)
        for _ in range(len(kb._rows) - 1):
            kb.moveDown()
        assert kb._first_row + kb._visible_rows - 1 == kb._focus_row


class TestRendering:
    def test_show_draws_preview_and_keys(self, canvas):
        kb = KeyboardInput(canvas, placeholder='OLD_NAME')
        kb.show()
        texts = canvas.get_all_text()
        assert 'OLD_NAME' in texts
        assert 'A' in texts and 'DEL' in texts

    def test_placeholder_is_grey_then_text_is_black(self, canvas):
        kb = KeyboardInput(canvas, placeholder='OLD')
        kb.show()
        preview = [i for i in canvas.find_withtag(kb._tag_preview)
                   if canvas.type(i) == 'text']
        assert canvas.itemcget(preview[0], 'fill') == KeyboardInput.PLACEHOLDER_COLOR
        kb.press()
        preview = [i for i in canvas.find_withtag(kb._tag_preview)
                   if canvas.type(i) == 'text']
        assert canvas.itemcget(preview[0], 'text') == 'A_'
        assert canvas.itemcget(preview[0], 'fill') == INPUT_DATA_COLOR

    def test_focused_key_highlighted(self, canvas):
        kb = KeyboardInput(canvas)
        kb.show()
        fills = [canvas.itemcget(i, 'fill') for i in canvas.find_withtag(kb._tag_key)]
        assert fills.count(INPUT_HIGHLIGHT_COLOR) == 1

    def test_hide_removes_everything(self, canvas):
        kb = KeyboardInput(canvas)
        kb.show()
        kb.hide()
        assert not canvas.find_withtag(kb._tag_key)
        assert not canvas.find_withtag(kb._tag_preview)
