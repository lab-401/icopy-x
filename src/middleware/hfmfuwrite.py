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

"""hfmfuwrite -- MIFARE Ultralight / NTAG writer.

Reimplemented from hfmfuwrite.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
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

# Iceman-native keywords for `hf mfu restore`.
# Matrix: divergence_matrix.md L905-928 `hf mfu restore` +
# divergence_matrix_v2_changes.md C4 correction.
#
# Source-cite:
#   Iceman /tmp/rrg-pm3/client/src/cmdhfmfu.c:4218 — CmdHF14AMfURestore
#     emits `PrintAndLogEx(INFO, "Done!")` on success (exclamation mark
#     is part of the literal).
#   Iceman cmdhf14a.c reader helper -> "Can't select card" on
#     selection failure (identical across both firmwares per matrix).
#   "failed to write block" — iceman cmdhfmfu.c write-loop on per-
#     block failure.
# Legacy cmdhfmfu.c:2343 emits `"Finish restore"` with NO "Done" token —
# this middleware no longer matches legacy completion. Phase 4 adapter
# responsibility (see gap log P3.3 entry).
_KW_RESTORE_SUCCESS = r'Done!'
_KW_SELECT_FAIL = "Can't select card"
_KW_WRITE_FAIL = "failed to write block"

def write(infos, file):
    """Write MIFARE Ultralight/NTAG data to a tag.

    Flow (6-write_spec.md §5.4, iceman-native post P3.3 compat-flip):
        1. Build iceman command: `hf mfu restore -s -e -f <file>`
        2. Execute via startPM3Task with write_call callback
        3. Check iceman failure keywords (`Can't select card`,
           `failed to write block`)
        4. Check iceman completion sentinel `Done!` (cmdhfmfu.c:4218)
        5. Return 1 (success) or -1/-10 (failure)

    Args:
        infos: dict with 'type' key (int tag type ID)
        file:  str path to .bin dump file (full path, no modification)

    Returns:
        1   on success
        -1  on failure
        -10 on critical failure (card not selectable)
    """
    # Iceman CLI form: `hf mfu restore -s -e -f <file>`
    # Matrix L908: iceman/legacy accept same flag syntax; legacy trace
    # prefix `hf mfu restore s e f` is the older flag spelling (no dash
    # on legacy — handled transparently by iceman parser aliases).
    cmd = "hf mfu restore -s -e -f {}".format(file)

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

    # Iceman failure keywords (iceman-native literals).
    if executor.hasKeyword(_KW_SELECT_FAIL):
        return -10
    if executor.hasKeyword(_KW_WRITE_FAIL):
        return -1

    # Iceman success sentinel: `Done!` (cmdhfmfu.c:4218 literal).
    # If the card lost contact mid-restore, the response only has
    # "Loaded N bytes" / "Restoring ..." without `Done!` — silent fail.
    if not executor.hasKeyword(_KW_RESTORE_SUCCESS):
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
