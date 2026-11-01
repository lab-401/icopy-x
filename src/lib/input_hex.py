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
        """Fit the complete label and HEX text by measured pixel width.

        Center on one row when possible. Otherwise split at the largest
        fitting digit boundary, aligning row two under the first HEX digit.
        Never shorten or alter the label or change the configured data limit.
        """
        label_width = self._measure(self._label)
        margin = max(4, self._x0)
        usable = SCREEN_W - 2 * margin
        if usable <= 0 or label_width >= usable:
            return None

        # Measuring whole strings accounts for font-specific spacing.
        full_width = self._measure(self._label + ''.join(digits))
        if full_width <= usable:
            split = len(digits)
        else:
            split = 0
            for i in range(1, len(digits)):
                if self._measure(self._label + ''.join(digits[:i])) <= usable:
                    split = i
                else:
                    break
            if not split:
                return None
            # Row two begins at the first digit's x position, so it has
            # less room than a full-width row when the label is long.
            if self._measure(''.join(digits[split:])) > usable - label_width:
                return None

        first_width = self._measure(self._label + ''.join(digits[:split]))
        first_left = max(margin, (SCREEN_W - first_width) // 2)
        first_digit_x = first_left + label_width
        second_width = self._measure(''.join(digits[split:]))
        if first_digit_x + second_width > SCREEN_W - margin:
            # Shift the centered block left only as far as margins permit.
            first_digit_x = SCREEN_W - margin - second_width
            first_left = first_digit_x - label_width
            if first_left < margin:
                return None

        positions = []
        for row, segment in ((0, digits[:split]), (1, digits[split:])):
            for i in range(len(segment)):
                prefix = ''.join(segment[:i])
                positions.append((row, first_digit_x + self._measure(prefix)))
        return positions

    # -- drawing -----------------------------------------------------

    def _redraw(self):
        canvas = self._canvas
        canvas.delete(TAG)
        row_top_y = self._y_offset
        row_bottom_y = row_top_y + self._line_gap
        positions = self._layout(self._digits)
        if self._label:
            label_x = (positions[0][1] - self._measure(self._label)) if positions else self._x0
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
