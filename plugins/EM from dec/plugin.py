##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
# Copyright (c) 2026: jareckib
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""EM4102 From Decimal plugin for iCopy-XS

Useful for recovering damaged tags that cannot be read by iCopy-X 
but still have a visible engraved ID number.
The plugin accepts up to 13 decimal digits (0 to 1099511627775),
validates the 40-bit EM4102 ID range, converts it to a 10-digit
hex UID, and clones it to T5577.
"""

import re
import time
from lib import resources
from lib._constants import SCREEN_W, CONTENT_Y0, CONTENT_H

from lib.input_dec import FreeDecInput

class SpacedFreeDecInput(FreeDecInput):
    """Render the three hint lines with 1 px more vertical spacing."""

    def _redraw(self):
        hint = self._hint
        self._hint = ''
        try:
            super(SpacedFreeDecInput, self)._redraw()
        finally:
            self._hint = hint
        if not hint:
            return
        lines = hint.split('\n')
        canvas = self._canvas
        probe = canvas.create_text(0, 0, text='Ag', font=self._hint_font, anchor='s', tags='_dec_hint_measure')
        try:
            bbox = canvas.bbox(probe)
            line_height = bbox[3] - bbox[1] if bbox else 12
        finally:
            canvas.delete(probe)
        step = line_height + 1
        bottom = CONTENT_Y0 + CONTENT_H - 2
        for index, line in enumerate(reversed(lines)):
            canvas.create_text(SCREEN_W // 2, bottom - index * step,
                               text=line, fill='#606060', font=self._hint_font,
                               anchor='s', tags='_dec_input')


TIMEOUT_WRITE = 8000
TIMEOUT_CLONE = 15000
TIMEOUT_VERIFY = 5000
TIMEOUT_DETECT = 15000
TIMEOUT_SEARCH = 5000
MIN_STAGE_SECONDS = 3.0


def dec_to_hex_uid(dec_str):
    if not re.match(r'^[0-9]{1,13}$', dec_str):
        return None
    value = int(dec_str)
    if value > 0xFFFFFFFFFF:
        return None
    return '{:010X}'.format(value)

def _extract_em410x_id(output):
    """Pull the 10-hex-digit ID out of 'lf em 410x reader' output."""
    if not output:
        return None
    for line in output.splitlines():
        m = re.search(r'\bEM\s*410x\s*ID\s*([0-9A-Fa-f]{10})\b', line, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None
class Em4102DecPlugin(object):

    def __init__(self, host=None):
        self.host = host
        self._dec = None

    def _pm3(self, cmd, timeout=TIMEOUT_WRITE):
        return self.host.pm3_command(cmd, timeout=timeout)

    def _tr(self, value):
        """Translate direct-widget strings through the native plugin translator."""
        translator = getattr(self.host, 'tr', None)
        if callable(translator):
            try:
                return translator(value)
            except Exception:
                pass
        return value

    def do_init(self):
        self.host.set_var('error_msg', '')
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
        self.host.set_var('dec_id', '')
        self.host.set_var('hex_uid', '')
        self.host.set_var('clone_count', '0')
        self.host.set_var('tags_label', self._tr('Tags:') + ' 0')
        return {'status': 'ok'}

    def show_dec_input(self):
        if self._dec is not None:
            self._dec.hide()
            self._dec = None
        canvas = self.host.getCanvas()
        self._dec = SpacedFreeDecInput(
            canvas, label=self._tr('DEC:'),
            hint=self._tr('SRW - return to input\n▲▼ - change digit\n◀ ▶ - move cursor'),
            max_length=13,
            font_size=13, hint_font_size=11,
            y_offset=CONTENT_Y0 + 45,
        )
        self._dec.show()

    def dec_roll_up(self):
        if self._dec is not None:
            self._dec.rollUp()

    def dec_roll_down(self):
        if self._dec is not None:
            self._dec.rollDown()

    def dec_move_left(self):
        if self._dec is not None:
            self._dec.moveLeft()

    def dec_move_right(self):
        if self._dec is not None:
            self._dec.moveRight()

    def dec_return_to_input(self):
        """SRW starts a fresh DEC entry without leaving the plugin."""
        if self._dec is not None:
            self._dec.hide()
            self._dec = None
        self.show_dec_input()
        return {'status': 'drawn'}

    def _validation_error(self, message, first, second=''):
        self.host.set_var('error_msg', message)
        self.host.set_var('error_line1', first)
        self.host.set_var('error_line2', second)
        if self._dec is not None:
            self._dec.hide()
            self._dec = None
        return {'status': 'error'}

    def do_capture_dec(self):
        self.host.set_var('error_msg', '')
        dec = self._dec.getValue() if self._dec is not None else ''

        if not dec:
            return self._validation_error('Enter a digit.', 'Enter a digit.')

        if int(dec) == 0:
            return self._validation_error('ID cannot be all zeros.', 'ID cannot be', 'all zeros.')

        uid = dec_to_hex_uid(dec)
        if uid is None:
            return self._validation_error('Invalid DEC (max 40-bit).', 'Invalid DEC', '(max 40-bit).')

        if self._dec is not None:
            self._dec.hide()
            self._dec = None

        self.host.set_var('dec_id', dec)
        self.host.set_var('hex_uid', uid)
        return {'status': 'ok'}

    def _error(self, message):
        self.host.set_var('error_msg', message)
        # Two independently centered lines avoid multiline layout ambiguity.
        if message == 'LF search failed':
            lines = ('LF search failed', '')
        elif message == 'T5577 not detected':
            lines = ('T5577', 'not detected')
        else:
            parts = message.split('\n', 1)
            if len(parts) > 1:
                lines = (parts[0], parts[1])
            elif len(message) > 22 and ' ' in message:
                words = message.split()
                best = min(range(1, len(words)),
                           key=lambda i: max(len(' '.join(words[:i])),
                                             len(' '.join(words[i:]))))
                lines = (' '.join(words[:best]), ' '.join(words[best:]))
            else:
                lines = (message, '')
        self.host.set_var('error_line1', lines[0])
        self.host.set_var('error_line2', lines[1])
        error_routes = {
            ('T5577 detection', 'timed out or failed.'): 'error_t5577_timeout',
            ('Clone failed.', 'Check T5577 position.'): 'error_clone_failed',
            ('Verification command', 'timed out or failed.'): 'error_verification_timeout',
            ('Verification mismatch.', 'Check T5577 position.'): 'error_verification_mismatch',
            ('Verify failed.', 'Check T5577 position.'): 'error_verify_failed',
        }
        return {'status': error_routes.get(lines, 'error')}


    def do_quick_search(self):
        started = time.monotonic()
        try:
            return self._worker_do_quick_search()
        finally:
            remaining = MIN_STAGE_SECONDS - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)  # run: background worker only

    def _worker_do_quick_search(self):
        """Short preliminary LF scan; never treat an EM ID as proof of T5577."""
        self.host.set_var('error_msg', '')
        try:
            ok, output = self._pm3('lf search', TIMEOUT_SEARCH)
        except Exception:
            return self._error('LF search failed')
        if not ok:
            return self._error('LF search failed')
        # A blank/unconfigured T5577 may not expose an EM410x ID.
        # The following detect step makes the final T55x7 decision.
        if re.search(r'\b(?:BUSY|timeout|timed out)\b', output or '', re.IGNORECASE):
            return self._error('LF search failed')
        return {'status': 'ok'}

    def do_precheck(self):
        started = time.monotonic()
        try:
            return self._worker_do_precheck()
        finally:
            remaining = MIN_STAGE_SECONDS - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)  # run: background worker only

    def _worker_do_precheck(self):
        self.host.set_var('error_msg', '')
        uid = self.host.get_var('hex_uid', '')
        if not re.fullmatch(r'[0-9A-Fa-f]{10}', uid or '') or int(uid, 16) == 0:
            return self._error('No valid UID.')
        try:
            ok, output = self._pm3('lf t55xx detect', TIMEOUT_DETECT)
        except Exception:
            return self._error('T5577 detection timed out or failed.')
        if not ok:
            return self._error('T5577 detection timed out or failed.')
        if not re.search(r'Chip type\.{2,}\s*T55x7\b', output or '', re.IGNORECASE):
            return self._error('T5577 not detected')
        return {'status': 'ok'}

    def do_write(self):
        started = time.monotonic()
        try:
            return self._worker_do_write()
        finally:
            remaining = MIN_STAGE_SECONDS - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)  # run: background worker only

    def _worker_do_write(self):
        uid = self.host.get_var('hex_uid', '')
        if not re.fullmatch(r'[0-9A-Fa-f]{10}', uid or '') or int(uid, 16) == 0:
            return self._error('No valid UID.')
        try:
            ok, output = self._pm3('lf em 410x clone --id {}'.format(uid.upper()), TIMEOUT_CLONE)
        except Exception:
            return self._error('Clone command timed out or failed.')
        if not ok or re.search(r'\[(?:-|!)\]|\b(?:error|failed|timeout)\b', output or '', re.IGNORECASE):
            return self._error('Clone failed.\nCheck T5577 position.')
        return {'status': 'ok'}

    def do_verify(self):
        started = time.monotonic()
        try:
            return self._worker_do_verify()
        finally:
            remaining = MIN_STAGE_SECONDS - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)  # run: background worker only

    def _worker_do_verify(self):
        uid = (self.host.get_var('hex_uid', '') or '').upper()
        try:
            ok, output = self._pm3('lf em 410x reader', TIMEOUT_VERIFY)
        except Exception:
            return self._error('Verification command timed out or failed.')
        if not ok:
            return self._error('Verification command timed out or failed.')
        read_id = _extract_em410x_id(output)
        if read_id is None:
            return self._error('Verify failed.\nCheck T5577 position.')
        if read_id != uid:
            return self._error('Verification mismatch.\nCheck T5577 position.')
        try:
            count = int(self.host.get_var('clone_count', '0')) + 1
        except (TypeError, ValueError):
            count = 1
        self.host.set_var('clone_count', str(count))
        self.host.set_var('tags_label', self._tr('Tags:') + ' ' + str(count))
        return {'status': 'done'}

    # Only the two mixed-color data rows use Canvas; all screen messages,
    # headings and errors are rendered by ui.json / Lab401 JsonRenderer.
    # Tag _jr_content makes native renderer clear these rows on state change.
    def _draw_pair(self, label, value, y):
        canvas = self.host.getCanvas()
        font = resources.get_font(12)
        probe = canvas.create_text(0, 0, text=label + value, font=font,
                                   anchor='w', tags='_em_measure')
        bounds = canvas.bbox(probe)
        canvas.delete(probe)
        width = bounds[2] - bounds[0] if bounds else 0
        x = (SCREEN_W - width) // 2
        item = canvas.create_text(x, y, text=label, font=font,
                                  fill='#606060', anchor='nw', tags='_jr_content')
        label_box = canvas.bbox(item)
        x = label_box[2] if label_box else x
        canvas.create_text(x, y, text=value, font=font,
                           fill='#0000FF', anchor='nw', tags='_jr_content')

    def draw_id_pairs(self):
        self._draw_pair('DEC: ', self.host.get_var('dec_id', ''), CONTENT_Y0 + 12)
        self._draw_pair('HEX: ', self.host.get_var('hex_uid', ''), CONTENT_Y0 + 39)
        return {'status': 'drawn'}

    def draw_success_pairs(self):
        self._draw_pair('DEC: ', self.host.get_var('dec_id', ''), CONTENT_Y0 + 57)
        self._draw_pair('HEX: ', self.host.get_var('hex_uid', ''), CONTENT_Y0 + 81)
        return {'status': 'drawn'}

