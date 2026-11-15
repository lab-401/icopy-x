##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""EM4102 From Decimal plugin for iCopy-X/XS.
Copyright (c) 2026: jareckib

Enter the decimal representation of a 40-bit EM4102 ID (1 to
1099511627775, up to 13 digits). An engraved number is suitable only
when it represents that ID directly; other printed-number formats
are not decoded by this plugin.

The plugin converts the ID to 10 hexadecimal digits, checks for a
T5577 destination, writes it and verifies the ID by reading it back.
The completed-tag count increases only after a matching readback.

Each explicit user read/write attempt renews the executor recovery budget
when supported. Failed reads request one managed reader restart; retry is
offered only after confirmed recovery. Block writes and automatic
verification do not renew the budget, and writes are never replayed
automatically. UI translations are in lang/fr.json.
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
TIMEOUT_DETECT = 10000
TIMEOUT_SEARCH = 5000
MIN_STAGE_SECONDS = 3.0


def dec_to_hex_uid(dec_str):
    if not isinstance(dec_str, str) or not re.fullmatch(r'[0-9]{1,13}', dec_str):
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
        match = re.search(r'\bEM\s*410x\s+ID\s+(\S+)', line, re.IGNORECASE)
        if match:
            token = match.group(1)
            return token.upper() if re.fullmatch(r'[0-9A-Fa-f]{10}', token) else None
    return None

class Em4102DecPlugin(object):

    def __init__(self, host=None):
        self.host = host
        self._dec = None
        self._recovery_status = None

    def _begin_user_operation(self):
        """Worker-only fresh recovery budget for an explicit user attempt."""
        try:
            import executor
        except ImportError:
            return  # Older hosts may expose PM3 only through the plugin API.
        reset = getattr(executor, 'resetReworkCount', None)
        if callable(reset):
            reset()

    def _pm3(self, cmd, timeout=TIMEOUT_WRITE):
        return self.host.pm3_command(cmd, timeout=timeout)

    def on_destroy(self):
        """Native host invokes cleanup on the UI thread, including Exit/PWR."""
        if self._dec is not None:
            self._dec.hide()
            self._dec = None

    def _read_transport_error(self, message):
        """Request recovery after a failed read, never replay the command."""
        self._recovery_status = self._error(message)['status']
        return {'status': 'recover_reader'}

    def do_recover_reader(self):
        """Worker-only: one managed restart, with explicit success required."""
        status = self._recovery_status
        self._recovery_status = None
        try:
            import executor
            recovered = status is not None and executor.reworkPM3All() is True
        except Exception:
            recovered = False
        if recovered:
            return {'status': status}
        self.host.set_var('error_line1', self.host.tr('PM3 restart failed.'))
        self.host.set_var('error_line2', self.host.tr('Restart device.'))
        return {'status': 'recovery_failed'}

    def do_init(self):
        self.host.set_var('error_msg', '')
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
        self.host.set_var('dec_id', '')
        self.host.set_var('hex_uid', '')
        self.host.set_var('clone_count', '0')
        self.host.set_var('tags_label', self.host.tr('Tags:') + ' 0')
        return {'status': 'ok'}

    def show_dec_input(self):
        if self._dec is not None:
            self._dec.hide()
            self._dec = None
        canvas = self.host.getCanvas()
        self._dec = SpacedFreeDecInput(
            canvas, label=self.host.tr('DEC:'),
            hint=self.host.tr('SRW - return to input\nUp/Down - digit\nLeft/Right - cursor'),
            max_length=13,
            font_size=12, hint_font_size=12,
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
            return self._validation_error(self.host.tr('Enter a digit.'), self.host.tr('Enter a digit.'))

        if re.fullmatch(r'0+', dec):
            return self._validation_error('ID cannot be all zeros.', self.host.tr('ID cannot be'), self.host.tr('all zeros.'))

        uid = dec_to_hex_uid(dec)
        if uid is None:
            return self._validation_error('Invalid DEC (max 40-bit).', self.host.tr('Invalid DEC'), self.host.tr('(max 40-bit).'))

        if self._dec is not None:
            self._dec.hide()
            self._dec = None

        self.host.set_var('dec_id', dec)
        self.host.set_var('hex_uid', uid)
        return {'status': 'ok'}

    def _error(self, message):
        # Explicit display fragments keep every translation extractable.
        messages = {
            'LF search failed': (self.host.tr('LF search failed'), '', 'error'),
            'T5577 not detected': ('T5577', self.host.tr('not detected'), 'error'),
            'No valid UID.': (self.host.tr('No valid UID.'), '', 'error'),
            'T5577 detection timed out or failed.': (
                self.host.tr('T5577 detection'), self.host.tr('timed out or failed.'), 'error_t5577_timeout'),
            'Clone command timed out or failed.': (
                self.host.tr('Clone command failed.'), self.host.tr('Check T5577 position.'), 'error_clone_failed'),
            'Clone failed.\nCheck T5577 position.': (
                self.host.tr('Clone failed.'), self.host.tr('Check T5577 position.'), 'error_clone_failed'),
            'Verification command timed out or failed.': (
                self.host.tr('Verification command'), self.host.tr('timed out or failed.'), 'error_verification_timeout'),
            'Verification mismatch.\nCheck T5577 position.': (
                self.host.tr('Verification mismatch.'), self.host.tr('Check T5577 position.'), 'error_verification_mismatch'),
            'Verify failed.\nCheck T5577 position.': (
                self.host.tr('Verify failed.'), self.host.tr('Check T5577 position.'), 'error_verify_failed'),
        }
        first, second, status = messages.get(message, (self.host.tr('Operation failed.'), '', 'error'))
        self.host.set_var('error_msg', message)
        self.host.set_var('error_line1', first)
        self.host.set_var('error_line2', second)
        return {'status': status}

    def draw_error(self):
        """UI-only error lines using the native bottom-bar font (16pt)."""
        from tkinter import font as tkfont
        canvas = self.host.getCanvas()
        canvas.delete('_jr_content')
        # Use exactly the same font request as JsonRenderer._render_buttons.
        face = resources.get_font(16)
        measure = tkfont.Font(font=face).measure
        texts = [self.host.tr(self.host.get_var(name, ''))
                 for name in ('error_line1', 'error_line2')]
        if not any(texts):
            texts = [self.host.tr('Operation failed.')]
        rows = []
        for text in texts:
            line = ''
            for word in text.split():
                while measure(word) > 222:
                    if line:
                        rows.append(line); line = ''
                    stop = 1
                    while stop < len(word) and measure(word[:stop+1]) <= 222:
                        stop += 1
                    rows.append(word[:stop]); word = word[stop:]
                candidate = line + (' ' if line else '') + word
                if line and measure(candidate) > 222:
                    rows.append(line); line = word
                else:
                    line = candidate
            if line:
                rows.append(line)
        height = tkfont.Font(font=face).metrics('linespace')
        y = (CONTENT_Y0 + CONTENT_H/2 - height/2) if len(rows) == 1 else 81 if len(rows) <= 3 else 62 if len(rows) == 4 else 43
        for row in rows:
            canvas.create_text(SCREEN_W//2, y, text=row, anchor='n',
                               font=face, fill='#D62636', tags='_jr_content')
            y += max(19, height + 1)
        return {'status': 'drawn'}

    def do_quick_search(self):
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
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
            self._begin_user_operation()
            ok, output = self._pm3('lf search', TIMEOUT_SEARCH)
        except Exception:
            return self._read_transport_error('LF search failed')
        if not ok:
            return self._read_transport_error('LF search failed')
        # A blank/unconfigured T5577 may not expose an EM410x ID.
        # The following detect step makes the final T55x7 decision.
        if re.search(r'\b(?:BUSY|timeout|timed out)\b', output or '', re.IGNORECASE):
            return self._read_transport_error('LF search failed')
        return {'status': 'ok'}

    def do_precheck(self):
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
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
            return self._read_transport_error('T5577 detection timed out or failed.')
        if not ok:
            return self._read_transport_error('T5577 detection timed out or failed.')
        if not re.search(r'Chip type\.{2,}\s*T55x7\b', output or '', re.IGNORECASE):
            return self._error('T5577 not detected')
        return {'status': 'ok'}

    def do_write(self):
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
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
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
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
            return self._read_transport_error('Verification command timed out or failed.')
        if not ok:
            return self._read_transport_error('Verification command timed out or failed.')
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
        self.host.set_var('tags_label', self.host.tr('Tags:') + ' ' + str(count))
        return {'status': 'done'}

    # Data rows and measured errors use Canvas; other screen messages
    # and headings are rendered by ui.json / Lab401 JsonRenderer.
    # Tag _jr_content makes native renderer clear these rows on state change.
    def _draw_pair(self, label, value, y):
        from tkinter import font as tkfont
        canvas = self.host.getCanvas()
        face = resources.get_font(12)
        measure = tkfont.Font(font=face).measure
        name = label.rstrip(' :')
        prefix = name + ': '
        x = (SCREEN_W - measure(prefix + value)) / 2
        canvas.create_text(x, y, text=name, font=face, fill='#64748B',
                           anchor='nw', tags='_jr_content')
        canvas.create_text(x + measure(name), y, text=':', font=face,
                           fill='#222222', anchor='nw', tags='_jr_content')
        canvas.create_text(x + measure(prefix), y, text=value, font=face,
                           fill='#1647D6', anchor='nw', tags='_jr_content')

    def draw_id_pairs(self):
        self._draw_pair('DEC: ', self.host.get_var('dec_id', ''), 62)
        self._draw_pair('HEX: ', self.host.get_var('hex_uid', ''), 81)
        return {'status': 'drawn'}

    def draw_success_pairs(self):
        self._draw_pair('DEC: ', self.host.get_var('dec_id', ''), 90)
        self._draw_pair('HEX: ', self.host.get_var('hex_uid', ''), 111)
        canvas = self.host.getCanvas()
        canvas.create_text(SCREEN_W//2, 132,
                           text=self.host.tr('Tags:') + ' ' + self.host.get_var('clone_count', '0'),
                           font=resources.get_font(12), fill='#222222',
                           anchor='n', tags='_jr_content')
        canvas.create_text(SCREEN_W//2, 190, text=self.host.tr('SRW - Exit'),
                           font=resources.get_font(10), fill='#1647D6',
                           anchor='center', tags='_jr_content')
        return {'status': 'drawn'}
