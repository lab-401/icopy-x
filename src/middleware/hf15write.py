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

Post compat-flip (Phase 3) — iceman-native regex / keywords.

Ground truth:
    Strings:     docs/v1090_strings/hf15write_strings.txt
    Spec:        docs/middleware-integration/6-write_spec.md (section 4)

Iceman sentinel emissions (verified against /tmp/rrg-pm3/client/src/cmdhf15.c):
    hf 15 restore success: PrintAndLogEx(INFO, "Done!")        — L2818
    hf 15 restore failure: PrintAndLogEx(FAILED, "Too many retries ...") — L2803
    hf 15 csetuid success: PrintAndLogEx(SUCCESS, "Setting new UID ( ok )") — L2900
    hf 15 csetuid fail:    PrintAndLogEx(FAILED, "no tag found") — L2891/:2702

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

# ── Iceman-native sentinels (post compat-flip) ────────────────────────
# hf 15 restore  — cmdhf15.c:2818  `PrintAndLogEx(INFO, "Done!")`
# hf 15 restore  — cmdhf15.c:2803  `PrintAndLogEx(FAILED, "Too many retries ...")`
# hf 15 csetuid  — cmdhf15.c:2900  `PrintAndLogEx(SUCCESS, "Setting new UID ( ok )")`
# hf 15 csetuid  — cmdhf15.c:2891  `PrintAndLogEx(FAILED, "no tag found")`
_KW_RESTORE_SUCCESS = r"Done!"
_KW_RESTORE_TOO_MANY = r"Too many retries"
_KW_CSETUID_NO_TAG = r"no tag found"
_RE_CSETUID_OK = r"Setting new UID\s*\(\s*ok\s*\)"


def write(infos, file):
    """Write ISO 15693 data to a tag.

    Iceman-native flow (cmdhf15.c):
        1. hf 15 restore -f {path}.bin  (timeout=28888)
           SUCCESS sentinel: "Done!" (L2818)
           FAIL sentinel:    "Too many retries" (L2803)
                             "no tag found" (L2702, scan mode)
                             "Memory image empty" (L2730)
        2. hf 15 csetuid -u {uid}  (timeout=5000)
           SUCCESS sentinel: "Setting new UID ( ok )" (L2900)
           FAIL sentinel:    "Setting new UID ( fail )" (L2905)
                             "no tag found" (L2868/2891)

    Returns:
        1  on success
        -1 on failure
    """
    # Step 1: Restore data blocks from dump file
    # iceman CLIParser: -f / --file
    # The bundle 'file' may already include .bin extension (from dump path).
    # Only append .bin if not already present to avoid double extension.
    restore_path = file if file.endswith('.bin') else '{}.bin'.format(file)
    write_cmd = "hf 15 restore -f {}".format(restore_path)
    executor.startPM3Task(write_cmd, 28888)

    # Step 2: Validate restore response against iceman native emissions.
    # Any failure sentinel → -1. Otherwise success sentinel "Done!" required.
    if executor.hasKeyword(_KW_RESTORE_TOO_MANY):
        return -1
    if executor.hasKeyword(_KW_CSETUID_NO_TAG):
        return -1
    if not executor.hasKeyword(_KW_RESTORE_SUCCESS):
        return -1

    # Step 3: Set UID on target card (iceman CLIParser: -u)
    uid = infos['uid']
    setuid_cmd = "hf 15 csetuid -u {}".format(uid)
    executor.startPM3Task(setuid_cmd, 5000)

    # Step 4: Validate csetuid response against iceman emissions.
    if executor.hasKeyword(_KW_CSETUID_NO_TAG):
        return -1
    if not executor.hasKeyword(_RE_CSETUID_OK):
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
