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

"""hficlass -- iCLASS tag identification and key checking.

Reimplemented from hficlass.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Strings:    docs/v1090_strings/hficlass_strings.txt
    Spec:       docs/middleware-integration/3-scan_spec.md
    Analysis:   docs/HOW_TO_BUILD_FLOWS.md (section 12.5)

API (scan-related subset):
    parser() -> dict
    checkKey(key) -> bool
"""

import re

# ---------------------------------------------------------------------------
# Constants — from binary string extraction
# ---------------------------------------------------------------------------
# Standard iCLASS Legacy keys (from hficlass_strings.txt)
_KEY_LEGACY_1 = 'AFA785A7DAB33378'
_KEY_LEGACY_2 = '2020666666668888'
_KEY_LEGACY_3 = '6666202066668888'

# PM3 commands
_CMD_RDBL = 'hf iclass rdbl b {:02d} k {}'
_CMD_INFO = 'hf iclass info'
_CMD_CHK = 'hf iclass chk f '

# Regex patterns
_RE_CSN = r'CSN:*\s([A-Fa-f0-9 ]+)'
_RE_BLK7 = r'Blk7#:([0-9a-fA-F]+)'


def checkKey(typ_or_key, key=None, block=1, elite=False):
    """Check if a key can read a block from the iCLASS tag.

    Binary citation: __pyx_pw_8hficlass_7checkKey
    Original .so signature: checkKey(typ, key) where typ is a string type name.
    iclasswrite.so calls: hficlass.checkKey(typ, key)

    Sends 'hf iclass rdbl b 01 k <key>' and checks for 'Block' (capital B)
    in response. Error messages contain lowercase 'block' and must NOT match.

    Returns True if key is valid, False otherwise.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return False

    # Support both calling conventions:
    #   checkKey(typ, key)          -- original .so convention
    #   checkKey(key, block=1, ...) -- our internal convention
    if key is None:
        # Called as checkKey(key_only) -- legacy internal call
        actual_key = typ_or_key
    else:
        # Called as checkKey(typ, key) -- original .so convention
        actual_key = key

    cmd = _CMD_RDBL.format(block, actual_key)
    if elite:
        cmd += ' e'
    ret = executor.startPM3Task(cmd, 5000)
    if ret == -1:
        return False

    # Ground truth (decompiled hficlass.so, string at 0x00022a2c):
    # Original .so uses getContentFromRegexG with pattern
    #   'block \d+ : ([a-fA-F0-9 ]+)'
    # This matches success output like "Block 01 : 12 FF FF FF 7F 1F FF 3C"
    # but NOT error messages like "[-] Error reading block" (no " \d+ : hex").
    content = executor.getContentFromRegex(r'[Bb]lock \d+ : ([a-fA-F0-9 ]+)')
    return bool(content and content.strip())


def readTagBlock(typ_or_key, block_or_key=None, key=None, elite=False):
    """Read a single iCLASS block and return the data.

    Binary citation: __pyx_pw_8hficlass_5readTagBlock
    Original .so signature: readTagBlock(typ, block, key)
    iclasswrite.so calls: hficlass.readTagBlock(typ, block, key)

    Sends 'hf iclass rdbl b <block> k <key>' and returns block data string.

    Returns block data string, or '' on failure.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return ''

    # Support both calling conventions:
    #   readTagBlock(typ, block, key)          -- original .so convention
    #   readTagBlock(key, block=1, elite=...) -- our internal convention
    if key is not None:
        # Called as readTagBlock(typ, block, key) -- original .so convention
        actual_block = block_or_key
        actual_key = key
    elif block_or_key is not None:
        # Called as readTagBlock(key, block) -- ambiguous, treat as (typ, block)
        actual_block = block_or_key
        actual_key = typ_or_key
    else:
        # Called as readTagBlock(key) -- single arg
        actual_block = 1
        actual_key = typ_or_key

    cmd = _CMD_RDBL.format(actual_block, actual_key)
    if elite:
        cmd += ' e'
    ret = executor.startPM3Task(cmd, 5000)
    if ret == -1:
        return ''

    content = executor.getPrintContent()
    if not content or not content.strip():
        return ''

    # Ground truth: PM3 iCLASS rdbl output contains 'block' keyword.
    # Note: [+] prefix is stripped by pm3_compat._pre_normalize on iceman,
    # so only check for 'block' presence.
    if 'block' in content.lower():
        return content
    return ''


def chkKeys_1(infos):
    """Check legacy keys (without elite flag).

    Binary citation: __pyx_pw_8hficlass_9chkKeys_1
    Tries all 3 standard keys without 'e' flag.

    Returns {'key': key, 'type': 'Legacy'} on success, or None.
    """
    legacy_keys = [_KEY_LEGACY_1, _KEY_LEGACY_2, _KEY_LEGACY_3]
    for key in legacy_keys:
        if checkKey(key, block=1, elite=False):
            return {'key': key, 'type': 'Legacy'}
    return None


def chkKeys_2(infos):
    """Check elite keys (with elite flag).

    Binary citation: __pyx_pw_8hficlass_11chkKeys_2
    Tries all 3 standard keys with 'e' flag.

    Returns {'key': key, 'type': 'Elite', 'e': 'e'} on success, or None.
    The 'e' field is used by iclassread.so::readFromKey to add the elite
    flag to the dump command.
    """
    legacy_keys = [_KEY_LEGACY_1, _KEY_LEGACY_2, _KEY_LEGACY_3]
    for key in legacy_keys:
        if checkKey(key, block=1, elite=True):
            return {'key': key, 'type': 'Elite', 'e': 'e'}
    return None


def chkKeys(infos):
    """Check all iCLASS keys: legacy first, then elite, then file-based chk.

    Binary citation: __pyx_pw_8hficlass_13chkKeys
    Called by iclassread.so to find a working key.
    Tries chkKeys_1 (legacy, no 'e' flag) first.
    If none found, tries chkKeys_2 (elite, with 'e' flag).
    If still none found, falls back to 'hf iclass chk' file-based check.

    Returns dict with 'key' and 'type' on success, or None on failure.
    """
    import re as _re
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return None

    result = chkKeys_1(infos)
    if result:
        return result
    result = chkKeys_2(infos)
    if result:
        return result

    # Fallback: file-based key check via 'hf iclass chk'
    # Ground truth: archive/lib_transliterated/hficlass.py line 254
    # Original .so falls back to 'hf iclass chk f <keyfile>' when rdbl fails
    cmd = 'hf iclass chk'
    ret = executor.startPM3Task(cmd, 30000)
    if ret == -1:
        return None

    content = executor.getPrintContent()
    if content and 'Found valid key' in content:
        m = _re.search(r'Found valid key\s+([0-9a-fA-F ]+)', content)
        if m:
            found_key = m.group(1).strip().replace(' ', '')
            return {'key': found_key, 'type': 'Elite', 'e': 'e'}

    return None


def chk_type(infos):
    """Determine iCLASS tag subtype based on key check results.

    Binary citation: __pyx_pw_8hficlass_15chk_type
    Returns tag type ID (ICLASS_LEGACY=17, ICLASS_ELITE=18, ICLASS_SE=47).
    """
    try:
        import tagtypes
    except ImportError:
        try:
            from . import tagtypes
        except ImportError:
            return 18  # default to ICLASS_ELITE

    result = chkKeys(infos)
    if result and result.get('type') == 'Legacy':
        return tagtypes.ICLASS_LEGACY  # 17
    return tagtypes.ICLASS_ELITE  # 18


def parser():
    """Identify iCLASS tag type by trying standard keys.

    Binary citation: __pyx_pw_8hficlass_17parser
    Tries Legacy keys in order. If any works → ICLASS_LEGACY.
    If none work → ICLASS_ELITE.

    Returns:
        dict: {'found': True, 'type': 17|18|47, 'uid': ..., ...}
    """
    try:
        import executor
        import tagtypes
    except ImportError:
        try:
            from . import executor
            from . import tagtypes
        except ImportError:
            return {'found': False}

    # Extract CSN from the hf search output (already in cache)
    csn_raw = executor.getContentFromRegex(_RE_CSN)
    csn = csn_raw.strip().replace(' ', '') if csn_raw else ''

    # Determine type and find key in a single pass via chkKeys().
    # Ground truth: original .so parser calls chkKeys() once, which tries
    # legacy keys (chkKeys_1), then elite keys (chkKeys_2), then file-based
    # chk. This avoids duplicate PM3 calls.
    key_result = chkKeys({})

    if key_result and key_result.get('type') == 'Legacy':
        tag_type = tagtypes.ICLASS_LEGACY  # 17
    else:
        tag_type = tagtypes.ICLASS_ELITE   # 18

    # Run hf iclass info to get full tag details
    executor.startPM3Task(_CMD_INFO, 5000)

    # Re-extract CSN from info output if available
    csn_info = executor.getContentFromRegex(_RE_CSN)
    if csn_info and csn_info.strip():
        csn = csn_info.strip().replace(' ', '')

    result = {
        'found': True,
        'type': tag_type,
        'csn': csn,
    }

    if key_result and key_result.get('key'):
        result['key'] = key_result['key']

    return result
