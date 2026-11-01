##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
# Copyright (c) 2026: jareckib
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################
"""Single-line filename-safe text input for iCopy-X / iCopy-XS.

Features:
- Enter uppercase A-Z, lowercase a-z, digits 0-9 and -_.() or space.
- Exclude characters forbidden in Windows filenames and control characters.
- UP/DOWN edits the current character within the selected group.
- M2 / nextCharset() cycles the existing four character groups:
  UPPER, LOWER, DIGITS and SPECIAL.
- LEFT/RIGHT moves the cursor or appends a character; the cursor is underlined.
- Keep the label and value left-aligned on one line, without centering or wrapping.
- Calculate available space dynamically from the label, selected font and
  screen width using Canvas.bbox() before extending or changing text.
- No fixed 20-character limit; an optional max_length set by the caller
  can impose an additional limit.
- getValue() returns the text as entered, including any trailing spaces.

Existing character-group switching behavior is retained. This update concerns
the single-line input width calculation, not a new charset-switching feature.

Copyright (c) 2026: jareckib
"""

import threading

from lib._constants import SCREEN_W, CONTENT_Y0, CONTENT_H
from lib import resources

UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWER = 'abcdefghijklmnopqrstuvwxyz'
DIGITS = '0123456789'
SPECIAL = '-_.() '

# Order matters: this is the order M2 cycles through.
CHARSETS = (UPPER, LOWER, DIGITS, SPECIAL)
CHARSET_NAMES = ('ABC', 'abc', '123', '-_.')

LABEL_COLOR = '#000000'
VALUE_COLOR = '#0000FF'
DEFAULT_TEXT_COLOR = VALUE_COLOR
HINT_COLOR = '#606060'

TAG = '_txt_input'


class FreeTextInput(object):
    """Grows a filename-safe string one character at a time."""

    def __init__(self, canvas, label='', hint='', max_length=None,
                 per_line=10, x0=8, font_size=13, hint_font_size=10,
                 line_gap=20, y_offset=9, text_color=DEFAULT_TEXT_COLOR):
        self._canvas = canvas
        self._owner_thread = threading.get_ident()
        self._label = label
        self._hint = hint
        self._max_length = None if max_length is None else max(1, int(max_length))
        self._per_line = per_line
        self._x0 = x0
        self._font = resources.get_font(font_size)
        self._hint_font = resources.get_font(hint_font_size)
        self._line_gap = line_gap
        self._y_offset = y_offset
        self._text_color = text_color
        self._charset_idx = 0  # start on UPPER
        self._chars = [CHARSETS[self._charset_idx][0]]  # 'A'
        self._cursor = 0

    def _check_ui_thread(self):
        return  # Existing plugin is responsible for UI-thread scheduling

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

    def getCharsetName(self):
        """Short label for the active group ('ABC'/'abc'/'123'/'-_.'),
        e.g. to show on the M2 button."""
        return CHARSET_NAMES[self._charset_idx]

    def show(self):
        self._redraw()

    def hide(self):
        self._check_ui_thread()
        self._canvas.delete(TAG)

    def _normalize_current_char(self):
        """Ensure current cursor char belongs to active charset."""
        charset = CHARSETS[self._charset_idx]
        ch = self._chars[self._cursor]
        if ch not in charset:
            proposed = self._chars[:]
            proposed[self._cursor] = charset[0]
            if self._fits_text(''.join(proposed)):
                self._chars[self._cursor] = charset[0]

    def rollUp(self):
        charset = CHARSETS[self._charset_idx]
        current = self._chars[self._cursor]
        idx = charset.index(current) if current in charset else -1
        candidate = charset[(idx + 1) % len(charset)]
        proposed = self._chars[:]
        proposed[self._cursor] = candidate
        if self._fits_text(''.join(proposed)):
            self._chars[self._cursor] = candidate
        self._redraw()

    def rollDown(self):
        charset = CHARSETS[self._charset_idx]
        current = self._chars[self._cursor]
        idx = charset.index(current) if current in charset else 0
        candidate = charset[(idx - 1) % len(charset)]
        proposed = self._chars[:]
        proposed[self._cursor] = candidate
        if self._fits_text(''.join(proposed)):
            self._chars[self._cursor] = candidate
        self._redraw()

    def nextCharset(self):
        """Switch to the next character group (UPPER->lower->digits->
        special->UPPER...) and reset the character under the cursor
        to that group's first entry if needed."""
        self._charset_idx = (self._charset_idx + 1) % len(CHARSETS)
        charset = CHARSETS[self._charset_idx]
        if self._chars[self._cursor] not in charset:
            proposed = self._chars[:]
            proposed[self._cursor] = charset[0]
            if self._fits_text(''.join(proposed)):
                self._chars[self._cursor] = charset[0]
        self._redraw()

    def moveLeft(self):
        if self._cursor > 0:
            self._cursor -= 1
            self._redraw()

    def _fits_text(self, value):
        """Check the complete label and value against the screen width."""
        margin = max(4, int(self._x0))
        available = SCREEN_W - margin - 4
        return self._text_width(self._label + ' ' + value) <= available

    def _get_input_limit(self):
        """Return optional caller limit; width is always checked separately."""
        return self._max_length

    def moveRight(self):
        input_limit = self._get_input_limit()
        if self._cursor < len(self._chars) - 1:
            self._cursor += 1
        elif ((input_limit is None or len(self._chars) < input_limit) and
              self._fits_text(''.join(self._chars) + CHARSETS[self._charset_idx][0])):
            self._chars.append(CHARSETS[self._charset_idx][0])
            self._cursor += 1
        self._redraw()

    def getValue(self):
        """Current text as typed, e.g. 'ASDFG0987'. May have trailing
        spaces if the user rolled to ' ' and stopped there -- callers
        that use this as a filename should .strip() it."""
        return ''.join(self._chars)

    def length(self):
        return len(self._chars)

    # -- drawing -----------------------------------------------------

    def _redraw(self):
        self._check_ui_thread()
        canvas = self._canvas
        canvas.delete(TAG)

        text = ''.join(self._chars)
        label_text = self._label + ' '
        value_text = text

        # label black
        label_item = canvas.create_text(
            self._x0,
            self._y_offset,
            text=label_text,
            fill=LABEL_COLOR,
            font=self._font,
            anchor='w',
            tags=TAG,
        )

        # draw value chars, with underline under active char
        x = self._x0 + self._text_width(label_text)
        for i, ch in enumerate(value_text):
            item = canvas.create_text(
                x,
                self._y_offset,
                text=ch,
                fill=self._text_color,
                font=self._font,
                anchor='w',
                tags=TAG,
            )
            bbox = canvas.bbox(item)
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            if i == self._cursor:
                canvas.create_line(
                    x0, y1 + 2, x1, y1 + 2,
                    fill=self._text_color,
                    width=2,
                    tags=TAG,
                )
            x = x1

        if self._hint:
            canvas.create_text(
                SCREEN_W // 2, CONTENT_Y0 + CONTENT_H - 2,
                text=self._hint,
                fill=HINT_COLOR,
                font=self._hint_font,
                anchor='s',
                tags=TAG,
            )
