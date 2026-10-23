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
"""Free-growing decimal digit input widget.

Unlike the fixed-width ``input_dec`` content type (ten boxes shown up
front, handled by ``InputMethods`` in :mod:`lib.widget`), this widget
starts with a single digit and grows one position at a time as the
user moves right -- useful for a variable-length decimal ID where you
don't want to stare at nine leading zero boxes to enter e.g. "39".

This is plain Python with no dependency on :mod:`lib.widget`, meant to
be imported directly by a plugin and driven through the ``call:``
action (see ``lib.plugin_activity``'s ``_handle_call``).  A plugin
wires it up like this:

    from lib.input_dec import FreeDecInput

    def show_dec_input(self):
        canvas = self.host.getCanvas()
        self._dec = FreeDecInput(canvas, label='INPUT DEC:',
                                  hint='Up/Down digit   Left/Right move')
        self._dec.show()
        return {'status': 'ok'}

    def dec_roll_up(self):    self._dec.rollUp()
    def dec_roll_down(self):  self._dec.rollDown()
    def dec_move_left(self):  self._dec.moveLeft()
    def dec_move_right(self): self._dec.moveRight()

    def do_capture_dec(self):
        dec = self._dec.getValue()
        ...

and the matching ``ui.json`` screen:

    "content": {"type": "empty"},
    "keys": {
        "UP":    "call:dec_roll_up",
        "DOWN":  "call:dec_roll_down",
        "LEFT":  "call:dec_move_left",
        "RIGHT": "call:dec_move_right",
        "OK":    "run:do_capture_dec",
        "M2":    "run:do_capture_dec"
    }

``"type": "empty"`` is required so the framework never attaches its
own ``InputMethods`` widget -- that would also intercept UP/DOWN/
LEFT/RIGHT and this widget would never see them.

No delete key: there's nothing to delete.  Moving left just reviews
an already-entered digit (rolling it up/down edits it in place);
moving right past the last entered digit grows the number by one new
digit (default ``'0'``), up to ``max_length``.  The digit currently
under the cursor is always underlined, so it's clear what UP/DOWN
will change -- wherever the cursor happens to be.
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

    def __init__(self, canvas, label='', hint='', max_length=10,
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

    def _fits(self, value):
        """Measure the actual rendered label + digits, not character count."""
        available = SCREEN_W - self._x0 - 4
        if available <= 0:
            return False
        return self._text_width(self._label + value) <= available

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

        x = self._x0
        if self._label:
            item = canvas.create_text(
                x, self._y_offset, text=self._label, fill=LABEL_COLOR,
                font=self._font, anchor='w', tags=TAG,
            )
            bbox = canvas.bbox(item)
            if bbox:
                x = bbox[2]

        for i, ch in enumerate(self._digits):
            item = canvas.create_text(
                x, self._y_offset, text=ch, fill=self._text_color,
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
            x = x1

        if self._hint:
            canvas.create_text(
                SCREEN_W // 2, CONTENT_Y0 + CONTENT_H - 2,
                text=self._hint, fill=HINT_COLOR,
                font=self._hint_font, anchor='s', tags=TAG,
            )
