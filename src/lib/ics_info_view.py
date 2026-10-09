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

from lib import resources
from lib._constants import BTN_BAR_Y0, CONSOLE_TEXT_COLOR, CONTENT_Y0
from lib.widget import ConsoleView


class ICSInfoView(ConsoleView):
    FOOTER_CLEARANCE = 8

    def __init__(self, canvas):
        super().__init__(
            canvas,
            y=CONTENT_Y0,
            height=BTN_BAR_Y0 - CONTENT_Y0 - self.FOOTER_CLEARANCE,
        )
        self._clip_rect = (
            self._x,
            self._y,
            self._x + self._width,
            self._y + self._height,
        )
        self._update_metrics()

    def _update_metrics(self):
        try:
            import tkinter.font as tkfont
            font = tkfont.Font(font=resources.get_font(self._font_size))
            measured_height = font.metrics('linespace')
        except Exception:
            measured_height = self._font_size + 2
        self._line_height = max(self._font_size + 4, measured_height + 2)
        self._bottom_padding = self._line_height
        self._content_bottom = self._clip_rect[3] - self._bottom_padding
        self._max_visible = max(
            1,
            (self._content_bottom - self._clip_rect[1]) // self._line_height,
        )
        self._scroll_offset = min(
            self._scroll_offset,
            max(0, len(self._lines) - self._max_visible),
        )

    def _redraw(self):
        self._canvas.delete(self._tag_line)
        self._canvas.delete(self._tag_bg)
        self._canvas.delete(self._tag_scrollbar)
        if not self._showing:
            return

        left, top, right, bottom = self._clip_rect
        self._canvas.create_rectangle(
            left, top, right, bottom,
            fill='#000000', outline='', tags=self._tag_bg,
        )
        end = min(self._scroll_offset + self._max_visible, len(self._lines))
        font_spec = resources.get_font(self._font_size)
        for index, line_index in enumerate(range(self._scroll_offset, end)):
            y_pos = top + index * self._line_height
            if y_pos + self._line_height > self._content_bottom:
                break
            item = self._canvas.create_text(
                left + 4 - self._h_offset, y_pos,
                text=self._lines[line_index],
                fill=CONSOLE_TEXT_COLOR,
                font=font_spec,
                anchor='nw',
                tags=self._tag_line,
            )
            bounds = self._canvas.bbox(item)
            if bounds is not None and (
                bounds[1] < top or bounds[3] > self._content_bottom
            ):
                self._canvas.delete(item)

        total = len(self._lines)
        if total > self._max_visible:
            scrollbar_width = 4
            scrollbar_left = right - scrollbar_width
            scrollbar_height = bottom - top
            self._canvas.create_rectangle(
                scrollbar_left, top, scrollbar_left + scrollbar_width, bottom,
                fill='#444444', outline='', tags=self._tag_scrollbar,
            )
            thumb_height = max(8, int(scrollbar_height * self._max_visible / total))
            thumb_top = top + int(scrollbar_height * self._scroll_offset / total)
            thumb_top = min(thumb_top, bottom - thumb_height)
            self._canvas.create_rectangle(
                scrollbar_left, thumb_top,
                scrollbar_left + scrollbar_width, thumb_top + thumb_height,
                fill='#AAAAAA', outline='', tags=self._tag_scrollbar,
            )
