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

"""lft55xx -- T55xx tag detection, dump, read, write, key check.

Reimplemented from lft55xx.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Strings:    docs/v1090_strings/lft55xx_strings.txt
    Spec:       docs/middleware-integration/3-scan_spec.md (section 5.4)
    Analysis:   docs/ORIGINAL_ANALYSIS.md (T55xx Read section)
    Archive:    archive/lib_transliterated/lft55xx.py

API:
    CMD_DETECT_NO_KEY  = 'lf t55xx detect'
    CMD_DETECT_ON_KEY  = 'lf t55xx detect -p FFFFFFFF'
    CMD_DUMP_NO_KEY    = 'lf t55xx dump'
    KEYWORD_CASE1      = 'Could not detect modulation automatically'
    TIMEOUT = 10000
    KEY_TEMP = None

    detectT55XX(key=None) -> dict | int
    dumpT55XX(listener, key=None) -> int
    chkT55xx(listener) -> list
    chkAndDumpT55xx(listener) -> dict
    detectAndDumpT55xxByKey(listener, key) -> dict
    parser() -> dict
    parser_b0() -> str
    set_key(key) -> None
    call_listener(listener, max_value, progress, state='read') -> None
    genKeyFile(keys) -> str
"""

import os
import re

# ---------------------------------------------------------------------------
# Constants — from binary string extraction
# ---------------------------------------------------------------------------
CMD_DETECT_NO_KEY = 'lf t55xx detect'
CMD_DETECT_ON_KEY = 'lf t55xx detect -p FFFFFFFF'
CMD_DUMP_NO_KEY = 'lf t55xx dump'
KEYWORD_CASE1 = 'Could not detect modulation automatically'
TIMEOUT = 10000

# Regex patterns — iceman-native (P3.5 refactor, 2026-04-17).
#
# Iceman source: /tmp/rrg-pm3/client/src/cmdlft55xx.c:1837-1848
# (printConfiguration() — called by CmdT55xxDetect):
#     PrintAndLogEx(INFO, " Chip type......... T55x7");         # 9 dots
#     PrintAndLogEx(INFO, " Modulation........ ASK");           # 8 dots
#     PrintAndLogEx(INFO, " Block0............ %08X %s", ...);  # 12 dots, NO 0x
#     PrintAndLogEx(INFO, " Password set...... No/Yes");        # 6 dots
#     PrintAndLogEx(INFO, " Password.......... %08X", pwd);     # 10 dots
#
# Legacy source: same field names but colon-separated with spaces:
#     "     Chip Type      : T55x7"
#     "     Modulation     : ASK"
#     "     Block0         : 0x000880E0"          # WITH 0x prefix
#     "     Password Set   : No"
#     "     Password       : 00000000"
#
# Matrix section: divergence_matrix.md L1252-1274.
# Divergence type: FORMAT (dotted-leader vs colon-separator).
#
# Middleware now targets iceman dotted shape.  `_normalize_t55xx_config`
# (pm3_compat.py:1563) rewrites iceman→legacy and is now INVERSE of what
# the middleware needs — MUST BE DISABLED in Phase 4.  See gap log P3.5
# entry "lf t55xx detect dotted-field regressions".
#
# Regex design notes:
#   - `Chip [Tt]ype` tolerates case because iceman uses lowercase `type`
#     (cmdlft55xx.c:1837) vs legacy `Type` (capitalised).  Dropping case
#     sensitivity removes need for a separate adapter.
#   - `Block0\.+\s+([A-Fa-f0-9]+)` — NO `0x` prefix; iceman prints a raw
#     hex dword after the dots.  Legacy adapter added `0x` before the
#     refactor; the new regex is iceman-native and disregards `0x`.
#   - `[Pp]assword\.{6,}\s+([A-Fa-f0-9]+)` — iceman `Password..........`
#     with 10 dots; use `{6,}` to tolerate the shorter 6-dot
#     `Password set.` line (which matches the same regex but captures
#     `No`/`Yes` non-hex so the regex engine backtracks to skip it if
#     scanned line-by-line).  Callers only invoke this regex when
#     `Password` itself is present (the `usepwd` branch), so collisions
#     are benign.  Additional trailing hex characters terminate at
#     whitespace per `\s+`.
_RE_CHIP_TYPE = r'Chip [Tt]ype\.+\s+(\S+)'
_RE_MODULATE = r'Modulation\.+\s+(\S+)'
_RE_BLOCK0 = r'Block0\.+\s+([A-Fa-f0-9]+)'
_RE_PWD = r'[Pp]assword\.{8,}\s+([A-Fa-f0-9]+)'

# Detection keyword — iceman cmdlft55xx.c:1837 lowercase `type`.
# Substring match via `re.search` is case-sensitive in hasKeyword so
# `'Chip type'` is the correct iceman-native match.  `_KW_CHIP_TYPE`
# here is the human-readable fragment; the PM3 response has
# `" Chip type......... T55x7"` so the substring `Chip type` appears
# naturally.  Matrix L1267.
_KW_CHIP_TYPE = 'Chip type'
_KW_COULD_NOT_DETECT = 'Could not detect modulation automatically'

# Default keys — EXACT from QEMU extraction (archive/lib_transliterated/lft55xx.py)
DEFAULT_KEYS = (
    "# known cloners\n"
    "51243648\n"
    "000D8787\n"
    "19920427\n"
    "65857569\n"
    "05D73B9F\n"
    "89A69E60\n"
    "314159E0\n"
    "AA55BBBB\n"
    "A5B4C3D2\n"
    "1C0B5848\n"
    "00434343\n"
    "44B44CAE\n"
    "88661858\n"
    "575F4F4B\n"
    "50520901\n"
    "50524F58\n"
    "00000000\n"
    "11111111\n"
    "22222222\n"
    "33333333\n"
    "44444444\n"
    "55555555\n"
    "66666666\n"
    "77777777\n"
    "88888888\n"
    "99999999\n"
    "AAAAAAAA\n"
    "BBBBBBBB\n"
    "CCCCCCCC\n"
    "DDDDDDDD\n"
    "EEEEEEEE\n"
    "FFFFFFFF\n"
    "a0a1a2a3\n"
    "b0b1b2b3\n"
    "aabbccdd\n"
    "bbccddee\n"
    "ccddeeff\n"
    "50415353\n"
    "00000001\n"
    "00000002\n"
    "0000000a\n"
    "0000000b\n"
    "01020304\n"
    "02030405\n"
    "03040506\n"
    "04050607\n"
    "05060708\n"
    "06070809\n"
    "0708090A\n"
    "08090A0B\n"
    "090A0B0C\n"
    "0A0B0C0D\n"
    "0B0C0D0E\n"
    "0C0D0E0F\n"
    "01234567\n"
    "12345678\n"
    "10000000\n"
    "20000000\n"
    "30000000\n"
    "40000000\n"
    "50000000\n"
    "60000000\n"
    "70000000\n"
    "80000000\n"
    "90000000\n"
    "A0000000\n"
    "B0000000\n"
    "C0000000\n"
    "D0000000\n"
    "E0000000\n"
    "F0000000\n"
    "10101010\n"
    "01010101\n"
    "11223344\n"
    "22334455\n"
    "33445566\n"
    "44556677\n"
    "55667788\n"
    "66778899\n"
    "778899AA\n"
    "8899AABB\n"
    "99AABBCC\n"
    "AABBCCDD\n"
    "BBCCDDEE\n"
    "CCDDEEFF\n"
    "0CB7E7FC\n"
    "FABADA11\n"
    "87654321\n"
    "12341234\n"
    "69696969\n"
    "12121212\n"
    "12344321\n"
    "1234ABCD\n"
    "11112222\n"
    "13131313\n"
    "10041004\n"
    "31415926\n"
    "abcd1234\n"
    "20002000\n"
    "19721972\n"
    "aa55aa55\n"
    "55aa55aa\n"
    "4f271149\n"
    "07d7bb0b\n"
    "9636ef8f\n"
    "b5f44686\n"
    "9E3779B9\n"
    "C6EF3720\n"
    "7854794A\n"
    "F1EA5EED\n"
)

# Module-level state
KEY_TEMP = None
DUMP_TEMP = None
DUMP_FILE = None  # Path to last dump file (used by write.py for T55xx restore)

# Re-export tagtypes constants that lfread.so accesses via lft55xx.T55X7_ID
try:
    import tagtypes as _tt
    T55X7_ID = _tt.T55X7_ID
except (ImportError, AttributeError):
    T55X7_ID = 23


# ===========================================================================
# Utility functions
# ===========================================================================

def call_listener(listener, max_value, progress, state='read'):
    """Call the listener callback with progress info.

    QEMU-verified: calls listener(max_value, progress, state).
    """
    if listener:
        try:
            listener(max_value, progress, state)
        except Exception:
            pass


def genKeyFile(keys):
    """Generate a temporary key file from a list of keys.

    Writes to /tmp/.keys/t5577_tmp_keys.dic — the .dic suffix is
    required because iceman PM3's loadFileDICTIONARY_safe() always
    appends .dic when searching (filenamemcopy in fileutils.c).
    Factory PM3 accepted the bare filename, so this file name change
    is iceman-specific.  Returns the full path (caller passes it to
    `lf t55xx chk -f <path>`; iceman skips the .dic append because
    the name already ends with it).
    """
    keys_dir = '/tmp/.keys'
    os.makedirs(keys_dir, exist_ok=True)
    tmp_keys_file = os.path.join(keys_dir, 't5577_tmp_keys.dic')
    with open(tmp_keys_file, 'w') as f:
        for line in keys:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key = line.split()[0] if ' ' in line else line
            f.write(key + '\n')
    return tmp_keys_file


def set_key(key):
    """Set temporary T55xx key for password-protected operations."""
    global KEY_TEMP
    KEY_TEMP = key


# ===========================================================================
# Utility functions — write-phase support
# ===========================================================================

def list_split(items, n):
    """Split a list into chunks of size n.

    QEMU-verified:
        list_split([1,2,3,4,5], 2) = [[1,2], [3,4], [5]]
        list_split([], 2) = []
    """
    if not items:
        return []
    return [items[i:i + n] for i in range(0, len(items), n)]


def append_keys_unique(ks, key_list):
    """Append unique keys from list ks to key_list.

    QEMU-verified: deduplicates against existing entries.
    """
    if not isinstance(ks, (list, tuple)):
        return
    for k in ks:
        k_stripped = k.strip()
        if k_stripped and k_stripped not in key_list:
            key_list.append(k_stripped)


def append_keys_files_unique(files, key_list):
    """Read keys from files and append unique ones to key_list."""
    if not files:
        return
    if isinstance(files, str):
        files = [files]
    for f in files:
        try:
            keys = read_keys_of_file(f)
            append_keys_unique(keys, key_list)
        except Exception:
            pass


def read_keys_of_file(file):
    """Read keys from a dictionary file, one per line.

    Skips lines starting with '#' and empty lines.
    """
    keys = []
    try:
        with open(file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key = line.split()[0] if ' ' in line else line
                keys.append(key)
    except Exception:
        pass
    return keys


# ===========================================================================
# Parser functions
# ===========================================================================

def parser():
    """Parse lf t55xx detect output from executor cache.

    QEMU-verified return values:
        No detect -> {'found': True, 'type': 23, 'chip': '', 'modulate': '', 'b0': '', 'key': '', 'known': True}
        Successful detect -> {'found': True, 'type': 23, 'chip': 'T55x7', 'modulate': 'ASK', 'b0': '00148040', 'key': '', 'known': True}
        CASE1 (no modulation) -> {'found': True, 'type': 23, 'chip': 'T55xx/Unknown', 'modulate': '--------', 'b0': '--------', 'known': False}
    """
    try:
        import executor
        import tagtypes
    except ImportError:
        try:
            from . import executor
            from . import tagtypes
        except ImportError:
            return {'found': True, 'type': 23, 'chip': '', 'modulate': '', 'b0': '', 'key': '', 'known': True}

    result = {
        'found': True,
        'type': tagtypes.T55X7_ID,
        'chip': '',
        'modulate': '',
        'b0': '',
        'key': '',
        'known': True,
    }

    # Check for CASE1: could not detect modulation
    if executor.hasKeyword(KEYWORD_CASE1):
        result['chip'] = 'T55xx/Unknown'
        result['modulate'] = '--------'
        result['b0'] = '--------'
        result['known'] = False
        return result

    # Extract chip type
    chip = executor.getContentFromRegex(_RE_CHIP_TYPE)
    if chip:
        result['chip'] = chip.strip()

    # Extract modulation
    mod = executor.getContentFromRegex(_RE_MODULATE)
    if mod:
        result['modulate'] = mod.strip()

    # Extract Block0
    b0 = executor.getContentFromRegex(_RE_BLOCK0)
    if b0:
        result['b0'] = b0.strip()

    # Extract password/key
    pwd = executor.getContentFromRegex(_RE_PWD)
    if pwd:
        result['key'] = pwd.strip()

    return result


def parser_b0():
    """Extract Block0 value from executor cache.

    QEMU-verified: returns Block0 hex value as string, or '' if not found.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return ''

    b0 = executor.getContentFromRegex(_RE_BLOCK0)
    if b0:
        return b0.strip()
    return ''


# ===========================================================================
# T55xx detect / dump / check operations
# ===========================================================================

def detectT55XX(key=None):
    """Detect T55xx tag using 'lf t55xx detect'.

    Binary citation: __pyx_pw_7lft55xx_25detectT55XX
    Sends 'lf t55xx detect' (with key if provided or KEY_TEMP),
    parses response for Chip Type to confirm T55xx presence.

    Returns: 0 on success, negative integer on failure.
    Ground truth: lfread.so::readT55XX does `ret < 0` on the return value
    of detectT55XX at line 209 (verified via TypeError when returning dict).
    detectT55XX MUST return an integer.  The parsed info dict is cached in
    DUMP_TEMP for callers (scan_t55xx, chkAndDumpT55xx, readT55XX) that
    need the tag info.
    """
    global DUMP_TEMP, KEY_TEMP
    try:
        import executor
        import tagtypes
    except ImportError:
        try:
            from . import executor
            from . import tagtypes
        except ImportError:
            return -1

    # Build command with key argument, or KEY_TEMP, or no key
    if key:
        cmd = 'lf t55xx detect -p %s' % key
    elif KEY_TEMP:
        cmd = 'lf t55xx detect -p %s' % KEY_TEMP
    else:
        cmd = CMD_DETECT_NO_KEY

    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1

    # Check if Chip Type was found in response
    if not executor.hasKeyword(_KW_CHIP_TYPE):
        return -1

    # Parse result and cache it
    info = parser()
    DUMP_TEMP = info

    # Store key if provided
    if key:
        KEY_TEMP = key

    return 0


def dumpT55XX(listener, key=None):
    """Dump T55xx tag to file.

    QEMU-verified: sends 'lf t55xx dump' with optional password.
    Creates dump path via appfiles.create_t55xx() and includes ' f <path>'
    in the PM3 command. Stores path in DUMP_FILE for write.py access.
    Returns 0 on success, -2 on failure.
    """
    global DUMP_FILE
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -2

    # Create dump file path (original .so uses appfiles.create_t55xx)
    dump_path = None
    try:
        import appfiles
        dump_path = appfiles.create_t55xx('')
    except Exception:
        import os
        dump_dir = '/mnt/upan/dump/t55xx'
        os.makedirs(dump_dir, exist_ok=True)
        # Generate a unique filename
        idx = 1
        while True:
            dump_path = os.path.join(dump_dir, 'T55XX_%d' % idx)
            if not os.path.exists(dump_path + '.bin'):
                break
            idx += 1

    cmd = CMD_DUMP_NO_KEY
    if dump_path:
        cmd += ' -f %s' % dump_path
    if key:
        cmd += ' -p %s' % key

    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -2

    # Iceman-native success sentinel (P3.5 refactor):
    #
    # Iceman `pm3_save_dump()` in `/tmp/rrg-pm3/client/src/fileutils.c:293`:
    #     PrintAndLogEx(SUCCESS, "Saved %zu bytes to binary file `%s`", ...)
    # capital `S`, with accompanying json/em-compatible save lines at
    # :320/:947.  Legacy emitted `saved 12 blocks ...` (blocks not bytes)
    # which iceman removed entirely (grep of /tmp/rrg-pm3/client/src/ for
    # `saved 12 blocks` yields zero matches).  CmdT55xxDump at
    # cmdlft55xx.c:2647 calls pm3_save_dump with jsfT55x7 for successful
    # dumps, unchanged between firmware revisions for the output text.
    #
    # `_normalize_save_messages` (pm3_compat.py, wired at :1862) currently
    # lowercases iceman `Saved` → legacy `saved` on the `lf t55xx dump`
    # critical path.  After the P3.5 flip, middleware expects iceman
    # capital shape; the normalizer should be disabled/inverted in
    # Phase 4.  See gap log P3.5 "lf t55xx dump save-message flip".
    #
    # Matrix section: divergence_matrix.md L1278-1291 (row `lf t55xx
    # dump` — COSMETIC save line) + L1490-1496 (systemic divergence #6).
    if executor.hasKeyword(r'Saved \d+ bytes to binary file'):
        # Store path for later access by write.py
        if dump_path:
            DUMP_FILE = dump_path
        return 0
    return -2


def chkT55xx(listener):
    """Check T55xx for known keys.

    QEMU-verified: generates key file from DEFAULT_KEYS,
    runs 'lf t55xx chk f <keyfile>', returns list of found keys.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return []

    found_keys = []

    # Iceman-native regex for `Found valid password` emission.
    #
    # Iceman source: /tmp/rrg-pm3/client/src/cmdlft55xx.c:3658/:3660/:3816
    #     PrintAndLogEx(SUCCESS, "Found valid password: [ %08X ]", curr);
    # Format: the 4-byte hex password is wrapped in `[ XX ]` brackets
    # with spaces.  Legacy printed `Found valid password: XXXXXXXX`
    # without brackets; the prior regex `Found valid.*?:\s*([A-Fa-f0-9]+)`
    # matched the legacy bare-hex form but fails on iceman because `[`
    # is not in the `[A-Fa-f0-9]` character class (verified via
    # `python3 -c re.search` — iceman match returns None).
    #
    # New iceman-native pattern accepts the bracketed form; the optional
    # `\[?` allows legacy bare-hex to still match during the transition
    # (Option B compat).  `_normalize_t55xx_chk_password` (pm3_compat.py;
    # matrix L1286) rewrites iceman brackets → legacy bare-hex when the
    # compat adapter runs — becomes inverse of middleware once flipped;
    # must be disabled in Phase 4.  Gap log P3.5.
    _RE_FOUND_VALID = r'Found valid password:\s*\[?\s*([A-Fa-f0-9]+)\s*\]?'

    def lineInternal(line):
        if 'Found valid' in str(line):
            m = re.search(_RE_FOUND_VALID, str(line))
            if m:
                key = m.group(1)
                if key not in found_keys:
                    found_keys.append(key)

    try:
        key_file = genKeyFile(DEFAULT_KEYS.split('\n'))
    except Exception:
        return []

    cmd = 'lf t55xx chk -f %s' % key_file
    executor.add_task_call(lineInternal)
    ret = executor.startPM3Task(cmd, TIMEOUT * 3)
    executor.del_task_call(lineInternal)

    # Also check output cache for found keys (in case callback missed them)
    content = executor.getPrintContent()
    if content:
        for m in re.finditer(_RE_FOUND_VALID, content):
            key = m.group(1)
            if key not in found_keys:
                found_keys.append(key)

    return found_keys


def chkAndDumpT55xx(listener):
    """Check for keys and dump T55xx tag.

    QEMU-verified: runs chkT55xx, then detectT55XX/dumpT55XX with found key.
    Called by lfread.so::readT55XX(listener).

    Returns: dict on success, negative integer on failure.
    Ground truth: lfread.so::readT55XX calls detectT55XX (returns int),
    then calls chkAndDumpT55xx.  readT55XX checks isinstance(ret, dict)
    on chkAndDumpT55xx's return to determine success.
    detectT55XX returns int and caches info in DUMP_TEMP.
    """
    keys = chkT55xx(listener)
    key = keys[0] if keys else None

    detect_ret = detectT55XX(key)
    if detect_ret < 0:
        return -1

    # detectT55XX caches parsed info in DUMP_TEMP
    detect = DUMP_TEMP
    if not isinstance(detect, dict):
        return -1

    if not detect.get('known', True):
        return -2

    ret = dumpT55XX(listener, key)
    detect['dump_ret'] = ret
    # read.so accesses result['return'], result['data'], result['raw']
    detect['return'] = 1 if ret == 0 else -1
    detect.setdefault('data', detect.get('chip', ''))
    detect.setdefault('raw', detect.get('b0', ''))
    # Include dump file path for write.py T55xx restore
    if DUMP_FILE:
        detect['file'] = DUMP_FILE
    return detect


def detectAndDumpT55xxByKey(listener, key):
    """Detect and dump T55xx using a specific key.

    QEMU-verified: detects with key, dumps with key.
    Returns: dict on success, negative integer on failure.
    """
    detect_ret = detectT55XX(key)
    if detect_ret < 0:
        return -1

    detect = DUMP_TEMP
    if not isinstance(detect, dict):
        return -1

    if not detect.get('known', True):
        return -2

    ret = dumpT55XX(listener, key)
    detect['dump_ret'] = ret
    detect['return'] = 1 if ret == 0 else -1
    detect.setdefault('data', detect.get('chip', ''))
    detect.setdefault('raw', detect.get('b0', ''))
    return detect


# ===========================================================================
# T55xx read / write / wipe / lock operations — write-phase support
# ===========================================================================

def dumpT55XX_Text(key=None):
    """Dump T55xx blocks as text.

    QEMU-verified: reads all blocks and returns text representation.
    Called by lfverify.so for T55xx dump verification.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return ''

    result = ''
    for b in range(8):
        if key:
            cmd = 'lf t55xx read -b {} -p {}'.format(b, key)
        else:
            cmd = 'lf t55xx read -b {}'.format(b)
        ret = executor.startPM3Task(cmd, TIMEOUT)
        if ret != -1:
            content = executor.getPrintContent()
            if content:
                result += content + '\n'
    return result


def readBlock(pwd_str, b_index, p_index=0):
    """Read a single T55xx block.

    QEMU-verified: sends 'lf t55xx read b <b_index> p <pwd> o <p_index>'.
    Returns block data or ''.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return ''

    if pwd_str:
        cmd = 'lf t55xx read -b {} -p {}'.format(b_index, pwd_str)
        if p_index:
            cmd += ' --page1'
    else:
        cmd = 'lf t55xx read -b {}'.format(b_index)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return ''
    return executor.getPrintContent()


def getB0WithKey(key=None, from_detect=False):
    """Get Block0 data with optional key.

    v1.0.90 verified: if from_detect=True, uses cached detect output.
    Otherwise sends 'lf t55xx detect' directly. Returns Block0 hex or -1.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -1

    if not from_detect:
        if key:
            cmd = 'lf t55xx detect -p {}'.format(key)
        else:
            cmd = CMD_DETECT_NO_KEY
        ret = executor.startPM3Task(cmd, TIMEOUT)
        if ret == -1:
            return -1

    b0 = parser_b0()
    if b0 and b0 != '--------':
        return b0
    return -1


def getB0WithKeys(keys=None, from_detect=False):
    """Try multiple keys to get Block0.

    QEMU-verified: tries each key in list. Returns (b0, key) tuple
    on first success, or (-1, '') on failure.
    """
    if not keys:
        return (-1, '')

    for key in keys:
        b0 = getB0WithKey(key, from_detect=False)
        if b0 != -1:
            return (b0, key)

    return (-1, '')


def is_b0_lock(b0_data):
    """Check if Block0 indicates the tag is password-locked.

    QEMU-verified:
        is_b0_lock('00148040') = False
        is_b0_lock('00148050') = True   (bit 4 of byte 3 set)
    """
    if not b0_data or len(b0_data) < 8:
        return None
    try:
        b0_int = int(b0_data, 16)
        return bool(b0_int & 0x10)
    except ValueError:
        return False


def switch_lock(b0_data, lock_enable):
    """Toggle the lock bit in Block0 data.

    QEMU-verified:
        switch_lock('00148040', True) = '00148050'
        switch_lock('80148040', False) = '80148040'
    """
    if not b0_data or len(b0_data) < 8:
        return b0_data
    try:
        b0_int = int(b0_data, 16)
        if lock_enable:
            b0_int |= 0x10
        return '%08X' % b0_int
    except ValueError:
        return b0_data


def lock(setkey=True, b0=None, check_detect=True):
    """Lock the T55xx tag with password.

    QEMU-verified: sets lock bit in B0 and writes password to block 7.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -1

    if check_detect:
        detect_ret = detectT55XX()
        if detect_ret < 0:
            return -1

    if b0 is None:
        b0 = parser_b0()
    if not b0 or b0 == '--------':
        return -1

    b0_locked = switch_lock(b0, True)
    cmd = 'lf t55xx write -b 0 -d {}'.format(b0_locked)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1

    if setkey:
        return set_key_block('FFFFFFFF')
    return 0


def set_key_block(key):
    """Write password to T55xx block 7.

    QEMU-verified: sends 'lf t55xx write b 7 d <key>'.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -1

    cmd = 'lf t55xx write -b 7 -d {}'.format(key)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 0


def wipe_t(key=None):
    """Wipe T55xx tag (internal).

    QEMU-verified: sends 'lf t55xx wipe' with optional password.
    """
    try:
        import executor
    except ImportError:
        try:
            from . import executor
        except ImportError:
            return -1

    if key:
        cmd = 'lf t55xx wipe -p {}'.format(key)
    else:
        cmd = 'lf t55xx wipe'
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 0


def wipe0(listener):
    """Wipe T55xx without key.

    QEMU-verified: calls wipe_t() without key.
    """
    call_listener(listener, 1, 0, 'read')
    ret = wipe_t()
    call_listener(listener, 1, 1, 'read')
    return ret


def wipe1(listener):
    """Wipe T55xx with default key.

    QEMU-verified: calls wipe_t() with 'FFFFFFFF' key.
    """
    call_listener(listener, 1, 0, 'read')
    ret = wipe_t(key='FFFFFFFF')
    call_listener(listener, 1, 1, 'read')
    return ret


def wipe(listener):
    """Wipe T55xx tag - tries without key first, then with default key.

    QEMU-verified: tries wipe0, if that fails tries wipe1.
    """
    ret = wipe0(listener)
    if ret != 0:
        ret = wipe1(listener)
    return ret
