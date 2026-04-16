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

"""hfmfkeys -- MIFARE Classic key management & recovery.

Reimplemented from hfmfkeys.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).
Full implementation — all exported functions for read AND write flows.

Ground truth:
    Strings:     docs/v1090_strings/hfmfkeys_strings.txt
    Audit:       docs/V1090_MODULE_AUDIT.txt (lines 454-512)
    Trace:       docs/Real_Hardware_Intel/trace_write_activity_attrs_20260402.txt
"""

import os
import re
import threading
import time

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import mifare
except ImportError:
    try:
        from . import mifare
    except ImportError:
        mifare = None

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
KEYS_MAP = {}
progressListener = None
keyInTagMax = 32

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
A = 'A'
B = 'B'
AB = 'AB'

RECOVERY_FCHK = 'ChkDIC'
RECOVERY_DARK = 'Darkside'
RECOVERY_NEST = 'Nested'
RECOVERY_STNE = 'STnested'

TIME_FHCK_ONE = 0.01
TIME_DARKSIDE_ONE = 60
TIME_NESTED_ONE = 11

TMP_KEYS_DIR = '/tmp/.keys'
TMP_KEYS_FILE = '/tmp/.keys/mf_tmp_keys.dic'

# ---------------------------------------------------------------------------
# Default key dictionary (from hfmfkeys_strings.txt lines 3083-3188)
# ---------------------------------------------------------------------------
DEFAULT_KEYS = [
    'FFFFFFFFFFFF', 'E00000000000', '000000000000', '111111111111',
    '010203040506', '0A65CB3EB977', '0000014B5C31', '021209197591',
    '050908080008', '0D258FE90296', '123456789ABC', '123456ABCDEF',
    '160A91D29A9C', '17193709ADF4', '199404281970', '1A2B3C4D5E6F',
    '1A982C7E459A', '1ACC3189578C', '22729A9BD40F', '2A2C13CC242A',
    '2EF720F2AF76', '314B49464956', '34016FAC127D', '369A4663ACD2',
    '38FCF33072E0', '4143532D494E', '414354616374', '414C41524F4E',
    '416363657302', '416363657303', '416363657304', '416363657305',
    '416363657306', '416363657307', '416363657308', '416363657309',
    '41636365730A', '41636365730B', '41636365730C', '41636365730D',
    '41636365730E', '41636365730F', '424C41524F4E', '4338265AFB87',
    '434143445649', '434456495243', '444156494442', '484558414354',
    '48734389EDC3', '49FAE4E3849F', '4A4C474F524D', '4A6352684677',
    '4D3A99C351DD', '4D414C414741', '4D61071B7254', '4F47454C4543',
    '509359F131B1', '533CB6C723F6', '536653644C65', '564C505F4D41',
    '587EE5F9350F', '5E594208EF02', '62D0C424ED8E', '6465706F7420',
    '66B03ACA6EE9', '66D2B7DC39EF', '6A1987C40A21', '6BC1E1AE547D',
    '6C20494E5049', '6C6520706173', '6C697365722E', '6C78928E1317',
    '714C5C886E97', '752FBB5B7B45', '7F33625BC129', '8829DA9DAF76',
    '89347350BD36', '8AD5517B4B18', '8FA1D601D0A2', '8FD0A4F256E9',
    '911E52FD7CE4', '96A301BCE267', 'A0478CC39091', 'A0A1A2A3A4A5',
    'A22AE129C013', 'A6CAC2886412', 'AA0720018738', 'AABBCCDDEEFF',
    'ABCDEF123456', 'AF9E38D36582', 'B0B1B2B3B4B5', 'B27CCAB30DBD',
    'B578F38A5C61', 'B7BF0C13066E', 'BF1F4424AF76', 'C0C1C2C3C4C5',
    'C2B7EC7D4EB1', 'D0D1D2D3D4D5', 'D3F7D3F7D3F7', 'E64A986A5D94',
    'E7D6064C5860', 'EEB420209D0C', 'F1EC94AACD81', 'F7EF6DE261F4',
]

# ---------------------------------------------------------------------------
# Composite key functions
# ---------------------------------------------------------------------------
def createTk(sector, typ):
    return '{}_{}'.format(sector, typ)

def getSectorFromTK(tk):
    return int(tk.split('_')[0])

def getTypeFromTK(tk):
    return tk.split('_')[1]

# ---------------------------------------------------------------------------
# Key map access
# ---------------------------------------------------------------------------
def getKey4Map(sector, typ):
    return KEYS_MAP.get(createTk(sector, typ))

def putKey2Map(sector, typ, key):
    KEYS_MAP[createTk(sector, typ)] = key

def delKey4Map(sector, typ):
    KEYS_MAP.pop(createTk(sector, typ), None)

def getAnyKey():
    for v in KEYS_MAP.values():
        return v
    return None

def hasKeyA(sector):
    return createTk(sector, A) in KEYS_MAP

def hasKeyB(sector):
    return createTk(sector, B) in KEYS_MAP

def hasAllKeys(size):
    sc = mifare.getSectorCount(size) if mifare else 0
    for sector in range(sc):
        if createTk(sector, A) not in KEYS_MAP:
            return False
        if createTk(sector, B) not in KEYS_MAP:
            return False
    return True

def getKeyMax4Size(size):
    sc = mifare.getSectorCount(size) if mifare else 0
    return sc - 1 if sc > 0 else 0

def getLostKeySector(size):
    sc = mifare.getSectorCount(size) if mifare else 0
    lost = 0
    for sector in range(sc):
        if createTk(sector, A) not in KEYS_MAP or createTk(sector, B) not in KEYS_MAP:
            lost += 1
    return lost

def getSizeFromBigSize(size):
    if size >= 4096:
        return 4
    if size >= 2048:
        return 2
    if size >= 1024:
        return 1
    return 0

# ---------------------------------------------------------------------------
# Key file I/O
# ---------------------------------------------------------------------------
def init_m1_key_file():
    try:
        os.makedirs(TMP_KEYS_DIR, exist_ok=True)
    except OSError:
        pass

def read_keys_of_file(file):
    keys = []
    try:
        with open(file, 'r') as f:
            for line in f:
                line = line.strip()
                if len(line) == 12 and re.match(r'^[A-Fa-f0-9]{12}$', line):
                    keys.append(line.upper())
    except (OSError, IOError):
        pass
    return keys

def append_keys_unique(files, key_list):
    seen = set(k.upper() for k in key_list)
    for fpath in (files if isinstance(files, list) else [files]):
        for k in read_keys_of_file(fpath):
            ku = k.upper()
            if ku not in seen:
                key_list.append(ku)
                seen.add(ku)

def genKeyFile(uid, key_list):
    init_m1_key_file()
    try:
        with open(TMP_KEYS_FILE, 'w') as f:
            for key in key_list:
                f.write(key + '\n')
    except (OSError, IOError):
        pass
    return TMP_KEYS_FILE

def list_split(items, n):
    """Split list into chunks of n."""
    return [items[i:i + n] for i in range(0, len(items), n)]

# ---------------------------------------------------------------------------
# fchks — fast dictionary key check
# PM3: hf mf fchk {size_param} {keyfile}  (timeout=600000)
# ---------------------------------------------------------------------------
_RE_KEY_TABLE = re.compile(
    r'\|\s*(\d+)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d+)\s*\|\s*([A-Fa-f0-9-]{12})\s*\|\s*(\d+)\s*\|'
)
_RE_HEX_KEY = re.compile(r'^[A-Fa-f0-9]{12}$')

def keysFromPrintParse(size):
    """Parse fchk output to populate KEYS_MAP.

    Only stores keys where res=1 (success) and the key is valid hex.
    The original .so ignores keys with res=0 (failed verification).
    Rows with '------------' (dashes) for a key field are skipped for that key.
    """
    text = executor.CONTENT_OUT_IN__TXT_CACHE if executor else ''
    for m in _RE_KEY_TABLE.finditer(text):
        sector = int(m.group(1))
        key_a = m.group(2).upper()
        res_a = int(m.group(3))
        key_b = m.group(4).upper()
        res_b = int(m.group(5))
        if res_a == 1 and _RE_HEX_KEY.match(key_a):
            putKey2Map(sector, A, key_a)
        if res_b == 1 and _RE_HEX_KEY.match(key_b):
            putKey2Map(sector, B, key_b)

def fchks(infos, size, with_call=True):
    """Fast dictionary key check. PM3: hf mf fchk."""
    uid = infos.get('uid', '') if isinstance(infos, dict) else ''
    key_file = genKeyFile(uid, list(DEFAULT_KEYS))

    size_flag = {4096: '--4k', 2048: '--2k', 320: '--mini'}.get(size, '--1k')
    cmd = 'hf mf fchk {} -f {}'.format(size_flag, key_file)
    ret = executor.startPM3Task(cmd, 600000)
    if ret == -1:
        return -1
    keysFromPrintParse(size)
    return 1

# ---------------------------------------------------------------------------
# Key recovery — darkside / nested
# These send PM3 commands and parse responses.
# ---------------------------------------------------------------------------
def darkside():
    """Darkside attack. PM3: hf mf darkside."""
    ret = executor.startPM3Task('hf mf darkside', 120000)
    if ret == -1:
        return -1
    text = executor.CONTENT_OUT_IN__TXT_CACHE or ''
    m = re.search(r'Found valid key\s*[:\[]\s*([A-Fa-f0-9]{12})', text)
    if m:
        key = m.group(1).upper()
        putKey2Map(0, A, key)
        return 1
    return -1

def darksideOneKey():
    """Single darkside attempt."""
    return darkside()

def onNestedCall(lines):
    """Callback for nested attack progress."""
    pass

def nestedOneKey(known, target, retryMax=5):
    """Nested attack for a single key."""
    known_sector = getSectorFromTK(known)
    known_type = getTypeFromTK(known)
    known_key = getKey4Map(known_sector, known_type)
    if not known_key:
        return -1
    target_sector = getSectorFromTK(target)
    target_type = getTypeFromTK(target)
    cmd = 'hf mf nested --1k --blk {} {} -k {} --tblk {} {}'.format(
        known_sector * 4, '-a' if known_type == 'A' else '-b', known_key,
        target_sector * 4, '--ta' if target_type == 'A' else '--tb')
    ret = executor.startPM3Task(cmd, 30000)
    if ret == -1:
        return -1
    text = executor.CONTENT_OUT_IN__TXT_CACHE or ''
    m = re.search(r'Found valid key\s*[:\[]\s*([A-Fa-f0-9]{12})', text)
    if m:
        putKey2Map(target_sector, target_type, m.group(1).upper())
        return 1
    return -1

def nested(size, infos):
    """Full nested attack for all missing keys."""
    known = getAnyKey()
    if not known:
        return -1
    known_tk = None
    for tk, key in KEYS_MAP.items():
        if key:
            known_tk = tk
            break
    if not known_tk:
        return -1
    sc = mifare.getSectorCount(size) if mifare else 16
    for sector in range(sc):
        for typ in (A, B):
            if not getKey4Map(sector, typ):
                nestedOneKey(known_tk, createTk(sector, typ))
    return 1

def nestedAllKeys(infos, size):
    """Recover all keys via nested."""
    return nested(size, infos)

# ---------------------------------------------------------------------------
# keys — full recovery pipeline
# ---------------------------------------------------------------------------
def keys(size, infos, listener):
    """Full key recovery pipeline: fchk → darkside → nested."""
    global progressListener
    progressListener = listener
    updateKeyMax(mifare.getSectorCount(size) * 2)

    # Start elapsed-time counter thread — drives the timer display
    # (ground truth: "01'08''" on read_tag_reading_2.png).
    _start_timer()

    try:
        updateRecovery(RECOVERY_FCHK)
        fchks(infos, size, with_call=True)
        updateKeyFound(0)
        if hasAllKeys(size):
            return 1

        updateRecovery(RECOVERY_DARK)
        darkside()
        updateKeyFound(0)
        if hasAllKeys(size):
            return 1

        updateRecovery(RECOVERY_FCHK)
        fchks(infos, size, with_call=False)
        updateKeyFound(0)
        if hasAllKeys(size):
            return 1

        updateRecovery(RECOVERY_NEST)
        nested(size, infos)
        updateKeyFound(0)
        if hasAllKeys(size):
            return 1

        updateRecovery(RECOVERY_FCHK)
        fchks(infos, size, with_call=False)
        updateKeyFound(0)
        return 1 if hasAllKeys(size) else -1
    finally:
        _stop_timer()

# ---------------------------------------------------------------------------
# Progress callbacks
#
# Ground truth: activity_read.py onReading() expects:
#   {'m1_keys': True, 'seconds': N, 'action': 'ChkDIC'|'Darkside'|'Nested',
#    'keyIndex': N, 'keyCountMax': 32, 'progress': N}
# ---------------------------------------------------------------------------
_current_action = ''
_timer_running = False
_timer_elapsed = 0

def _start_timer():
    """Start the 1-second elapsed-time counter thread.

    Ground truth: original .so count_down drives periodic progress
    callbacks with elapsed seconds so the UI timer ("01'08''") updates
    every second even when no keys are being found.
    """
    global _timer_running, _timer_elapsed
    _timer_elapsed = 0
    _timer_running = True

    def _tick():
        global _timer_elapsed
        while _timer_running:
            time.sleep(1)
            if not _timer_running:
                break
            _timer_elapsed += 1
            callProgress(seconds=_timer_elapsed)

    t = threading.Thread(target=_tick, daemon=True)
    t.start()

def _stop_timer():
    """Stop the elapsed-time counter thread."""
    global _timer_running
    _timer_running = False

def callProgress(seconds=0):
    """Report progress to the listener."""
    if progressListener is not None:
        found = sum(1 for v in KEYS_MAP.values() if v)
        # Use the running timer's elapsed seconds if no explicit value
        secs = seconds if seconds else _timer_elapsed
        try:
            progressListener({
                'm1_keys': True,
                'seconds': int(secs),
                'action': _current_action,
                'keyIndex': found,
                'keyCountMax': keyInTagMax,
                'progress': int(found * 100 / max(keyInTagMax, 1)),
            })
        except Exception:
            pass

def count_down():
    """Legacy entry point — timer is now thread-based via _start_timer."""
    pass

def updateKeyFound(count):
    """Report that keys were found."""
    callProgress()

def updateKeyMax(key_count_max):
    global keyInTagMax
    keyInTagMax = key_count_max

def updateRecovery(rec):
    """Update current recovery action and notify listener."""
    global _current_action
    _current_action = rec
    callProgress()

def is_keys_check_call(call):
    return False
