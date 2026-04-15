"""Tests for MainActivity — root menu of the iCopy-X.

Covers:
  - Menu creation (title, buttons, 14 items, icons, initial selection)
  - Navigation (UP/DOWN scroll, OK/M2 launch, pagination)
  - Activity launch dispatch (registry lookup, missing module handling)
  - Battery bar (shown on resume)
  - Return from child activity (position preserved)

All tests run headless via MockCanvas and actstack._canvas_factory.
Activity classes for launch targets are stubbed.
"""

import os
import sys
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from actbase import BaseActivity
from actmain import MainActivity, _ACTIVITY_REGISTRY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class StubActivity(BaseActivity):
    """Minimal stub activity for launch target testing."""
    launched = False
    launch_count = 0

    def onCreate(self, bundle=None):
        StubActivity.launched = True
        StubActivity.launch_count += 1

    @classmethod
    def reset(cls):
        cls.launched = False
        cls.launch_count = 0


@pytest.fixture(autouse=True)
def reset_actstack():
    """Reset actstack state before each test."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    StubActivity.reset()
    yield
    actstack._reset()


@pytest.fixture
def main_activity():
    """Create and start a MainActivity via actstack."""
    act = actstack.start_activity(MainActivity)
    return act


# ---------------------------------------------------------------------------
# TestMainMenuCreation
# ---------------------------------------------------------------------------

class TestMainMenuCreation:
    """Tests for MainActivity.onCreate rendering."""

    def test_title_is_main_page(self, main_activity):
        """Title bar should say 'Main Page'."""
        canvas = main_activity.getCanvas()
        texts = canvas.get_all_text()
        assert "Main Page" in texts

    def test_right_button_empty(self, main_activity):
        """Right button (M2) should be empty on main menu."""
        canvas = main_activity.getCanvas()
        # M2 is empty on the real device main menu
        right_btn_ids = canvas.find_withtag("tags_btn_right")
        if right_btn_ids:
            for iid in right_btn_ids:
                text = canvas.itemcget(iid, "text")
                assert text == "", f"Right button should be empty, got '{text}'"

    def test_left_button_empty(self, main_activity):
        """Left button (M1) should be empty string on main menu."""
        canvas = main_activity.getCanvas()
        # The left button text should be "" (empty)
        # Check that tags_btn_left items have empty or no text
        left_btn_ids = canvas.find_withtag("tags_btn_left")
        if left_btn_ids:
            for iid in left_btn_ids:
                text = canvas.itemcget(iid, "text")
                assert text == "", f"Left button should be empty, got '{text}'"

    def test_14_menu_items(self, main_activity):
        """ListView should have exactly 14 items."""
        assert main_activity.lv_main_page is not None
        assert len(main_activity.lv_main_page._items) == 14

    def test_item_labels_correct_order(self, main_activity):
        """Menu items should appear in the verified v1.0.90 order."""
        expected = [
            "Auto Copy", "Dump Files", "Scan Tag", "Read Tag",
            "Sniff TRF", "Simulation", "PC-Mode", "Diagnosis",
            "Backlight", "Volume", "About", "Erase Tag",
            "Time Settings", "LUA Script",
        ]
        assert main_activity.lv_main_page._items == expected

    def test_all_items_have_icons(self, main_activity):
        """All 14 items should have icons."""
        expected_icons = [
            "1", "2", "3", "4", "5", "6", "7",
            "diagnosis", "8", "9",
            "list", "erase", "time", "script",
        ]
        icons = main_activity.lv_main_page._icons
        for i, expected in enumerate(expected_icons):
            assert icons[i] == expected, (
                f"Item {i} should have icon '{expected}', got '{icons[i]}'"
            )

    def test_initial_selection_is_0(self, main_activity):
        """Initial selection should be index 0 (Auto Copy)."""
        assert main_activity.lv_main_page.selection() == 0


# ---------------------------------------------------------------------------
# TestMainMenuNavigation
# ---------------------------------------------------------------------------

class TestMainMenuNavigation:
    """Tests for UP/DOWN/OK/M2 key handling."""

    def test_down_scrolls_list(self, main_activity):
        """DOWN key should advance selection by 1."""
        assert main_activity.lv_main_page.selection() == 0
        main_activity.onKeyEvent('DOWN')
        assert main_activity.lv_main_page.selection() == 1

    def test_up_scrolls_list(self, main_activity):
        """UP key should move selection back by 1 (wraps to end from 0)."""
        assert main_activity.lv_main_page.selection() == 0
        main_activity.onKeyEvent('UP')
        # Wraps to last item (index 13)
        assert main_activity.lv_main_page.selection() == 13

    def test_down_wraps_at_end(self, main_activity):
        """DOWN from last item should wrap to first item."""
        main_activity.lv_main_page.setSelection(13)
        main_activity.onKeyEvent('DOWN')
        assert main_activity.lv_main_page.selection() == 0

    def test_up_wraps_at_start(self, main_activity):
        """UP from first item should wrap to last item."""
        assert main_activity.lv_main_page.selection() == 0
        main_activity.onKeyEvent('UP')
        assert main_activity.lv_main_page.selection() == 13

    def test_ok_launches_activity(self, main_activity):
        """OK key should attempt to launch the selected activity."""
        # Patch the registry to use our stub
        import actmain as actmain_mod
        original_registry = actmain_mod._ACTIVITY_REGISTRY.copy()
        actmain_mod._ACTIVITY_REGISTRY['autocopy'] = (
            'tests.ui.activities.test_main_menu', 'StubActivity'
        )
        # Create a stub module entry in sys.modules
        stub_mod = types.ModuleType('tests.ui.activities.test_main_menu')
        stub_mod.StubActivity = StubActivity
        sys.modules['tests.ui.activities.test_main_menu'] = stub_mod

        try:
            main_activity.lv_main_page.setSelection(0)
            main_activity.onKeyEvent('OK')
            assert StubActivity.launched
        finally:
            actmain_mod._ACTIVITY_REGISTRY.update(original_registry)
            sys.modules.pop('tests.ui.activities.test_main_menu', None)

    def test_m2_launches_activity(self, main_activity):
        """M2 key should behave identically to OK."""
        import actmain as actmain_mod
        original_registry = actmain_mod._ACTIVITY_REGISTRY.copy()
        actmain_mod._ACTIVITY_REGISTRY['autocopy'] = (
            'tests.ui.activities.test_main_menu', 'StubActivity'
        )
        stub_mod = types.ModuleType('tests.ui.activities.test_main_menu')
        stub_mod.StubActivity = StubActivity
        sys.modules['tests.ui.activities.test_main_menu'] = stub_mod

        try:
            main_activity.lv_main_page.setSelection(0)
            main_activity.onKeyEvent('M2')
            assert StubActivity.launched
        finally:
            actmain_mod._ACTIVITY_REGISTRY.update(original_registry)
            sys.modules.pop('tests.ui.activities.test_main_menu', None)

    def test_m1_no_action(self, main_activity):
        """M1 on main menu should do nothing (no crash, no state change)."""
        sel_before = main_activity.lv_main_page.selection()
        stack_before = actstack.get_stack_size()
        main_activity.onKeyEvent('M1')
        assert main_activity.lv_main_page.selection() == sel_before
        assert actstack.get_stack_size() == stack_before

    def test_pwr_no_crash(self, main_activity):
        """PWR key should not crash (stub for shutdown flow)."""
        main_activity.onKeyEvent('PWR')
        # Should not raise; main menu is root, PWR does not pop it

    def test_pagination_across_pages(self, main_activity):
        """Navigation should cross page boundaries correctly."""
        lv = main_activity.lv_main_page
        page_size = lv._max_display

        # Start at item 0, page 0
        assert lv.selection() == 0
        assert lv.getPagePosition() == 0

        # Move down page_size times to reach next page
        for _ in range(page_size):
            main_activity.onKeyEvent('DOWN')
        assert lv.selection() == page_size
        assert lv.getPagePosition() == 1

        # Move down page_size more to reach page 2
        for _ in range(page_size):
            main_activity.onKeyEvent('DOWN')
        assert lv.selection() == page_size * 2
        assert lv.getPagePosition() == 2

    def test_busy_blocks_keys(self, main_activity):
        """When busy, key events should be ignored."""
        main_activity.setbusy()
        main_activity.onKeyEvent('DOWN')
        assert main_activity.lv_main_page.selection() == 0
        main_activity.setidle()
        main_activity.onKeyEvent('DOWN')
        assert main_activity.lv_main_page.selection() == 1


# ---------------------------------------------------------------------------
# TestMainMenuActivityLaunch
# ---------------------------------------------------------------------------

class TestMainMenuActivityLaunch:
    """Tests for activity launch dispatch."""

    def _setup_stub_at(self, main_activity, action_key):
        """Wire StubActivity into the registry for a given key."""
        import actmain as actmain_mod
        mod_path = 'stub_act_for_test'
        stub_mod = types.ModuleType(mod_path)
        stub_mod.StubActivity = StubActivity
        sys.modules[mod_path] = stub_mod
        actmain_mod._ACTIVITY_REGISTRY[action_key] = (mod_path, 'StubActivity')
        return mod_path

    def _teardown_stub(self, action_key, mod_path, original_entry):
        """Restore original registry entry."""
        import actmain as actmain_mod
        if original_entry is not None:
            actmain_mod._ACTIVITY_REGISTRY[action_key] = original_entry
        sys.modules.pop(mod_path, None)

    def test_launch_diagnosis(self, main_activity):
        """Index 7 should dispatch to diagnosis action key."""
        import actmain as actmain_mod
        orig = actmain_mod._ACTIVITY_REGISTRY.get('diagnosis')
        mod_path = self._setup_stub_at(main_activity, 'diagnosis')
        try:
            main_activity.lv_main_page.setSelection(7)
            main_activity.onKeyEvent('OK')
            assert StubActivity.launched
        finally:
            self._teardown_stub('diagnosis', mod_path, orig)

    def test_launch_volume(self, main_activity):
        """Index 9 should dispatch to volume action key."""
        import actmain as actmain_mod
        orig = actmain_mod._ACTIVITY_REGISTRY.get('volume')
        mod_path = self._setup_stub_at(main_activity, 'volume')
        try:
            main_activity.lv_main_page.setSelection(9)
            main_activity.onKeyEvent('OK')
            assert StubActivity.launched
        finally:
            self._teardown_stub('volume', mod_path, orig)

    def test_launch_about(self, main_activity):
        """Index 10 should dispatch to about action key."""
        import actmain as actmain_mod
        orig = actmain_mod._ACTIVITY_REGISTRY.get('about')
        mod_path = self._setup_stub_at(main_activity, 'about')
        try:
            main_activity.lv_main_page.setSelection(10)
            main_activity.onKeyEvent('OK')
            assert StubActivity.launched
        finally:
            self._teardown_stub('about', mod_path, orig)

    def test_launch_unknown_no_crash(self, main_activity):
        """Launching an unimplemented activity should not crash."""
        # All default registry entries point to unimplemented modules,
        # so just try launching index 0 with no stub installed
        main_activity.lv_main_page.setSelection(0)
        main_activity.onKeyEvent('OK')
        # Should not raise -- just logs a warning

    def test_return_from_activity_restores_position(self, main_activity):
        """After a child activity finishes, main menu selection is preserved."""
        import actmain as actmain_mod
        orig = actmain_mod._ACTIVITY_REGISTRY.get('diagnosis')
        mod_path = self._setup_stub_at(main_activity, 'diagnosis')

        try:
            # Navigate to item 7 and launch
            main_activity.lv_main_page.setSelection(7)
            main_activity.onKeyEvent('OK')
            assert StubActivity.launched

            # Child is on the stack; pop it
            actstack.finish_activity()

            # Main activity should be back, selection preserved
            assert actstack.get_current_activity() is main_activity
            assert main_activity.lv_main_page.selection() == 7
        finally:
            self._teardown_stub('diagnosis', mod_path, orig)

    def test_launch_all_14_action_keys(self, main_activity):
        """Every menu item maps to a valid action key in the registry."""
        expected_keys = [
            "autocopy", "dump_files", "scan", "read_list",
            "sniff", "simulation", "pcmode", "diagnosis",
            "backlight", "volume", "about", "erase",
            "time_settings", "lua_script",
        ]
        for i, expected_key in enumerate(expected_keys):
            _label, _icon, action_key = main_activity._menu_items[i]
            assert action_key == expected_key, (
                f"Item {i} action key should be '{expected_key}', got '{action_key}'"
            )
            assert action_key in _ACTIVITY_REGISTRY, (
                f"Action key '{action_key}' not in registry"
            )


# ---------------------------------------------------------------------------
# TestMainMenuBattery
# ---------------------------------------------------------------------------

class TestMainMenuBattery:
    """Tests for battery bar integration."""

    def test_battery_bar_shown(self, main_activity):
        """After onCreate + onResume, battery bar should be shown (resumed=True)."""
        # BaseActivity.onResume sets resumed=True and calls _showBatteryBar
        assert main_activity.resumed is True

    def test_battery_updates_on_resume(self, main_activity):
        """onResume should re-show the battery bar."""
        # Simulate pause (child activity pushed)
        main_activity.onPause()
        assert main_activity.resumed is False

        # Resume (child returned)
        main_activity.onResume()
        assert main_activity.resumed is True


# ---------------------------------------------------------------------------
# TestMainMenuJSON
# ---------------------------------------------------------------------------

class TestMainMenuJSON:
    """Tests for the main_menu.json screen definition."""

    @pytest.fixture
    def menu_json(self):
        import json
        json_path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'src', 'screens', 'main_menu.json'
        )
        json_path = os.path.normpath(json_path)
        with open(json_path) as f:
            return json.load(f)

    def test_json_id(self, menu_json):
        assert menu_json["id"] == "main_menu"

    def test_json_title(self, menu_json):
        assert menu_json["screen"]["title"] == "Main Page"

    def test_json_14_items(self, menu_json):
        assert len(menu_json["screen"]["content"]["items"]) == 14

    def test_json_right_button_null(self, menu_json):
        assert menu_json["screen"]["buttons"]["right"] is None

    def test_json_left_button_null(self, menu_json):
        assert menu_json["screen"]["buttons"]["left"] is None

    def test_json_first_item_autocopy(self, menu_json):
        first = menu_json["screen"]["content"]["items"][0]
        assert first["label"] == "Auto Copy"
        assert first["icon"] == "1"
        assert first["action"] == "push:autocopy"

    def test_json_last_item_lua(self, menu_json):
        last = menu_json["screen"]["content"]["items"][-1]
        assert last["label"] == "LUA Script"
        assert last["icon"] is None
        assert last["action"] == "push:lua_script"

    def test_json_icons_first_10_non_null(self, menu_json):
        items = menu_json["screen"]["content"]["items"]
        for i in range(10):
            assert items[i]["icon"] is not None, f"Item {i} should have icon"

    def test_json_icons_last_4_null(self, menu_json):
        items = menu_json["screen"]["content"]["items"]
        for i in range(10, 14):
            assert items[i]["icon"] is None, f"Item {i} should have no icon"

    def test_json_keys_up_down_ok_m2(self, menu_json):
        keys = menu_json["screen"]["keys"]
        assert keys["UP"] == "scroll:-1"
        assert keys["DOWN"] == "scroll:1"
        assert keys["OK"] == "select"
        assert keys["M2"] == "select"
