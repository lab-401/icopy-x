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

"""Diagnosis activities — replaces DiagnosisActivity + 6 sub-activities from activity_tools.so.

Source: activity_tools.so (DiagnosisActivity, ScreenTestActivity, ButtonTestActivity,
SoundTestActivity, HFReaderTestActivity, LfReaderTestActivity, UsbPortTestActivity)
Spec: docs/UI_Mapping/09_diagnosis/README.md

Two-level menu architecture:
  Level 1 (ITEMS_MAIN): BigTextListView with "User diagnosis" / "Factory diagnosis"
  Level 2 (ITEMS_TEST): CheckedListView with 9 sub-test items
  Tests execute via PM3 commands (executor) or sub-activity launch.

Import convention: ``from lib.activity_tools import DiagnosisActivity``
"""

import re
import threading

from lib.actbase import BaseActivity
from lib.widget import ListView, BigTextListView, CheckedListView
from lib import actstack, resources
from lib._constants import (
    SCREEN_W,
    SCREEN_H,
    CONTENT_Y0,
    LIST_ITEM_H,
    LIST_TEXT_X_NO_ICON,
    KEY_UP,
    KEY_DOWN,
    KEY_OK,
    KEY_M1,
    KEY_M2,
    KEY_PWR,
    KEY_LEFT,
    KEY_RIGHT,
    COLOR_ACCENT,
    COLOR_PASS,
    COLOR_NOT_TESTED,
    COLOR_BLACK,
    COLOR_WHITE,
    NORMAL_TEXT_COLOR,
    TITLE_TEXT_COLOR,
)


# =====================================================================
# State constants
# =====================================================================

STATE_ITEMS_MAIN = 'items_main'
STATE_ITEMS_TEST = 'items_test'
STATE_TESTING = 'testing'
STATE_RESULTS = 'results'

# Test result constants
RESULT_PASS = 'Pass'
RESULT_FAIL = 'Fail'
RESULT_NONE = None  # not tested

# Colors for pass/fail display (imported from _constants.py)
COLOR_FAIL = COLOR_ACCENT


# =====================================================================
# DiagnosisActivity
# =====================================================================

class DiagnosisActivity(BaseActivity):
    """Hardware self-test coordinator.

    Real device flow (from screenshots + original .so):
      1. ITEMS_MAIN: ListView with "User diagnosis" / "Factory diagnosis"
         No button labels. OK selects.
      2. TIPS: Canvas text "Press start button to start diagnosis."
         M1="Cancel" M2="Start"
      3. TESTING: Sequential auto-run of 5 PM3 tests.
         Canvas text "Testing with:\n{test_name}" for each.
         No button labels during testing.
      4. RESULTS: Plain text list showing pass/fail with values.
         Title "Diagnosis 1/1". Format: "HF Voltage : √ (37V)"

    Source: activity_tools.so, real device screenshots diagnosis_menu_1..6,
    diagnosis_results_1_1.png
    """

    ACT_NAME = 'diagnosis'

    # Top-level items
    _MAIN_KEYS = ('diagnosis_item1', 'diagnosis_item2')

    # User diagnosis PM3 tests (run sequentially)
    _USER_TESTS = [
        # (name_key, pm3_cmd, timeout, parse_type)
        ('diagnosis_subitem1', 'hf tune',      8888, 'voltage'),  # HF Voltage
        ('diagnosis_subitem2', 'lf tune',      8888, 'voltage'),  # LF Voltage
        ('diagnosis_subitem3', 'hf 14a reader', 5888, 'reader'),  # HF reader
        ('diagnosis_subitem4', 'lf sea',       8888, 'reader'),   # LF reader
        ('diagnosis_subitem5', None,           5888, 'flash'),    # Flash Memory
    ]

    def __init__(self, bundle=None):
        self._state = STATE_ITEMS_MAIN
        self._main_listview = None
        self._main_items = []
        self._test_results = []   # list of (name, passed, value_str)
        self._is_testing = False
        self._testing_tag = 'diag_testing'
        self._results_tag = 'diag_results'
        super().__init__(bundle)

    def onCreate(self, bundle):
        """OSS: skip User/Factory menu, launch directly into User Diagnosis.

        Original shows ITEMS_MAIN with "User diagnosis" / "Factory diagnosis".
        OSS skips this and goes straight to the tips/start screen.
        """
        self.setTitle(resources.get_str('diagnosis'))
        self.setLeftButton('')
        self.setRightButton('')

        self._main_items = list(resources.get_str(list(self._MAIN_KEYS)))

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._main_listview = ListView(canvas)
        self._main_listview.setItems(self._main_items[:1])

        # Skip directly to User Diagnosis tips screen.
        self._show_tips()

    def _show_main_menu(self):
        """Display ITEMS_MAIN — plain list of User/Factory diagnosis."""
        self._state = STATE_ITEMS_MAIN
        canvas = self.getCanvas()
        if canvas is None:
            return

        # Clear any testing/results display
        canvas.delete(self._testing_tag)
        canvas.delete(self._results_tag)

        # Show main menu items as proper ListView
        if self._main_listview is not None:
            self._main_listview.show()

        self.setTitle(resources.get_str('diagnosis'))
        self.setLeftButton('')
        self.setRightButton('')

    def _show_tips(self):
        """TIPS screen: instructions before starting tests.

        Source: diagnosis_menu_2.png — "Press start button to start
        diagnosis." with M1="Cancel" M2="Start"
        """
        self._state = STATE_ITEMS_TEST  # test expects M2="Start" in this state
        canvas = self.getCanvas()
        if canvas is None:
            return

        # Hide main menu
        if self._main_listview is not None:
            self._main_listview.hide()

        # Show tips text.
        # Ground truth: original state dump — font=monospace 15, (120,120),
        # fill=#1C6AEB, anchor=center.
        tips = resources.get_str('start_diagnosis_tips')
        canvas.delete(self._testing_tag)
        canvas.create_text(
            SCREEN_W // 2, SCREEN_H // 2,
            text=tips,
            fill=COLOR_ACCENT,
            font=resources.get_font(15),
            anchor='center',
            width=200,
            tags=self._testing_tag,
        )

        self.setLeftButton(resources.get_str('cancel'))
        self.setRightButton(resources.get_str('start'))

    # Path for flash memory test file — must exist before mem spiffs load.
    # Ground truth: trace_misc_flows_session2_20260330.txt line 73.524
    _FLASH_TEST_FILE = '/tmp/test_pm3_mem.nikola'

    def _run_all_tests(self):
        """Run all 5 user diagnosis tests sequentially.

        Source: diagnosis_menu_3..6 — shows "Testing with: \\n{name}"
        for each test. No buttons during testing.
        Ground truth: trace_misc_flows_session2_20260330.txt (timing,
        command sequence, response parsing).
        Original .so state dump: font=monospace 15, text at (120, 120).
        """
        self._state = STATE_TESTING
        self._is_testing = True
        self._test_results = []

        # Hide the entire button bar during testing (not just empty labels)
        self.dismissButton()

        # Run tests in a thread to avoid blocking the UI
        def _test_runner():
            canvas = self.getCanvas()

            # Ensure flash test file exists (2 bytes "NK").
            # Ground truth: diagnosis_common.sh line 116.
            try:
                import os
                if not os.path.exists(self._FLASH_TEST_FILE):
                    with open(self._FLASH_TEST_FILE, 'wb') as f:
                        f.write(b'\x4E\x4B')
            except Exception:
                pass

            for i, (name_key, cmd, timeout, parse_type) in enumerate(self._USER_TESTS):
                test_name = resources.get_str(name_key)

                # Show "Testing with: \n{name}" on canvas.
                # Ground truth: original state dump — font 15, fill=#1C6AEB,
                # text='Testing with: \n{name}', (120, 120), anchor=center.
                if canvas is not None:
                    def _show_testing(name=test_name):
                        canvas.delete(self._testing_tag)
                        canvas.delete(self._results_tag)
                        canvas.create_text(
                            SCREEN_W // 2, SCREEN_H // 2,
                            text='Testing with: \n%s' % name,
                            fill=COLOR_ACCENT,
                            font=resources.get_font(15),
                            anchor='center',
                            tags=self._testing_tag,
                        )
                    try:
                        canvas.after(0, _show_testing)
                    except Exception:
                        pass

                # Execute test — no artificial delay.
                # Ground truth: real device trace shows <0.1s between commands.
                passed = False
                value_str = ''
                try:
                    import executor
                    if parse_type == 'flash':
                        # Flash memory: load + wipe.
                        # Ground truth: trace shows exact command:
                        #   mem spiffs load f /tmp/test_pm3_mem.nikola o test_pm3_mem.nikola
                        ret = executor.startPM3Task(
                            'mem spiffs load f %s o test_pm3_mem.nikola'
                            % self._FLASH_TEST_FILE,
                            timeout=timeout,
                            rework_max=0,
                        )
                        if ret == 1:
                            content = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
                            passed = bool(re.search(r'Wrote \d+ bytes', content))
                            try:
                                executor.startPM3Task('mem spiffs wipe',
                                                      timeout=timeout,
                                                      rework_max=0)
                            except Exception:
                                pass
                    else:
                        # rework_max=0: diagnosis tests must not trigger
                        # reworkPM3All() retries.  The original firmware
                        # completes each test in <1s; if our PM3 doesn't
                        # respond, retrying just wastes 30s per test and
                        # corrupts the socket for subsequent tests.
                        ret = executor.startPM3Task(cmd, timeout=timeout,
                                                    rework_max=0)
                        if ret == 1:
                            content = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
                            if parse_type == 'voltage':
                                # Use findall + take LAST match: first reading
                                # is always "0 mV / 0 V" (antenna warmup).
                                # Real measurement follows after [=] separators.
                                matches = re.findall(r'(\d+)\s*mV\s*/\s*(\d+)\s*V', content)
                                if matches:
                                    mv = int(matches[-1][0])
                                    v = matches[-1][1]
                                    passed = mv > 0
                                    value_str = '(%sV)' % v
                            elif parse_type == 'reader':
                                # Pass = tag actually found in response.
                                # HF: UID present. LF: valid tag ID found.
                                if 'UID' in content or 'ATQA' in content:
                                    passed = True
                                elif re.search(r'Valid|TAG ID|ID\s*:', content):
                                    passed = True
                                else:
                                    passed = False
                except Exception:
                    pass

                self._test_results.append((test_name, passed, value_str))

            # All tests done — show results on main thread
            self._is_testing = False
            if canvas is not None:
                try:
                    canvas.after(0, self._show_results)
                except Exception:
                    pass

        threading.Thread(target=_test_runner, daemon=True).start()

    def _show_results(self):
        """Display test results as plain text list.

        Source: diagnosis_results_1_1.png, original .so QEMU state dump.
        Format: "HF Voltage  : √ (37V)" or "LF reader   : X"
        Title: "Diagnosis 1/1"

        Ground truth positions (from original .so state dump):
          x = LIST_TEXT_X_NO_ICON (19)
          y = CONTENT_Y0 + i * LIST_ITEM_H + LIST_ITEM_H // 2
            = 60, 100, 140, 180, 220
          font = monospace 13, fill = black, anchor = 'w'
        Names preserve trailing spaces for column alignment.
        """
        self._state = STATE_RESULTS
        canvas = self.getCanvas()
        if canvas is None:
            return

        canvas.delete(self._testing_tag)
        canvas.delete(self._results_tag)

        self.setTitle('%s 1/1' % resources.get_str('diagnosis'))
        self.setLeftButton('')
        self.setRightButton('')

        for i, (name, passed, value_str) in enumerate(self._test_results):
            mark = '\u221a' if passed else 'X'  # √ or X
            # Preserve trailing spaces in name for column alignment.
            # Ground truth: original .so text='HF Voltage  : √ (37V)'
            line = '%s: %s' % (name, mark)
            if value_str:
                line += ' %s' % value_str

            y = CONTENT_Y0 + i * LIST_ITEM_H + LIST_ITEM_H // 2

            canvas.create_text(
                LIST_TEXT_X_NO_ICON, y,
                text=line,
                fill=NORMAL_TEXT_COLOR,
                font=resources.get_font(13),
                anchor='w',
                tags=self._results_tag,
            )

    def onKeyEvent(self, key):
        """Key handling per state.

        ITEMS_MAIN: OK → tips screen, PWR → exit
        TIPS: M2/OK → run tests, M1/PWR → back to main
        TESTING: PWR → cancel
        RESULTS: PWR → back to main
        """
        if self._is_testing:
            # Busy — PWR ignored during active testing
            return

        if self._state == STATE_ITEMS_MAIN:
            if key in (KEY_M2, KEY_OK):
                self._show_tips()
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()

        elif self._state == STATE_ITEMS_TEST:
            # TIPS state — M2/OK starts tests, M1/PWR goes back
            if key in (KEY_M2, KEY_OK):
                self._run_all_tests()
            elif key in (KEY_M1, KEY_PWR):
                if key == KEY_PWR and self._handlePWR():
                    return
                self._show_main_menu()

        elif self._state == STATE_RESULTS:
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self._show_main_menu()

    def _cancel_test(self):
        """Cancel current test and return to main menu."""
        self._is_testing = False
        self._show_main_menu()

    def updateTitle(self):
        self.setTitle(resources.get_str('diagnosis'))

    def setTipsEnable(self, enable):
        """Show/hide tips text on canvas."""
        if enable:
            self._show_tips()
        else:
            canvas = self.getCanvas()
            if canvas:
                canvas.delete(self._testing_tag)

    def onData(self, data):
        """Receive results from sub-activities."""
        if isinstance(data, dict):
            test_index = data.get('test_index')
            result = data.get('result', False)
            if test_index is not None:
                pass  # Sub-activity results not used in user diagnosis

    def get_state(self):
        return self._state

    def get_test_results(self):
        return list(self._test_results)


# =====================================================================
# ScreenTestActivity
# =====================================================================

class ScreenTestActivity(BaseActivity):
    """Display color cycle test.

    Cycles through test colors: blue -> green -> white -> green -> black.
    User manually confirms pass/fail via M1 (Fail) / M2 (Pass).

    Binary source: activity_tools.so ScreenTestActivity
    Spec: docs/UI_Mapping/09_diagnosis/README.md section 9
    """

    ACT_NAME = 'screen_test'

    # Test colors in cycle order
    COLORS = [COLOR_ACCENT, COLOR_PASS, COLOR_WHITE, COLOR_PASS, COLOR_BLACK]

    def __init__(self, bundle=None):
        self._color_pos = 0
        self._test_index = 7  # default screen test index
        self._showing_colors = False
        self._bg_tag = 'screen_test_bg'
        self._tips_tag = 'screen_test_tips'
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show instructions, M1="Fail", M2="Pass".

        From binary ScreenTestActivity.onCreate:
            1. Show tips: "Press 'OK' to start test..."
            2. M1="Fail", M2="Pass"
        """
        if isinstance(bundle, dict):
            self._test_index = bundle.get('test_index', 7)

        self.setTitle(resources.get_str('diagnosis'))
        self.setLeftButton(resources.get_str('fail'))
        self.setRightButton(resources.get_str('pass'))

        self.showTips()

    def onKeyEvent(self, key):
        """Handle screen test keys.

        OK: advance to next color (or start test)
        M2: Pass -- return result
        M1: Fail -- return result
        PWR: Exit (fail)
        UP/DOWN: change screen color
        """
        if key == KEY_OK:
            if not self._showing_colors:
                self._showing_colors = True
                self._color_pos = 0
                self.showBigBg()
            else:
                # Advance or stop test
                self._color_pos += 1
                if self._color_pos >= len(self.COLORS):
                    self.resetColorPos()
                    self.showTips()
                    self._showing_colors = False
                else:
                    self.showBigBg()
        elif key == KEY_UP:
            if self._showing_colors:
                self._color_pos = max(0, self._color_pos - 1)
                self.showBigBg()
        elif key == KEY_DOWN:
            if self._showing_colors:
                self._color_pos = min(len(self.COLORS) - 1, self._color_pos + 1)
                self.showBigBg()
        elif key == KEY_M2:
            self._finish_with_result(True)
        elif key == KEY_M1:
            self._finish_with_result(False)
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._finish_with_result(False)

    def showBigBg(self):
        """Fill screen with current test color."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete(self._bg_tag)
        canvas.delete(self._tips_tag)
        color = self.COLORS[self._color_pos]
        canvas.create_rectangle(
            0, 0, SCREEN_W, SCREEN_H,
            fill=color, outline=color, tags=self._bg_tag,
        )

    def showBtns(self):
        """Show pass/fail buttons."""
        self.setLeftButton(resources.get_str('fail'))
        self.setRightButton(resources.get_str('pass'))

    def showTips(self):
        """Display test instructions."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete(self._tips_tag)
        tips = resources.get_str('test_screen_tips')
        canvas.create_text(
            SCREEN_W // 2, SCREEN_H // 2,
            text=tips, fill=TITLE_TEXT_COLOR, anchor='center',
            font=resources.get_font(15), tags=self._tips_tag,
        )

    def resetColorPos(self):
        """Reset to first color."""
        self._color_pos = 0

    def _finish_with_result(self, passed):
        """Return result to parent DiagnosisActivity and finish."""
        # Notify parent via onData if stack allows
        stack = actstack.get_activity_pck()
        if len(stack) >= 2:
            parent = stack[-2]
            if hasattr(parent, 'onData'):
                parent.onData({
                    'test_index': self._test_index,
                    'result': passed,
                })
        self.finish()


# =====================================================================
# ButtonTestActivity
# =====================================================================

class ButtonTestActivity(BaseActivity):
    """Button press verification test.

    Displays button state indicators. All buttons must be pressed within
    timeout. Result: all pressed = Pass, timeout = Fail.

    Binary source: activity_tools.so ButtonTestActivity
    Spec: docs/UI_Mapping/09_diagnosis/README.md section 9
    """

    ACT_NAME = 'button_test'

    # All buttons that must be pressed
    REQUIRED_BUTTONS = [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_OK, KEY_M1, KEY_M2, KEY_PWR]

    AUTO_STOP_TIMEOUT_MS = 30000  # 30 second timeout

    def __init__(self, bundle=None):
        self._test_index = 6  # default button test index
        self._pressed = set()
        self._btn_tag = 'btn_test_state'
        self._auto_stop_timer = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show button state display.

        From binary ButtonTestActivity.onCreate:
            1. setTitle("Buttons")
            2. Show button state indicators (all waiting)
            3. Start auto_stop timer
        """
        if isinstance(bundle, dict):
            self._test_index = bundle.get('test_index', 6)

        self.setTitle(resources.get_str('buttons_test'))
        self.setLeftButton('')
        self.setRightButton('')

        self.update_btn_state()
        self.auto_stop_run()

    def onKeyEvent(self, key):
        """Record button press and update display.

        Each key press is recorded. When all required buttons are pressed,
        the test passes and finishes automatically.
        """
        self._pressed.add(key)
        self.update_btn_state()

        # Check if all buttons pressed
        if all(btn in self._pressed for btn in self.REQUIRED_BUTTONS):
            self._cancel_timer()
            self._finish_with_result(True)

    def update_btn_state(self):
        """Update visual feedback for each button state."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete(self._btn_tag)

        y_start = 50
        line_h = 20
        for i, btn_name in enumerate(self.REQUIRED_BUTTONS):
            y_pos = y_start + i * line_h
            state = 'pressed' if btn_name in self._pressed else 'waiting'
            color = COLOR_PASS if state == 'pressed' else COLOR_NOT_TESTED
            canvas.create_text(
                SCREEN_W // 2, y_pos,
                text=f'{btn_name}: [{state}]',
                fill=color, anchor='center',
                font=resources.get_font(13),
                tags=self._btn_tag,
            )

    def auto_stop_run(self):
        """Start auto-stop timer. If not all buttons pressed in time, fail."""
        canvas = self.getCanvas()
        if canvas is not None:
            self._auto_stop_timer = canvas.after(
                self.AUTO_STOP_TIMEOUT_MS,
                self._on_timeout,
            )

    def _on_timeout(self):
        """Timer expired -- fail the test."""
        self._finish_with_result(False)

    def _cancel_timer(self):
        """Cancel the auto-stop timer if running."""
        if self._auto_stop_timer is not None:
            canvas = self.getCanvas()
            if canvas is not None:
                canvas.after_cancel(self._auto_stop_timer)
            self._auto_stop_timer = None

    def _finish_with_result(self, passed):
        """Return result to parent DiagnosisActivity and finish."""
        stack = actstack.get_activity_pck()
        if len(stack) >= 2:
            parent = stack[-2]
            if hasattr(parent, 'onData'):
                parent.onData({
                    'test_index': self._test_index,
                    'result': passed,
                })
        self.finish()


# =====================================================================
# SoundTestActivity
# =====================================================================

class SoundTestActivity(BaseActivity):
    """Audio playback test.

    Plays audio.playStartExma() and asks user to confirm pass/fail.

    Binary source: activity_tools.so SoundTestActivity
    Spec: docs/UI_Mapping/09_diagnosis/README.md section 9
    """

    ACT_NAME = 'sound_test'

    def __init__(self, bundle=None):
        self._test_index = 8  # default sound test index
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Play test sound and show pass/fail buttons.

        From binary SoundTestActivity.onCreate:
            1. setTitle("Sound")
            2. M1="Fail", M2="Pass"
            3. Play audio.playStartExma()
            4. Show tips: "Do you hear the music?"
        """
        if isinstance(bundle, dict):
            self._test_index = bundle.get('test_index', 8)

        self.setTitle(resources.get_str('sound_test'))
        self.setLeftButton(resources.get_str('fail'))
        self.setRightButton(resources.get_str('pass'))

        # Play test sound
        try:
            import audio
            audio.playStartExma()
        except Exception:
            pass

        # Show tips
        canvas = self.getCanvas()
        if canvas is not None:
            tips = resources.get_str('test_music_tips')
            canvas.create_text(
                SCREEN_W // 2, SCREEN_H // 2,
                text=tips, fill=TITLE_TEXT_COLOR, anchor='center',
                font=resources.get_font(15),
                tags='sound_tips',
            )

    def onKeyEvent(self, key):
        """M2 = Pass, M1 = Fail, PWR = Exit (fail)."""
        if key == KEY_M2:
            self._finish_with_result(True)
        elif key == KEY_M1:
            self._finish_with_result(False)
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._finish_with_result(False)

    def _finish_with_result(self, passed):
        """Return result to parent and finish."""
        stack = actstack.get_activity_pck()
        if len(stack) >= 2:
            parent = stack[-2]
            if hasattr(parent, 'onData'):
                parent.onData({
                    'test_index': self._test_index,
                    'result': passed,
                })
        self.finish()


# =====================================================================
# HFReaderTestActivity
# =====================================================================

class HFReaderTestActivity(BaseActivity):
    """HF antenna reader test via 'hf 14a reader'.

    Shows tips, runs PM3 command, reports pass/fail.

    Binary source: activity_tools.so HFReaderTestActivity
    Spec: docs/UI_Mapping/09_diagnosis/README.md section 9
    """

    ACT_NAME = 'hf_reader_test'

    def __init__(self, bundle=None):
        self._test_index = 2  # default HF reader test index
        self._tips_tag = 'hf_reader_tips'
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show instructions and start button.

        From binary HFReaderTestActivity.onCreate:
            1. setTitle("HF reader")
            2. M1="", M2="Start"
            3. Show tips: "Please place Tag with 'IC Test'"
        """
        if isinstance(bundle, dict):
            self._test_index = bundle.get('test_index', 2)

        self.setTitle(resources.get_str('hf_reader_test'))
        self.setLeftButton('')
        self.setRightButton(resources.get_str('start'))

        self.showTips()

    def onKeyEvent(self, key):
        """M2/OK = run test, PWR = exit (fail)."""
        if key in (KEY_M2, KEY_OK):
            self.run_check()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._finish_with_result(False)

    def run_check(self):
        """Send 'hf 14a reader' and parse result."""
        try:
            import executor
            ret = executor.startPM3Task('hf 14a reader', timeout=5888)
            if ret == 1:
                content = ''
                try:
                    content = executor.getPrintContent()
                except Exception:
                    pass
                passed = bool(re.search(r'UID|ATQA|SAK', content))
                self._finish_with_result(passed)
            else:
                self._finish_with_result(False)
        except Exception:
            self._finish_with_result(False)

    def showTips(self):
        """Display placement instructions."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete(self._tips_tag)
        tips = resources.get_str('test_hf_reader_tips')
        canvas.create_text(
            SCREEN_W // 2, SCREEN_H // 2,
            text=tips, fill=TITLE_TEXT_COLOR, anchor='center',
            font=resources.get_font(15),
            tags=self._tips_tag,
        )

    def _finish_with_result(self, passed):
        """Return result to parent and finish."""
        stack = actstack.get_activity_pck()
        if len(stack) >= 2:
            parent = stack[-2]
            if hasattr(parent, 'onData'):
                parent.onData({
                    'test_index': self._test_index,
                    'result': passed,
                })
        self.finish()


# =====================================================================
# LfReaderTestActivity
# =====================================================================

class LfReaderTestActivity(BaseActivity):
    """LF antenna reader test via 'lf sea' + optional 'lf em 410x_watch'.

    Binary source: activity_tools.so LfReaderTestActivity
    Spec: docs/UI_Mapping/09_diagnosis/README.md section 9
    """

    ACT_NAME = 'lf_reader_test'

    def __init__(self, bundle=None):
        self._test_index = 3  # default LF reader test index
        self._tips_tag = 'lf_reader_tips'
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show instructions and start button.

        From binary LfReaderTestActivity.onCreate:
            1. setTitle("LF reader")
            2. M1="", M2="Start"
            3. Show tips: "Please place Tag with 'ID Test'"
        """
        if isinstance(bundle, dict):
            self._test_index = bundle.get('test_index', 3)

        self.setTitle(resources.get_str('lf_reader_test'))
        self.setLeftButton('')
        self.setRightButton(resources.get_str('start'))

        self.showTips()

    def onKeyEvent(self, key):
        """M2/OK = run test, PWR = exit (fail)."""
        if key in (KEY_M2, KEY_OK):
            self.run_check()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._finish_with_result(False)

    def run_check(self):
        """Send 'lf sea' and parse result. Falls back to run_watch if needed."""
        try:
            import executor
            ret = executor.startPM3Task('lf sea', timeout=8888)
            if ret == 1:
                content = ''
                try:
                    content = executor.getPrintContent()
                except Exception:
                    pass
                if re.search(r'Valid|found|TAG ID', content):
                    self._finish_with_result(True)
                else:
                    # Fallback: try EM410x watch
                    self.run_watch()
            else:
                self._finish_with_result(False)
        except Exception:
            self._finish_with_result(False)

    def run_watch(self):
        """Run 'lf em 410x_watch' for live EM tag detection."""
        try:
            import executor
            ret = executor.startPM3Task('lf em 410x_watch', timeout=8888)
            if ret == 1:
                content = ''
                try:
                    content = executor.getPrintContent()
                except Exception:
                    pass
                passed = bool(re.search(r'EM TAG ID|410x', content, re.IGNORECASE))
                self._finish_with_result(passed)
            else:
                self._finish_with_result(False)
        except Exception:
            self._finish_with_result(False)

    def showTips(self):
        """Display placement instructions."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete(self._tips_tag)
        tips = resources.get_str('test_lf_reader_tips')
        canvas.create_text(
            SCREEN_W // 2, SCREEN_H // 2,
            text=tips, fill=TITLE_TEXT_COLOR, anchor='center',
            font=resources.get_font(15),
            tags=self._tips_tag,
        )

    def _finish_with_result(self, passed):
        """Return result to parent and finish."""
        stack = actstack.get_activity_pck()
        if len(stack) >= 2:
            parent = stack[-2]
            if hasattr(parent, 'onData'):
                parent.onData({
                    'test_index': self._test_index,
                    'result': passed,
                })
        self.finish()


# =====================================================================
# UsbPortTestActivity
# =====================================================================

class UsbPortTestActivity(BaseActivity):
    """USB gadget detection test.

    Checks for USB OTG connection at OS level.

    Binary source: activity_tools.so UsbPortTestActivity
    Spec: docs/UI_Mapping/09_diagnosis/README.md section 9
    """

    ACT_NAME = 'usb_port_test'

    def __init__(self, bundle=None):
        self._test_index = 5  # default USB test index
        self._tips_tag = 'usb_test_tips'
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show instructions and start button.

        From binary UsbPortTestActivity.onCreate:
            1. setTitle("USB port")
            2. M1="", M2="Start"
            3. Show tips: "Please connect to charger."
        """
        if isinstance(bundle, dict):
            self._test_index = bundle.get('test_index', 5)

        self.setTitle(resources.get_str('usb_port_test'))
        self.setLeftButton('')
        self.setRightButton(resources.get_str('start'))

        self.showTips()

    def onKeyEvent(self, key):
        """M2/OK = run check, PWR = exit (fail)."""
        if key in (KEY_M2, KEY_OK):
            self.run_check()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finishOnResult(False)

    def run_check(self):
        """Perform OS-level USB detection.

        Checks for USB gadget device presence.
        """
        # On real device: check /sys/class/udc/ or /dev/ttyGS0
        import os
        usb_detected = (
            os.path.exists('/dev/ttyGS0') or
            os.path.exists('/sys/class/udc')
        )
        self.finishOnResult(usb_detected)

    def showTips(self):
        """Display connection instructions."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete(self._tips_tag)
        tips = resources.get_str('test_usb_connect_tips')
        canvas.create_text(
            SCREEN_W // 2, SCREEN_H // 2,
            text=tips, fill=TITLE_TEXT_COLOR, anchor='center',
            font=resources.get_font(15),
            tags=self._tips_tag,
        )

    def finishOnResult(self, passed):
        """Return result to parent DiagnosisActivity and finish."""
        stack = actstack.get_activity_pck()
        if len(stack) >= 2:
            parent = stack[-2]
            if hasattr(parent, 'onData'):
                parent.onData({
                    'test_index': self._test_index,
                    'result': passed,
                })
        self.finish()
