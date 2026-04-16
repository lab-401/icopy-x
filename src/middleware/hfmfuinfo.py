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

"""hfmfuinfo -- MIFARE Ultralight info helper.

Reimplemented from hfmfuinfo.so (iCopy-X v1.0.90).

Ground truth:
    Strings:  docs/v1090_strings/hfmfuinfo_strings.txt
    Audit:    docs/V1090_MODULE_AUDIT.txt
"""

import re

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        tagtypes = None

CMD = 'hf mfu info'
TIMEOUT = 8888


def getUID():
    """Extract UID from hf mfu info output."""
    text = executor.CONTENT_OUT_IN__TXT_CACHE if executor else ''
    m = re.search(r'UID\s*:\s*([0-9A-Fa-f ]+)', text)
    if m:
        return m.group(1).replace(' ', '').upper()
    return ''


def parser():
    """Parse hf mfu info output to determine Ultralight subtype.

    Returns dict with: found, type, uid, pages, etc.
    """
    text = executor.CONTENT_OUT_IN__TXT_CACHE if executor else ''
    result = {'found': False, 'type': -1, 'uid': ''}

    uid = getUID()
    if uid:
        result['uid'] = uid
        result['found'] = True

    if 'NTAG213' in text:
        result['type'] = getattr(tagtypes, 'NTAG213_144B', 5)
    elif 'NTAG215' in text:
        result['type'] = getattr(tagtypes, 'NTAG215_504B', 6)
    elif 'NTAG216' in text:
        result['type'] = getattr(tagtypes, 'NTAG216_888B', 7)
    elif 'Ultralight C' in text or 'UL-C' in text:
        result['type'] = getattr(tagtypes, 'ULTRALIGHT_C', 3)
    elif 'Ultralight EV1' in text or 'UL EV1' in text:
        result['type'] = getattr(tagtypes, 'ULTRALIGHT_EV1', 4)
    elif 'Ultralight' in text:
        result['type'] = getattr(tagtypes, 'ULTRALIGHT', 2)

    return result
