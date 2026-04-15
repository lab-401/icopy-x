"""Tests for BatteryBar widget — battery level indicator in title bar.

Covers position, external rect, contact pip, fill colors at various
thresholds, fill width proportional to percent, charging indicator,
show/hide lifecycle.

All coordinate and color assertions derived from _constants.py and UI_SPEC.md.
"""

import sys
import os
import pytest

# Ensure src/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from lib.widget import BatteryBar, createTag
from lib._constants import (
    BATTERY_X,
    BATTERY_Y,
    BATTERY_W,
    BATTERY_H,
    BATTERY_OUTLINE_COLOR,
    BATTERY_OUTLINE_WIDTH,
    BATTERY_PIP_X0,
    BATTERY_PIP_Y0,
    BATTERY_PIP_X1,
    BATTERY_PIP_Y1,
    BATTERY_PIP_COLOR,
    BATTERY_FILL_X0,
    BATTERY_FILL_Y0,
    BATTERY_FILL_Y1,
    BATTERY_FILL_MAX_W,
    BATTERY_COLOR_HIGH,
    BATTERY_COLOR_MED,
    BATTERY_COLOR_LOW,
    BATTERY_THRESHOLD_HIGH,
    BATTERY_THRESHOLD_LOW,
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
def bat(canvas):
    """A BatteryBar at default position, shown with 100% charge."""
    bb = BatteryBar(canvas)
    bb.show()
    return bb


def _get_rects(canvas):
    """Return all rectangle items as list of (id, item_dict)."""
    return canvas.get_items_by_type('rectangle')


def _get_text_items(canvas):
    """Return all text items as list of (id, item_dict)."""
    return canvas.get_items_by_type('text')


def _find_outline_rect(canvas):
    """Find the battery outline rectangle (has outline='white', fill='')."""
    for iid, item in _get_rects(canvas):
        if (item['options'].get('outline') == BATTERY_OUTLINE_COLOR and
                item['options'].get('fill') == ''):
            return iid, item
    return None, None


def _find_fill_rect(canvas):
    """Find the battery fill rectangle (has outline='', width=0)."""
    for iid, item in _get_rects(canvas):
        opts = item['options']
        if (opts.get('outline') == '' and
                str(opts.get('width', '')) == '0' and
                opts.get('fill') not in ('', BATTERY_OUTLINE_COLOR)):
            return iid, item
    return None, None


def _find_pip_rect(canvas):
    """Find the contact pip rectangle (fill=white, outline=white)."""
    for iid, item in _get_rects(canvas):
        opts = item['options']
        if (opts.get('fill') == BATTERY_PIP_COLOR and
                opts.get('outline') == BATTERY_PIP_COLOR and
                item['coords'][0] == BATTERY_PIP_X0):
            return iid, item
    return None, None


# =================================================================
# Default position
# =================================================================

class TestBatteryBarPosition:

    def test_default_position(self, canvas):
        """Default position is (208, 15) per SPEC."""
        bb = BatteryBar(canvas)
        assert bb._x == 208
        assert bb._y == 15

    def test_external_rect_coords(self, canvas, bat):
        """External rect spans (208,15) to (230,27)."""
        _, outline = _find_outline_rect(canvas)
        assert outline is not None
        coords = outline['coords']
        assert coords[0] == BATTERY_X       # 208
        assert coords[1] == BATTERY_Y       # 15
        assert coords[2] == BATTERY_X + BATTERY_W  # 230
        assert coords[3] == BATTERY_Y + BATTERY_H  # 27

    def test_contact_pip_present(self, canvas, bat):
        """Contact pip rectangle exists at correct coordinates."""
        _, pip = _find_pip_rect(canvas)
        assert pip is not None
        coords = pip['coords']
        assert coords[0] == BATTERY_PIP_X0  # 230
        assert coords[1] == BATTERY_PIP_Y0  # 19.2
        assert coords[2] == BATTERY_PIP_X1  # 232.4
        assert coords[3] == BATTERY_PIP_Y1  # 22.8


# =================================================================
# Colors
# =================================================================

class TestBatteryBarColors:

    def test_outline_color_white(self, canvas, bat):
        """Battery outline is white with width=2."""
        _, outline = _find_outline_rect(canvas)
        assert outline is not None
        assert outline['options']['outline'] == 'white'
        assert str(outline['options']['width']) == str(BATTERY_OUTLINE_WIDTH)

    def test_fill_color_green_above_50(self, canvas):
        """Battery fill is green (#00FF00) when percent > 50."""
        bb = BatteryBar(canvas)
        bb.setBattery(75)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        assert fill['options']['fill'] == BATTERY_COLOR_HIGH  # '#00FF00'

    def test_fill_color_yellow_at_50(self, canvas):
        """Battery fill is yellow (#FFFF00) at exactly 50%."""
        bb = BatteryBar(canvas)
        bb.setBattery(50)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        assert fill['options']['fill'] == BATTERY_COLOR_MED  # '#FFFF00'

    def test_fill_color_yellow_at_30(self, canvas):
        """Battery fill is yellow (#FFFF00) at 30%."""
        bb = BatteryBar(canvas)
        bb.setBattery(30)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        assert fill['options']['fill'] == BATTERY_COLOR_MED  # '#FFFF00'

    def test_fill_color_red_below_20(self, canvas):
        """Battery fill is red (#FF0000) when percent < 20."""
        bb = BatteryBar(canvas)
        bb.setBattery(10)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        assert fill['options']['fill'] == BATTERY_COLOR_LOW  # '#FF0000'

    def test_fill_color_red_at_15(self, canvas):
        """Battery fill is red at 15% (below threshold of 20)."""
        bb = BatteryBar(canvas)
        bb.setBattery(15)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        assert fill['options']['fill'] == BATTERY_COLOR_LOW  # '#FF0000'


# =================================================================
# Fill width
# =================================================================

class TestBatteryBarFillWidth:

    def test_fill_width_proportional(self, canvas):
        """Fill width is proportional to percent (50% -> 9px of 18px max)."""
        bb = BatteryBar(canvas)
        bb.setBattery(50)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        fill_w = fill['coords'][2] - fill['coords'][0]
        expected_w = int(BATTERY_FILL_MAX_W * 50 / 100)  # 9
        assert fill_w == expected_w

    def test_fill_width_at_100(self, canvas):
        """At 100%, fill spans the full internal width (18px)."""
        bb = BatteryBar(canvas)
        bb.setBattery(100)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is not None
        fill_w = fill['coords'][2] - fill['coords'][0]
        assert fill_w == BATTERY_FILL_MAX_W  # 18

    def test_fill_width_at_0(self, canvas):
        """At 0%, no fill rectangle is drawn."""
        bb = BatteryBar(canvas)
        bb.setBattery(0)
        bb.show()
        _, fill = _find_fill_rect(canvas)
        assert fill is None, 'No fill rect should be drawn at 0%'


# =================================================================
# Charging
# =================================================================

class TestBatteryBarCharging:

    def test_charging_indicator_shown(self, canvas):
        """setCharging(True) draws a lightning bolt text item."""
        bb = BatteryBar(canvas)
        bb.setCharging(True)
        bb.show()
        texts = _get_text_items(canvas)
        bolt_items = [t for _, t in texts if '\u26A1' in t['options'].get('text', '')]
        assert len(bolt_items) == 1

    def test_charging_indicator_hidden(self, canvas, bat):
        """By default (not charging), no lightning bolt is drawn."""
        texts = _get_text_items(canvas)
        bolt_items = [t for _, t in texts if '\u26A1' in t['options'].get('text', '')]
        assert len(bolt_items) == 0


# =================================================================
# Show / Hide lifecycle
# =================================================================

class TestBatteryBarLifecycle:

    def test_show_creates_items(self, canvas):
        """show() puts items on the canvas."""
        bb = BatteryBar(canvas)
        assert len(canvas.find_all()) == 0
        bb.show()
        assert len(canvas.find_all()) > 0

    def test_hide_removes_items(self, canvas, bat):
        """hide() removes all battery items from canvas."""
        assert len(canvas.find_all()) > 0
        bat.hide()
        assert len(canvas.find_all()) == 0

    def test_is_showing(self, canvas):
        """isShowing() tracks visibility state."""
        bb = BatteryBar(canvas)
        assert bb.isShowing() is False
        bb.show()
        assert bb.isShowing() is True
        bb.hide()
        assert bb.isShowing() is False

    def test_destroy_prevents_show(self, canvas):
        """After destroy(), show() has no effect."""
        bb = BatteryBar(canvas)
        bb.destroy()
        assert bb.isDestroy() is True
        bb.show()
        assert bb.isShowing() is False
        assert len(canvas.find_all()) == 0
