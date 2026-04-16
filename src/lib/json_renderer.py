##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""JSON UI Schema → tkinter Canvas renderer.

Renders screen definitions from JSON into a 240x240 tkinter Canvas.
Visual constants are sourced from _constants.py which derives from
ground-truth measurements of the real iCopy-X v1.0.90 device.

Activities define their UI declaratively as JSON screen dicts. The
renderer translates those dicts into canvas draw calls. Activities
handle logic (key events, .so callbacks, state transitions) and tell
the renderer what screen to draw.

Usage:
    from lib.json_renderer import JsonRenderer
    renderer = JsonRenderer(canvas)
    renderer.set_state({'uid': '3AF73501', 'tag_family': 'MIFARE'})
    renderer.render(screen_dict)
"""

import json
import os

from lib._constants import (
    SCREEN_W, SCREEN_H,
    CONTENT_Y0, CONTENT_H,
    BTN_BAR_Y0, BTN_BAR_BG, BTN_TEXT_COLOR, BTN_TEXT_COLOR_DISABLED,
    BTN_LEFT_X, BTN_LEFT_Y, BTN_LEFT_ANCHOR,
    BTN_RIGHT_X, BTN_RIGHT_Y, BTN_RIGHT_ANCHOR,
    TITLE_BAR_BG, TITLE_BAR_H, TITLE_TEXT_COLOR,
    BG_COLOR,
    SELECT_BG,
    NORMAL_TEXT_COLOR,
    PROGRESS_X, PROGRESS_Y, PROGRESS_W, PROGRESS_H,
    PROGRESS_BG, PROGRESS_FG, PROGRESS_MSG_COLOR,
    COLOR_ACCENT,
    BATTERY_X, BATTERY_Y, BATTERY_W, BATTERY_H,
    BATTERY_OUTLINE_COLOR, BATTERY_OUTLINE_WIDTH,
    BATTERY_PIP_X0, BATTERY_PIP_Y0, BATTERY_PIP_X1, BATTERY_PIP_Y1,
    BATTERY_PIP_COLOR,
    BATTERY_FILL_X0, BATTERY_FILL_Y0, BATTERY_FILL_Y1,
    BATTERY_FILL_MAX_W,
    BATTERY_COLOR_HIGH, BATTERY_COLOR_MED, BATTERY_COLOR_LOW,
    BATTERY_THRESHOLD_HIGH, BATTERY_THRESHOLD_LOW,
    LIST_ITEM_H, LIST_ITEMS_PER_PAGE,
    LIST_TEXT_X_NO_ICON, LIST_TEXT_X_WITH_ICON,
    CHECK_BOX_SIZE, CHECK_BOX_MARGIN_RIGHT,
    CHECK_COLOR_UNCHECKED_BORDER, CHECK_COLOR_CHECKED_FILL,
    PAGE_INDICATOR_COLOR,
    ICON_RECOLOR_NORMAL, ICON_RECOLOR_SELECTED,
    INPUT_DATA_COLOR, INPUT_FIELD_BG, INPUT_BG_COLOR,
    TE_DATE_BOX, TE_TIME_BOX,
    TE_YEAR_BOX, TE_MONTH_BOX, TE_DAY_BOX,
    TE_HOUR_BOX, TE_MINUTE_BOX, TE_SECOND_BOX,
    TE_FIELD_FONT_SIZE,
    TE_DATE_Y, TE_YEAR_X, TE_MONTH_X, TE_DAY_X,
    TE_DATE_SEP_Y, TE_DATE_SEP_X, TE_DATE_SEP_FONT_SIZE, TE_DATE_SEP_COLOR,
    TE_TIME_Y, TE_HOUR_X, TE_MINUTE_X, TE_SECOND_X,
    TE_TIME_SEP_Y, TE_TIME_SEP_X, TE_TIME_SEP_FONT_SIZE, TE_TIME_SEP_COLOR,
    TE_CARET_DATE_Y, TE_CARET_TIME_Y, TE_CARET_FONT_SIZE, TE_CARET_X, TE_CARET_Y,
)
from lib import resources


class JsonRenderer:
    """Renders a JSON screen definition to a tkinter Canvas.

    All visual constants come from _constants.py which is sourced from:
    - Ground truth: actbase.so, widget.so string tables
    - Ground truth: real device screenshots pixel measurements
    """

    def __init__(self, canvas):
        self.canvas = canvas
        self.state = {}
        self._icon_cache = {}

    def set_state(self, state_dict):
        """Update placeholder context for {variable} resolution."""
        self.state.update(state_dict)

    def resolve(self, text):
        """Resolve {variable} placeholders."""
        if not text or not isinstance(text, str) or '{' not in text:
            return text
        try:
            return text.format(**self.state)
        except (KeyError, ValueError, IndexError):
            return text

    # ================================================================
    # Main render entry point
    # ================================================================

    def render(self, screen):
        """Render a complete screen definition.

        Args:
            screen: dict with title, content, buttons, toast, etc.
                    Or a JSON string.
        """
        if isinstance(screen, str):
            screen = json.loads(screen)

        c = self.canvas

        # Content area background
        # Ground truth: real screenshots show white/light content area
        c.create_rectangle(0, CONTENT_Y0, SCREEN_W, BTN_BAR_Y0,
                           fill=BG_COLOR, outline='', tags='_jr_content_bg')

        # Content
        content = screen.get('content', {})
        content_type = content.get('type', 'empty')

        renderers = {
            'list': self._render_list,
            'template': self._render_template,
            'progress': self._render_progress,
            'card_info_with_progress': self._render_card_info_with_progress,
            'text': self._render_text,
            'empty': self._render_empty,
            'time_editor': self._render_time_editor,
        }
        renderer = renderers.get(content_type, self._render_empty)
        renderer(content)

        # Button bar — only if buttons have text
        # Ground truth: main_page_1_3_1.png has no bar, scan_tag_scanning_5.png does
        buttons = screen.get('buttons', {})
        left_btn = buttons.get('left')
        right_btn = buttons.get('right')
        if left_btn or right_btn:
            self._render_buttons(left_btn, right_btn)

    def render_content_only(self, content):
        """Render only the content area (for partial updates)."""
        c = self.canvas
        c.delete('_jr_content')
        content_type = content.get('type', 'empty')
        renderers = {
            'list': self._render_list,
            'template': self._render_template,
            'progress': self._render_progress,
            'card_info_with_progress': self._render_card_info_with_progress,
            'text': self._render_text,
            'empty': self._render_empty,
            'time_editor': self._render_time_editor,
        }
        renderer = renderers.get(content_type, self._render_empty)
        renderer(content)

    # ================================================================
    # Content: template (scan result, read result, etc.)
    # ================================================================

    def _render_template(self, content):
        """Render structured field display.

        Ground truth pixel positions from scan_tag_scanning_5.png:
            y=52: header (bold 20px, black)
            y=86: subheader (bold 13px, dark grey)
            y=110, 132, 155: fields (regular 12px, grey)
            Row fields: two items on same line
        """
        c = self.canvas

        header = self.resolve(content.get('header', ''))
        subheader = self.resolve(content.get('subheader', ''))
        fields = content.get('fields', [])

        # Header — bold, large
        # Ground truth: scan_tag_scanning_5.png y=52
        if header:
            c.create_text(10, 52, text=header, fill='black',
                          font=resources.get_bold_font(20), anchor='nw',
                          tags='_jr_content')

        # Subheader — bold, medium, dark grey
        # Ground truth: scan_tag_scanning_5.png y=86
        if subheader:
            c.create_text(10, 86, text=subheader, fill='#3C3C3C',
                          font=resources.get_bold_font(13), anchor='nw',
                          tags='_jr_content')

        # Fields — regular, grey, starting at y=110 with 22px spacing
        # Ground truth: scan_tag_scanning_5.png y=110, 132, 155
        font_body = resources.get_font(12)
        field_color = '#505050'
        y = 110

        for field in fields:
            if 'row' in field:
                # Multiple items on same row
                row_items = field['row']
                x = 10
                spacing = (SCREEN_W - 20) // max(len(row_items), 1)
                for rf in row_items:
                    label = self.resolve(rf.get('label', ''))
                    value = self.resolve(rf.get('value', ''))
                    text = '%s: %s' % (label, value) if value else label
                    c.create_text(x, y, text=text, fill=field_color,
                                  font=font_body, anchor='nw', tags='_jr_content')
                    x += spacing
                y += 22
            else:
                label = self.resolve(field.get('label', ''))
                value = self.resolve(field.get('value', ''))
                text = '%s: %s' % (label, value) if value else label
                c.create_text(10, y, text=text, fill=field_color,
                              font=font_body, anchor='nw', tags='_jr_content')
                y += 22

    # ================================================================
    # Content: progress
    # ================================================================

    def _render_progress(self, content):
        """Render progress bar.

        Ground truth: scan_tag_scanning_2.png:
            Bar at y=210..229, x=20..220
            "Scanning..." text at y≈208, centered, blue
            No percentage counter (only in Erase flow)
        """
        c = self.canvas
        message = self.resolve(content.get('message', ''))
        value = content.get('value', 0)
        if isinstance(value, str):
            try:
                value = int(self.resolve(value))
            except (ValueError, TypeError):
                value = 0
        max_val = content.get('max', 100)

        # Message text above bar
        if message:
            c.create_text(SCREEN_W // 2, PROGRESS_Y - 2,
                          text=message, fill=PROGRESS_MSG_COLOR,
                          font=resources.get_font(10), anchor='s',
                          tags='_jr_content')

        # Background track
        c.create_rectangle(PROGRESS_X, PROGRESS_Y,
                           PROGRESS_X + PROGRESS_W, PROGRESS_Y + PROGRESS_H,
                           fill=PROGRESS_BG, outline='', tags='_jr_content')

        # Fill
        if max_val > 0 and value > 0:
            fill_w = int(PROGRESS_W * min(value, max_val) / max_val)
            if fill_w > 0:
                c.create_rectangle(PROGRESS_X, PROGRESS_Y,
                                   PROGRESS_X + fill_w, PROGRESS_Y + PROGRESS_H,
                                   fill=PROGRESS_FG, outline='', tags='_jr_content')

    # ================================================================
    # Content: card_info_with_progress
    # ================================================================

    def _render_card_info_with_progress(self, content):
        """Render card info template + progress bar.

        Used by the reading state (read_tag.json).  The card info
        template is rendered by template.draw() in the activity layer;
        this renders the progress portion so the dispatch table is
        complete.
        """
        progress_content = {
            'message': content.get('progress_message', ''),
            'value': content.get('progress_value', 0),
            'max': content.get('progress_max', 100),
        }
        self._render_progress(progress_content)

    # ================================================================
    # Content: list
    # ================================================================

    def _render_list(self, content):
        """Render list content (menu, plain, radio, checklist).

        Ground truth: main_page_1_3_1.png — 5 items, 40px each,
        icons at x≈15, text at x=19 or x=50 (with icon).
        Selection = #EEEEEE highlight, text always black.
        """
        c = self.canvas
        items = content.get('items', [])
        style = content.get('style', 'plain')
        selected = content.get('selected', 0)
        page_size = content.get('page_size', LIST_ITEMS_PER_PAGE)
        scroll_offset = content.get('scroll_offset', 0)

        visible = items[scroll_offset:scroll_offset + page_size]

        for i, item in enumerate(visible):
            y = CONTENT_Y0 + i * LIST_ITEM_H
            abs_idx = scroll_offset + i
            is_sel = (abs_idx == selected)

            # Selection highlight
            if is_sel:
                c.create_rectangle(0, y, SCREEN_W, y + LIST_ITEM_H,
                                   fill=SELECT_BG, outline='',
                                   tags='_jr_content')

            label = self.resolve(item.get('label', ''))
            text_color = NORMAL_TEXT_COLOR  # always black on light bg

            if style == 'menu':
                icon_name = item.get('icon')
                text_x = LIST_TEXT_X_WITH_ICON if icon_name else LIST_TEXT_X_NO_ICON
                if icon_name:
                    self._draw_icon(c, icon_name, 15, y + LIST_ITEM_H // 2, is_sel)
                c.create_text(text_x, y + LIST_ITEM_H // 2, text=label,
                              fill=text_color, font=resources.get_font(13),
                              anchor='w', tags='_jr_content')

            elif style == 'radio':
                c.create_text(LIST_TEXT_X_NO_ICON, y + LIST_ITEM_H // 2,
                              text=label, fill=text_color,
                              font=resources.get_font(13), anchor='w',
                              tags='_jr_content')
                # Checkbox on right
                chk_x = SCREEN_W - CHECK_BOX_MARGIN_RIGHT - CHECK_BOX_SIZE // 2
                chk_y = y + LIST_ITEM_H // 2
                sz = CHECK_BOX_SIZE // 2
                if item.get('checked', False):
                    c.create_rectangle(chk_x - sz, chk_y - sz,
                                       chk_x + sz, chk_y + sz,
                                       fill=CHECK_COLOR_CHECKED_FILL,
                                       outline='white', width=2,
                                       tags='_jr_content')
                else:
                    c.create_rectangle(chk_x - sz, chk_y - sz,
                                       chk_x + sz, chk_y + sz,
                                       fill='', outline=CHECK_COLOR_UNCHECKED_BORDER,
                                       width=1, tags='_jr_content')
            else:
                # plain
                numbered = content.get('numbered', False)
                prefix = '%d. ' % (abs_idx + 1) if numbered else ''
                c.create_text(LIST_TEXT_X_NO_ICON, y + LIST_ITEM_H // 2,
                              text=prefix + label, fill=text_color,
                              font=resources.get_font(13), anchor='w',
                              tags='_jr_content')

        # Page arrows
        if scroll_offset > 0:
            c.create_text(SCREEN_W // 2, CONTENT_Y0 + 2, text='\u25b2',
                          fill=PAGE_INDICATOR_COLOR,
                          font=resources.get_font(8), anchor='n',
                          tags='_jr_content')
        if scroll_offset + page_size < len(items):
            c.create_text(SCREEN_W // 2, CONTENT_Y0 + CONTENT_H - 2,
                          text='\u25bc', fill=PAGE_INDICATOR_COLOR,
                          font=resources.get_font(8), anchor='s',
                          tags='_jr_content')

    def _draw_icon(self, canvas, name, cx, cy, selected=False):
        """Draw a menu icon at center (cx, cy)."""
        variant = 'selected' if selected else 'normal'
        key = (name, variant)
        if key not in self._icon_cache:
            try:
                from lib import images
                rgb = ICON_RECOLOR_SELECTED if selected else ICON_RECOLOR_NORMAL
                img = images.load(name, rgb=rgb)
                if img:
                    self._icon_cache[key] = img
            except Exception:
                return
        img = self._icon_cache.get(key)
        if img:
            canvas.create_image(cx, cy, image=img, anchor='center',
                                tags='_jr_content')

    # ================================================================
    # Content: text
    # ================================================================

    def _render_text(self, content):
        """Render multi-line text content.

        Schema:
            lines[]: list of line definitions
                text: string (supports {variable} resolution)
                size: 'normal' | 'large' (default: normal)
                align: 'left' | 'center' (default: left)
                color: hex color string (default: NORMAL_TEXT_COLOR)
            y: starting Y position (default: CONTENT_Y0 + 10)
            tag: canvas tag for cleanup (default: '_jr_content')
        """
        c = self.canvas
        lines = content.get('lines', [])
        y = content.get('y', CONTENT_Y0 + 10)
        tag = content.get('tag', '_jr_content')

        for line_def in lines:
            if isinstance(line_def, str):
                line_def = {'text': line_def}
            text = self.resolve(line_def.get('text', ''))
            size = line_def.get('size', 'normal')
            align = line_def.get('align', 'left')
            color = line_def.get('color', NORMAL_TEXT_COLOR)
            font_sizes = {'normal': 10, 'large': 13, 'xlarge': 28}
            line_heights = {'normal': 16, 'large': 19, 'xlarge': 34}
            fs = font_sizes.get(size, 10)
            lh = line_heights.get(size, 16)
            font = resources.get_font(fs)
            _gutter = 15
            if align == 'center':
                x, anchor = SCREEN_W // 2, 'n'
                wrap_w = SCREEN_W - _gutter * 2
            else:
                x, anchor = _gutter, 'nw'
                wrap_w = SCREEN_W - _gutter * 2
            # Handle embedded \n — render each sub-line separately
            for sub_line in text.split('\n'):
                if sub_line.strip() or text == '':
                    tid = c.create_text(x, y, text=sub_line, fill=color,
                                        font=font, anchor=anchor,
                                        width=wrap_w, tags=tag)
                    # Advance y by actual rendered height (may wrap)
                    bbox = c.bbox(tid)
                    if bbox:
                        y += bbox[3] - bbox[1]
                    else:
                        y += lh

    # ================================================================
    # Content: empty
    # ================================================================

    def _render_time_editor(self, content):
        """Render time/date editor matching real device screenshots.

        Visual structure (from time_settings_*.png):
          - Page background: BG_COLOR (light off-white)
          - Container boxes: INPUT_FIELD_BG (#E5E5E5) with thin border
          - Input field boxes: INPUT_BG_COLOR (white) inside containers
          - Field text: INPUT_DATA_COLOR (#000000) at TE_FIELD_FONT_SIZE
          - Separators: NORMAL_TEXT_COLOR (black) dashes/colons
          - Caret ^: NORMAL_TEXT_COLOR, between rows
        """
        c = self.canvas
        tag = '_jr_content'
        values = content.get('values', [2026, 1, 1, 0, 0, 0])
        cursor = content.get('cursor', -1)

        # Container background boxes (light grey)
        c.create_rectangle(*TE_DATE_BOX, fill=INPUT_FIELD_BG,
                           outline='#CCCCCC', tags=tag)
        c.create_rectangle(*TE_TIME_BOX, fill=INPUT_FIELD_BG,
                           outline='#CCCCCC', tags=tag)

        # Individual white input field boxes inside containers
        for box in (TE_YEAR_BOX, TE_MONTH_BOX, TE_DAY_BOX,
                    TE_HOUR_BOX, TE_MINUTE_BOX, TE_SECOND_BOX):
            c.create_rectangle(*box, fill=INPUT_BG_COLOR,
                               outline='#CCCCCC', tags=tag)

        field_font = resources.get_font(TE_FIELD_FONT_SIZE)
        sep_font = resources.get_font(TE_DATE_SEP_FONT_SIZE)
        time_sep_font = resources.get_font(TE_TIME_SEP_FONT_SIZE)
        caret_font = resources.get_font(TE_CARET_FONT_SIZE)

        # Draw in order matching original content_text:
        # [0] year, [1] "-", [2] month, [3] "-", [4] day,
        # [5] hour, [6] ":", [7] minute, [8] ":", [9] second, [10] "^"

        # Date row: year - month - day (CENTER-aligned in white boxes)
        c.create_text(TE_YEAR_X, TE_DATE_Y, text='{:04d}'.format(values[0]),
                      fill=INPUT_DATA_COLOR, font=field_font, anchor='center', tags=tag)
        c.create_text(TE_DATE_SEP_X[0], TE_DATE_SEP_Y, text='-',
                      fill=TE_DATE_SEP_COLOR, font=sep_font, anchor='center', tags=tag)
        c.create_text(TE_MONTH_X, TE_DATE_Y, text='{:02d}'.format(values[1]),
                      fill=INPUT_DATA_COLOR, font=field_font, anchor='center', tags=tag)
        c.create_text(TE_DATE_SEP_X[1], TE_DATE_SEP_Y, text='-',
                      fill=TE_DATE_SEP_COLOR, font=sep_font, anchor='center', tags=tag)
        c.create_text(TE_DAY_X, TE_DATE_Y, text='{:02d}'.format(values[2]),
                      fill=INPUT_DATA_COLOR, font=field_font, anchor='center', tags=tag)

        # Time row: hour : minute : second (CENTER-aligned in white boxes)
        c.create_text(TE_HOUR_X, TE_TIME_Y, text='{:02d}'.format(values[3]),
                      fill=INPUT_DATA_COLOR, font=field_font, anchor='center', tags=tag)
        c.create_text(TE_TIME_SEP_X[0], TE_TIME_SEP_Y, text=':',
                      fill=TE_TIME_SEP_COLOR, font=time_sep_font, anchor='center', tags=tag)
        c.create_text(TE_MINUTE_X, TE_TIME_Y, text='{:02d}'.format(values[4]),
                      fill=INPUT_DATA_COLOR, font=field_font, anchor='center', tags=tag)
        c.create_text(TE_TIME_SEP_X[1], TE_TIME_SEP_Y, text=':',
                      fill=TE_TIME_SEP_COLOR, font=time_sep_font, anchor='center', tags=tag)
        c.create_text(TE_SECOND_X, TE_TIME_Y, text='{:02d}'.format(values[5]),
                      fill=INPUT_DATA_COLOR, font=field_font, anchor='center', tags=tag)

        # Caret ^ — always rendered (original .so state dump confirms caret
        # present at (60, 111) fill='black' even in DISPLAY mode).
        # In DISPLAY mode (cursor=-1): defaults to position 0 (year field).
        # In EDIT mode (cursor>=0): positioned under the focused field.
        caret_idx = cursor if cursor >= 0 else 0
        caret_x = TE_CARET_X.get(caret_idx, TE_CARET_X[0])
        caret_y = TE_CARET_Y.get(caret_idx, TE_CARET_DATE_Y)
        c.create_text(caret_x, caret_y, text='^',
                      fill=NORMAL_TEXT_COLOR, font=caret_font,
                      anchor='center', tags=tag)

    def _render_empty(self, content=None):
        pass

    # ================================================================
    # Button bar
    # ================================================================

    @staticmethod
    def _parse_button(btn):
        """Parse a button spec into (text, active).

        Accepts:
            "Back"                          → ("Back", True)
            {"text": "Start", "active": false} → ("Start", False)
        """
        if btn is None:
            return ('', True)
        if isinstance(btn, str):
            return (btn, True)
        return (btn.get('text', ''), btn.get('active', True))

    def _render_buttons(self, left=None, right=None):
        """Render button bar.

        Ground truth: actbase_strings.txt line 1228 (#222222),
        line 1230 (white text). Only drawn when buttons have text.

        Buttons may be strings or objects with text+active.
        Inactive buttons render in BTN_TEXT_COLOR_DISABLED.
        """
        c = self.canvas
        c.create_rectangle(0, BTN_BAR_Y0, SCREEN_W, SCREEN_H,
                           fill=BTN_BAR_BG, outline=BTN_BAR_BG,
                           tags='_jr_buttons')
        font = resources.get_font(16)

        left_text, left_active = self._parse_button(left)
        right_text, right_active = self._parse_button(right)

        if left_text:
            text = self.resolve(left_text)
            color = BTN_TEXT_COLOR if left_active else BTN_TEXT_COLOR_DISABLED
            c.create_text(BTN_LEFT_X, BTN_LEFT_Y, text=text,
                          fill=color, font=font,
                          anchor=BTN_LEFT_ANCHOR, tags='_jr_buttons')
        if right_text:
            text = self.resolve(right_text)
            color = BTN_TEXT_COLOR if right_active else BTN_TEXT_COLOR_DISABLED
            c.create_text(BTN_RIGHT_X, BTN_RIGHT_Y, text=text,
                          fill=color, font=font,
                          anchor=BTN_RIGHT_ANCHOR, tags='_jr_buttons')
