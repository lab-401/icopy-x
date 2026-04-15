"""Comprehensive tests for _renderer.py — JSON screen -> Canvas renderer.

Tests verify that canvas items have correct coordinates, colors, fill
values, text content, anchors, fonts, and tags.  Every assertion is
traceable to UI_SPEC.md or _constants.py.

Uses MockCanvas from tests/ui/conftest.py (no X11 display needed).
"""

import pytest
import sys
import os

# Ensure src/lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from lib._renderer import (
    Renderer,
    TAG_TITLE_BAR, TAG_TITLE_TEXT, TAG_PAGE_INDICATOR,
    TAG_CONTENT, TAG_BUTTON_BAR, TAG_BUTTON_LEFT, TAG_BUTTON_RIGHT,
    TAG_TOAST,
)
from lib import _constants as C


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def renderer(canvas):
    """Renderer wired to a fresh MockCanvas."""
    return Renderer(canvas)


def _find_items_by_tag(canvas, tag):
    """Return list of (id, item_dict) for items with given tag."""
    ids = canvas.find_withtag(tag)
    return [(iid, canvas.get_item(iid)) for iid in ids]


def _find_texts_by_tag(canvas, tag):
    """Return list of text option strings for text items with tag."""
    results = []
    for iid in canvas.find_withtag(tag):
        item = canvas.get_item(iid)
        if item and item["type"] == "text":
            results.append(item["options"].get("text", ""))
    return results


def _find_rects_by_tag(canvas, tag):
    """Return list of (id, item_dict) for rectangles with tag."""
    results = []
    for iid in canvas.find_withtag(tag):
        item = canvas.get_item(iid)
        if item and item["type"] == "rectangle":
            results.append((iid, item))
    return results


# =========================================================================
# Title Bar
# =========================================================================

class TestTitleBar:
    """SPEC section 2.1 / 12.1: title bar background and text."""

    def test_title_bar_rect_coords(self, canvas, renderer):
        renderer.render_title("Test")
        rects = _find_rects_by_tag(canvas, TAG_TITLE_BAR)
        assert len(rects) == 1
        _, item = rects[0]
        assert item["coords"] == [0, C.TITLE_BAR_Y0, C.SCREEN_W, C.TITLE_BAR_Y1]

    def test_title_bar_rect_color(self, canvas, renderer):
        renderer.render_title("Test")
        rects = _find_rects_by_tag(canvas, TAG_TITLE_BAR)
        _, item = rects[0]
        assert item["options"]["fill"] == C.TITLE_BAR_BG

    def test_title_bar_rect_no_outline(self, canvas, renderer):
        renderer.render_title("Test")
        rects = _find_rects_by_tag(canvas, TAG_TITLE_BAR)
        _, item = rects[0]
        assert item["options"]["outline"] == ""

    def test_title_text_position(self, canvas, renderer):
        renderer.render_title("Scan Tag")
        texts = _find_items_by_tag(canvas, TAG_TITLE_TEXT)
        assert len(texts) == 1
        _, item = texts[0]
        assert item["coords"] == [C.TITLE_TEXT_X, C.TITLE_TEXT_Y]

    def test_title_text_color(self, canvas, renderer):
        renderer.render_title("Scan Tag")
        texts = _find_items_by_tag(canvas, TAG_TITLE_TEXT)
        _, item = texts[0]
        assert item["options"]["fill"] == C.TITLE_TEXT_COLOR

    def test_title_text_anchor(self, canvas, renderer):
        renderer.render_title("Scan Tag")
        texts = _find_items_by_tag(canvas, TAG_TITLE_TEXT)
        _, item = texts[0]
        assert item["options"]["anchor"] == C.TITLE_TEXT_ANCHOR

    def test_title_text_font(self, canvas, renderer):
        renderer.render_title("Scan Tag")
        texts = _find_items_by_tag(canvas, TAG_TITLE_TEXT)
        _, item = texts[0]
        assert item["options"]["font"] == C.FONT_TITLE

    def test_title_text_content(self, canvas, renderer):
        renderer.render_title("Read Tag")
        texts = _find_texts_by_tag(canvas, TAG_TITLE_TEXT)
        assert texts == ["Read Tag"]

    def test_title_with_placeholder(self, canvas, renderer):
        renderer.set_state({"screen": "Volume"})
        renderer.render_title("{screen}")
        texts = _find_texts_by_tag(canvas, TAG_TITLE_TEXT)
        assert texts == ["Volume"]

    def test_title_replaces_previous(self, canvas, renderer):
        renderer.render_title("First")
        renderer.render_title("Second")
        texts = _find_texts_by_tag(canvas, TAG_TITLE_TEXT)
        assert texts == ["Second"]
        # Old title gone
        assert "First" not in canvas.get_all_text()


# =========================================================================
# Page Indicator
# =========================================================================

class TestPageIndicator:
    """Page indicator in title area when applicable."""

    def test_no_page_indicator_by_default(self, canvas, renderer):
        renderer.render_title("Main Page")
        items = _find_items_by_tag(canvas, TAG_PAGE_INDICATOR)
        assert len(items) == 0

    def test_page_indicator_shown(self, canvas, renderer):
        renderer.render_title("Main Page", page="1/2")
        items = _find_items_by_tag(canvas, TAG_PAGE_INDICATOR)
        assert len(items) == 1
        _, item = items[0]
        assert item["options"]["text"] == "1/2"

    def test_page_indicator_color(self, canvas, renderer):
        renderer.render_title("Main Page", page="2/4")
        items = _find_items_by_tag(canvas, TAG_PAGE_INDICATOR)
        _, item = items[0]
        assert item["options"]["fill"] == C.TITLE_TEXT_COLOR

    def test_page_indicator_font(self, canvas, renderer):
        renderer.render_title("Main Page", page="1/3")
        items = _find_items_by_tag(canvas, TAG_PAGE_INDICATOR)
        _, item = items[0]
        assert item["options"]["font"] == C.FONT_PAGE_ARROW

    def test_page_indicator_resolves_placeholder(self, canvas, renderer):
        renderer.set_state({"pg": "3/5"})
        renderer.render_title("Test", page="{pg}")
        items = _find_items_by_tag(canvas, TAG_PAGE_INDICATOR)
        _, item = items[0]
        assert item["options"]["text"] == "3/5"


# =========================================================================
# Button Bar
# =========================================================================

class TestButtonBar:
    """SPEC section 2.2 / 12.2-12.4: button bar background and buttons."""

    def test_button_bar_rect_coords(self, canvas, renderer):
        renderer.render_buttons("Back", "OK")
        rects = _find_rects_by_tag(canvas, TAG_BUTTON_BAR)
        assert len(rects) == 1
        _, item = rects[0]
        assert item["coords"] == [0, C.BTN_BAR_Y0, C.SCREEN_W, C.BTN_BAR_Y1]

    def test_button_bar_rect_color(self, canvas, renderer):
        renderer.render_buttons("Back", "OK")
        rects = _find_rects_by_tag(canvas, TAG_BUTTON_BAR)
        _, item = rects[0]
        assert item["options"]["fill"] == C.BTN_BAR_BG

    def test_left_button_position(self, canvas, renderer):
        renderer.render_buttons("Back", None)
        items = _find_items_by_tag(canvas, TAG_BUTTON_LEFT)
        assert len(items) == 1
        _, item = items[0]
        assert item["coords"] == [C.BTN_LEFT_X, C.BTN_LEFT_Y]

    def test_left_button_anchor(self, canvas, renderer):
        renderer.render_buttons("Back", None)
        items = _find_items_by_tag(canvas, TAG_BUTTON_LEFT)
        _, item = items[0]
        assert item["options"]["anchor"] == C.BTN_LEFT_ANCHOR

    def test_left_button_color(self, canvas, renderer):
        renderer.render_buttons("Back", None)
        items = _find_items_by_tag(canvas, TAG_BUTTON_LEFT)
        _, item = items[0]
        assert item["options"]["fill"] == C.BTN_TEXT_COLOR

    def test_left_button_font(self, canvas, renderer):
        renderer.render_buttons("Back", None)
        items = _find_items_by_tag(canvas, TAG_BUTTON_LEFT)
        _, item = items[0]
        assert item["options"]["font"] == C.FONT_BUTTON

    def test_right_button_position(self, canvas, renderer):
        renderer.render_buttons(None, "Scan")
        items = _find_items_by_tag(canvas, TAG_BUTTON_RIGHT)
        assert len(items) == 1
        _, item = items[0]
        assert item["coords"] == [C.BTN_RIGHT_X, C.BTN_RIGHT_Y]

    def test_right_button_anchor(self, canvas, renderer):
        renderer.render_buttons(None, "Scan")
        items = _find_items_by_tag(canvas, TAG_BUTTON_RIGHT)
        _, item = items[0]
        assert item["options"]["anchor"] == C.BTN_RIGHT_ANCHOR

    def test_right_button_color(self, canvas, renderer):
        renderer.render_buttons(None, "Scan")
        items = _find_items_by_tag(canvas, TAG_BUTTON_RIGHT)
        _, item = items[0]
        assert item["options"]["fill"] == C.BTN_TEXT_COLOR

    def test_right_button_font(self, canvas, renderer):
        renderer.render_buttons(None, "Scan")
        items = _find_items_by_tag(canvas, TAG_BUTTON_RIGHT)
        _, item = items[0]
        assert item["options"]["font"] == C.FONT_BUTTON

    def test_both_buttons(self, canvas, renderer):
        renderer.render_buttons("Back", "OK")
        left = _find_texts_by_tag(canvas, TAG_BUTTON_LEFT)
        right = _find_texts_by_tag(canvas, TAG_BUTTON_RIGHT)
        assert left == ["Back"]
        assert right == ["OK"]

    def test_no_left_button(self, canvas, renderer):
        renderer.render_buttons(None, "Scan")
        left = _find_items_by_tag(canvas, TAG_BUTTON_LEFT)
        assert len(left) == 0

    def test_no_right_button(self, canvas, renderer):
        renderer.render_buttons("Back", None)
        right = _find_items_by_tag(canvas, TAG_BUTTON_RIGHT)
        assert len(right) == 0

    def test_no_buttons(self, canvas, renderer):
        renderer.render_buttons(None, None)
        left = _find_items_by_tag(canvas, TAG_BUTTON_LEFT)
        right = _find_items_by_tag(canvas, TAG_BUTTON_RIGHT)
        assert len(left) == 0
        assert len(right) == 0
        # Background still drawn
        rects = _find_rects_by_tag(canvas, TAG_BUTTON_BAR)
        assert len(rects) == 1

    def test_button_text_resolved(self, canvas, renderer):
        renderer.set_state({"m1": "Rescan", "m2": "Simulate"})
        renderer.render_buttons("{m1}", "{m2}")
        left = _find_texts_by_tag(canvas, TAG_BUTTON_LEFT)
        right = _find_texts_by_tag(canvas, TAG_BUTTON_RIGHT)
        assert left == ["Rescan"]
        assert right == ["Simulate"]

    def test_buttons_replaced_on_rerender(self, canvas, renderer):
        renderer.render_buttons("A", "B")
        renderer.render_buttons("C", "D")
        left = _find_texts_by_tag(canvas, TAG_BUTTON_LEFT)
        right = _find_texts_by_tag(canvas, TAG_BUTTON_RIGHT)
        assert left == ["C"]
        assert right == ["D"]


# =========================================================================
# Content type: list
# =========================================================================

class TestListContent:
    """SPEC section 5.2: scrollable item list rendering."""

    MENU_ITEMS = [
        {"label": "Auto Copy", "icon": "icon_autocopy.png"},
        {"label": "Scan Tag", "icon": "icon_scan.png"},
        {"label": "Read Tag", "icon": "icon_read.png"},
        {"label": "Write Tag", "icon": "icon_write.png"},
    ]

    RADIO_ITEMS = [
        {"label": "Off"},
        {"label": "Low"},
        {"label": "Middle", "checked": True},
        {"label": "High"},
    ]

    def test_list_items_rendered(self, canvas, renderer):
        content = {"type": "list", "items": self.MENU_ITEMS, "style": "menu", "selected": 0}
        renderer.render_content(content)
        text_strs = _find_texts_by_tag(canvas, TAG_CONTENT)
        assert "Auto Copy" in text_strs
        assert "Scan Tag" in text_strs
        assert "Read Tag" in text_strs
        assert "Write Tag" in text_strs

    def test_list_menu_text_x_with_icon(self, canvas, renderer):
        content = {"type": "list", "items": self.MENU_ITEMS[:1], "style": "menu", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [(iid, it) for iid, it in texts if it["type"] == "text"]
        assert len(text_items) >= 1
        _, item = text_items[0]
        assert item["coords"][0] == C.LIST_TEXT_X_WITH_ICON

    def test_list_plain_text_x_no_icon(self, canvas, renderer):
        content = {"type": "list", "items": [{"label": "Test"}], "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [(iid, it) for iid, it in texts if it["type"] == "text"]
        assert len(text_items) >= 1
        _, item = text_items[0]
        assert item["coords"][0] == C.LIST_TEXT_X_NO_ICON

    def test_list_item_height_40px(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "A"}, {"label": "B"}],
            "style": "plain", "selected": 0,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [(iid, it) for iid, it in texts if it["type"] == "text"]
        # First item y: CONTENT_Y0 + LIST_ITEM_H//2 = 40 + 20 = 60
        # Second item y: CONTENT_Y0 + LIST_ITEM_H + LIST_ITEM_H//2 = 40 + 40 + 20 = 100
        y_vals = sorted([it["coords"][1] for _, it in text_items])
        assert y_vals[0] == C.CONTENT_Y0 + C.LIST_ITEM_H // 2
        assert y_vals[1] == C.CONTENT_Y0 + C.LIST_ITEM_H + C.LIST_ITEM_H // 2

    def test_list_text_anchor_west(self, canvas, renderer):
        content = {"type": "list", "items": [{"label": "Item"}], "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [(iid, it) for iid, it in texts if it["type"] == "text"]
        _, item = text_items[0]
        assert item["options"]["anchor"] == C.LIST_TEXT_ANCHOR

    def test_list_selection_highlight(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "A"}, {"label": "B"}],
            "style": "plain", "selected": 1,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        # Find selection rect (fill == SELECT_BG)
        sel_rects = [(iid, it) for iid, it in rects if it["options"].get("fill") == C.SELECT_BG]
        assert len(sel_rects) == 1
        _, item = sel_rects[0]
        expected_y = C.CONTENT_Y0 + 1 * C.LIST_ITEM_H  # second item
        assert item["coords"] == [0, expected_y, C.SCREEN_W, expected_y + C.LIST_ITEM_H]

    def test_list_selection_outline(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "A"}],
            "style": "plain", "selected": 0,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        sel_rects = [(iid, it) for iid, it in rects if it["options"].get("fill") == C.SELECT_BG]
        _, item = sel_rects[0]
        assert item["options"]["outline"] == C.SELECT_OUTLINE
        assert item["options"]["width"] == C.SELECT_OUTLINE_WIDTH

    def test_list_selected_text_color(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "Selected"}, {"label": "Normal"}],
            "style": "plain", "selected": 0,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [(iid, it) for iid, it in texts if it["type"] == "text"]
        # First item (selected)
        first = [it for _, it in text_items if it["options"]["text"] == "Selected"][0]
        assert first["options"]["fill"] == C.SELECT_TEXT_COLOR
        # Second item (normal)
        second = [it for _, it in text_items if it["options"]["text"] == "Normal"][0]
        assert second["options"]["fill"] == C.NORMAL_TEXT_COLOR

    def test_list_4_items_per_page_default(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {"type": "list", "items": items, "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts if it["type"] == "text"]
        # Only page_size=4 items visible (plus possible page arrow)
        labels = [it["options"]["text"] for it in text_items
                  if it["options"]["text"] not in ("\u25b2", "\u25bc")]
        assert len(labels) == C.LIST_ITEMS_PER_PAGE

    def test_list_scroll_offset(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {
            "type": "list", "items": items, "style": "plain",
            "selected": 4, "scroll_offset": 4,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts if it["type"] == "text"]
        labels = [it["options"]["text"] for it in text_items
                  if it["options"]["text"] not in ("\u25b2", "\u25bc")]
        assert "Item 4" in labels
        assert "Item 0" not in labels

    def test_list_custom_page_size(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(10)]
        content = {
            "type": "list", "items": items, "style": "plain",
            "selected": 0, "page_size": 5,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts if it["type"] == "text"]
        labels = [it["options"]["text"] for it in text_items
                  if it["options"]["text"] not in ("\u25b2", "\u25bc")]
        assert len(labels) == 5

    def test_list_font(self, canvas, renderer):
        content = {"type": "list", "items": [{"label": "X"}], "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts if it["type"] == "text"]
        assert text_items[0]["options"]["font"] == C.FONT_CONTENT


class TestListPagination:
    """Page arrows for multi-page lists."""

    def test_down_arrow_when_more_items(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {"type": "list", "items": items, "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_strs = [it["options"]["text"] for _, it in texts if it["type"] == "text"]
        assert "\u25bc" in text_strs

    def test_no_down_arrow_when_all_fit(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(4)]
        content = {"type": "list", "items": items, "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_strs = [it["options"]["text"] for _, it in texts if it["type"] == "text"]
        assert "\u25bc" not in text_strs

    def test_up_arrow_when_scrolled(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {
            "type": "list", "items": items, "style": "plain",
            "selected": 4, "scroll_offset": 4,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_strs = [it["options"]["text"] for _, it in texts if it["type"] == "text"]
        assert "\u25b2" in text_strs

    def test_no_up_arrow_at_top(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {"type": "list", "items": items, "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_strs = [it["options"]["text"] for _, it in texts if it["type"] == "text"]
        assert "\u25b2" not in text_strs

    def test_both_arrows_when_in_middle(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(12)]
        content = {
            "type": "list", "items": items, "style": "plain",
            "selected": 4, "scroll_offset": 4,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_strs = [it["options"]["text"] for _, it in texts if it["type"] == "text"]
        assert "\u25b2" in text_strs
        assert "\u25bc" in text_strs

    def test_arrow_color(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {"type": "list", "items": items, "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        arrow_items = [it for _, it in texts
                       if it["type"] == "text" and it["options"]["text"] == "\u25bc"]
        assert len(arrow_items) == 1
        assert arrow_items[0]["options"]["fill"] == C.PAGE_INDICATOR_COLOR

    def test_down_arrow_position(self, canvas, renderer):
        items = [{"label": "Item %d" % i} for i in range(8)]
        content = {"type": "list", "items": items, "style": "plain", "selected": 0}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        arrow_items = [(iid, it) for iid, it in texts
                       if it["type"] == "text" and it["options"]["text"] == "\u25bc"]
        _, item = arrow_items[0]
        assert item["coords"] == [C.SCREEN_W // 2, C.CONTENT_Y1 - 2]
        assert item["options"]["anchor"] == "s"


class TestListStyles:
    """Different list styles: menu, radio, checklist, plain."""

    def test_radio_unchecked_indicator(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "Off"}, {"label": "Low"}],
            "style": "radio", "selected": 0,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        # Should have selection rect + 2 radio indicator rects
        indicator_rects = [(iid, it) for iid, it in rects
                          if it["options"].get("outline") == "grey"]
        # Second item (unchecked) should have grey outline indicator
        assert len(indicator_rects) >= 1

    def test_radio_checked_indicator_color(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "Off", "checked": True}],
            "style": "radio", "selected": 0,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        accent_rects = [(iid, it) for iid, it in rects
                        if it["options"].get("fill") == C.COLOR_ACCENT]
        assert len(accent_rects) == 1

    def test_checklist_checked_shows_filled_rect(self, canvas, renderer):
        """Checked item renders blue-bordered + blue-filled checkbox rectangles."""
        content = {
            "type": "list",
            "items": [{"label": "Item A", "checked": True}],
            "style": "checklist", "selected": 0,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        # Checked state: outer border rect + inner fill rect
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.CHECK_COLOR_CHECKED_FILL]
        assert len(fill_rects) == 1

    def test_checklist_unchecked_shows_box(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "Item B", "checked": False}],
            "style": "checklist", "selected": 0,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        box_rects = [(iid, it) for iid, it in rects
                     if it["options"].get("outline") == "grey"
                     and it["options"].get("fill") == ""]
        assert len(box_rects) >= 1

    def test_menu_style_with_icon_uses_icon_x(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "Scan Tag", "icon": "1.png"}],
            "style": "menu", "selected": 0,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        label_items = [it for _, it in texts
                       if it["type"] == "text" and it["options"]["text"] == "Scan Tag"]
        assert len(label_items) == 1
        assert label_items[0]["coords"][0] == C.LIST_TEXT_X_WITH_ICON

    def test_menu_style_without_icon_uses_no_icon_x(self, canvas, renderer):
        content = {
            "type": "list",
            "items": [{"label": "Test"}],
            "style": "menu", "selected": 0,
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        label_items = [it for _, it in texts
                       if it["type"] == "text" and it["options"]["text"] == "Test"]
        assert label_items[0]["coords"][0] == C.LIST_TEXT_X_NO_ICON


# =========================================================================
# Content type: template
# =========================================================================

class TestTemplateContent:
    """Template rendering: header, subheader, field rows."""

    TEMPLATE = {
        "type": "template",
        "header": "MIFARE",
        "subheader": "M1 S50 1K (4B)",
        "fields": [
            {"label": "Frequency", "value": "13.56 MHz"},
            {"label": "UID", "value": "{uid}"},
            {"row": [
                {"label": "SAK", "value": "{sak}"},
                {"label": "ATQA", "value": "{atqa}"},
            ]},
        ],
    }

    def test_header_rendered(self, canvas, renderer):
        renderer.render_content(self.TEMPLATE)
        texts = canvas.get_all_text()
        assert "MIFARE" in texts

    def test_subheader_rendered(self, canvas, renderer):
        renderer.render_content(self.TEMPLATE)
        texts = canvas.get_all_text()
        assert "M1 S50 1K (4B)" in texts

    def test_field_rendered(self, canvas, renderer):
        renderer.render_content(self.TEMPLATE)
        texts = canvas.get_all_text()
        assert "Frequency: 13.56 MHz" in texts

    def test_field_placeholder_resolved(self, canvas, renderer):
        renderer.set_state({"uid": "2CADC272", "sak": "08", "atqa": "0004"})
        renderer.render_content(self.TEMPLATE)
        texts = canvas.get_all_text()
        assert "UID: 2CADC272" in texts

    def test_row_fields_rendered(self, canvas, renderer):
        renderer.set_state({"uid": "AABB", "sak": "08", "atqa": "0004"})
        renderer.render_content(self.TEMPLATE)
        texts = canvas.get_all_text()
        assert "SAK: 08" in texts
        assert "ATQA: 0004" in texts

    def test_header_centered(self, canvas, renderer):
        renderer.render_content(self.TEMPLATE)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        header_items = [it for _, it in texts
                        if it["type"] == "text" and it["options"]["text"] == "MIFARE"]
        assert len(header_items) == 1
        assert header_items[0]["coords"][0] == C.SCREEN_W // 2
        assert header_items[0]["options"]["anchor"] == "n"

    def test_field_left_aligned(self, canvas, renderer):
        renderer.render_content(self.TEMPLATE)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        field_items = [it for _, it in texts
                       if it["type"] == "text"
                       and it["options"]["text"] == "Frequency: 13.56 MHz"]
        assert len(field_items) == 1
        assert field_items[0]["coords"][0] == 10
        assert field_items[0]["options"]["anchor"] == "nw"

    def test_unresolved_placeholder_stays(self, canvas, renderer):
        # No state set -- {uid} should stay as-is
        renderer.render_content(self.TEMPLATE)
        texts = canvas.get_all_text()
        assert "UID: {uid}" in texts

    def test_template_no_header(self, canvas, renderer):
        content = {"type": "template", "fields": [{"label": "Test", "value": "123"}]}
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "Test: 123" in texts


# =========================================================================
# Content type: progress
# =========================================================================

class TestProgressContent:
    """SPEC section 5.4 / 12.7: progress bar rendering."""

    def test_progress_bar_bg_coords(self, canvas, renderer):
        content = {"type": "progress", "message": "Reading...", "value": 50, "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        bg_rects = [(iid, it) for iid, it in rects
                    if it["options"].get("fill") == C.PROGRESS_BG]
        assert len(bg_rects) == 1
        _, item = bg_rects[0]
        assert item["coords"] == [
            C.PROGRESS_X, C.PROGRESS_Y,
            C.PROGRESS_X + C.PROGRESS_W, C.PROGRESS_Y + C.PROGRESS_H,
        ]

    def test_progress_bar_fill_color(self, canvas, renderer):
        content = {"type": "progress", "message": "", "value": 50, "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        assert len(fill_rects) == 1

    def test_progress_bar_fill_width_proportional(self, canvas, renderer):
        content = {"type": "progress", "message": "", "value": 50, "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        _, item = fill_rects[0]
        expected_x1 = C.PROGRESS_X + int(C.PROGRESS_W * 50 / 100)
        assert item["coords"] == [C.PROGRESS_X, C.PROGRESS_Y, expected_x1, C.PROGRESS_Y + C.PROGRESS_H]

    def test_progress_bar_full(self, canvas, renderer):
        content = {"type": "progress", "message": "", "value": 100, "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        _, item = fill_rects[0]
        assert item["coords"][2] == C.PROGRESS_X + C.PROGRESS_W

    def test_progress_bar_empty(self, canvas, renderer):
        content = {"type": "progress", "message": "", "value": 0, "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        assert len(fill_rects) == 0

    def test_progress_message_position(self, canvas, renderer):
        content = {"type": "progress", "message": "Scanning...", "value": 0, "max": 100}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        msg_items = [it for _, it in texts
                     if it["type"] == "text" and it["options"]["text"] == "Scanning..."]
        assert len(msg_items) == 1
        assert msg_items[0]["coords"] == [C.PROGRESS_MSG_X, C.PROGRESS_MSG_Y]

    def test_progress_message_color(self, canvas, renderer):
        content = {"type": "progress", "message": "Reading...", "value": 0, "max": 100}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        msg_items = [it for _, it in texts
                     if it["type"] == "text" and it["options"]["text"] == "Reading..."]
        assert msg_items[0]["options"]["fill"] == C.PROGRESS_MSG_COLOR

    def test_progress_message_anchor(self, canvas, renderer):
        content = {"type": "progress", "message": "Writing...", "value": 0, "max": 100}
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        msg_items = [it for _, it in texts
                     if it["type"] == "text" and it["options"]["text"] == "Writing..."]
        assert msg_items[0]["options"]["anchor"] == C.PROGRESS_MSG_ANCHOR

    def test_progress_detail_text(self, canvas, renderer):
        content = {
            "type": "progress", "message": "", "value": 50, "max": 100,
            "detail": "Sector 3/16",
        }
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "Sector 3/16" in texts

    def test_progress_placeholder_value(self, canvas, renderer):
        renderer.set_state({"prog": "75"})
        content = {"type": "progress", "message": "", "value": "{prog}", "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        assert len(fill_rects) == 1
        _, item = fill_rects[0]
        expected_x1 = C.PROGRESS_X + int(C.PROGRESS_W * 75 / 100)
        assert item["coords"][2] == expected_x1


# =========================================================================
# Content type: text
# =========================================================================

class TestTextContent:
    """Multi-line text display with size and alignment."""

    def test_text_lines_rendered(self, canvas, renderer):
        content = {
            "type": "text",
            "lines": [
                {"text": "ICopy-XS", "size": "large", "align": "center"},
                {"text": ""},
                {"text": "HW  1.0.4"},
            ],
        }
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "ICopy-XS" in texts
        assert "HW  1.0.4" in texts

    def test_text_large_uses_title_font(self, canvas, renderer):
        content = {
            "type": "text",
            "lines": [{"text": "BIG", "size": "large"}],
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "BIG"]
        assert text_items[0]["options"]["font"] == C.FONT_TITLE

    def test_text_normal_uses_progress_font(self, canvas, renderer):
        content = {
            "type": "text",
            "lines": [{"text": "normal line", "size": "normal"}],
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "normal line"]
        assert text_items[0]["options"]["font"] == C.FONT_PROGRESS

    def test_text_center_aligned(self, canvas, renderer):
        content = {
            "type": "text",
            "lines": [{"text": "Centered", "align": "center"}],
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "Centered"]
        assert text_items[0]["coords"][0] == C.SCREEN_W // 2
        assert text_items[0]["options"]["anchor"] == "n"

    def test_text_left_aligned(self, canvas, renderer):
        content = {
            "type": "text",
            "lines": [{"text": "Left", "align": "left"}],
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "Left"]
        assert text_items[0]["coords"][0] == 15
        assert text_items[0]["options"]["anchor"] == "nw"

    def test_text_string_shorthand(self, canvas, renderer):
        """Lines can be plain strings instead of dicts."""
        content = {
            "type": "text",
            "lines": ["Line 1", "Line 2"],
        }
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "Line 1" in texts
        assert "Line 2" in texts

    def test_text_color_is_white(self, canvas, renderer):
        content = {
            "type": "text",
            "lines": [{"text": "Check color"}],
        }
        renderer.render_content(content)
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "Check color"]
        assert text_items[0]["options"]["fill"] == C.BTN_TEXT_COLOR


# =========================================================================
# Content type: input
# =========================================================================

class TestInputContent:
    """Hex/text input display."""

    def test_input_label_rendered(self, canvas, renderer):
        content = {
            "type": "input", "label": "Enter Key A:",
            "format": "hex", "length": 12, "value": "",
            "placeholder": "FFFFFFFFFFFF",
        }
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "Enter Key A:" in texts

    def test_input_placeholder_shown(self, canvas, renderer):
        content = {
            "type": "input", "label": "Key:",
            "value": "", "placeholder": "FFFFFFFFFFFF",
        }
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "FFFFFFFFFFFF" in texts

    def test_input_value_shown(self, canvas, renderer):
        content = {
            "type": "input", "label": "Key:",
            "value": "A0B1C2D3E4F5", "placeholder": "FFFFFFFFFFFF",
        }
        renderer.render_content(content)
        texts = canvas.get_all_text()
        assert "A0B1C2D3E4F5" in texts

    def test_input_box_drawn(self, canvas, renderer):
        content = {"type": "input", "label": "", "value": "", "placeholder": ""}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        input_rects = [(iid, it) for iid, it in rects
                       if it["options"].get("outline") == C.COLOR_ACCENT]
        assert len(input_rects) >= 1

    def test_input_cursor_highlight(self, canvas, renderer):
        content = {
            "type": "input", "label": "",
            "value": "AABBCCDD", "placeholder": "",
            "cursor": 2,
        }
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        highlight_rects = [(iid, it) for iid, it in rects
                          if it["options"].get("fill") == C.INPUT_HIGHLIGHT_COLOR]
        assert len(highlight_rects) == 1


# =========================================================================
# Content type: empty
# =========================================================================

class TestEmptyContent:
    """Empty content area rendering."""

    def test_empty_produces_no_extra_items(self, canvas, renderer):
        content = {"type": "empty"}
        renderer.render_content(content)
        # Only the content background rect from clear_content removal
        # and no additional items from _render_empty
        items = _find_items_by_tag(canvas, TAG_CONTENT)
        assert len(items) == 0  # clear_content removed all, empty adds nothing

    def test_empty_default_type(self, canvas, renderer):
        content = {}  # No type specified -> defaults to "empty"
        renderer.render_content(content)
        items = _find_items_by_tag(canvas, TAG_CONTENT)
        assert len(items) == 0


# =========================================================================
# Toast
# =========================================================================

class TestToast:
    """Toast overlay rendering and clearing."""

    def test_toast_background_drawn(self, canvas, renderer):
        toast = {"text": "Tag Found", "icon": "check", "style": "success"}
        renderer.render_toast(toast)
        rects = _find_rects_by_tag(canvas, TAG_TOAST)
        assert len(rects) >= 1
        _, item = rects[0]
        assert item["options"]["fill"] == C.TOAST_BG

    def test_toast_text_rendered(self, canvas, renderer):
        toast = {"text": "Tag Found", "icon": "check"}
        renderer.render_toast(toast)
        texts = _find_texts_by_tag(canvas, TAG_TOAST)
        assert "Tag Found" in texts

    def test_toast_icon_check(self, canvas, renderer):
        toast = {"text": "OK", "icon": "check"}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        icon_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "\u2713"]
        assert len(icon_items) == 1
        assert icon_items[0]["options"]["fill"] == "#00FF00"

    def test_toast_icon_error(self, canvas, renderer):
        toast = {"text": "Failed", "icon": "error"}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        icon_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "\u2717"]
        assert len(icon_items) == 1
        assert icon_items[0]["options"]["fill"] == "#FF0000"

    def test_toast_icon_warning(self, canvas, renderer):
        toast = {"text": "Warn", "icon": "warning"}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        icon_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "\u26a0"]
        assert len(icon_items) == 1
        assert icon_items[0]["options"]["fill"] == "#FFFF00"

    def test_toast_icon_info(self, canvas, renderer):
        toast = {"text": "Info", "icon": "info"}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        icon_items = [it for _, it in texts
                      if it["type"] == "text" and it["options"]["text"] == "\u2139"]
        assert len(icon_items) == 1
        assert icon_items[0]["options"]["fill"] == "#1C6AEB"

    def test_toast_no_icon(self, canvas, renderer):
        toast = {"text": "Plain toast", "icon": None}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        icon_chars = {"\u2713", "\u2717", "\u26a0", "\u2139"}
        icons_found = [it for _, it in texts
                       if it["type"] == "text" and it["options"].get("text") in icon_chars]
        assert len(icons_found) == 0

    def test_toast_text_color(self, canvas, renderer):
        toast = {"text": "Test", "icon": None}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        msg_items = [it for _, it in texts
                     if it["type"] == "text" and it["options"]["text"] == "Test"]
        assert msg_items[0]["options"]["fill"] == C.TOAST_TEXT_COLOR

    def test_toast_font(self, canvas, renderer):
        toast = {"text": "Check font", "icon": None}
        renderer.render_toast(toast)
        texts = _find_items_by_tag(canvas, TAG_TOAST)
        msg_items = [it for _, it in texts
                     if it["type"] == "text" and it["options"]["text"] == "Check font"]
        assert msg_items[0]["options"]["font"] == C.FONT_TOAST

    def test_toast_border(self, canvas, renderer):
        toast = {"text": "Border", "icon": None}
        renderer.render_toast(toast)
        rects = _find_rects_by_tag(canvas, TAG_TOAST)
        _, item = rects[0]
        assert item["options"]["outline"] == C.TOAST_BORDER

    def test_clear_toast_removes_items(self, canvas, renderer):
        toast = {"text": "Temporary", "icon": "check"}
        renderer.render_toast(toast)
        assert len(canvas.find_withtag(TAG_TOAST)) > 0
        renderer.clear_toast()
        assert len(canvas.find_withtag(TAG_TOAST)) == 0

    def test_toast_overlay_does_not_clear_content(self, canvas, renderer):
        # Draw content first
        content = {"type": "text", "lines": [{"text": "Keep me"}]}
        renderer.render_content(content)
        assert "Keep me" in canvas.get_all_text()
        # Add toast
        toast = {"text": "Overlay", "icon": None}
        renderer.render_toast(toast)
        # Content still present
        assert "Keep me" in canvas.get_all_text()
        assert "Overlay" in canvas.get_all_text()

    def test_toast_text_resolved(self, canvas, renderer):
        renderer.set_state({"msg": "Dynamic Toast"})
        toast = {"text": "{msg}", "icon": None}
        renderer.render_toast(toast)
        texts = _find_texts_by_tag(canvas, TAG_TOAST)
        assert "Dynamic Toast" in texts

    def test_rerender_toast_replaces_previous(self, canvas, renderer):
        renderer.render_toast({"text": "First", "icon": None})
        renderer.render_toast({"text": "Second", "icon": None})
        texts = _find_texts_by_tag(canvas, TAG_TOAST)
        assert "Second" in texts
        assert "First" not in texts


# =========================================================================
# Variable resolution
# =========================================================================

class TestVariableResolution:
    """Placeholder resolution via resolve() and set_state()."""

    def test_resolve_simple(self, canvas, renderer):
        renderer.set_state({"name": "iCopy-X"})
        assert renderer.resolve("{name}") == "iCopy-X"

    def test_resolve_multiple(self, canvas, renderer):
        renderer.set_state({"a": "X", "b": "Y"})
        assert renderer.resolve("{a} and {b}") == "X and Y"

    def test_resolve_no_placeholder(self, canvas, renderer):
        assert renderer.resolve("plain text") == "plain text"

    def test_resolve_unresolved_stays(self, canvas, renderer):
        # No state set for 'missing'
        result = renderer.resolve("{missing}")
        assert result == "{missing}"

    def test_resolve_none_returns_empty(self, canvas, renderer):
        assert renderer.resolve(None) == ""

    def test_resolve_non_string_passthrough(self, canvas, renderer):
        assert renderer.resolve(42) == 42

    def test_set_state_merges(self, canvas, renderer):
        renderer.set_state({"a": "1"})
        renderer.set_state({"b": "2"})
        assert renderer.resolve("{a}") == "1"
        assert renderer.resolve("{b}") == "2"

    def test_set_state_overwrites(self, canvas, renderer):
        renderer.set_state({"key": "old"})
        renderer.set_state({"key": "new"})
        assert renderer.resolve("{key}") == "new"

    def test_resolve_partial_unresolved(self, canvas, renderer):
        renderer.set_state({"known": "OK"})
        result = renderer.resolve("{known} and {unknown}")
        # With partial resolution failure, original text returned
        assert "{unknown}" in result


# =========================================================================
# Clear operations
# =========================================================================

class TestClearOperations:
    """clear_content, clear_toast, clear_all."""

    def test_clear_content_removes_content_tags(self, canvas, renderer):
        content = {"type": "text", "lines": [{"text": "Remove me"}]}
        renderer.render_content(content)
        assert len(canvas.find_withtag(TAG_CONTENT)) > 0
        renderer.clear_content()
        assert len(canvas.find_withtag(TAG_CONTENT)) == 0

    def test_clear_content_preserves_title(self, canvas, renderer):
        renderer.render_title("Keep Title")
        content = {"type": "text", "lines": [{"text": "Remove"}]}
        renderer.render_content(content)
        renderer.clear_content()
        assert "Keep Title" in canvas.get_all_text()

    def test_clear_content_preserves_buttons(self, canvas, renderer):
        renderer.render_buttons("Left", "Right")
        content = {"type": "text", "lines": [{"text": "Remove"}]}
        renderer.render_content(content)
        renderer.clear_content()
        assert "Left" in canvas.get_all_text()
        assert "Right" in canvas.get_all_text()

    def test_clear_toast_preserves_content(self, canvas, renderer):
        content = {"type": "text", "lines": [{"text": "Stay"}]}
        renderer.render_content(content)
        renderer.render_toast({"text": "Gone", "icon": None})
        renderer.clear_toast()
        assert "Stay" in canvas.get_all_text()
        assert "Gone" not in canvas.get_all_text()

    def test_clear_all_removes_everything(self, canvas, renderer):
        renderer.render_title("Title")
        renderer.render_buttons("L", "R")
        renderer.render_content({"type": "text", "lines": [{"text": "Body"}]})
        renderer.render_toast({"text": "Toast", "icon": None})
        renderer.clear_all()
        assert canvas.find_all() == ()


# =========================================================================
# Full screen render
# =========================================================================

class TestFullRender:
    """Render a complete screen definition end-to-end."""

    SCAN_FOUND = {
        "id": "scan_found",
        "title": "Scan Tag",
        "page": "1/1",
        "content": {
            "type": "template",
            "header": "{tag_type}",
            "subheader": "M1 S50 1K",
            "fields": [
                {"label": "UID", "value": "{uid}"},
            ],
        },
        "toast": {"text": "Tag Found", "icon": "check", "timeout": 3000},
        "buttons": {"left": "Rescan", "right": "Simulate"},
    }

    def test_full_render_has_title(self, canvas, renderer):
        renderer.render(self.SCAN_FOUND, state={"tag_type": "MIFARE", "uid": "AABB"})
        assert "Scan Tag" in canvas.get_all_text()

    def test_full_render_has_page_indicator(self, canvas, renderer):
        renderer.render(self.SCAN_FOUND, state={"tag_type": "MIFARE", "uid": "AABB"})
        assert "1/1" in canvas.get_all_text()

    def test_full_render_has_content(self, canvas, renderer):
        renderer.render(self.SCAN_FOUND, state={"tag_type": "MIFARE", "uid": "AABB"})
        assert "MIFARE" in canvas.get_all_text()
        assert "UID: AABB" in canvas.get_all_text()

    def test_full_render_has_buttons(self, canvas, renderer):
        renderer.render(self.SCAN_FOUND, state={"tag_type": "MIFARE", "uid": "AABB"})
        assert "Rescan" in canvas.get_all_text()
        assert "Simulate" in canvas.get_all_text()

    def test_full_render_has_toast(self, canvas, renderer):
        renderer.render(self.SCAN_FOUND, state={"tag_type": "MIFARE", "uid": "AABB"})
        assert "Tag Found" in canvas.get_all_text()

    def test_full_render_clears_previous(self, canvas, renderer):
        renderer.render(self.SCAN_FOUND, state={"tag_type": "A", "uid": "1"})
        renderer.render({
            "title": "New",
            "content": {"type": "empty"},
            "buttons": {"left": None, "right": None},
        })
        assert "Scan Tag" not in canvas.get_all_text()
        assert "MIFARE" not in canvas.get_all_text()
        assert "New" in canvas.get_all_text()

    def test_full_render_state_persists(self, canvas, renderer):
        """State from render() call persists to next render."""
        renderer.render(self.SCAN_FOUND, state={"tag_type": "MIFARE", "uid": "AABB"})
        # State should be available on the renderer
        assert renderer.resolve("{uid}") == "AABB"

    MAIN_MENU = {
        "id": "main_page",
        "title": "Main Page",
        "page": "1/2",
        "content": {
            "type": "list",
            "style": "menu",
            "selected": 0,
            "items": [
                {"label": "Auto Copy", "icon": "icon_autocopy.png"},
                {"label": "Scan Tag", "icon": "icon_scan.png"},
                {"label": "Read Tag", "icon": "icon_read.png"},
                {"label": "Write Tag", "icon": "icon_write.png"},
            ],
        },
        "buttons": {"left": None, "right": "OK"},
    }

    def test_main_menu_render(self, canvas, renderer):
        renderer.render(self.MAIN_MENU)
        texts = canvas.get_all_text()
        assert "Main Page" in texts
        assert "Auto Copy" in texts
        assert "OK" in texts

    def test_main_menu_selection_on_first(self, canvas, renderer):
        renderer.render(self.MAIN_MENU)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        sel_rects = [(iid, it) for iid, it in rects
                     if it["options"].get("fill") == C.SELECT_BG]
        assert len(sel_rects) == 1
        _, item = sel_rects[0]
        assert item["coords"][1] == C.CONTENT_Y0  # First item

    VOLUME_SCREEN = {
        "id": "volume",
        "title": "Volume",
        "content": {
            "type": "list",
            "style": "radio",
            "selected": 2,
            "items": [
                {"label": "Off"},
                {"label": "Low"},
                {"label": "Middle", "checked": True},
                {"label": "High"},
            ],
        },
        "buttons": {"left": "Back", "right": "OK"},
    }

    def test_volume_radio_screen(self, canvas, renderer):
        renderer.render(self.VOLUME_SCREEN)
        texts = canvas.get_all_text()
        assert "Volume" in texts
        assert "Off" in texts
        assert "Middle" in texts
        assert "Back" in texts
        assert "OK" in texts

    PROGRESS_SCREEN = {
        "title": "Read Tag",
        "content": {
            "type": "progress",
            "message": "Reading...",
            "value": 30,
            "max": 100,
            "detail": "Sector 3/16",
        },
        "buttons": {"left": None, "right": "Stop"},
    }

    def test_progress_screen(self, canvas, renderer):
        renderer.render(self.PROGRESS_SCREEN)
        texts = canvas.get_all_text()
        assert "Read Tag" in texts
        assert "Reading..." in texts
        assert "Sector 3/16" in texts
        assert "Stop" in texts


# =========================================================================
# Edge cases
# =========================================================================

class TestEdgeCases:
    """Edge cases and error handling."""

    def test_render_empty_screen(self, canvas, renderer):
        renderer.render({"title": "", "content": {"type": "empty"}, "buttons": {}})
        # Should not crash; title bar and button bar still drawn
        assert len(canvas.find_all()) > 0

    def test_render_missing_content(self, canvas, renderer):
        renderer.render({"title": "No Content"})
        assert "No Content" in canvas.get_all_text()

    def test_render_missing_buttons(self, canvas, renderer):
        renderer.render({"title": "T", "content": {"type": "empty"}})
        # Should not crash
        assert "T" in canvas.get_all_text()

    def test_render_unknown_content_type(self, canvas, renderer):
        """Unknown content type falls back to empty."""
        renderer.render({"title": "T", "content": {"type": "unknown_widget"}})
        assert "T" in canvas.get_all_text()

    def test_list_empty_items(self, canvas, renderer):
        content = {"type": "list", "items": [], "style": "plain", "selected": 0}
        renderer.render_content(content)
        # No items rendered, no crash
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts if it["type"] == "text"]
        assert len(text_items) == 0

    def test_progress_max_zero(self, canvas, renderer):
        content = {"type": "progress", "message": "x", "value": 50, "max": 0}
        renderer.render_content(content)
        # No fill drawn when max is 0
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        assert len(fill_rects) == 0

    def test_template_empty_fields(self, canvas, renderer):
        content = {"type": "template", "header": "H", "fields": []}
        renderer.render_content(content)
        assert "H" in canvas.get_all_text()

    def test_text_empty_lines(self, canvas, renderer):
        content = {"type": "text", "lines": []}
        renderer.render_content(content)
        # No crash, no text items
        texts = _find_items_by_tag(canvas, TAG_CONTENT)
        text_items = [it for _, it in texts if it["type"] == "text"]
        assert len(text_items) == 0

    def test_render_content_with_state_param(self, canvas, renderer):
        content = {
            "type": "template",
            "header": "{title}",
            "fields": [],
        }
        renderer.render_content(content, state={"title": "Dynamic"})
        assert "Dynamic" in canvas.get_all_text()

    def test_toast_with_state_param(self, canvas, renderer):
        renderer.render_toast({"text": "{msg}", "icon": None}, state={"msg": "Hello"})
        assert "Hello" in canvas.get_all_text()

    def test_progress_value_exceeds_max(self, canvas, renderer):
        """Value > max should clamp at max."""
        content = {"type": "progress", "message": "", "value": 200, "max": 100}
        renderer.render_content(content)
        rects = _find_rects_by_tag(canvas, TAG_CONTENT)
        fill_rects = [(iid, it) for iid, it in rects
                      if it["options"].get("fill") == C.PROGRESS_FG]
        assert len(fill_rects) == 1
        _, item = fill_rects[0]
        assert item["coords"][2] == C.PROGRESS_X + C.PROGRESS_W
