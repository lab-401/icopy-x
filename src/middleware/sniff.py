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

"""sniff -- Sniff trace parsing and PM3 sniff command dispatch.

Reimplemented from sniff.so (iCopy-X v1.0.90).

Ground truth:
    Binary:   decompiled/sniff_ghidra_raw.txt (10,281 lines)
    Strings:  docs/v1090_strings/sniff_strings.txt (1484 lines)
    Audit:    docs/V1090_MODULE_AUDIT.txt (lines 154-181)
    Symbols:  18 exported functions (__pyx_mdef_5sniff_1 through _35)

Complete exported API (from __pyx_mdef_5sniff_* in sniff_strings.txt:1467-1484):
    #1  sniff14AStart()
    #3  sniff14BStart()
    #5  sniffIClassAStart()
    #7  sniffTopazStart()
    #9  sniff125KStart()
    #11 sniffT5577Start()
    #13 parserLfTraceLen()
    #15 parserKeyForLine(line, regex)
    #17 parserT5577OkKeyForLine(line)
    #19 parserT5577LeadingKeyForLine(line)
    #21 parserT5577WriteKeyForLine(line)
    #23 parserKeysForT5577(parser_fn)
    #25 parserHfTraceLen()
    #27 parserM1KeyForLine(line)
    #29 parserDataForSCA(line, src, crc, annotation)
    #31 parserUidForData(line)
    #33 parserUidForKeyIndex(index, lines)
    #35 parserKeyForM1()

IMPORTS: executor, re
"""

import re

# ── Constants from binary ────────────────────────────────────────────
# sniff_strings.txt line 867
PATTERN_LF_TRACE_LEN = r'Reading (\d+) bytes from device memory'
# sniff_ghidra_raw.txt line 324, STR@0x0001c370
# Legacy: "trace len = 1066", Iceman: "Recorded activity ( 1066 bytes )"
PATTERN_HF_TRACE_LEN = r'(?:trace len = |Recorded activity \( )(\d+)'
# sniff_strings.txt line 871
PATTERN_T5577_OK_KEY = r'Default pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\|'
# sniff_strings.txt line 870
PATTERN_T5577_WRITE_KEY = r'Default write\s+\|\s+([A-Fa-f0-9]{8})\s\|'
# sniff_strings.txt line 869
PATTERN_T5577_LEADING_KEY = r'Leading [0-9a-zA-Z]* pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\|'
# sniff_strings.txt line 893
PATTERN_M1_KEY = r'key\s+([A-Fa-f0-9]+)'


# ── Sniff start commands ──────────────────────────────────────────────
# Each dispatches a PM3 command via executor.startPM3Task.
# Ground truth: sniff_ghidra_raw.txt, trace_sniff_flow_20260403.txt

def sniff14AStart():
    """Start ISO14443A sniff.

    Binary: __pyx_pw_5sniff_1sniff14AStart
    PM3 command: 'hf 14a sniff' (STR@0x0001c340)
    Ground truth: trace_original_sniff_full_20260412.txt line 408:
        PM3> hf 14a sniff (timeout=8000)
    The sniff command is fire-and-forget — PM3 starts listening and
    returns the prompt immediately. timeout=8000 lets startPM3Task
    return quickly so the activity can handle Stop keys.
    """
    import executor
    executor.startPM3Task('hf 14a sniff', 8000)


def sniff14BStart():
    """Start ISO14443B sniff.

    Binary: __pyx_pw_5sniff_3sniff14BStart
    PM3 command: 'hf 14b sniff' (follows 14A pattern, same timeout)
    """
    import executor
    executor.startPM3Task('hf 14b sniff', 8000)


def sniffIClassAStart():
    """Start iClass sniff.

    Binary: __pyx_pw_5sniff_5sniffIClassAStart
    PM3 command: 'hf iclass sniff' (STR@0x0001c2a0)
    """
    import executor
    executor.startPM3Task('hf iclass sniff', 8000)


def sniffTopazStart():
    """Start Topaz sniff.

    Binary: __pyx_pw_5sniff_7sniffTopazStart
    PM3 command: 'hf topaz sniff' (STR@0x0001c2e0)
    """
    import executor
    executor.startPM3Task('hf topaz sniff', 8000)


def sniff125KStart():
    """Start generic LF 125kHz sniff.

    Binary: __pyx_pw_5sniff_9sniff125KStart
    PM3 command: 'lf sniff' (STR@0x0001c3c0)

    Note: This is the GENERIC LF sniff. For T5577-specific sniff
    with lf config + lf t55xx sniff, use sniffT5577Start().
    """
    import executor
    executor.startPM3Task('lf sniff', 8000)


def sniffT5577Start():
    """Start T5577-specific LF sniff with config.

    Binary: __pyx_pw_5sniff_11sniffT5577Start (sniff_strings.txt:1159)
    PM3 commands:
        1. 'lf config a 0 t 20 s 10000' (sniff_strings.txt:874, timeout=5000)
        2. 'lf t55xx sniff' (sniff_strings.txt:897, timeout=-1, blocks until done)

    Ground truth:
        trace_sniff_t5577_enhanced_20260404.txt:
            lf config a 0 t 20 s 10000 (timeout=5000)
            lf t55xx sniff (timeout=-1)
        All T5577 fixtures use these two commands.

    This is SEPARATE from sniff125KStart() which sends 'lf sniff'.
    The original activity_main.so calls sniffT5577Start(), NOT sniff125KStart().
    """
    import executor
    executor.startPM3Task('lf config a 0 t 20 s 10000', 5000)
    executor.startPM3Task('lf t55xx sniff', -1)


# ── Trace length parsers ─────────────────────────────────────────────

def parserHfTraceLen():
    """Parse HF trace length from executor cache.

    Binary: __pyx_pw_5sniff_25parserHfTraceLen (sniff_strings.txt:1155)
    Takes ZERO arguments.
    Reads executor.CONTENT_OUT_IN__TXT_CACHE internally.
    Uses regex: 'trace len = (\\d+)' (STR@0x0001c370)

    Returns:
        int: trace length in bytes, or 0 if no match.
    """
    import executor
    result = executor.getContentFromRegexG(PATTERN_HF_TRACE_LEN, 1)
    if result:
        try:
            return int(result)
        except (ValueError, TypeError):
            return 0
    return 0


def parserLfTraceLen():
    """Parse LF trace length from executor cache.

    Binary: __pyx_pw_5sniff_13parserLfTraceLen (sniff_strings.txt:1156)
    Takes ZERO arguments.
    Reads executor.CONTENT_OUT_IN__TXT_CACHE internally.
    Uses regex: 'Reading (\\d+) bytes from device memory' (sniff_strings.txt:867)

    Ground truth: T5577 fixtures all contain 'Reading N bytes from device memory'
    where N is the trace length (e.g., 42259, 38499, 24999).

    Returns:
        int: trace length in bytes, or 0 if no match.
    """
    import executor
    result = executor.getContentFromRegexG(PATTERN_LF_TRACE_LEN, 1)
    if result:
        try:
            return int(result)
        except (ValueError, TypeError):
            return 0
    return 0


# Backward-compat alias: original sniff.py used 'parserTraceLen' (not in binary)
parserTraceLen = parserHfTraceLen


# ── T5577 key/password parsers ───────────────────────────────────────

def parserT5577OkKeyForLine(line):
    """Extract password from a 'Default pwd write' trace line.

    Binary: __pyx_pw_5sniff_17parserT5577OkKeyForLine (sniff_strings.txt:1148)
    Regex: 'Default pwd write\\s+\\|\\s+([A-Fa-f0-9]{8})\\s\\|' (sniff_strings.txt:871)

    Example match:
        '[+] Default pwd write | 20206666 | 00148040 |  1  |...'
        → returns '20206666'

    Does NOT match 'Default write' or 'Default write/pwd read' lines.

    Args:
        line: Single trace line string.

    Returns:
        str: 8-char hex password, or '' if no match.
    """
    if not line:
        return ''
    m = re.search(PATTERN_T5577_OK_KEY, str(line))
    if m:
        return m.group(1)
    return ''


def parserT5577LeadingKeyForLine(line):
    """Extract password from a 'Leading ... pwd write' trace line.

    Binary: __pyx_pw_5sniff_19parserT5577LeadingKeyForLine (sniff_strings.txt:1147)
    Regex: 'Leading [0-9a-zA-Z]* pwd write\\s+\\|\\s+([A-Fa-f0-9]{8})\\s\\|'
           (sniff_strings.txt:869)

    Args:
        line: Single trace line string.

    Returns:
        str: 8-char hex password, or '' if no match.
    """
    if not line:
        return ''
    m = re.search(PATTERN_T5577_LEADING_KEY, str(line))
    if m:
        return m.group(1)
    return ''


def parserT5577WriteKeyForLine(line):
    """Extract data from a 'Default write' (no password) trace line.

    Binary: __pyx_pw_5sniff_21parserT5577WriteKeyForLine (sniff_strings.txt:1146)
    Regex: 'Default write\\s+\\|\\s+([A-Fa-f0-9]{8})\\s\\|' (sniff_strings.txt:870)

    Example match:
        '[+] Default write | 00000000 | C02A4E07 |  1  |...'
        → returns '00000000'

    Does NOT match 'Default pwd write' or 'Default write/pwd read' lines
    because the regex requires 'Default write' followed by whitespace+pipe,
    not 'Default pwd write' or 'Default write/'.

    Args:
        line: Single trace line string.

    Returns:
        str: 8-char hex data, or '' if no match.
    """
    if not line:
        return ''
    m = re.search(PATTERN_T5577_WRITE_KEY, str(line))
    if m:
        return m.group(1)
    return ''


def parserKeysForT5577(parser_fn):
    """Extract T5577 keys from executor cache using a line parser function.

    Binary: __pyx_pw_5sniff_23parserKeysForT5577 (sniff_strings.txt:1145)
    Takes 1 argument: a parser function (e.g., parserT5577OkKeyForLine).

    Reads executor.CONTENT_OUT_IN__TXT_CACHE, splits into lines,
    applies parser_fn to each line, and collects non-empty results.

    Ground truth (QEMU probe, post-mortem Section 2.3):
        parserKeysForT5577(parserT5577OkKeyForLine)
        → ['20206666', '20206666', ...] (list of hex password strings)

    Args:
        parser_fn: Callable(line) → str. Returns key/password or ''.

    Returns:
        list: List of non-empty key strings extracted from cache.
    """
    import executor
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if not cache.strip():
        return []

    results = []
    for line in cache.split('\n'):
        key = parser_fn(line)
        if key:
            results.append(key)
    return results


# ── HF key and data parsers ──────────────────────────────────────────

def parserKeyForLine(line, regex):
    """Extract key from a trace line using regex.

    Binary: __pyx_pw_5sniff_15parserKeyForLine (sniff_strings.txt:1149)

    Args:
        line: Single trace line string.
        regex: Regex pattern with capturing group for the key.

    Returns:
        str: Matched key hex string, or '' if no match.
    """
    if not line or not regex:
        return ''
    m = re.search(regex, str(line))
    if m and m.lastindex:
        return m.group(m.lastindex)
    return ''


def parserM1KeyForLine(line):
    """Extract MIFARE key from a single trace line.

    Binary: __pyx_pw_5sniff_27parserM1KeyForLine (sniff_strings.txt:1162)
    Regex: 'key\\s+([A-Fa-f0-9]+)' (sniff_strings.txt:893)

    Matches trace annotation lines containing 'key FFFFFFFFFFFF' pattern.
    Example: '... | key FFFFFFFFFFFF prng WEAK |' → 'FFFFFFFFFFFF'

    Args:
        line: Single trace line string from 'hf list mf' output.

    Returns:
        str: Hex key string, or '' if no match.
    """
    if not line:
        return ''
    m = re.search(PATTERN_M1_KEY, str(line))
    if m:
        return m.group(1).upper()
    return ''


def parserDataForSCA(line, src='Rdr', crc='ok', annotation=''):
    """Parse trace line for Side Channel Analysis data.

    Binary: __pyx_pw_5sniff_29parserDataForSCA (sniff_strings.txt:1161)

    Parses structured trace output lines (from hf list / hf 14a list).
    Filters by source (Rdr/Tag), CRC status, and optional annotation.

    Args:
        line: Single trace line from PM3 list output.
        src: Source filter — 'Rdr' (reader) or 'Tag'.
        crc: CRC filter — 'ok' or 'fail'.
        annotation: Annotation text filter.

    Returns:
        dict: {'src': str, 'data': str, 'crc': str, 'annotation': str}
              or None if line doesn't match filters.
    """
    if not line:
        return None
    # Parse tabular trace format:
    # "  N |  time | Rdr |data          | crc | annotation"
    parts = [p.strip() for p in str(line).split('|')]
    if len(parts) < 4:
        return None
    line_src = parts[2] if len(parts) > 2 else ''
    line_data = parts[3] if len(parts) > 3 else ''
    line_crc = parts[4] if len(parts) > 4 else ''
    line_ann = parts[5] if len(parts) > 5 else ''

    if src and src not in line_src:
        return None
    if crc and crc not in line_crc.lower():
        return None
    if annotation and annotation not in line_ann:
        return None

    return {
        'src': line_src.strip(),
        'data': line_data.strip(),
        'crc': line_crc.strip(),
        'annotation': line_ann.strip(),
    }


def parserUidForData(line):
    """Extract UID/CSN from trace data line.

    Binary: __pyx_pw_5sniff_31parserUidForData (sniff_strings.txt:1158)
    Uses SELECT_UID marker (STR@0x0001c3a8) to identify UID response.

    Enhanced beyond original binary: also matches 'CSN' annotation
    for iClass protocol traces. RRG PM3 'hf list iclass' annotates
    the Tag IDENTIFY response as 'CSN'.

    Args:
        line: Trace line potentially containing UID/CSN data.

    Returns:
        str: UID/CSN hex string, or '' if not found.
    """
    if not line:
        return ''
    line = str(line)
    # SELECT_UID: ISO14443A MIFARE (original binary behavior)
    # CSN: iClass IDENTIFY response (RRG PM3 enhancement)
    if 'SELECT_UID' in line or '| CSN' in line:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) > 3:
            data = parts[3].strip()
            # UID is in the data field, remove spaces
            return data.replace(' ', '').strip()
    return ''


def parserUidForKeyIndex(index, lines):
    """Get UID associated with a key index from trace lines.

    Binary: __pyx_pw_5sniff_33parserUidForKeyIndex (sniff_strings.txt:1144)

    Args:
        index: Key index (0-based).
        lines: List of trace line strings.

    Returns:
        str: UID hex string, or '' if not found.
    """
    if not lines or index < 0:
        return ''
    uid_count = 0
    for line in lines:
        uid = parserUidForData(line)
        if uid:
            if uid_count == index:
                return uid
            uid_count += 1
    return ''


def parserKeyForM1():
    """Extract MIFARE Classic keys from executor cache.

    Binary: __pyx_pw_5sniff_35parserKeyForM1 (sniff_strings.txt:1143)
    Reads executor.CONTENT_OUT_IN__TXT_CACHE, parses trace lines
    to extract UID->key mappings from authentication exchanges.

    Returns:
        dict: {uid_hex: [key1_hex, key2_hex, ...]} or empty dict.
    """
    import executor
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if not cache.strip():
        return {}

    result = {}
    current_uid = None
    for line in cache.split('\n'):
        # Detect UID from SELECT_UID annotation
        uid = parserUidForData(line)
        if uid:
            current_uid = uid
            if current_uid not in result:
                result[current_uid] = []
            continue
        # Detect key from authentication response
        # MIFARE auth pattern: key bytes in reader data after SELECT
        if current_uid and '|' in line:
            key = parserM1KeyForLine(line)
            if key:
                result[current_uid].append(key)
    return result


# ── Save function (NOT in sniff.so — provided for activity compatibility) ──

def saveSniffData():
    """Save captured trace data to file.

    NOTE: This function does NOT exist in the original sniff.so binary
    (confirmed: not in symbol table, sniff_ghidra_raw.txt).
    In the original firmware, SniffActivity.saveSniffData() is an
    activity method in activity_main.so that writes executor cache
    to /mnt/upan/trace/ directly.

    This function is provided so that SimulationTraceActivity._saveSniffData()
    can delegate to it. It writes executor.CONTENT_OUT_IN__TXT_CACHE to
    /mnt/upan/trace/sim_{N}.txt.
    """
    import os
    import executor
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if not cache.strip():
        return
    trace_dir = '/mnt/upan/trace'
    try:
        os.makedirs(trace_dir, exist_ok=True)
        existing = [f for f in os.listdir(trace_dir)
                    if f.startswith('sim_') and f.endswith('.txt')]
        seq = len(existing) + 1
        fpath = os.path.join(trace_dir, 'sim_%d.txt' % seq)
        with open(fpath, 'w') as f:
            f.write(cache)
    except OSError:
        pass
