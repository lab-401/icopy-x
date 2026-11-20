##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
# 
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################
"""Decimal input widget for iCopy-X / iCopy-XS.

Features:
- Enter digits 0-9, starting from one editable digit.
- UP/DOWN changes a digit; LEFT/RIGHT moves or extends the input.
- Underline the active digit; center label + value on one line when possible.
- If the combined text is too wide, put the label above centered digits.
- Use actual Canvas font metrics to position digits and check screen fit.
- Respect the configured max_length (default: 13 digits).
- Keep original colors, font, hint and key-handling methods.
- getValue() returns decimal text, including any leading zeroes.
- This module does not convert, encode or write RFID tags.

Copyright (c) 2026: jareckib
"""

import threading

from lib._constants import SCREEN_W, CONTENT_Y0, CONTENT_H
from lib import resources

LABEL_COLOR = '#000000'
DIGIT_COLOR = '#0000FF'
DEFAULT_TEXT_COLOR = DIGIT_COLOR
HINT_COLOR = '#606060'

TAG = '_dec_input'


class FreeDecInput(object):
    """Grows a decimal number one digit at a time; no fixed-width boxes."""

    def __init__(self, canvas, label='', hint='', max_length=13,
                 x0=8, font_size=13, hint_font_size=10, y_offset=None,
                 text_color=DEFAULT_TEXT_COLOR):
        self._canvas = canvas
        self._label = label
        self._hint = hint
        self._max_length = max(1, int(max_length))
        self._owner_thread = threading.get_ident()
        self._x0 = x0
        self._font = resources.get_font(font_size)
        self._hint_font = resources.get_font(hint_font_size)
        default_y = CONTENT_Y0 + CONTENT_H // 2
        self._y_offset = default_y if y_offset is None else int(y_offset)
        self._text_color = text_color
        self._digits = ['0']
        self._cursor = 0

    def _check_ui_thread(self):
        return  # Existing plugin is responsible for UI-thread scheduling

    def _layout(self, value):
        """Return layout based on measured pixels, allowing a two-line fallback."""
        margin = max(4, self._x0)
        usable = SCREEN_W - 2 * margin
        if usable <= 0:
            return None
        combined = self._text_width(self._label + value)
        if combined <= usable:
            left = max(margin, (SCREEN_W - combined) // 2)
            return (left, left + self._text_width(self._label),
                    self._y_offset, self._y_offset)
        digit_width = self._text_width(value)
        if digit_width > usable or self._text_width(self._label) > usable:
            return None
        return (max(margin, (SCREEN_W - self._text_width(self._label)) // 2),
                max(margin, (SCREEN_W - digit_width) // 2),
                self._y_offset - 10, self._y_offset + 10)

    def _fits(self, value):
        """Check whether digits fit in one or two rows without clipping."""
        return self._layout(value) is not None

    def _text_width(self, text):
        """Measure text with the actual Canvas font, not a font-spec string."""
        if not text:
            return 0
        item = self._canvas.create_text(0, 0, text=text, font=self._font,
                                        anchor='w', tags='_input_measure')
        try:
            rect = self._canvas.bbox(item)
            return rect[2] - rect[0] if rect else 0
        finally:
            self._canvas.delete(item)

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
        self._check_ui_thread()
        self._canvas.delete(TAG)

    def rollUp(self):
        d = int(self._digits[self._cursor])
        self._digits[self._cursor] = str((d + 1) % 10)
        self._redraw()

    def rollDown(self):
        d = int(self._digits[self._cursor])
        self._digits[self._cursor] = str((d - 1) % 10)
        self._redraw()

    def moveLeft(self):
        if self._cursor > 0:
            self._cursor -= 1
            self._redraw()

    def moveRight(self):
        if self._cursor < len(self._digits) - 1:
            self._cursor += 1
        elif len(self._digits) < self._max_length and self._fits(''.join(self._digits) + '0'):
            self._digits.append('0')
            self._cursor += 1
        # already at max_length and at the edge: nowhere further to grow
        self._redraw()

    def getValue(self):
        """Current digits as typed, e.g. '39' or '0004213039'."""
        return ''.join(self._digits)

    def length(self):
        return len(self._digits)

    # -- drawing -----------------------------------------------------

    def _redraw(self):
        self._check_ui_thread()
        canvas = self._canvas
        canvas.delete(TAG)

        value = ''.join(self._digits)
        layout = self._layout(value)
        if layout is None:
            return
        label_x, digit_start, label_y, digit_y = layout
        if self._label:
            canvas.create_text(
                label_x, label_y, text=self._label, fill=LABEL_COLOR,
                font=self._font, anchor='w', tags=TAG,
            )
        for i, ch in enumerate(self._digits):
            x = digit_start + self._text_width(''.join(self._digits[:i]))
            item = canvas.create_text(
                x, digit_y, text=ch, fill=self._text_color,
                font=self._font, anchor='w', tags=TAG,
            )
            bbox = canvas.bbox(item)
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            if i == self._cursor:
                canvas.create_line(
                    x0, y1 + 2, x1, y1 + 2,
                    fill=self._text_color, width=2, tags=TAG,
                )

        if self._hint:
            canvas.create_text(
                SCREEN_W // 2, CONTENT_Y0 + CONTENT_H - 2,
                text=self._hint, fill=HINT_COLOR,
                font=self._hint_font, anchor='s', justify='center', tags=TAG,
            )
