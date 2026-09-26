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

"""appfiles -- File/directory management for card dumps.

Reimplemented from appfiles.so (iCopy-X v1.0.90).

Ground truth:
    Strings:  docs/v1090_strings/appfiles_strings.txt
    Audit:    docs/V1090_MODULE_AUDIT.txt
"""

import json
import os
import re

try:
    import commons
except ImportError:
    try:
        from . import commons
    except ImportError:
        commons = None

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
PATH_UPAN = '/mnt/upan/'
PATH_DUMP = '/mnt/upan/dump/'
PATH_KEYS = '/mnt/upan/keys/'
PATH_LOG_FILE = '/mnt/upan/log.txt'
PATH_TRACE = '/mnt/upan/trace/'

# ---------------------------------------------------------------------------
# Directory names per card type
# ---------------------------------------------------------------------------
DIR_NAME_M1 = 'mf1'
DIR_NAME_MFU = 'mfu'
DIR_NAME_HF14A = 'hf14a'
DIR_NAME_ICODE = 'icode'
DIR_NAME_LEGIC = 'legic'
DIR_NAME_T55XX = 't55xx'
DIR_NAME_EM410X = 'em410x'
DIR_NAME_EM4X05 = 'em4x05'
DIR_NAME_FELICA = 'felica'
DIR_NAME_ICLASS = 'iclass'
DIR_NAME_INDALA = 'indala'
DIR_NAME_IOPROX = 'ioprox'
DIR_NAME_HID = 'hid'
DIR_NAME_AWID = 'awid'
DIR_NAME_FDX = 'fdx'
DIR_NAME_PAC = 'pac'
DIR_NAME_KERI = 'keri'
DIR_NAME_PRESCO = 'presco'
DIR_NAME_VIKING = 'viking'
DIR_NAME_GPROXII = 'gproxii'
DIR_NAME_NORALSY = 'noralsy'
DIR_NAME_PARADOX = 'paradox'
DIR_NAME_PYRAMID = 'pyramid'
DIR_NAME_NEXWATCH = 'nexwatch'
DIR_NAME_VISA2000 = 'visa2000'
DIR_NAME_GALLAGHER = 'gallagher'
DIR_NAME_JABLOTRON = 'jablotron'
DIR_NAME_SECURAKEY = 'securakey'
DIR_NAME_NEDAP = 'nedap'
DIR_NAME_PAXTON = 'paxton'
DIR_NAME_HITAG2 = 'hitag2'

# Constructed dump paths
PATH_DUMP_M1 = PATH_DUMP + DIR_NAME_M1 + '/'
PATH_DUMP_MFU = PATH_DUMP + DIR_NAME_MFU + '/'
PATH_DUMP_HF14A = PATH_DUMP + DIR_NAME_HF14A + '/'
PATH_DUMP_ICODE = PATH_DUMP + DIR_NAME_ICODE + '/'
PATH_DUMP_LEGIC = PATH_DUMP + DIR_NAME_LEGIC + '/'
PATH_DUMP_T55XX = PATH_DUMP + DIR_NAME_T55XX + '/'
PATH_DUMP_EM410X = PATH_DUMP + DIR_NAME_EM410X + '/'
PATH_DUMP_EM4X05 = PATH_DUMP + DIR_NAME_EM4X05 + '/'
PATH_DUMP_FELICA = PATH_DUMP + DIR_NAME_FELICA + '/'
PATH_DUMP_ICLASS = PATH_DUMP + DIR_NAME_ICLASS + '/'
PATH_DUMP_PAXTON = PATH_DUMP + DIR_NAME_PAXTON + '/'
PATH_DUMP_HITAG2 = PATH_DUMP + DIR_NAME_HITAG2 + '/'

# Key storage paths
PATH_KEYS_M1 = PATH_KEYS + DIR_NAME_M1 + '/'
PATH_KEYS_T5577 = PATH_KEYS + DIR_NAME_T55XX + '/'

# ---------------------------------------------------------------------------
# File prefix constants
# ---------------------------------------------------------------------------
FILE_PREFIX_M1_1K_4B = 'M1-1K-4B'
FILE_PREFIX_M1_1K_7B = 'M1-1K-7B'
FILE_PREFIX_M1_4K_4B = 'M1-4K-4B'
FILE_PREFIX_M1_4K_7B = 'M1-4K-7B'
FILE_PREFIX_M1_MINI = 'M1-Mini'
FILE_PREFIX_M1_PLUS_2K = 'M1-Plus-2K'

PREFIX_NAME_UL = 'UL'
PREFIX_NAME_ULC = 'ULC'
PREFIX_NAME_UL_EV1 = 'UL-EV1'
PREFIX_NAME_NTAG213 = 'NTAG213'
PREFIX_NAME_NTAG215 = 'NTAG215'
PREFIX_NAME_NTAG216 = 'NTAG216'


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def mkdirs_on_icopy(path):
    """Create directory with permissions."""
    if commons:
        commons.mkdirs_on_icopy(path)
    else:
        os.makedirs(path, mode=0o775, exist_ok=True)


def _ensure_dir(path):
    """Ensure directory for a file path exists."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, mode=0o775, exist_ok=True)


def _next_filename(directory, prefix, uid, ext='.bin'):
    """Find next available numbered filename: prefix_uid_N.ext"""
    _ensure_dir(directory)
    n = 1
    while True:
        name = '{}_{}'.format(prefix, uid)
        path = os.path.join(directory, '{}_{}{}'.format(name, n, ext))
        if not os.path.exists(path):
            return path
        n += 1
        if n > 999:
            return path


def save2any(data, filename):
    """Save data to a file."""
    _ensure_dir(filename)
    try:
        if isinstance(data, bytes):
            with open(filename, 'wb') as f:
                f.write(data)
        else:
            with open(filename, 'w') as f:
                f.write(str(data))
    except Exception:
        pass


def create_file(path, data):
    """Create a file with data content."""
    save2any(data, path)


def read_text(file):
    """Read file as text."""
    try:
        with open(file, 'r') as f:
            return f.read()
    except Exception:
        return ''


def to_bytes(data):
    """Convert to bytes."""
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode('utf-8')
    return bytes(data)


def mkfile(path):
    """Create an empty file (original .so export)."""
    _ensure_dir(path)
    try:
        with open(path, 'w') as f:
            pass
    except Exception:
        pass


def replace_char_on_name(filename, char_map):
    """Replace characters in filename per char_map dict."""
    for old, new in char_map.items():
        filename = filename.replace(old, new)
    return filename


def delIfHaveSep(path):
    """Delete file if path contains directory separators."""
    if os.sep in str(path):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def get_num(filename_prefix):
    """Get next sequential number for filename prefix (legacy compat)."""
    return 1


def get_max_num(directory, prefix):
    """Get maximum sequential number used in directory for prefix."""
    if not os.path.isdir(directory):
        return 0
    max_n = 0
    for f in os.listdir(directory):
        if f.startswith(prefix):
            try:
                # Extract trailing number before extension
                base = os.path.splitext(f)[0]
                parts = base.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    max_n = max(max_n, int(parts[1]))
            except (ValueError, IndexError):
                pass
    return max_n


# ---------------------------------------------------------------------------
# Dump renaming (Dump Files > Tag Info > DOWN)
# ---------------------------------------------------------------------------
RENAME_OK = 1
RENAME_INVALID = -1
RENAME_EXISTS = -2
RENAME_FAILED = -3

# Characters never allowed in a dump name (path separators / FAT reserved)
_RENAME_INVALID_CHARS = '/\\:*?"<>|'


def is_valid_dump_name(name):
    """True if *name* can be used as a dump filename (without extension)."""
    if not name or name in ('.', '..') or name != name.strip():
        return False
    if name.startswith('.'):
        return False
    for ch in name:
        if ch in _RENAME_INVALID_CHARS or ord(ch) < 0x20:
            return False
    return True


def dump_set_files(path, whole_set=True):
    """Files that belong with dump *path*.

    With *whole_set*, every file in the same folder sharing the name before
    the extension (e.g. .bin + .json + .eml written by iceman for one dump);
    otherwise just *path*.
    """
    if not whole_set:
        return [path]
    directory = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        return [os.path.join(directory, f) for f in sorted(os.listdir(directory))
                if os.path.splitext(f)[0] == stem
                and os.path.isfile(os.path.join(directory, f))]
    except OSError:
        return [path]


def rename_dump_set(path, new_stem, whole_set=True):
    """Rename dump *path* (and its set, see dump_set_files) to *new_stem*.

    Extensions are kept. The rename is refused if any other file in the
    folder already uses *new_stem* (compared case-insensitively, as the
    dump storage is FAT). If one file fails to rename, the files already
    renamed are put back.

    Returns (code, new_path) where code is RENAME_OK, RENAME_INVALID,
    RENAME_EXISTS or RENAME_FAILED, and new_path is the renamed *path*
    (or the original *path* when nothing was renamed).
    """
    if not path or not is_valid_dump_name(new_stem):
        return RENAME_INVALID, path
    directory = os.path.dirname(path)
    old_stem = os.path.splitext(os.path.basename(path))[0]
    if new_stem == old_stem:
        return RENAME_OK, path

    sources = dump_set_files(path, whole_set)
    if path not in sources:
        sources.append(path)

    # Refuse if another file already uses the new name
    try:
        entries = os.listdir(directory)
    except OSError:
        return RENAME_FAILED, path
    own = set(os.path.basename(s) for s in sources)
    for f in entries:
        if f in own:
            continue
        if os.path.splitext(f)[0].lower() == new_stem.lower():
            return RENAME_EXISTS, path

    done = []
    try:
        for src in sources:
            ext = os.path.splitext(src)[1]
            dst = os.path.join(directory, new_stem + ext)
            os.rename(src, dst)
            done.append((src, dst))
    except OSError:
        for src, dst in reversed(done):
            try:
                os.rename(dst, src)
            except OSError:
                pass
        return RENAME_FAILED, path

    return RENAME_OK, os.path.join(directory, new_stem + os.path.splitext(path)[1])


# ---------------------------------------------------------------------------
# Dump content readers (shared by Tag Info and plugins)
#
# Read identifying values from inside a dump set rather than its filename,
# so renamed dumps still work. *path* may be any file of the set (.bin,
# .json, .eml, .txt); siblings are found by the name before the extension.
# Every reader returns None when the value can't be read, and hex values
# are uppercase with no spaces. They only read file contents: callers that
# prefer a device-format filename decide that order themselves.
# ---------------------------------------------------------------------------

# .bin length -> MIFARE Classic size label (hfmfread.create_name_by_type)
DUMP_MF1_SIZES = {320: 'Mini', 1024: '1K', 2048: 'Plus-2K', 4096: '4K'}

# iceman mfu_dump_t header length (include/mifare.h MFU_DUMP_PREFIX_LENGTH)
MFU_DUMP_HEADER_LEN = 56


def _is_hex(value, length=None):
    """True if *value* is a non-empty hex string (of *length* chars)."""
    if not value or (length is not None and len(value) != length):
        return False
    return all(c in '0123456789ABCDEFabcdef' for c in value)


def _dump_sibling(path, ext, mode='rb'):
    """Contents of the file in *path*'s dump set with extension *ext*, or None."""
    if not path:
        return None
    try:
        with open(os.path.splitext(path)[0] + ext, mode) as f:
            return f.read()
    except Exception:
        return None


def dump_json_card(path):
    """The 'Card' dict from the dump set's iceman .json sidecar, or {}."""
    text = _dump_sibling(path, '.json', 'r')
    if not text:
        return {}
    try:
        card = json.loads(text).get('Card', {})
        return card if isinstance(card, dict) else {}
    except Exception:
        return {}


def dump_mf1_size(path):
    """MIFARE Classic size from the .bin length: 'Mini', '1K', 'Plus-2K', '4K'.

    Returns None when there is no .bin or its length isn't a known size.
    """
    data = _dump_sibling(path, '.bin')
    if data is None:
        return None
    return DUMP_MF1_SIZES.get(len(data))


def dump_mf1_block0(path):
    """(uid, uid_len, sak, atqa) from .bin block 0, or None.

    Mirrors iceman pm3_save_mf_dump() (client/src/fileutils.c):
      4-byte UID: BCC matches and ATQA single-size bits clear
                  -> UID b0-3, SAK b5, ATQA b6-7
      7-byte UID: ATQA double-size bits set
                  -> UID b0-6, SAK b7, ATQA b8-9
    Block ATQA is little-endian; the result uses display order ('0004').
    """
    data = _dump_sibling(path, '.bin')
    if not data or len(data) < 16:
        return None
    d = bytearray(data[:16])
    if (d[0] ^ d[1] ^ d[2] ^ d[3]) == d[4] and (d[6] & 0xC0) == 0:
        return (bytes(d[0:4]).hex().upper(), 4,
                '%02X' % d[5], '%02X%02X' % (d[7], d[6]))
    if (d[8] & 0xC0) == 0x40:
        return (bytes(d[0:7]).hex().upper(), 7,
                '%02X' % d[7], '%02X%02X' % (d[9], d[8]))
    return None


def dump_mf1_card(path):
    """(uid, uid_len, sak, atqa) for a MIFARE Classic dump, or None.

    The .json Card values first (as saved from the anticollision response),
    then block 0 (dump_mf1_block0). From the .json, sak/atqa are None if
    not stored; ATQA is swapped from the JSON's little-endian order.
    """
    card = dump_json_card(path)
    uid = card.get('UID', '')
    if _is_hex(uid) and len(uid) in (8, 14, 20):
        sak = card.get('SAK', '')
        atqa = card.get('ATQA', '')
        return (uid.upper(), len(uid) // 2,
                sak.upper() if _is_hex(sak, 2) else None,
                (atqa[2:4] + atqa[0:2]).upper() if _is_hex(atqa, 4) else None)
    return dump_mf1_block0(path)


def dump_mfu_uid(path):
    """7-byte Ultralight/NTAG UID (14 hex chars), or None.

    Order: .json Card.UID (iceman jsfMfuMemory), then the .bin page data
    after the 56-byte header (UID = page0[0:3] + page1[0:4]). The .bin is
    only trusted when its length matches the header's page count (header
    byte 11 = last page index).
    """
    uid = dump_json_card(path).get('UID', '')
    if _is_hex(uid, 14):
        return uid.upper()
    data = _dump_sibling(path, '.bin')
    hdr = MFU_DUMP_HEADER_LEN
    if not data or len(data) < hdr + 8:
        return None
    if len(data) != hdr + 4 * (data[11] + 1):
        return None
    return (data[hdr:hdr + 3] + data[hdr + 4:hdr + 8]).hex().upper()


def dump_t55xx_b0(path):
    """T55xx block 0 (8 hex chars) from the 48-byte .bin, or None.

    iceman CmdT55xxDump saves each block big-endian, so block 0 is the
    first 4 bytes in display order. An all-zero block 0 is treated as
    invalid (iceman restore refuses to write it too).
    """
    data = _dump_sibling(path, '.bin')
    if not data or len(data) != 48:
        return None
    b0 = data[0:4]
    if b0 == b'\x00\x00\x00\x00':
        return None
    return b0.hex().upper()


def dump_hf14a_uid(path):
    """UID from the 'UID: <uid>' line hf14aread saves in its .txt, or None."""
    text = _dump_sibling(path, '.txt', 'r')
    if not text:
        return None
    for line in text.split('\n'):
        if line.startswith('UID:'):
            uid = line[len('UID:'):].strip()
            return uid.upper() if _is_hex(uid) else None
    return None


def dump_uid(path):
    """UID of a dump, chosen by its dump folder (mf1, mfu, hf14a), or None."""
    folder = os.path.basename(os.path.dirname(path or ''))
    if folder == DIR_NAME_M1:
        card = dump_mf1_card(path)
        return card[0] if card else None
    if folder == DIR_NAME_MFU:
        return dump_mfu_uid(path)
    if folder == DIR_NAME_HF14A:
        return dump_hf14a_uid(path)
    return None


def log_to_file(msg):
    """Append message to log file."""
    try:
        _ensure_dir(PATH_LOG_FILE)
        with open(PATH_LOG_FILE, 'a') as f:
            f.write(str(msg) + '\n')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Platform detection (no-ops on Linux, present for API compatibility)
# ---------------------------------------------------------------------------
_platform_mode = 'linux'


def isWindows():
    """Always False on iCopy-X (ARM Linux)."""
    return False


def switch_mode(mode):
    """Set platform mode string."""
    global _platform_mode
    _platform_mode = mode


def switch_windows():
    """Set Windows mode (no-op on real device)."""
    switch_mode('windows')


def switch_linux():
    """Set Linux mode."""
    switch_mode('linux')


def switch_current():
    """Set current platform mode."""
    switch_mode('linux')


def get_card_list():
    """Return list of supported card type directory names."""
    return [
        DIR_NAME_M1, DIR_NAME_MFU, DIR_NAME_HF14A, DIR_NAME_ICODE,
        DIR_NAME_LEGIC, DIR_NAME_T55XX, DIR_NAME_EM410X, DIR_NAME_EM4X05,
        DIR_NAME_FELICA, DIR_NAME_ICLASS, DIR_NAME_INDALA, DIR_NAME_IOPROX,
        DIR_NAME_HID, DIR_NAME_AWID, DIR_NAME_FDX, DIR_NAME_PAC,
        DIR_NAME_KERI, DIR_NAME_PRESCO, DIR_NAME_VIKING, DIR_NAME_GPROXII,
        DIR_NAME_NORALSY, DIR_NAME_PARADOX, DIR_NAME_PYRAMID, DIR_NAME_NEXWATCH,
        DIR_NAME_VISA2000, DIR_NAME_GALLAGHER, DIR_NAME_JABLOTRON,
        DIR_NAME_SECURAKEY, DIR_NAME_NEDAP, DIR_NAME_PAXTON,
    ]


# ---------------------------------------------------------------------------
# Card-type-specific file creation functions
# ---------------------------------------------------------------------------
def create_m1(uid, file):
    """Create MIFARE Classic dump path."""
    mkdirs_on_icopy(PATH_DUMP_M1)


def create_mfu(uid, file):
    """Create MIFARE Ultralight dump path."""
    mkdirs_on_icopy(PATH_DUMP_MFU)


def create_14443a(uid, file):
    """Create ISO14443A dump path."""
    mkdirs_on_icopy(PATH_DUMP_HF14A)


def create_icode(uid, file):
    """Create ISO15693 ICODE dump path."""
    mkdirs_on_icopy(PATH_DUMP_ICODE)


def create_legic(uid, file):
    """Create LEGIC dump path."""
    mkdirs_on_icopy(PATH_DUMP_LEGIC)


def create_felica(uid, file):
    """Create FeliCa dump path."""
    mkdirs_on_icopy(PATH_DUMP_FELICA)


def create_iclass(typ, csn):
    """Create iCLASS dump file path.

    Original .so creates directory and returns next available path:
    /mnt/upan/dump/iclass/Iclass-{typ}_{csn}_{n}
    Ground truth: trace_iclass_elite_read_20260401.txt line 7 —
    'hf iclass dump k ... f /mnt/upan/dump/iclass/Iclass-Elite_4A678E15FEFF12E0_1 e'
    """
    mkdirs_on_icopy(PATH_DUMP_ICLASS)
    prefix = 'Iclass-%s' % typ if typ else 'Iclass'
    uid = csn if csn else '00000000'
    return _next_filename(PATH_DUMP_ICLASS, prefix, uid, ext='').rstrip('.')


def create_t55xx(b0, b1='00000000', b2='00000000'):
    """Create T55XX dump path using block values in the filename.

    Returns next available path: /mnt/upan/dump/t55xx/T55xx_<b0>_<b1>_<b2>_N
    (without extension — iceman appends .bin and .json automatically).
    """
    mkdirs_on_icopy(PATH_DUMP_T55XX)
    b0 = b0.upper() if b0 else '00000000'
    b1 = b1.upper() if b1 else '00000000'
    b2 = b2.upper() if b2 else '00000000'
    uid = '%s_%s_%s' % (b0, b1, b2)
    return _next_filename(PATH_DUMP_T55XX, 'T55xx', uid, ext='').rstrip('.')


def create_em410x(uid, file):
    mkdirs_on_icopy(PATH_DUMP_EM410X)


def create_em4x05(uid, file):
    mkdirs_on_icopy(PATH_DUMP_EM4X05)


def create_indala(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_INDALA + '/')


def create_ioprox(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_IOPROX + '/')


def create_hid(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_HID + '/')


def create_awid(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_AWID + '/')


def create_fdx(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_FDX + '/')


def create_pac(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_PAC + '/')


def create_keri(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_KERI + '/')


def create_presco(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_PRESCO + '/')


def create_viking(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_VIKING + '/')


def create_gproxii(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_GPROXII + '/')


def create_noralsy(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_NORALSY + '/')


def create_paradox(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_PARADOX + '/')


def create_pyramid(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_PYRAMID + '/')


def create_nexwatch(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_NEXWATCH + '/')


def create_visa2000(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_VISA2000 + '/')


def create_gallagher(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_GALLAGHER + '/')


def create_jablotron(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_JABLOTRON + '/')


def create_securakey(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_SECURAKEY + '/')


def create_nedap(uid, file):
    mkdirs_on_icopy(PATH_DUMP + DIR_NAME_NEDAP + '/')


def create_paxton(uid, file):
    mkdirs_on_icopy(PATH_DUMP_PAXTON)


def create_hitag2(uid, file):
    mkdirs_on_icopy(PATH_DUMP_HITAG2)


def create_mf1_keys(uid, file):
    """Create MF1 keyfile directory."""
    mkdirs_on_icopy(PATH_KEYS_M1)


def create_t5577_keys(uid, file):
    mkdirs_on_icopy(PATH_KEYS_T5577)


def search_mf1_dump(pattern):
    """Search M1 dumps for pattern."""
    try:
        return [f for f in os.listdir(PATH_DUMP_M1)
                if re.search(pattern, f)]
    except (OSError, IOError):
        return []


def search_mf1_keys(pattern):
    """Search M1 keyfiles for pattern."""
    try:
        return [f for f in os.listdir(PATH_KEYS_M1)
                if re.search(pattern, f)]
    except (OSError, IOError):
        return []
