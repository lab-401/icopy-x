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

"""commons -- Common utilities (byte/hex operations, file system helpers).
    Audit:    docs/ (lines 267-282)
"""

import os
import platform

PATH_UPAN = '/mnt/upan/'


def getFlashID():
    """Extract Flash ID from PM3 output (unused in write flow)."""
    return ''


def startPlatformCMD(cmd):
    """Execute a platform command."""
    try:
        import subprocess
        return subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
    except Exception:
        return ''


def mkdirs_on_icopy(path):
    """Create directory tree with permissions."""
    try:
        os.makedirs(path, mode=0o775, exist_ok=True)
    except OSError:
        os.system('sudo mkdir -p {} ; sudo chmod 775 {}'.format(path, path))


def mkfile_on_icopy(file):
    """Create a file with permissions."""
    try:
        d = os.path.dirname(file)
        if d:
            os.makedirs(d, mode=0o775, exist_ok=True)
        with open(file, 'a'):
            pass
        os.chmod(file, 0o775)
    except OSError:
        os.system('sudo touch {} ; sudo chmod 775 {}'.format(file, file))


def delfile_on_icopy(file):
    """Delete a file."""
    try:
        os.remove(file)
    except OSError:
        os.system('sudo rm -f {}'.format(file))


def recreate_on_icopy(file):
    """Delete and recreate a file."""
    delfile_on_icopy(file)
    mkfile_on_icopy(file)


def append_str_on_icopy(txt, file):
    """Append text to a file."""
    try:
        with open(file, 'a') as f:
            f.write(txt + '\n')
    except OSError:
        os.system('echo "{}" |sudo tee -a {}'.format(txt, file))
