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

"""T5577 Multiwriter plugin for iCopy-XS

Port of lf_t55xx_multiwriter.lua by jareckib - Jarek Barwinski

Stores 1, 2 or 3 EM4102 UIDs on a single T5577 tag.
Supports:
  - Manual HEX input (10 hex chars)
  - Manual DEC input (10 decimal digits = engraved ID)
  - Read from original fob via PM3

Block0 values per UID count:
  1 UID  -> 00148040
  2 UIDs -> 00148080
  3 UIDs -> 001480C0

Compatible readers: ACM08Y, ACM26C, Sycreader R60D, Elatech Multitech TWN4
"""

import re
import os

TIMEOUT_READ  = 10000
TIMEOUT_WRITE = 8000
TIMEOUT_DET   = 6000

BLOCK0 = {1: '00148040', 2: '00148080', 3: '001480C0'}


# ---------------------------------------------------------------------------
# EM4102 encoding (Lua port)
# ---------------------------------------------------------------------------

def _hex_to_bin40(hex_value):
    """Convert a 10-character hex string to a 40-bit binary string."""
    if not re.match(r'^[0-9A-Fa-f]{10}$', hex_value):
        return None
    dec = int(hex_value, 16)
    return '{:040b}'.format(dec)

def _even_parity(bits):
    return '0' if bits.count('1') % 2 == 0 else '1'

def encode_uid(uid_hex):
    """Encode EM4102 UID into T5577 format (two 8-hex blocks).

    Returns (block_a, block_b) or None if the UID is invalid.
    """
    uid_bin = _hex_to_bin40(uid_hex.upper())
    if uid_bin is None:
        return None

    # 9 start bits (1 + 8x1)
    start_bits = '1' + '1' * 8

    # 40 data bits + parity bit every 4 bits
    data_with_parity = ''
    for i in range(0, 40, 4):
        nibble = uid_bin[i:i+4]
        data_with_parity += nibble + _even_parity(nibble)

    # 4 column parity bits
    col_parity = ''
    for col in range(4):
        col_bits = data_with_parity[col::5]
        col_parity += _even_parity(col_bits)

    # Stop bit
    full_bin = start_bits + data_with_parity + col_parity + '0'

    # Convert to hex (64 bits = 16 hex characters = 2 blocks of 8)
    full_hex = '{:016X}'.format(int(full_bin, 2))
    return full_hex[:8], full_hex[8:]

def dec_to_hex_uid(dec_str):
    """Convert a 10-digit decimal (engraved ID) to a 10-character hex string."""
    if not re.match(r'^\d{10}$', dec_str):
        return None
    return '{:010X}'.format(int(dec_str))


# ---------------------------------------------------------------------------
# PM3 output parsers
# ---------------------------------------------------------------------------

def _parse_em410x_id(output):
    """Extract EM410x ID from 'lf em 410x read' output."""
    if not output:
        return None
    for line in output.splitlines():
        m = re.search(r'EM\s*410x\s*ID\s*([0-9A-Fa-f]{10})', line, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None

def _parse_block(output, block_num):
    """Extract block N value from 'lf t55xx read' output."""
    if not output:
        return None
    pattern = r'\[\s*\+\s*\]\s*{:02X}\s*\|\s*([0-9A-Fa-f]{{8}})'.format(block_num)
    m = re.search(pattern, output, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Alternative format
    m2 = re.search(r'\b{:02d}\s*\|\s*([0-9A-Fa-f]{{8}})'.format(block_num), output)
    if m2:
        return m2.group(1).upper()
    return None
# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class T55xxMultiwriterPlugin(object):

    def __init__(self, host=None):
        self.host = host

    # ── helpers ──────────────────────────────────────────────────────────

    def _pm3(self, cmd, timeout=TIMEOUT_WRITE):
        return self.host.pm3_command(cmd, timeout=timeout)

    def _get_uid_list(self):
        """Load the UID list from state variables."""
        uids = []
        for i in range(1, 4):
            uid = self.host.get_var('uid{}'.format(i), '')
            if uid:
                uids.append(uid)
        return uids

    def _set_uid(self, index, uid):
        self.host.set_var('uid{}'.format(index), uid)

    def _clear_uids(self):
        for i in range(1, 4):
            self.host.set_var('uid{}'.format(i), '')
        self.host.set_var('uid_count', '0')

    def _update_uid_count(self):
        count = len(self._get_uid_list())
        self.host.set_var('uid_count', str(count))
        self.host.set_var('uid_count_label',
            '{} UID{} stored'.format(count, 's' if count != 1 else ''))
        # Summary
        lines = []
        for i, uid in enumerate(self._get_uid_list(), 1):
            lines.append('UID{}: {}'.format(i, uid))
        self.host.set_var('uid_summary', '\n'.join(lines) if lines else 'No UIDs yet')
        return count

    # ── Initialization ─────────────────────────────────────────────────────

    def do_init(self):
        self._clear_uids()
        self.host.set_var('error_msg', '')
        self.host.set_var('uid_summary', 'No UIDs yet')
        self.host.set_var('uid_count_label', '0 UIDs stored')
        self.host.set_var('input_mode', '')
        return {'status': 'ok'}

    # ── UID Capture ────────────────────────────────────────────────────

    def do_capture_hex(self):
        """Get UID from the hex input widget (10 hex characters)."""
        self.host.set_var('error_msg', '')
        val = self.host.get_input()
        if not val or not val.strip():
            self.host.set_var('error_msg', 'Enter 10 hex chars.')
            return {'status': 'error'}

        uid = val.strip().upper()
        if not re.match(r'^[0-9A-F]{10}$', uid):
            self.host.set_var('error_msg',
                'Invalid: {}\nMust be 10 hex chars (0-9 A-F).'.format(uid))
            return {'status': 'error'}

        return self._store_uid(uid)

    def do_capture_dec(self):
        """Get UID from the dec input (10 decimal digits = engraved ID)."""
        self.host.set_var('error_msg', '')
        val = self.host.get_input()
        if not val or not val.strip():
            self.host.set_var('error_msg', 'Enter 10 decimal digits.')
            return {'status': 'error'}

        dec = val.strip()
        if not re.match(r'^\d{10}$', dec):
            self.host.set_var('error_msg',
                'Invalid: {}\nMust be 10 decimal digits.'.format(dec))
            return {'status': 'error'}

        uid = dec_to_hex_uid(dec)
        self.host.set_var('converted_uid', uid)
        return self._store_uid(uid)

    def do_read_fob(self):
        """Read UID from the original fob via PM3."""
        self.host.set_var('error_msg', '')
        ok, out = self._pm3('lf em 410x read', TIMEOUT_READ)
        uid = _parse_em410x_id(out) if out else None

        if not uid:
            self.host.set_var('error_msg',
                'No EM410x tag detected.\nAdjust position and retry.')
            return {'status': 'error'}

        return self._store_uid(uid)

    def _store_uid(self, uid):
        """Save the UID into the next available slot."""
        uids = self._get_uid_list()
        if len(uids) >= 3:
            self.host.set_var('error_msg', 'Maximum 3 UIDs reached.')
            return {'status': 'full'}

        # Encode and verify
        result = encode_uid(uid)
        if result is None:
            self.host.set_var('error_msg',
                'Encoding failed for:\n{}'.format(uid))
            return {'status': 'error'}

        # Save
        idx = len(uids) + 1
        self._set_uid(idx, uid)
        count = self._update_uid_count()
        self.host.set_var('last_uid', uid)

        if count < 3:
            return {'status': 'stored_more'}   # More UIDs can be added
        else:
            return {'status': 'stored_full'}   # Maximum of 3 reached

    # ── Write to T5577 ────────────────────────────────────────────────────

    def do_write(self):
        """Encode all UIDs and write them to the T5577 tag."""
        self.host.set_var('error_msg', '')
        uids = self._get_uid_list()

        if not uids:
            self.host.set_var('error_msg', 'No UIDs to write.')
            return {'status': 'error'}

        # Encode all UIDs
        all_blocks = []
        for uid in uids:
            result = encode_uid(uid)
            if result is None:
                self.host.set_var('error_msg',
                    'Encoding failed for:\n{}'.format(uid))
                return {'status': 'error'}
            all_blocks.append(result[0])
            all_blocks.append(result[1])

        block0 = BLOCK0[len(uids)]

        # Write block 0
        ok, _ = self._pm3('lf t55xx write -b 0 -d {}'.format(block0))
        if not ok:
            self.host.set_var('error_msg',
                'Write failed on block 0.\nCheck tag position.')
            return {'status': 'error'}

        # Write data blocks
        for i, blk in enumerate(all_blocks, 1):
            ok, _ = self._pm3('lf t55xx write -b {} -d {}'.format(i, blk))
            if not ok:
                self.host.set_var('error_msg',
                    'Write failed on block {}.\nCheck tag position.'.format(i))
                return {'status': 'error'}

        # Save to state for verification
        self.host.set_var('written_block0', block0)
        for i, blk in enumerate(all_blocks, 1):
            self.host.set_var('written_block{}'.format(i), blk)
        self.host.set_var('written_count', str(len(all_blocks)))

        return {'status': 'done'}

    def do_verify(self):
        """Post-write verification — reads blocks and compares them."""
        self.host.set_var('error_msg', '')

        block0 = self.host.get_var('written_block0', '')
        n = int(self.host.get_var('written_count', '0'))

        if not block0 or n == 0:
            self.host.set_var('error_msg', 'No write data to verify.')
            return {'status': 'error'}

        # Detect
        self._pm3('lf t55xx detect', TIMEOUT_DET)

        # Read blocks
        all_output = ''
        for i in range(0, n + 1):
            ok, out = self._pm3('lf t55xx read -b {}'.format(i), TIMEOUT_DET)
            if out:
                all_output += out + '\n'

        # Check block 0
        found0 = _parse_block(all_output, 0)
        if not found0 or found0.upper() != block0.upper():
            self.host.set_var('error_msg',
                'Block 0 mismatch.\nExpected: {}\nFound: {}'.format(
                    block0, found0 or 'N/A'))
            return {'status': 'failed'}

        # Check data blocks
        for i in range(1, n + 1):
            expected = self.host.get_var('written_block{}'.format(i), '')
            found = _parse_block(all_output, i)
            if not found or found.upper() != expected.upper():
                self.host.set_var('error_msg',
                    'Block {} mismatch.\nExpected: {}\nFound: {}'.format(
                        i, expected, found or 'N/A'))
                return {'status': 'failed'}

        return {'status': 'ok'}

    def do_remove_last(self):
        """Remove the last added UID."""
        uids = self._get_uid_list()
        if not uids:
            self.host.set_var('error_msg', 'No UIDs to remove.')
            return {'status': 'empty'}
        # Clear the last one
        self.host.set_var('uid{}'.format(len(uids)), '')
        self._update_uid_count()
        return {'status': 'ok'}
