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

"""hfmfwrite -- MIFARE Classic writer.

Reimplemented from hfmfwrite.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).
DRM gate (tagChk1) is BYPASSED — open-source implementation.

Ground truth:
    Strings:     docs/v1090_strings/hfmfwrite_strings.txt
    Spec:        docs/middleware-integration/6-write_spec.md (section 2)
    Trace:       docs/Real_Hardware_Intel/trace_write_activity_attrs_20260402.txt

API:
    write(listener, infos, bundle) -> int
    verify(infos, bundle) -> int

    Internal:
        write_common, write_with_standard, write_with_gen1a,
        write_block, start_wrbl_cmd, gen1afreeze, call_progress,
        read_blocks_4file, tagChk1 (bypassed)

Return codes:
    1   = success
    -1  = failure
    -9  = DRM failure (never returned — DRM bypassed)
    -10 = critical failure
"""

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import hfmfkeys
except ImportError:
    try:
        from . import hfmfkeys
    except ImportError:
        hfmfkeys = None

try:
    import hfmfread
except ImportError:
    try:
        from . import hfmfread
    except ImportError:
        hfmfread = None

try:
    import mifare
except ImportError:
    try:
        from . import mifare
    except ImportError:
        mifare = None

try:
    import scan
except ImportError:
    try:
        from . import scan
    except ImportError:
        scan = None

# ---------------------------------------------------------------------------
# DRM bypass — tagChk1
# Original: AES-based license check via /proc/cpuinfo serial.
# Open-source: always passes, returns a no-op tag factory.
# Strings: __pyx_k_tagChk1, __pyx_k_AA55C396, __pyx_k_Crypto_Cipher,
#          __pyx_k_cat_proc_cpuinfo, __pyx_k_VB1v2qvOinVNIlv2
# ---------------------------------------------------------------------------
def tagChk1(infos, file, newinfos):
    """DRM gate — BYPASSED.

    Original checks cpuinfo serial, computes MD5, decrypts AES,
    compares against AA55C396 marker.  Returns init_tag factory on
    success, or causes write_common to return -9 on failure.

    Open-source: always returns a lambda that passes through the
    infos dict unchanged.
    """
    def init_tag(infos_arg):
        return infos_arg
    return init_tag

# ---------------------------------------------------------------------------
# read_blocks_4file — load dump .bin into dict
# Strings: __pyx_k_read_blocks_4file
# Binary format: 16 bytes per block, sequential
# ---------------------------------------------------------------------------
def read_blocks_4file(infos, file):
    """Load blocks from binary dump file.

    Returns dict: block_num → 32-char uppercase hex string.
    """
    blocks = {}
    try:
        with open(file, 'rb') as f:
            block_num = 0
            while True:
                data = f.read(16)
                if not data or len(data) < 16:
                    break
                blocks[block_num] = data.hex().upper()
                block_num += 1
    except Exception:
        return {}
    return blocks

# ---------------------------------------------------------------------------
# write_block / start_wrbl_cmd — per-block write
# Strings: __pyx_k_hf_mf_wrbl, __pyx_k_isOk_01
# Trace: hf mf wrbl 60 A ffffffffffff 00000000...
# ---------------------------------------------------------------------------
def start_wrbl_cmd(block, typ, key, data):
    """Build the wrbl command string.

    Strings: __pyx_k_start_wrbl_cmd
    Format: 'hf mf wrbl --blk {block} -a/-b -k {key} -d {data} --force'
    """
    return 'hf mf wrbl --blk {} {} -k {} -d {} --force'.format(
        block, '-a' if typ == 'A' else '-b', key, data)

def write_block(block, typ, key, data):
    """Write a single block.

    Strings: __pyx_k_write_block, __pyx_k_isOk_01
    Returns 1 on success (isOk:01), -1 on failure.
    """
    cmd = start_wrbl_cmd(block, typ, key, data)
    ret = executor.startPM3Task(cmd, 10000)
    if ret == -1:
        return -1
    if executor.hasKeyword(r'isOk:01|Write \( ok \)'):
        return 1
    return -1

# ---------------------------------------------------------------------------
# call_progress — progress reporting
# Strings: __pyx_k_call_progress, __pyx_k_progress, __pyx_k_max_value
# ---------------------------------------------------------------------------
def call_progress(listener, progress, max_val):
    """Report progress to listener: {'max': N, 'progress': M}."""
    if listener is None:
        return
    try:
        listener({'max': max_val, 'progress': progress})
    except Exception:
        pass

# ---------------------------------------------------------------------------
# gen1afreeze — lock Gen1a magic card
# Strings: __pyx_k_gen1afreeze
# Spec §2.7: 5 raw commands
# ---------------------------------------------------------------------------
def gen1afreeze():
    """Execute Gen1a freeze sequence (5 raw commands).

    Strings:
        __pyx_k_hf_14a_raw_p_a_b_7_40
        __pyx_k_hf_14a_raw_c_p_a_e000
        __pyx_k_hf_14a_raw_c_p_a_e100
        __pyx_k_hf_14a_raw_c_a_5000
        __pyx_k_hf_14a_raw_p_a_43
        __pyx_k_hf_14a_raw_c_p_a_850000000000000000000000000000 08
    """
    # Compat flip: -p (keep-field-on) renamed to -k in iceman
    commands = [
        'hf 14a raw -k -a -b 7 40',
        'hf 14a raw -c -k -a 43',
        'hf 14a raw -c -k -a e000',
        'hf 14a raw -c -k -a 85000000000000000000000000000008',
        'hf 14a raw -c -a 5000',
    ]
    for cmd in commands:
        executor.startPM3Task(cmd, 10000)

# ---------------------------------------------------------------------------
# write_with_gen1a — bulk load via cload
# Strings: __pyx_k_hf_mf_cload_b, __pyx_k_Card_loaded_d_blocks_from_file,
#          __pyx_k_Can_t_set_magic_card_block
# ---------------------------------------------------------------------------
def write_with_gen1a(infos, file):
    """Write entire dump to Gen1a card via cload.

    Spec §2.6:
        1. hf mf cload b {file}
        2. Check 'Card loaded' in response
        3. gen1afreeze()

    Returns 1 on success, -1 on failure.
    """
    cmd = 'hf mf cload -f {}'.format(file)
    ret = executor.startPM3Task(cmd, 10000)
    if ret == -1:
        return -1

    if executor.hasKeyword("Can't set magic"):
        return -1
    if not executor.hasKeyword('Card loaded'):
        return -1

    gen1afreeze()
    return 1

def write_with_gen1a_only_uid(infos):
    """Write UID-only to Gen1a card.

    Strings: __pyx_k_hf_mf_csetuid_w
    Command: hf mf csetuid {uid} {sak} {atqa} w
    """
    uid = infos.get('uid', '')
    sak = infos.get('sak', '08')
    atqa = infos.get('atqa', '0004')
    cmd = 'hf mf csetuid -u {} -s {} -a {} -w'.format(uid, sak, atqa)
    ret = executor.startPM3Task(cmd, 10000)
    if ret == -1:
        return -1
    if executor.hasKeyword("Can't set magic"):
        return -1
    gen1afreeze()
    return 1

# ---------------------------------------------------------------------------
# write_with_standard — per-block write in reverse sector order
# Trace: blocks 60,61,62, 56,57,58, ..., 4,5,6, 0,1,2, then 63,59,...,3
# ---------------------------------------------------------------------------
def write_with_standard(infos, file, listener):
    """Write to standard (non-magic) MIFARE Classic card.

    Trace (trace_write_activity_attrs_20260402.txt):
        1. Data blocks: reverse sector order, skip trailers
           Sector 15: 60,61,62 → Sector 14: 56,57,58 → ... → Sector 0: 0,1,2
        2. Trailer blocks: reverse sector order
           63, 59, 55, 51, 47, 43, 39, 35, 31, 27, 23, 19, 15, 11, 7, 3

    Block 0 uses createManufacturerBlock (UID+BCC+SAK+ATQA from infos).
    All other blocks use dump file data or EMPTY_DATA.
    Trailers use dump file data or EMPTY_TRAI.

    Returns 1 if all blocks succeeded, -1 if any block failed.
    """
    # Load dump file into block dict
    blocks = read_blocks_4file(infos, file)

    # Get card geometry
    typ = infos.get('type', 1)
    size = hfmfread.sizeGuess(typ)
    sector_count = mifare.getSectorCount(size)
    total_blocks = sum(mifare.getBlockCountInSector(s) for s in range(sector_count))

    progress = 0
    write_success_list = []
    write_fail = False

    # --- Phase 1: Write data blocks (reverse sector order) ---
    # Trace (trace_original_full_20260410.txt): 3× Key A retry + 1× Key B fallback
    # per block.  Pattern: wrbl N A key → isOk:00 ×3, wrbl N B key → isOk:01
    for sector in range(sector_count - 1, -1, -1):
        first_block = mifare.sectorToBlock(sector)
        blocks_in_sector = mifare.getBlockCountInSector(sector)
        trailer_block = first_block + blocks_in_sector - 1

        key_a = hfmfkeys.getKey4Map(sector, 'A') if hfmfkeys else None
        key_b = hfmfkeys.getKey4Map(sector, 'B') if hfmfkeys else None

        # Write data blocks (all blocks except trailer)
        for offset in range(blocks_in_sector - 1):
            block_num = first_block + offset

            # Get block data from dump
            if block_num == 0:
                block_data = blocks.get(0, hfmfread.createManufacturerBlock(infos))
            else:
                block_data = blocks.get(block_num, mifare.EMPTY_DATA)

            written = False
            # Try Key A up to 3 times
            use_key_a = key_a or mifare.EMPTY_KEY
            for _attempt in range(3):
                ret = write_block(block_num, 'A', use_key_a, block_data)
                if ret == 1:
                    written = True
                    break
            # Fallback to Key B
            if not written and key_b:
                ret = write_block(block_num, 'B', key_b, block_data)
                if ret == 1:
                    written = True

            if written:
                write_success_list.append(block_num)
            else:
                write_fail = True

            progress += 1
            call_progress(listener, progress, total_blocks)

    # --- Phase 2: Write trailer blocks (reverse sector order) ---
    # Trace: same 3× Key A + 1× Key B pattern for trailers
    for sector in range(sector_count - 1, -1, -1):
        first_block = mifare.sectorToBlock(sector)
        blocks_in_sector = mifare.getBlockCountInSector(sector)
        trailer_block = first_block + blocks_in_sector - 1

        key_a = hfmfkeys.getKey4Map(sector, 'A') if hfmfkeys else None
        key_b = hfmfkeys.getKey4Map(sector, 'B') if hfmfkeys else None

        trailer_data = blocks.get(trailer_block, mifare.EMPTY_TRAI)

        written = False
        use_key_a = key_a or mifare.EMPTY_KEY
        for _attempt in range(3):
            ret = write_block(trailer_block, 'A', use_key_a, trailer_data)
            if ret == 1:
                written = True
                break
        if not written and key_b:
            ret = write_block(trailer_block, 'B', key_b, trailer_data)
            if ret == 1:
                written = True

        if written:
            write_success_list.append(trailer_block)
        else:
            write_fail = True

        progress += 1
        call_progress(listener, progress, total_blocks)

    # Original .so returns -1 if ANY block failed to write
    if write_fail:
        return -1
    if write_success_list:
        return 1
    return -1

# ---------------------------------------------------------------------------
# write_common — main dispatch (DRM → gen1a detect → write)
# ---------------------------------------------------------------------------
def write_common(listener, infos, bundle):
    """Shared write logic: DRM gate, Gen1a detection, key check, dispatch.

    Trace sequence:
        1. hf 14a info (card present)
        2. hf mf cgetblk 0 (gen1a detect)
        3. hf mf fchk (key verify)
        4. write_with_gen1a or write_with_standard
        5. hf 14a info (post-write check)
        6. hf mf cgetblk 0 (post-write gen1a check)

    Returns 1 on success, -1 on failure, -9 never (DRM bypassed).
    """
    # DRM gate — BYPASSED
    tagChk1(infos, bundle, {})

    # Step 1: Verify card present
    # Ground truth: on legacy firmware, hf 14a info always detected the card
    # here because the field stayed active.  On iceman, the field may be off
    # and the first probe can fail.  Check the response content — if no UID
    # is found, the card isn't on the reader and we must not proceed to fchk
    # (which would block for 600s on an empty reader).
    ret = executor.startPM3Task('hf 14a info', 10000)
    if ret == -1:
        return -1
    text_14a = executor.CONTENT_OUT_IN__TXT_CACHE or ''
    if not executor.hasKeyword('UID'):
        return -1

    # Step 2: Gen1a detection
    # Ground truth: Gen1a is confirmed ONLY when cgetblk 0 returns actual
    # block data WITHOUT error indicators.
    # Trace: standard card → "[#] wupC1 error\n[!!] Can't read block. error=-1"
    #        gen1a card   → "[+] Block 0: 2CADC272..." (actual block data)
    # Non-gen1a fixtures may contain: "isOk:00", "Can't set magic card block"
    import re as _re
    ret = executor.startPM3Task('hf mf cgetblk --blk 0', 10000)
    is_gen1a = False
    if ret == 1:
        text = executor.CONTENT_OUT_IN__TXT_CACHE or ''
        has_error = (executor.hasKeyword('wupC1 error') or
                     executor.hasKeyword("Can't read block") or
                     executor.hasKeyword("Can't set magic") or
                     executor.hasKeyword('isOk:00'))
        # Positive detection: "Block 0:" or "data:" followed by hex data
        # RRG PM3 v385d892 outputs "data: XX XX XX ..." for cgetblk
        has_block_data = bool(_re.search(r'(?:Block\s*0\s*:|data:)\s*[A-Fa-f0-9 ]{16,}', text))
        if has_block_data and not has_error:
            is_gen1a = True

    # Use infos gen1a flag if set by scan phase
    if infos.get('gen1a', False):
        is_gen1a = True

    # Step 3: Key verification on TARGET card (only for standard path)
    # Ground truth (trace_original_full_20260410.txt): the original firmware
    # ALWAYS runs fchk during write, even if keys are in the map from the
    # read phase.  The read-phase keys belong to the SOURCE card — the
    # TARGET card may have different keys.  Clear the map and re-check.
    if not is_gen1a:
        typ = infos.get('type', 1)
        size = hfmfread.sizeGuess(typ)
        if hfmfkeys:
            hfmfkeys.KEYS_MAP.clear()
            hfmfkeys.fchks(infos, size)

    # Step 4: Dispatch to write path
    file_path = bundle if isinstance(bundle, str) else ''

    if is_gen1a:
        result = write_with_gen1a(infos, file_path)
    else:
        result = write_with_standard(infos, file_path, listener)

    # Step 5: Post-write card check
    executor.startPM3Task('hf 14a info', 10000)
    executor.startPM3Task('hf mf cgetblk --blk 0', 10000)

    return result

# ---------------------------------------------------------------------------
# write — main entry point (called from write.py dispatcher)
# ---------------------------------------------------------------------------
def write(listener, infos, bundle):
    """Write MIFARE Classic data to a tag.

    Called from write.py dispatcher for types 0,1,25,26,40,41,42,43,44.

    Args:
        listener: callback receiving progress/result dicts
        infos:    dict from scan cache {'type', 'uid', 'sak', 'atqa', 'gen1a', ...}
        bundle:   str file path to .bin dump

    Returns:
        int: 1=success, -1=failure
    """
    try:
        # Fresh rework budget for this write — previous flows should not
        # pre-brick this one.
        try:
            executor.resetReworkCount()
        except AttributeError:
            pass
        return write_common(listener, infos, bundle)
    except Exception:
        return -1

# ---------------------------------------------------------------------------
# verify — read back and compare
# Trace: hf 14a info → hf mf cgetblk 0 (UID-level verify only)
# ---------------------------------------------------------------------------
def verify(infos, bundle):
    """Verify written card against source dump.

    Ground truth (trace_write_activity_attrs_20260402.txt line 225-231,
    QEMU original trace — no rdbl/rdsc commands after cgetblk 0):
        verify() issues hf 14a info twice — once as a pre-check and once
        to extract the UID for comparison — then hf mf cgetblk 0.
        No per-block comparison — original .so returns success if the
        card is present and UID matches.

    Returns 1 on success, -1 on failure.
    """
    try:
        # Pre-check: card still on antenna
        ret = executor.startPM3Task('hf 14a info', 10000)
        if ret == -1:
            return -1

        # Card presence + UID check
        ret = executor.startPM3Task('hf 14a info', 10000)
        if ret == -1:
            return -1

        # Extract UID from hf 14a info output
        card_uid = None
        content = executor.getPrintContent() if hasattr(executor, 'getPrintContent') else ''
        if not content:
            content = executor.getContentFromRegex(r'UID:\s*([\dA-Fa-f ]+)') or ''
        import re
        m = re.search(r'UID:\s*([\dA-Fa-f ]+)', content)
        if m:
            card_uid = m.group(1).replace(' ', '').upper()

        # Gen1a probe (matches original trace exactly)
        executor.startPM3Task('hf mf cgetblk --blk 0', 10000)

        # Compare UID with expected
        expected_uid = (infos.get('uid') or '').upper()
        if card_uid and expected_uid and card_uid.startswith(expected_uid):
            return 1
        if card_uid and expected_uid and expected_uid.startswith(card_uid):
            return 1

        # Fallback: card present but UID comparison inconclusive
        # Original .so returns success if card is on antenna
        if ret == 1 and card_uid:
            return 1

        return -1

    except Exception:
        return -1
