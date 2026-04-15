"""I-1: Full-stack boot and navigation integration tests.

Validates the entire UI stack end-to-end:
  actstack -> actbase -> actmain (MainActivity) -> child activities

Tests that the activity stack, lifecycle, canvas switching, and key
dispatch all work together correctly -- not just in isolation.
"""

import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from actbase import BaseActivity
from actmain import MainActivity, _ACTIVITY_REGISTRY
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


# ===================================================================
# Collect ALL activity classes for parametrized PWR tests
# ===================================================================

def _collect_all_activity_classes():
    """Import and return all BaseActivity subclasses from the codebase.

    Returns a list of (class, needs_bundle) tuples.  Activities that
    require special external modules (executor, PM3, scan cache) are
    included -- they should still handle PWR correctly even if their
    onCreate partially fails.
    """
    classes = []

    # activity_main.py
    from activity_main import (
        BacklightActivity,
        VolumeActivity,
        SleepModeActivity,
        AboutActivity,
        WarningDiskFullActivity,
        ConsolePrinterActivity,
        ScanActivity,
        PCModeActivity,
        TimeSyncActivity,
        LUAScriptCMDActivity,
        ReadListActivity,
        WipeTagActivity,
        SniffActivity,
        WarningWriteActivity,
        WriteActivity,
        WarningM1Activity,
        AutoCopyActivity,
        SimulationActivity,
        SimulationTraceActivity,
        CardWalletActivity,
        KeyEnterM1Activity,
        UpdateActivity,
        OTAActivity,
        SniffForMfReadActivity,
        SniffForT5XReadActivity,
        SniffForSpecificTag,
        IClassSEActivity,
        WearableDeviceActivity,
        ReadFromHistoryActivity,
        AutoExceptCatchActivity,
        SnakeGameActivity,
        WarningT5XActivity,
        WarningT5X4X05KeyEnterActivity,
    )
    classes.extend([
        BacklightActivity,
        VolumeActivity,
        SleepModeActivity,
        AboutActivity,
        WarningDiskFullActivity,
        ConsolePrinterActivity,
        ScanActivity,
        PCModeActivity,
        TimeSyncActivity,
        LUAScriptCMDActivity,
        ReadListActivity,
        WipeTagActivity,
        SniffActivity,
        WarningWriteActivity,
        WriteActivity,
        WarningM1Activity,
        AutoCopyActivity,
        SimulationActivity,
        SimulationTraceActivity,
        CardWalletActivity,
        KeyEnterM1Activity,
        UpdateActivity,
        OTAActivity,
        SniffForMfReadActivity,
        SniffForT5XReadActivity,
        SniffForSpecificTag,
        IClassSEActivity,
        WearableDeviceActivity,
        ReadFromHistoryActivity,
        AutoExceptCatchActivity,
        SnakeGameActivity,
        WarningT5XActivity,
        WarningT5X4X05KeyEnterActivity,
    ])

    # activity_tools.py
    from activity_tools import (
        DiagnosisActivity,
        ScreenTestActivity,
        ButtonTestActivity,
        SoundTestActivity,
        HFReaderTestActivity,
        LfReaderTestActivity,
        UsbPortTestActivity,
    )
    classes.extend([
        DiagnosisActivity,
        ScreenTestActivity,
        ButtonTestActivity,
        SoundTestActivity,
        HFReaderTestActivity,
        LfReaderTestActivity,
        UsbPortTestActivity,
    ])

    # activity_read.py
    from activity_read import ReadActivity
    classes.append(ReadActivity)

    # actmain.py
    # MainActivity is NOT included -- it is the root and PWR does NOT
    # call finish() on it (it triggers sleep/shutdown instead).

    return classes


ALL_ACTIVITIES = _collect_all_activity_classes()


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def main_activity():
    """Boot MainActivity via actstack (full lifecycle)."""
    return actstack.start_activity(MainActivity)


# ===================================================================
# Menu item -> expected activity class name mapping
# ===================================================================

# Maps menu index to (expected_title, expected_class_name)
# Some activities may not be importable; we test only the ones that are.
MENU_EXPECTED = [
    (0,  "autocopy",    "AutoCopyActivity"),
    (1,  "dump_files",  "CardWalletActivity"),
    (2,  "scan",        "ScanActivity"),
    (3,  "read_list",   "ReadListActivity"),
    (4,  "sniff",       "SniffActivity"),
    (5,  "simulation",  "SimulationActivity"),
    (6,  "pcmode",      "PCModeActivity"),
    (7,  "diagnosis",   "DiagnosisActivity"),
    (8,  "backlight",   "BacklightActivity"),
    (9,  "volume",      "VolumeActivity"),
    (10, "about",       "AboutActivity"),
    (11, "erase",       "WipeTagActivity"),
    (12, "time_settings", "TimeSyncActivity"),
    (13, "lua_script",  "LUAScriptCMDActivity"),
]


# ===================================================================
# TestFullStackBoot
# ===================================================================

class TestFullStackBoot:
    """Validate the entire stack: actstack -> actbase -> actmain -> activities."""

    def test_main_activity_boots(self, main_activity):
        """MainActivity creates and renders correctly."""
        # Stack should have exactly 1 activity
        assert actstack.get_stack_size() == 1
        assert actstack.get_current_activity() is main_activity

        # Lifecycle: created and resumed
        assert main_activity.life.created is True
        assert main_activity.life.resumed is True

        # Canvas was created
        canvas = main_activity.getCanvas()
        assert canvas is not None

        # Title "Main Page" present
        texts = canvas.get_all_text()
        assert "Main Page" in texts

        # 14 items in ListView
        assert main_activity.lv_main_page is not None
        assert len(main_activity.lv_main_page._items) == 14

        # Main menu has no M2 button label (setRightButton(""))
        # Verify menu items are visible instead
        assert "Auto Copy" in texts

    def test_navigate_to_each_menu_item(self, main_activity):
        """From main menu, navigate DOWN to each activity and verify launch."""
        for index, action_key, expected_cls_name in MENU_EXPECTED:
            # Resolve the activity class -- skip if not importable
            act_cls = main_activity._getActivityClass(action_key)
            if act_cls is None:
                continue

            # Navigate to position: DOWN from 0 to index
            # Reset selection to 0 first by going back to main
            main_activity.lv_main_page.setSelection(0)

            for _ in range(index):
                main_activity.onKeyEvent(KEY_DOWN)

            # Verify selection
            assert main_activity.lv_main_page.selection() == index, (
                f"Expected selection at {index} for {action_key}"
            )

            # Press OK to launch
            before_depth = actstack.get_stack_size()
            main_activity.onKeyEvent(KEY_OK)

            # Stack should be deeper by 1
            assert actstack.get_stack_size() == before_depth + 1, (
                f"Activity '{action_key}' did not push onto stack"
            )

            # Top of stack should be the expected class
            top = actstack.get_current_activity()
            assert top.__class__.__name__ == expected_cls_name, (
                f"Expected {expected_cls_name}, got {top.__class__.__name__}"
            )

            # Main activity should be paused
            assert main_activity.life.paused is True

            # Go back: finish the child activity
            actstack.finish_activity()

            # Main activity should be resumed and current again
            assert actstack.get_current_activity() is main_activity
            assert actstack.get_stack_size() == before_depth

    def test_deep_navigation(self, main_activity):
        """Main -> Backlight -> back -> verify Main restored."""
        # Navigate to Backlight (index 8 in the menu)
        main_activity.lv_main_page.setSelection(8)
        main_activity.onKeyEvent(KEY_OK)

        # Should be on BacklightActivity
        top = actstack.get_current_activity()
        assert top.__class__.__name__ == 'BacklightActivity'
        assert actstack.get_stack_size() == 2

        # Main is paused
        assert main_activity.life.paused is True

        # Go back
        actstack.finish_activity()

        # Back at Main
        assert actstack.get_current_activity() is main_activity
        assert actstack.get_stack_size() == 1
        assert main_activity.life.resumed is True

        # Main canvas should have its content
        texts = main_activity.getCanvas().get_all_text()
        assert "Main Page" in texts

    def test_pwr_always_returns_toward_main(self, main_activity):
        """PWR from any child depth returns toward main."""
        from keymap import key as key_event

        # Navigate to Backlight (index 8 in the menu)
        main_activity.lv_main_page.setSelection(8)
        main_activity.onKeyEvent(KEY_OK)
        assert actstack.get_stack_size() == 2

        # Bind key events to current activity
        top = actstack.get_current_activity()
        key_event.bind(top)

        # PWR should finish the current activity
        key_event.onKey('PWR')
        assert actstack.get_stack_size() == 1
        assert actstack.get_current_activity() is main_activity


# ===================================================================
# TestNavigationStack
# ===================================================================

class TestNavigationStack:
    """Validate push/pop lifecycle ordering."""

    def test_push_pauses_previous(self, main_activity):
        """Pushing a new activity pauses the previous one."""
        assert main_activity.life.resumed is True
        assert main_activity.life.paused is False

        # Push a child
        from activity_main import BacklightActivity
        child = actstack.start_activity(BacklightActivity)

        # Main should be paused
        assert main_activity.life.paused is True
        # Child should be resumed
        assert child.life.created is True
        assert child.life.resumed is True

    def test_pop_resumes_previous(self, main_activity):
        """Popping an activity resumes the previous one."""
        from activity_main import VolumeActivity
        child = actstack.start_activity(VolumeActivity)

        # Main is paused
        assert main_activity.life.paused is True

        # Pop the child
        actstack.finish_activity()

        # Main should be resumed again
        assert main_activity.life.resumed is True
        assert actstack.get_current_activity() is main_activity

    def test_stack_depth_tracking(self, main_activity):
        """Stack depth increases on push and decreases on pop."""
        assert actstack.get_stack_size() == 1

        from activity_main import BacklightActivity, VolumeActivity

        actstack.start_activity(BacklightActivity)
        assert actstack.get_stack_size() == 2

        actstack.start_activity(VolumeActivity)
        assert actstack.get_stack_size() == 3

        actstack.finish_activity()
        assert actstack.get_stack_size() == 2

        actstack.finish_activity()
        assert actstack.get_stack_size() == 1

    def test_canvas_switching_on_push_pop(self, main_activity):
        """Each activity gets its own canvas; they are distinct objects."""
        main_canvas = main_activity.getCanvas()
        assert main_canvas is not None

        from activity_main import AboutActivity
        child = actstack.start_activity(AboutActivity)
        child_canvas = child.getCanvas()

        # Different canvas objects
        assert child_canvas is not main_canvas

        # Pop and verify main still has its canvas
        actstack.finish_activity()
        assert main_activity.getCanvas() is main_canvas

    def test_lifecycle_order_on_push(self, main_activity):
        """Push sequence: prev.onPause -> new.onCreate -> new.onResume."""
        from activity_main import AboutActivity

        # Record lifecycle event ordering
        events = []

        orig_pause = main_activity.onPause
        def track_pause():
            events.append('main.onPause')
            orig_pause()
        main_activity.onPause = track_pause

        orig_about_create = AboutActivity.onCreate
        orig_about_resume = AboutActivity.onResume

        def patched_create(self, bundle=None):
            events.append('child.onCreate')
            orig_about_create(self, bundle)

        def patched_resume(self):
            events.append('child.onResume')
            orig_about_resume(self)

        AboutActivity.onCreate = patched_create
        AboutActivity.onResume = patched_resume
        try:
            actstack.start_activity(AboutActivity)
            assert events == ['main.onPause', 'child.onCreate', 'child.onResume']
        finally:
            AboutActivity.onCreate = orig_about_create
            AboutActivity.onResume = orig_about_resume

    def test_lifecycle_order_on_pop(self, main_activity):
        """Pop sequence: act.onPause -> act.onDestroy -> prev.onResume."""
        from activity_main import AboutActivity
        child = actstack.start_activity(AboutActivity)

        events = []

        orig_child_pause = child.onPause
        orig_child_destroy = child.onDestroy
        orig_main_resume = main_activity.onResume

        def track_child_pause():
            events.append('child.onPause')
            orig_child_pause()
        def track_child_destroy():
            events.append('child.onDestroy')
            orig_child_destroy()
        def track_main_resume():
            events.append('main.onResume')
            orig_main_resume()

        child.onPause = track_child_pause
        child.onDestroy = track_child_destroy
        main_activity.onResume = track_main_resume

        actstack.finish_activity()
        assert events == ['child.onPause', 'child.onDestroy', 'main.onResume']


# ===================================================================
# TestPWRAlwaysExits
# ===================================================================

class TestPWRAlwaysExits:
    """PWR key MUST exit every activity. Parametrized over all activity classes.

    PWR is dispatched via callKeyEvent() to onKeyEvent(), where each
    activity handles it (usually via _handlePWR() then finish()).
    Activities that show toasts on create may need multiple PWR presses:
    the first dismisses the toast, the second exits.
    Activities like ButtonTestActivity and ScanActivity (in SCANNING state)
    handle PWR specially and are excluded from this test.
    """

    # Activities where PWR does NOT immediately exit:
    # - ButtonTestActivity: records PWR as a button press, never calls finish
    # - ScanActivity: ignores all keys while in SCANNING state (auto-starts scan)
    # - AutoCopyActivity: auto-starts scan with setbusy(), PWR swallowed
    # - ReadActivity: auto-starts scan on create, SCANNING state ignores all keys
    _PWR_EXCEPTIONS = {
        'ButtonTestActivity',   # PWR is recorded as a button press
        'ScanActivity',         # SCANNING state ignores all keys
        'AutoCopyActivity',     # auto-starts scan with setbusy()
        'ReadActivity',         # auto-starts scan, SCANNING state ignores all keys
    }

    @pytest.mark.parametrize(
        "activity_cls",
        ALL_ACTIVITIES,
        ids=lambda c: c.__name__,
    )
    def test_pwr_exits(self, activity_cls):
        """PWR via keymap.key.onKey('PWR') pops the activity from the stack.

        Activities that show a toast on create need two PWR presses:
        the first dismisses the toast (_handlePWR returns True),
        the second triggers finish().
        """
        if activity_cls.__name__ in self._PWR_EXCEPTIONS:
            pytest.skip(
                f"{activity_cls.__name__} handles PWR specially "
                f"(not a simple exit)"
            )

        from keymap import key as key_event

        # Push a root activity first (so there is something to return to)
        root = actstack.start_activity(MainActivity)
        assert actstack.get_stack_size() == 1

        # Push the activity under test
        child = actstack.start_activity(activity_cls)
        assert actstack.get_stack_size() == 2

        # Bind key events to the child
        key_event.bind(child)

        # Send PWR up to 3 times — activities with toasts or busy states
        # may swallow the first PWR (dismissing toast or clearing busy),
        # then exit on the second.
        for _ in range(3):
            key_event.onKey('PWR')
            if actstack.get_stack_size() == 1:
                break

        # Stack should be back to 1 (root only)
        assert actstack.get_stack_size() == 1, (
            f"PWR did not exit {activity_cls.__name__}: "
            f"stack size is {actstack.get_stack_size()}"
        )

        # Root should be current
        assert actstack.get_current_activity() is root
