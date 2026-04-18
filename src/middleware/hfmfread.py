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

"""hfmfread -- MIFARE Classic block/sector reader.

Reimplemented from hfmfread.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).
Full implementation — all exported functions for read AND write flows.

Ground truth:
    Strings:     docs/v1090_strings/hfmfread_strings.txt
    Audit:       docs/V1090_MODULE_AUDIT.txt
    Spec:        docs/middleware-integration/5-read_spec.md (section 2)
"""

import os
import re

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

try:
    import hfmfkeys
except ImportError:
    try:
        from . import hfmfkeys
    except ImportError:
        hfmfkeys = None

try:
    import appfiles
except ImportError:
    try:
        from . import appfiles
    except ImportError:
        appfiles = None

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
DATA_MAP = {}
FILE_READ = None
A = 'A'
B = 'B'

# ---------------------------------------------------------------------------
# Utility wrappers (match original .so API)
# ---------------------------------------------------------------------------
def hasKeyword(keywords, line=None):
    return executor.hasKeyword(keywords, line) if executor else False

def getContentFromRegexA(regex):
    return executor.getContentFromRegexA(regex) if executor else None

def getContentFromRegexG(regex, group):
    return executor.getContentFromRegexG(regex, group) if executor else None

def startPM3Task(cmd, timeout, listener=None, rework_max=2):
    return executor.startPM3Task(cmd, timeout, listener, rework_max) if executor else -1

# ---------------------------------------------------------------------------
# Byte/hex utilities
# ---------------------------------------------------------------------------
def endian(atqa):
    """Swap byte order of 4-char hex string. '0004' → '0400'."""
    if not atqa or len(atqa) < 4:
        return atqa
    return atqa[2:4] + atqa[0:2]

def xor(datahex):
    """XOR all bytes of a hex string. Returns 2-char hex."""
    result = 0
    for i in range(0, len(datahex), 2):
        result ^= int(datahex[i:i + 2], 16)
    return '{:02X}'.format(result)

# ---------------------------------------------------------------------------
# Size / type mapping
# ---------------------------------------------------------------------------
def sizeGuess(typ):
    """Map tag type ID to card byte size."""
    if typ in (0, 40, 41):
        return 4096
    if typ in (1, 42, 43, 44):
        return 1024
    if typ == 26:
        return 2048
    if typ == 25:
        return 320
    return 1024

# ---------------------------------------------------------------------------
# Block data construction
# ---------------------------------------------------------------------------
def createManufacturerBlock(infos):
    """Construct block 0 from UID/SAK/ATQA."""
    uid = infos.get('uid', '')
    sak = infos.get('sak', '08')
    atqa = infos.get('atqa', '0004')
    uid_4b = uid[:8] if len(uid) >= 8 else uid.ljust(8, '0')
    bcc = xor(uid_4b)
    atqa_le = endian(atqa)
    block0 = uid_4b + bcc + sak + atqa_le
    return block0.ljust(32, '0')[:32]

def createEmptyBlock(block, infos):
    """Create an empty block (32 hex zeros)."""
    if mifare and mifare.isTrailerBlock(block):
        return mifare.EMPTY_TRAI
    return mifare.EMPTY_DATA if mifare else '00' * 16

def createTempDatas(size, infos):
    """Create a full empty card dump (list of 32-char hex per block)."""
    sc = mifare.getSectorCount(size) if mifare else 16
    data = []
    for sector in range(sc):
        bc = mifare.getBlockCountInSector(sector) if mifare else 4
        fb = mifare.sectorToBlock(sector) if mifare else sector * 4
        for offset in range(bc):
            block = fb + offset
            if block == 0:
                data.append(createManufacturerBlock(infos))
            else:
                data.append(createEmptyBlock(block, infos))
    return data

def createTempSector(sector, infos):
    """Create empty blocks for one sector."""
    bc = mifare.getBlockCountInSector(sector) if mifare else 4
    fb = mifare.sectorToBlock(sector) if mifare else sector * 4
    blocks = []
    for offset in range(bc):
        block = fb + offset
        blocks.append(createEmptyBlock(block, infos))
    return blocks

def create_name_by_type(infos):
    """Generate filename prefix from type and UID."""
    typ = infos.get('type', 1)
    uid = infos.get('uid', 'UNKNOWN')
    uid_len = infos.get('len', 4)
    size = sizeGuess(typ)
    if size == 4096:
        sz = '4K'
    elif size == 2048:
        sz = 'Plus-2K'
    elif size == 320:
        sz = 'Mini'
    else:
        sz = '1K'
    if uid_len == 7:
        return 'M1-{}-7B_{}'.format(sz, uid)
    return 'M1-{}-4B_{}'.format(sz, uid)

# ---------------------------------------------------------------------------
# File caching and saving
# ---------------------------------------------------------------------------
def cacheFile(file):
    global FILE_READ
    FILE_READ = file

def fillKeys2DataMap():
    """Copy hfmfkeys.KEYS_MAP into DATA_MAP."""
    global DATA_MAP
    if hfmfkeys:
        DATA_MAP.update(hfmfkeys.KEYS_MAP)

def save_bin(infos, data_list):
    """Save block data as binary .bin file."""
    name = create_name_by_type(infos)
    dump_dir = appfiles.PATH_DUMP_M1 if appfiles else '/mnt/upan/dump/mf1/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        pass
    n = 1
    while True:
        path = os.path.join(dump_dir, '{}_{}.bin'.format(name, n))
        if not os.path.exists(path):
            break
        n += 1
        if n > 999:
            break
    try:
        with open(path, 'wb') as f:
            for block_hex in data_list:
                if block_hex and len(block_hex) >= 32:
                    f.write(bytes.fromhex(block_hex[:32]))
                else:
                    f.write(b'\x00' * 16)
        cacheFile(path)
        return path
    except Exception:
        return None

def save_eml(infos, data_list):
    """Save block data as .eml text file."""
    name = create_name_by_type(infos)
    dump_dir = appfiles.PATH_DUMP_M1 if appfiles else '/mnt/upan/dump/mf1/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        pass
    n = 1
    while True:
        path = os.path.join(dump_dir, '{}_{}.eml'.format(name, n))
        if not os.path.exists(path):
            break
        n += 1
        if n > 999:
            break
    try:
        with open(path, 'w') as f:
            for block_hex in data_list:
                f.write((block_hex or '00' * 16).upper() + '\n')
        cacheFile(path)
        return path
    except Exception:
        return None

def parseAllKeyFromDataFile(infos, file):
    """Parse keys from a binary dump file's trailer blocks."""
    if not hfmfkeys:
        return []
    typ = infos.get('type', 1)
    size = sizeGuess(typ)
    sc = mifare.getSectorCount(size) if mifare else 16
    try:
        with open(file, 'rb') as f:
            data = f.read()
    except Exception:
        return []
    for sector in range(sc):
        fb = mifare.sectorToBlock(sector) if mifare else sector * 4
        bc = mifare.getBlockCountInSector(sector) if mifare else 4
        trailer_block = fb + bc - 1
        offset = trailer_block * 16
        if offset + 16 <= len(data):
            trailer = data[offset:offset + 16]
            key_a = trailer[0:6].hex().upper()
            key_b = trailer[10:16].hex().upper()
            hfmfkeys.putKey2Map(sector, A, key_a)
            hfmfkeys.putKey2Map(sector, B, key_b)
    return []

# ---------------------------------------------------------------------------
# Block / sector reading via PM3
# ---------------------------------------------------------------------------
# Block data emission shape — matches BOTH known iceman variants and
# the legacy-via-adapter shape:
#
#   1) `data: XX XX ... XX` (16 spaced hex pairs).
#      - Older iceman that uses sprint_hex without the table wrapper.
#      - Legacy FW after `pm3_compat._normalize_mf_block_grid` rewrites
#        ` N | XX XX ...` → `data: XX XX ...` (pm3_compat.py:1281 entry
#        for `hf mf rdsc`/`hf mf rdbl`).
#
#   2) ` N | XX XX ... XX | ascii` (block-num + pipe + 16 hex pairs +
#      pipe + ascii). Iceman v4.21611 native shape from
#      mf_print_block_one (/tmp/rrg-pm3/client/src/cmdhfmf.c:565-606)
#      via sprint_hex_ascii.  Legacy FW also natively emits the no-
#      ascii ` N | XX ...` variant, so this branch also catches the
#      raw legacy shape if the adapter is bypassed (LEGACY_COMPAT=False
#      kill-switch test).
#
# Both branches capture group 1 = 16-byte spaced hex.  re.MULTILINE so
# `^` anchors to per-line block-num rows (skip the table header which
# starts with `#`, not a digit).
_RE_BLOCK_DATA_LINE = re.compile(
    r'(?:data:|^\s*\d+\s*\|)\s*'
    r'((?:[A-Fa-f0-9]{2}\s+){15}[A-Fa-f0-9]{2})',
    re.MULTILINE
)


def _parse_blocks_from_text(text):
    """Extract 32-char hex block strings from iceman PM3 output.

    Iceman-native shape on this device: ``data: XX XX XX XX ... XX``
    (16 space-separated hex pairs per block) emitted from
    ``mf_print_block_one`` via sprint_hex/sprint_hex_ascii (cmdhfmf.c:572/
    L601/L603). Each matched line yields one 32-char hex block.
    """
    blocks = []
    for m in _RE_BLOCK_DATA_LINE.finditer(text):
        blocks.append(m.group(1).replace(' ', ''))
    return blocks

def readBlock(block, typ, key):
    """Read single block. PM3: hf mf rdbl --blk {block} -a/-b -k {key}."""
    cmd = 'hf mf rdbl --blk {} {} -k {}'.format(
        block, '-a' if typ == 'A' else '-b', key)
    ret = executor.startPM3Task(cmd, 10000)
    if ret == -1:
        return None
    if executor.hasKeyword('Auth error'):
        return -2
    text = executor.CONTENT_OUT_IN__TXT_CACHE or ''
    blocks = _parse_blocks_from_text(text)
    if blocks:
        return blocks[0].upper()
    return -2

def readSector(sector, typ, key):
    """Read a full sector. PM3: hf mf rdsc {sector} {typ} {key}."""
    fb = mifare.sectorToBlock(sector) if mifare else sector * 4
    bc = mifare.getBlockCountInSector(sector) if mifare else 4
    cmd = 'hf mf rdsc -s {} {} -k {}'.format(
        sector, '-a' if typ == 'A' else '-b', key)
    ret = executor.startPM3Task(cmd, 15000)
    if ret == -1:
        return None
    if executor.hasKeyword('Auth error'):
        return -2
    text = executor.CONTENT_OUT_IN__TXT_CACHE or ''
    blocks = _parse_blocks_from_text(text)
    if blocks and len(blocks) >= bc:
        return [b.upper() for b in blocks[:bc]]
    if blocks:
        return [b.upper() for b in blocks]
    return -2

def readBlocks(sector, keyA, keyB, infos):
    """Read all blocks in a sector, trying key A then key B."""
    result = None
    if keyA:
        result = readSector(sector, A, keyA)
    if (result is None or result == -2) and keyB:
        result = readSector(sector, B, keyB)
    return result if isinstance(result, list) else None

def readIfIsGen1a(infos):
    """Check if card is Gen1a via hf mf cgetblk --blk 0.

    Trust-then-probe detection against iceman PM3:
      1. Trust the scan cache if it already confirmed Gen1a (scan ran
         the same cgetblk probe and got a successful response).
      2. Otherwise run the probe and check for the iceman-native
         ``data:`` line (mf_print_block_one via sprint_hex) OR the
         iceman error keywords ``wupC1 error`` / ``Can't read block``
         (ARM Dbprintf + cmdhfmf.c:6171 PrintAndLogEx).

    Matrix section `hf mf cgetblk` (divergence_matrix.md L595-605):
    iceman success = `"data: 3A F7 35 01 ..."`, failure = `"wupC1 error\\n
    Can't read block. error=-1"`.
    """
    # 1) Trust the scan cache when it's already confirmed Gen1a — the scan
    #    layer ran the same cgetblk probe and got a successful response.
    if isinstance(infos, dict) and infos.get('gen1a') in (True, 'True', 'true', 1, '1'):
        return True

    ret = executor.startPM3Task('hf mf cgetblk --blk 0', 5888)
    if ret == -1:
        return None
    if executor.hasKeyword('wupC1 error') or executor.hasKeyword("Can't read block"):
        return None
    text = executor.CONTENT_OUT_IN__TXT_CACHE or ''
    # 2) Active probe: positive response is iceman's ``data: XX XX ...``
    #    line (cmdhfmf.c:603 sprint_hex_ascii via mf_print_block_one).
    if _RE_BLOCK_DATA_LINE.search(text):
        return True
    return None

# ---------------------------------------------------------------------------
# callListener — progress reporting
# Progress range: 80 + int((sector+1)/sectorMax * 20)  →  [81..100]
# ---------------------------------------------------------------------------
def callListener(sector, sectorMax, listener):
    """Report read progress to listener.

    Format matches activity_read.py onReading() expectations.
    Action 'REC_ALL' triggers the "Reading...N/Nkeys" status text.
    """
    if listener is None:
        return
    progress = 80 + int((sector + 1) / max(sectorMax, 1) * 20)
    try:
        listener({
            'm1_keys': True,
            'progress': progress,
            'action': 'REC_ALL',
            'keyIndex': sector + 1,
            'keyCountMax': sectorMax,
            'seconds': 0,
        })
    except Exception:
        pass

# ---------------------------------------------------------------------------
# readAllSector — main read loop
# ---------------------------------------------------------------------------
def readAllSector(size, infos, listener):
    """Read all sectors with available keys.

    Iterates each sector, reads with key A or B from hfmfkeys.KEYS_MAP.
    Reports progress via callListener.
    Returns list of 32-char hex strings (one per block), or [] if no
    blocks were successfully read (total failure).
    """
    sc = mifare.getSectorCount(size) if mifare else 16
    data_list = []
    real_read_count = 0
    for sector in range(sc):
        keyA = hfmfkeys.getKey4Map(sector, A) if hfmfkeys else None
        keyB = hfmfkeys.getKey4Map(sector, B) if hfmfkeys else None
        bc = mifare.getBlockCountInSector(sector) if mifare else 4
        blocks = readBlocks(sector, keyA, keyB, infos)
        if blocks and isinstance(blocks, list):
            data_list.extend(blocks)
            real_read_count += len(blocks)
        else:
            fb = mifare.sectorToBlock(sector) if mifare else sector * 4
            for offset in range(bc):
                data_list.append(createEmptyBlock(fb + offset, infos))
        callListener(sector, sc, listener)
    if real_read_count == 0:
        return []  # Total failure — no blocks readable
    return data_list
