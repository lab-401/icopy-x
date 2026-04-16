##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
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

"""Byte/string conversion utilities — replaces bytestr.so.

Exports:
    bytesToHexString(data)    — bytes → comma-separated uppercase hex string
    to_bytes(bytes_or_str)    — str/bytes → bytes (UTF-8 encode)
    to_str(bytes_or_str)      — bytes/str → str (UTF-8 decode)

Source: archive/lib_transliterated/bytestr.py
Verified: QEMU extraction of original bytestr.so behaviour

String table (from Ghidra):
    bytesToHexString, to_bytes, to_str, bytes_or_str, encode, decode,
    value, utf-8, %02X,

Original Cython source path:
    C:\\Users\\ADMINI~1\\AppData\\Local\\Temp\\1\\tmpz23h9_uv\\bytestr.py

No external module dependencies.
"""


def bytesToHexString(data):
    """Convert raw bytes to a comma-separated uppercase hex string.

    Each byte is formatted as two uppercase hex digits.  A trailing comma
    is always appended (matching the original .so exactly).

    Args:
        data: bytes object.

    Returns:
        Hex string with trailing comma, or '' for empty input.

    Examples (QEMU-verified against original .so):
        bytesToHexString(b'')                         → ''
        bytesToHexString(bytes([0x41]))                → '41,'
        bytesToHexString(bytes([0x41, 0x42]))          → '41,42,'
        bytesToHexString(bytes([0, 1, 2, 0xAB, 0xFF]))→ '00,01,02,AB,FF,'
        bytesToHexString(bytes([0xDE,0xAD,0xBE,0xEF]))→ 'DE,AD,BE,EF,'
    """
    if not data:
        return ''
    return ','.join('%02X' % b for b in data) + ','


def to_bytes(s):
    """Convert a string to bytes using UTF-8 encoding.

    If the input is already bytes, returns it unchanged.
    This is a simple str.encode() wrapper, NOT a hex parser.

    Args:
        s: string or bytes.

    Returns:
        bytes object.

    Examples (QEMU-verified):
        to_bytes('hello')     → b'hello'
        to_bytes('DEADBEEF')  → b'DEADBEEF'  (not hex-decoded!)
        to_bytes(b'hello')    → b'hello'     (passthrough)
        to_bytes('')          → b''
    """
    if isinstance(s, bytes):
        return s
    return s.encode('utf-8')


def to_str(b):
    """Convert bytes to a string using UTF-8 decoding.

    If the input is already a string, returns it unchanged.

    Args:
        b: bytes or string.

    Returns:
        str.

    Raises:
        UnicodeDecodeError: if bytes are not valid UTF-8.

    Examples (QEMU-verified):
        to_str(b'hello')    → 'hello'
        to_str(b'test123')  → 'test123'
        to_str('hello')     → 'hello'  (passthrough)
    """
    if isinstance(b, str):
        return b
    return b.decode('utf-8')
