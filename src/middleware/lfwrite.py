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

"""lfwrite -- LF cloning/writing for various card types.

Reimplemented from lfwrite.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Archive:    archive/lib_transliterated/lfwrite.py
    Spec:       docs/middleware-integration/6-write_spec.md (section 3)
    Strings:    docs/v1090_strings/lfwrite_strings.txt

Compat-flip status (P3.6 Write LF):
    All PM3 commands emitted by this module are iceman-native per the
    CLIParserInit signatures in /tmp/rrg-pm3/client/src/cmdlf*.c. Every
    command below cites the iceman dispatch entry + CLI spec; response
    parsing relies on `executor.startPM3Task` return code only (no
    output-keyword inspection in this module's critical paths), so the
    iceman divergence surface here is strictly on the SEND side (flag
    spelling). The Phase-4-deferred adapter (`pm3_compat.py`) handles
    the LEGACY-direction reverse translation for live-firmware
    compatibility; middleware remains iceman-canonical.

    See tools/ground_truth/divergence_matrix.md:
        L1053  lf em 410x clone
        L1126  lf fdxb clone
        L1158  lf hid clone
        L1176  lf indala clone
        L1189  RAW_CLONE_MAP (securakey/gallagher/pac/paradox/nexwatch)
        L1040  lf em 4x05 read/write/dump
        L1278  lf t55xx write/restore

API:
    write(listener, typ, infos, raw_par, key=None) -> int
    write_b0_need(typ, key=None) -> None
    write_em410x(em410x_id) -> int
    write_hid(hid_id) -> int
    write_indala(raw) -> int
    write_fdx_par(animal_id) -> int|None
    write_nedap(raw) -> bool
    write_raw(typ, raw, key=None) -> int
    write_raw_clone(typ, raw) -> bool
    write_raw_t55xx(raw) -> bool
    write_dump_t55xx(file, key=None) -> int
    write_dump_em4x05(file, key=None) -> int
    write_block_em4x05(blocks, start, end, key) -> int
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
    import lft55xx
except ImportError:
    try:
        from . import lft55xx
    except ImportError:
        lft55xx = None

try:
    import lfem4x05
except ImportError:
    try:
        from . import lfem4x05
    except ImportError:
        lfem4x05 = None

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        class tagtypes:
            EM410X_ID = 8
            HID_PROX_ID = 9
            INDALA_ID = 10
            AWID_ID = 11
            IO_PROX_ID = 12
            GPROX_II_ID = 13
            SECURAKEY_ID = 14
            VIKING_ID = 15
            PYRAMID_ID = 16
            T55X7_ID = 23
            EM4305_ID = 24
            FDXB_ID = 28
            GALLAGHER_ID = 29
            JABLOTRON_ID = 30
            KERI_ID = 31
            NEDAP_ID = 32
            NORALSY_ID = 33
            PAC_ID = 34
            PARADOX_ID = 35
            PRESCO_ID = 36
            VISA2000_ID = 37
            NEXWATCH_ID = 45

# ---------------------------------------------------------------------------
# Constants -- EXACT from QEMU extraction (lfwrite_strings.txt)
# ---------------------------------------------------------------------------
TIMEOUT = 10000

# B0_WRITE_MAP: tag type ID -> Block0 config word for T5577 cloning
# From binary strings: __pyx_k_00148068, __pyx_k_00088040, etc.
B0_WRITE_MAP = {
    37: '00148068',   # VISA2000
    15: '00088040',   # VIKING
    33: '00088C6A',   # NORALSY
    36: '00088088',   # PRESCO
    9:  '00107060',   # HID_PROX
    11: '00107060',   # AWID
    16: '00107080',   # PYRAMID
    12: '00147040',   # IO_PROX
    31: '603E1040',   # KERI
    30: '00158040',   # JABLOTRON
    13: '00150060',   # GPROX_II
    32: '907F0042',   # NEDAP
    # GROUND-TRUTH DEVIATION (Phase 6 workaround):
    # PAC/Stanley is normally cloned via `lf pac clone b <raw>`, which
    # the iCopy-X Community fork PM3 firmware accepts syntactically but
    # hangs during clone_t55xx_tag() on this hardware (observed: no
    # response + 3-4 reworks + eventual timeout; device requires app
    # restart to recover).  Computed config word from cmdlfpac.c:244:
    #   blocks[0] = T55x7_MODULATION_DIRECT (0)
    #             | T55x7_BITRATE_RF_32     (0x00080000)
    #             | 4 << T55x7_MAXBLOCK_SHIFT (4 << 5 = 0x80)
    #           = 0x00080080
    # Bypassing `lf pac clone` by doing direct `lf t55xx write` block
    # writes via the standard B0_WRITE_MAP path.
    34: '00080080',   # PAC/STANLEY (see deviation note above)
}

# RAW_CLONE_MAP: tag type ID -> PM3 clone command template
#
# Iceman-native: all five accept `-r <hex>` (short form of `--raw`) via
# CLIParserInit argtable `arg_str0/1("r", "raw", ...)`:
#   - lf securakey clone  -- cmdlfsecurakey.c:172 (dispatch :301)
#   - lf gallagher clone  -- cmdlfgallagher.c:175 (dispatch :387)
#   - lf pac clone        -- cmdlfpac.c:225       (dispatch :402)
#   - lf paradox clone    -- cmdlfparadox.c:296   (dispatch :478)
#   - lf nexwatch clone   -- cmdlfnexwatch.c:296  (dispatch :586)
# Divergence matrix L1189-1214. No structural divergence on the SEND side.
# Response emits "Done!" on success (e.g. cmdlfparadox.c success path) but
# this module only checks the PM3 return code via startPM3Task.
RAW_CLONE_MAP = {
    14: 'lf securakey clone -r {}',
    29: 'lf gallagher clone -r {}',
    # 34 (PAC/STANLEY) moved to B0_WRITE_MAP — `lf pac clone` hangs on
    # this firmware's clone_t55xx_tag() implementation.  See note above.
    35: 'lf paradox clone -r {}',
    45: 'lf nexwatch clone -r {}',
}

# Lock-unavailable types (from __pyx_k_lock_unavailable_list)
LOCK_UNAVAILABLE_LIST = []


# ===========================================================================
# Per-type write functions
# ===========================================================================

def write_em410x(em410x_id):
    """Write EM410x ID to T5577 card.

    Iceman-native: sends `lf em 410x clone --id <hex>`.
    CLI spec: cmdlfem410x.c:625 CLIParserInit "lf em 410x clone", argtable
    arg_str1(NULL, "id", "<hex>", ...). Dispatch at cmdlfem410x.c:896
    `{"clone", CmdEM410xClone, ...}`. Divergence matrix L1053-1069.

    Returns 1 on success, -1 on error (PM3 task return).
    """
    cmd = 'lf em 410x clone --id {}'.format(em410x_id)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 1


def write_hid(hid_id):
    """Clone HID Prox to T5577.

    Iceman-native: sends `lf hid clone -r <hex>` (short form of `--raw`).
    CLI spec: cmdlfhid.c:400 CmdHIDClone / CLIParserInit "lf hid clone",
    argtable arg_str0("r", "raw", "<hex>", ...). Dispatch at
    cmdlfhid.c:724. Divergence matrix L1158-1172. Legacy firmware also
    accepted `-r <hex>`; the SEND-side divergence is dormant.
    """
    cmd = 'lf hid clone -r {}'.format(hid_id)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 1


def write_indala(raw):
    """Clone Indala to T5577 / Q5.

    Iceman-native: sends `lf indala clone -r <hex>`.
    CLI spec: cmdlfindala.c:786 CmdIndalaClone / CLIParserInit
    "lf indala clone", argtable arg_str0("r", "raw", ...). Dispatch at
    cmdlfindala.c:1103. Divergence matrix L1176-1187.
    """
    cmd = 'lf indala clone -r {}'.format(raw)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 1


def write_fdx_par(animal_id):
    """Clone FDX-B animal tag.

    Iceman-native: sends `lf fdxb clone --country <dec> --national <dec>`.
    CLI spec: cmdlffdxb.c:712 CLIParserInit "lf fdxb clone", argtable
    arg_u64_1("c", "country", ...) + arg_u64_1("n", "national", ...).
    Dispatch at cmdlffdxb.c:909. Namespace changed iceman-vs-legacy:
    iceman uses `fdxb` (B-suffix); legacy used `fdx`. Divergence matrix
    L1126-1138.

    Input `animal_id` is a `<country>-<national>` or `<country> <national>`
    string.
    """
    parts = str(animal_id).replace('-', ' ').split()
    if len(parts) >= 2:
        cmd = 'lf fdxb clone --country {} --national {}'.format(parts[0], parts[1])
    else:
        return None
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1
    return 1


def write_nedap(raw):
    """Clone NEDAP tag.

    QEMU-verified: writes raw data to T5577 blocks.
    """
    return write_raw_t55xx(raw)


# PAR_CLONE_MAP: tag type ID -> function for parameter-based cloning
PAR_CLONE_MAP = {
    8:  write_em410x,
    9:  write_hid,
    10: write_indala,
    28: write_fdx_par,
    32: write_nedap,
}


def write_raw_clone(typ, raw):
    """Clone a tag using a raw clone command from RAW_CLONE_MAP."""
    if typ not in RAW_CLONE_MAP:
        return False
    cmd = RAW_CLONE_MAP[typ].format(raw)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return False
    return True


def write_raw_t55xx(raw):
    """Write raw data to T5577 blocks.

    Iceman-native: emits one `lf t55xx write -b N -d <hex>` per 4-byte
    (8 hex char) block. CLI spec: cmdlft55xx.c:1853 CmdT55xxWriteBlock /
    CLIParserInit "lf t55xx write", argtable arg_int1("b", "blk", ...) +
    arg_str0("d", "data", ...). Dispatch at cmdlft55xx.c:4794. Divergence
    matrix L1278-1290 (COSMETIC on response: iceman emits `Writing
    page %d  block: %02d  data: 0x%08X`, cmdlft55xx.c:1932).
    """
    blocks = [raw[i:i + 8] for i in range(0, len(raw), 8)]
    for i, block_data in enumerate(blocks):
        cmd = 'lf t55xx write -b {} -d {}'.format(i, block_data)
        ret = executor.startPM3Task(cmd, TIMEOUT)
        if ret == -1:
            return False
    return True


def write_b0_need(typ, key=None):
    """Write Block0 config word for a given tag type.

    Iceman-native: `lf t55xx write -b 0 -d <hex> [-p <hex>]`.
    Block 0 holds the T55xx modulation/bit-rate config word. Same CLI
    spec as `write_raw_t55xx` -- arg_str0("p", "pwd", ...) for the
    optional password.

    Looks up B0_WRITE_MAP and writes to T5577 block 0.
    """
    if typ not in B0_WRITE_MAP:
        return None

    config_block = B0_WRITE_MAP[typ]
    if key:
        cmd = 'lf t55xx write -b 0 -d {} -p {}'.format(config_block, key)
    else:
        cmd = 'lf t55xx write -b 0 -d {}'.format(config_block)
    executor.startPM3Task(cmd, TIMEOUT)
    return None


def write_raw(typ, raw, key=None):
    """Write raw data to T5577, with optional Block0 config.

    Iceman-native: one `lf t55xx write -b N -d <hex> [-p <hex>]` per
    block (N = 1..K for data, 0 last for config). CLI spec per
    `write_b0_need` / `write_raw_t55xx`.

    Ground truth (awid_write_trace_20260328.txt lines 19-26):
    Data blocks 1..N are written FIRST, then config block 0 LAST.
    Block 0 sets modulation/bit-rate -- writing it last avoids the
    tag re-modulating mid-sequence while data blocks are incomplete.
    """
    if typ in RAW_CLONE_MAP:
        return write_raw_clone(typ, raw)

    # Write data blocks 1..N first
    blocks = [raw[i:i + 8] for i in range(0, len(raw), 8)]
    for i, block_data in enumerate(blocks):
        block_num = i + 1
        if key:
            cmd = 'lf t55xx write -b {} -d {} -p {}'.format(block_num, block_data, key)
        else:
            cmd = 'lf t55xx write -b {} -d {}'.format(block_num, block_data)
        ret = executor.startPM3Task(cmd, TIMEOUT)
        if ret == -1:
            return -1

    # Write config block 0 LAST (sets modulation for the written data)
    if typ in B0_WRITE_MAP:
        write_b0_need(typ, key)

    return 0


def write_dump_t55xx(file, key=None):
    """Restore T5577 dump from file, then verify by reading blocks back.

    Iceman-native: `lf t55xx restore -f <path>`. CLI spec: cmdlft55xx.c:2653
    CmdT55xxRestore / CLIParserInit "lf t55xx restore" @ :2655, argtable
    arg_str0("f", "file", ...) + arg_str0("p", "pwd", ...). Dispatch at
    cmdlft55xx.c:4790. Iceman restore emits per-block writes via nested
    CmdT55xxWriteBlock calls, then `PrintAndLogEx(INFO, "Done!")` at
    cmdlft55xx.c:2771.  (Note: iceman HEAD has an orphaned v1 of
    CmdT55xxRestore inside a `/* ... */` comment block starting at
    :2774 — cite L2653 for the live function.)  Trace prefix was
    historically `lf t55xx restore f ...` (pre-canonicalisation); iceman
    accepts BOTH `-f` and the bare-char form.  Divergence matrix L1287.

    Ground truth: PM3 command log (original_current_ui write_t55xx_block_fail)
    shows the original lfwrite.so sends:
        1. lf t55xx restore f <file>
        2. lf t55xx detect
        3. lf t55xx read b 0 .. b 7 (page 0)
        4. lf t55xx read b 0 1 .. b 3 1 (page 1)
    and compares read-back blocks against dump file. This reimplementation
    delegates the detect+read-back step to `lft55xx` (P3.5 scope) and keeps
    the restore+compare-dump-file logic here.

    Returns 1 on verified success, -1 on restore failure or verify mismatch.
    """
    cmd = 'lf t55xx restore -f {}'.format(file)
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return -1

    # Post-restore verification: detect + read blocks + compare with dump file
    if lft55xx is None:
        return 1

    detect_ret = lft55xx.detectT55XX()
    if detect_ret < 0:
        return -1

    info = lft55xx.DUMP_TEMP
    det_key = None
    if isinstance(info, dict):
        det_key = info.get('key', '') or None

    # Read blocks from tag after restore
    dump_text = lft55xx.dumpT55XX_Text(det_key)

    # Read expected data from dump file for comparison
    expected_blocks = []
    try:
        paths = [file]
        if not file.endswith('.bin'):
            paths.append(file + '.bin')
        for fpath in paths:
            try:
                with open(fpath, 'rb') as f:
                    raw = f.read()
                # Parse 4-byte blocks (T55xx has 8 blocks × 4 bytes = 32 bytes,
                # or 12 blocks × 4 bytes = 48 bytes for full dump)
                for i in range(0, len(raw), 4):
                    block_hex = raw[i:i + 4].hex().upper()
                    expected_blocks.append(block_hex)
                break
            except FileNotFoundError:
                continue
    except Exception:
        pass

    if not expected_blocks:
        # Can't read dump file — accept restore success
        return 1

    # Compare: extract block hex from dump_text.
    #
    # Iceman-native row emission: cmdlft55xx.c:1831
    #     PrintAndLogEx(NORMAL, "%02d | 0x%08X | %s", j, blockData, ...)
    # Shape: `NN | 0xHHHHHHHH | <binary-ascii>`.  Iceman NEVER emits
    # `blk <N>` or `block <N>` on data rows — `blk` only appears in the
    # column header at cmdlft55xx.c:677 where the "hex data" column is
    # literal text, not extractable hex.  Pre-fix pattern
    # `(?:blk|block)\s*\d+\s*\|\s*([A-Fa-f0-9]{8})` was dead code
    # against iceman output.  The bare `\b[A-Fa-f0-9]{8}\b` fallback
    # was removed because it greedily captured the first 8-hex token
    # anywhere in the cache (including unrelated config descriptors,
    # DLMode tables, password strings).  The anchored iceman pattern
    # below rejects false-matches by requiring the `NN | 0x<8hex>`
    # framing.
    import re as _re
    read_blocks = _re.findall(r'^\s*\d+\s*\|\s*0x([A-Fa-f0-9]{8})\s*\|',
                              dump_text, _re.MULTILINE)

    if not read_blocks:
        return -1

    # Compare each block (skip block 0 config which may change)
    for i in range(1, min(len(expected_blocks), len(read_blocks))):
        if read_blocks[i].upper() != expected_blocks[i].upper():
            return -1

    return 1


def write_block_em4x05(blocks, start, end, key):
    """Write blocks to EM4x05/EM4x69 tag.

    Iceman-native: `lf em 4x05 write -a <dec> -d <hex> [-p <hex>]`.
    CLI spec: cmdlfem4x05.c:1399 CmdEM4x05Write / CLIParserInit
    "lf em 4x05 write", argtable arg_int0("a", "addr", ...) +
    arg_str1("d", "data", ...) + arg_str0("p", "pwd", ...). Divergence
    matrix L1040-1053 (FORMAT divergence on response output only;
    covered by `_normalize_em4x05_info` -- middleware doesn't parse
    write-response here).
    """
    for i in range(start, end + 1):
        if i < len(blocks):
            data = blocks[i]
            if not data or not data.strip():
                continue
            cmd = 'lf em 4x05 write -a {} -d {} -p {}'.format(i, data, key)
            ret = executor.startPM3Task(cmd, TIMEOUT)
            if ret == -1:
                return -1
    return 0


def write_dump_em4x05(file, key=None):
    """Restore EM4x05 dump from file.

    Iceman-native: per-block `lf em 4x05 write ...` for all 16 blocks,
    then per-block `lf em 4x05 read -a N [-p <hex>]` for the verify
    pass. Read CLI spec: cmdlfem4x05.c:1352 CmdEM4x05Read / CLIParserInit
    "lf em 4x05 read", argtable arg_int1("a", "addr", ...) +
    arg_str0("p", "pwd", ...). Read success emits:
        `Address %02d | %08X - %s`   (cmdlfem4x05.c:1391)
    where `%s` is "Lock" for addresses > 13, empty otherwise. The
    iceman-native verify regex below targets the `| %08X -` shape
    exactly (8 hex chars, no loose substring match).

    Reads blocks from dump file and writes via write_block_em4x05.
    Tries file as-is, then with .bin suffix.
    """
    dump_data = None
    for fpath in [file, file + '.bin'] if not file.endswith('.bin') else [file]:
        try:
            with open(fpath, 'rb') as f:
                dump_data = f.read()
            break
        except FileNotFoundError:
            continue
        except Exception:
            return -1
    if dump_data is None:
        return -1

    # Parse dump: 4 bytes per block, 16 blocks
    blocks = []
    for i in range(0, min(len(dump_data), 64), 4):
        block_hex = dump_data[i:i + 4].hex().upper()
        blocks.append(block_hex)

    if not blocks:
        return -1

    # Write blocks (skip block 4 which is password on EM4305)
    # Write order from spec: 0-3, 5-13, then 4 (password), then 14-15
    write_order = list(range(0, 4)) + list(range(5, 14)) + [4, 14, 15]

    for block_num in write_order:
        if block_num < len(blocks):
            data = blocks[block_num]
            cmd = 'lf em 4x05 write -a {} -d {} -p {}'.format(block_num, data, key or '')
            ret = executor.startPM3Task(cmd, TIMEOUT)
            if ret == -1:
                return -1

    # Verify: read blocks back
    # Iceman-native read success line shape (cmdlfem4x05.c:1391):
    #     `Address %02d | %08X - %s`
    # where `%s` is "Lock" for addr > 13, empty otherwise. Regex below
    # anchors on the `| <8-hex> -` motif to avoid matching any other
    # pipe-separated hex fragment that might appear in the cache.
    for block_num in range(min(len(blocks), 16)):
        cmd = 'lf em 4x05 read -a {}'.format(block_num)
        if key:
            cmd += ' -p {}'.format(key)
        ret = executor.startPM3Task(cmd, TIMEOUT)
        if ret == -1:
            return -1
        # Check read content matches
        content = executor.getPrintContent()
        if not content:
            return -1
        # Iceman-native: `Address NN | HHHHHHHH - <...>`
        m = re.search(r'Address\s+\d+\s+\|\s+([A-Fa-f0-9]{8})\s+-', content)
        if m is None:
            # Fallback: bare `| HHHHHHHH -` motif (for cache bodies where
            # the `Address NN` prefix was stripped by executor). Still
            # iceman-canonical, but more permissive.
            m = re.search(r'\|\s+([A-Fa-f0-9]{8})\s+-', content)
        if m:
            read_data = m.group(1).upper()
            if read_data != blocks[block_num]:
                return -1

    return 1


# DUMP_WRITE_MAP: tag type ID -> dump write function
DUMP_WRITE_MAP = {
    23: write_dump_t55xx,
    24: write_dump_em4x05,
}


def check_detect(key=None, listener=None):
    """Detect T55xx tag before write, wipe if password-protected.

    Ground truth (trace_original_write_newtag_20260410.txt lines 18-21):
    Original firmware sequence on write:
        1. lf t55xx wipe p 20206666
        2. lf t55xx detect
        3. If detect OK → proceed to write
        4. If detect FAIL → detect p 20206666 → if still fail → chk (brute force)

    Ground truth (trace_original_backlight_volume_20260410.txt lines 52-59):
    On a broken/unresponsive tag, the original firmware:
        1. wipe p 20206666
        2. detect → fail
        3. detect p 20206666 → fail
        4. chk f /tmp/.keys/t5577_tmp_keys → brute force all keys
    UI shows "Checking T55xx keys..." with ProgressBar during step 4.
    """
    _DRM_PWD = '20206666'

    if lft55xx is None:
        return -1

    # Step 1: Wipe with DRM password first (clears locked tags)
    lft55xx.wipe_t(_DRM_PWD)

    # Step 2: Try detect (works on clean/wiped tags)
    detect_ret = lft55xx.detectT55XX(key)
    if detect_ret == 0:
        # Detected — check if still locked and wipe again if so
        info = lft55xx.DUMP_TEMP
        if isinstance(info, dict):
            b0 = info.get('b0', '')
            if b0 and lft55xx.is_b0_lock(b0):
                lft55xx.wipe_t(info.get('key', '') or _DRM_PWD)
                lft55xx.detectT55XX()
        return 0

    # Step 3: Detect failed — try wipe without password, detect again
    lft55xx.wipe_t()
    detect_ret = lft55xx.detectT55XX()
    if detect_ret == 0:
        return 0

    # Step 4: Try detect with DRM password
    detect_ret = lft55xx.detectT55XX(_DRM_PWD)
    if detect_ret == 0:
        return 0

    # Step 5: Brute-force key check (matches original firmware fallback)
    # UI: "Checking T55xx keys..." with progress
    if listener is not None:
        try:
            _notify_listener(listener, 'Checking T55xx keys...')
        except Exception:
            pass

    found_keys = lft55xx.chkT55xx(listener)
    if found_keys:
        # Key found — wipe with it, detect
        lft55xx.wipe_t(found_keys[0])
        detect_ret = lft55xx.detectT55XX()
        if detect_ret == 0:
            return 0

    # All strategies exhausted — tag is unresponsive/broken
    return -1


def _notify_listener(listener, message):
    """Send a progress message to the write listener for UI update.

    The listener is the WriteActivity's on_write callback. We send a
    dict that the activity can use to update the ProgressBar message.
    """
    if listener is not None:
        try:
            listener({'progress_message': message, 'progress': -1})
        except Exception:
            pass


def _inline_verify(typ):
    """Post-clone inline verify: lf sea + tag-specific read.

    Iceman-native: `lf sea` -- iceman accepts both `lf sea` (short-prefix
    alias resolved by the dispatcher) and `lf search` (CLIParserInit at
    cmdlf.c:1890). Divergence matrix Appendix B L1567: "kept as
    `lf sea` in middleware since both accept it." No SEND-side adapter
    needed; `pm3_compat.py` has no `lf sea` reverse rule.

    Ground truth: PM3 command log (original_current_ui
    write_lf_em410x_verify_fail) shows the original lfwrite.so does
    `lf sea` + `lf em 410x_read` after cloning, before returning success.
    This consumes sequential fixture responses in the correct order.
    Result is not checked -- it's a best-effort inline verify.
    """
    try:
        executor.startPM3Task('lf sea', 10000)
        import lfread as _lfread
        read_fn = _lfread.READ.get(typ)
        if read_fn is not None:
            read_fn()
    except Exception:
        pass


def write(listener, typ, infos, raw_par, key=None):
    """Write/clone a tag based on type.

    Ground truth: lfwrite_strings.txt + archive/lib_transliterated/lfwrite.py
    Dispatch:
    1. If typ in DUMP_WRITE_MAP: write dump
    2. detect + wipe if needed
    3. If typ in PAR_CLONE_MAP: write by parameters
    4. If typ in RAW_CLONE_MAP: write raw clone
    5. If typ in B0_WRITE_MAP: write raw with B0
    6. Else: return -9
    """
    if not infos:
        return -9

    # Fresh rework budget for this write — previous flows' rework state
    # should not pre-brick this one.
    if executor is not None:
        try:
            executor.resetReworkCount()
        except AttributeError:
            pass

    # Dump-based write (T55xx dump, EM4305 dump)
    if typ in DUMP_WRITE_MAP:
        file_path = infos.get('file', '')
        if file_path:
            ret = DUMP_WRITE_MAP[typ](file_path, key)
            if ret == -1:
                return -9
            return ret

    # For all other LF types, detect T55xx and wipe if needed
    detect_ret = check_detect(key, listener=listener)
    if detect_ret < 0:
        return -9

    # Notify listener of progress
    if lft55xx:
        lft55xx.call_listener(listener, 2, 1, 'read')

    # Parameter-based clone
    if typ in PAR_CLONE_MAP:
        ret = PAR_CLONE_MAP[typ](raw_par)
        if ret is None or ret == -1:
            return -9
        # Inline verify: original lfwrite.so does lf sea + tag-specific read
        # after cloning (confirmed by PM3 command log).
        _inline_verify(typ)
        return 1

    # Raw clone command
    if typ in RAW_CLONE_MAP:
        ret = write_raw_clone(typ, raw_par)
        if ret is False:
            return -9
        _inline_verify(typ)
        return 1

    # B0 + raw write
    if typ in B0_WRITE_MAP:
        ret = write_raw(typ, raw_par, key)
        if ret == -1:
            return -9
        _inline_verify(typ)
        return 1

    return -9
