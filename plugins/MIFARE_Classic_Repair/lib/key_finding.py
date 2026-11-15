# Copyright (c) 2026 jareckib
"""Read-only MIFARE Classic 1K key-finding helpers.

No RFID writes; parses Iceman and older single-table fchk formats.
"""
from __future__ import absolute_import

import re

KEY_PATTERN = re.compile(r'^[0-9a-fA-F]{12}$')
_TABLE_ROW = re.compile(
    r'^\s*(?:\[\+\]\s*)?(\d{1,3})\s*\|\s*'
    r'(?:(\d{1,3})\s*\|\s*)?'
    r'([0-9a-fA-F]{12}|-{12})\s*\|\s*([01])\s*\|\s*'
    r'([0-9a-fA-F]{12}|-{12})\s*\|\s*([01])(?:\s*\||\s*$)'
)
_BRACKET_KEY = re.compile(r'(?i)(?:found\s+valid\s+key|found\s+key)\s*(?:\[|:|=)\s*([0-9a-f]{12})')
_ANSI = re.compile(r'\x1b\[[0-9;]*m')


def parse_fchk_keys(output):
    """Return {(sector, 'a'/'b'): key} for successful checkkeys results."""
    found = {}
    for raw in (output or '').splitlines():
        m = _TABLE_ROW.match(_ANSI.sub('', raw))
        if not m:
            continue
        sector, block, a, a_ok, b, b_ok = m.groups()
        sector = int(sector)
        if sector > 15 or (block is not None and int(block) != (sector * 4 + 3)):
            continue
        if a_ok == '1' and KEY_PATTERN.fullmatch(a):
            found[(sector, 'a')] = a.upper()
        if b_ok == '1' and KEY_PATTERN.fullmatch(b):
            found[(sector, 'b')] = b.upper()
    return found


def parse_attack_key(output):
    match = _BRACKET_KEY.search(_ANSI.sub('', output or ''))
    return match.group(1).upper() if match else None


def is_finished_fchk(ok, output):
    """Reject timeout/transport/CLI errors, not ordinary missed keys."""
    if not ok:
        return False
    s = (output or '').lower()
    if any(x in s for x in ('invalid option', 'unknown command', 'unexpected argument',
                             'timeout while waiting', 'command execution time out',
                             'cannot open', 'failed to load', 'can\'t select card',
                             'auth error', 'aborted via keyboard')):
        return False
    return ('time in checkkeys' in s or 'time in checkkeys (fast)' in s
            or 'found keys' in s or 'running strategy' in s and 'testing' in s)


def fmt_duration(seconds):
    if seconds is None:
        return '--:--'
    v = max(0, int(round(seconds)))
    h, v = divmod(v, 3600)
    m, sec = divmod(v, 60)
    return '%d:%02d:%02d' % (h, m, sec) if h else '%02d:%02d' % (m, sec)


def progress_metrics(done, total, elapsed):
    """Conservative estimate based on FINISHED key batches only."""
    rate = (float(done) / elapsed) if elapsed > 0 and done else 0.0
    eta = ((total - done) / rate) if rate > 0 and done <= total else None
    return rate, eta
