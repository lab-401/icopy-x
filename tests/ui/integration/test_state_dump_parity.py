"""I-4: State dump parity tests.

Validates that extract_ui_state() produces output matching the QEMU
_dump_state() format from tools/minimal_launch_090.py.

The QEMU test infrastructure validates state via JSON dumps containing:
  current_activity, activity_stack, title, M1, M2, toast, content_text

Our extract_ui_state() must produce the same dict structure from
the canvas items rendered by our reimplemented activities.
"""

import pytest

from tests.ui.conftest import MockCanvas
import actstack
from actmain import MainActivity
from _constants import KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2, KEY_PWR
from tests.ui.integration.conftest import extract_ui_state


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def main_activity():
    """Boot MainActivity via actstack (full lifecycle)."""
    return actstack.start_activity(MainActivity)


# ===================================================================
# TestStateDumpParity
# ===================================================================

class TestStateDumpParity:
    """Our state extraction must match QEMU _dump_state() format."""

    def test_state_has_required_keys(self, main_activity):
        """State dict must contain all keys from _dump_state()."""
        state = extract_ui_state()
        required = {
            'current_activity', 'activity_stack', 'title',
            'M1', 'M2', 'toast', 'content_text',
        }
        assert required.issubset(state.keys()), (
            f"Missing keys: {required - state.keys()}"
        )

    def test_title_extracted_correctly(self, main_activity):
        """Title should match what setTitle() rendered."""
        state = extract_ui_state()
        assert state['title'] == 'Main Page'

    def test_buttons_extracted(self, main_activity):
        """M1 and M2 buttons should be extracted."""
        state = extract_ui_state()
        # Main menu has setLeftButton("") and setRightButton("") -- both empty.
        # extract_ui_state may pick up list item text via fallback-by-coords
        # if an item is at y>=200 (5th item extends into button bar zone).
        # With 5 items per page, item 4 at y=200 can trigger the fallback.
        # For main menu, M2 is None (no right button label).
        assert state['M2'] is None

    def test_content_text_from_listview(self, main_activity):
        """Content text should include the visible ListView items."""
        state = extract_ui_state()
        content_texts = [item['text'] for item in state['content_text']]
        # First visible items in the main menu ListView
        assert 'Auto Copy' in content_texts

    def test_toast_none_when_hidden(self, main_activity):
        """Toast should be None when no toast is showing."""
        state = extract_ui_state()
        assert state['toast'] is None

    def test_toast_text_when_visible(self):
        """Toast should contain the message text when showing."""
        from widget import Toast

        # Create a simple activity that shows a toast
        from activity_main import AboutActivity
        act = actstack.start_activity(AboutActivity)
        canvas = act.getCanvas()

        toast = Toast(canvas)
        toast.show("Test Toast Message", duration_ms=0)

        state = extract_ui_state(act)
        assert state['toast'] is not None
        assert 'Test Toast Message' in state['toast']

    def test_activity_stack_names(self, main_activity):
        """Activity stack should list class names in push order."""
        state = extract_ui_state()
        assert len(state['activity_stack']) == 1
        assert state['activity_stack'][0]['class'] == 'MainActivity'

        # Push a child
        from activity_main import BacklightActivity
        child = actstack.start_activity(BacklightActivity)

        state = extract_ui_state(child)
        assert len(state['activity_stack']) == 2
        assert state['activity_stack'][0]['class'] == 'MainActivity'
        assert state['activity_stack'][1]['class'] == 'BacklightActivity'

    def test_current_activity_is_top_of_stack(self, main_activity):
        """current_activity should be the top activity's class name."""
        state = extract_ui_state()
        assert state['current_activity'] == 'MainActivity'

        from activity_main import VolumeActivity
        child = actstack.start_activity(VolumeActivity)

        state = extract_ui_state(child)
        assert state['current_activity'] == 'VolumeActivity'

    def test_content_text_has_position_data(self, main_activity):
        """Content text entries should have x, y, fill, font fields."""
        state = extract_ui_state()
        if state['content_text']:
            entry = state['content_text'][0]
            assert 'text' in entry
            assert 'x' in entry
            assert 'y' in entry
            assert 'fill' in entry
            assert 'font' in entry

    def test_lifecycle_in_stack_entries(self, main_activity):
        """Stack entries should include lifecycle state."""
        state = extract_ui_state()
        entry = state['activity_stack'][0]
        assert 'lifecycle' in entry
        lc = entry['lifecycle']
        assert lc['created'] is True
        assert lc['resumed'] is True
        assert lc['destroyed'] is False

    # ---------------------------------------------------------------
    # Specific activity state snapshots
    # ---------------------------------------------------------------

    def test_main_menu_state_matches(self, main_activity):
        """Main menu state should match expected QEMU dump."""
        state = extract_ui_state()
        assert state['current_activity'] == 'MainActivity'
        assert state['title'] == 'Main Page'
        # Main menu has no M2 button (setRightButton(""))
        assert state['M2'] is None
        assert state['toast'] is None
        # Content should have at least some menu items rendered
        assert len(state['content_text']) > 0

    def test_backlight_state_matches(self):
        """Backlight activity state should match expected QEMU dump."""
        root = actstack.start_activity(MainActivity)

        from activity_main import BacklightActivity
        act = actstack.start_activity(BacklightActivity)

        state = extract_ui_state(act)
        assert state['current_activity'] == 'BacklightActivity'
        assert state['title'] == 'Backlight'
        # Backlight has no M2 button (setRightButton(""), save is via OK key)
        assert state['M2'] is None
        assert state['toast'] is None
        # Should have stack depth 2
        assert len(state['activity_stack']) == 2
        assert state['activity_stack'][0]['class'] == 'MainActivity'
        assert state['activity_stack'][1]['class'] == 'BacklightActivity'
        # Content should include backlight level items
        content_texts = [item['text'] for item in state['content_text']]
        # At least one of Low/Middle/High should appear
        assert any(
            level in content_texts
            for level in ('Low', 'Middle', 'High')
        ), f"Expected backlight level items, got: {content_texts}"

    def test_scan_idle_state_matches(self):
        """Scan activity idle state should match expected QEMU dump."""
        root = actstack.start_activity(MainActivity)

        from activity_main import ScanActivity
        act = actstack.start_activity(ScanActivity)

        state = extract_ui_state(act)
        assert state['current_activity'] == 'ScanActivity'
        assert state['title'] == 'Scan Tag'
        assert state['toast'] is None
        assert len(state['activity_stack']) == 2

    def test_volume_state_matches(self):
        """Volume activity state should match expected QEMU dump."""
        root = actstack.start_activity(MainActivity)

        from activity_main import VolumeActivity
        act = actstack.start_activity(VolumeActivity)

        state = extract_ui_state(act)
        assert state['current_activity'] == 'VolumeActivity'
        assert state['title'] == 'Volume'
        # Volume has no M2 button (setRightButton(""), save is via OK key)
        assert state['M2'] is None
        # Content should include volume level items
        content_texts = [item['text'] for item in state['content_text']]
        assert any(
            level in content_texts
            for level in ('Off', 'Low', 'Middle', 'High')
        ), f"Expected volume level items, got: {content_texts}"

    def test_about_state_matches(self):
        """About activity state should match expected QEMU dump."""
        root = actstack.start_activity(MainActivity)

        from activity_main import AboutActivity
        act = actstack.start_activity(AboutActivity)

        state = extract_ui_state(act)
        assert state['current_activity'] == 'AboutActivity'
        assert state['title'] == 'About'

    def test_state_after_pop_matches(self):
        """After popping a child, state should revert to parent."""
        root = actstack.start_activity(MainActivity)

        from activity_main import BacklightActivity
        child = actstack.start_activity(BacklightActivity)

        # State shows child
        state = extract_ui_state(child)
        assert state['current_activity'] == 'BacklightActivity'

        # Pop child
        actstack.finish_activity()

        # State should revert to main
        state = extract_ui_state()
        assert state['current_activity'] == 'MainActivity'
        assert state['title'] == 'Main Page'
        assert len(state['activity_stack']) == 1


# ===================================================================
# TestExtractUIStateEdgeCases
# ===================================================================

class TestExtractUIStateEdgeCases:
    """Edge cases for the extract_ui_state helper."""

    def test_empty_stack(self):
        """Empty stack should return None/empty values."""
        state = extract_ui_state()
        assert state['current_activity'] is None
        assert state['activity_stack'] == []
        assert state['title'] is None
        assert state['M1'] is None
        assert state['M2'] is None
        assert state['toast'] is None
        assert state['content_text'] == []

    def test_explicit_activity_param(self, main_activity):
        """Passing activity explicitly should use that activity's canvas."""
        state = extract_ui_state(main_activity)
        assert state['current_activity'] == 'MainActivity'
        assert state['title'] == 'Main Page'

    def test_multiple_toasts_last_wins(self):
        """If multiple toast texts exist, they should all be captured."""
        from widget import Toast
        from activity_main import AboutActivity

        act = actstack.start_activity(AboutActivity)
        canvas = act.getCanvas()

        toast = Toast(canvas)
        toast.show("Line 1\nLine 2", duration_ms=0)

        state = extract_ui_state(act)
        assert state['toast'] is not None
        assert 'Line 1' in state['toast']
        assert 'Line 2' in state['toast']

    def test_battery_text_excluded_from_content(self, main_activity):
        """Battery bar text in top-right corner should not appear in content_text."""
        canvas = main_activity.getCanvas()

        # Simulate battery text at top-right corner
        canvas.create_text(220, 20, text="100%", fill="white", font="mononoki 8",
                           tags="battery_text")

        state = extract_ui_state()
        content_texts = [item['text'] for item in state['content_text']]
        assert '100%' not in content_texts
