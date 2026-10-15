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

"""hficlass -- iCLASS tag identification and key checking.

Reimplemented from hficlass.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Phase 3 (compat-flip, P3.7): middleware is now iceman-native. Every regex
targets exactly what iceman PM3 `PrintAndLogEx` emits. Legacy-form handling
(if any) belongs in `pm3_compat.py` adapters, not here.

Ground truth:
    Strings:    docs/v1090_strings/hficlass_strings.txt
    Spec:       docs/middleware-integration/3-scan_spec.md
    Analysis:   docs/HOW_TO_BUILD_FLOWS.md (section 12.5)
    Matrix:     tools/ground_truth/divergence_matrix.md#hf-iclass-info
                tools/ground_truth/divergence_matrix.md#hf-iclass-rdbl
                tools/ground_truth/divergence_matrix.md#hf-iclass-chk

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
_CMD_RDBL = 'hf iclass rdbl --blk {:02d} -k {}'
_CMD_INFO = 'hf iclass info'
_CMD_CHK = 'hf iclass chk -f '

# Regex patterns — iceman-native (compat-flip P3.7)
#
# _RE_CSN — matches iceman's `hf iclass info` CSN line
#   Source: /tmp/rrg-pm3/client/src/cmdhficlass.c:8032
#     PrintAndLogEx(SUCCESS, "    CSN: " _GREEN_("%s") " uid", ...)
#   Iceman emits `    CSN: 75 D0 E0 13 FE FF 12 E0 uid` (4-space indent,
#   `uid` suffix after hex). Matrix v2 correction (line 433) confirms the
#   pattern `CSN:*\s([A-Fa-f0-9 ]+)` matches iceman verbatim: `CSN:` is
#   followed by a literal space, then the hex run. The `:*` allows zero
#   or more colons to absorb Fingerprint-banner variants where iceman
#   uses dotted form `CSN..........` (cmdhficlass.c:8088/8098). The hex
#   class captures until a non-hex char (space before `uid` still
#   matches the class; trailing text is discarded at regex boundary).
_RE_CSN = r'CSN:*\s([A-Fa-f0-9 ]+)'

# _RE_BLK7 — Blk7#: hex is a legacy iCopy-X-specific line fed by the
# original .so's own synthesised output (not a PM3 string). Retained for
# API compatibility with callers that still consume the `blk7` dict field.
# No iceman source emits this shape; consumer paths that depend on it are
# logged in the P3.7 gap log.
_RE_BLK7 = r'Blk7#:([0-9a-fA-F]+)'

# _RE_BLOCK_READ — matches iceman `hf iclass rdbl` output.
#   Source: /tmp/rrg-pm3/client/src/cmdhficlass.c:3501
#     PrintAndLogEx(SUCCESS, " block %3d/0x%02X : " _GREEN_("%s"), ...)
#   Iceman emits ` block   6/0x06 : 12 FF FF FF 7F 1F FF 3C` (leading
#   space, 3-space-padded decimal, slash, 0x + 2-hex-digit, space, colon,
#   space, hex run).
#   Matrix divergence (line 508) flagged the prior regex
#   `r'[Bb]lock \d+ : ...'` as matching NEITHER iceman nor legacy raw
#   forms — legacy is ` block %02X : ` (uppercase hex block ≥10
#   unmatchable by `\d+`); iceman inserts `/0x%02X` between digit and
#   colon. The iceman-native regex below captures the decimal block
#   number and the hex payload; Phase 4 will rely on `_normalize_iclass_rdbl`
#   to rewrite legacy hex block numbers to decimal for cross-fw parity.
_RE_BLOCK_READ = r'block\s+\d+\s*/0x[0-9A-Fa-f]+\s*:\s+([A-Fa-f0-9 ]+)'


def checkKey(typ_or_key, key=None, block=1, elite=False):
    """Check if a key can read a block from the iCLASS tag.

    Binary citation: __pyx_pw_8hficlass_7checkKey
    Original .so signature: checkKey(typ, key) where typ is a string type name.
    iclasswrite.so calls: hficlass.checkKey(typ, key)

    Sends 'hf iclass rdbl --blk 01 -k <key>' and checks for an iceman-shaped
    block-read success line (` block   1/0x01 : 12 FF ...`). Error messages
    lack the `/0x%02X` infix and must NOT match.

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
        cmd += ' --elite'
    ret = executor.startPM3Task(cmd, 5000)
    if ret == -1:
        return False

    # Ground truth: iceman emits ` block %3d/0x%02X : %s` at
    # /tmp/rrg-pm3/client/src/cmdhficlass.c:3501. The regex targets the
    # iceman-native shape directly. Error paths (e.g. auth failure,
    # tag-not-present) do NOT emit the `block .../0x.. : hex` pattern
    # so the regex naturally rejects them.
    content = executor.getContentFromRegex(_RE_BLOCK_READ)
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
        cmd += ' --elite'
    ret = executor.startPM3Task(cmd, 5000)
    if ret == -1:
        return ''

    content = executor.getPrintContent()
    if not content or not content.strip():
        return ''

    # Ground truth: iceman block-read line ` block %3d/0x%02X : <hex>` is a
    # reliable positive sentinel; error outputs do NOT contain the
    # `/0x..` infix. Matching on the regex (not on a naked `block`
    # substring) reduces false-positives from help text and other noise.
    # Source: /tmp/rrg-pm3/client/src/cmdhficlass.c:3501
    if re.search(_RE_BLOCK_READ, content):
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
    cmd = 'hf iclass chk --vb6kdf'
    ret = executor.startPM3Task(cmd, 30000)
    if ret == -1:
        return None

    # Iceman `CmdHFiClassCheckKeys` emits `Found valid key <hex>` on success.
    # Source: /tmp/rrg-pm3/client/src/cmdhficlass.c:5925 and :7016
    #   PrintAndLogEx(NORMAL, "Found valid key " _GREEN_("%s") ...)
    #   PrintAndLogEx(SUCCESS, "Found valid key " _GREEN_("%s"), ...)
    # sprint_hex_inrow emits uppercase hex pairs separated by single spaces;
    # the regex below accepts either case and collapses spaces after match.
    # Matrix citation: divergence_matrix.md "hf iclass chk" (line 445).
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
