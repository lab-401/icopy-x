"""Tests for Toast widget — overlay message system.

Covers creation, display modes, multiline, icons, auto-dismiss timer,
cancel behavior, and overlay preservation of existing content.

All coordinate and color assertions derived from _constants.py and UI_SPEC.md.
"""

import sys
import os
import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import Toast, createTag
from lib._constants import (
    SCREEN_W,
    SCREEN_H,
    CONTENT_Y0,
    TOAST_MASK_CENTER,
    TOAST_MASK_FULL,
    TOAST_MASK_TOP_CENTER,
    TOAST_BG,
    TOAST_BORDER,
    TOAST_TEXT_COLOR,
    TOAST_MARGIN,
    TOAST_H,
    TOAST_CENTER_Y,
)

# Import the MockCanvas from the UI conftest
from tests.ui.conftest import MockCanvas


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

@pytest.fixture
def canvas():
    """Fresh 240x240 MockCanvas."""
    return MockCanvas(width=240, height=240, bg='#222222')


@pytest.fixture
def toast(canvas):
    """A Toast instance with default 2000ms duration."""
    return Toast(canvas, duration_ms=2000)


def _get_rects(canvas):
    """Return all rectangle items as list of (id, item_dict)."""
    return canvas.get_items_by_type('rectangle')


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


def _get_texts(canvas):
    """Extract all text strings currently on the canvas."""
    return canvas.get_all_text()


# =================================================================
# Toast overlay creation
# =================================================================

class TestToastShowCreatesOverlay:

    def test_show_creates_overlay(self, canvas, toast):
        """show() creates a PIL mask image and text items."""
        toast.show('Hello')
        images = canvas.get_items_by_type('image')
        texts = _get_text_items(canvas)
        assert len(images) >= 1, 'Expected at least one overlay image (PIL mask)'
        assert len(texts) >= 1, 'Expected at least one text item'

    def test_show_with_message_text(self, canvas, toast):
        """show() displays the message string on the canvas."""
        toast.show('Tag Found')
        texts = _get_texts(canvas)
        assert 'Tag Found' in texts

    def test_multiline_message(self, canvas, toast):
        """Multiline messages split on \\n produce separate text items."""
        toast.show('Read\nSuccessful!\nFile saved')
        texts = _get_texts(canvas)
        assert 'Read' in texts
        assert 'Successful!' in texts
        assert 'File saved' in texts

    def test_overlay_is_pil_image(self, canvas, toast):
        """Toast background is a PIL-composited RGBA image, not canvas rects."""
        toast.show('Test')
        images = canvas.get_items_by_type('image')
        assert len(images) >= 1, 'Expected PIL mask image on canvas'

    def test_overlay_text_is_white(self, canvas, toast):
        """Toast text is rendered in white."""
        toast.show('Test')
        texts = _get_text_items(canvas)
        assert len(texts) >= 1
        _, t = texts[0]
        assert t['options']['fill'] == 'white'


# =================================================================
# Cancel and visibility
# =================================================================

class TestToastCancelAndVisibility:

    def test_cancel_removes_overlay(self, canvas, toast):
        """cancel() removes all toast items from canvas."""
        toast.show('Visible')
        assert len(canvas.find_all()) > 0
        toast.cancel()
        assert len(canvas.find_all()) == 0

    def test_is_show_true_when_visible(self, canvas, toast):
        """isShow() returns True after show()."""
        toast.show('Active')
        assert toast.isShow() is True

    def test_is_show_false_after_cancel(self, canvas, toast):
        """isShow() returns False after cancel()."""
        toast.show('Active')
        toast.cancel()
        assert toast.isShow() is False

    def test_is_show_false_before_show(self, canvas, toast):
        """isShow() returns False before any show()."""
        assert toast.isShow() is False


# =================================================================
# Auto-dismiss timer
# =================================================================

class TestToastAutoDismiss:

    def test_auto_dismiss_timer_set(self, canvas, toast):
        """show() with duration > 0 stores an after() timer."""
        toast.show('Timed', duration_ms=3000)
        assert len(canvas._timers) == 1

    def test_cancel_cancels_timer(self, canvas, toast):
        """cancel() removes the auto-dismiss timer."""
        toast.show('Timed', duration_ms=3000)
        assert len(canvas._timers) == 1
        toast.cancel()
        assert len(canvas._timers) == 0

    def test_persistent_toast_no_timer(self, canvas, toast):
        """duration_ms=0 means no auto-dismiss timer."""
        toast.show('Persistent', duration_ms=0)
        assert len(canvas._timers) == 0

    def test_auto_dismiss_fires_cancel(self, canvas, toast):
        """When timer fires, toast is dismissed."""
        toast.show('Will dismiss', duration_ms=1000)
        assert toast.isShow() is True
        # Fire the timer manually
        canvas.fire_all_after()
        assert toast.isShow() is False
        assert len(canvas.find_all()) == 0


# =================================================================
# Icons
# =================================================================

class TestToastIcons:
    """Toast icons are composited into the PIL RGBA mask image, not rendered
    as separate canvas text glyphs.  Tests verify that an icon parameter
    results in the same single mask image (icon baked in) plus text items.
    """

    def test_icon_check_creates_mask(self, canvas, toast):
        """icon='check' still produces a PIL mask image on canvas."""
        toast.show('OK', icon='check')
        images = canvas.get_items_by_type('image')
        assert len(images) >= 1, 'Expected PIL mask image with icon composited'

    def test_icon_error_creates_mask(self, canvas, toast):
        """icon='error' still produces a PIL mask image on canvas."""
        toast.show('Fail', icon='error')
        images = canvas.get_items_by_type('image')
        assert len(images) >= 1

    def test_icon_warning_creates_mask(self, canvas, toast):
        """icon='warning' still produces a PIL mask image on canvas."""
        toast.show('Warn', icon='warning')
        images = canvas.get_items_by_type('image')
        assert len(images) >= 1

    def test_icon_info_creates_mask(self, canvas, toast):
        """icon='info' still produces a PIL mask image on canvas."""
        toast.show('Info', icon='info')
        images = canvas.get_items_by_type('image')
        assert len(images) >= 1

    def test_no_icon(self, canvas, toast):
        """No icon parameter still creates mask image (just no icon inside)."""
        toast.show('Plain')
        images = canvas.get_items_by_type('image')
        assert len(images) >= 1


# =================================================================
# Overlay preservation
# =================================================================

class TestToastOverlayPreservation:

    def test_overlay_preserves_existing_content(self, canvas, toast):
        """Toast overlay does NOT remove pre-existing canvas items."""
        # Add some existing content
        existing_id = canvas.create_text(120, 120, text='Existing', fill='white')
        toast.show('Overlay message')
        # The existing item should still be on the canvas
        item = canvas.get_item(existing_id)
        assert item is not None
        assert item['options']['text'] == 'Existing'

    def test_second_show_replaces_first(self, canvas, toast):
        """A second show() call replaces the first toast entirely."""
        toast.show('First')
        first_texts = _get_texts(canvas)
        assert 'First' in first_texts

        toast.show('Second')
        second_texts = _get_texts(canvas)
        assert 'Second' in second_texts
        assert 'First' not in second_texts
