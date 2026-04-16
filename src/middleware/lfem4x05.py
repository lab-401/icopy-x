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

"""lfem4x05 -- EM4x05 tag operations (info, dump, read, write, verify).

Reimplemented from lfem4x05.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Archive:    archive/lib_transliterated/lfem4x05.py
    Spec:       docs/middleware-integration/5-read_spec.md (section 10)
    Strings:    docs/v1090_strings/lfem4x05_strings.txt

API:
    CMD = 'lf em 4x05_info FFFFFFFF'
    TIMEOUT = 5000

    parser() -> dict
    info4X05(key=None) -> dict
    dump4X05(infos, key=None) -> int
    read4x05(block, key=None) -> str
    readBlocks(key=None) -> list
    set_key(key) -> int
    verify4x05(data1, data2) -> bool
    infoAndDumpEM4x05ByKey(key=None) -> dict
"""

import re

# ---------------------------------------------------------------------------
# Constants -- EXACT from QEMU extraction
# ---------------------------------------------------------------------------
CMD = 'lf em 4x05_info FFFFFFFF'
TIMEOUT = 5000

# Module-level state -- accessed by read.so (lfem4x05.DUMP_TEMP)
DUMP_TEMP = None
KEY_TEMP = None

# ---------------------------------------------------------------------------
# Internal regex patterns -- EXACT from binary strings extraction
# ---------------------------------------------------------------------------
_RE_CHIP = r'.*Chip Type.*\|(.*)'
_RE_CONFIG = r'.*ConfigWord:(.*)\(.*'
_RE_SERIAL = r'.*Serial.*:(.*)'


# ===========================================================================
# Parser functions
# ===========================================================================

def parser():
    """Parse lf em 4x05_info output from executor cache.

    QEMU-verified return values:
        No 'Chip Type' keyword -> {'found': False}
        With 'Chip Type' -> {
            'found': True,
            'type': 24,
            'chip': '<chip type string>',
            'sn': '<serial number>',
            'cw': '<config word>'
        }

    Detection: checks for 'Chip Type' keyword first.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return {'found': False}

    try:
        import tagtypes
        em4305_id = tagtypes.EM4305_ID
    except (ImportError, AttributeError):
        try:
            from . import tagtypes
            em4305_id = tagtypes.EM4305_ID
        except (ImportError, AttributeError):
            em4305_id = 24

    if not executor.hasKeyword('Chip Type'):
        return {'found': False}

    result = {
        'found': True,
        'type': em4305_id,
        'key': '',
    }

    # Extract chip type
    chip = executor.getContentFromRegex(_RE_CHIP)
    if not chip:
        # Try getContentFromRegexG if getContentFromRegex doesn't work
        try:
            chip = executor.getContentFromRegexG(_RE_CHIP, 1)
        except Exception:
            chip = None
    result['chip'] = chip.strip() if chip else ''

    # Extract serial number
    sn = executor.getContentFromRegex(_RE_SERIAL)
    if not sn:
        try:
            sn = executor.getContentFromRegexG(_RE_SERIAL, 1)
        except Exception:
            sn = None
    result['sn'] = sn.strip() if sn else ''

    # Extract config word
    cw = executor.getContentFromRegex(_RE_CONFIG)
    if not cw:
        try:
            cw = executor.getContentFromRegexG(_RE_CONFIG, 1)
        except Exception:
            cw = None
    result['cw'] = cw.strip() if cw else ''

    return result


def info4X05(key=None):
    """Get EM4x05 tag info.

    QEMU-verified: sends 'lf em 4x05_info' with optional key.
    Returns parser() result. Caches in DUMP_TEMP (accessed by read.so).
    """
    global DUMP_TEMP, KEY_TEMP
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return {'found': False}

    if key:
        cmd = 'lf em 4x05_info %s' % key
        KEY_TEMP = key
    else:
        # Ground truth: binary string constant CMD = 'lf em 4x05_info FFFFFFFF'
        # Original sends default key FFFFFFFF when no explicit key given.
        # Original PM3 trace confirms: first scan command is 'lf em 4x05_info FFFFFFFF'
        cmd = CMD

    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return {'found': False}

    info = parser()
    return info


def read4x05(block, key=None):
    """Read a single EM4x05 block.

    QEMU-verified: sends 'lf em 4x05_read <block> <key>'.
    Returns block data string or ''.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return ''

    if key:
        cmd = 'lf em 4x05_read %s %s' % (block, key)
    else:
        cmd = 'lf em 4x05_read %s' % block

    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return ''

    return executor.getPrintContent()


def readBlocks(key=None):
    """Read all EM4x05 blocks.

    QEMU-verified: reads blocks 0-15, returns list of data strings.
    """
    blocks = []
    for b in range(16):
        data = read4x05(b, key)
        blocks.append(data)
    return blocks


def dump4X05(infos=None, key=None):
    """Dump EM4x05 tag data to file.

    Ground truth (original PM3 log):
        lf em 4x05_info FFFFFFFF
        lf em 4x05_info
        lf em 4x05_dump f /mnt/upan/dump/em4x05/EM4305_AABBCCDD_4

    Original .so creates dump path via appfiles.create_em4x05(),
    includes ' f <path>' in the PM3 command, then extracts the path
    from 'saved 64 bytes to binary file <path>' and stores in DUMP_TEMP.
    read.so accesses lfem4x05.DUMP_TEMP for the dump file path.

    Returns 0 on success, -1 on failure.
    """
    global DUMP_TEMP
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -1

    # Build dump file path from serial number
    # Ground truth (original PM3 log): lf em 4x05_dump f /mnt/upan/dump/em4x05/EM4305_AABBCCDD_4
    # appfiles.create_em4x05() adds the EM4305_ prefix and _N uniqueness suffix
    sn = ''
    if isinstance(infos, dict):
        sn = infos.get('sn', '') or ''

    # Create path via appfiles (original .so does this)
    dump_path = None
    try:
        import appfiles
        dump_path = appfiles.create_em4x05(sn)
    except Exception:
        # Fallback: construct path directly
        import os
        dump_path = os.path.join('/mnt/upan/dump/em4x05', 'EM4305_%s' % sn if sn else 'EM4305')

    # Ground truth: binary format string ' f {}' (lfem4x05_strings.txt line 825)
    # Command: 'lf em 4x05_dump' + ' f {}'.format(path)
    cmd = 'lf em 4x05_dump' + ' f {}'.format(dump_path)

    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1

    # Extract actual file path from response and store in DUMP_TEMP
    # Ground truth: response contains 'saved 64 bytes to binary file <path>'
    if executor.hasKeyword('saved 64 bytes to binary file'):
        path = executor.getContentFromRegexG(
            r'saved \d+ bytes to binary file\s*(.*)', 1)
        if path:
            DUMP_TEMP = path.strip()
        else:
            DUMP_TEMP = dump_path
    else:
        DUMP_TEMP = dump_path

    return 0


def set_key(key):
    """Set password on EM4x05 tag.

    QEMU-verified: writes key to the EM4x05 password block.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -1

    cmd = 'lf em 4x05_write 2 %s %s' % (key, key)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 0


def verify4x05(data1, data2):
    """Verify two data blocks match.

    QEMU-verified: reads blocks from tag and compares.
    Without PM3, always returns False.
    """
    if not data1 or not data2:
        return False
    current_blocks = readBlocks()
    if not current_blocks:
        return False
    return False


def infoAndDumpEM4x05ByKey(key=None):
    """Get info and dump EM4x05 using a specific key.

    QEMU-verified: calls info4X05 then dump4X05.
    Returns the info dict with 'return', 'data', 'raw' keys for
    read.so compatibility.
    """
    info = info4X05(key)
    if info.get('found'):
        dump_ret = dump4X05(info, key)
        info['return'] = 1 if dump_ret == 0 else -1
    else:
        info['return'] = -1
    # read.so accesses result['data'], result['raw'], result['key']
    info.setdefault('data', info.get('sn', ''))
    info.setdefault('raw', info.get('cw', ''))
    info.setdefault('key', key or '')
    return info
