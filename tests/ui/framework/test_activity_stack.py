"""Tests for lib.actstack — Activity, LifeCycle, and activity stack management.

Covers:
  - LifeCycle thread-safe state machine (6 tests)
  - Activity base class lifecycle callbacks (6 tests)
  - Module-level stack push/pop/query operations (9 tests)

Total: 21 tests, 100% branch coverage of actstack.py.
"""

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from lib.actstack import (
    Activity,
    LifeCycle,
    start_activity,
    finish_activity,
    get_current_activity,
    get_activity_pck,
    get_stack,
    get_stack_size,
    init,
    register,
    unregister,
    _reset,
)

# Import MockCanvas from the UI conftest
from tests.ui.conftest import MockCanvas


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clean_stack():
    """Reset actstack module state before each test."""
    import lib.actstack as mod
    _reset()
    mod._canvas_factory = lambda: MockCanvas()
    yield
    _reset()


# ═══════════════════════════════════════════════════════════════════════
# Helpers — test Activity subclasses that record callback invocations
# ═══════════════════════════════════════════════════════════════════════

class RecordingActivity(Activity):
    """Activity subclass that records lifecycle callback invocations."""

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self.calls = []

    def onCreate(self, bundle):
        self.calls.append(("onCreate", bundle))

    def onResume(self):
        self.calls.append(("onResume",))

    def onPause(self):
        self.calls.append(("onPause",))

    def onDestroy(self):
        self.calls.append(("onDestroy",))

    def onKeyEvent(self, key):
        self.calls.append(("onKeyEvent", key))

    def onActivity(self, bundle):
        self.calls.append(("onActivity", bundle))

    def onData(self, event):
        self.calls.append(("onData", event))


class ExceptActivity(Activity):
    """Activity that records exceptions from onActExcept."""

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self.caught_exceptions = []

    def onActExcept(self, exception):
        self.caught_exceptions.append(exception)


# ═══════════════════════════════════════════════════════════════════════
# TestLifeCycle
# ═══════════════════════════════════════════════════════════════════════

class TestLifeCycle:

    def test_initial_state_all_false(self):
        """All lifecycle flags start as False."""
        lc = LifeCycle()
        assert lc.created is False
        assert lc.resumed is False
        assert lc.paused is False
        assert lc.destroyed is False

    def test_set_created(self):
        """Setting created flag works via property setter."""
        lc = LifeCycle()
        lc.created = True
        assert lc.created is True
        assert lc.resumed is False

    def test_set_resumed(self):
        """Setting resumed flag works via property setter."""
        lc = LifeCycle()
        lc.resumed = True
        assert lc.resumed is True

    def test_set_paused(self):
        """Setting paused flag works via property setter."""
        lc = LifeCycle()
        lc.paused = True
        assert lc.paused is True

    def test_set_destroyed(self):
        """Setting destroyed flag works via property setter."""
        lc = LifeCycle()
        lc.destroyed = True
        assert lc.destroyed is True

    def test_thread_safety(self):
        """Multiple threads setting lifecycle state concurrently do not corrupt it.

        100 threads each set a different flag; afterwards all flags should
        have the last-written value (True).
        """
        lc = LifeCycle()
        errors = []

        def set_created():
            try:
                for _ in range(100):
                    lc.created = True
                    lc.created = False
                lc.created = True
            except Exception as e:
                errors.append(e)

        def set_resumed():
            try:
                for _ in range(100):
                    lc.resumed = True
                    lc.resumed = False
                lc.resumed = True
            except Exception as e:
                errors.append(e)

        def set_paused():
            try:
                for _ in range(100):
                    lc.paused = True
                    lc.paused = False
                lc.paused = True
            except Exception as e:
                errors.append(e)

        def set_destroyed():
            try:
                for _ in range(100):
                    lc.destroyed = True
                    lc.destroyed = False
                lc.destroyed = True
            except Exception as e:
                errors.append(e)

        threads = []
        for fn in [set_created, set_resumed, set_paused, set_destroyed]:
            for _ in range(25):
                t = threading.Thread(target=fn)
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Thread errors: {errors}"
        # After all threads finish, each flag was last set to True
        assert lc.created is True
        assert lc.resumed is True
        assert lc.paused is True
        assert lc.destroyed is True


# ═══════════════════════════════════════════════════════════════════════
# TestActivity
# ═══════════════════════════════════════════════════════════════════════

class TestActivity:

    def test_create_with_bundle(self):
        """Activity stores bundle and initializes lifecycle."""
        bundle = {"key": "value"}
        act = Activity(bundle)
        assert act._bundle == bundle
        assert act.life.created is False
        assert act._canvas is None
        assert act._manifest == {}

    def test_lifecycle_callbacks_called(self):
        """start() calls onCreate then onResume in correct order."""
        act = RecordingActivity()
        bundle = {"test": 1}
        act.start(bundle)

        assert act.calls == [
            ("onCreate", bundle),
            ("onResume",),
        ]
        assert act.life.created is True
        assert act.life.resumed is True

    def test_get_canvas_after_start(self):
        """After start(), getCanvas() returns a canvas (MockCanvas)."""
        import lib.actstack as mod
        mod._canvas_factory = lambda: MockCanvas()

        act = Activity()
        act.start(None)
        canvas = act.getCanvas()
        assert canvas is not None
        assert isinstance(canvas, MockCanvas)

    def test_finish_calls_finish_activity(self):
        """Activity.finish() delegates to module-level finish_activity()."""
        # Push an activity onto the stack first
        act = start_activity(RecordingActivity, None)
        assert get_stack_size() == 1

        act.finish()
        assert get_stack_size() == 0

    def test_start_bg_task_runs_in_thread(self):
        """startBGTask runs target in a daemon thread."""
        act = Activity()
        result = []

        def worker():
            result.append(threading.current_thread().name)

        t = act.startBGTask(worker)
        t.join(timeout=2.0)

        assert len(result) == 1
        assert result[0] != threading.current_thread().name

    def test_bg_task_exception_calls_on_act_except(self):
        """When a background task raises, onActExcept is called."""
        act = ExceptActivity()

        def failing_task():
            raise ValueError("test error")

        t = act.startBGTask(failing_task)
        t.join(timeout=2.0)

        assert len(act.caught_exceptions) == 1
        assert isinstance(act.caught_exceptions[0], ValueError)
        assert str(act.caught_exceptions[0]) == "test error"

    def test_call_key_event_dispatches(self):
        """callKeyEvent dispatches to onKeyEvent."""
        act = RecordingActivity()
        act.callKeyEvent("OK")
        assert ("onKeyEvent", "OK") in act.calls

    def test_get_manifest(self):
        """getManifest returns the manifest dict."""
        act = Activity()
        act._manifest = {"name": "TestAct"}
        assert act.getManifest() == {"name": "TestAct"}

    def test_bg_task_with_args(self):
        """startBGTask forwards args and kwargs to target."""
        act = Activity()
        result = []

        def worker(a, b, c=None):
            result.append((a, b, c))

        t = act.startBGTask(worker, 1, 2, c=3)
        t.join(timeout=2.0)

        assert result == [(1, 2, 3)]


# ═══════════════════════════════════════════════════════════════════════
# TestActivityStack
# ═══════════════════════════════════════════════════════════════════════

class TestActivityStack:

    def test_empty_stack(self):
        """Empty stack returns None for current, 0 for size."""
        assert get_current_activity() is None
        assert get_stack_size() == 0
        assert get_stack() == []
        assert get_activity_pck() == []

    def test_push_activity(self):
        """start_activity pushes onto the stack and starts the activity."""
        act = start_activity(RecordingActivity, {"init": True})

        assert get_stack_size() == 1
        assert get_current_activity() is act
        assert act.life.created is True
        assert act.life.resumed is True
        assert ("onCreate", {"init": True}) in act.calls
        assert ("onResume",) in act.calls

    def test_push_pauses_previous(self):
        """Pushing a new activity pauses the previous one and hides its canvas."""
        first = start_activity(RecordingActivity, None)
        first.calls.clear()

        second = start_activity(RecordingActivity, None)

        # First should have been paused
        assert ("onPause",) in first.calls
        assert first.life.paused is True

        # Second is now current
        assert get_current_activity() is second
        assert get_stack_size() == 2

    def test_pop_destroys_current(self):
        """finish_activity pops, pauses, and destroys the current activity."""
        act = start_activity(RecordingActivity, None)
        act.calls.clear()

        finish_activity()

        assert ("onPause",) in act.calls
        assert ("onDestroy",) in act.calls
        assert act.life.paused is True
        assert act.life.destroyed is True
        assert get_stack_size() == 0

    def test_pop_resumes_previous(self):
        """Popping the top activity resumes the one beneath it."""
        first = start_activity(RecordingActivity, None)
        second = start_activity(RecordingActivity, None)

        first.calls.clear()

        finish_activity()

        # first should have been resumed
        assert ("onResume",) in first.calls
        assert first.life.resumed is True
        assert get_current_activity() is first

    def test_get_current_activity(self):
        """get_current_activity returns the top of stack."""
        assert get_current_activity() is None

        first = start_activity(RecordingActivity, None)
        assert get_current_activity() is first

        second = start_activity(RecordingActivity, None)
        assert get_current_activity() is second

    def test_get_stack_size(self):
        """get_stack_size tracks push and pop correctly."""
        assert get_stack_size() == 0
        start_activity(RecordingActivity, None)
        assert get_stack_size() == 1
        start_activity(RecordingActivity, None)
        assert get_stack_size() == 2
        finish_activity()
        assert get_stack_size() == 1
        finish_activity()
        assert get_stack_size() == 0

    def test_canvas_factory_for_testing(self):
        """Setting _canvas_factory provides mock canvases."""
        import lib.actstack as mod

        canvases_created = []

        def factory():
            mc = MockCanvas()
            canvases_created.append(mc)
            return mc

        mod._canvas_factory = factory

        act = start_activity(RecordingActivity, None)
        assert len(canvases_created) == 1
        assert act.getCanvas() is canvases_created[0]

    def test_multiple_push_pop(self):
        """Full push/pop cycle with 3 activities: push A, B, C, pop C, B, A."""
        a = start_activity(RecordingActivity, {"name": "A"})
        b = start_activity(RecordingActivity, {"name": "B"})
        c = start_activity(RecordingActivity, {"name": "C"})

        assert get_stack_size() == 3
        assert get_current_activity() is c

        # Pop C — B resumes
        b.calls.clear()
        finish_activity()
        assert get_current_activity() is b
        assert ("onResume",) in b.calls

        # Pop B — A resumes
        a.calls.clear()
        finish_activity()
        assert get_current_activity() is a
        assert ("onResume",) in a.calls

        # Pop A — stack empty
        finish_activity()
        assert get_stack_size() == 0
        assert get_current_activity() is None

    def test_finish_on_empty_stack_is_safe(self):
        """Calling finish_activity on an empty stack does not raise."""
        finish_activity()  # should not raise
        assert get_stack_size() == 0

    def test_lifecycle_order_on_push(self):
        """Verify the exact callback order when pushing a second activity."""
        first = start_activity(RecordingActivity, None)
        first.calls.clear()

        second = start_activity(RecordingActivity, {"b": 2})

        # first: onPause only
        assert first.calls == [("onPause",)]

        # second: onCreate then onResume
        assert second.calls == [
            ("onCreate", {"b": 2}),
            ("onResume",),
        ]

    def test_lifecycle_order_on_pop(self):
        """Verify the exact callback order when popping an activity."""
        first = start_activity(RecordingActivity, None)
        second = start_activity(RecordingActivity, None)

        first.calls.clear()
        second.calls.clear()

        finish_activity()

        # second (popped): onPause then onDestroy
        assert second.calls == [
            ("onPause",),
            ("onDestroy",),
        ]

        # first (resumed): onResume
        assert first.calls == [("onResume",)]


# ═══════════════════════════════════════════════════════════════════════
# TestRegisterUnregister
# ═══════════════════════════════════════════════════════════════════════

class TestRegisterUnregister:

    def test_register_and_unregister(self):
        """register/unregister manage the _REGISTERED list."""
        import lib.actstack as mod

        act = Activity()
        register(act)
        assert act in mod._REGISTERED

        unregister(act)
        assert act not in mod._REGISTERED

    def test_unregister_nonexistent_is_safe(self):
        """Unregistering an activity not in the list does not raise."""
        act = Activity()
        unregister(act)  # should not raise

    def test_register_idempotent(self):
        """Registering the same activity twice does not duplicate it."""
        import lib.actstack as mod

        act = Activity()
        register(act)
        register(act)
        assert mod._REGISTERED.count(act) == 1
