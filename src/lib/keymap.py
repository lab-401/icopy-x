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

"""Key event dispatcher — replaces keymap.so.

Central key event translation and dispatch.  The HMI driver calls
``key.onKey(raw_event)`` when a hardware button press arrives over
UART.  KeyEvent translates the raw code to a logical key constant
(UP, DOWN, OK, ...) then dispatches to the bound activity's
``callKeyEvent()`` method.

PWR is dispatched to ``onKeyEvent()`` like all other keys.
Each activity handles PWR in its own ``onKeyEvent()``.

"""

import logging
import threading

from lib._constants import (
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
    KEY_SHUTDOWN, KEY_ALL, KEY_APO,
)

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────
# Re-export key constants at module level for compat
# (original keymap.so exposes UP, DOWN, OK, etc.)
# ───────────────────────────────────────────────────
UP = KEY_UP
DOWN = KEY_DOWN
LEFT = KEY_LEFT
RIGHT = KEY_RIGHT
OK = KEY_OK
M1 = KEY_M1
M2 = KEY_M2
POWER = KEY_PWR
SHUTDOWN = KEY_SHUTDOWN
ALL = KEY_ALL
APO = KEY_APO

# ───────────────────────────────────────────────────
# Hardware-to-logical key translation table
# ───────────────────────────────────────────────────
# Three hardware formats:
#   v1.0.90:  KEYOK_PRES!   (KEY prefix, newer GD32)
#   Legacy:   OK_PRES!      (no prefix, older GD32)
#   Direct:   OK            (already logical, e.g. from emulation)
_COMPAT_MAP = {
    # v1.0.90 format (KEY prefix — newer GD32, HW 1.7)
    'KEYOK_PRES!':        OK,
    'KEYM1_PRES!':        M1,
    'KEYM2_PRES!':        M2,
    'KEYUP_PRES!':        UP,
    'KEYDOWN_PRES!':      DOWN,
    'KEYLEFT_PRES!':      LEFT,
    'KEYRIGHT_PRES!':     RIGHT,
    'KEY_PWR_CAN_PRES!':  POWER,

    # Legacy format (no prefix — older GD32, HW 1.0.4)
    'OK_PRES!':           OK,
    'M1_PRES!':           M1,
    'M2_PRES!':           M2,
    'UP_PRES!':           UP,
    'DOWN_PRES!':         DOWN,
    'LEFT_PRES!':         LEFT,
    'RIGHT_PRES!':        RIGHT,

    # PWR variants
    'PWR_PRES!':          POWER,
    'KEYPWR_PRES!':       POWER,
    '_PWR_CAN_PRES!':     POWER,
    'PWR_CAN_PRES!':      POWER,

    # ALL key — S-R/W button (bottom-right physical button)
    # Hardware code from logic analyser: KEY_ALL_PRES!
    'KEY_ALL_PRES!':      ALL,
    '_ALL_PRES!':         ALL,
    'KEYALL_PRES!':       ALL,
    'ALL_PRES!':          ALL,

    # Direct format (already logical — pass-through)
    'OK':                 OK,
    'M1':                 M1,
    'M2':                 M2,
    'UP':                 UP,
    'DOWN':               DOWN,
    'LEFT':               LEFT,
    'RIGHT':              RIGHT,
    'PWR':                POWER,

    # Special keys
    'SHUTDOWN':           SHUTDOWN,
    'ALL':                ALL,
    'APO':                APO,
}

class KeyEvent:
    """Central key event dispatcher.

    The HMI driver calls ``onKey()`` when a hardware key is pressed.
    KeyEvent translates hardware codes to logical key names, then
    dispatches to the bound activity's ``callKeyEvent()``.

    PWR is dispatched to onKeyEvent like all other keys. Each activity
    handles PWR in its own onKeyEvent (finish, cancel, hide console, etc.).
    Ground truth: original keymap.so's _run_shutdown runs 'sudo shutdown -t 0'
    (system shutdown), NOT activity pop. Activity pop is per-activity logic.
    """

    def __init__(self):
        self._target = None          # Currently bound activity
        self._lock = threading.Lock()
        self._shutdown_callback = None

    def bind(self, target):
        """Bind an activity to receive key events.

        *target* must have a ``callKeyEvent(key)`` method.
        """
        with self._lock:
            self._target = target

    def unbind(self):
        """Remove current binding."""
        with self._lock:
            self._target = None

    def onKey(self, event: str):
        """Called by HMI driver when key is pressed.

        *event* is a raw key code from hardware (e.g. ``'KEYOK_PRES!'``).
        Translates via ``_compat()``, then dispatches to bound activity.

        Key dispatch is scheduled on the Tk main thread via root.after()
        because callKeyEvent() triggers UI operations (canvas destroy,
        toast show, activity transitions) which must run on the main
        thread — Tkinter is not thread-safe.
        """
        logical = self._compat(event)
        if logical is None:
            logger.debug("Unknown key event ignored: %r", event)
            return

        with self._lock:
            target = self._target

        if target is not None:
            try:
                from lib import actstack
                if actstack._root is not None:
                    actstack._root.after(0, target.callKeyEvent, logical)
                else:
                    target.callKeyEvent(logical)
            except Exception:
                logger.exception("Error dispatching key %s to %r", logical, target)

    def _compat(self, event: str) -> str:
        """Translate hardware key code to logical key constant.

        Returns the logical key string (UP, DOWN, OK, ...) or ``None``
        if the event is not recognised.
        """
        return _COMPAT_MAP.get(event)

    def _run_shutdown(self):
        """Perform graceful system shutdown.

        Source: keymap_strings.txt lines 623-636:
            _run_shutdown → shutdowning, stopscreen, sudo shutdown -t 0
        """
        try:
            from lib import hmi_driver
            hmi_driver.shutdowning()
            hmi_driver.stopscreen()
        except Exception:
            logger.exception("Error in shutdown serial commands")
        import os
        os.system("sudo shutdown -t 0")

# ───────────────────────────────────────────────────
# Module-level singleton — this is what other modules import
# ───────────────────────────────────────────────────
key = KeyEvent()
