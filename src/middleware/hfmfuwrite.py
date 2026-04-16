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

"""hfmfuwrite -- MIFARE Ultralight / NTAG writer.

Reimplemented from hfmfuwrite.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Decompiled:  decompiled/hfmfuwrite_ghidra_raw.txt
    Strings:     docs/v1090_strings/hfmfuwrite_strings.txt
    Spec:        docs/middleware-integration/6-write_spec.md (section 5)

API:
    write(infos, file) -> int
    write_call(line) -> None
    verify(infos, file=None) -> int

Return codes:
    1   = success
    -1  = failure
    -10 = critical failure (card not selectable)
"""

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import scan
except ImportError:
    try:
        from . import scan
    except ImportError:
        scan = None

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        tagtypes = None


def write_call(line):
    """Callback for per-line PM3 output during restore.

    Ground truth (hfmfuwrite_strings.txt):
        __pyx_pw_10hfmfuwrite_1write_call
        __pyx_k_Can_t_select_card       = "Can't select card"
        __pyx_k_failed_to_write_block   = "failed to write block"

    Called by executor for each line of PM3 output during
    'hf mfu restore' execution. Checks for error keywords.
    """
    # This callback is registered with executor via add_task_call.
    # The original .so checks keywords in the line for real-time
    # error detection. In our executor, hasKeyword checks the full
    # cached response after command completes, so this callback
    # serves primarily as the progress hook for the executor's
    # listener mechanism.
    pass


def write(infos, file):
    """Write MIFARE Ultralight/NTAG data to a tag.

    Ground truth (hfmfuwrite_strings.txt):
        __pyx_kp_u_hf_mfu_restore_s_e_f   = "hf mfu restore s e f {}"
        __pyx_kp_u_Can_t_select_card       = "Can't select card"
        __pyx_kp_u_failed_to_write_block   = "failed to write block"
        __pyx_n_s_startPM3Task
        __pyx_n_s_hasKeyword
        __pyx_n_s_stopPM3Task

    Flow (6-write_spec.md §5.4):
        1. Build command: "hf mfu restore s e f {filepath}"
        2. Execute via startPM3Task with write_call callback
        3. Check for failure keywords
        4. Return 1 (success) or -1/-10 (failure)

    Args:
        infos: dict with 'type' key (int tag type ID)
        file:  str path to .bin dump file (full path, no modification)

    Returns:
        1   on success
        -1  on failure
        -10 on critical failure (card not selectable)
    """
    # Build PM3 command
    # Strings: __pyx_kp_u_hf_mfu_restore_s_e_f = "hf mfu restore s e f {}"
    cmd = "hf mfu restore s e f {}".format(file)

    # Execute with callback
    # Strings: __pyx_n_s_startPM3Task
    # Ground truth timeouts (from real device traces):
    #   UL plain: 10888  (trace_dump_files_20260403)
    #   UL-EV1:   16888  (trace_original_full_20260410)
    # Larger tags (NTAG213/215/216) scale with page count.
    typ = infos.get('type', 2) if isinstance(infos, dict) else 2
    try:
        typ = int(typ)
    except (ValueError, TypeError):
        typ = 2
    _MFU_TIMEOUTS = {
        2: 10888,   # ULTRALIGHT
        3: 10888,   # ULTRALIGHT_C
        4: 16888,   # ULTRALIGHT_EV1
        5: 30000,   # NTAG213_144B (45 pages)
        6: 60000,   # NTAG215_504B (135 pages)
        7: 120000,  # NTAG216_888B (231 pages)
    }
    timeout = _MFU_TIMEOUTS.get(typ, 30000)
    executor.startPM3Task(cmd, timeout, write_call)

    # Check for failure keywords
    # Strings: __pyx_kp_u_Can_t_select_card
    if executor.hasKeyword("Can't select card"):
        return -10

    # Strings: __pyx_kp_u_failed_to_write_block
    if executor.hasKeyword("failed to write block"):
        return -1

    # Iceman success indicator: "Done" appears after all blocks written.
    # If the card lost contact mid-restore, the response only has
    # "Loaded N bytes" without "Done" — that's a silent failure.
    if not executor.hasKeyword("Done"):
        return -1

    return 1


def verify(infos, file=None):
    """Verify MIFARE Ultralight/NTAG data after writing.

    Ground truth (hfmfuwrite_strings.txt):
        __pyx_n_s_scan_14a    = "scan_14a"
        __pyx_n_s_isTagFound  = "isTagFound"
        __pyx_n_s_stopPM3Task = "stopPM3Task"

    Flow (6-write_spec.md §5.5):
        1. scan.scan_14a() — re-scan for tag
        2. scan.isTagFound() — verify tag present
        3. Compare UID with original infos

    Args:
        infos: dict with 'uid' and 'type' keys
        file:  optional str path (not used for UID-only verify)

    Returns:
        1  on success
        -1 on failure
    """
    # Step 1: Re-scan for tag
    # Strings: __pyx_n_s_scan_14a
    new_infos = scan.scan_14a()

    # Step 2: Check tag found
    # Strings: __pyx_n_s_isTagFound
    if not scan.isTagFound(new_infos):
        return -1

    # Step 3: Compare UID
    # Strings: __pyx_n_u_uid, __pyx_n_u_type
    if new_infos.get('uid', '') != infos.get('uid', ''):
        return -1

    return 1
