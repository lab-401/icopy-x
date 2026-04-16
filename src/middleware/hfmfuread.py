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

"""hfmfuread -- MIFARE Ultralight / NTAG reader.

Reimplemented from hfmfuread.so (iCopy-X v1.0.90).

Ground truth:
    Strings:  docs/v1090_strings/hfmfuread_strings.txt
    Audit:    docs/V1090_MODULE_AUDIT.txt
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

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        tagtypes = None

FILE_MFU_READ = None

_TYPE_PREFIX = {
    2: 'M0-UL',
    3: 'M0-UL-C',
    4: 'M0-UL-EV1',
    5: 'NTAG213',
    6: 'NTAG215',
    7: 'NTAG216',
}


def createFileNamePreByType(typ):
    """Return filename prefix based on type ID."""
    return _TYPE_PREFIX.get(typ, 'Unknow')


def read(infos):
    """Read MIFARE Ultralight/NTAG tag.

    PM3: hf mfu dump f {path}  (timeout=30000)
    Returns: {'return': 0/1, 'file': path} on success, {'return': -1} on failure.
    """
    global FILE_MFU_READ

    typ = infos.get('type', 2)
    uid = infos.get('uid', 'UNKNOWN')
    prefix = createFileNamePreByType(typ)

    dump_dir = appfiles.PATH_DUMP_MFU if appfiles else '/mnt/upan/dump/mfu/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        pass

    n = 1
    while True:
        path = os.path.join(dump_dir, '{}_{}'.format(prefix, uid))
        full = '{}_{}'.format(path, n)
        if not os.path.exists(full + '.bin'):
            break
        n += 1
        if n > 999:
            break

    file_path = '{}_{}'.format(path, n)
    cmd = 'hf mfu dump -f {}'.format(file_path)
    ret = executor.startPM3Task(cmd, 30000)

    if ret == -1:
        return {'return': -1, 'file': ''}

    if executor.hasKeyword("Can't select card"):
        return {'return': -1, 'file': ''}

    bin_path = file_path + '.bin'
    if os.path.exists(bin_path):
        FILE_MFU_READ = bin_path
        return {'return': 0, 'file': bin_path}

    if executor.hasKeyword('Partial dump created'):
        FILE_MFU_READ = bin_path
        return {'return': 0, 'file': bin_path}

    return {'return': -1, 'file': ''}
