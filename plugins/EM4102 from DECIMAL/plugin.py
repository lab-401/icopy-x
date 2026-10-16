##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################
"""
EM4102 From Decimal plugin for iCopy-XS (author jareckib- Jarek Barwinski)

Useful for recovering damaged tags that cannot be read by iCopy-X 
but still have a visible engraved ID number.
The plugin converts it to a hex UID, encodes EM4102 and clones to T5577.

"""

import re

TIMEOUT_WRITE = 8000
TIMEOUT_CLONE = 15000


def _hex_to_bin40(hex_value):
    if not re.match(r'^[0-9A-Fa-f]{10}$', hex_value):
        return None
    return '{:040b}'.format(int(hex_value, 16))

def _even_parity(bits):
    return '0' if bits.count('1') % 2 == 0 else '1'

def encode_uid(uid_hex):
    uid_bin = _hex_to_bin40(uid_hex.upper())
    if uid_bin is None:
        return None
    start_bits = '1' + '1' * 8
    data_with_parity = ''
    for i in range(0, 40, 4):
        nibble = uid_bin[i:i+4]
        data_with_parity += nibble + _even_parity(nibble)
    col_parity = ''
    for col in range(4):
        col_bits = data_with_parity[col::5]
        col_parity += _even_parity(col_bits)
    full_bin = start_bits + data_with_parity + col_parity + '0'
    full_hex = '{:016X}'.format(int(full_bin, 2))
    return full_hex[:8], full_hex[8:]

def dec_to_hex_uid(dec_str):
    if not re.match(r'^\d{10}$', dec_str):
        return None
    return '{:010X}'.format(int(dec_str))


class Em4102DecPlugin(object):

    def __init__(self, host=None):
        self.host = host

    def _pm3(self, cmd, timeout=TIMEOUT_WRITE):
        return self.host.pm3_command(cmd, timeout=timeout)

    def do_init(self):
        self.host.set_var('error_msg', '')
        self.host.set_var('dec_id', '')
        self.host.set_var('hex_uid', '')
        self.host.set_var('clone_count', '0')
        return {'status': 'ok'}

    def do_capture_dec(self):
        self.host.set_var('error_msg', '')
        val = self.host.get_input()

        if not val or not val.strip():
            self.host.set_var('error_msg', 'Enter 10 digits.')
            return {'status': 'error'}

        dec = val.strip()
        uid = dec_to_hex_uid(dec)
        if uid is None or encode_uid(uid) is None:
            self.host.set_var('error_msg', 'Conversion failed.')
            return {'status': 'error'}

        self.host.set_var('dec_id', dec)
        self.host.set_var('hex_uid', uid)
        return {'status': 'ok'}

    def do_clone(self):
        self.host.set_var('error_msg', '')
        uid = self.host.get_var('hex_uid', '')

        if not re.match(r'^[0-9A-F]{10}$', uid):
            self.host.set_var('error_msg', 'No valid UID.')
            return {'status': 'error'}

        ok, _ = self._pm3('lf em 410x clone --id {}'.format(uid), TIMEOUT_CLONE)
        if not ok:
            self.host.set_var('error_msg', 'Clone failed.\nCheck T5577 position.')
            return {'status': 'error'}

        count = int(self.host.get_var('clone_count', '0')) + 1
        self.host.set_var('clone_count', str(count))
        return {'status': 'done'}
