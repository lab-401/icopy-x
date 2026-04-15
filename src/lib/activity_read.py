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

"""ReadActivity — Tag data reading with key recovery pipeline.
types with different read strategies (MFC key recovery, UL direct read,
iCLASS, LF, ISO15693, etc.).

The .so modules (read.so, scan.so, template.so, executor.so) handle ALL
RFID logic.  We orchestrate UI state transitions only.

  - trace_read_flow_20260401.txt: Real device read flow (2 MFC 1K reads)
  - trace_autocopy_mf1k_standard.txt: AutoCopy with READER_START args
  - read_tag_*.png: Real device screenshots
  - QEMU probing: Reader() no-args, start(tag_type, bundle) 2 positional args
  -

Key architecture finding from trace_read_flow_20260401.txt:
  - ReadListActivity IS-A ReadActivity on real device (inherits)
  - Stack stays at depth 2 — NO separate ReadActivity pushed
  - read.so calls showReadToast() directly on the activity instance
  - The activity reference comes from the call_reading bound method's __self__
  - onReading(sector, total, callback) is the progress callback signature

Import convention: ``from lib.activity_read import ReadActivity``
"""

from lib.actbase import BaseActivity
from lib.widget import Toast, ProgressBar
from lib import actstack, resources
from lib._constants import (
    SCREEN_W,
    SCREEN_H,
    KEY_UP,
    KEY_DOWN,
    KEY_OK,
    KEY_M1,
    KEY_M2,
    KEY_PWR,
    KEY_LEFT,
    KEY_RIGHT,
    COLOR_ACCENT,
)


class ConsoleMixin:
    """Inline PM3 console view shared by ReadListActivity and AutoCopyActivity.

    view within the activity. Stack doesn't change. RIGHT toggles on, PWR off.

    Requires: self.getCanvas(), SCREEN_W, SCREEN_H available.
    Init must set: self._console = None, self._console_showing = False
    """

    def _showConsole(self):
        """Show inline console view (NOT a separate activity).

        Creates ConsoleView on our canvas, hides read content beneath it.
        Loads executor.CONTENT_OUT_IN__TXT_CACHE for current PM3 output.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        self._console_showing = True

        if self._console is None:
            from lib.widget import ConsoleView
            self._console = ConsoleView(canvas, x=0, y=0,
                                        width=SCREEN_W, height=SCREEN_H)

        self._console.clear()
        try:
            import executor
            cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if cache:
                self._console.addText(cache)
        except Exception:
            pass

        self._console.autofit_font_size()
        self._console.show()

        # Poll for live updates during read
        try:
            import executor
            self._console_poll_len = len(
                getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or '')
        except Exception:
            self._console_poll_len = 0
        import threading
        def _poll():
            import time
            while self._console_showing:
                try:
                    import executor
                    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
                    if len(cache) > self._console_poll_len:
                        self._console.addText(cache[self._console_poll_len:])
                        self._console_poll_len = len(cache)
                except Exception:
                    pass
                time.sleep(0.3)
        threading.Thread(target=_poll, daemon=True).start()

    def _hideConsole(self):
        """Hide console view, restore read content."""
        self._console_showing = False
        if self._console is not None:
            self._console.hide()

    def _handleConsoleKey(self, key):
        """Dispatch key to ConsoleView. Returns True if handled.

        console key handler — activity_main.py lines 936-966):
            M1:    textfontsizedown (zoom out)
            M2:    textfontsizeup (zoom in)
            UP:    scrollUp
            DOWN:  scrollDown
            RIGHT: horizontal scroll right
            LEFT:  horizontal scroll left
            PWR:   exit console
        """
        if not self._console_showing:
            return False
        if key == KEY_PWR:
            self._hideConsole()
        elif key == KEY_M2:
            if self._console:
                self._console.textfontsizeup()
        elif key == KEY_M1:
            if self._console:
                self._console.textfontsizedown()
        elif key == KEY_UP:
            if self._console:
                self._console.scrollUp()
        elif key == KEY_DOWN:
            if self._console:
                self._console.scrollDown()
        elif key == KEY_RIGHT:
            if self._console:
                self._console.scrollRight()
        elif key == KEY_LEFT:
            if self._console:
                self._console.scrollLeft()
        return True


class ReadActivity(ConsoleMixin, BaseActivity):
    """Tag data reading — scan for tag then read its data.

    Launched by ReadListActivity with bundle={'tag_type': int, 'tag_name': str}.

    Screenshots: read_tag_scanning_*.png, read_tag_reading_*.png,
                 read_tag_no_tag_or_wrong_type_*.png
    """

    ACT_NAME = 'read'

    def __init__(self, bundle=None):
        self._state = 'idle'
        self._tag_type = None
        self._tag_name = None
        self._scan_cache = None
        self._scanner = None
        self._reader = None
        self._toast = None
        self._progress = None
        self._got_progress = False  # True once onReading progress fires
        self._read_bundle = None    # Read result for write flow (dump path or dict)
        self._console = None        # ConsoleView instance (inline, not activity)
        self._console_showing = False
        self._pending_result = None  # Deferred result when console is showing
        self._fake_timer = None     # Timer ID for fake progress animation
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, receive tag_type from bundle, start scan.

        START(ReadListActivity, None) → immediate hf 14a info.
        Screenshot: read_tag_scanning_1.png — title "Read Tag".
        """
        self.setTitle(resources.get_str('read_tag'))

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._toast = Toast(canvas)

        from lib.json_renderer import JsonRenderer
        self._jr = JsonRenderer(canvas)

        bundle = bundle or {}
        self._tag_type = bundle.get('tag_type')
        self._tag_name = bundle.get('tag_name', '')

        if self._tag_type is not None:
            self._startScan()

    def onResume(self):
        """Called when this activity becomes visible again.

        If read.so pushed a Warning activity directly (PUSH path) and the
        user dismissed it, we need to show the appropriate toast.
        etc.) expect toast:Read Failed after Warning is dismissed.
        """
        super().onResume()
        # If we're still in 'reading' state when resumed, a Warning was
        # pushed and dismissed without our code handling completion.
        if self._state == 'reading':
            self._reader = None
            self._showReadFailed()

    def onActivity(self, result):
        """Receives result from child WarningM1Activity.

        with result={'action': 'force'} → restart read with force=True.
        """
        if result is None or not isinstance(result, dict):
            return
        action = result.get('action')
        if action == 'force':
            self._startRead(force=True)
        elif action == 'sniff':
            try:
                from lib.activity_main import SniffActivity
                actstack.start_activity(SniffActivity)
            except (ImportError, AttributeError):
                pass
        elif action == 'enter_key':
            try:
                from lib.activity_main import KeyEnterM1Activity
                actstack.start_activity(KeyEnterM1Activity,
                                        {'tag_type': self._tag_type})
            except (ImportError, AttributeError):
                pass
        elif action == 'write':
            # FINISH(WarningWriteActivity) → START(WriteActivity, bundle)
            # Bundle is the same read result (path or dict) passed through.
            try:
                from lib.activity_main import WriteActivity
                actstack.start_activity(WriteActivity,
                                        result.get('read_bundle'))
            except (ImportError, AttributeError):
                pass

    def onDestroy(self):
        self._cancelScan()
        self._cancelRead()

    def onKeyEvent(self, key):
        """State-dependent key routing.

        inline view mode within ReadActivity, NOT a separate activity.
        Stack stays at same depth. RIGHT toggles console on, PWR toggles off.

        Console mode keys (read_console_common.sh lines 27-35):
            UP / M2:   textfontsizeup (zoom in)
            DOWN / M1: textfontsizedown (zoom out)
            RIGHT:     horizontal scroll right
            LEFT:      horizontal scroll left
            PWR:       exit console (back to read view)
        """
        # Console mode: all keys go to ConsoleView (from ConsoleMixin)
        if self._handleConsoleKey(key):
            return

        # PWR: always works, even during scanning/reading.
        # Must abort any in-flight PM3 command before finishing.
        if key == KEY_PWR:
            # Dismiss toast if showing (but don't swallow the key)
            for attr in ('_toast',):
                toast = getattr(self, attr, None)
                if toast is not None:
                    try:
                        if toast.isShow():
                            toast.cancel()
                    except Exception:
                        pass
            if self._state in ('scanning', 'reading'):
                try:
                    import hmi_driver
                    hmi_driver.presspm3()
                except Exception:
                    pass
                try:
                    import executor
                    executor.stopPM3Task()
                except Exception:
                    pass
            self.finish()
            return

        # Normal mode: state-dependent routing
        if self._state == 'scanning':
            # Busy — all keys except PWR ignored during active scan
            return

        if self._state == 'reading':
            # Busy — only RIGHT (console) works during active read
            if key == KEY_RIGHT:
                self._showConsole()
            return

        if self._state in ('read_success', 'read_partial'):
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
            elif key == KEY_M1:
                self._reread()
            elif key in (KEY_M2, KEY_OK):
                self._launchWrite()
            elif key == KEY_RIGHT:
                self._showConsole()
            return

        if self._state == 'read_failed':
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
            elif key == KEY_M1:
                self._reread()
            elif key == KEY_RIGHT:
                self._showConsole()
            return

        if self._state in ('no_tag', 'wrong_type'):
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
            elif key in (KEY_M1, KEY_M2, KEY_OK):
                self._startScan()
            return

    # ================================================================
    # Scan phase
    # ================================================================

    def _startScan(self):
        """Start scan using Scanner() pattern.

        Screenshot: read_tag_scanning_1-3.png.
        """
        self._state = 'scanning'
        self.setbusy()
        self._scan_cache = None
        self._clearContent()
        self.dismissButton()

        canvas = self.getCanvas()
        if canvas is not None:
            self._progress = ProgressBar(canvas)
            self._progress.setMessage(resources.get_str('scanning'))
            self._progress.show()
            # animates to 50% when entering scan, then advances based
            # on results, and completes to 100% before screen transition.
            self._progress.setProgress(50)

        try:
            import scan as _scan_mod
            self._scanner = _scan_mod.Scanner()
            self._scanner.call_progress = self.onScanning
            self._scanner.call_resulted = self.onScanFinish
            self._scanner.call_exception = self.onScanFinish
            # calls scanner.scan_type_asynchronous(tag_type), NOT scan_all.
            # Original PM3 traces confirm type-specific scanning:
            #   EM4305: lf em 4x05_info FFFFFFFF (no hf 14a info, no lf sea)
            #   AWID:   lf awid read (no hf 14a info, no lf sea)
            #   MF1K:   hf 14a info (no lf sea)
            #
            # NOTE: scan_type_synchronous has a strict type match check (spec
            # section 6.7, line 622) that rejects cross-subtype matches (e.g.
            # M1_PLUS_2K scanned as M1_S50_1K_4B). The original activity_main.so
            # has is_m1_tag_type() to handle this, not yet reimplemented.
            # Use scan_type for types with dedicated scan functions; scan_all
            # for types where cross-subtype matching is needed.
            _type_specific = set()
            try:
                import tagtypes as _tt
                _type_specific = {_tt.T55X7_ID, _tt.EM4305_ID}  # 23, 24
            except (ImportError, AttributeError):
                _type_specific = {23, 24}
            if self._tag_type in _type_specific:
                self._scanner.scan_type_asynchronous(self._tag_type)
            else:
                self._scanner.scan_all_asynchronous()
        except Exception as e:
            import traceback as _tb
            print('[READ-SCAN] scan start error: %s' % e, flush=True)
            _tb.print_exc()

    def _cancelScan(self):
        self.setidle()
        if self._scanner is not None:
            try:
                self._scanner.stop()
            except Exception:
                pass
            self._scanner = None

    def onScanning(self, progress):
        """Callback from scan.so — progress bar update."""
        if isinstance(progress, (list, tuple)) and len(progress) >= 2:
            pct = int(progress[0] * 100 / max(progress[1], 1))
        else:
            pct = int(progress) if progress else 0
        if self._progress is not None:
            self._progress.setProgress(pct)

    def onScanFinish(self, result):
        """Callback from scan.so — scan complete.

        hf 14a info → hf mf cgetblk 0 → scan cache set → fchks starts.
        After scan, read starts AUTOMATICALLY (no user button press).

        ProgressBar completes to 100% before transitioning.
        """
        self._scanner = None
        self.setidle()

        if result is None or isinstance(result, (str, int)):
            if self._progress is not None:
                self._progress.complete(self._showNoTag)
            else:
                self._showNoTag()
            return

        found = result.get('found', False)
        if found:
            self._scan_cache = result

            def _after_complete():
                self._clearContent()
                self._showTemplate()
                self._startRead()

            if self._progress is not None:
                self._progress.complete(_after_complete)
            else:
                _after_complete()
        else:
            has_multi = result.get('hasMulti', False)
            if has_multi:
                self._showNoTag(resources.get_str('tag_multi'))
            else:
                self._showNoTag()

    # ================================================================
    # Read phase
    # ================================================================

    def _startRead(self, force=False):
        """Start read using Reader().

        READER_START args=(1, {'infos': {scan_cache}, 'force': False})
        QEMU probe: Reader() no-args, start(tag_type, bundle) 2 positional args.

        ProgressBar (#1C6AEB) during the entire reading phase.

        Args:
            force: If True, force read with available keys (skip warning).
                   after WarningM1Activity returns action='force'.
        """
        self._state = 'reading'
        self.setbusy()
        self.dismissButton()

        # Show "Reading..." progress bar during read phase.
        # then advances based on key recovery / sector reads.
        canvas = self.getCanvas()
        if canvas is not None:
            self._progress = ProgressBar(canvas)
            self._progress.setMessage(resources.get_str('reading'))
            self._progress.show()
            self._progress.setProgress(50)

        self._start_fake_progress(start=50, ceiling=80)

        try:
            import scan as _scan_mod
            scan_cache = _scan_mod.getScanCache()
        except Exception:
            scan_cache = self._scan_cache
        if scan_cache is None:
            scan_cache = self._scan_cache or {}

        bundle = {'infos': scan_cache, 'force': force}

        try:
            import read as _read_mod
            self._reader = _read_mod.Reader()
            # call_reading receives onReading bound method.
            # read.so extracts __self__ to get the activity reference,
            # then calls showReadToast() directly on the activity.
            # <bound method ReadActivity.onReading of ReadListActivity>
            self._reader.call_reading = self.onReading
            self._reader.call_exception = self._onReadException
            self._reader.start(self._tag_type, bundle)

            # Completion is handled through FOUR mechanisms (all ground truth):
            #
            # 1. MFC reads: onReading receives completion dict with 'success'
            #    key. Handled in onReading() above.
            #
            # 2. LF/T55xx failures: read.so pushes Warning activities DIRECTLY
            #    via actstack.start_activity.
            #
            # 3. Errors: call_exception fires. Handled in _onReadException().
            #
            # 4. Other readers (iCLASS, UL, ISO15693, Felica, Legic):
            #    completion doesn't reliably use mechanisms 1-3. Fallback
            #    to is_reading() poll with delay to allow 1-3 to act first.
            import threading as _thr
            def _wait_for_completion():
                import time
                # Wait for reader to finish, then give 2s for mechanisms
                # 1-3 to fire before falling back to success.
                while self._reader is not None and self._state == 'reading':
                    try:
                        if not self._reader.is_reading():
                            # Wait for Warning push / onReading dict / exception
                            time.sleep(2.0)
                            # If state already changed, another mechanism handled it
                            if self._state != 'reading':
                                return
                            # Check if a Warning was pushed on top of us
                            try:
                                top = actstack.get_current_activity()
                                if top is not self:
                                    return  # Warning activity handles the UI
                            except Exception:
                                pass
                            # No other mechanism fired.
                            # If progress updates were received, read started
                            # and completed → success. If no progress, the
                            # read failed silently → "Read Failed".
                            self._reader = None
                            if self._got_progress:
                                self._showReadSuccess()
                            else:
                                self._showReadFailed()
                            return
                    except Exception:
                        pass
                    time.sleep(0.3)
            _thr.Thread(target=_wait_for_completion, daemon=True).start()
        except Exception as e:
            import traceback as _tb
            print('[READ] read start error: %s' % e, flush=True)
            _tb.print_exc()
            self._showReadFailed()

    def _cancelRead(self):
        self.setidle()
        self._cancel_fake_progress()
        if self._reader is not None:
            try:
                self._reader.stop()
            except Exception:
                pass
            self._reader = None

    def _start_fake_progress(self, start=0, ceiling=80):
        """Animate progress bar at ~1%/s until real callbacks arrive."""
        self._cancel_fake_progress()
        if actstack._root is None:
            return
        self._fake_pct = start

        def _tick():
            if self._state not in ('reading', 'scanning'):
                self._fake_timer = None
                return
            if self._fake_pct < ceiling:
                self._fake_pct += 1
                if self._progress is not None:
                    self._progress.setProgress(self._fake_pct)
                self._fake_timer = actstack._root.after(1000, _tick)
            else:
                self._fake_timer = None
        self._fake_timer = actstack._root.after(1000, _tick)

    def _cancel_fake_progress(self):
        """Stop fake progress animation."""
        if self._fake_timer is not None:
            try:
                actstack._root.after_cancel(self._fake_timer)
            except Exception:
                pass
            self._fake_timer = None

    def onReading(self, *args):
        """Callback from read.so — progress during reading.

        HFMFREAD.callListener((sector, total, <bound method onReading>))
        Called with (sector_num, total_sectors, callback_ref) during read.

        Screenshot: read_tag_reading_1.png — "Reading..." at bottom,
        read_tag_scanning_5.png — "Reading...32/32Keys".
        """
        if not args:
            return

        # COMPLETION CHECK: read.so sends the final result THROUGH
        # call_reading as the last onReading call. Discovered via
        # /tmp/_onreading_force.log and [READ-POLL] logging:
        #   {'success': False, 'tag_info': {...}, 'return': -3}
        # When 'success' key is present, this is a completion notification.
        data = args[0] if isinstance(args[0], dict) else {}
        if isinstance(data, dict) and 'success' in data:
            self._cancel_fake_progress()
            self._reader = None
            success = data.get('success', False)
            ret_code = data.get('return', 0)
            print('[READ-COMPL] ret=%s success=%s keys=%s bundle=%r' % (ret_code, success, list(data.keys()), data.get('bundle', '?')), flush=True)
            # read.so sends return codes via call_reading completion dict.
            # The ORIGINAL activity_main.so ReadActivity.onReading maps these
            # to UI actions (toast, warning, buttons). We replace that UI logic.
            # This is NOT middleware — read.so computes the codes, we render UI.
            # Same pattern as ScanActivity mapping found/not-found to toasts.
            ret_code = data.get('return', 0)
            if success:
                # Store bundle for write flow — ground truth:
                # awid_write_trace line 11: bundle is read result dict
                # full_read_write_trace line 49: bundle is dump file path
                self._read_bundle = data.get('bundle', data.get('tag_info', ''))
                if data.get('force'):
                    self._showReadSuccess(partial=True)
                else:
                    self._showReadSuccess()
            elif ret_code in (-3, -4):
                # -3: partial key recovery (some keys found, not all)
                # -4: key recovery method failed (e.g., darkside not vulnerable)
                # Both mean recovery IS possible → push WarningM1Activity
                self._launchWarningKeys()
            elif ret_code == -2:
                # -2: read operation failed (all reader types)
                # (tag_lost, all_sectors_fail, felica_fail, iclass_no_key, etc.)
                self._showReadFailed()
            elif ret_code == -1:
                # -1: read couldn't complete.
                # Audit finding 7: this checks scan cache structure to
                # determine HF vs LF. This reads scan.so's own data (not
                # middleware) — the cache structure IS the ground truth.
                #   HF cache has 'uid' (from hf 14a info), LF has 'data'+'raw'
                # scan.getScanCache() has 'sak'/'atqa'
                #   for HF tags (MFC, UL, NTAG, iCLASS, etc.) but not LF
                sc = self._scan_cache or {}
                try:
                    import scan as _s
                    _sc = _s.getScanCache()
                    if _sc:
                        sc = _sc
                except Exception:
                    pass
                # If scan confirmed a specific tag type, read genuinely
                # failed → "Read Failed". If scan was tentative (no type
                # confirmed), read couldn't verify → "Wrong type".
                # UL scan cache has isMFU+type but no sak/atqa.
                # LF scan cache has no type confirmation at all.
                # HF scan cache has 'uid' (from hf 14a info / hf sea).
                # LF scan cache has 'data'+'raw' (from lf sea), no 'uid'.
                #   MFC cache=['found','uid','len','sak','atqa',...],
                #   LF cache=['data','raw','type','found']
                if sc.get('uid'):
                    self._showReadFailed()
                else:
                    self._showNoTag()
            else:
                self._showReadFailed()
            return

        # {'m1_keys': True, 'seconds': 66, 'action': 'ChkDIC',
        #  'keyIndex': 0, 'keyCountMax': 32, 'progress': 0}
        #
        # Real device screenshot format (read_tag_reading_2.png):
        #   "01'08''"           — countdown timer (MM'SS'')
        #   "ChkDIC...0/32keys" — action + key progress
        # Both lines CENTER-ALIGNED, blue (#1C6AEB)
        data = args[0] if isinstance(args[0], dict) else {}
        if not isinstance(data, dict):
            return

        self._got_progress = True
        self._cancel_fake_progress()

        if self._console_showing:
            return

        seconds = data.get('seconds', 0)
        action = data.get('action', '')
        key_idx = data.get('keyIndex', 0)
        key_max = data.get('keyCountMax', 0)
        progress = data.get('progress', 0)

        # Build timer string — ground truth format from read_tag_reading_2.png:
        #   "01'08''" (MM'SS'')
        if seconds and int(seconds) > 0:
            mm = int(seconds) // 60
            ss = int(seconds) % 60
            timer = "%02d'%02d''" % (mm, ss)
        else:
            timer = ''

        # Build action string — ground truth format from read_tag_reading_2.png:
        #   "ChkDIC...0/32keys" or "Reading...5/16Keys"
        if action == 'REC_ALL' and key_max > 0:
            status = resources.get_str('reading_with_keys').format(key_idx, key_max)
        elif action and key_max > 0:
            status = '%s...%d/%dkeys' % (action, key_idx, key_max)
        elif action:
            status = action
        else:
            status = ''

        # Schedule UI update on Tk main thread — callback fires from
        # read background thread.  ProgressBar widget handles rendering
        # at the correct position with correct colors.
        def _update_ui():
            if self._progress is not None:
                if progress:
                    self._progress.setProgress(int(progress))
                if status:
                    self._progress.setMessage(status)
                self._progress.setTimer(timer)

        try:
            from lib import actstack
            if actstack._root is not None:
                actstack._root.after(0, _update_ui)
            else:
                _update_ui()
        except Exception:
            pass

    def showReadToast(self, *args):
        """Called DIRECTLY by read.so on the activity when read completes.

        returns 1, the .so calls showReadToast() on the activity instance.
        The activity reference comes from call_reading bound method's __self__.

        ReadActivity.showReadToast

        Audit finding 6: The binary's showReadToast receives a resource key
        string and displays it as a toast. The routing to success/fail/keys
        states happens through the onReading completion dict (mechanism 1)
        or via read.so pushing Warning activities directly (mechanism 2).
        showReadToast is a DISPLAY method, not a routing method.
        """
        self._reader = None

        msg = args[0] if args and isinstance(args[0], str) else ''

        # Display the toast message from read.so (pure UI, no routing)
        if msg and self._toast:
            self._toast.show(msg, duration_ms=0)

        # State routing is handled by onReading completion dict and
        # _wait_for_completion poll, not by keyword matching here.
        # Mark that read.so has called back (for the poll thread).
        self._got_progress = True

    def hideReadToast(self, *args):
        """Called by read.so to dismiss toast.

        ReadActivity.hideReadToast
        """
        if self._toast is not None:
            self._toast.cancel()

    def onData(self, *args):
        """Called by read.so with read data.

        ReadActivity.onData
        """
        self._reader = None
        print('[READ] onData args=%r' % (args,), flush=True)
        # onData may fire before or after showReadToast.
        # Don't transition state here — let showReadToast handle UI.

    def _onReadException(self, *args):
        """Callback from read.so via call_exception — error during read.

        QEMU probe confirmed: call_exception fires with traceback string
        on read ERRORS (not success). This is the only callback that
        reliably reaches Python objects from read.so.
        """
        self._reader = None
        if args:
            print('[READ-EXC] %s' % str(args[0])[:300], flush=True)
        # Exception during read: if no progress updates were received,
        # the reader couldn't handle the tag → "Wrong type"
        if self._got_progress:
            self._showReadFailed()
        else:
            self._showNoTag()

    # ================================================================
    # UI state rendering — all from ground truth screenshots
    # ================================================================

    def _showTemplate(self):
        """Render card info via template.so.

        Frequency: 13.56MHZ, UID, SAK, ATQA. template.so does ALL rendering.
        Scan flow lesson #2: NEVER invent display logic.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return
        try:
            import template
            tag_type = self._tag_type
            if self._scan_cache and isinstance(self._scan_cache, dict):
                tag_type = self._scan_cache.get('type', tag_type)
            template.draw(tag_type, self._scan_cache, canvas)
        except Exception as e:
            print('[TEMPLATE] draw failed: %s' % e, flush=True)

    def _showNoTag(self, message=None):
        """Show no-tag toast."""
        self.setidle()
        self._state = 'no_tag'
        if self._console_showing:
            self._pending_result = ('no_tag', message)
            return
        self._clearContent()
        msg = message or resources.get_str('no_tag_found2')
        if self._toast is not None:
            self._toast.show(msg, mode=Toast.MASK_CENTER, icon='error',
                             duration_ms=0)
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('rescan'))

    def _showReadSuccess(self, partial=False):
        """Show read success toast with tag info template visible underneath.

        Real device shows tag info summary behind the success toast.
        """
        self.setidle()
        self._state = 'read_partial' if partial else 'read_success'
        if self._console_showing:
            self._pending_result = ('success', partial)
            return

        def _after_complete():
            if self._progress is not None:
                self._progress.hide()
                self._progress = None
            canvas = self.getCanvas()
            if canvas is not None:
                canvas.delete('_read_status')
            self._showTemplate()
            msg_key = 'read_ok_2' if partial else 'read_ok_1'
            if self._toast is not None:
                self._toast.show(resources.get_str(msg_key),
                                 mode=Toast.MASK_CENTER, icon='check',
                                 duration_ms=0)
            self.setLeftButton(resources.get_str('reread'))
            self.setRightButton(resources.get_str('write'))

        if self._progress is not None:
            self._progress.complete(_after_complete)
        else:
            _after_complete()

    def _showReadFailed(self):
        """Show read failed toast. ProgressBar completes to 100% first."""
        self.setidle()
        self._state = 'read_failed'
        if self._console_showing:
            self._pending_result = ('failed', None)
            return

        def _after_complete():
            if self._progress is not None:
                self._progress.hide()
                self._progress = None
            canvas = self.getCanvas()
            if canvas is not None:
                canvas.delete('_read_status')
            if self._toast is not None:
                self._toast.show(resources.get_str('read_failed'),
                                 mode=Toast.MASK_CENTER, icon='error',
                                 duration_ms=0)
            self.setLeftButton(resources.get_str('reread'))
            self.setRightButton(resources.get_str('write'), active=False)

        if self._progress is not None:
            self._progress.complete(_after_complete)
        else:
            _after_complete()

    # ================================================================
    # Navigation
    # ================================================================

    def _launchWarningKeys(self):
        """Push WarningM1Activity when keys are missing.

        WarningM1Activity presents options: Sniff, Enter, Force, PC-M.
        Result returns via onActivity() with action name.
        """
        self._state = 'warning_keys'
        # Hide reading progress bar before pushing Warning activity
        if self._progress is not None:
            self._progress.hide()
            self._progress = None
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.delete('_read_status')
        try:
            import scan as _scan_mod
            infos = _scan_mod.getScanCache() or self._scan_cache or {}
        except Exception:
            infos = self._scan_cache or {}
        bundle = {'infos': infos}
        try:
            from lib.activity_main import WarningM1Activity
            actstack.start_activity(WarningM1Activity, bundle)
        except (ImportError, AttributeError):
            self._showReadFailed()

    def _showConsole(self):
        """Show console — hide progress bar and status text underneath.
        """
        if self._progress is not None:
            self._progress.hide()
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.delete('_read_status')
        super()._showConsole()

    def _hideConsole(self):
        """Hide console + show deferred result if one arrived during console."""
        super()._hideConsole()
        # If read is still in progress, re-show progress bar
        if self._state == 'reading' and self._progress is not None:
            self._progress.show()
        # Show deferred result that arrived while console was open
        if self._pending_result is not None:
            kind, data = self._pending_result
            self._pending_result = None
            if kind == 'success':
                self._showReadSuccess(partial=data)
            elif kind == 'failed':
                self._showReadFailed()
            elif kind == 'no_tag':
                self._showNoTag(data)

    def _reread(self):
        self.dismissButton()
        self._clearContent()
        self._startScan()

    def _launchWrite(self):
        """Launch WarningWriteActivity with read bundle.

        - MFC: START(WarningWriteActivity, '/mnt/upan/dump/mf1/..._7.bin')
          (full_read_write_trace_20260327.txt line 49)
        - LF:  START(WarningWriteActivity, {'return':1, 'data':..., 'raw':...})
          (awid_write_trace_20260328.txt line 11)
        - T55: START(WarningWriteActivity, {'return':1, ..., 'file':'...'})
          (t55_to_t55_write_trace_20260328.txt line 19)

        The bundle is the read result — either a dump file path (HF)
        or a read result dict (LF). Passed through to WriteActivity.
        """
        try:
            from lib.activity_main import WarningWriteActivity
            actstack.start_activity(WarningWriteActivity,
                                    self._read_bundle)
        except (ImportError, AttributeError):
            pass

    # ================================================================
    # Utility
    # ================================================================

    def _clearContent(self):
        """Clear all content-area widgets.

        must clear JSON renderer tags + template.so items.
        """
        if self._progress is not None:
            self._progress.hide()
            self._progress = None
        if self._toast is not None:
            self._toast.cancel()
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.delete('_read_status')
            canvas.delete('_jr_content')
            canvas.delete('_jr_content_bg')
            canvas.delete('_jr_buttons')
            try:
                import template
                template.dedraw(canvas)
            except Exception:
                pass

    def canidle(self):
        """Binary symbol: ReadActivity.canidle"""
        return self._state not in ('scanning', 'reading')

    @property
    def state(self):
        return self._state

    @property
    def scan_cache(self):
        return self._scan_cache
