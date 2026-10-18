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
import re
import stat

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


# Both shipped clients write mfu_dump_t, not raw page-only dumps. See
# docs/ULTRALIGHT_DUMPS.md for source references and the factory display bug.
_HEADER_BYTES = 56
_MAX_DUMP_BYTES = _HEADER_BYTES + 256 * 4
_FULL_PAGES = {2: (16,), 3: (48,), 4: (20, 41), 5: (45,), 6: (135,), 7: (231,)}


def _validate_dump(path, infos, partial):
    """Validate a newly generated binary; never rewrite or pad its contents."""
    try:
        if not stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode):
            return None
        with open(path, 'rb') as stream:
            data = stream.read(_MAX_DUMP_BYTES + 1)
    except OSError:
        return None
    # Pages 0 and 1 are required to bind the saved UID to the scanned card.
    if not _HEADER_BYTES + 8 <= len(data) <= _MAX_DUMP_BYTES:
        return None
    pages = data[11] + 1
    if len(data) != _HEADER_BYTES + pages * 4:
        return None
    uid = (data[56:59] + data[60:64]).hex().upper()
    if uid != infos['uid'].upper():
        return None
    expected = _FULL_PAGES[infos['type']]
    if infos['type'] == 4:
        # GET_VERSION storage byte distinguishes the two supported EV1 sizes.
        # Zero/unknown versions occur on compatible cards; retain both sizes.
        expected = {0x0b: (20,), 0x0e: (41,)}.get(data[6], expected)
    if pages > max(expected):
        return None
    return dict(partial=bool(partial or pages not in expected), pages=pages)


def read(infos):
    """Save a verified Ultralight/NTAG dump, explicitly identifying partial data.

    A completed command or a partial-dump message alone is not a saved read.
    Invalid output stays on disk for diagnosis but is never cached for writing.
    """
    global FILE_MFU_READ
    FILE_MFU_READ = None
    failed = {'return': -1, 'file': ''}
    typ = infos.get('type', 2)
    uid = infos.get('uid', '')
    if typ not in _FULL_PAGES or not isinstance(uid, str) or not re.fullmatch(r'[0-9a-fA-F]{14}', uid):
        return failed
    infos = dict(infos, type=typ)
    prefix = createFileNamePreByType(typ)
    dump_dir = appfiles.PATH_DUMP_MFU if appfiles else '/mnt/upan/dump/mfu/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        return failed

    # Never reuse stale output, including orphaned JSON files or broken links.
    for n in range(1, 1000):
        file_path = os.path.join(dump_dir, '{}_{}_{}'.format(prefix, uid, n))
        if not any(os.path.lexists(file_path + ext) for ext in ('.bin', '.json')):
            break
    else:
        return failed
    ret = executor.startPM3Task('hf mfu dump -f {}'.format(file_path), 30000)
    if ret == -1 or executor.hasKeyword("Can't select card"):
        return failed
    bin_path = file_path + '.bin'
    details = _validate_dump(bin_path, infos, executor.hasKeyword('Partial dump created'))
    if details is None:
        return failed
    FILE_MFU_READ = bin_path
    return dict(details, **{'return': 0, 'file': bin_path})
