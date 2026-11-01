##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################
"""Free-growing hex digit input widget.

Second line is indented to line up under the FIRST digit of line one.
Copyright (c) 2026: jareckib
"""

from lib._constants import SCREEN_W, CONTENT_Y0, CONTENT_H
from lib import resources

HEX_CHARS = '0123456789ABCDEF'

LABEL_COLOR = '#000000'
DIGIT_COLOR = '#0000FF'
DEFAULT_TEXT_COLOR = DIGIT_COLOR
HINT_COLOR = '#606060'

TAG = '_hex_input'


class FreeHexInput(object):
    """Grows a hex value one digit at a time; wraps after per_line chars."""

    def __init__(self, canvas, label='', hint='', max_length=16,
                 per_line=8, x0=8, font_size=13, hint_font_size=10,
                 line_gap=20, y_offset=None, text_color=DEFAULT_TEXT_COLOR):
        self._canvas = canvas
        self._label = label
        self._hint = hint
        self._max_length = max(1, int(max_length))
        self._per_line = max(1, int(per_line))
        self._x0 = x0
        self._font_size = int(font_size)
        self._font = resources.get_font(font_size)
        self._hint_font = resources.get_font(hint_font_size)
        self._line_gap = line_gap
        default_y1 = CONTENT_Y0 + CONTENT_H // 2 - line_gap // 2
        self._y_offset = default_y1 if y_offset is None else int(y_offset)
        self._text_color = text_color
        self._digits = ['0']
        self._cursor = 0


    # -- public API ------------------------------------------------

    def setY(self, y):
        self._y_offset = int(y)

    def setLabel(self, label):
        self._label = label

    def setTextColor(self, color):
        self._text_color = color
        self._redraw()

    def show(self):
        self._redraw()

    def hide(self):
        self._canvas.delete(TAG)

    def rollUp(self):
        idx = HEX_CHARS.index(self._digits[self._cursor])
        self._digits[self._cursor] = HEX_CHARS[(idx + 1) % len(HEX_CHARS)]
        self._redraw()

    def rollDown(self):
        idx = HEX_CHARS.index(self._digits[self._cursor])
        self._digits[self._cursor] = HEX_CHARS[(idx - 1) % len(HEX_CHARS)]
        self._redraw()

    def moveLeft(self):
        if self._cursor > 0:
            self._cursor -= 1
            self._redraw()

    def moveRight(self):
        if self._cursor < len(self._digits) - 1:
            self._cursor += 1
        elif len(self._digits) < self._max_length:
            candidate = self._digits + ['0']
            if self._layout(candidate) is not None:
                self._digits.append('0')
                self._cursor += 1
        self._redraw()

    def getValue(self):
        """Current hex digits as typed, e.g. '39' or '123456789ABCDEF0'."""
        return ''.join(self._digits)

    def length(self):
        return len(self._digits)

    # -- Dump Diff 2 character-capacity layout -------------------------

    def _line_capacity(self):
        """Dump Diff 2 Courier New rule: floor(24 * 11 / font_size).

        The agreed size-14 calibration is 21 total positions. One
        position on each side is reserved as a screen margin.
        """
        if self._font_size <= 0:
            return 0
        total = (24 * 11) // self._font_size
        if self._font_size == 14:
            total = 21
        return max(0, total - 2)

    def _layout(self, digits):
        """Center one line when it fits the Dump Diff 2 character budget.

        Otherwise use 8+8 for 16 HEX or 8+2 for 10 HEX, with
        the second line aligned under the first HEX digit.
        """
        capacity = self._line_capacity()
        label_length = len(self._label)
        count = len(digits)
        if label_length + count <= capacity:
            split = count
        elif self._max_length in (10, 16) and count > 8:
            split = 8
        else:
            return None
        if label_length + split > capacity or count - split > capacity:
            return None

        # Courier New is monospaced; character positions use the agreed
        # 240px screen budget rather than measuring Canvas glyph bounds.
        total_positions = self._line_capacity() + 2
        cell_width = float(SCREEN_W) / total_positions if total_positions else 0
        first_width = (label_length + split) * cell_width
        first_left = (SCREEN_W - first_width) / 2
        first_digit_x = first_left + label_length * cell_width
        if first_digit_x + (count - split) * cell_width > SCREEN_W - cell_width:
            return None
        return [(0 if i < split else 1,
                 first_digit_x + (i if i < split else i - split) * cell_width)
                for i in range(count)]

    # -- drawing -----------------------------------------------------

    def _redraw(self):
        canvas = self._canvas
        canvas.delete(TAG)
        row_top_y = self._y_offset
        row_bottom_y = row_top_y + self._line_gap
        positions = self._layout(self._digits)
        if self._label:
            label_x = (positions[0][1] - len(self._label) * (float(SCREEN_W) / (self._line_capacity() + 2))) if positions else self._x0
            canvas.create_text(label_x, row_top_y, text=self._label,
                               fill=LABEL_COLOR, font=self._font,
                               anchor='w', tags=TAG)

        if positions is None:
            # Defensive fallback for labels changed after text was entered.
            positions = self._layout(self._digits[:1]) or [(0, self._x0)]

        for i, (row, x) in enumerate(positions):
            ch = self._digits[i]
            y = row_top_y if row == 0 else row_bottom_y
            item = canvas.create_text(x, y, text=ch, fill=self._text_color,
                                      font=self._font, anchor='w', tags=TAG)
            bounds = canvas.bbox(item)
            if bounds and i == self._cursor:
                x0, y0, x1, y1 = bounds
                canvas.create_line(x0, y1 + 2, x1, y1 + 2,
                                   fill=self._text_color, width=2, tags=TAG)

        if self._hint:
            canvas.create_text(SCREEN_W // 2, CONTENT_Y0 + CONTENT_H - 2,
                               text=self._hint, fill=HINT_COLOR,
                               font=self._hint_font, anchor='s', tags=TAG)
