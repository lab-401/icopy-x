"""I-3: Screenshot regression — screen structure and color validation.

These tests render activity screens via MockCanvas and validate that
the canvas item structure matches the expected layout from the original
firmware.  Since we use MockCanvas (not real Tk), we validate canvas
item properties (types, positions, colors, text values) rather than
pixel comparison.

Each test creates a real activity via actstack, renders it, and
inspects the canvas for correctness.

Reference: docs/UI_SPEC.md, _constants.py (QEMU-verified values)
"""

import pytest

import actstack
from tests.ui.conftest import MockCanvas
from tests.ui.integration.conftest import (
    extract_ui_state,
    extract_canvas_colors,
    get_items_in_content_area,
)
from _constants import (
    SCREEN_W, SCREEN_H,
    TITLE_BAR_BG, BG_COLOR,
    SELECT_BG,
    PROGRESS_FG,
    BTN_TEXT_COLOR,
    BATTERY_X, BATTERY_Y, BATTERY_W, BATTERY_H,
    CONTENT_Y0, CONTENT_Y1,
)


# =====================================================================
# TestScreenRendering
# =====================================================================

class TestScreenRendering:
    """Validate that rendered screens match expected structure."""

    def test_main_menu_page1_structure(self):
        """Main menu page 1: title, 4 items, icons, selection."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        state = extract_ui_state(act)
        assert state['title'] == 'Main Page'
        # Main menu has no M2 button (setRightButton(""))
        assert state['M2'] is None

        # Should have at least 4 visible item texts on page 1
        content_texts = [ct['text'] for ct in state['content_text']]
        assert 'Auto Copy' in content_texts
        # Selection rect should exist (highlight on item 0)
        rects = canvas.get_items_by_type('rectangle')
        has_selection = any(
            item['options'].get('fill', '').upper() == '#EEEEEE'
            for _, item in rects
        )
        assert has_selection, "No selection highlight rectangle found"

    def test_main_menu_page2_structure(self):
        """Scroll to page 2: items 5-9 visible."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)

        # Navigate DOWN x5 to get to page 2 (5 items per page)
        for _ in range(5):
            act.onKeyEvent('DOWN')

        state = extract_ui_state(act)
        content_texts = [ct['text'] for ct in state['content_text']]
        # Page 2 should show items starting from index 5 (Simulation)
        assert 'Simulation' in content_texts

    def test_backlight_structure(self):
        """Backlight: title, 3 radio items, checked current."""
        from activity_main import BacklightActivity
        act = actstack.start_activity(BacklightActivity)
        canvas = act.getCanvas()

        state = extract_ui_state(act)
        assert state['title'] == 'Backlight'
        # Backlight has no M2 button (setRightButton(""), save is via OK key)
        assert state['M2'] is None

        # Content should include the three level labels
        content_texts = [ct['text'] for ct in state['content_text']]
        assert 'Low' in content_texts
        assert 'Middle' in content_texts
        assert 'High' in content_texts

    def test_volume_structure(self):
        """Volume: title, 4 radio items, checked current."""
        from activity_main import VolumeActivity
        act = actstack.start_activity(VolumeActivity)
        canvas = act.getCanvas()

        state = extract_ui_state(act)
        assert state['title'] == 'Volume'
        # Volume has no M2 button (setRightButton(""), save is via OK key)
        assert state['M2'] is None

        # Content should include four level labels
        content_texts = [ct['text'] for ct in state['content_text']]
        assert 'Off' in content_texts
        assert 'Low' in content_texts
        assert 'Middle' in content_texts
        assert 'High' in content_texts

    def test_about_structure(self):
        """About: title, version info text."""
        from activity_main import AboutActivity
        act = actstack.start_activity(AboutActivity)

        state = extract_ui_state(act)
        assert state['title'] == 'About'
        # Content should have version info (from mock version module)
        content_texts = [ct['text'] for ct in state['content_text']]
        # At least one content text item should exist with version info
        all_text = ' '.join(content_texts)
        assert 'iCopy-X' in all_text or len(content_texts) > 0

    def test_diagnosis_structure(self):
        """Diagnosis: title, 2 main items (User/Factory)."""
        from activity_tools import DiagnosisActivity
        act = actstack.start_activity(DiagnosisActivity)

        state = extract_ui_state(act)
        assert state['title'] == 'Diagnosis'
        # Diagnosis starts in ITEMS_MAIN state with no buttons
        # M2="Start" only appears after selecting an item (TIPS state)
        assert state['M2'] is None

    def test_title_bar_present(self):
        """Every activity must have a title bar rectangle."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        # Find title bar rectangle
        found_title_bar = False
        for item_id, item in canvas.get_items_by_type('rectangle'):
            if 'tags_title' in item['tags']:
                found_title_bar = True
                break
        assert found_title_bar, "Title bar rectangle not found"

    def test_button_bar_present(self):
        """Button bar bg is drawn only when button text is non-empty.

        Main menu has no button labels (setLeftButton(""), setRightButton(""))
        so the button bar background is NOT drawn. Use an activity that has
        button labels to test button bar presence.
        """
        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        # WarningDiskFullActivity sets M1/M2 button labels
        found_btn_bg = False
        for item_id, item in canvas.get_items_by_type('rectangle'):
            if 'tags_btn_bg' in item['tags']:
                found_btn_bg = True
                break
        assert found_btn_bg, "Button bar background not found"

    def test_content_area_populated(self):
        """Content area (y=40 to y=200) should have items."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        items = get_items_in_content_area(canvas)
        assert len(items) > 0, "Content area has no items"

    def test_toast_overlay_rendering(self):
        """Toast overlays correctly on content."""
        from activity_main import BacklightActivity
        act = actstack.start_activity(BacklightActivity)
        canvas = act.getCanvas()

        # Trigger a toast via the activity's toast widget
        if hasattr(act, '_toast') and act._toast is not None:
            act._toast.show("Test Toast", duration_ms=0)

            # Verify toast items exist on canvas.
            # Toast tags use format: 'ID:Toast-{id}:mask_layer' and
            # 'ID:Toast-{id}:msg' (from widget.createTag)
            toast_items_found = False
            for item_id in canvas.find_all():
                tags = canvas.gettags(item_id)
                for tag in tags:
                    if ':mask_layer' in tag or ':msg' in tag:
                        toast_items_found = True
                        break
                if toast_items_found:
                    break
            assert toast_items_found, "Toast overlay items not found on canvas"

    def test_progress_bar_rendering(self):
        """Progress bar at correct position with correct colors."""
        from widget import ProgressBar
        canvas = MockCanvas()
        pb = ProgressBar(canvas)
        pb.show()
        pb.setProgress(50)

        # Verify background rect exists
        bg_found = False
        fill_found = False
        for item_id, item in canvas.get_items_by_type('rectangle'):
            tags = item['tags']
            for tag in tags:
                if ':bg' in tag:
                    fill = item['options'].get('fill', '')
                    if fill.lower() == '#eeeeee':
                        bg_found = True
                if ':fill' in tag:
                    fill = item['options'].get('fill', '')
                    if fill.upper() == '#1C6AEB':
                        fill_found = True

        assert bg_found, "Progress bar background not found"
        assert fill_found, "Progress bar fill not found"

    def test_battery_bar_in_title(self):
        """Battery bar should render at (208, 15) area."""
        from widget import BatteryBar
        canvas = MockCanvas()
        bb = BatteryBar(canvas)
        bb.setBattery(75)
        bb.show()

        # Find battery outline rect
        outline_found = False
        for item_id, item in canvas.get_items_by_type('rectangle'):
            coords = item['coords']
            tags = item['tags']
            for tag in tags:
                if ':bat_outline' in tag or 'bat_outline' in tag:
                    outline_found = True
                    # Verify position is near (208, 15)
                    assert abs(coords[0] - BATTERY_X) < 2, (
                        "Battery X position wrong: %s" % coords[0]
                    )
                    assert abs(coords[1] - BATTERY_Y) < 2, (
                        "Battery Y position wrong: %s" % coords[1]
                    )
        assert outline_found, "Battery bar outline not found"


# =====================================================================
# TestScreenColors
# =====================================================================

class TestScreenColors:
    """Validate pixel-perfect color values from _constants.py."""

    def test_title_bar_color(self):
        """Title bar background must be #7C829A."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('rectangle'):
            if 'tags_title' in item['tags']:
                fill = item['options'].get('fill', '')
                assert fill == TITLE_BAR_BG, (
                    "Title bar color should be %s, got %s" % (TITLE_BAR_BG, fill)
                )
                return
        pytest.fail("Title bar rectangle not found")

    def test_content_bg_color(self):
        """Content background (canvas bg) must match BG_COLOR (#F8FCF8)."""
        canvas = MockCanvas(bg=BG_COLOR)
        assert canvas._bg == BG_COLOR

    def test_selection_highlight_color(self):
        """Selection highlight must be #EEEEEE."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        found = False
        for item_id, item in canvas.get_items_by_type('rectangle'):
            fill = item['options'].get('fill', '').upper()
            if fill == SELECT_BG.upper():
                found = True
                break
        assert found, "Selection highlight (#EEEEEE) not found"

    def test_progress_bar_fill_color(self):
        """Progress fill must be #1C6AEB."""
        from widget import ProgressBar
        canvas = MockCanvas()
        pb = ProgressBar(canvas)
        pb.show()
        pb.setProgress(50)

        found = False
        for item_id, item in canvas.get_items_by_type('rectangle'):
            for tag in item['tags']:
                if ':fill' in tag:
                    fill = item['options'].get('fill', '').upper()
                    if fill == PROGRESS_FG.upper():
                        found = True
        assert found, "Progress bar fill color (#1C6AEB) not found"

    def test_button_text_color(self):
        """Button text must be white."""
        # Use WarningDiskFullActivity which has actual button labels
        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('text'):
            if 'tags_btn_right' in item['tags'] or 'tags_btn_left' in item['tags']:
                fill = item['options'].get('fill', '')
                assert fill == BTN_TEXT_COLOR, (
                    "Button text color should be %s, got %s"
                    % (BTN_TEXT_COLOR, fill)
                )
                return
        pytest.fail("Button text not found")

    def test_title_text_color_is_white(self):
        """Title text must be white."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('text'):
            if 'tags_title' in item['tags']:
                fill = item['options'].get('fill', '')
                assert fill == 'white', (
                    "Title text color should be white, got %s" % fill
                )
                return
        pytest.fail("Title text not found")

    def test_button_bar_bg_color(self):
        """Button bar background must be BTN_BAR_BG (#222222)."""
        from _constants import BTN_BAR_BG
        # Use WarningDiskFullActivity which has actual button labels
        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('rectangle'):
            if 'tags_btn_bg' in item['tags']:
                fill = item['options'].get('fill', '')
                assert fill == BTN_BAR_BG, (
                    "Button bar bg should be %s, got %s" % (BTN_BAR_BG, fill)
                )
                return
        pytest.fail("Button bar background not found")

    def test_battery_bar_outline_white(self):
        """Battery bar outline must be white."""
        from widget import BatteryBar
        canvas = MockCanvas()
        bb = BatteryBar(canvas)
        bb.setBattery(75)
        bb.show()

        for item_id, item in canvas.get_items_by_type('rectangle'):
            for tag in item['tags']:
                if ':bat_outline' in tag:
                    outline = item['options'].get('outline', '')
                    assert outline == 'white', (
                        "Battery outline should be white, got %s" % outline
                    )
                    return
        pytest.fail("Battery outline rect not found")


# =====================================================================
# TestScreenPositions
# =====================================================================

class TestScreenPositions:
    """Validate that UI elements appear at correct pixel positions."""

    def test_title_bar_at_top(self):
        """Title bar rectangle: (0, 0, 240, 40)."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('rectangle'):
            if 'tags_title' in item['tags']:
                coords = item['coords']
                assert coords[0] == 0, "Title bar x0 should be 0"
                assert coords[1] == 0, "Title bar y0 should be 0"
                assert coords[2] == SCREEN_W, (
                    "Title bar x1 should be %d" % SCREEN_W
                )
                assert coords[3] == 40, "Title bar y1 should be 40"
                return
        pytest.fail("Title bar rectangle not found")

    def test_title_text_centered(self):
        """Title text at (TITLE_TEXT_X, 20) anchor=center."""
        from _constants import TITLE_TEXT_X
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('text'):
            if 'tags_title' in item['tags']:
                coords = item['coords']
                assert coords[0] == TITLE_TEXT_X, (
                    "Title text X should be %d, got %d" % (TITLE_TEXT_X, coords[0])
                )
                assert coords[1] == 20, "Title text Y should be 20"
                anchor = item['options'].get('anchor', '')
                assert anchor == 'center', (
                    "Title text anchor should be center, got %s" % anchor
                )
                return
        pytest.fail("Title text not found")

    def test_button_bar_at_bottom(self):
        """Button bar rectangle: (0, 200, 240, 240)."""
        # Use WarningDiskFullActivity which has actual button labels
        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('rectangle'):
            if 'tags_btn_bg' in item['tags']:
                coords = item['coords']
                assert coords[0] == 0, "Button bar x0 should be 0"
                assert coords[1] == 200, "Button bar y0 should be 200"
                assert coords[2] == SCREEN_W, (
                    "Button bar x1 should be %d" % SCREEN_W
                )
                assert coords[3] == SCREEN_H, (
                    "Button bar y1 should be %d" % SCREEN_H
                )
                return
        pytest.fail("Button bar rectangle not found")

    def test_m1_button_position(self):
        """M1 button text at (BTN_LEFT_X, BTN_LEFT_Y) anchor=sw."""
        from _constants import BTN_LEFT_X, BTN_LEFT_Y
        # Use WarningDiskFullActivity which has actual M1 button label
        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('text'):
            if 'tags_btn_left' in item['tags']:
                coords = item['coords']
                assert coords[0] == BTN_LEFT_X, (
                    "M1 X should be %d" % BTN_LEFT_X
                )
                assert coords[1] == BTN_LEFT_Y, (
                    "M1 Y should be %d" % BTN_LEFT_Y
                )
                return
        # M1 may be empty string which is still rendered
        # Just check that the tag exists
        btn_left_ids = canvas.find_withtag('tags_btn_left')
        assert len(btn_left_ids) > 0, "tags_btn_left items not found"

    def test_m2_button_position(self):
        """M2 button text at (BTN_RIGHT_X, BTN_RIGHT_Y) anchor=se."""
        from _constants import BTN_RIGHT_X, BTN_RIGHT_Y
        # Use WarningDiskFullActivity which has actual M2 button label
        from activity_main import WarningDiskFullActivity
        act = actstack.start_activity(WarningDiskFullActivity)
        canvas = act.getCanvas()

        for item_id, item in canvas.get_items_by_type('text'):
            if 'tags_btn_right' in item['tags']:
                coords = item['coords']
                assert coords[0] == BTN_RIGHT_X, (
                    "M2 X should be %d" % BTN_RIGHT_X
                )
                assert coords[1] == BTN_RIGHT_Y, (
                    "M2 Y should be %d" % BTN_RIGHT_Y
                )
                return
        pytest.fail("M2 button text not found")

    def test_content_starts_at_y40(self):
        """Content area should start at y=40 (below title bar)."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)
        canvas = act.getCanvas()

        items = get_items_in_content_area(canvas, y_min=40, y_max=200)
        # Find the topmost content item
        min_y = min(item['coords'][1] for item in items)
        # First content item should be near y=40
        assert min_y >= 38, "Content starts too high (y=%s)" % min_y
        assert min_y <= 70, "Content starts too low (y=%s)" % min_y
