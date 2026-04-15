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

"""hfmfuinfo -- MIFARE Ultralight info helper.
    Audit:    docs/
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
