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

"""scan — RFID tag scanning orchestrator.

Transliterated from scan.so (iCopy-X v1.0.90, Cython 0.29.21, ARM 32-bit).

Ground truth:
    Strings:    docs/v1090_strings/scan_strings.txt
    Traces:     docs/Real_Hardware_Intel/trace_scan_flow_20260331.txt
                docs/Real_Hardware_Intel/trace_lf_scan_flow_20260331.txt
    Spec:       docs/middleware-integration/3-scan_spec.md

Orchestrates multi-step RFID tag detection by delegating to leaf parser
modules (hf14ainfo, hfsearch, lfsearch, hffelica, lft55xx, lfem4x05)
and PM3 execution (executor).

Module-level constants:
    CODE_TIMEOUT = -1
    CODE_TAG_LOST = -2
    CODE_TAG_MULT = -3
    CODE_TAG_NO = -4
    CODE_TAG_TYPE_WRONG = -5

Module-level state:
    INFOS = None            # cached scan result
    INFOS_CACHE_ENABLE = True
"""

import threading
import traceback

# ---------------------------------------------------------------------------
# Constants (exactly as extracted from scan.so __pyx_int_neg_*)
# ---------------------------------------------------------------------------
CODE_TIMEOUT = -1
CODE_TAG_LOST = -2
CODE_TAG_MULT = -3
CODE_TAG_NO = -4
CODE_TAG_TYPE_WRONG = -5

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
INFOS = None
INFOS_CACHE_ENABLE = True

# ---------------------------------------------------------------------------
# Scan cache helpers
# ---------------------------------------------------------------------------
def setScanCache(infos):
    """Store scan result in module-level cache (INFOS global)."""
    global INFOS
    INFOS = infos

def getScanCache():
    """Return the cached scan result, or None."""
    return INFOS

def clearScanCahe():
    """Clear the scan cache.  Note: the typo is intentional (matches .so)."""
    global INFOS
    INFOS = None

def set_infos_cache(enable):
    """Enable or disable the INFOS cache."""
    global INFOS_CACHE_ENABLE
    INFOS_CACHE_ENABLE = enable

# ---------------------------------------------------------------------------
# Key-setting helpers (delegate to sub-modules)
# ---------------------------------------------------------------------------
def set_scan_t55xx_key(key):
    """Set the temporary T55xx key used during scanning.

    Delegates to lft55xx.set_key(key).
    """
    try:
        from . import lft55xx
        lft55xx.set_key(key)
    except ImportError:
        try:
            import lft55xx as _lft55xx
            _lft55xx.set_key(key)
        except Exception:
            pass

def set_scan_em4x05_key(key):
    """Set the temporary EM4x05 key used during scanning.

    Delegates to lfem4x05.set_key(key).
    """
    try:
        from . import lfem4x05
        lfem4x05.set_key(key)
    except ImportError:
        try:
            import lfem4x05 as _lfem4x05
            _lfem4x05.set_key(key)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Factory functions that create result dicts
# ---------------------------------------------------------------------------
def createExecTimeout(progress):
    """Create a result dict representing an execution timeout.

    Returns {'progress': progress, 'return': -1, 'found': False, 'type': -1}
    """
    return {'progress': progress, 'return': CODE_TIMEOUT, 'found': False, 'type': -1}

def createTagLost(progress):
    """Create a result dict representing a lost tag.

    Returns {'progress': progress, 'return': -2, 'found': False, 'type': -1}
    """
    return {'progress': progress, 'return': CODE_TAG_LOST, 'found': False, 'type': -1}

def createTagMulti(progress):
    """Create a result dict representing multiple tags detected.

    Note: found is True when multiple tags are present.

    Returns {'progress': progress, 'return': -3, 'found': True, 'type': -1}
    """
    return {'progress': progress, 'return': CODE_TAG_MULT, 'found': True, 'type': -1}

def createTagNoFound(progress):
    """Create a result dict representing no tag found.

    Returns {'progress': progress, 'return': -4, 'found': False, 'type': -1}
    """
    return {'progress': progress, 'return': CODE_TAG_NO, 'found': False, 'type': -1}

def createTagTypeWrong(progress):
    """Create a result dict representing a wrong tag type.

    Returns {'progress': progress, 'return': -5, 'found': False, 'type': -1}
    """
    return {'progress': progress, 'return': CODE_TAG_TYPE_WRONG, 'found': False, 'type': -1}

# ---------------------------------------------------------------------------
# Predicate helpers that inspect result dicts
# ---------------------------------------------------------------------------
def isTagFound(maps):
    """Return True if the result dict indicates a tag was found."""
    return maps['found']

def isTagLost(maps):
    """Return True if the result dict indicates the tag was lost."""
    return maps['return'] == CODE_TAG_LOST

def isTagMulti(maps):
    """Return True if the result dict indicates multiple tags."""
    return maps['return'] == CODE_TAG_MULT

def isTimeout(value):
    """Return True if the result dict indicates a timeout."""
    return value['return'] == CODE_TIMEOUT

def isTagTypeWrong(maps):
    """Return True if the result dict indicates wrong tag type."""
    return maps['return'] == CODE_TAG_TYPE_WRONG

def isCanNext(value):
    """Return True if scanning can proceed to the next step.

    Returns True when found is False AND the return code is NOT
    CODE_TIMEOUT (-1) and NOT CODE_TAG_LOST (-2).
    When found is True, always returns False (a tag was found,
    no need to continue scanning).
    """
    if value.get('found', False):
        return False
    ret = value['return']
    return ret != CODE_TIMEOUT and ret != CODE_TAG_LOST

# ---------------------------------------------------------------------------
# Low-level scan functions (each talks to PM3 via executor)
# ---------------------------------------------------------------------------
def scan_14a():
    """Scan for ISO 14443-A tags using 'hf 14a info'.

    Returns a result dict with progress=0.
    On timeout or no PM3: createExecTimeout(0)
    On no tag (PM3 responded): createTagNoFound(0)

    Special cases from spec:
      - hasMulti: return createTagMulti(0) — type=-1, found=True
      - isUL: run 'hf mfu info' to determine UL subtype
    """
    try:
        import executor
        import tagtypes
        ret = executor.startPM3Task('hf 14a info', 5000)
        if ret == -1:
            return createExecTimeout(0)
        import hf14ainfo
        info = hf14ainfo.parser()
        if info.get('found'):
            # Multiple tags detected — use factory function for proper type=-1
            if info.get('hasMulti'):
                return createTagMulti(0)

            # Ultralight/NTAG — need additional 'hf mfu info' to determine subtype
            # Spec section 9.3: hf 14a info → hf mfu info → TYPE field
            if info.get('isUL'):
                # Extract UID from hf 14a info BEFORE hf mfu info clobbers cache
                # Ground truth: original_current_ui scan_mf_ultralight shows
                # scan_cache = {found, isMFU, type, uid} with uid from hf14ainfo
                ul_uid = hf14ainfo.get_uid()

                ul_ret = executor.startPM3Task('hf mfu info', 8888)
                if ul_ret != -1:
                    # Determine UL subtype from TYPE field
                    # Priority order from hfmfuinfo_strings.txt
                    if executor.hasKeyword('NTAG 213'):
                        ul_type = tagtypes.NTAG213_144B
                    elif executor.hasKeyword('NTAG 215'):
                        ul_type = tagtypes.NTAG215_504B
                    elif executor.hasKeyword('NTAG 216'):
                        ul_type = tagtypes.NTAG216_888B
                    elif executor.hasKeyword('Ultralight C') or \
                         executor.hasKeyword('MF0ULC'):
                        ul_type = tagtypes.ULTRALIGHT_C
                    elif executor.hasKeyword('Ultralight EV1') or \
                         executor.hasKeyword('MF0UL1101'):
                        ul_type = tagtypes.ULTRALIGHT_EV1
                    else:
                        # Plain Ultralight or Unknown → default to ULTRALIGHT
                        ul_type = tagtypes.ULTRALIGHT

                    result = {
                        'found': True,
                        'type': ul_type,
                        'isMFU': True,
                    }
                    if ul_uid:
                        result['uid'] = ul_uid
                    return result
                else:
                    # hf mfu info failed — fall back to generic ULTRALIGHT
                    result = {
                        'found': True,
                        'type': tagtypes.ULTRALIGHT,
                        'isMFU': True,
                    }
                    if ul_uid:
                        result['uid'] = ul_uid
                    return result

            info['progress'] = 0
            info['return'] = info.get('type', -1)
            return info
        return createTagNoFound(0)
    except Exception:
        return createExecTimeout(0)

def scan_hfsea():
    """Run HF search using 'hf sea'.

    Returns a result dict with progress=2.
    On timeout or no PM3: createExecTimeout(2)
    On no tag (PM3 responded): createTagNoFound(2)

    Special cases:
      - isIclass: delegate to hficlass.parser() for subtype identification
      - isMifare: re-run hf14ainfo.parser() for MIFARE type classification
    """
    try:
        import executor
        ret = executor.startPM3Task('hf sea', 10000)
        if ret == -1:
            # PM3 error — treat as "no tag found" so pipeline continues
            # to LF scan. On real device, PM3 always responds to 'hf sea';
            # -1 only happens on TCP failure which is transient.
            return createTagNoFound(2)
        import hfsearch
        info = hfsearch.parser()
        if info.get('found'):
            # iCLASS detected — delegate to hficlass for subtype identification
            if info.get('isIclass'):
                try:
                    import hficlass
                    iclass_info = hficlass.parser()
                    if iclass_info.get('found'):
                        iclass_info['progress'] = 2
                        iclass_info['return'] = iclass_info.get('type', -1)
                        return iclass_info
                except ImportError:
                    pass
                # Fallback: return as generic iCLASS (type not determined)
                info['progress'] = 2
                info['return'] = -1
                return info

            # MIFARE detected via hf search — re-run hf 14a info for classification
            if info.get('isMifare'):
                r14a = scan_14a()
                if r14a.get('found'):
                    r14a['progress'] = 2
                    return r14a
                # Fallback
                info['progress'] = 2
                info['return'] = -1
                return info

            info['progress'] = 2
            info['return'] = info.get('type', -1)
            return info
        return createTagNoFound(2)
    except Exception:
        return createExecTimeout(2)

def scan_lfsea():
    """Run LF search using 'lf sea'.

    Returns a result dict with progress=1.
    On timeout or no PM3: createExecTimeout(1)

    Special case: isT55XX=True means "LF signal present but no known
    modulation" — this is NOT a final "found" result. Return TagNoFound
    so the pipeline proceeds to scan_t55xx() which handles T55XX detection.
    """
    try:
        import executor
        ret = executor.startPM3Task('lf sea', 10000)
        if ret == -1:
            return createExecTimeout(1)
        import lfsearch
        info = lfsearch.parser()
        if info.get('found'):
            # isT55XX means "no known tag but signal present" — not a real tag match
            # Let pipeline continue to scan_t55xx() which handles actual T55XX detection
            if info.get('isT55XX'):
                return createTagNoFound(1)
            info['progress'] = 1
            info['return'] = info.get('type', -1)
            return info
        return createTagNoFound(1)
    except Exception:
        return createExecTimeout(1)

def scan_t55xx():
    """Scan for T55xx tags.

    Delegates to lft55xx.detectT55XX() which sends 'lf t55xx detect'.
    Ground truth: detectT55XX returns integer (0=success, negative=failure).
    Parsed info dict is cached in lft55xx.DUMP_TEMP (lft55xx.py:351).

    Returns a result dict with progress=3.
    On timeout or no PM3: createExecTimeout(3)
    """
    try:
        import lft55xx
        ret = lft55xx.detectT55XX()
        if ret >= 0:
            # Detection succeeded — read cached info from DUMP_TEMP
            info = lft55xx.DUMP_TEMP
            if isinstance(info, dict) and info.get('found'):
                info['progress'] = 3
                info['return'] = info.get('type', 23)  # T55X7_ID = 23
                return info
        return createTagNoFound(3)
    except Exception:
        return createExecTimeout(3)

def scan_em4x05():
    """Scan for EM4x05 tags.

    Delegates to lfem4x05.infoAndDumpEM4x05ByKey().

    Returns a result dict with progress=4.
    """
    try:
        import lfem4x05
        info = lfem4x05.infoAndDumpEM4x05ByKey()
        if isinstance(info, dict) and info.get('found'):
            info['progress'] = 4
            info['return'] = info.get('type', 24)  # EM4305_ID = 24
            return info
        return createTagNoFound(4)
    except Exception:
        return createTagNoFound(4)

def scan_felica():
    """Scan for FeliCa tags using 'hf felica reader'.

    Returns a result dict with progress=5.
    On timeout or no PM3: createExecTimeout(5)
    Note: returns ExecTimeout (NOT TagNoFound) when no FeliCa found,
    since FeliCa is the terminal step.
    """
    try:
        import executor
        ret = executor.startPM3Task('hf felica reader', 10000)
        if ret == -1:
            return createExecTimeout(5)
        import hffelica
        info = hffelica.parser()
        if info.get('found'):
            info['progress'] = 5
            info['return'] = 21  # FELICA = 21
            info['type'] = 21
            return info
        return createExecTimeout(5)
    except Exception:
        return createExecTimeout(5)

def lf_wav_filter():
    """Analyze raw LF waveform to confirm T55XX-like signal presence.

    T55XX gatekeeper: saves PM3 graph buffer and checks waveform amplitude.

    Flow:
    1. Send 'data save f /tmp/lf_trace_tmp' (PM3 auto-appends .pm3)
    2. Read /tmp/lf_trace_tmp.pm3 directly (Linux) or via PM3 cat proxy (Windows)
    3. Parse integer samples from file (one per line)
    4. Compute amplitude: max(values) - min(values)
    5. Return amplitude >= 90 (threshold from __pyx_int_90)
    6. Cleanup: commons.delfile_on_icopy(file_path)

    Chinese label strings in binary (logging only):
        __pyx_kp_u__8 = '峰值最大值: ' (Peak Maximum Value)
        __pyx_kp_u__9 = '峰值最小值: ' (Peak Minimum Value)
    """
    import executor
    import platform
    import commons

    FILE_BASE = '/tmp/lf_trace_tmp'
    FILE_EXT = 'pm3'
    file_path = FILE_BASE + '.' + FILE_EXT

    try:
        # Step 1: Save PM3 graph buffer to temp file
        cmd = 'data save -f ' + FILE_BASE
        ret = executor.startPM3Task(cmd, 90)
        if ret == -1:
            return False

        # Step 2: Read the saved waveform data
        content = ''
        if platform.system() == 'Windows':
            executor.startPM3Plat('cat ' + FILE_BASE)
            content = executor.getPrintContent()
        else:
            try:
                with open(file_path) as fd:
                    content = fd.read()
            except Exception:
                commons.delfile_on_icopy(file_path)
                return False

        if not content:
            commons.delfile_on_icopy(file_path)
            return False

        # Step 3: Parse waveform data (one integer sample per line)
        lines = content.replace('\r', '').split('\n')
        values = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    values.append(int(line))
                except (ValueError, TypeError):
                    pass

        if not values:
            commons.delfile_on_icopy(file_path)
            return False

        # Step 4: Amplitude analysis
        max_val = max(values)
        min_val = min(values)
        amplitude = max_val - min_val
        has_signal = amplitude >= 90  # Exact threshold from binary: __pyx_int_90

        # Step 5: Cleanup
        commons.delfile_on_icopy(file_path)

        return has_signal

    except Exception:
        try:
            commons.delfile_on_icopy(file_path)
        except Exception:
            pass
        return False

# ---------------------------------------------------------------------------
# scanForType — module-level type-specific scan with listener callback
# ---------------------------------------------------------------------------
def scanForType(listener, typ):
    """Scan for a specific tag type and call listener with results.

    Dispatches to the appropriate scan sub-function based on the tag type ID,
    checks type match, and calls listener({'progress': 100, 'return': result}).
    """
    try:
        import tagtypes

        hf_14a_types = {
            tagtypes.M1_S70_4K_4B, tagtypes.M1_S50_1K_4B,
            tagtypes.M1_S70_4K_7B, tagtypes.M1_S50_1K_7B,
            tagtypes.M1_MINI, tagtypes.M1_PLUS_2K,
            tagtypes.M1_POSSIBLE_4B, tagtypes.M1_POSSIBLE_7B,
            tagtypes.ULTRALIGHT, tagtypes.ULTRALIGHT_C,
            tagtypes.ULTRALIGHT_EV1,
            tagtypes.NTAG213_144B, tagtypes.NTAG215_504B, tagtypes.NTAG216_888B,
            tagtypes.HF14A_OTHER,
            tagtypes.MIFARE_DESFIRE, tagtypes.TOPAZ,
        }

        lf_types = {
            tagtypes.EM410X_ID, tagtypes.HID_PROX_ID, tagtypes.INDALA_ID,
            tagtypes.AWID_ID, tagtypes.IO_PROX_ID, tagtypes.GPROX_II_ID,
            tagtypes.SECURAKEY_ID, tagtypes.VIKING_ID, tagtypes.PYRAMID_ID,
            tagtypes.FDXB_ID, tagtypes.GALLAGHER_ID, tagtypes.JABLOTRON_ID,
            tagtypes.KERI_ID, tagtypes.NEDAP_ID, tagtypes.NORALSY_ID,
            tagtypes.PAC_ID, tagtypes.PARADOX_ID, tagtypes.PRESCO_ID,
            tagtypes.VISA2000_ID, tagtypes.NEXWATCH_ID,
        }

        result = None

        if typ in hf_14a_types:
            result = scan_14a()
            if result and not result.get('found'):
                result = scan_hfsea()
        elif typ in lf_types:
            result = scan_lfsea()
        elif typ == tagtypes.T55X7_ID:
            result = scan_t55xx()
        elif typ == tagtypes.EM4305_ID:
            result = scan_em4x05()
        elif typ in {tagtypes.ICLASS_LEGACY, tagtypes.ICLASS_ELITE, tagtypes.ICLASS_SE}:
            result = scan_hfsea()
        elif typ in {tagtypes.ISO15693_ICODE, tagtypes.ISO15693_ST_SA}:
            result = scan_hfsea()
        elif typ == tagtypes.LEGIC_MIM256:
            result = scan_hfsea()
        elif typ == tagtypes.FELICA:
            result = scan_felica()
        elif typ == tagtypes.ISO14443B:
            result = scan_hfsea()
        elif typ == tagtypes.HITAG2_ID:
            result = scan_hfsea()
        else:
            result = scan_hfsea()

        if result is not None:
            if result.get('found') and result.get('type', -1) != typ:
                result = createTagTypeWrong(result.get('progress', 0))

            if listener:
                listener({'progress': 100, 'return': result})

    except Exception:
        if listener:
            listener({'progress': 100, 'return': createExecTimeout(0)})

# ---------------------------------------------------------------------------
# Scanner class
# ---------------------------------------------------------------------------
class Scanner:
    """Orchestrates multi-step tag scanning.

    Properties:
        call_progress: Callback for progress updates. Called with (progress, max_value) tuple.
        call_resulted: Callback for final results. Called with the result dict.
        call_exception: Callback for exceptions. Called with traceback string.
    """

    def __init__(self):
        self._call_progress = None
        self._call_resulted = None
        self._call_exception = None
        self._call_value_max = 100
        self._scan_lock = threading.RLock()
        self._scan_running = False
        self._stop_label = False

    # -- Properties (match the .so property descriptors) --

    @property
    def call_progress(self):
        return self._call_progress

    @call_progress.setter
    def call_progress(self, value):
        self._call_progress = value

    @property
    def call_resulted(self):
        return self._call_resulted

    @call_resulted.setter
    def call_resulted(self, value):
        self._call_resulted = value

    @property
    def call_exception(self):
        return self._call_exception

    @call_exception.setter
    def call_exception(self, value):
        self._call_exception = value

    # -- Internal callback dispatch --

    def _call_progress_method(self, progress):
        """Call the progress callback with (progress, _call_value_max)."""
        if self._call_progress is not None:
            self._call_progress((progress, self._call_value_max))

    def _call_resulted_method(self, resulted):
        """Call the result callback with the result dict."""
        if self._call_resulted is not None:
            self._call_resulted(resulted)

    def _call_exception_method(self):
        """Call the exception callback with the current traceback string."""
        if self._call_exception is not None:
            self._call_exception(traceback.format_exc())

    # -- State management --

    def _raise_on_multi_scan(self):
        """Raise if a scan is already running."""
        if self._scan_running:
            raise Exception("\u4e0d\u5141\u8bb8\u5bf9\u4e00\u4e2a\u8bbe\u5907\u540c\u65f6\u5f00\u542f\u591a\u6b21\u67e5\u8be2\u4efb\u52a1\u3002")

    def _set_run_label(self, value):
        """Set the running state.

        When value is True:  _scan_running = True,  _stop_label = False
        When value is False: _scan_running = False, _stop_label = False
        """
        with self._scan_lock:
            self._scan_running = value
            self._stop_label = False

    def _set_stop_label(self, value):
        """Set the stop label. Does NOT change _scan_running."""
        with self._scan_lock:
            self._stop_label = value

    def _is_can_next(self, value):
        """Check whether scanning can proceed to the next step.

        Returns False if _stop_label is True (scan_stop() called).
        Returns False if value['found'] is True (tag found, done).
        Returns False if value['return'] is CODE_TIMEOUT or CODE_TAG_LOST.
        Returns True otherwise.
        """
        if self._stop_label:
            return False
        if value.get('found', False):
            return False
        ret = value['return']
        return ret != CODE_TIMEOUT and ret != CODE_TAG_LOST

    # -- Public scan methods --

    def scan_all_synchronous(self):
        """Run a full scan (HF + LF), blocking.

        Pipeline order (spec section 6.5, verified from original_current_ui
        progress bar widths: 23%→33%→53%→67%→83%→90%):
            1. scan_14a    (progress=0)
            2. scan_hfsea  (progress=2)
            3. scan_lfsea  (progress=1)
            4. scan_t55xx  (progress=3)
            5. scan_em4x05 (progress=4)
            6. scan_felica (progress=5)

        Ground truth: original_current_ui scan_em410x shows LF tag found at
        53% progress (state 4), confirming order is 14a→hfsea→lfsea.

        Between each step, _is_can_next is checked.
        Results are delivered via call_resulted callback.
        """
        self._raise_on_multi_scan()
        self._set_run_label(True)
        try:
            result = None

            # Progress values chosen to match original scan.so behaviour.
            # Ground truth (original_current_ui captures):
            #   First scanning state: 23% fill (46px / 200px)
            #   After LF search:      53% fill (106px / 200px)
            # The callback fires BEFORE each scan step so the UI shows
            # a blue progress bar throughout the scanning phase.

            # Step 1: HF 14A (progress=0)
            self._call_progress_method(23)
            r = scan_14a()
            if r.get('found'):
                result = r
            elif not self._is_can_next(r):
                result = r
            else:
                # Step 2: LF search — real device traces show LF before HF
                # (trace_lf_scan_flow_20260331.txt: 14a → lf sea → hf sea)
                self._call_progress_method(33)
                r = scan_lfsea()
                if r.get('found'):
                    result = r
                elif not self._is_can_next(r):
                    result = r
                else:
                    # Step 3: HF search
                    self._call_progress_method(53)
                    r = scan_hfsea()
                    if r.get('found'):
                        result = r
                    elif not self._is_can_next(r):
                        result = r
                    else:
                        # Step 4: T55xx (progress=3)
                        self._call_progress_method(67)
                        r = scan_t55xx()
                        if r.get('found'):
                            result = r
                        elif not self._is_can_next(r):
                            result = r
                        else:
                            # Step 5: EM4x05 (progress=4)
                            self._call_progress_method(83)
                            r = scan_em4x05()
                            if r.get('found'):
                                result = r
                            elif not self._is_can_next(r):
                                result = r
                            else:
                                # Step 6: FeliCa — terminal (progress=5)
                                self._call_progress_method(90)
                                r = scan_felica()
                                result = r

            # Cache result if enabled and tag found
            if INFOS_CACHE_ENABLE and result and result.get('found'):
                setScanCache(result)

            # Signal completion
            self._call_progress_method(100)

            # Deliver result
            self._call_resulted_method(result)

        except Exception:
            self._call_exception_method()
        finally:
            self._set_stop_label(True)
            self._set_run_label(False)

    def scan_all_asynchronous(self):
        """Run a full scan (HF + LF) in a background daemon thread.

        Returns immediately. Results delivered via callbacks.
        """
        t = threading.Thread(target=self.scan_all_synchronous, daemon=True)
        t.start()

    def scan_type_synchronous(self, typ):
        """Scan for a specific tag type, blocking.

        Dispatches to the appropriate scan function based on typ.
        Results are delivered via call_resulted callback.
        """
        self._raise_on_multi_scan()
        self._set_run_label(True)
        try:
            import tagtypes
            result = None

            hf_14a_types = {
                tagtypes.M1_S70_4K_4B, tagtypes.M1_S50_1K_4B,
                tagtypes.M1_S70_4K_7B, tagtypes.M1_S50_1K_7B,
                tagtypes.M1_MINI, tagtypes.M1_PLUS_2K,
                tagtypes.M1_POSSIBLE_4B, tagtypes.M1_POSSIBLE_7B,
                tagtypes.ULTRALIGHT, tagtypes.ULTRALIGHT_C,
                tagtypes.ULTRALIGHT_EV1,
                tagtypes.NTAG213_144B, tagtypes.NTAG215_504B, tagtypes.NTAG216_888B,
                tagtypes.HF14A_OTHER,
                tagtypes.MIFARE_DESFIRE,
            }

            lf_types = {
                tagtypes.EM410X_ID, tagtypes.HID_PROX_ID, tagtypes.INDALA_ID,
                tagtypes.AWID_ID, tagtypes.IO_PROX_ID, tagtypes.GPROX_II_ID,
                tagtypes.SECURAKEY_ID, tagtypes.VIKING_ID, tagtypes.PYRAMID_ID,
                tagtypes.FDXB_ID, tagtypes.GALLAGHER_ID, tagtypes.JABLOTRON_ID,
                tagtypes.KERI_ID, tagtypes.NEDAP_ID, tagtypes.NORALSY_ID,
                tagtypes.PAC_ID, tagtypes.PARADOX_ID, tagtypes.PRESCO_ID,
                tagtypes.VISA2000_ID, tagtypes.NEXWATCH_ID,
            }

            if typ in hf_14a_types:
                self._call_progress_method(23)
                r = scan_14a()
                if r.get('found'):
                    result = r
                elif self._is_can_next(r):
                    self._call_progress_method(50)
                    r = scan_hfsea()
                    result = r
                else:
                    result = r

            elif typ in lf_types:
                self._call_progress_method(23)
                r = scan_lfsea()
                if r.get('found'):
                    result = r
                elif self._is_can_next(r):
                    self._call_progress_method(60)
                    r = scan_t55xx()
                    result = r
                else:
                    result = r

            elif typ == tagtypes.T55X7_ID:       # 23
                self._call_progress_method(23)
                result = scan_t55xx()

            elif typ == tagtypes.EM4305_ID:      # 24
                self._call_progress_method(23)
                result = scan_em4x05()

            elif typ in {tagtypes.ICLASS_LEGACY, tagtypes.ICLASS_ELITE, tagtypes.ICLASS_SE}:
                self._call_progress_method(23)
                result = scan_hfsea()            # 17, 18, 47

            elif typ in {tagtypes.ISO15693_ICODE, tagtypes.ISO15693_ST_SA}:
                self._call_progress_method(23)
                result = scan_hfsea()            # 19, 46

            elif typ == tagtypes.LEGIC_MIM256:   # 20
                self._call_progress_method(23)
                result = scan_hfsea()

            elif typ == tagtypes.FELICA:         # 21
                self._call_progress_method(23)
                result = scan_felica()

            elif typ == tagtypes.ISO14443B:      # 22
                self._call_progress_method(23)
                result = scan_hfsea()

            elif typ == tagtypes.HITAG2_ID:      # 38
                self._call_progress_method(23)
                result = scan_hfsea()

            else:
                result = None  # Unknown type

            # Type match check
            if result and result.get('found') and result.get('type', -1) != typ:
                result = createTagTypeWrong(result.get('progress', 0))

            # Cache if appropriate
            if INFOS_CACHE_ENABLE and result and result.get('found'):
                setScanCache(result)

            # Signal completion
            self._call_progress_method(100)

            # Deliver result
            self._call_resulted_method(result)

        except Exception:
            self._call_exception_method()
        finally:
            self._set_stop_label(True)
            self._set_run_label(False)

    def scan_type_asynchronous(self, typ):
        """Scan for a specific tag type in a background daemon thread.

        Returns immediately. Results delivered via callbacks.
        """
        t = threading.Thread(target=self.scan_type_synchronous, args=(typ,), daemon=True)
        t.start()

    def scan_stop(self):
        """Request scan stop. Sets _stop_label=True, checked by _is_can_next."""
        self._stop_label = True
