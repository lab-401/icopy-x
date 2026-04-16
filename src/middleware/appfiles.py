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
        DIR_NAME_SECURAKEY, DIR_NAME_NEDAP,
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


def create_t55xx(uid, file):
    """Create T55XX dump path."""
    mkdirs_on_icopy(PATH_DUMP_T55XX)


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
