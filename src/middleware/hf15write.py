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

"""hf15write -- ISO 15693 tag writer.

Reimplemented from hf15write.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Strings:     docs/v1090_strings/hf15write_strings.txt
    Spec:        docs/middleware-integration/6-write_spec.md (section 4)

API:
    write(infos, file) -> int
    verify(infos, file) -> int

Return codes:
    1   = success
    -1  = failure
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

def write(infos, file):
    """Write ISO 15693 data to a tag.

    Ground truth (hf15write_strings.txt line 475):
        The keyword for csetuid success is stored as:
            "setting new UID \\(ok\\)"
        with regex-escaped parentheses (hasKeyword uses re.search).

    Flow (6-write_spec.md §4.4):
        1. hf 15 restore f {path}.bin  (timeout=28888)
        2. Check: HAS "Write OK" AND HAS "done" AND NOT "restore failed" AND NOT "Too many retries"
        3. hf 15 csetuid {uid}  (timeout=5000)
        4. Check: HAS "setting new UID \\(ok\\)" AND NOT "can't read card UID"

    Returns:
        1  on success
        -1 on failure
    """
    # Step 1: Restore data blocks from dump file
    # Strings: __pyx_k_hf_15_restore_f_bin = "hf 15 restore f {}.bin"
    # The bundle 'file' may already include .bin extension (from dump path).
    # Only append .bin if not already present to avoid double extension.
    restore_path = file if file.endswith('.bin') else '{}.bin'.format(file)
    write_cmd = "hf 15 restore f {}".format(restore_path)
    executor.startPM3Task(write_cmd, 28888)

    # Step 2: Validate restore response
    # Strings: __pyx_k_restore_failed, __pyx_k_Too_many_retries,
    #          __pyx_k_Write_OK, __pyx_k_done
    if executor.hasKeyword("restore failed"):
        return -1
    if executor.hasKeyword("Too many retries"):
        return -1
    if not executor.hasKeyword("Write OK"):
        return -1
    if not executor.hasKeyword("done"):
        return -1

    # Step 3: Set UID on target card
    # Strings: __pyx_k_hf_15_csetuid = "hf 15 csetuid {}"
    uid = infos['uid']
    setuid_cmd = "hf 15 csetuid {}".format(uid)
    executor.startPM3Task(setuid_cmd, 5000)

    # Step 4: Validate csetuid response
    # Strings (line 475): "setting new UID \(ok\)" — regex-escaped parens
    # Strings: __pyx_k_can_t_read_card_UID = "can't read card UID"
    if executor.hasKeyword("can't read card UID"):
        return -1
    if not executor.hasKeyword(r"setting new UID \(ok\)"):
        return -1

    return 1

def verify(infos, file):
    """Verify ISO 15693 tag data after writing.

    Ground truth (hf15write_strings.txt):
        __pyx_n_s_scan_hfsea    = "scan_hfsea"
        __pyx_n_s_isTagFound    = "isTagFound"
        __pyx_n_s_set_infos_cache = "set_infos_cache"

    Flow (6-write_spec.md §4.5):
        1. scan.scan_hfsea()
        2. scan.isTagFound()
        3. Compare UID

    Returns:
        1  on success
        -1 on failure
    """
    # Step 1: Re-scan for tag
    infos_new = scan.scan_hfsea()

    # Step 2: Check tag found
    if not scan.isTagFound(infos_new):
        return -1

    # Step 3: Update scan cache
    scan.set_infos_cache(infos_new)

    # Step 4: Compare UID
    if infos_new.get('uid', '') != infos.get('uid', ''):
        return -1

    return 1
