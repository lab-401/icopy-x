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

"""felicaread -- FeliCa Lite reader.

Reimplemented from felicaread.so (iCopy-X v1.0.90).

Ground truth:
    Strings:  docs/v1090_strings/felicaread_strings.txt
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
