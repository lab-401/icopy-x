# MIFARE Classic Magic UID repair helpers. No firmware modifications.
# Targets only user-owned writable-UID Magic cards.
from __future__ import absolute_import

import os
import re

KEY_DEFAULT = 'FFFFFFFFFFFF'
FAIL_MARKERS = re.compile(
    r'(?i)(?:unknown command|not recognized|invalid (?:argument|option|command)|'
    r'auth\s+error|auth(?:entication)?\s+(?:failed|error)|'
    r'(?:write|read)\s*\(\s*fail\s*\)|'
    r'can.t (?:select card|set uid|read block)|'
    r'(?:write|read) failed|iso14443a card select failed|'
    r'wup(?:c1|gdm1)\s+error|'
    r'\berror\s*[:=]\s*-?\d+|'
    r'command execution time out|\b(?:timed?\s*out|timeout)\b|'
    r'\[\s*[-!]\s*\])'
)

MODES = (
    ('g2_1k4', 'Gen2 1K UID4', 'gen2', '1K', 4),
    ('g2_4k4', 'Gen2 4K UID4', 'gen2', '4K', 4),
    ('g2_1k7', 'Gen2 1K UID7', 'gen2', '1K', 7),
    ('g2_4k7', 'Gen2 4K UID7', 'gen2', '4K', 7),
    ('g1_1k4', 'Gen1a 1K UID4', 'gen1a', '1K', 4),
    ('g1_4k4', 'Gen1a 4K UID4', 'gen1a', '4K', 4),
)


# Auto Repair is a workflow, not a seventh write mode.  An inconclusive
# read must never be converted into a speculative block-0 write.
MENU_ITEMS = (('auto', 'Auto Repair'), ('keys_only', 'Key Finding')) + MODES

def parse_magic_identity(output):
    """Read-only classification; return (family, size, uidlen) or None.

    Only recognize explicit Magic family, memory size, and complete UID.
    Never infer memory capacity from damaged SAK/ATQA alone.
    """
    s = output or ''
    uid = extract_uid(s)
    if not uid:
        return None
    low = s.lower()
    if not re.search(r'magic\s+capabilities', low):
        return None
    if re.search(r'gen\s*1a\b', low):
        family = 'gen1a'
    elif re.search(r'gen\s*2\s*/\s*cuid', low):
        family = 'gen2'
    else:
        return None
    # Require explicit printed size.  This can be absent on damaged tags.
    sizes = set(re.findall(r'mifare\s+(?:classic\s+)?(1k|4k)\b', low))
    if len(sizes) != 1:
        return None
    size = sizes.pop().upper()
    length = len(uid) // 2
    if family == 'gen1a' and length != 4:
        return None
    for mode in MODES:
        if (mode[2], mode[3], mode[4]) == (family, size, length):
            return mode
    return None


def has_magic_evidence(output):
    return bool(re.search(r'(?i)magic\s+capabilities', output or ''))


def is_standard_only(output):
    """Evidence that a selectable card does not advertise Magic capabilities."""
    output = output or ''
    return bool(extract_uid(output) and re.search(r'(?i)mifare\s+classic', output)
                and not has_magic_evidence(output))


def new_uid(length):
    if length == 4:
        raw = bytearray(os.urandom(4))
        # No restrictions are mandated by the repair path, but avoid trivial reserved-looking identifiers.
        if not any(raw) or all(b == 255 for b in raw):
            raw[0] ^= 0x5A
        # ISO14443A reserves 0x88 as the cascade tag; not a valid UID0 for 4B.
        if raw[0] == 0x88:
            raw[0] = 0x42
    elif length == 7:
        # Proxmark3 magic_cards_notes.md uses manufacturer prefix 04 for 7-byte UID cards.
        raw = bytearray(b'\x04' + os.urandom(6))
    else:
        raise ValueError('Only 4 or 7 byte UIDs are supported')
    return bytes(raw).hex().upper()


def block0(mode, uid):
    """Build a standard (documented) Gen2 DirectWrite 16-byte manufacturer block.

    Adapted from RRG Proxmark3 doc/magic_cards_notes.md, DirectWrite recovery.
    Byte layout for 4-byte UID: UID[4], BCC, SAK, ATQA low/high, manufacturer[8].
    Byte layout for 7-byte UID: UID[7], SAK, ATQA low/high, manufacturer[6].
    """
    _, _, family, size, length = mode
    if family != 'gen2':
        raise ValueError('Gen1a uses csetuid, not direct block0')
    if not isinstance(uid, str) or not re.fullmatch('[0-9A-Fa-f]{%d}' % (length * 2), uid):
        raise ValueError('Invalid UID length or hex format')
    b = bytes.fromhex(uid)
    sak = 0x08 if size == '1K' else 0x18
    if length == 4:
        bcc = b[0] ^ b[1] ^ b[2] ^ b[3]
        atqa_lo = 0x04 if size == '1K' else 0x02
        result = b + bytes([bcc, sak, atqa_lo, 0x00]) + bytes.fromhex('6263646566676869')
    else:
        atqa_lo = 0x44 if size == '1K' else 0x42
        result = b + bytes([sak, atqa_lo, 0x00]) + bytes.fromhex('626364656667')
    if len(result) != 16:
        raise AssertionError('Invalid manufacturer block length')
    return result.hex().upper()


def repair_commands(mode, uid, key=KEY_DEFAULT, key_type="a"):
    _, _, family, size, length = mode
    if family == 'gen2':
        config = ('hf 14a config --atqa force --bcc ignore --cl2 skip --rats skip' if length == 4
                  else 'hf 14a config --atqa force --bcc ignore --cl2 force --cl3 skip --rats skip')
        if not re.fullmatch(r'[0-9A-Fa-f]{12}', key or '') or key_type not in ('a', 'b'):
            raise ValueError('Invalid sector-0 authentication credentials')
        write = 'hf mf wrbl --blk 0 -{} -k {} -d {} --force'.format(key_type, key.upper(), block0(mode, uid))
    else:
        config = None
        # Iceman Gen1a backdoor csetuid repairs the manufacturer block without overwriting sectors.
        atqa, sak = ('0004', '08') if size == '1K' else ('0044', '18')
        write = 'hf mf csetuid -u {} -a {} -s {}'.format(uid, atqa, sak)
    return config, write


def help_capabilities(config_help, wrbl_help, csetuid_help):
    """Conservative, non-RF capability gate: no version-number guesses.

    Each help response must contain the actual relevant flags; translated legacy
    commands are not treated as proof that direct-write rescue is possible.
    """
    c = (config_help or '').lower()
    w = (wrbl_help or '').lower()
    u = (csetuid_help or '').lower()
    c_ok = ('config' in c and '--atqa' in c and '--bcc' in c and '--cl2' in c and '--std' in c)
    w_ok = ('wrbl' in w and '--force' in w and '--blk' in w and '-d' in w)
    u_ok = ('csetuid' in u and '-u' in u and '-a' in u and '-s' in u)
    return {'gen2': bool(c_ok and w_ok), 'gen1a': bool(c_ok and u_ok), 'config': bool(c_ok)}


def extract_uid(output):
    """Parse the 4/7-byte ISO14443A UID from common PM3 print formats.

    Handles `UID: 11 22 ...`, `UID........... 11 22 ...`, and compact
    `UID: 11223344`.  Do not parse any unrelated hex printed elsewhere.
    """
    for line in (output or '').splitlines():
        match = re.search(
            r'(?i)\b(?:new\s+uid|uid)\s*[.:= ]+\s*'
            r'((?:[0-9a-f]{2}[\s:-]?){4,7})(?![0-9a-f])', line)
        if not match:
            continue
        raw = re.sub(r'[^0-9A-Fa-f]', '', match.group(1)).upper()
        if len(raw) in (8, 14):
            return raw
    return None

def command_failed(ok, output):
    if not ok:
        return True
    return bool(FAIL_MARKERS.search(output or ''))


# Each command is read-only. Ordinary MIFARE Classic keys are tried in A/B
# mode; no key search, dictionary attack or opportunistic card write occurs.
RECOVERY_KEYS = (
    'FFFFFFFFFFFF',
    'A0A1A2A3A4A5',
    'D3F7D3F7D3F7',
    '000000000000',
    'B0B1B2B3B4B5',
    '4D3A99C351DD',
)


def extract_block_bytes(output):
    """Extract a displayed 16-byte block, not merely a successful CLI exit.

    Avoid matching help texts/echoed commands; require a block output line.
    The PM3 clients display either spaced 16 bytes or one compact hex row.
    """
    for raw in (output or '').splitlines():
        line = re.sub(r'\x1b\[[0-9;]*m', '', raw).strip()
        if re.search(r'(?i)(?:usage|example|hf mf|--blk|hint:|writing|reading|help)', line):
            continue
        if not ('|' in line or re.search(r'(?i)\bblock\b|\bsector\b', line)):
            continue
        compact = re.search(r'(?i)(?<![a-f0-9])([a-f0-9]{32})(?![a-f0-9])', line)
        if compact:
            return compact.group(1).upper()
        # Table rows can contain a sector/block number at the beginning.
        cells = re.findall(r'(?i)(?<![a-f0-9])[a-f0-9]{2}(?![a-f0-9])', line)
        if len(cells) >= 16:
            return ''.join(cells[-16:]).upper()
    return None


def recovery_config(length):
    if length == 4:
        return 'hf 14a config --atqa force --bcc ignore --cl2 skip --rats skip'
    if length == 7:
        return 'hf 14a config --atqa force --bcc ignore --cl2 force --cl3 skip --rats skip'
    raise ValueError('Unsupported UID length')
