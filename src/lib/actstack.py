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

"""Activity stack & lifecycle management — replaces actstack.so.

Provides the Activity base class, LifeCycle state machine, and the
module-level navigation stack that manages activity push/pop transitions.

Decompilation source: actstack.so (125KB, 93 functions, 15 Activity +
9 LifeCycle methods).  Every lifecycle transition order matches the
original firmware exactly as documented in decompiled/SUMMARY.md §2.

Import convention: ``from lib.actstack import Activity, start_activity``
or (on-device) ``import actstack`` when ``lib/`` is on sys.path.
"""

import threading
import traceback

from lib._constants import SCREEN_W, SCREEN_H, BG_COLOR


# ═══════════════════════════════════════════════════════════════════════
# LifeCycle — thread-safe lifecycle state machine
# ═══════════════════════════════════════════════════════════════════════

class LifeCycle:
    """Thread-safe lifecycle state machine.

    States: created, resumed, paused, destroyed.
    All state changes are protected by a threading.RLock so that
    concurrent readers (e.g. background tasks) see consistent values.

    Internal attribute names match the decompiled binary:
        _life_created, _life_resumed, _life_paused, _life_destroyed
        _life_lock (RLock)
    """

    def __init__(self):
        self._life_lock = threading.RLock()
        self._life_created = False
        self._life_resumed = False
        self._life_paused = False
        self._life_destroyed = False

    # -- Properties (read under lock) ----------------------------------

    @property
    def created(self) -> bool:
        with self._life_lock:
            return self._life_created

    @created.setter
    def created(self, value: bool):
        self._set_life_in_lock("_life_created", value)

    @property
    def resumed(self) -> bool:
        with self._life_lock:
            return self._life_resumed

    @resumed.setter
    def resumed(self, value: bool):
        self._set_life_in_lock("_life_resumed", value)

    @property
    def paused(self) -> bool:
        with self._life_lock:
            return self._life_paused

    @paused.setter
    def paused(self, value: bool):
        self._set_life_in_lock("_life_paused", value)

    @property
    def destroyed(self) -> bool:
        with self._life_lock:
            return self._life_destroyed

    @destroyed.setter
    def destroyed(self, value: bool):
        self._set_life_in_lock("_life_destroyed", value)

    # -- Internal -------------------------------------------------------

    def _set_life_in_lock(self, attr: str, value: bool):
        """Set a lifecycle flag under the RLock.

        Matches the decompiled ``_set_life_in_lock(self, attr, value)``
        pattern which acquires ``_life_lock`` before writing.
        """
        with self._life_lock:
            setattr(self, attr, value)


# ═══════════════════════════════════════════════════════════════════════
# Activity — base class for all activities
# ═══════════════════════════════════════════════════════════════════════

class Activity:
    """Base activity with lifecycle management.

    Subclassed by BaseActivity (actbase.py) which adds UI rendering
    (title bar, button bar, busy state, battery bar).

    Instance variables match the decompiled binary:
        _canvas  — tkinter Canvas instance (created per-activity)
        life     — LifeCycle instance
        _bundle  — bundle dict passed to onCreate
        _manifest — activity manifest metadata dict
    """

    def __init__(self, bundle=None):
        self._canvas = None
        self.life = LifeCycle()
        self._bundle = bundle
        self.bundle = bundle  # Public — write.so accesses activity.bundle
        self._manifest = {}

    # -- Lifecycle callbacks (override in subclasses) -------------------

    def onCreate(self, bundle):
        """Called when the activity is first created."""
        pass

    def onResume(self):
        """Called when the activity becomes visible / gains focus."""
        pass

    def onPause(self):
        """Called when the activity loses focus (another pushed on top)."""
        pass

    def onDestroy(self):
        """Called when the activity is being destroyed (popped)."""
        pass

    def onKeyEvent(self, key):
        """Called when a key event is dispatched to this activity."""
        pass

    def onActivity(self, bundle):
        """Receives result data from a child activity."""
        pass

    def onData(self, event):
        """Receives data events (e.g. from serial listener)."""
        pass

    # -- Lifecycle management -------------------------------------------

    def start(self, bundle=None):
        """Initialize and start the activity.

        Lifecycle order (from decompiled Activity.start):
            1. Create canvas (240x240, bg, highlightthickness=0, bd=0)
            2. Assign to self._canvas
            3. canvas.grid() — make visible
            4. life.created = True
            5. self.onCreate(bundle)
            6. life.resumed = True
            7. self.onResume()
        """
        canvas = _create_canvas()
        self._canvas = canvas
        if canvas is not None:
            canvas.grid()
        self.life.created = True
        self.onCreate(bundle)
        self.life.resumed = True
        self.onResume()

    def getCanvas(self):
        """Return the activity's Canvas."""
        return self._canvas

    def getManifest(self):
        """Return activity manifest dict."""
        return self._manifest

    def finish(self):
        """Finish this activity — pops it from the stack."""
        finish_activity()

    def callKeyEvent(self, key):
        """Dispatch key event to onKeyEvent."""
        self.onKeyEvent(key)

    def startBGTask(self, target, *args, **kwargs):
        """Run *target* function in a background daemon thread.

        Wraps the call in try/except; on exception calls onActExcept.
        Uses ``traceback.format_exc()`` for error reporting (matches
        the decompiled ``catch_run`` wrapper).
        """
        activity = self  # closure reference

        def _catch_run():
            try:
                target(*args, **kwargs)
            except Exception as exc:
                activity.onActExcept(exc)

        t = threading.Thread(target=_catch_run, daemon=True)
        t.start()
        return t

    def onActExcept(self, exception):
        """Handle exception from background task. Override in subclass."""
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════
# Module-level activity stack
# ═══════════════════════════════════════════════════════════════════════

_ACTIVITY_STACK = []
"""The activity back-stack.  Accessed by external .so modules
(e.g. server_iclassse.so) so it must remain a plain list at module level."""

_root = None
"""The root tkinter Tk instance — set during app init."""

_main_frame = None
"""The main frame / container widget — set during app init."""

_canvas_factory = None
"""Optional factory function for testing.  When set, _create_canvas()
calls this instead of creating a real tkinter.Canvas.  Set externally:
    actstack._canvas_factory = lambda: MockCanvas()
"""


def init(root, main_frame=None):
    """Initialize the activity system with the tkinter root window.

    Called once at app startup.  For headless testing, pass ``None``
    and set ``_canvas_factory`` instead.
    """
    global _root, _main_frame
    _root = root
    _main_frame = main_frame or root


def _create_canvas():
    """Create a new Canvas for an activity.

    Priority:
        1. _canvas_factory (testing hook)
        2. Real tkinter.Canvas on _main_frame (or _root)
        3. None (headless / no display)
    """
    if _canvas_factory:
        return _canvas_factory()
    if _root:
        import tkinter
        parent = _main_frame or _root
        c = tkinter.Canvas(
            parent,
            width=SCREEN_W,
            height=SCREEN_H,
            bg=BG_COLOR,
            highlightthickness=0,
            bd=0,
        )
        return c
    return None


def start_activity(activity_cls, bundle=None):
    """Push a new activity onto the stack.

    Lifecycle order (from decompiled start_activity):
        1. new_act = activity_cls(bundle)
        2. If stack not empty:
           a. prev_act = _ACTIVITY_STACK[-1]
           b. prev_act.onPause()
           c. prev_act.life.paused = True
           d. prev_act._canvas.grid_remove()  — hide previous canvas
        3. _ACTIVITY_STACK.append(new_act)
        4. new_act.start(bundle) — creates canvas, onCreate, onResume
    """
    new_act = activity_cls(bundle)
    if _ACTIVITY_STACK:
        prev_act = _ACTIVITY_STACK[-1]
        prev_act.onPause()
        prev_act.life.paused = True
        if prev_act._canvas is not None:
            prev_act._canvas.grid_remove()
    _ACTIVITY_STACK.append(new_act)
    new_act.start(bundle)
    return new_act


def finish_activity():
    """Pop the current activity from the stack.

    Lifecycle order (from decompiled finish_activity):
        1. act = _ACTIVITY_STACK.pop()
        2. act.onPause()
        3. act.life.paused = True
        4. act.onDestroy()
        5. act.life.destroyed = True
        6. act._canvas.grid_remove()
        7. act._canvas.destroy()
        8. If stack not empty:
           a. prev_act = _ACTIVITY_STACK[-1]
           b. prev_act.onResume()
           c. prev_act.life.resumed = True
           d. prev_act._canvas.grid()  — show previous canvas
    """
    if not _ACTIVITY_STACK:
        return
    act = _ACTIVITY_STACK.pop()
    # Capture result before destroying the activity
    result = getattr(act, '_result', None)
    act.onPause()
    act.life.paused = True
    act.onDestroy()
    act.life.destroyed = True

    # PM3 pipeline cleanup is handled by individual activities that need it
    # (e.g. WipeTagActivity, WriteActivity) in their onDestroy methods.
    # Global rework here is too aggressive — it drops the HF field on
    # internal transitions and can crash during app shutdown.

    if act._canvas is not None:
        act._canvas.grid_remove()
        act._canvas.destroy()
    if _ACTIVITY_STACK:
        prev_act = _ACTIVITY_STACK[-1]
        prev_act.onResume()
        prev_act.life.resumed = True
        if prev_act._canvas is not None:
            prev_act._canvas.grid()
        # Pass result from finished activity to parent via onActivity()
        # Ground truth: WarningM1Activity sets self._result before finish(),
        # parent ReadActivity receives it via onActivity(result).
        if result is not None:
            try:
                prev_act.onActivity(result)
            except Exception:
                pass


def get_current_activity():
    """Get the activity on top of the stack, or None."""
    return _ACTIVITY_STACK[-1] if _ACTIVITY_STACK else None


def get_activity_pck():
    """Return the activity stack (list).

    Named to match the decompiled export ``get_activity_pck``.
    """
    return _ACTIVITY_STACK


def get_stack():
    """Get the full stack (list).  Alias for get_activity_pck."""
    return _ACTIVITY_STACK


def get_stack_size():
    """Number of activities on the stack."""
    return len(_ACTIVITY_STACK)


# -- Registration stubs ------------------------------------------------
# actbase.BaseActivity calls register(self) in __init__ and
# unregister(self) in onDestroy.  The decompiled actstack.so does NOT
# export these symbols — they are likely lightweight bookkeeping that
# actbase performs via the stack list itself.  We provide no-op stubs
# so that actbase can call them without error.

_REGISTERED = []
"""Optional activity registry — separate from the stack.  actbase
calls register() in __init__ (before the activity is pushed) and
unregister() in onDestroy (after the activity is popped)."""


def register(activity):
    """Register an activity instance (called from actbase.__init__)."""
    if activity not in _REGISTERED:
        _REGISTERED.append(activity)


def unregister(activity):
    """Unregister an activity instance (called from actbase.onDestroy)."""
    try:
        _REGISTERED.remove(activity)
    except ValueError:
        pass


def get_registered():
    """Return the list of registered activities (for debugging)."""
    return _REGISTERED


# -- Stack reset (testing only) ----------------------------------------

def _reset():
    """Reset all module state.  For testing only."""
    global _root, _main_frame, _canvas_factory
    _ACTIVITY_STACK.clear()
    _REGISTERED.clear()
    _root = None
    _main_frame = None
    _canvas_factory = None
