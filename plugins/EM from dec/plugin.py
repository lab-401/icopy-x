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
The plugin converts it to a hex UID, encodes EM4102 and clones to T5577.
"""

import re
import time

from lib.input_dec import FreeDecInput

MIN_STATUS_SECONDS = 2.0


def _status_pause(started):
    """Keep a background progress screen visible for at least 2 seconds."""
    remaining = MIN_STATUS_SECONDS - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)


TIMEOUT_WRITE = 8000
TIMEOUT_CLONE = 15000
TIMEOUT_VERIFY = 5000
TIMEOUT_DETECT = 15000
TIMEOUT_SEARCH = 5000


def dec_to_hex_uid(dec_str):
    if not re.match(r'^\d{1,10}$', dec_str):
        return None
    return '{:010X}'.format(int(dec_str))

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

    def do_init(self):
        self.host.set_var('error_msg', '')
        self.host.set_var('dec_id', '')
        self.host.set_var('hex_uid', '')
        self.host.set_var('clone_count', '0')
        return {'status': 'ok'}

    def show_dec_input(self):
        canvas = self.host.getCanvas()
        self._dec = FreeDecInput(
            canvas, label='DEC:',
            hint='\nUp/Down - digit\nL/R: move',
            max_length=10,
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

    def dec_back_cleanse(self):
        if self._dec is not None:
            self._dec.hide()
            self._dec = None
        return {'status': 'ok'}

    def do_capture_dec(self):
        self.host.set_var('error_msg', '')
        dec = self._dec.getValue() if self._dec is not None else ''

        if not dec:
            self.host.set_var('error_msg', 'Enter a digit.')
            return {'status': 'error'}

        if int(dec) == 0:
            self.host.set_var('error_msg', 'ID cannot be all zeros.')
            return {'status': 'error'}

        uid = dec_to_hex_uid(dec)
        if uid is None:
            self.host.set_var('error_msg', 'Conversion failed.')
            return {'status': 'error'}

        if self._dec is not None:
            self._dec.hide()
            self._dec = None

        self.host.set_var('dec_id', dec)
        self.host.set_var('hex_uid', uid)
        return {'status': 'ok'}

    def _error(self, message):
        self.host.set_var('error_msg', message)
        return {'status': 'error'}

    def do_quick_search(self):
        _status_started = time.monotonic()
        try:
            """Short preliminary LF scan; never treat an EM ID as proof of T5577."""
            self.host.set_var('error_msg', '')
            try:
                ok, output = self._pm3('lf search', TIMEOUT_SEARCH)
            except Exception:
                return self._error('LF search timed out or failed.')
            if not ok:
                return self._error('LF search timed out or failed.')
            # A blank/unconfigured T5577 may not expose an EM410x ID.
            # The following detect step makes the final T55x7 decision.
            if re.search(r'\b(?:BUSY|timeout|timed out)\b', output or '', re.IGNORECASE):
                return self._error('LF search timed out or failed.')
            return {'status': 'ok'}
        finally:
            _status_pause(_status_started)


    def do_precheck(self):
        _status_started = time.monotonic()
        try:
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
                return self._error('T5577 not detected.\nCheck tag position.')
            return {'status': 'ok'}
        finally:
            _status_pause(_status_started)


    def do_write(self):
        _status_started = time.monotonic()
        try:
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
        finally:
            _status_pause(_status_started)


    def do_verify(self):
        _status_started = time.monotonic()
        try:
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
            return {'status': 'done'}
        finally:
            _status_pause(_status_started)

