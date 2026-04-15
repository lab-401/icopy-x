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

"""hf14aread -- Generic ISO 14443A reader.
For unknown/generic 14443A tags — saves infos to text file (no PM3 dump).

    Audit:    docs/
"""

import os
import json

try:
    import appfiles
except ImportError:
    try:
        from . import appfiles
    except ImportError:
        appfiles = None

FILE_READ = None


def read(infos):
    """Save 14443A tag info to text file.

    No PM3 dump command — just saves the scan cache (UID, SAK, ATQA) to a file.
    Returns: {'return': 0, 'file': path} or {'return': -1, 'file': ''}
    """
    global FILE_READ

    uid = infos.get('uid', 'UNKNOWN')
    dump_dir = appfiles.PATH_DUMP_HF14A if appfiles else '/mnt/upan/dump/hf14a/'
    try:
        os.makedirs(dump_dir, exist_ok=True)
    except OSError:
        pass

    n = 1
    while True:
        path = os.path.join(dump_dir, 'HF14A_{}_{}.txt'.format(uid, n))
        if not os.path.exists(path):
            break
        n += 1
        if n > 999:
            break

    try:
        with open(path, 'w') as f:
            f.write('UID: {}\n'.format(infos.get('uid', '')))
            f.write('SAK: {}\n'.format(infos.get('sak', '')))
            f.write('ATQA: {}\n'.format(infos.get('atqa', '')))
        FILE_READ = path
        return {'return': 0, 'file': path}
    except Exception:
        return {'return': -1, 'file': ''}
