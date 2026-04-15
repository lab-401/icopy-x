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

"""JSON screen definition -> Canvas renderer engine.

Takes a JSON screen definition dict and draws it to a tkinter Canvas
(240x240), pixel-identical to the original iCopy-X v1.0.90 firmware.

The renderer handles:
  - Title bar: #7C829A background, white centered text
  - Content area: dispatches by content.type to type-specific renderers
  - Button bar: #222222 background, M1 at (15,228) sw, M2 at (225,228) se
  - Toast overlay: on top of everything, with icon and auto-dismiss
  - Page indicator: arrows for multi-page lists

The renderer does NOT handle key events or activity lifecycle -- those
are the state machine's and actstack's jobs respectively.

Source key:
    SPEC  = docs/UI_SPEC.md (QEMU-verified canvas items)
    SCHEMA = docs/UI_JSON_SCHEMA.md (JSON contract)
    CONST = src/lib/_constants.py (all pixel values)
"""

from . import _constants as C


# =========================================================================
# Canvas tag constants -- used for layer management
# =========================================================================
TAG_TITLE_BAR = "title_bar"
TAG_TITLE_TEXT = "title_text"
TAG_PAGE_INDICATOR = "page_indicator"
TAG_CONTENT = "content"
TAG_BUTTON_BAR = "button_bar"
TAG_BUTTON_LEFT = "button_left"
TAG_BUTTON_RIGHT = "button_right"
TAG_TOAST = "toast"


class Renderer:
    """Renders JSON screen definitions to a tkinter Canvas (240x240).

    Public methods operate on canvas regions independently so callers can
    update title, content, buttons, or toast without a full redraw.
    """

    def __init__(self, canvas):
        """Initialize with a tkinter Canvas (240x240).

        Args:
            canvas: tkinter.Canvas instance (or MockCanvas for testing).
        """
        self._canvas = canvas
        self._state = {}
        self._toast_items = []

    # =====================================================================
    # Public API
    # =====================================================================

    def render(self, screen_def, state=None):
        """Render a complete screen definition to the canvas.

        Args:
            screen_def: JSON screen definition dict (from screen.json).
            state: Variable state dict for {placeholder} resolution.
                   Merged into the renderer's internal state.
        """
        if state is not None:
            self._state.update(state)

        self.clear_all()

        # Title bar
        title = screen_def.get("title", "")
        page = screen_def.get("page")
        self.render_title(title, page)

        # Content area background
        self._canvas.create_rectangle(
            0, C.CONTENT_Y0, C.SCREEN_W, C.CONTENT_Y1,
            fill=C.CONTENT_BG, outline="", tags=(TAG_CONTENT,),
        )

        # Content
        content = screen_def.get("content", {})
        self.render_content(content)

        # Button bar
        buttons = screen_def.get("buttons", {})
        self.render_buttons(buttons.get("left"), buttons.get("right"))

        # Toast (on top of everything)
        toast = screen_def.get("toast")
        if toast:
            self.render_toast(toast)

    def render_title(self, title, page=None):
        """Render just the title bar.

        SPEC section 2.1 / 12.1:
          Rectangle (0,0,240,40) fill='#7C829A' outline=''
          Text (120,20) fill='white' anchor='center'
        """
        c = self._canvas
        # Remove previous title elements
        c.delete(TAG_TITLE_BAR)
        c.delete(TAG_TITLE_TEXT)
        c.delete(TAG_PAGE_INDICATOR)

        # Background rectangle
        c.create_rectangle(
            0, C.TITLE_BAR_Y0, C.SCREEN_W, C.TITLE_BAR_Y1,
            fill=C.TITLE_BAR_BG, outline="", tags=(TAG_TITLE_BAR,),
        )

        # Title text
        resolved_title = self.resolve(title)
        c.create_text(
            C.TITLE_TEXT_X, C.TITLE_TEXT_Y,
            text=resolved_title,
            fill=C.TITLE_TEXT_COLOR,
            font=C.FONT_TITLE,
            anchor=C.TITLE_TEXT_ANCHOR,
            tags=(TAG_TITLE_TEXT,),
        )

        # Page indicator (shown in title area when provided)
        if page:
            resolved_page = self.resolve(page)
            c.create_text(
                C.SCREEN_W - 40, C.TITLE_TEXT_Y,
                text=resolved_page,
                fill=C.TITLE_TEXT_COLOR,
                font=C.FONT_PAGE_ARROW,
                anchor="center",
                tags=(TAG_PAGE_INDICATOR,),
            )

    def render_buttons(self, left=None, right=None):
        """Render just the button bar.

        SPEC section 2.2 / 12.2-12.4:
          Background: rectangle (0,200,240,240) fill='#222222'
          Left text:  (15,228) anchor='sw'
          Right text: (225,228) anchor='se'
        """
        c = self._canvas
        c.delete(TAG_BUTTON_BAR)
        c.delete(TAG_BUTTON_LEFT)
        c.delete(TAG_BUTTON_RIGHT)

        # Background
        c.create_rectangle(
            0, C.BTN_BAR_Y0, C.SCREEN_W, C.BTN_BAR_Y1,
            fill=C.BTN_BAR_BG, outline="", tags=(TAG_BUTTON_BAR,),
        )

        # Left button (M1)
        if left is not None:
            c.create_text(
                C.BTN_LEFT_X, C.BTN_LEFT_Y,
                text=self.resolve(left),
                fill=C.BTN_TEXT_COLOR,
                font=C.FONT_BUTTON,
                anchor=C.BTN_LEFT_ANCHOR,
                tags=(TAG_BUTTON_LEFT,),
            )

        # Right button (M2)
        if right is not None:
            c.create_text(
                C.BTN_RIGHT_X, C.BTN_RIGHT_Y,
                text=self.resolve(right),
                fill=C.BTN_TEXT_COLOR,
                font=C.FONT_BUTTON,
                anchor=C.BTN_RIGHT_ANCHOR,
                tags=(TAG_BUTTON_RIGHT,),
            )

    def render_content(self, content, state=None):
        """Render just the content area, dispatching by content.type.

        Clears existing content first, then draws new content.

        Args:
            content: content dict with 'type' key.
            state: optional state dict (merged into renderer state).
        """
        if state is not None:
            self._state.update(state)

        self.clear_content()

        content_type = content.get("type", "empty")
        dispatch = {
            "list": _render_list,
            "template": _render_template,
            "progress": _render_progress,
            "card_info_with_progress": _render_card_info_with_progress,
            "text": _render_text,
            "input": _render_input,
            "empty": _render_empty,
        }
        handler = dispatch.get(content_type, _render_empty)
        handler(self._canvas, content, self._state)

    def render_toast(self, toast, state=None):
        """Render toast overlay on top of everything.

        Args:
            toast: toast dict with text, icon, timeout, style.
            state: optional state dict.
        """
        if state is not None:
            self._state.update(state)
        self.clear_toast()
        _render_toast(self._canvas, toast, self._state, self._toast_items,
                      resolve_fn=self.resolve)

    def clear_toast(self):
        """Remove toast overlay items from the canvas."""
        self._canvas.delete(TAG_TOAST)
        self._toast_items.clear()

    def clear_content(self):
        """Clear the content area only."""
        self._canvas.delete(TAG_CONTENT)

    def clear_all(self):
        """Clear entire canvas."""
        self._canvas.delete("all")
        self._toast_items.clear()

    def set_state(self, state):
        """Update variable state for placeholder resolution.

        Args:
            state: dict of key-value pairs to merge into current state.
        """
        self._state.update(state)

    def resolve(self, text):
        """Resolve {placeholders} in text from current state.

        Unresolved placeholders are left as-is (e.g. '{unknown}' stays).

        Args:
            text: string potentially containing {key} placeholders.

        Returns:
            Resolved string, or original text if resolution fails.
        """
        if text is None:
            return ""
        if not isinstance(text, str) or "{" not in text:
            return text
        try:
            return text.format(**self._state)
        except (KeyError, ValueError, IndexError):
            # Unresolved placeholders stay as-is
            return text


# =========================================================================
# Content type renderers (module-level functions, called by Renderer)
# =========================================================================

def _render_list(canvas, content, state):
    """Render scrollable item list.

    SPEC section 5.2 / 12.6:
      Item height: 40px, 5 items per page (extends into button bar y=220).
      Selection rect: (0,y,240,y+40) fill='#EEEEEE' outline='black' width=0
      Text: (19,y+20) anchor='w' or (50,y+20) with icon.

    Styles: menu (icon+label), radio (label+indicator), checklist, plain.
    """
    items = content.get("items", [])
    style = content.get("style", "plain")
    selected = content.get("selected", 0)
    page_size = content.get("page_size", C.LIST_ITEMS_PER_PAGE)
    scroll_offset = content.get("scroll_offset", 0)

    # Determine visible items
    visible = items[scroll_offset:scroll_offset + page_size]

    for i, item in enumerate(visible):
        abs_index = scroll_offset + i
        y = C.CONTENT_Y0 + i * C.LIST_ITEM_H
        is_selected = (abs_index == selected)

        # Selection highlight
        if is_selected:
            canvas.create_rectangle(
                0, y, C.SCREEN_W, y + C.LIST_ITEM_H,
                fill=C.SELECT_BG,
                outline=C.SELECT_OUTLINE,
                width=C.SELECT_OUTLINE_WIDTH,
                tags=(TAG_CONTENT,),
            )

        label = _resolve_text(item.get("label", ""), state)
        text_color = C.SELECT_TEXT_COLOR if is_selected else C.NORMAL_TEXT_COLOR

        if style == "menu":
            # Icon + label (icon at LIST_ICON_X, text at LIST_TEXT_X_WITH_ICON)
            icon = item.get("icon")
            text_x = C.LIST_TEXT_X_WITH_ICON if icon else C.LIST_TEXT_X_NO_ICON
            canvas.create_text(
                text_x, y + C.LIST_ITEM_H // 2,
                text=label, fill=text_color,
                font=C.FONT_CONTENT, anchor=C.LIST_TEXT_ANCHOR,
                tags=(TAG_CONTENT,),
            )
            # Icon rendering is handled by images module (not renderer's job)
            # but we mark the position so the widget layer can overlay icons.

        elif style == "radio":
            canvas.create_text(
                C.LIST_TEXT_X_NO_ICON, y + C.LIST_ITEM_H // 2,
                text=label, fill=text_color,
                font=C.FONT_CONTENT, anchor=C.LIST_TEXT_ANCHOR,
                tags=(TAG_CONTENT,),
            )
            # Radio indicator on right side
            chk_x = C.SCREEN_W - 30
            chk_y = y + C.LIST_ITEM_H // 2
            chk_sz = 8
            if item.get("checked", False):
                canvas.create_rectangle(
                    chk_x - chk_sz, chk_y - chk_sz,
                    chk_x + chk_sz, chk_y + chk_sz,
                    fill=C.COLOR_ACCENT, outline=C.BTN_TEXT_COLOR, width=2,
                    tags=(TAG_CONTENT,),
                )
            else:
                canvas.create_rectangle(
                    chk_x - chk_sz, chk_y - chk_sz,
                    chk_x + chk_sz, chk_y + chk_sz,
                    fill="", outline="grey", width=1,
                    tags=(TAG_CONTENT,),
                )

        elif style == "checklist":
            canvas.create_text(
                C.LIST_TEXT_X_NO_ICON, y + C.LIST_ITEM_H // 2,
                text=label, fill=text_color,
                font=C.FONT_CONTENT, anchor=C.LIST_TEXT_ANCHOR,
                tags=(TAG_CONTENT,),
            )
            # Checkbox square on RIGHT side (matches CheckedListView widget)
            half_box = C.CHECK_BOX_SIZE // 2
            chk_cx = C.SCREEN_W - C.CHECK_BOX_MARGIN_RIGHT - half_box
            chk_cy = y + C.LIST_ITEM_H // 2
            box_x0 = chk_cx - half_box
            box_y0 = chk_cy - half_box
            box_x1 = chk_cx + half_box
            box_y1 = chk_cy + half_box
            if item.get("checked", False):
                # Checked: outer blue border + inner blue fill
                canvas.create_rectangle(
                    box_x0, box_y0, box_x1, box_y1,
                    outline=C.CHECK_COLOR_CHECKED_BORDER,
                    fill="",
                    tags=(TAG_CONTENT,),
                )
                canvas.create_rectangle(
                    box_x0 + C.CHECK_INNER_INSET, box_y0 + C.CHECK_INNER_INSET,
                    box_x1 - C.CHECK_INNER_INSET, box_y1 - C.CHECK_INNER_INSET,
                    fill=C.CHECK_COLOR_CHECKED_FILL,
                    outline="",
                    tags=(TAG_CONTENT,),
                )
            else:
                # Unchecked: grey border, no fill
                canvas.create_rectangle(
                    box_x0, box_y0, box_x1, box_y1,
                    fill="", outline=C.CHECK_COLOR_UNCHECKED_BORDER,
                    tags=(TAG_CONTENT,),
                )

        else:  # plain
            canvas.create_text(
                C.LIST_TEXT_X_NO_ICON, y + C.LIST_ITEM_H // 2,
                text=label, fill=text_color,
                font=C.FONT_CONTENT, anchor=C.LIST_TEXT_ANCHOR,
                tags=(TAG_CONTENT,),
            )

    # Page arrows -- show when items span multiple pages
    total_items = len(items)
    if scroll_offset > 0:
        canvas.create_text(
            C.SCREEN_W // 2, C.CONTENT_Y0 + 2,
            text="\u25b2", fill=C.PAGE_INDICATOR_COLOR,
            font=C.FONT_PAGE_ARROW, anchor="n",
            tags=(TAG_CONTENT, TAG_PAGE_INDICATOR),
        )
    if scroll_offset + page_size < total_items:
        canvas.create_text(
            C.SCREEN_W // 2, C.CONTENT_Y1 - 2,
            text="\u25bc", fill=C.PAGE_INDICATOR_COLOR,
            font=C.FONT_PAGE_ARROW, anchor="s",
            tags=(TAG_CONTENT, TAG_PAGE_INDICATOR),
        )


def _render_template(canvas, content, state):
    """Render tag info display (header, subheader, field rows).

    Fields can use {variable} placeholders resolved from state.
    Fields can be single or row-grouped (side by side).
    """
    y = C.CONTENT_Y0 + 8

    header = _resolve_text(content.get("header", ""), state)
    if header:
        canvas.create_text(
            C.SCREEN_W // 2, y, text=header,
            fill=C.BTN_TEXT_COLOR, font=C.FONT_TITLE,
            anchor="n", tags=(TAG_CONTENT,),
        )
        y += 22

    subheader = _resolve_text(content.get("subheader", ""), state)
    if subheader:
        canvas.create_text(
            C.SCREEN_W // 2, y, text=subheader,
            fill=C.BTN_TEXT_COLOR, font=C.FONT_TOAST,
            anchor="n", tags=(TAG_CONTENT,),
        )
        y += 18

    for field in content.get("fields", []):
        y += 4
        if "row" in field:
            # Inline fields (e.g. SAK + ATQA on same line)
            row = field["row"]
            col_w = C.SCREEN_W // max(len(row), 1)
            x = 10
            for rf in row:
                label = _resolve_text(rf.get("label", ""), state)
                value = _resolve_text(rf.get("value", ""), state)
                text = "%s: %s" % (label, value) if value else label
                canvas.create_text(
                    x, y, text=text,
                    fill=C.BTN_TEXT_COLOR, font=C.FONT_PROGRESS,
                    anchor="nw", tags=(TAG_CONTENT,),
                )
                x += col_w
            y += 16
        else:
            label = _resolve_text(field.get("label", ""), state)
            value = _resolve_text(field.get("value", ""), state)
            text = "%s: %s" % (label, value) if value else label
            canvas.create_text(
                10, y, text=text,
                fill=C.BTN_TEXT_COLOR, font=C.FONT_PROGRESS,
                anchor="nw", tags=(TAG_CONTENT,),
            )
            y += 16


def _render_progress(canvas, content, state):
    """Render progress bar at fixed position.

    SPEC section 5.4 / 12.7:
      Background rect: (20,100,220,120) fill='#eeeeee'
      Fill rect:       (20,100,20+fw,120) fill='#1C6AEB'
      Message text:    (120,98) fill='#1C6AEB' anchor='s'
    """
    message = _resolve_text(content.get("message", ""), state)
    detail = _resolve_text(content.get("detail"), state)

    # Resolve value/max -- may be placeholders like "{scan_progress}"
    raw_value = content.get("value", 0)
    raw_max = content.get("max", 100)
    value = _resolve_int(raw_value, state)
    max_val = _resolve_int(raw_max, state)

    # Message text above bar
    if message:
        canvas.create_text(
            C.PROGRESS_MSG_X, C.PROGRESS_MSG_Y,
            text=message, fill=C.PROGRESS_MSG_COLOR,
            font=C.FONT_PROGRESS, anchor=C.PROGRESS_MSG_ANCHOR,
            tags=(TAG_CONTENT,),
        )

    # Background rect
    canvas.create_rectangle(
        C.PROGRESS_X, C.PROGRESS_Y,
        C.PROGRESS_X + C.PROGRESS_W, C.PROGRESS_Y + C.PROGRESS_H,
        fill=C.PROGRESS_BG, outline="",
        tags=(TAG_CONTENT,),
    )

    # Fill rect
    if max_val > 0 and value > 0:
        fill_w = int(C.PROGRESS_W * min(value, max_val) / max_val)
        if fill_w > 0:
            canvas.create_rectangle(
                C.PROGRESS_X, C.PROGRESS_Y,
                C.PROGRESS_X + fill_w, C.PROGRESS_Y + C.PROGRESS_H,
                fill=C.PROGRESS_FG, outline="",
                tags=(TAG_CONTENT,),
            )

    # Detail text below bar
    if detail:
        canvas.create_text(
            C.PROGRESS_MSG_X, C.PROGRESS_Y + C.PROGRESS_H + 15,
            text=detail, fill=C.BTN_TEXT_COLOR,
            font=C.FONT_PROGRESS, anchor="center",
            tags=(TAG_CONTENT,),
        )


def _render_card_info_with_progress(canvas, content, state):
    """Render card info template + progress bar.

    Used by the reading state in read_tag.json.  Renders the tag info
    template (via template.draw) at the top and a progress bar at the
    fixed position at the bottom.  The activity code handles this
    directly via template.draw() + ProgressBar widget, but this
    renderer implementation ensures the dispatch table is complete.

    JSON schema:
        card_info:        template placeholder (scan cache dict)
        progress_message: status text above bar
        progress_value:   current progress (0-max)
        progress_max:     maximum value (default 100)
    """
    # Card info template is rendered by template.draw() in the activity
    # layer.  The renderer can only draw the progress portion since the
    # template module needs the raw tag_type + data dict, not a
    # JSON-resolved string.

    # Progress portion — reuse _render_progress with mapped keys
    progress_content = {
        "message": content.get("progress_message", ""),
        "value": content.get("progress_value", 0),
        "max": content.get("progress_max", 100),
    }
    _render_progress(canvas, progress_content, state)


def _render_text(canvas, content, state):
    """Render multi-line text display.

    Supports size ("large", "normal") and align ("center", "left").
    """
    lines = content.get("lines", [])
    y = C.CONTENT_Y0 + 10

    for line_def in lines:
        if isinstance(line_def, str):
            line_def = {"text": line_def}

        text = _resolve_text(line_def.get("text", ""), state)
        size = line_def.get("size", "normal")
        align = line_def.get("align", "left")

        if size == "large":
            font = C.FONT_TITLE
            line_h = 24
        else:
            font = C.FONT_PROGRESS
            line_h = 16

        if align == "center":
            x = C.SCREEN_W // 2
            anchor = "n"
        else:
            x = 15
            anchor = "nw"

        canvas.create_text(
            x, y, text=text,
            fill=C.BTN_TEXT_COLOR, font=font,
            anchor=anchor, tags=(TAG_CONTENT,),
        )
        y += line_h


def _render_input(canvas, content, state):
    """Render hex/text input display.

    Shows label, input box, current value with cursor position.
    """
    label = _resolve_text(content.get("label", ""), state)
    value = content.get("value", "")
    placeholder = content.get("placeholder", "")
    cursor_pos = content.get("cursor", -1)

    y = C.CONTENT_Y0 + 40

    # Label
    if label:
        canvas.create_text(
            C.SCREEN_W // 2, y, text=label,
            fill=C.BTN_TEXT_COLOR, font=C.FONT_CONTENT,
            anchor="center", tags=(TAG_CONTENT,),
        )
        y += 30

    # Input box
    canvas.create_rectangle(
        20, y, 220, y + 30,
        fill=C.INPUT_BG_COLOR, outline=C.COLOR_ACCENT, width=2,
        tags=(TAG_CONTENT,),
    )

    # Display text (value or placeholder)
    display = value if value else placeholder
    color = C.INPUT_DATA_COLOR if value else "grey"
    canvas.create_text(
        C.SCREEN_W // 2, y + 15, text=display,
        fill=color, font=C.FONT_CONTENT,
        anchor="center", tags=(TAG_CONTENT,),
    )

    # Cursor highlight (per-character highlight if cursor_pos >= 0)
    if cursor_pos >= 0 and value and cursor_pos < len(value):
        # Approximate character width for monospace font
        char_w = 10  # mononoki 13pt approximate
        total_w = len(value) * char_w
        start_x = C.SCREEN_W // 2 - total_w // 2
        cursor_x = start_x + cursor_pos * char_w
        canvas.create_rectangle(
            cursor_x, y + 2, cursor_x + char_w, y + 28,
            fill=C.INPUT_HIGHLIGHT_COLOR, outline="",
            tags=(TAG_CONTENT,),
        )


def _render_empty(canvas, content, state):
    """Clear content area (just background).

    The content area background is already drawn by render(), so this
    is intentionally a no-op.
    """
    pass


# =========================================================================
# Toast rendering
# =========================================================================

def _render_toast(canvas, toast_def, state, toast_items, resolve_fn=None):
    """Overlay toast on canvas.

    Toast dict has: text, icon, timeout, style.
    Draws semi-transparent overlay, centered text, optional icon.

    Icon mapping:
      check   -> green checkmark
      error   -> red X
      warning -> yellow triangle
      info    -> blue info circle

    Uses TAG_TOAST for easy removal.
    """
    if resolve_fn is None:
        resolve_fn = lambda t: _resolve_text(t, state)

    text = resolve_fn(toast_def.get("text", ""))
    icon = toast_def.get("icon")
    style = toast_def.get("style", "info")

    # Semi-transparent overlay background
    overlay_id = canvas.create_rectangle(
        C.TOAST_MARGIN, C.TOAST_CENTER_Y - C.TOAST_H // 2,
        C.SCREEN_W - C.TOAST_MARGIN, C.TOAST_CENTER_Y + C.TOAST_H // 2,
        fill=C.TOAST_BG, outline=C.TOAST_BORDER, width=1,
        tags=(TAG_TOAST,),
    )
    toast_items.append(overlay_id)

    # Icon characters and colors
    icon_map = {
        "check": ("\u2713", "#00FF00"),     # green checkmark
        "error": ("\u2717", "#FF0000"),     # red X
        "warning": ("\u26a0", "#FFFF00"),   # yellow warning
        "info": ("\u2139", "#1C6AEB"),      # blue info
    }

    icon_x = C.TOAST_MARGIN + 25
    text_x = C.SCREEN_W // 2

    if icon and icon in icon_map:
        icon_char, icon_color = icon_map[icon]
        icon_id = canvas.create_text(
            icon_x, C.TOAST_CENTER_Y,
            text=icon_char, fill=icon_color,
            font=C.FONT_TOAST, anchor="center",
            tags=(TAG_TOAST,),
        )
        toast_items.append(icon_id)
        text_x = C.SCREEN_W // 2 + 10  # shift text right to make room

    # Toast text (supports multiline with \n)
    text_id = canvas.create_text(
        text_x, C.TOAST_CENTER_Y,
        text=text, fill=C.TOAST_TEXT_COLOR,
        font=C.FONT_TOAST, anchor="center",
        tags=(TAG_TOAST,),
    )
    toast_items.append(text_id)


# =========================================================================
# Internal helpers
# =========================================================================

def _resolve_text(text, state):
    """Resolve {placeholders} in text from state dict.

    Returns original text if resolution fails. None becomes empty string.
    """
    if text is None:
        return ""
    if not isinstance(text, str) or "{" not in text:
        return text
    try:
        return text.format(**state)
    except (KeyError, ValueError, IndexError):
        return text


def _resolve_int(raw, state):
    """Resolve a value that may be an int or a {placeholder} string."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        resolved = _resolve_text(raw, state)
        try:
            return int(resolved)
        except (ValueError, TypeError):
            return 0
    return 0
