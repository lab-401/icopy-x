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
"""HEX input widget for iCopy-X / iCopy-XS.

Features:
- Enter uppercase hexadecimal digits (0-9, A-F) one at a time.
- UP/DOWN changes a digit; LEFT/RIGHT moves or extends the input.
- Cursor underline identifies the editable digit.
- Canvas font metrics determine whether label + digits fit on one line.
- For 16-digit inputs, use one line or a fixed 8+8 split.
- For 10-digit inputs, use one line or put all digits beneath the label.
- Center each row independently while preserving cursor underline.
- Keep the configured max_length, font, colors, hint and screen margins.
- getValue() returns the entered HEX string; no RFID operation is performed.

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
    """Grows a hex value one digit at a time; wraps when necessary."""

    def __init__(self, canvas, label='', hint='', max_length=16,
                 per_line=8, x0=8, font_size=13, hint_font_size=10,
                 line_gap=20, y_offset=None, text_color=DEFAULT_TEXT_COLOR):
        self._canvas = canvas
        self._label = label
        self._hint = hint
        self._max_length = max(1, int(max_length))
        self._per_line = max(1, int(per_line))
        self._x0 = x0
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

    # -- device font measurement ----------------------------------------

    def _measure(self, text):
        """Measure actual text width with the same Canvas font used to draw."""
        if not text:
            return 0
        item = self._canvas.create_text(0, 0, text=text, font=self._font,
                                        anchor='w', tags='_hex_measure')
        try:
            bounds = self._canvas.bbox(item)
            return max(0, bounds[2] - bounds[0]) if bounds else len(text) * 10
        finally:
            self._canvas.delete(item)

    def _layout(self, digits):
        """Center label and digits, using two rows when necessary."""
        margin = max(4, self._x0)
        usable = SCREEN_W - 2 * margin
        label_width = self._measure(self._label)
        value = ''.join(digits)
        if usable <= 0 or label_width > usable:
            return None
        combined = self._measure(self._label + value)
        if combined <= usable:
            left = max(margin, (SCREEN_W - combined) // 2)
            return (left, [(0, left + label_width + self._measure(value[:i]))
                           for i in range(len(digits))])
        if self._max_length == 16:
            first, second = value[:8], value[8:]
            if (self._measure(self._label + first) > usable
                    or self._measure(second) > usable):
                return None
            first_left = max(margin, (SCREEN_W - self._measure(self._label + first)) // 2)
            second_left = max(margin, (SCREEN_W - self._measure(second)) // 2)
            positions = [(0, first_left + label_width + self._measure(first[:i]))
                         for i in range(len(first))]
            positions += [(1, second_left + self._measure(second[:i]))
                          for i in range(len(second))]
            return (first_left, positions)
        if self._measure(value) > usable:
            return None
        label_left = max(margin, (SCREEN_W - label_width) // 2)
        digit_left = max(margin, (SCREEN_W - self._measure(value)) // 2)
        return (label_left, [(1, digit_left + self._measure(value[:i]))
                             for i in range(len(digits))])

    # -- drawing -----------------------------------------------------

    def _redraw(self):
        canvas = self._canvas
        canvas.delete(TAG)
        row_top_y = self._y_offset
        row_bottom_y = row_top_y + self._line_gap
        layout = self._layout(self._digits)
        if layout is None:
            return
        label_x, positions = layout
        if self._label:
            canvas.create_text(label_x, row_top_y, text=self._label,
                               fill=LABEL_COLOR, font=self._font,
                               anchor='w', tags=TAG)

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
                               font=self._hint_font, anchor='s', justify='center', tags=TAG)
