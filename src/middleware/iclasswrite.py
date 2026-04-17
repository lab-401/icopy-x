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

"""iclasswrite -- iClass writer (blocks, password, verify).

Reimplemented from iclasswrite.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Phase 3 (compat-flip, P3.7): middleware is iceman-native. All regex and
keywords target exactly what iceman PM3 emits (source citations in each
pattern). Legacy colon-separator, `successful` keyword, and hex-block
formats are handled only by pm3_compat.py adapters.

Ground truth:
    Archive:    archive/lib_transliterated/iclasswrite.py
    Spec:       docs/middleware-integration/6-write_spec.md (section on iclasswrite)
    Strings:    docs/v1090_strings/iclasswrite_strings.txt
    Matrix:     tools/ground_truth/divergence_matrix.md#hf-iclass-wrbl
                tools/ground_truth/divergence_matrix.md#hf-iclass-calcnewkey
                tools/ground_truth/divergence_matrix.md#hf-iclass-rdbl

API:
    readBlockHex(file, block, block_size=8) -> str
    getNeedWriteBlock(typ) -> list
    writeDataBlock(typ, block, data, key) -> int
    writeDataBlocks(typ, file_or_dict, key='2020666666668888') -> int
    writePassword(typ, new_key, oldkey='2020666666668888', l2e=False) -> int
    calcNewKey(typ, oldkey, newkey, l2e=False) -> str or -10
    write(infos, bundle) -> int
    verify(infos, bundle) -> int
"""

import re

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import hficlass
except ImportError:
    try:
        from . import hficlass
    except ImportError:
        hficlass = None

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        class tagtypes:
            ICLASS_LEGACY = 17
            ICLASS_ELITE = 18
            ICLASS_SE = 47

# ---------------------------------------------------------------------------
# Constants -- EXACT from QEMU extraction
# ---------------------------------------------------------------------------
ICLASS_E_WRITE_BLOCK = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
ICLASS_L_WRITE_BLOCK = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

TIMEOUT = 10000

# _RE_XOR_DIV_KEY — iceman `hf iclass calcnewkey` success result.
#   Source: /tmp/rrg-pm3/client/src/cmdhficlass.c:5419
#     PrintAndLogEx(SUCCESS, "Xor div key.... " _YELLOW_("%s") "\n", ...)
#   Iceman emits `Xor div key.... <hex>` with a **4-dot** separator
#   (verified by reading source L5419; the prior matrix note at line 1361
#   claimed a colon separator which was incorrect — corrected by this
#   refactor). `sprint_hex_inrow` emits uppercase hex bytes separated by
#   spaces. The regex anchors on `Xor div key` followed by one-or-more
#   dots and whitespace, then captures the hex run.
#
# Matrix citation: divergence_matrix.md "hf iclass calcnewkey" (line 1350).
# Systemic #7 (dotted-separator) applies — pm3_compat.py _RE_DOTTED_SEPARATOR
# converts iceman dots to colon globally, which breaks this regex when
# the adapter is active; Phase 4 must disable that normalizer for
# Xor div key. Entry logged in phase3_phase4_gap_log.md under P3.7.
_RE_XOR_DIV_KEY = r'Xor div key\.+\s+([0-9A-Fa-f ]+)'

# _KW_WRBL_SUCCESS — iceman `hf iclass wrbl` success sentinel.
#   Source: /tmp/rrg-pm3/client/src/cmdhficlass.c:3134
#     PrintAndLogEx(SUCCESS,
#       "Wrote block " _YELLOW_("%d") " / " _YELLOW_("0x%02X") " ( "
#       _GREEN_("ok") " )", ...)
#   Iceman emits `Wrote block 6 / 0x06 ( ok )` with literal ` ( ok )`.
#   Legacy emits `Wrote block 07 successful` (uppercase hex block,
#   trailing word `successful`). Matrix "hf iclass wrbl" (line 518)
#   marks this a FORMAT divergence; pm3_compat._normalize_iclass_wrbl
#   rewrites iceman's `( ok )` to `successful` for back-compat.
#
# After compat flip: middleware targets the iceman-native `( ok )`
# sentinel directly. The adapter normalizer becomes obsolete; Phase 4
# will remove the normalizer, the iceman-native keyword will still match.
_KW_WRBL_SUCCESS = r'\( ok \)'


# ===========================================================================
# Utility functions
# ===========================================================================

def readBlockHex(file, block, block_size=8):
    """Read a block from a binary dump file as hex string.

    Returns hex string of block data, uppercase.
    Tries file as-is, then with .bin suffix if not found.
    """
    import os
    paths_to_try = [file]
    if not file.endswith('.bin'):
        paths_to_try.append(file + '.bin')
    for fpath in paths_to_try:
        try:
            with open(fpath, 'rb') as f:
                f.seek(block * block_size)
                data = f.read(block_size)
                if len(data) < block_size:
                    return ''
                return data.hex().upper()
        except FileNotFoundError:
            continue
        except Exception:
            return ''
    return ''


def getNeedWriteBlock(typ):
    """Get list of blocks that need to be written for a given type."""
    if typ in ('legacy', 'Legacy', getattr(tagtypes, 'ICLASS_LEGACY', 17)):
        return list(ICLASS_L_WRITE_BLOCK)
    elif typ in ('elite', 'Elite', getattr(tagtypes, 'ICLASS_ELITE', 18)):
        return list(ICLASS_E_WRITE_BLOCK)
    else:
        return list(ICLASS_L_WRITE_BLOCK)


def append_suffix(file):
    """Ensure file has .bin suffix."""
    if not file.endswith('.bin'):
        return file + '.bin'
    return file


def make_se_data(blk7):
    """Create SE (Secure Element) data blocks dict from block 7 data."""
    return {
        6: '000000000000E014',
        7: blk7,
        8: '0000000000000000',
        9: '0000000000000000',
    }


def calcNewKey(typ, oldkey, newkey, l2e=False):
    """Calculate a new key via PM3 'hf iclass calcnewkey' command.

    Returns calculated key hex string, or -10 on failure.
    """
    if l2e:
        cmd = 'hf iclass calcnewkey --old {} --new {} --elite'.format(oldkey, newkey)
    else:
        cmd = 'hf iclass calcnewkey --old {} --new {}'.format(oldkey, newkey)

    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -10

    # Extract the calculated key
    content = executor.getPrintContent()
    if content:
        m = re.search(_RE_XOR_DIV_KEY, content)
        if m:
            return m.group(1).strip().replace(' ', '')

    return -10


def writeDataBlock(typ, block, data, key):
    """Write a single data block to an iClass tag.

    Binary string: 'hf iclass wrbl -b {} -d {} -k {}'
    Returns 0 on success, -10 on PM3 task error.
    """
    # Elite cards (type 18) need --elite for key derivation
    is_elite = (typ == getattr(tagtypes, 'ICLASS_ELITE', 18))
    cmd = 'hf iclass wrbl --blk {} -d {} -k {}'.format(block, data, key)
    if is_elite:
        cmd += ' --elite'
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -10

    # Iceman success: `Wrote block <N> / 0x<NN> ( ok )`
    # (cmdhficlass.c:3134). See _KW_WRBL_SUCCESS for citation detail.
    if executor.hasKeyword(_KW_WRBL_SUCCESS):
        return 0
    return -10


def writeDataBlocks(typ, file_or_dict, key='2020666666668888'):
    """Write multiple data blocks to an iClass tag.

    Data comes from file (binary) or dict (block_num -> hex_data).
    Returns 0 on success, -1 on any block failure.
    """
    blocks = getNeedWriteBlock(typ)

    for block_num in blocks:
        if isinstance(file_or_dict, dict):
            data = file_or_dict.get(block_num, '')
        else:
            data = readBlockHex(file_or_dict, block_num)

        if not data:
            continue

        ret = writeDataBlock(typ, block_num, data, key)
        if ret != 0:
            return -1

    return 0


def writePassword(typ, new_key, oldkey='2020666666668888', l2e=False):
    """Write a new password/key to the iClass tag.

    Returns 0 on success, or error code.
    """
    calc_key = calcNewKey(typ, oldkey, new_key, l2e)
    if calc_key == -10:
        return -10

    ret = writeDataBlock(typ, 3, calc_key, oldkey)
    if ret != 0:
        return -1

    return 0


def write(infos, bundle):
    """Write iClass tag from bundle data.

    Args:
        infos: dict with tag info (type, key, csn, etc.)
        bundle: dict with write data or file path string

    Returns 1 on success, -1 on failure.
    """
    if not infos:
        return -1

    try:
        typ = int(infos.get('type', getattr(tagtypes, 'ICLASS_LEGACY', 17)))
    except (ValueError, TypeError):
        typ = getattr(tagtypes, 'ICLASS_LEGACY', 17)
    key_info = infos.get('key', '2020666666668888')

    # Determine if bundle is a file path or dict
    if isinstance(bundle, str):
        file_path = bundle
    elif isinstance(bundle, dict):
        file_path = bundle.get('file', '')
    else:
        return -1

    if not file_path:
        return -1

    # Determine write key
    write_key = key_info if key_info else '2020666666668888'

    # Write data blocks
    ret = writeDataBlocks(typ, file_path, write_key)
    if ret != 0:
        return -1

    return 1


def verify(infos, bundle):
    """Verify iClass tag write by reading back and comparing.

    Args:
        infos: dict with tag info
        bundle: dict with expected data or file path string

    Returns 1 on verification passed, -1 on failure.
    """
    if not infos or not bundle:
        return -1

    try:
        typ = int(infos.get('type', getattr(tagtypes, 'ICLASS_LEGACY', 17)))
    except (ValueError, TypeError):
        typ = getattr(tagtypes, 'ICLASS_LEGACY', 17)
    key_info = infos.get('key', '2020666666668888')

    if isinstance(bundle, str):
        file_path = bundle
    elif isinstance(bundle, dict):
        file_path = bundle.get('file', '')
    else:
        return -1

    if not file_path:
        return -1

    read_key = key_info if key_info else '2020666666668888'
    blocks = getNeedWriteBlock(typ)

    for block_num in blocks:
        expected = readBlockHex(file_path, block_num)
        if not expected:
            continue

        # Read current block from tag
        is_elite = (typ == getattr(tagtypes, 'ICLASS_ELITE', 18))
        if hficlass:
            content = hficlass.readTagBlock(typ, block_num, read_key,
                                            elite=is_elite)
        else:
            cmd = 'hf iclass rdbl --blk {:02d} -k {}'.format(block_num, read_key)
            if is_elite:
                cmd += ' --elite'
            ret = executor.startPM3Task(cmd, TIMEOUT)
            if ret == -1:
                return -1
            content = executor.getPrintContent()

        if not content:
            return -1

        # Iceman rdbl block line:
        #   ` block %3d/0x%02X : <hex>` (cmdhficlass.c:3501)
        # The regex targets the iceman-native shape directly — prior form
        # `[Bb]lock\s*[0-9a-fA-F]+\s*:\s*...` matched neither iceman (had
        # `/0x..` infix) nor legacy blocks ≥10 (regex used `[0-9a-fA-F]`
        # which accepted hex, but the `\s*:` split failed on iceman). See
        # divergence_matrix.md "hf iclass rdbl" (line 493, Systemic #4).
        m = re.search(r'block\s+\d+\s*/0x[0-9A-Fa-f]+\s*:\s+([A-Fa-f0-9 ]+)',
                      content)
        if m:
            read_data = m.group(1).strip().replace(' ', '').upper()
            if read_data != expected.upper():
                return -1

    return 1
