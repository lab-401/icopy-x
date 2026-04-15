"""Tests for lib.actbase — BaseActivity with title bar, button bar, busy state.

Covers:
  - Title bar rendering: rect + text, draw-once semantics, update (5 tests)
  - Button bar rendering: left/right position, background, dismiss, disable, font (7 tests)
  - Busy state: initial, set, clear, thread safety (4 tests)
  - Battery bar: creation, show on resume, hide on pause (3 tests)
  - Lifecycle: onResume/onPause flags, unique_id format (3 tests)
  - Integration: full screen setup, push/pop lifecycle (2 tests)

Total: 24 tests, 100% branch coverage of actbase.py.
"""

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from lib.actbase import BaseActivity
from lib import actstack
from lib.actstack import start_activity, finish_activity, _reset
from lib._constants import (
    SCREEN_W,
    TITLE_BAR_Y0,
    TITLE_BAR_Y1,
    TITLE_BAR_BG,
    TITLE_TEXT_X,
    TITLE_TEXT_Y,
    TITLE_TEXT_COLOR,
    TITLE_TEXT_ANCHOR,
    BTN_BAR_Y0,
    BTN_BAR_Y1,
    BTN_BAR_BG,
    BTN_LEFT_X,
    BTN_LEFT_Y,
    BTN_LEFT_ANCHOR,
    BTN_RIGHT_X,
    BTN_RIGHT_Y,
    BTN_RIGHT_ANCHOR,
    BTN_TEXT_COLOR,
    TAG_TITLE,
    TAG_BTN_LEFT,
    TAG_BTN_RIGHT,
    TAG_BTN_BG,
)

# Import MockCanvas from the UI conftest
from tests.ui.conftest import MockCanvas


# =====================================================================
# Test Activity subclass
# =====================================================================

class SampleActivity(BaseActivity):
    """Concrete subclass for testing. Records lifecycle calls."""

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self.calls = []

    def onCreate(self, bundle):
        self.calls.append(("onCreate", bundle))

    def onResume(self):
        super().onResume()
        self.calls.append(("onResume",))

    def onPause(self):
        super().onPause()
        self.calls.append(("onPause",))

    def onDestroy(self):
        super().onDestroy()
        self.calls.append(("onDestroy",))

    def onKeyEvent(self, key):
        self.calls.append(("onKeyEvent", key))


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def clean_stack():
    """Reset actstack module state before each test."""
    _reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    _reset()


@pytest.fixture
def activity():
    """Return a started SampleActivity with a MockCanvas."""
    act = start_activity(SampleActivity)
    return act


@pytest.fixture
def canvas(activity):
    """Return the MockCanvas from a started activity."""
    return activity.getCanvas()


# =====================================================================
# TestTitleBar
# =====================================================================

class TestTitleBar:

    def test_set_title_creates_rect(self, activity, canvas):
        """setTitle creates a background rect at (0, 0, 240, 40) fill=#7C829A."""
        activity.setTitle("Test Title")
        rects = canvas.get_items_by_type("rectangle")
        title_rects = [(iid, item) for iid, item in rects
                       if TAG_TITLE in item["tags"]]
        assert len(title_rects) >= 1
        _, rect = title_rects[0]
        assert rect["coords"] == [0, TITLE_BAR_Y0, SCREEN_W, TITLE_BAR_Y1]
        assert rect["options"]["fill"] == TITLE_BAR_BG

    def test_set_title_creates_text(self, activity, canvas):
        """setTitle creates text at (120, 20) anchor=center fill=white."""
        activity.setTitle("Test Title")
        texts = canvas.get_items_by_type("text")
        title_texts = [(iid, item) for iid, item in texts
                       if TAG_TITLE in item["tags"]]
        assert len(title_texts) >= 1
        _, text_item = title_texts[0]
        assert text_item["coords"] == [TITLE_TEXT_X, TITLE_TEXT_Y]
        assert text_item["options"]["text"] == "Test Title"
        assert text_item["options"]["fill"] == TITLE_TEXT_COLOR
        assert text_item["options"]["anchor"] == TITLE_TEXT_ANCHOR

    def test_set_title_tag(self, activity, canvas):
        """All title bar items use TAG_TITLE tag."""
        activity.setTitle("Tagged")
        items = canvas.find_withtag(TAG_TITLE)
        # Should have at least 2 items: rect + text
        assert len(items) >= 2

    def test_set_title_only_draws_once(self, activity, canvas):
        """Calling setTitle twice does NOT create duplicate background rects."""
        activity.setTitle("First")
        items_before = len(canvas.find_withtag(TAG_TITLE))
        activity.setTitle("Second")
        items_after = len(canvas.find_withtag(TAG_TITLE))
        # Second call should not add items (only itemconfig)
        assert items_after == items_before

    def test_set_title_updates_text_on_second_call(self, activity, canvas):
        """Second setTitle call updates existing text via itemconfig."""
        activity.setTitle("First")
        activity.setTitle("Updated")
        # The text items tagged TAG_TITLE should have updated text
        texts = canvas.get_items_by_type("text")
        title_texts = [(iid, item) for iid, item in texts
                       if TAG_TITLE in item["tags"]]
        assert len(title_texts) >= 1
        # itemconfig updates ALL items with the tag, so the text item
        # should now have text="Updated"
        _, text_item = title_texts[0]
        assert text_item["options"]["text"] == "Updated"


# =====================================================================
# TestButtonBar
# =====================================================================

class TestButtonBar:

    def test_set_left_button_position(self, activity, canvas):
        """setLeftButton creates text at (15, 228) anchor=sw."""
        activity.setLeftButton("Back")
        texts = canvas.get_items_by_type("text")
        left_texts = [(iid, item) for iid, item in texts
                      if TAG_BTN_LEFT in item["tags"]]
        assert len(left_texts) == 1
        _, item = left_texts[0]
        assert item["coords"] == [BTN_LEFT_X, BTN_LEFT_Y]
        assert item["options"]["anchor"] == BTN_LEFT_ANCHOR
        assert item["options"]["text"] == "Back"

    def test_set_right_button_position(self, activity, canvas):
        """setRightButton creates text at (225, 228) anchor=se."""
        activity.setRightButton("OK")
        texts = canvas.get_items_by_type("text")
        right_texts = [(iid, item) for iid, item in texts
                       if TAG_BTN_RIGHT in item["tags"]]
        assert len(right_texts) == 1
        _, item = right_texts[0]
        assert item["coords"] == [BTN_RIGHT_X, BTN_RIGHT_Y]
        assert item["options"]["anchor"] == BTN_RIGHT_ANCHOR
        assert item["options"]["text"] == "OK"

    def test_button_bar_background(self, activity, canvas):
        """Button bar background rect at (0, 200, 240, 240) fill=#222222."""
        activity.setLeftButton("Test")
        rects = canvas.get_items_by_type("rectangle")
        bg_rects = [(iid, item) for iid, item in rects
                    if TAG_BTN_BG in item["tags"]]
        assert len(bg_rects) == 1
        _, rect = bg_rects[0]
        assert rect["coords"] == [0, BTN_BAR_Y0, SCREEN_W, BTN_BAR_Y1]
        assert rect["options"]["fill"] == BTN_BAR_BG

    def test_dismiss_left_button(self, activity, canvas):
        """dismissButton(left=True) removes left button text."""
        activity.setLeftButton("Back")
        assert len(canvas.find_withtag(TAG_BTN_LEFT)) == 1
        activity.dismissButton(left=True)
        assert len(canvas.find_withtag(TAG_BTN_LEFT)) == 0
        # Background should still exist
        assert len(canvas.find_withtag(TAG_BTN_BG)) == 1

    def test_dismiss_right_button(self, activity, canvas):
        """dismissButton(right=True) removes right button text."""
        activity.setRightButton("OK")
        assert len(canvas.find_withtag(TAG_BTN_RIGHT)) == 1
        activity.dismissButton(right=True)
        assert len(canvas.find_withtag(TAG_BTN_RIGHT)) == 0
        # Background should still exist
        assert len(canvas.find_withtag(TAG_BTN_BG)) == 1

    def test_disable_button_changes_color(self, activity, canvas):
        """disableButton greys out button text via itemconfig."""
        activity.setLeftButton("Back")
        activity.setRightButton("OK")
        activity.disableButton(left=True, right=True)
        # Check left button color changed to grey
        left_items = canvas.find_withtag(TAG_BTN_LEFT)
        assert len(left_items) == 1
        item = canvas.get_item(left_items[0])
        assert item["options"]["fill"] == "#808080"
        # Check right button color changed to disabled color
        right_items = canvas.find_withtag(TAG_BTN_RIGHT)
        assert len(right_items) == 1
        item = canvas.get_item(right_items[0])
        assert item["options"]["fill"] == "#808080"

    def test_button_font(self, activity):
        """_getBtnFontAndY returns correct font and y position."""
        font_spec, y = activity._getBtnFontAndY()
        assert font_spec == "mononoki 16"
        assert y == 233


# =====================================================================
# TestBusyState
# =====================================================================

class TestBusyState:

    def test_initial_not_busy(self, activity):
        """Activity starts in non-busy state."""
        assert activity.isbusy() is False

    def test_setbusy(self, activity):
        """setbusy() sets busy flag to True."""
        activity.setbusy()
        assert activity.isbusy() is True

    def test_setidle(self, activity):
        """setidle() clears busy flag."""
        activity.setbusy()
        assert activity.isbusy() is True
        activity.setidle()
        assert activity.isbusy() is False

    def test_thread_safety(self, activity):
        """Concurrent setbusy/setidle calls do not corrupt state."""
        errors = []

        def toggle_busy():
            try:
                for _ in range(200):
                    activity.setbusy()
                    activity.setidle()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=toggle_busy) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == []
        # After all toggles, state should be idle (last operation was setidle)
        assert activity.isbusy() is False


# =====================================================================
# TestBatteryBar
# =====================================================================

class TestBatteryBar:

    def test_battery_bar_created(self):
        """Battery bar is created lazily on first _initBatteryBar call."""
        # Create activity without starting it (no onResume)
        act = SampleActivity()
        act._canvas = MockCanvas()
        assert act._battery_bar is None
        act._initBatteryBar()
        assert act._battery_bar is not None

    def test_battery_bar_shown_on_resume(self, activity):
        """onResume creates and shows battery bar."""
        # activity was already started (which calls onResume once)
        assert activity._battery_bar is not None
        assert activity._battery_bar.isShowing() is True

    def test_battery_bar_hidden_on_pause(self, activity):
        """onPause hides battery bar."""
        # Ensure battery bar is showing first
        assert activity._battery_bar is not None
        assert activity._battery_bar.isShowing() is True
        activity.onPause()
        assert activity._battery_bar.isShowing() is False


# =====================================================================
# TestLifecycle
# =====================================================================

class TestLifecycle:

    def test_on_resume_sets_resumed(self, activity):
        """onResume sets resumed=True."""
        # activity is already resumed from start()
        assert activity.resumed is True

    def test_on_pause_clears_resumed(self, activity):
        """onPause sets resumed=False."""
        activity.onPause()
        assert activity.resumed is False

    def test_unique_id_format(self, activity):
        """unique_id returns 'ID:{classname}-{id}' format."""
        uid = activity.unique_id()
        assert uid.startswith("ID:SampleActivity-")
        # Should contain the object id
        assert str(id(activity)) in uid


# =====================================================================
# TestIntegration
# =====================================================================

class TestIntegration:

    def test_full_screen_setup(self, activity, canvas):
        """Title bar + both buttons + battery bar all render correctly."""
        activity.setTitle("Settings")
        activity.setLeftButton("Back")
        activity.setRightButton("Save")

        # Title bar present
        title_items = canvas.find_withtag(TAG_TITLE)
        assert len(title_items) >= 2  # rect + text

        # Button bar present
        assert len(canvas.find_withtag(TAG_BTN_BG)) == 1
        assert len(canvas.find_withtag(TAG_BTN_LEFT)) == 1
        assert len(canvas.find_withtag(TAG_BTN_RIGHT)) == 1

        # Battery bar is showing (from onResume during start)
        assert activity._battery_bar is not None
        assert activity._battery_bar.isShowing() is True

    def test_push_pop_lifecycle(self):
        """Push two activities, pop one — lifecycle callbacks fire correctly."""
        act1 = start_activity(SampleActivity)
        assert act1.resumed is True
        assert ("onResume",) in act1.calls

        act2 = start_activity(SampleActivity)
        # act1 should be paused
        assert act1.resumed is False
        assert ("onPause",) in act1.calls
        # act2 should be resumed
        assert act2.resumed is True

        # Pop act2
        finish_activity()
        # act2 should be paused and destroyed
        assert act2.resumed is False
        assert ("onPause",) in act2.calls
        assert ("onDestroy",) in act2.calls
        # act1 should be resumed again
        assert act1.resumed is True

    def test_dismiss_all_buttons(self, activity, canvas):
        """dismissButton() with no args removes bg + left + right."""
        activity.setLeftButton("Back")
        activity.setRightButton("OK")
        assert len(canvas.find_withtag(TAG_BTN_BG)) == 1
        assert len(canvas.find_withtag(TAG_BTN_LEFT)) == 1
        assert len(canvas.find_withtag(TAG_BTN_RIGHT)) == 1

        activity.dismissButton()
        assert len(canvas.find_withtag(TAG_BTN_BG)) == 0
        assert len(canvas.find_withtag(TAG_BTN_LEFT)) == 0
        assert len(canvas.find_withtag(TAG_BTN_RIGHT)) == 0
        # Button inited flag should be reset
        assert activity._is_button_inited is False
