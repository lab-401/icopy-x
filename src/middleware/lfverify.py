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

"""lfverify -- LF write verification.

Reimplemented from lfverify.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Archive:    archive/lib_transliterated/lfverify.py
    Spec:       docs/middleware-integration/6-write_spec.md
    Strings:    docs/v1090_strings/lfverify_strings.txt

API:
    verify(typ, uid_par, raw_par) -> int
    verify_t55xx(file) -> int
    verify_em4x05(file) -> int

Return values:
    0   = verification passed
    -10 = verification failed
"""

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
    import lfsearch
except ImportError:
    try:
        from . import lfsearch
    except ImportError:
        lfsearch = None

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        class tagtypes:
            EM4305_ID = 24
            T55X7_ID = 23

# ---------------------------------------------------------------------------
# Verification return codes
# ---------------------------------------------------------------------------
VERIFY_OK = 0
VERIFY_FAIL = -10


def verify_t55xx(file):
    """Verify a T55xx tag against a dump file.

    Detects tag, reads blocks as text, compares with file.
    """
    if lft55xx is None:
        return VERIFY_FAIL

    try:
        detect_ret = lft55xx.detectT55XX()
        if detect_ret < 0:
            return VERIFY_FAIL

        info = lft55xx.DUMP_TEMP
        key = None
        if isinstance(info, dict):
            key = info.get('key', '') or None

        dump_text = lft55xx.dumpT55XX_Text(key)
        if not dump_text:
            return VERIFY_FAIL

        try:
            with open(file, 'r') as f:
                file_text = f.read()
        except Exception:
            return VERIFY_FAIL

        if dump_text.strip() == file_text.strip():
            return VERIFY_OK
        return VERIFY_FAIL

    except Exception:
        return VERIFY_FAIL


def verify_em4x05(file):
    """Verify an EM4x05 tag against a dump file.

    Ground truth: lfverify_strings.txt references verify4x05, readBlocks,
    data_hex, data2_hex, hex, rb, upper — reads blocks from tag, reads
    expected from binary dump file, compares hex-uppercased block data.
    """
    if lfem4x05 is None:
        return VERIFY_FAIL

    try:
        # Read blocks from tag
        blocks = lfem4x05.readBlocks()
        if not blocks:
            return VERIFY_FAIL

        # Read expected data from binary dump file
        import re as _re
        expected_blocks = []
        try:
            paths = [file]
            if not file.endswith('.bin'):
                paths.append(file + '.bin')
            for fpath in paths:
                try:
                    with open(fpath, 'rb') as f:
                        raw = f.read()
                    for i in range(0, len(raw), 4):
                        block_hex = raw[i:i + 4].hex().upper()
                        expected_blocks.append(block_hex)
                    break
                except FileNotFoundError:
                    continue
        except Exception:
            return VERIFY_FAIL

        if not expected_blocks:
            return VERIFY_FAIL

        # Compare: extract hex data from each block's PM3 output
        for i in range(min(len(expected_blocks), len(blocks))):
            block_content = blocks[i] if blocks[i] else ''
            # Extract hex data from PM3 lf em 4x05_read output
            m = _re.search(r'\b([A-Fa-f0-9]{8})\b', block_content)
            if m:
                data_hex = m.group(1).upper()
                if data_hex != expected_blocks[i]:
                    return VERIFY_FAIL

        return VERIFY_OK

    except Exception:
        return VERIFY_FAIL


def verify(typ, uid_par, raw_par):
    """Verify a written LF tag by reading it back.

    For T55XX (23) and EM4305 (24), uses dump file verification.
    For clone types: scan_lfsea() + isTagFound() for tag presence, then
    lfread.READ[typ]() for tag-specific data, compare with uid_par/raw_par.

    Ground truth:
        lfverify_strings.txt: scan_lfsea, isTagFound, lfread, uid_e, raw_e, upper
        PM3 command log (original_current_ui write_lf_em410x_verify_fail):
            Each verify does: lf sea → lf em 410x_read → compare
    """
    if typ == getattr(tagtypes, 'T55X7_ID', 23):
        return verify_t55xx(raw_par)

    if typ == getattr(tagtypes, 'EM4305_ID', 24):
        return verify_em4x05(raw_par)

    # Step 1: scan_lfsea — check tag presence
    try:
        import scan as _scan
    except ImportError:
        try:
            from . import scan as _scan
        except ImportError:
            _scan = None

    if _scan is not None:
        result = _scan.scan_lfsea()
        if not _scan.isTagFound(result):
            return VERIFY_FAIL
    else:
        ret = executor.startPM3Task('lf sea', 10000)
        if ret == -1:
            return VERIFY_FAIL
        if lfsearch is None:
            return VERIFY_FAIL
        result = lfsearch.parser()
        if not result.get('found', False):
            return VERIFY_FAIL

    # Step 2: tag-specific read via lfread to get actual data from tag
    found_data = ''
    found_raw = ''
    try:
        import lfread as _lfread
    except ImportError:
        try:
            from . import lfread as _lfread
        except ImportError:
            _lfread = None

    if _lfread is not None and hasattr(_lfread, 'READ'):
        read_fn = _lfread.READ.get(typ)
        if read_fn is not None:
            try:
                read_result = read_fn()
                if isinstance(read_result, dict) and read_result.get('return', -1) == 1:
                    found_data = read_result.get('data', '') or ''
                    found_raw = read_result.get('raw', '') or ''
            except Exception:
                pass

    # If lfread didn't produce data, fall back to scan result
    if not found_data and not found_raw:
        found_data = result.get('data', '') if isinstance(result, dict) else ''
        found_raw = result.get('raw', '') if isinstance(result, dict) else ''

    # Step 3: compare with expected values (uid_par/raw_par from bundle)
    uid_e = str(uid_par).upper() if uid_par else ''
    raw_e = str(raw_par).upper() if raw_par else ''
    data_hex = str(found_data).upper() if found_data else ''
    raw_hex = str(found_raw).upper() if found_raw else ''

    if uid_e and data_hex:
        return VERIFY_OK if uid_e == data_hex else VERIFY_FAIL
    if raw_e and raw_hex:
        return VERIFY_OK if raw_e == raw_hex else VERIFY_FAIL

    # No data to compare — tag presence is sufficient
    return VERIFY_OK
