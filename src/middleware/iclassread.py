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

"""iclassread -- iCLASS dump reader.

This module shadows iclassread.so and handles the iCLASS read flow
using our hficlass.py middleware. The original .so has compatibility
issues when combined with our Python middleware modules.

    Archive: archive/lib_transliterated/iclassread.py

API matches original:
    read(infos) -> dict
    readFromKey(infos, key, typ) -> dict
    readLegacy(infos) -> dict
    readElite(infos) -> dict
"""

try:
    import executor
except ImportError:
    from . import executor

try:
    import appfiles
except ImportError:
    try:
        from . import appfiles
    except ImportError:
        appfiles = None

try:
    import hficlass
except ImportError:
    try:
        from . import hficlass
    except ImportError:
        hficlass = None

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        class tagtypes:
            ICLASS_LEGACY = 17
            ICLASS_ELITE = 18
            ICLASS_SE = 47

# ---------------------------------------------------------------------------
# Constants -- from binary strings extraction
# ---------------------------------------------------------------------------
TIMEOUT = 30000
_KW_DUMP_SUCCESS = 'saving dump file'

# iclassread module state -- read.so accesses these after read() returns
# to build the callback dict {'bundle': {'file': FILE_READ, 'key': KEY_READ}}
FILE_READ = ''
KEY_READ = ''


def readFromKey(infos, key, typ):
    """Read/dump iClass tag using a specific key.

    Sends 'hf iclass dump k <key> f <path>' (with ' e' for Elite).
    """
    if not key:
        return {'return': -1, 'file': '', 'key': '', 'typ': ''}

    # Create file path via appfiles
    file_path = ''
    if appfiles is not None:
        try:
            appfiles.switch_linux()
            csn = ''
            if isinstance(infos, dict):
                csn = infos.get('csn', '')
            file_path = appfiles.create_iclass(typ, csn)
            appfiles.switch_current()
        except Exception:
            file_path = '/tmp/iclass_dump.bin'
    else:
        file_path = '/tmp/iclass_dump.bin'

    # Build dump command
    cmd = 'hf iclass dump k %s' % key
    if file_path:
        cmd += ' f %s' % file_path
    if typ == 'Elite':
        cmd += ' e'

    ret = executor.startPM3Task(cmd, TIMEOUT)

    if ret == executor.CODE_PM3_TASK_ERROR:
        return {'return': -1, 'file': '', 'key': '', 'typ': ''}

    if executor.hasKeyword(_KW_DUMP_SUCCESS):
        # Store in module state for read.so to access
        global FILE_READ, KEY_READ
        FILE_READ = file_path
        KEY_READ = key
        return {
            'return': 0,
            'file': file_path,
            'key': key,
            'typ': typ,
        }

    return {'return': -1, 'file': '', 'key': '', 'typ': ''}


def readLegacy(infos):
    """Read iClass tag using Legacy key (no 'e' flag)."""
    if hficlass is None:
        return {'return': -1, 'file': '', 'key': '', 'typ': ''}

    key_result = hficlass.chkKeys_1(infos)
    if not key_result or 'key' not in key_result:
        return {'return': -1, 'file': '', 'key': '', 'typ': ''}

    key = key_result['key']
    return readFromKey(infos, key, 'Legacy')


def readElite(infos):
    """Read iClass tag using Elite key (with 'e' flag)."""
    if hficlass is None:
        return {'return': -1, 'file': '', 'key': '', 'typ': ''}

    key_result = hficlass.chkKeys_2(infos)
    if not key_result or 'key' not in key_result:
        return {'return': -1, 'file': '', 'key': '', 'typ': ''}

    key = key_result['key']
    return readFromKey(infos, key, 'Elite')


def read(*args, **kwargs):
    """Read/dump an iClass tag.

    Accepts variable arguments to handle different calling conventions
    from read.so (which may pass tag_type, tag_data, listener).

    Tries Legacy first, then Elite.
    """
    # Handle both read(infos) and read(tag_type, tag_data, listener) signatures
    if len(args) >= 2:
        # read.so calls with (tag_type, tag_data, listener)
        infos = args[1] if isinstance(args[1], dict) else {}
    elif len(args) == 1:
        infos = args[0] if isinstance(args[0], dict) else {}
    else:
        infos = {}

    # Try Legacy first
    result = readLegacy(infos)
    if result.get('return') == 0:
        # read.so::call_on_finish checks `ret == 1` for success.
        # Original iclassread.so returns 1 on success, -2 on failure.
        return 1

    # Try Elite
    result = readElite(infos)
    if result.get('return') == 0:
        return 1

    # Fallback: use hficlass.chkKeys which includes 'hf iclass chk' file-based search
    if hficlass is not None:
        key_result = hficlass.chkKeys(infos)
        if key_result and 'key' in key_result:
            key = key_result['key']
            typ = key_result.get('type', 'Elite')
            result = readFromKey(infos, key, typ)
            if result.get('return') == 0:
                return 1

    # Return -2 for read failures (maps to _showReadFailed / "Read Failed!" toast)
    # ret=-1 has special handling in activity_read.py for scan cache inspection
    return -2
