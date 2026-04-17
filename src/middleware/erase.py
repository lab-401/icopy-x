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

"""Erase tag middleware — MF1 (Gen1a + standard) and T5577.

Reimplements the erase logic from activity_main.so WipeTagActivity:
    wipe_m1         (activity_main_strings.txt:21185)
    wipe_magic_m1   (activity_main_strings.txt:21025)
    wipe_std_m1     (activity_main_strings.txt:21073)
    wipe_t5577      (activity_main_strings.txt:21101)

Ground truth:
    Trace: docs/Real_Hardware_Intel/trace_erase_flow_20260330.txt
    UI spec: docs/UI_Mapping/13_erase_tag/README.md

This module does NOT touch UI. It returns a result string that the
activity uses to show the appropriate toast. Progress is reported
via an optional callback so the activity can update its ProgressBar.

Results:
    'success'  — erase completed
    'no_keys'  — MF1 standard: no sector keys found
    'no_tag'   — hf 14a info timeout (no tag on reader)
    'error'    — MF1: cwipe timeout or wrbl isOk:00
    'failed'   — T5577: all wipe strategies exhausted
"""

import re

# =====================================================================
# MF1 — Tag Detection (separate from erase for SCANNING state)
# =====================================================================

def detect_mf1_tag():
    """Detect MF1 tag and determine Gen1a vs standard.

    Binary source: WipeTagActivity.wipe_m1 (detection phase)
    Trace: trace_erase_flow_20260330.txt lines 6-10

    Returns:
        dict: {'info_cache': str, 'is_gen1a': bool} on success
        str: 'no_tag' if no tag detected
    """
    import executor

    # Step 1: Detect tag (trace line 9)
    ret = executor.startPM3Task('hf 14a info', 5000)
    if ret == -1:
        return 'no_tag'
    info_cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''

    # Step 2: Test Gen1a magic (trace line 10)
    # Gen1a is confirmed when cgetblk returns actual block data without errors.
    # Legacy firmware included 'isOk:01'; iceman returns 'data: XX XX ...' format.
    import re as _re
    ret = executor.startPM3Task('hf mf cgetblk --blk 0', 5888)
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    has_error = ('wupC1 error' in cache or "Can't read block" in cache)
    has_block_data = bool(_re.search(
        r'(?:Block\s*0\s*:|data:|isOk:01)\s*[A-Fa-f0-9 ]{16,}', cache))
    is_gen1a = has_block_data and not has_error

    return {'info_cache': info_cache, 'is_gen1a': is_gen1a}

# =====================================================================
# MF1 — Erase (after detection)
# =====================================================================

def erase_mf1_detected(info_cache, is_gen1a, on_progress=None):
    """Erase MF1 tag after detection.

    Binary source: WipeTagActivity.wipe_magic_m1 / wipe_std_m1
    Trace: trace_erase_flow_20260330.txt

    Args:
        info_cache: Response from hf 14a info (for SAK parsing)
        is_gen1a: True if Gen1a magic card detected
        on_progress: Optional callback(phase, current, total)
            phase='chkdic'  — key check started (current=0, total=0)
            phase='erasing' — block write progress (current=block, total=num_blocks)

    Returns:
        str: 'success', 'no_keys', or 'error'
    """
    if is_gen1a:
        return _erase_magic_m1()
    return _erase_std_m1(info_cache, on_progress)

def erase_mf1(on_progress=None):
    """Erase MF1 tag — detect then erase (convenience wrapper).

    Returns:
        str: 'success', 'no_tag', 'no_keys', or 'error'
    """
    result = detect_mf1_tag()
    if result == 'no_tag':
        return 'no_tag'
    return erase_mf1_detected(
        result['info_cache'], result['is_gen1a'], on_progress)

def _erase_magic_m1():
    """Gen1a magic card: single cwipe command.

    Binary source: WipeTagActivity.wipe_magic_m1
    Trace: trace_erase_flow_20260330.txt line 10
    Timeout: 28888ms (from trace)

    Returns:
        str: 'success' or 'error'
    """
    import executor

    ret = executor.startPM3Task('hf mf cwipe', 28888)
    if ret == -1:
        return 'error'
    return 'success'

def _erase_std_m1(info_cache, on_progress=None):
    """Standard MF1 card: fchk keys then wrbl zeros/transport to all blocks.

    Binary source: WipeTagActivity.wipe_std_m1
    Trace: trace_erase_gen1a_and_standard.txt (1K) — 112 wrbl commands
    Trace: trace_erase_flow_20260330.txt (4K) — 326 wrbl commands

    Algorithm (from trace):
        Phase 1: Data blocks — zeros, reverse sector order
            - Highest sector data blocks first (skip trailers)
            - Block 0: UID+BCC+SAK+ATQA+manufacturer (preserve card identity)
        Phase 2: Trailer blocks — transport config, reverse order
            - Data: FFFFFFFFFFFFFF078069FFFFFFFFFFFF
            - 3 retries with key A, then 1 with key B
            - Trailers: blocks 3,7,11,...,63 (1K) or 3,7,...,255 (4K)

    Args:
        info_cache: Response from hf 14a info (for SAK/UID/ATQA parsing)
        on_progress: Optional callback(phase, current, total)

    Returns:
        str: 'success', 'no_keys', or 'error'
    """
    import executor

    # Determine card type from SAK (trace: SAK 08 → 1K, SAK 18 → 4K)
    sak_m = re.search(r'SAK:\s*([0-9a-fA-F]+)', info_cache)
    sak = int(sak_m.group(1), 16) if sak_m else 0x08
    mf_type = 4 if sak == 0x18 else 1
    num_blocks = 256 if mf_type == 4 else 64
    # 1K: 16 sectors × 4 blocks, 4K: 32 × 4 + 8 × 16 blocks
    # Sector trailers: every 4th block for sectors 0-31,
    #   every 16th block offset 15 for sectors 32-39 (4K only)
    if mf_type == 4:
        sector_trailers = set(
            [i * 4 + 3 for i in range(32)] +
            [128 + i * 16 + 15 for i in range(8)]
        )
    else:
        sector_trailers = set(i * 4 + 3 for i in range(16))

    # Key check (trace: timeout=600000ms)
    if on_progress:
        on_progress('chkdic', 0, 0)
    size_flag = {0: '--mini', 1: '--1k', 2: '--2k', 4: '--4k'}.get(mf_type, '--1k')
    # Ensure the MF Classic key dictionary file exists on disk —
    # iceman PM3 fails with "can't find .dic" otherwise.  hfmfkeys.fchks()
    # normally generates it during reads, but erase may run cold (no
    # prior read in this boot) and /tmp is volatile across reboots.
    key_file = '/tmp/.keys/mf_tmp_keys.dic'
    try:
        import hfmfkeys as _hfmfkeys
        key_file = _hfmfkeys.genKeyFile('', list(_hfmfkeys.DEFAULT_KEYS))
    except Exception:
        pass
    ret = executor.startPM3Task(
        'hf mf fchk %s -f %s' % (size_flag, key_file), 600000)
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''

    # Check if any keys were found
    fm = re.search(r'found\s+(\d+)/(\d+)\s+keys', cache)
    if fm and int(fm.group(1)) == 0:
        return 'no_keys'

    # Extract per-sector keys from fchk output
    # Trace (trace_original_full_20260410.txt): erase uses correct key per sector
    # e.g. sectors 0-5 use 4a6352684677/536653644c65, sectors 6-15 use ffffffffffff
    keys_a = {}
    keys_b = {}
    for km in re.finditer(
            r'\|\s*(\d+)\s*\|\s*([0-9a-fA-F]{12})\s*\|\s*(\d)\s*\|'
            r'\s*([0-9a-fA-F]{12})\s*\|\s*(\d)\s*\|', cache):
        sec = int(km.group(1))
        if km.group(3) == '1':
            keys_a[sec] = km.group(2)
        if km.group(5) == '1':
            keys_b[sec] = km.group(4)

    # Fallback: sector 0 keys or default
    default_key_a = keys_a.get(0, 'ffffffffffff')
    default_key_b = keys_b.get(0, default_key_a)

    # Construct block 0 data: UID + BCC + SAK + ATQA(reversed) + manufacturer
    # Trace: wrbl 0 A key 9C75088465080400016F016D4568F81D (1K)
    # Trace: wrbl 0 A key 0000000000180200016F016D4568F81D (4K)
    # Manufacturer bytes: hardcoded in hfmfread.so (__pyx_kp_u_016F016D4568F81D)
    _DEFAULT_MFR = '016F016D4568F81D'
    uid_m = re.search(r'UID:\s*([0-9A-Fa-f ]+)', info_cache)
    atqa_m = re.search(r'ATQA:\s*([0-9A-Fa-f ]+)', info_cache)
    uid_hex = uid_m.group(1).replace(' ', '').strip() if uid_m else '00000000'
    uid_bytes = bytes.fromhex(uid_hex)
    bcc = 0
    for b in uid_bytes:
        bcc ^= b
    sak_hex = '%02X' % sak
    atqa_raw = atqa_m.group(1).replace(' ', '').strip() if atqa_m else '0004'
    # ATQA in block 0 is byte-reversed (00 04 → 04 00)
    atqa_reversed = atqa_raw[2:4] + atqa_raw[0:2] if len(atqa_raw) >= 4 else atqa_raw
    block0_data = (uid_hex + '%02X' % bcc + sak_hex + atqa_reversed +
                   _DEFAULT_MFR).upper()
    # Pad/truncate to 32 hex chars (16 bytes)
    block0_data = (block0_data + '0' * 32)[:32]

    # Transport trailer: default keys + access bits 078069
    # Trace: FFFFFFFFFFFFFF078069FFFFFFFFFFFF
    transport_trailer = 'FFFFFFFFFFFFFF078069FFFFFFFFFFFF'
    zeros = '00000000000000000000000000000000'

    # Helper: block number → sector number
    def _block_to_sector(block):
        if mf_type == 4 and block >= 128:
            return 32 + (block - 128) // 16
        return block // 4

    # --- Phase 1: Data blocks (reverse sector order) ---
    # Trace (trace_original_full_20260410.txt): 3× Key A + 1× Key B per block
    # Trace: 60,61,62, 56,57,58, ..., 4,5,6, 0,1,2 (1K)
    if mf_type == 4:
        ordered_data = []
        for sec in range(39, 31, -1):
            base = 128 + (sec - 32) * 16
            for blk in range(base, base + 15):
                ordered_data.append(blk)
        for sec in range(31, -1, -1):
            base = sec * 4
            for blk in range(base, base + 3):
                ordered_data.append(blk)
    else:
        ordered_data = []
        for sec in range(15, -1, -1):
            base = sec * 4
            for blk in range(base, base + 3):
                ordered_data.append(blk)

    total_writes = len(ordered_data) + len(sector_trailers)
    write_count = 0

    for block in ordered_data:
        if on_progress:
            on_progress('erasing', write_count, total_writes)
        data = block0_data if block == 0 else zeros
        sec = _block_to_sector(block)
        ka = keys_a.get(sec, default_key_a)
        kb = keys_b.get(sec, default_key_b)

        written = False
        # Try Key A up to 3 times
        for _attempt in range(3):
            ret = executor.startPM3Task(
                'hf mf wrbl --blk %d -a -k %s -d %s --force' % (block, ka, data), 5888)
            wr_cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if 'isOk:01' in wr_cache or 'Write ( ok )' in wr_cache:
                written = True
                break
        # Fallback to Key B
        if not written:
            ret = executor.startPM3Task(
                'hf mf wrbl --blk %d -b -k %s -d %s --force' % (block, kb, data), 5888)
            wr_cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if 'isOk:01' in wr_cache or 'Write ( ok )' in wr_cache:
                written = True
        if not written:
            return 'error'
        write_count += 1

    # --- Phase 2: Trailer blocks (reverse order, key A×3 + key B fallback) ---
    # Trace: 63,59,55,...,7,3 each with A,A,A,B pattern
    sorted_trailers = sorted(sector_trailers, reverse=True)
    for block in sorted_trailers:
        if on_progress:
            on_progress('erasing', write_count, total_writes)
        sec = _block_to_sector(block)
        ka = keys_a.get(sec, default_key_a)
        kb = keys_b.get(sec, default_key_b)

        written = False
        for _attempt in range(3):
            ret = executor.startPM3Task(
                'hf mf wrbl --blk %d -a -k %s -d %s --force' % (block, ka, transport_trailer),
                5888)
            wr_cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if 'isOk:01' in wr_cache or 'Write ( ok )' in wr_cache:
                written = True
                break
        if not written:
            ret = executor.startPM3Task(
                'hf mf wrbl --blk %d -b -k %s -d %s --force' % (block, kb, transport_trailer),
                5888)
            wr_cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if 'isOk:01' in wr_cache or 'Write ( ok )' in wr_cache:
                written = True
        # Trailer write failures are non-fatal (card may have restricted access)
        write_count += 1

    return 'success'

# =====================================================================
# T5577
# =====================================================================

def erase_t5577():
    """Erase T5577 tag — fallback chain.

    Binary source: WipeTagActivity.wipe_t5577
    Trace: trace_erase_flow_20260330.txt
    Spec: docs/UI_Mapping/13_erase_tag/README.md lines 173-178

    Fallback chain:
        1. lf t55xx wipe (no password)
        2. lf t55xx detect (verify)
        3. lf t55xx wipe p 20206666 (DRM password)
        4. lf t55xx detect (verify)
        5. lf t55xx detect p 20206666
        6. lf t55xx chk (brute force)

    Returns:
        str: 'success' or 'failed'
    """
    import executor

    # Step 1: Wipe without password
    ret = executor.startPM3Task('lf t55xx wipe', 5000)
    if ret == -1:
        return 'failed'

    # Step 2: Verify with detect (timeout=10000, from trace)
    ret = executor.startPM3Task('lf t55xx detect', 10000)
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if 'Chip Type' in cache:
        return 'success'

    # Step 3: Try with DRM password 20206666
    executor.startPM3Task('lf t55xx wipe -p 20206666', 5000)
    ret = executor.startPM3Task('lf t55xx detect', 10000)
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if 'Chip Type' in cache:
        return 'success'

    # Step 4: Try detect with password (timeout=10000, from trace)
    ret = executor.startPM3Task('lf t55xx detect -p 20206666', 10000)
    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
    if 'Chip Type' in cache:
        return 'success'

    # Step 5: Password brute force (last resort)
    # Trace: lf t55xx chk f /tmp/.keys/t5577_tmp_keys (timeout=180000)
    # lft55xx.genKeyFile writes the 107 default T5577 keys (same set the
    # original factory firmware used — confirmed via real-device trace).
    # It returns the full path (ending in .dic so iceman's
    # loadFileDICTIONARY_safe finds it without auto-appending the suffix).
    key_file = '/tmp/.keys/t5577_tmp_keys.dic'
    try:
        import lft55xx as _lft55xx
        key_file = _lft55xx.genKeyFile(_lft55xx.DEFAULT_KEYS.split('\n'))
    except Exception:
        pass
    executor.startPM3Task('lf t55xx chk -f %s' % key_file, 180000)

    # All strategies failed
    return 'failed'
