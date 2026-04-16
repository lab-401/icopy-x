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

"""read -- Tag read dispatcher.

Reimplemented from read.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Decompiled:  decompiled/read_ghidra_raw.txt
    Strings:     docs/v1090_strings/read_strings.txt
    Audit:       docs/V1090_MODULE_AUDIT.txt (line 151)
    Spec:        docs/middleware-integration/5-read_spec.md

Architecture:
    Reader class dispatches to protocol-specific AbsReader subclasses
    based on tag type. Each reader sends PM3 commands, parses responses,
    saves dump files, and reports results via listener callback.

Import chain (from audit):
    appfiles, executor, felicaread, hf14aread, hf15read, hfmfkeys,
    hfmfread, hfmfuread, lfem4x05, lfread, lft55xx, os, platform,
    tagtypes, threading, traceback
"""

import os
import threading
import traceback

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


# ---------------------------------------------------------------------------
# Callback helpers (match .so API)
# ---------------------------------------------------------------------------
def callReadSuccess(listener, infos, bundle, is_force=False):
    if listener:
        listener({'success': True, 'tag_info': infos, 'force': is_force, 'bundle': bundle})


def callReadFailed(listener, infos, ret):
    if listener:
        listener({'success': False, 'tag_info': infos, 'return': ret})


def call_on_finish(ret, listener, infos, bundle, is_force=False):
    if ret == 1 or ret == 0:
        callReadSuccess(listener, infos, bundle, is_force)
    else:
        callReadFailed(listener, infos, ret)


# ---------------------------------------------------------------------------
# Protocol-specific reader implementations
# ---------------------------------------------------------------------------
def _read_mfc(infos, listener):
    """MIFARE Classic read: fchk → readAllSector → save dump."""
    import hfmfkeys
    import hfmfread
    import mifare as _mf

    typ = infos.get('type', 1)
    size = hfmfread.sizeGuess(typ)

    # Gen1a detection
    gen1a = hfmfread.readIfIsGen1a(infos)
    if gen1a:
        infos['gen1a'] = True
        # Gen1a: save via csave
        csave_size = '1' if size <= 1024 else '4'
        name = hfmfread.create_name_by_type(infos)
        import appfiles as _af
        dump_dir = _af.PATH_DUMP_M1 if _af else '/mnt/upan/dump/mf1/'
        os.makedirs(dump_dir, exist_ok=True)
        n = 1
        while True:
            path = os.path.join(dump_dir, '{}_{}'.format(name, n))
            if not os.path.exists(path + '.bin'):
                break
            n += 1
            if n > 999:
                break
        cmd = 'hf mf csave {} o {}'.format(csave_size, path)
        executor.startPM3Task(cmd, 30000)
        bin_path = path + '.bin'
        hfmfread.cacheFile(bin_path)
        return (1, bin_path)

    # Standard: key recovery then sector reading
    infos['gen1a'] = False
    ret = hfmfkeys.fchks(infos, size, with_call=True)
    if ret == -1:
        # fchk timed out — propagate failure
        return (-1, '')

    if not hfmfkeys.hasAllKeys(size):
        hfmfkeys.keys(size, infos, listener)
        if not hfmfkeys.hasAllKeys(size) and not hfmfkeys.getAnyKey():
            # Zero keys found — key recovery completely failed
            # Ground truth: activity_read.py:562-566 — ret_code -4 → WarningM1Activity (M1:Sniff)
            return (-4, '')

    data_list = hfmfread.readAllSector(size, infos, listener)

    if not data_list:
        # Total read failure — no blocks readable
        return (-2, '')

    eml_path = hfmfread.save_eml(infos, data_list)
    bin_path = hfmfread.save_bin(infos, data_list)

    if bin_path:
        return (1, bin_path)
    return (-1, '')


def _read_ultralight(infos, listener):
    """MIFARE Ultralight/NTAG read."""
    import hfmfuread
    result = hfmfuread.read(infos)
    ret = result.get('return', -1)
    file_path = result.get('file', '')
    return (0 if ret >= 0 else -1, file_path)


def _read_lf(infos, listener):
    """LF 125kHz read."""
    import lfread
    typ = infos.get('type', -1)
    read_fn = lfread.READ.get(typ)
    if read_fn:
        result = read_fn()
        if isinstance(result, dict):
            return (result.get('return', -1), result)
    return (-1, '')


def _read_iclass(infos, listener):
    """iCLASS read."""
    import iclassread
    result = iclassread.read(infos)
    # iclassread.read() returns int (1=success, -2=failure), not dict
    if isinstance(result, int):
        file_path = getattr(iclassread, 'FILE_READ', '') or ''
        key = getattr(iclassread, 'KEY_READ', '') or ''
        bundle = {'file': file_path, 'key': key} if file_path else ''
        return (0 if result >= 0 else -1, bundle)
    ret = result.get('return', -1)
    return (0 if ret >= 0 else -1, result)


def _read_iso15693(infos, listener):
    """ISO 15693 read."""
    import hf15read
    result = hf15read.read(infos)
    ret = result.get('return', -1)
    file_path = result.get('file', '')
    return (0 if ret >= 0 else -1, file_path)


def _read_hf14a(infos, listener):
    """Generic ISO14443A read."""
    import hf14aread
    result = hf14aread.read(infos)
    ret = result.get('return', -1)
    file_path = result.get('file', '')
    return (0 if ret >= 0 else -1, file_path)


def _read_legic(infos, listener):
    """LEGIC read."""
    import legicread
    result = legicread.read(infos)
    ret = result.get('return', -1)
    return (0 if ret >= 0 else -1, result.get('file', ''))


def _read_felica(infos, listener):
    """FeliCa read."""
    import felicaread
    result = felicaread.read(infos)
    ret = result.get('return', -1)
    return (0 if ret >= 0 else -1, result.get('file', ''))


# Type dispatch table
_MFC_TYPES = {0, 1, 25, 26, 41, 42, 43, 44}
_UL_TYPES = {2, 3, 4, 5, 6, 7}
_LF_TYPES = {8, 9, 10, 11, 12, 13, 14, 15, 16, 23, 24, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45}
_ICLASS_TYPES = {17, 18, 47}
_ISO15693_TYPES = {19, 46}
_LEGIC_TYPES = {20}
_FELICA_TYPES = {21}
_HF14A_TYPES = {40}


def _dispatch_read(typ, infos, listener):
    """Dispatch to protocol-specific reader."""
    if typ in _MFC_TYPES:
        return _read_mfc(infos, listener)
    if typ in _UL_TYPES:
        return _read_ultralight(infos, listener)
    if typ in _LF_TYPES:
        return _read_lf(infos, listener)
    if typ in _ICLASS_TYPES:
        return _read_iclass(infos, listener)
    if typ in _ISO15693_TYPES:
        return _read_iso15693(infos, listener)
    if typ in _LEGIC_TYPES:
        return _read_legic(infos, listener)
    if typ in _FELICA_TYPES:
        return _read_felica(infos, listener)
    if typ in _HF14A_TYPES:
        return _read_hf14a(infos, listener)
    return (-1, '')


# ---------------------------------------------------------------------------
# Reader class (matches read.so API)
# ---------------------------------------------------------------------------
class Reader:
    """Tag read orchestrator. Dispatches to protocol readers in a thread."""

    def __init__(self):
        self._call_reading = None
        self._call_exception = None
        self._reading = False
        self._stop_label = False
        self._thread = None

    @property
    def call_reading(self):
        return self._call_reading

    @call_reading.setter
    def call_reading(self, value):
        self._call_reading = value

    @property
    def call_exception(self):
        return self._call_exception

    @call_exception.setter
    def call_exception(self, value):
        self._call_exception = value

    def start(self, tag_type, tag_data):
        """Start reading in a background thread.

        Args:
            tag_type: int tag type ID
            tag_data: dict with 'infos' (scan cache) and optional 'force' flag
        """
        infos = tag_data.get('infos', tag_data) if isinstance(tag_data, dict) else {}
        is_force = tag_data.get('force', False) if isinstance(tag_data, dict) else False
        listener = self._call_reading

        self._reading = True
        self._stop_label = False

        def _run():
            try:
                ret, bundle = _dispatch_read(tag_type, infos, listener)
                call_on_finish(ret, listener, infos, bundle, is_force)
            except Exception:
                tb = traceback.format_exc()
                if self._call_exception:
                    try:
                        self._call_exception(tb)
                    except Exception:
                        pass
                callReadFailed(listener, infos, -1)
            finally:
                self._reading = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        """Request read stop."""
        self._stop_label = True
