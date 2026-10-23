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
"""Free-growing filename-safe text input widget.

Same mechanics as :mod:`lib.input_dec` / :mod:`lib.input_hex`, but
rolls through character sets restricted to characters that are safe
in filenames on both Windows and Linux -- important here since the
iCopy-X exports its user partition as a USB mass-storage drive, and
anything written on-device may end up copied/renamed on a PC too.

Excluded everywhere: ``\\ / : * ? " < > |`` (forbidden in Windows
filenames) and control characters.

Unlike input_dec/input_hex (one flat alphabet), this one has FOUR
character groups, switched with ``nextCharset()`` (bind to M2), in
this order:

    1. UPPER   -- A-Z
    2. LOWER   -- a-z
    3. DIGITS  -- 0-9
    4. SPECIAL -- - _ . ( ) space

UP/DOWN roll within whichever group is currently active; switching
groups with M2 resets the character under the cursor to the first
letter of the new group (e.g. 'A', 'a', '0', '-') so you always know
where you are. Starts on UPPER, so the very first character shown is
'A'.

Wire-up is identical to FreeDecInput/FreeHexInput -- imported directly
by a plugin and driven through ``call:`` (see ``lib.plugin_activity``'s
``_handle_call``):

    from lib.input_txt import FreeTextInput

    def show_txt_input(self):
        canvas = self.host.getCanvas()
        self._txt = FreeTextInput(canvas, label='Name:', max_length=20, y_offset=9)
        self._txt.show()
        return {'status': 'ok'}

    def txt_roll_up(self):      self._txt.rollUp()
    def txt_roll_down(self):    self._txt.rollDown()
    def txt_move_left(self):    self._txt.moveLeft()
    def txt_move_right(self):   self._txt.moveRight()
    def txt_next_charset(self): self._txt.nextCharset()

    def do_capture_txt(self):
        value = self._txt.getValue()
        ...

and the matching ``ui.json`` screen:

    "content": {"type": "empty"},
    "keys": {
        "UP":    "call:txt_roll_up",
        "DOWN":  "call:txt_roll_down",
        "LEFT":  "call:txt_move_left",
        "RIGHT": "call:txt_move_right",
        "M2":    "call:txt_next_charset",
        "OK":    "run:do_capture_txt"
    }
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

    def __init__(self, canvas, label='', hint='', max_length=20,
                 per_line=10, x0=8, font_size=13, hint_font_size=10,
                 line_gap=20, y_offset=9, text_color=DEFAULT_TEXT_COLOR):
        self._canvas = canvas
        self._owner_thread = threading.get_ident()
        self._label = label
        self._hint = hint
        self._max_length = max_length
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
        self.max_total_chars = 20

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
            self._chars[self._cursor] = charset[0]

    def rollUp(self):
        self._normalize_current_char()
        charset = CHARSETS[self._charset_idx]
        idx = charset.index(self._chars[self._cursor])
        self._chars[self._cursor] = charset[(idx + 1) % len(charset)]
        self._redraw()

    def rollDown(self):
        self._normalize_current_char()
        charset = CHARSETS[self._charset_idx]
        idx = charset.index(self._chars[self._cursor])
        self._chars[self._cursor] = charset[(idx - 1) % len(charset)]
        self._redraw()

    def nextCharset(self):
        """Switch to the next character group (UPPER->lower->digits->
        special->UPPER...) and reset the character under the cursor
        to that group's first entry if needed."""
        self._charset_idx = (self._charset_idx + 1) % len(CHARSETS)
        charset = CHARSETS[self._charset_idx]
        if self._chars[self._cursor] not in charset:
            self._chars[self._cursor] = charset[0]
        self._redraw()

    def moveLeft(self):
        if self._cursor > 0:
            self._cursor -= 1
            self._redraw()

    def _get_input_limit(self):
        # Use measured pixel width; preserve the original 20-character ceiling.
        char_limit = max(1, self.max_total_chars - len(self._label) - 1)
        max_chars = min(max(1, int(self._max_length)), char_limit)
        remaining = SCREEN_W - self._x0 - 4 - self._text_width(self._label + ' ')
        if remaining <= 0:
            return 1
        count = 0
        for i in range(max_chars):
            ch = self._chars[i] if i < len(self._chars) else CHARSETS[self._charset_idx][0]
            if self._text_width(''.join(self._chars[:min(i, len(self._chars))]) +
                                  (ch if i >= len(self._chars) else '')) > remaining:
                break
            count += 1
        return max(1, count)

    def moveRight(self):
        input_limit = self._get_input_limit()
        if self._cursor < len(self._chars) - 1:
            self._cursor += 1
        elif len(self._chars) < input_limit:
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
        value_text = text[:self._get_input_limit()]

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
        label_bbox = canvas.bbox(label_item)
        x = label_bbox[2] if label_bbox else self._x0 + 55
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
