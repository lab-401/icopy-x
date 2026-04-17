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

"""felicaread -- FeliCa Lite reader.

Reimplemented from felicaread.so (iCopy-X v1.0.90).

Post compat-flip (Phase 3) — iceman-native command form.

Ground truth:
    Strings:  docs/v1090_strings/felicaread_strings.txt
    Audit:    docs/V1090_MODULE_AUDIT.txt
    Source:   /tmp/rrg-pm3/client/src/cmdhffelica.c:5056 `CmdHFFelicaDumpLite`

Middleware flow:
    - Issue `hf felica litedump` (identical CLI on iceman and legacy; the
      dispatch table entry `{"litedump", ...}` is unchanged between forks).
    - Iceman prints a trace block via `print_hex_break`; legacy writes a
      dump file. This middleware only checks `startPM3Task` return code
      and reports the target path (file write itself happens inside PM3
      when legacy handler runs; iceman behaves differently — see matrix
      L390-406 for the trace-vs-file gap).
"""

import os

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import appfiles
except ImportError:
    try:
        from . import appfiles
    except ImportError:
        appfiles = None

CMD = 'hf felica litedump'
TIMEOUT = 5000


def read(infos):
    """Read FeliCa tag. PM3: hf felica litedump (timeout=5000)."""
    uid = infos.get('uid', infos.get('idm', 'UNKNOWN'))
    dump_dir = appfiles.PATH_DUMP_FELICA if appfiles else '/mnt/upan/dump/felica/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        pass

    n = 1
    while True:
        path = os.path.join(dump_dir, 'FeliCa_{}_{}.bin'.format(uid, n))
        if not os.path.exists(path):
            break
        n += 1
        if n > 999:
            break

    ret = executor.startPM3Task(CMD, TIMEOUT)
    if ret == -1:
        return {'return': -1, 'file': ''}

    return {'return': 0, 'file': path}
