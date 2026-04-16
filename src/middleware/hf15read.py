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

"""hf15read -- ISO 15693 reader.

Reimplemented from hf15read.so (iCopy-X v1.0.90).

Ground truth:
    Strings:  docs/v1090_strings/hf15read_strings.txt
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

CMD = 'hf 15 dump'
FILE_READ = None
TIMEOUT = 38000


def read(infos):
    """Read ISO 15693 tag.

    PM3: hf 15 dump f {path}  (timeout=38000)
    Returns: {'return': 0, 'file': path} or {'return': -1, 'file': ''}
    """
    global FILE_READ

    uid = infos.get('uid', 'UNKNOWN')
    dump_dir = appfiles.PATH_DUMP_ICODE if appfiles else '/mnt/upan/dump/icode/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        pass

    n = 1
    while True:
        path = os.path.join(dump_dir, 'ICODE_{}_{}'.format(uid, n))
        if not os.path.exists(path + '.bin'):
            break
        n += 1
        if n > 999:
            break

    cmd = 'hf 15 dump f {}'.format(path)
    ret = executor.startPM3Task(cmd, TIMEOUT)

    if ret == -1:
        return {'return': -1, 'file': ''}

    bin_path = path + '.bin'
    if os.path.exists(bin_path):
        FILE_READ = bin_path
        return {'return': 0, 'file': bin_path}

    FILE_READ = path
    return {'return': 0, 'file': path}
