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

"""write -- Tag write dispatcher.

Reimplemented from write.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Archive:    archive/lib_transliterated/write.py
    Spec:       docs/middleware-integration/6-write_spec.md (section 1)
    Strings:    docs/v1090_strings/write_strings.txt

API:
    write(listener, infos, bundle, run_on_subthread=True)
    verify(listener, infos, bundle, run_on_subthread=True)
    callReadFailed(listener, ret)
    callReadSuccess(listener)
    call_on_finish(ret, listener)
    call_on_state(state, listener)
    run_action(run, run_on_subthread)
"""

import threading

try:
    import tagtypes
except ImportError:
    try:
        from . import tagtypes
    except ImportError:
        tagtypes = None


# ---------------------------------------------------------------------------
# Callback helpers (match the .so exactly)
# ---------------------------------------------------------------------------
def callReadFailed(listener, ret):
    """Notify listener of a write/verify failure.

    Calls ``listener({'success': False, 'return': ret})``.
    """
    if listener:
        listener({'success': False, 'return': ret})


def callReadSuccess(listener):
    """Notify listener of a write/verify success.

    Calls ``listener({'success': True})``.
    """
    if listener:
        listener({'success': True})


def call_on_finish(ret, listener):
    """Dispatch based on return code.

    If ``ret == 1``, calls ``callReadSuccess(listener)``.
    Otherwise, calls ``callReadFailed(listener, ret)``.
    """
    if ret == 1:
        callReadSuccess(listener)
    else:
        callReadFailed(listener, ret)


def call_on_state(state, listener):
    """Notify listener of a state change.

    Calls ``listener({'state': state})``.
    """
    if listener:
        listener({'state': state})


# ---------------------------------------------------------------------------
# Thread helper
# ---------------------------------------------------------------------------
def run_action(run, run_on_subthread):
    """Run a callable, optionally in a background thread."""
    if run_on_subthread:
        t = threading.Thread(target=run, daemon=True)
        t.start()
    else:
        run()


# ---------------------------------------------------------------------------
# Tag type sets for dispatch
# ---------------------------------------------------------------------------
# MIFARE Classic types
_MF_CLASSIC_TYPES = {0, 1, 25, 26, 40, 41, 42, 43, 44}

# MIFARE Ultralight / NTAG types
_MF_ULTRALIGHT_TYPES = {2, 3, 4, 5, 6, 7}

# LF types (125 kHz)
_LF_TYPES = {8, 9, 10, 11, 12, 13, 14, 15, 16, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45}

# T55xx / EM4305 (LF but with dump files)
_LF_DUMP_TYPES = {23, 24}

# iClass types
_ICLASS_TYPES = {17, 18, 47}

# ISO 15693 types
_ISO15693_TYPES = {19, 46}

# Unsupported types (read-only or not implemented)
_UNSUPPORTED_TYPES = {20, 21, 22, 27, 38, 39}


# ---------------------------------------------------------------------------
# write -- main write dispatcher
# ---------------------------------------------------------------------------
def write(listener, infos, bundle, run_on_subthread=True):
    """Write data to a tag.

    Dispatches to the correct write sub-module based on ``infos['type']``.

    Args:
        listener: Callback receiving progress/result dicts.
                  write.so accesses listener.__self__ to call:
                    - playWriting()
                    - playVerifying()
                    - setBtnEnable(True/False)
        infos:    Dict with at least ``{'type': int}``.
        bundle:   Read result. For MFC: file path string.
                  For LF: dict with 'data'/'raw' keys.
                  For iCLASS: dict with dump data.
        run_on_subthread: If True (default), run in daemon thread.
    """
    typ = infos.get('type', -1) if isinstance(infos, dict) else -1

    def _run():
        # Small delay to let UI show "Writing..." progress before actual write starts.
        # Original .so has natural latency from Cython dispatch overhead.
        import time
        time.sleep(0.3)
        try:
            if typ in _MF_CLASSIC_TYPES:
                import hfmfwrite
                ret = hfmfwrite.write(listener, infos, bundle)
                if ret is not None and not isinstance(ret, dict):
                    call_on_finish(ret, listener)
            elif typ in _MF_ULTRALIGHT_TYPES:
                import hfmfuwrite
                file_path = bundle if isinstance(bundle, str) else bundle.get('file', '')
                ret = hfmfuwrite.write(infos, file_path)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _LF_TYPES:
                import lfwrite
                # Extract data and raw from infos (set by read flow)
                data = ''
                raw = ''
                if isinstance(infos, dict):
                    data_field = infos.get('data', '')
                    if isinstance(data_field, dict):
                        data = data_field.get('uid', data_field.get('data', ''))
                        raw = data_field.get('raw', '')
                    elif isinstance(data_field, str):
                        data = data_field
                    raw = raw or infos.get('raw', '')

                # PAR_CLONE_MAP types need human-readable data (e.g.,
                # FDX-B "0060-030207938416", EM410x "1234567890").
                # B0_WRITE_MAP and RAW_CLONE_MAP types need raw hex
                # bytes (e.g., AWID "01deb4ddede7e8b7edbdb7e1").
                #
                # HID Prox (9) and Indala (10) are exceptions within
                # PAR_CLONE_MAP: their cache `data` field holds a
                # human display string (e.g., 'FC,CN: 128,54641'),
                # while the actual clone arg is the raw hex payload
                # in `raw`.  Both writers expose multiple encoding
                # paths (formatted FC/CN vs raw hex), but per iceman
                # cmdlfindala.c:790 _RED_("Warning, encoding with
                # FC/CN doesn't always work") the raw form is the
                # universally-correct one for both protocols.
                # Source: cmdlfhid.c:400 + cmdlfindala.c:786 (iceman).
                _RAW_CLONE_PAR_TYPES = {9, 10}  # HID Prox, Indala
                if typ in _RAW_CLONE_PAR_TYPES:
                    raw_par = raw if raw else data
                elif typ in getattr(lfwrite, 'PAR_CLONE_MAP', {}):
                    raw_par = data if data else raw
                else:
                    raw_par = raw if raw else data
                ret = lfwrite.write(listener, typ, infos, raw_par)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _LF_DUMP_TYPES:
                import lfwrite
                file_path = ''
                if isinstance(bundle, str):
                    file_path = bundle
                elif isinstance(bundle, dict):
                    file_path = bundle.get('file', infos.get('file', ''))
                    if not file_path or not isinstance(file_path, str):
                        file_path = ''
                # For T55xx, try lft55xx.DUMP_FILE (set during read phase dump)
                if not file_path and typ == 23:
                    try:
                        import lft55xx as _lft
                        file_path = getattr(_lft, 'DUMP_FILE', '') or ''
                    except ImportError:
                        pass
                # For EM4305, try lfem4x05.DUMP_TEMP (set during read phase dump)
                if not file_path and typ == 24:
                    try:
                        import lfem4x05 as _lfem
                        file_path = getattr(_lfem, 'DUMP_TEMP', '') or ''
                    except ImportError:
                        pass
                if typ == 23:
                    ret = lfwrite.write_dump_t55xx(file_path)
                else:
                    ret = lfwrite.write_dump_em4x05(file_path)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _ICLASS_TYPES:
                import iclasswrite
                ret = iclasswrite.write(infos, bundle)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _ISO15693_TYPES:
                import hf15write
                file_path = bundle if isinstance(bundle, str) else bundle.get('file', '')
                ret = hf15write.write(infos, file_path)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _UNSUPPORTED_TYPES:
                callReadFailed(listener, -1)
            else:
                callReadFailed(listener, -1)
        except Exception as e:
            import traceback
            traceback.print_exc()
            callReadFailed(listener, -1)

    run_action(_run, run_on_subthread)


# ---------------------------------------------------------------------------
# verify -- main verify dispatcher
# ---------------------------------------------------------------------------
def verify(listener, infos, bundle, run_on_subthread=True):
    """Verify data on a tag after writing.

    Dispatches to the correct verify sub-module based on ``infos['type']``.
    """
    typ = infos.get('type', -1) if isinstance(infos, dict) else -1

    def _run():
        import time
        time.sleep(0.3)
        try:
            if typ in _MF_CLASSIC_TYPES:
                import hfmfwrite
                ret = hfmfwrite.verify(infos, bundle)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _MF_ULTRALIGHT_TYPES:
                import hfmfuwrite
                file_path = bundle if isinstance(bundle, str) else bundle.get('file', '')
                ret = hfmfuwrite.verify(infos, file_path)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _LF_TYPES or typ in _LF_DUMP_TYPES:
                import lfverify
                data = ''
                raw = ''
                # Ground truth: PM3 command log shows original lfverify reads
                # tag-specific data. The BUNDLE from the read phase has the
                # correct UID/data (from lfread), while the scan cache may
                # have empty data due to lf sea compact format parsing.
                # Try bundle first, fall back to infos (scan cache).
                for src in [bundle, infos]:
                    if not isinstance(src, dict):
                        continue
                    data_field = src.get('data', '')
                    if isinstance(data_field, dict):
                        d = data_field.get('uid', data_field.get('data', ''))
                        r = data_field.get('raw', '')
                    elif isinstance(data_field, str):
                        d = data_field
                        r = ''
                    else:
                        d = ''
                        r = ''
                    r = r or src.get('raw', '')
                    if d or r:
                        data = d
                        raw = r
                        break

                ret = lfverify.verify(typ, data, raw)
                call_on_finish(1 if ret == 0 else -1, listener)
            elif typ in _ICLASS_TYPES:
                import iclasswrite
                ret = iclasswrite.verify(infos, bundle)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _ISO15693_TYPES:
                import hf15write
                file_path = bundle if isinstance(bundle, str) else bundle.get('file', '')
                ret = hf15write.verify(infos, file_path)
                call_on_finish(ret if isinstance(ret, int) else -1, listener)
            elif typ in _UNSUPPORTED_TYPES:
                callReadFailed(listener, -1)
            else:
                callReadFailed(listener, -1)
        except Exception as e:
            import traceback
            traceback.print_exc()
            callReadFailed(listener, -1)

    run_action(_run, run_on_subthread)
