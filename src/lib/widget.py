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

"""UI widgets — ListView, BigTextListView, Toast, BatteryBar, createTag.

Reconstructed from widget.so (642KB, 9 classes, 148 methods) with
rendering behavior verified via QEMU screenshots of the original v1.0.90
firmware.  Every pixel coordinate, color, and canvas tag matches the
specification in docs/UI_SPEC.md.

This file will eventually contain ALL widget classes; for now it provides
the ListView (most-used widget), BigTextListView, Toast, BatteryBar,
PageIndicator, ConsoleView, InputMethods, and the createTag utility
that all widgets share.
"""

import math
import logging
from typing import List, Optional, Callable

from lib._constants import (
    SCREEN_W,
    SCREEN_H,
    CONTENT_Y0,
    CONTENT_Y1,
    LIST_ITEM_H,
    LIST_ITEMS_PER_PAGE,
    LIST_TEXT_X_NO_ICON,
    LIST_TEXT_X_WITH_ICON,
    LIST_TEXT_ANCHOR,
    SELECT_BG,
    SELECT_OUTLINE,
    SELECT_OUTLINE_WIDTH,
    SELECT_TEXT_COLOR,
    NORMAL_TEXT_COLOR,
    CHECK_COLOR,
    CHECK_BOX_SIZE,
    CHECK_BOX_MARGIN_RIGHT,
    CHECK_COLOR_UNCHECKED_BORDER,
    CHECK_COLOR_CHECKED_BORDER,
    CHECK_COLOR_CHECKED_FILL,
    CHECK_INNER_INSET,
    PROGRESS_X,
    PROGRESS_Y,
    PROGRESS_W,
    PROGRESS_H,
    PROGRESS_BG,
    PROGRESS_FG,
    COLOR_ACCENT,
    PROGRESS_MSG_X,
    PROGRESS_MSG_Y,
    PROGRESS_MSG_ANCHOR,
    PROGRESS_MSG_COLOR,
    # Toast constants
    TOAST_MASK_CENTER,
    TOAST_MASK_FULL,
    TOAST_MASK_TOP_CENTER,
    TOAST_DEFAULT_MODE,
    TOAST_BG,
    TOAST_BORDER,
    TOAST_TEXT_COLOR,
    TOAST_MARGIN,
    TOAST_H,
    TOAST_CENTER_Y,
    FONT_TOAST,
    # Battery constants
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
    BATTERY_PIP_WIDTH,
    BATTERY_FILL_X0,
    BATTERY_FILL_Y0,
    BATTERY_FILL_Y1,
    BATTERY_FILL_MAX_W,
    BATTERY_COLOR_HIGH,
    BATTERY_COLOR_MED,
    BATTERY_COLOR_LOW,
    BATTERY_COLOR_CHARGING,
    BATTERY_THRESHOLD_HIGH,
    BATTERY_THRESHOLD_LOW,
    # PageIndicator constants
    PAGE_INDICATOR_COLOR,
    CONTENT_H,
    # Icon recolor
    ICON_RECOLOR_NORMAL,
    ICON_RECOLOR_SELECTED,
    # ConsoleView constants
    CONSOLE_TEXT_COLOR,
    FONT_CONSOLE,
    # InputMethods constants
    INPUT_BG_COLOR,
    INPUT_DATA_COLOR,
    INPUT_HIGHLIGHT_COLOR,
)
from lib import resources

logger = logging.getLogger(__name__)


# =====================================================================
# Tag utility
# =====================================================================

def createTag(obj, tag):
    """Generate a unique canvas tag string.

    Format: ``'ID:{classname}-{id(obj)}:{tag}'``

    Every widget instance uses this to create per-instance canvas tags so
    that multiple widgets of the same class can coexist without interfering.

    Args:
        obj: The widget instance.
        tag: Suffix string (e.g. ``'bg'``, ``'text'``, ``'icon'``).

    Returns:
        A unique tag string like ``'ID:ListView-140234567890:bg'``.
    """
    return f"ID:{type(obj).__name__}-{id(obj)}:{tag}"


# =====================================================================
# ListView
# =====================================================================

class ListView:
    """Scrollable list of text items with selection highlighting.

    This is the primary navigation widget on the iCopy-X.  Every menu,
    every type list, and every settings screen uses it.

    Rendering contract (must match original firmware pixel-perfect):

    1. ``show()`` or selection change clears previous items via tag.
    2. Visible page = ``selection // items_per_page``.
    3. Each visible item is drawn at ``y = self._y + i * item_height``
       where *i* is the item's index within the current page.
    4. Selected item gets a highlight rectangle
       ``(0, y, 240, y + item_height)`` with ``fill=#EEEEEE``,
       ``outline=black``, ``width=0``.
    5. Page indicators (arrows) are drawn when multiple pages exist.
    """

    def __init__(self, canvas, xy=None, items=None,
                 text_size=13, item_height=LIST_ITEM_H):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            xy: ``(x, y)`` top-left position.  Defaults to ``(0, CONTENT_Y0)``.
            items: Initial item list (optional).
            text_size: Font size for item text (default 13).
            item_height: Height per item in pixels (default 40).
        """
        if xy is None:
            xy = (0, CONTENT_Y0)

        self._canvas = canvas
        self._x = xy[0]
        self._y = xy[1]
        self._width = SCREEN_W
        self._height = 0  # computed from items_per_page * item_height
        self._item_height = item_height
        self._text_size = text_size

        # Item storage
        self._items: List[str] = []

        # Selection / pagination
        self._selection = 0
        self._page = 0
        self._max_display = LIST_ITEMS_PER_PAGE  # default items per page (5)

        # Appearance
        self._select_bg_color = SELECT_BG
        self._title_color = NORMAL_TEXT_COLOR
        self._image_color = None

        # Page mode
        self._page_mode = False

        # Icons: parallel list, None = no icon for that index
        self._icons: List[Optional[str]] = []
        self._icon_images: dict = {}

        # Callbacks
        self._on_page_change: Optional[Callable] = None
        self._on_selection_change: Optional[Callable] = None

        # Visibility
        self._showing = False

        # Canvas tags — unique per instance via createTag
        self._uid = createTag(self, '')
        self._tag_bg = createTag(self, 'bg')
        self._tag_text = createTag(self, 'text')
        self._tag_icon = createTag(self, 'icon')
        self._tag_arrow_up = createTag(self, 'arrow_up')
        self._tag_arrow_down = createTag(self, 'arrow_down')

        # Initialise with provided items
        if items:
            self._items = list(items)

    # -----------------------------------------------------------------
    # Item management
    # -----------------------------------------------------------------

    def setItems(self, items: list):
        """Replace all items.  Resets selection to 0 and redraws."""
        self._items = list(items)
        self._selection = 0
        self._page = 0
        if self._showing:
            self._redraw()

    def addItem(self, item: str):
        """Append a single item."""
        self._items.append(item)
        if self._showing:
            self._redraw()

    def setItemHeight(self, h: int):
        """Set row height in pixels."""
        self._item_height = h

    def setItemWidth(self, w: int):
        """Set item width (full-width highlight rect uses this)."""
        self._width = w

    def setDisplayItemMax(self, n: int):
        """Override the items-per-page count."""
        self._max_display = n

    def setUI(self, x: int, y: int, w: int, h: int):
        """Set position and dimensions."""
        self._x = x
        self._y = y
        self._width = w
        self._height = h
        self._max_display = h // self._item_height if self._item_height else 4

    # -----------------------------------------------------------------
    # Selection
    # -----------------------------------------------------------------

    def next(self):
        """Move selection down.  Wraps to start at end."""
        if not self._items:
            return
        old_sel = self._selection
        old_page = self._page

        if self._selection >= len(self._items) - 1:
            # Wrap to beginning
            self._selection = 0
            self._page = 0
        else:
            self._selection += 1
            self._page = self._selection // self._max_display

        if old_page != self._page and self._on_page_change:
            self._on_page_change(self._page)

        if old_sel != self._selection:
            if self._on_selection_change:
                self._on_selection_change(self._selection)
            if self._showing:
                if old_page == self._page:
                    self._update_highlight(old_sel, self._selection)
                else:
                    self._redraw()

    def prev(self):
        """Move selection up.  Wraps to end at beginning."""
        if not self._items:
            return
        old_sel = self._selection
        old_page = self._page

        if self._selection <= 0:
            # Wrap to end
            self._selection = len(self._items) - 1
            self._page = self._selection // self._max_display
        else:
            self._selection -= 1
            self._page = self._selection // self._max_display

        if old_page != self._page and self._on_page_change:
            self._on_page_change(self._page)

        if old_sel != self._selection:
            if self._on_selection_change:
                self._on_selection_change(self._selection)
            if self._showing:
                if old_page == self._page:
                    self._update_highlight(old_sel, self._selection)
                else:
                    self._redraw()

    def selection(self) -> int:
        """Get current selection index (0-based)."""
        return self._selection

    def getSelection(self) -> Optional[str]:
        """Get selected item text."""
        if 0 <= self._selection < len(self._items):
            return self._items[self._selection]
        return None

    def setSelection(self, idx: int):
        """Set selection to a specific index."""
        if not self._items:
            return
        idx = max(0, min(idx, len(self._items) - 1))
        old_sel = self._selection
        old_page = self._page
        self._selection = idx
        self._page = idx // self._max_display

        if old_page != self._page and self._on_page_change:
            self._on_page_change(self._page)
        if old_sel != self._selection and self._on_selection_change:
            self._on_selection_change(self._selection)
        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Appearance
    # -----------------------------------------------------------------

    def setupSelectBG(self, color: str = SELECT_BG):
        """Set selection highlight color."""
        self._select_bg_color = color

    def setTitleColor(self, color: str):
        """Set text color for all (non-selected) items."""
        self._title_color = color

    def setImageColor(self, color: str):
        """Set icon tint color."""
        self._image_color = color

    # -----------------------------------------------------------------
    # Pagination
    # -----------------------------------------------------------------

    def setPageModeEnable(self, enable: bool):
        """Enable/disable page mode."""
        self._page_mode = enable

    def getPageCount(self) -> int:
        """Get total number of pages."""
        if not self._items or self._max_display <= 0:
            return 0
        return math.ceil(len(self._items) / self._max_display)

    def getPagePosition(self) -> int:
        """Get current page number (0-based)."""
        return self._page

    def getPagePositionFromItem(self, item_idx: int) -> int:
        """Compute which page contains *item_idx*."""
        if self._max_display <= 0:
            return 0
        return item_idx // self._max_display

    def getItemCountOnPage(self, page: int) -> int:
        """Count items on given page."""
        start = page * self._max_display
        end = min(start + self._max_display, len(self._items))
        return max(0, end - start)

    def getItemIndexInPage(self, item_idx: int) -> int:
        """Get position of item within its page (0-based)."""
        return item_idx % self._max_display

    def isItemPositionInPage(self, item_idx: int) -> bool:
        """Check if item is on the currently displayed page."""
        start = self._page * self._max_display
        end = start + self._max_display
        return start <= item_idx < end

    def goto_page(self, page: int):
        """Jump to a specific page."""
        max_page = self.getPageCount() - 1
        if max_page < 0:
            return
        page = max(0, min(page, max_page))
        self._page = page
        self._selection = page * self._max_display
        if self._showing:
            self._redraw()

    def goto_first_page(self):
        """Jump to page 0."""
        self.goto_page(0)

    def goto_last_page(self):
        """Jump to the last page."""
        self.goto_page(self.getPageCount() - 1)

    # -----------------------------------------------------------------
    # Icons
    # -----------------------------------------------------------------

    def setIcons(self, icons: list):
        """Set icon names for items (parallel list).

        Each entry is either an icon name string (e.g. ``'1'``, ``'sleep'``)
        or ``None`` for no icon.  Icons are drawn at x=15 centered in the
        40px left zone; text shifts to x=50 when an icon is present.
        """
        self._icons = list(icons)
        self._icon_images.clear()
        try:
            from lib import images
            for name in self._icons:
                if name is None:
                    continue
                # Normal: dark icons on light bg
                normal_key = (name, 'normal')
                if normal_key not in self._icon_images:
                    img = images.load(name, rgb=ICON_RECOLOR_NORMAL)
                    if img is not None:
                        self._icon_images[normal_key] = img
                # Selected: black icons on highlight bg
                selected_key = (name, 'selected')
                if selected_key not in self._icon_images:
                    img = images.load(name, rgb=ICON_RECOLOR_SELECTED)
                    if img is not None:
                        self._icon_images[selected_key] = img
        except ImportError:
            logger.warning("lib.images not available - icons will not be shown")
        except Exception as e:
            logger.error(f"Error loading icons: {e}")

        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------

    def setOnPageChangeCall(self, callback):
        """Register callback(page_number) for page changes."""
        self._on_page_change = callback

    def setOnSelectionChangeCall(self, callback):
        """Register callback(selection_index) for selection changes."""
        self._on_selection_change = callback

    # -----------------------------------------------------------------
    # Visibility
    # -----------------------------------------------------------------

    def show(self):
        """Render the list to the canvas."""
        self._showing = True
        self._redraw()

    def hide(self):
        """Remove list from canvas."""
        self._showing = False
        self._delete_all()

    def isShowing(self) -> bool:
        """Check if currently displayed."""
        return self._showing

    # -----------------------------------------------------------------
    # Text updates
    # -----------------------------------------------------------------

    def drawStr(self, idx: int, text: str, color: str = None):
        """Update text of a specific item."""
        if 0 <= idx < len(self._items):
            self._items[idx] = text
            if self._showing:
                self._redraw()

    def drawMulti(self, texts: list):
        """Update multiple items at once."""
        self._items = list(texts)
        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Internal rendering
    # -----------------------------------------------------------------

    def _delete_all(self):
        """Delete all canvas items belonging to this ListView."""
        self._canvas.delete(self._tag_bg)
        self._canvas.delete(self._tag_text)
        self._canvas.delete(self._tag_icon)
        self._canvas.delete(self._tag_arrow_up)
        self._canvas.delete(self._tag_arrow_down)

    def _redraw(self):
        """Clear and redraw the entire list view for the current page."""
        if not self._showing:
            return
        self._delete_all()
        self._draw_items()
        self._draw_page_indicators()

    def _update_highlight(self, old_idx, new_idx):
        """Move selection highlight in-place (no delete/recreate).

        Only changes fill colors on the old and new selection rows.
        Much faster than _redraw() — eliminates visible flash.
        """
        page_start = self._page * self._max_display

        # Find all bg rectangles and text items by tag
        bg_items = self._canvas.find_withtag(self._tag_bg)
        text_items = self._canvas.find_withtag(self._tag_text)

        # Delete old highlight rect and recreate for new position
        self._canvas.delete(self._tag_bg)

        # Draw new highlight
        new_rel = new_idx - page_start
        new_y = self._y + (new_rel * self._item_height)
        self._canvas.create_rectangle(
            0, new_y,
            SCREEN_W, new_y + self._item_height,
            fill=self._select_bg_color,
            outline=SELECT_OUTLINE,
            width=SELECT_OUTLINE_WIDTH,
            tags=self._tag_bg,
        )
        # Send highlight behind text/icons
        self._canvas.tag_lower(self._tag_bg)

        # Update text colors
        old_rel = old_idx - page_start
        page_end = min(page_start + self._max_display, len(self._items))

        for text_id in text_items:
            try:
                coords = self._canvas.coords(text_id)
                if not coords:
                    continue
                ty = coords[1]
                # Determine which row this text belongs to
                row = int((ty - self._y) / self._item_height)
                abs_idx = page_start + row
                if abs_idx == new_idx:
                    self._canvas.itemconfig(text_id, fill=SELECT_TEXT_COLOR)
                elif abs_idx == old_idx:
                    self._canvas.itemconfig(text_id, fill=self._title_color)
            except Exception:
                pass

    def _draw_items(self):
        """Draw all visible items for the current page."""
        if not self._items:
            return

        page_start = self._page * self._max_display
        page_end = min(page_start + self._max_display, len(self._items))
        font_spec = resources.get_font(self._text_size)

        for abs_idx in range(page_start, page_end):
            rel_idx = abs_idx - page_start
            y_pos = self._y + (rel_idx * self._item_height)
            is_selected = (abs_idx == self._selection)

            # --- Selection highlight rectangle ---
            if is_selected:
                self._canvas.create_rectangle(
                    0, y_pos,
                    SCREEN_W, y_pos + self._item_height,
                    fill=self._select_bg_color,
                    outline=SELECT_OUTLINE,
                    width=SELECT_OUTLINE_WIDTH,
                    tags=self._tag_bg,
                )
                text_color = SELECT_TEXT_COLOR
            else:
                text_color = self._title_color

            # --- Icon ---
            has_icon = (abs_idx < len(self._icons) and
                        self._icons[abs_idx] is not None)
            icon_drawn = False

            if has_icon:
                icon_name = self._icons[abs_idx]
                color_key = 'selected' if is_selected else 'normal'
                img_key = (icon_name, color_key)
                photo = self._icon_images.get(img_key)
                if photo is not None:
                    icon_cy = y_pos + self._item_height // 2
                    self._canvas.create_image(
                        self._x + LIST_TEXT_X_NO_ICON, icon_cy,
                        image=photo,
                        anchor='center',
                        tags=self._tag_icon,
                    )
                    icon_drawn = True

            # --- Item text ---
            text_x = (LIST_TEXT_X_WITH_ICON if icon_drawn
                      else LIST_TEXT_X_NO_ICON)
            text_y = y_pos + self._item_height // 2

            self._canvas.create_text(
                text_x, text_y,
                text=self._items[abs_idx],
                fill=text_color,
                font=font_spec,
                anchor=LIST_TEXT_ANCHOR,
                tags=self._tag_text,
            )

    def _draw_page_indicators(self):
        """Page indicators — disabled.

        The real device does NOT show up/down arrows in ListViews.
        Pagination is indicated only by the page counter in the title bar
        (e.g. "Main Page 1/3"). Arrows removed to match real device.
        [Source: real device screenshots show no arrows]
        """
        pass


# =====================================================================
# BigTextListView
# =====================================================================

class BigTextListView:
    """ListView variant for displaying large text blocks.

    Simpler than ListView -- no pagination, no multi-item selection.
    Used for warning screens, instruction text, etc.
    """

    def __init__(self, canvas, xy=None, text_size=13):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas).
            xy: ``(x, y)`` top-left position.  Defaults to ``(0, CONTENT_Y0)``.
            text_size: Font size for text.
        """
        if xy is None:
            xy = (0, CONTENT_Y0)
        self._canvas = canvas
        self._x = xy[0]
        self._y = xy[1]
        self._text_size = text_size
        self._text = ''
        self._tag_text = createTag(self, 'text')

    def drawStr(self, text: str):
        """Display a single large text string."""
        self._text = text
        self._canvas.delete(self._tag_text)
        self._canvas.create_text(
            self._x + LIST_TEXT_X_NO_ICON,
            self._y + 10,
            text=text,
            fill=NORMAL_TEXT_COLOR,
            font=resources.get_font(self._text_size),
            anchor='nw',
            width=SCREEN_W - 2 * LIST_TEXT_X_NO_ICON,
            tags=self._tag_text,
        )

    def selection(self) -> int:
        """Always returns 0 (no multi-item selection)."""
        return 0

    def hide(self):
        """Remove text from canvas."""
        self._canvas.delete(self._tag_text)


# =====================================================================
# ProgressBar
# =====================================================================

class ProgressBar:
    """Progress bar at FIXED position (20,100)->(220,120).

    Background ``#eeeeee``, fill ``#1C6AEB``.  Used by Read, Write,
    Update, and AutoCopy activities to show operation progress.

    Rendering contract (matches original firmware pixel-perfect):

    1. Background rect: ``(x, y, x+width, y+height)`` fill ``#eeeeee``
    2. Fill rect: ``(x, y, x+fill_width, y+height)`` fill ``#1C6AEB``
       where ``fill_width = (progress / max) * width``
    3. Message text: ``(x + width//2, y - 2)`` anchor ``'s'``
       fill ``#1C6AEB``
    4. Percentage text: centered on bar, e.g. ``"50%"``
    5. Tags: ``{uid}:bg``, ``{uid}:fill``, ``{uid}:msg``, ``{uid}:pct``
    """

    def __init__(self, canvas, x=PROGRESS_X, y=PROGRESS_Y,
                 width=PROGRESS_W, height=PROGRESS_H, max_v=100):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            x: Left edge of the progress bar (default 20).
            y: Top edge of the progress bar (default 100).
            width: Width in pixels (default 200).
            height: Height in pixels (default 20).
            max_v: Maximum value (default 100).
        """
        self._canvas = canvas
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self._max = max(1, max_v)
        self._progress = 0
        self._message = ''
        self._timer = ''
        self._showing = False

        self._anim_id = 0      # Monotonic counter to cancel stale animations

        # Canvas tags — unique per instance via createTag
        self._tag_bg = createTag(self, 'bg')
        self._tag_fill = createTag(self, 'fill')
        self._tag_msg = createTag(self, 'msg')
        self._tag_timer = createTag(self, 'timer')
        self._tag_pct = createTag(self, 'pct')

    # -----------------------------------------------------------------
    # Value management
    # -----------------------------------------------------------------

    def setMax(self, max_val: int):
        """Set maximum value (clamped to >= 1)."""
        self._max = max(1, max_val)
        if self._progress > self._max:
            self._progress = self._max
        if self._showing:
            self._redraw()

    def getMax(self) -> int:
        """Get maximum value."""
        return self._max

    def setProgress(self, value: int):
        """Set progress with smooth animation (clamped 0-max).

        Animation strategy (keeps max duration <= 300ms):
        - Gap < 10: step by 1 at 15ms intervals (max 135ms)
        - Gap >= 10: step by ceil(gap/10) at 15ms intervals (10 steps = 150ms)
        Uses canvas.after() to avoid blocking the UI thread.
        """
        target = max(0, min(value, self._max))
        if not self._showing or target == self._progress:
            self._progress = target
            return
        self._animate_to(target)

    def _setProgressImmediate(self, value: int):
        """Set progress instantly without animation (for internal use)."""
        self._progress = max(0, min(value, self._max))
        if self._showing:
            self._redraw()

    def _animate_to(self, target):
        """Smoothly step progress from current to target.

        Uses at most 10 animation frames at 15ms each (150ms total).
        canvas.after() schedules steps on the Tk event loop — non-blocking.
        Each call increments _anim_id so stale animations from prior
        setProgress() calls are silently discarded.
        """
        self._anim_id += 1
        my_id = self._anim_id

        gap = abs(target - self._progress)
        if gap == 0:
            return
        step = math.ceil(gap / 10) if gap >= 10 else 1
        direction = 1 if target > self._progress else -1
        step = step * direction

        def _step():
            # Stale animation — a newer setProgress() superseded us
            if my_id != self._anim_id:
                return
            if not self._showing:
                self._progress = target
                return
            remaining = target - self._progress
            if (direction > 0 and remaining > 0) or \
               (direction < 0 and remaining < 0):
                # Don't overshoot
                if abs(remaining) <= abs(step):
                    self._progress = target
                else:
                    self._progress += step
                self._redraw()
                if self._progress != target and self._canvas:
                    self._canvas.after(15, _step)
            else:
                self._progress = target
                self._redraw()
        _step()

    def complete(self, callback=None):
        """Animate to 100% (max) then call optional callback.

        Useful for operations that finish and want a visual completion
        animation before transitioning to the next screen.
        """
        if not self._showing or self._progress == self._max:
            self._progress = self._max
            if self._showing:
                self._redraw()
            if callback:
                callback()
            return
        # Calculate animation time: at most 10 steps * 15ms = 150ms + 50ms buffer
        gap = self._max - self._progress
        steps = min(gap, 10)
        delay = steps * 15 + 50

        self._animate_to(self._max)

        if self._canvas and self._showing and callback:
            self._canvas.after(delay, callback)
        elif callback:
            callback()

    def getProgress(self) -> int:
        """Get current progress."""
        return self._progress

    def increment(self, amount: int = 1):
        """Add to progress (clamped at max)."""
        self.setProgress(self._progress + amount)

    def decrement(self, amount: int = 1):
        """Subtract from progress (clamped at 0)."""
        self.setProgress(self._progress - amount)

    # -----------------------------------------------------------------
    # Message
    # -----------------------------------------------------------------

    def setMessage(self, msg: str):
        """Set action text above bar at (x + width//2, y - 2), anchor='s', color=#1C6AEB."""
        self._message = msg
        if self._showing:
            self._redraw()

    def setTimer(self, timer_text: str):
        """Set timer text above the message line.

        renders above the action line "ChkDIC...0/32keys".
        Position: (x + width//2, y - 18), anchor='s', color=#1C6AEB.
        """
        self._timer = timer_text
        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Visibility
    # -----------------------------------------------------------------

    def show(self):
        """Draw bar + message on canvas."""
        self._showing = True
        self._redraw()

    def hide(self):
        """Remove from canvas."""
        self._showing = False
        self._canvas.delete(self._tag_bg)
        self._canvas.delete(self._tag_fill)
        self._canvas.delete(self._tag_msg)
        self._canvas.delete(self._tag_timer)
        self._canvas.delete(self._tag_pct)

    # -----------------------------------------------------------------
    # Internal rendering
    # -----------------------------------------------------------------

    def _redraw(self):
        """Update the progress bar in-place (no flicker).

        First call creates canvas items; subsequent calls update coords/text
        via itemconfig/coords instead of delete/recreate.
        """
        if not self._showing:
            return

        # --- Background rect (create once) ---
        if not self._canvas.find_withtag(self._tag_bg):
            self._canvas.create_rectangle(
                self._x, self._y,
                self._x + self._width, self._y + self._height,
                fill=PROGRESS_BG,
                outline='',
                tags=self._tag_bg,
            )

        # --- Fill rect ---
        fill_width = int((self._progress / self._max) * self._width)
        fill_items = self._canvas.find_withtag(self._tag_fill)
        if fill_width > 0:
            if fill_items:
                self._canvas.coords(
                    fill_items[0],
                    self._x, self._y,
                    self._x + fill_width, self._y + self._height,
                )
            else:
                self._canvas.create_rectangle(
                    self._x, self._y,
                    self._x + fill_width, self._y + self._height,
                    fill=PROGRESS_FG,
                    outline='',
                    tags=self._tag_fill,
                )
        elif fill_items:
            self._canvas.delete(self._tag_fill)

        # --- Timer text (above message line) ---
        timer_items = self._canvas.find_withtag(self._tag_timer)
        if self._timer:
            if timer_items:
                self._canvas.itemconfig(timer_items[0], text=self._timer)
            else:
                self._canvas.create_text(
                    self._x + self._width // 2,
                    self._y - 18,
                    text=self._timer,
                    fill=PROGRESS_MSG_COLOR,
                    font=resources.get_font(10),
                    anchor=PROGRESS_MSG_ANCHOR,
                    tags=self._tag_timer,
                )
        elif timer_items:
            self._canvas.delete(self._tag_timer)

        # --- Message text (above bar) ---
        msg_items = self._canvas.find_withtag(self._tag_msg)
        if self._message:
            if msg_items:
                self._canvas.itemconfig(msg_items[0], text=self._message)
            else:
                self._canvas.create_text(
                    self._x + self._width // 2,
                    self._y - 2,
                    text=self._message,
                    fill=PROGRESS_MSG_COLOR,
                    font=resources.get_font(10),
                    anchor=PROGRESS_MSG_ANCHOR,
                    tags=self._tag_msg,
                )
        elif msg_items:
            self._canvas.delete(self._tag_msg)


# =====================================================================
# CheckedListView
# =====================================================================

class CheckedListView(ListView):
    """ListView with checkbox squares on the RIGHT side.

    Used for Backlight (radio), Volume (radio), Diagnosis (checklist).
    Unchecked: grey-outlined empty square on right side.
    Checked: blue-outlined square with inner blue-filled square on right side.
    Check state survives page changes.
    """

    def __init__(self, canvas, **kwargs):
        super().__init__(canvas, **kwargs)
        self._checked: set = set()  # Set of checked absolute indices
        self._tag_check = createTag(self, 'check')

    # -----------------------------------------------------------------
    # Check management
    # -----------------------------------------------------------------

    def check(self, idx: int, checked: bool = True):
        """Set check state for item at idx."""
        if checked:
            self._checked.add(idx)
        else:
            self._checked.discard(idx)
        if self._showing:
            self._redraw()

    def auto_show_chk(self):
        """Toggle check on current selection."""
        idx = self._selection
        if idx in self._checked:
            self._checked.discard(idx)
        else:
            self._checked.add(idx)
        if self._showing:
            self._redraw()

    def getCheckPosition(self) -> set:
        """Get set of checked indices."""
        return set(self._checked)

    # -----------------------------------------------------------------
    # Internal rendering (extends ListView)
    # -----------------------------------------------------------------

    def _delete_all(self):
        """Delete all canvas items including check marks."""
        super()._delete_all()
        self._canvas.delete(self._tag_check)

    def _draw_items(self):
        """Draw visible items with checkbox squares on the RIGHT side.

        Unchecked: grey-outlined empty square on right side.
        Checked: blue-outlined square with inner blue-filled square.
        Matches real device screenshots (backlight_1.png, volume_1.png).
        """
        if not self._items:
            return

        page_start = self._page * self._max_display
        page_end = min(page_start + self._max_display, len(self._items))
        font_spec = resources.get_font(self._text_size)

        half_box = CHECK_BOX_SIZE // 2

        for abs_idx in range(page_start, page_end):
            rel_idx = abs_idx - page_start
            y_pos = self._y + (rel_idx * self._item_height)
            is_selected = (abs_idx == self._selection)

            # --- Selection highlight rectangle ---
            if is_selected:
                self._canvas.create_rectangle(
                    0, y_pos,
                    SCREEN_W, y_pos + self._item_height,
                    fill=self._select_bg_color,
                    outline=SELECT_OUTLINE,
                    width=SELECT_OUTLINE_WIDTH,
                    tags=self._tag_bg,
                )
                text_color = SELECT_TEXT_COLOR
            else:
                text_color = self._title_color

            # --- Checkbox on RIGHT side ---
            chk_cx = SCREEN_W - CHECK_BOX_MARGIN_RIGHT - half_box
            chk_cy = y_pos + self._item_height // 2
            box_x0 = chk_cx - half_box
            box_y0 = chk_cy - half_box
            box_x1 = chk_cx + half_box
            box_y1 = chk_cy + half_box

            if abs_idx in self._checked:
                # Checked: outer blue border + inner blue fill
                self._canvas.create_rectangle(
                    box_x0, box_y0, box_x1, box_y1,
                    outline=CHECK_COLOR_CHECKED_BORDER,
                    fill='',
                    tags=self._tag_check,
                )
                self._canvas.create_rectangle(
                    box_x0 + CHECK_INNER_INSET, box_y0 + CHECK_INNER_INSET,
                    box_x1 - CHECK_INNER_INSET, box_y1 - CHECK_INNER_INSET,
                    fill=CHECK_COLOR_CHECKED_FILL,
                    outline='',
                    tags=self._tag_check,
                )
            else:
                # Unchecked: grey border, no fill
                self._canvas.create_rectangle(
                    box_x0, box_y0, box_x1, box_y1,
                    outline=CHECK_COLOR_UNCHECKED_BORDER,
                    fill='',
                    tags=self._tag_check,
                )

            # --- Icon ---
            has_icon = (abs_idx < len(self._icons) and
                        self._icons[abs_idx] is not None)
            icon_drawn = False

            if has_icon:
                icon_name = self._icons[abs_idx]
                color_key = 'selected' if is_selected else 'normal'
                img_key = (icon_name, color_key)
                photo = self._icon_images.get(img_key)
                if photo is not None:
                    icon_cy = y_pos + self._item_height // 2
                    self._canvas.create_image(
                        self._x + LIST_TEXT_X_NO_ICON, icon_cy,
                        image=photo,
                        anchor='center',
                        tags=self._tag_icon,
                    )
                    icon_drawn = True

            # --- Item text ---
            text_x = (LIST_TEXT_X_WITH_ICON if icon_drawn
                      else LIST_TEXT_X_NO_ICON)
            text_y = y_pos + self._item_height // 2

            self._canvas.create_text(
                text_x, text_y,
                text=self._items[abs_idx],
                fill=text_color,
                font=font_spec,
                anchor=LIST_TEXT_ANCHOR,
                tags=self._tag_text,
            )


# =====================================================================
# Toast
# =====================================================================

class Toast:
    """Toast overlay — matches original widget.so _showMask.

    The original uses create_image with an RGBA PhotoImage (tags_mask_layer)
    for the semi-transparent mask, then create_text for the message.
    PIL handles transparency + icon compositing. Tkinter handles text
    rendering with its native mononoki font (which works under QEMU).

    Layout (pixel-verified from pil_renderer._apply_toast):
        - 20% black dim on entire 240x240 screen
        - 205px-wide toast box at 50% black, vertically centered
        - PNG icon (23x23) at left margin inside box
        - White bold text centered in area right of icon
        - Margins: left=10, icon-text gap=5, right=5, top/bottom=10

    Icon mapping:
        'check'   -> res/img/right.png
        'error'   -> res/img/wrong.png
        'warning' -> res/img/wrong.png
        'info'    -> res/img/right.png
    """

    MASK_CENTER = TOAST_MASK_CENTER
    MASK_FULL = TOAST_MASK_FULL
    MASK_TOP_CENTER = TOAST_MASK_TOP_CENTER

    _ICON_FILES = {
        'check': 'right.png', 'error': 'wrong.png',
        'warning': 'wrong.png', 'info': 'right.png',
    }

    # Toast geometry constants (from pil_renderer)
    _TOAST_W = 220
    _ML = 10      # left margin
    _MG = 5       # gap from icon right edge to text
    _MR = 5       # right margin (from text to box right edge)
    _MTB = 10     # top/bottom margin
    _ICON_SZ = 23 # icon width/height

    def __init__(self, canvas, duration_ms=2000):
        self._canvas = canvas
        self._duration_ms = duration_ms
        self._showing = False
        self._timer_id = None
        self._tag_mask = createTag(self, 'mask_layer')
        self._tag_text = createTag(self, 'msg')
        self._tk_mask = None  # prevent GC of PhotoImage

    def show(self, message, duration_ms=None, mode=None, icon=None, wrap='auto'):
        """Show toast overlay.

        Args:
            wrap: 'auto' — strip \\n, natural word-wrap, auto-reduce font >3 lines
                  'no-wrap' — preserve \\n exactly, no word wrapping
                  'no-resize' — natural word-wrap but never reduce font
        """
        self._clear()
        if duration_ms is None:
            duration_ms = self._duration_ms
        self._showing = True

        self._draw(message, icon, wrap=wrap)

        # Re-raise toast elements to top of z-order — ensures toast
        # stays on top even if other widgets were drawn between show() calls
        try:
            self._canvas.tag_raise(self._tag_mask)
            self._canvas.tag_raise(self._tag_text)
        except Exception:
            pass

        if duration_ms and duration_ms > 0:
            self._timer_id = self._canvas.after(duration_ms, self.cancel)

    def _draw(self, message, icon, wrap='auto'):
        """Render mask layer (PIL RGBA) + text (tkinter canvas)."""
        from PIL import Image, ImageTk
        import os

        W, H = SCREEN_W, SCREEN_H
        tw = self._TOAST_W

        # --- Load icon ---
        icon_img = None
        if icon and icon in self._ICON_FILES:
            for d in [os.path.join(os.getcwd(), 'res', 'img'),
                      '/mnt/sdcard/root2/root/home/pi/ipk_app_main/res/img']:
                p = os.path.join(d, self._ICON_FILES[icon])
                if os.path.isfile(p):
                    icon_img = Image.open(p).convert('RGBA')
                    break

        icon_w = icon_img.width if icon_img else 0

        # --- Compute toast text lines ---
        import tkinter.font as tkfont
        font_size = 18
        tk_font = tkfont.Font(family='mononoki', size=font_size, weight='bold')
        lh = tk_font.metrics('linespace')
        ta_x = self._ML + icon_w + self._MG
        ta_w = tw - ta_x - self._MR

        if wrap == 'no-wrap':
            # Preserve \n exactly, no wrapping at all
            lines = [line.strip() for line in message.split('\n')]
        elif wrap == 'no-resize':
            # Natural wrap (strip \n), no font reduction
            clean = ' '.join(message.replace('\n', ' ').split())
            lines = self._wrap(clean, tk_font, ta_w)
        else:
            # 'auto': use \n as preferred break points (preserves semantic
            # phrases like "Wrong type found!"), then wrap any lines that
            # still overflow, then reduce font if >3 lines total.
            lines = []
            for paragraph in message.split('\n'):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                if tk_font.measure(paragraph) <= ta_w:
                    lines.append(paragraph)
                else:
                    lines.extend(self._wrap(paragraph, tk_font, ta_w))
            # Auto-reduce font if more than 3 lines
            while len(lines) > 3 and font_size > 12:
                font_size -= 2
                tk_font = tkfont.Font(family='mononoki', size=font_size, weight='bold')
                lh = tk_font.metrics('linespace')
                lines = []
                for paragraph in message.split('\n'):
                    paragraph = paragraph.strip()
                    if not paragraph:
                        continue
                    if tk_font.measure(paragraph) <= ta_w:
                        lines.append(paragraph)
                    else:
                        lines.extend(self._wrap(paragraph, tk_font, ta_w))
        text_h = len(lines) * lh
        toast_h = max((self._ICON_SZ if icon_img else 20) + self._MTB * 2,
                      text_h + self._MTB * 2)

        # --- Center on screen ---
        tx = (W - tw) // 2
        ty = (H - toast_h) // 2

        # --- Build RGBA mask: dim + toast box + icon ---
        # is visible, the dim overlay does NOT cover the buttons.
        from lib._constants import TAG_BTN_BG, BTN_BAR_Y0
        has_btn_bar = bool(self._canvas.find_withtag(TAG_BTN_BG))
        dim_h = BTN_BAR_Y0 if has_btn_bar else H

        mask = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dim = Image.new('RGBA', (W, dim_h), (0, 0, 0, 51))
        mask.paste(dim, (0, 0))
        # 50% black toast box
        box = Image.new('RGBA', (tw, toast_h), (0, 0, 0, 127))
        region = mask.crop((tx, ty, tx + tw, ty + toast_h))
        mask.paste(Image.alpha_composite(region, box), (tx, ty))
        # Icon
        if icon_img:
            ix = tx + self._ML
            iy = ty + (toast_h - icon_img.height) // 2
            mask.paste(icon_img, (ix, iy), icon_img)

        # --- Place mask on canvas ---
        self._tk_mask = ImageTk.PhotoImage(mask)
        self._canvas.create_image(
            0, 0, image=self._tk_mask, anchor='nw', tags=self._tag_mask)
        # Ensure mask renders above all other widgets (z-order fix)
        self._canvas.tag_raise(self._tag_mask)

        # --- Draw text using tkinter (native mononoki bold) ---
        text_cx = tx + ta_x + ta_w // 2
        text_y = ty + (toast_h - text_h) // 2 + lh // 2
        for line in lines:
            self._canvas.create_text(
                text_cx, text_y,
                text=line, fill='white',
                font=('mononoki', font_size, 'bold'), anchor='center',
                tags=self._tag_text)
            text_y += lh
        # Ensure text renders above the mask layer (z-order fix)
        self._canvas.tag_raise(self._tag_text)

    @staticmethod
    def _wrap(text, font, max_w):
        """Word-wrap text to fit within max_w pixels.

        Respects explicit \\n line breaks first, then wraps long lines.
        """
        result = []
        for paragraph in text.split('\n'):
            words = paragraph.split()
            if not words:
                result.append('')
                continue
            cur = ''
            for word in words:
                test = (cur + ' ' + word).strip()
                if font.measure(test) <= max_w:
                    cur = test
                else:
                    if cur:
                        result.append(cur)
                    cur = word
            if cur:
                result.append(cur)
        return result or [text]

    def cancel(self):
        """Hide toast and cancel auto-dismiss timer."""
        if self._timer_id is not None:
            self._canvas.after_cancel(self._timer_id)
            self._timer_id = None
        self._clear()
        self._showing = False

    def isShow(self):
        return self._showing

    def _clear(self):
        if self._timer_id is not None:
            self._canvas.after_cancel(self._timer_id)
            self._timer_id = None
        self._canvas.delete(self._tag_mask)
        self._canvas.delete(self._tag_text)
        self._tk_mask = None


# =====================================================================
# BatteryBar
# =====================================================================

class BatteryBar:
    """Battery level indicator in title bar.

    Position: (208, 15) -- top-right of title bar.

    Rendering (from ``_constants.py`` / ``UI_SPEC.md``):

    - External rect: ``(BATTERY_X, BATTERY_Y)`` to
      ``(BATTERY_X+BATTERY_W, BATTERY_Y+BATTERY_H)`` = (208,15)->(230,27),
      outline=white, width=2, no fill.
    - Contact pip: small rect at (230, 19.2) to (232.4, 22.8), fill=white.
    - Internal fill: starts at x=210, width proportional to percent.
      Color: green if > 50, yellow if 20-50, red if < 20.
    - Charging indicator: lightning bolt symbol overlaid when charging.

    Tags: ``{uid}:bat_outline``, ``{uid}:bat_pip``,
    ``{uid}:bat_fill``, ``{uid}:bat_charge``
    """

    def __init__(self, canvas, x=BATTERY_X, y=BATTERY_Y):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            x: X coordinate of battery body top-left (default 208).
            y: Y coordinate of battery body top-left (default 15).
        """
        self._canvas = canvas
        self._x = x
        self._y = y
        self._percent = 100
        self._charging = False
        self._showing = False
        self._destroyed = False

        # Canvas tags -- unique per instance
        self._tag_outline = createTag(self, 'bat_outline')
        self._tag_pip = createTag(self, 'bat_pip')
        self._tag_fill = createTag(self, 'bat_fill')
        self._tag_charge = createTag(self, 'bat_charge')

    def setBattery(self, percent):
        """Set battery level 0-100.  Updates fill width and color.

        Args:
            percent: integer 0-100.
        """
        self._percent = max(0, min(100, int(percent)))
        if self._showing:
            self._draw()

    def setCharging(self, charging):
        """Show/hide charging indicator.

        Args:
            charging: bool -- True to show lightning bolt.
        """
        self._charging = bool(charging)
        if self._showing:
            self._draw()

    def show(self):
        """Draw battery bar on canvas."""
        if self._destroyed:
            return
        self._showing = True
        self._draw()

    def hide(self):
        """Remove battery bar from canvas."""
        self._showing = False
        self._delete_all()

    def destroy(self):
        """Mark as destroyed (won't draw)."""
        self._destroyed = True
        self._showing = False
        self._delete_all()

    def isDestroy(self):
        """Check if destroyed.

        Returns:
            bool: True if destroy() has been called.
        """
        return self._destroyed

    def isShowing(self):
        """Check if currently displayed.

        Returns:
            bool: True if battery bar is visible on canvas.
        """
        return self._showing

    def _delete_all(self):
        """Remove all battery canvas items."""
        self._canvas.delete(self._tag_outline)
        self._canvas.delete(self._tag_pip)
        self._canvas.delete(self._tag_fill)
        self._canvas.delete(self._tag_charge)

    def _get_fill_color(self):
        """Return the fill color based on current percent and charging state.

        Returns:
            str: hex color string.
        """
        if self._charging:
            return BATTERY_COLOR_CHARGING
        if self._percent > BATTERY_THRESHOLD_HIGH:
            return BATTERY_COLOR_HIGH
        if self._percent >= BATTERY_THRESHOLD_LOW:
            return BATTERY_COLOR_MED
        return BATTERY_COLOR_LOW

    def _draw(self):
        """Redraw the full battery bar."""
        self._delete_all()
        if not self._showing:
            return

        # --- External body outline ---
        self._canvas.create_rectangle(
            self._x, self._y,
            self._x + BATTERY_W, self._y + BATTERY_H,
            outline=BATTERY_OUTLINE_COLOR,
            width=BATTERY_OUTLINE_WIDTH,
            fill='',
            tags=self._tag_outline,
        )

        # --- Contact pip (positive terminal nub) ---
        self._canvas.create_rectangle(
            BATTERY_PIP_X0, BATTERY_PIP_Y0,
            BATTERY_PIP_X1, BATTERY_PIP_Y1,
            fill=BATTERY_PIP_COLOR,
            outline=BATTERY_PIP_COLOR,
            width=BATTERY_PIP_WIDTH,
            tags=self._tag_pip,
        )

        # --- Internal fill ---
        fill_w = int(BATTERY_FILL_MAX_W * self._percent / 100)
        if fill_w > 0:
            color = self._get_fill_color()
            self._canvas.create_rectangle(
                BATTERY_FILL_X0, BATTERY_FILL_Y0,
                BATTERY_FILL_X0 + fill_w, BATTERY_FILL_Y1,
                fill=color,
                outline='',
                width=0,
                tags=self._tag_fill,
            )

        # --- Charging indicator ---
        if self._charging:
            cx = self._x + BATTERY_W // 2
            cy = self._y + BATTERY_H // 2
            self._canvas.create_text(
                cx, cy,
                text='\u26A1',  # HIGH VOLTAGE SIGN (lightning bolt)
                fill='#FFFFFF',
                font=('mononoki', 7),
                anchor='center',
                tags=self._tag_charge,
            )


# =====================================================================
# PageIndicator
# =====================================================================

class PageIndicator:
    """Scroll arrows showing pagination position.

    Shows a small up-pointing triangle at the top of the content area
    when the current page is not the first page, and a small
    down-pointing triangle at the bottom when it is not the last page.

    Used by ListView internally but also available as a standalone
    widget for custom scrollable views.
    """

    def __init__(self, canvas, x=0, y=CONTENT_Y0, width=SCREEN_W, height=CONTENT_H):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            x: Left edge x-coordinate.
            y: Top edge y-coordinate (default: content area top).
            width: Width of the indicator area.
            height: Height of the indicator area.
        """
        self._canvas = canvas
        self._x = x
        self._y = y
        self._width = width
        self._height = height

        # State
        self._top_enable = False
        self._bottom_enable = False
        self._top_value = 0
        self._top_max = 0
        self._bottom_total = 0
        self._bottom_current = 0
        self._loop = False
        self._showing = False

        # Canvas tags
        self._tag_arrow_up = createTag(self, 'arrow_up')
        self._tag_arrow_down = createTag(self, 'arrow_down')

    # -----------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------

    def setTopIndicatorEnable(self, enable: bool):
        """Show/hide the up arrow."""
        self._top_enable = enable
        if self._showing:
            self.update()

    def setBottomIndicatorEnable(self, enable: bool):
        """Show/hide the down arrow."""
        self._bottom_enable = enable
        if self._showing:
            self.update()

    def setTopIndicatorValue(self, value: int):
        """Set the current position for the top indicator."""
        self._top_value = value
        if self._showing:
            self.update()

    def setTopIndicatorMax(self, max_val: int):
        """Set the maximum position for the top indicator."""
        self._top_max = max_val
        if self._showing:
            self.update()

    def setLoop(self, loop: bool):
        """Enable or disable wrap-around mode."""
        self._loop = loop

    def setupBottomIndicator(self, total: int, current: int):
        """Set total item count and current position for the bottom indicator."""
        self._bottom_total = total
        self._bottom_current = current
        if self._showing:
            self.update()

    # -----------------------------------------------------------------
    # Visibility
    # -----------------------------------------------------------------

    def show(self):
        """Display the indicators on the canvas."""
        self._showing = True
        self.update()

    def hide(self):
        """Remove indicators from canvas."""
        self._showing = False
        self._canvas.delete(self._tag_arrow_up)
        self._canvas.delete(self._tag_arrow_down)

    def showing(self) -> bool:
        """Check if the indicator is currently visible."""
        return self._showing

    # -----------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------

    def update(self):
        """Redraw the indicators based on current state."""
        self._canvas.delete(self._tag_arrow_up)
        self._canvas.delete(self._tag_arrow_down)

        if not self._showing:
            return

        mid_x = self._x + self._width // 2

        # Up arrow at top-center of content area
        if self._top_enable:
            self._canvas.create_text(
                mid_x, self._y + 2,
                text='\u25b2',  # BLACK UP-POINTING TRIANGLE
                fill=PAGE_INDICATOR_COLOR,
                font=resources.get_font(8),
                anchor='n',
                tags=self._tag_arrow_up,
            )

        # Down arrow at bottom-center of content area
        if self._bottom_enable:
            self._canvas.create_text(
                mid_x, self._y + self._height - 2,
                text='\u25bc',  # BLACK DOWN-POINTING TRIANGLE
                fill=PAGE_INDICATOR_COLOR,
                font=resources.get_font(8),
                anchor='s',
                tags=self._tag_arrow_down,
            )


# =====================================================================
# ConsoleView
# =====================================================================

class ConsoleView:
    """Monospace scrolling text display for PM3 output.

    Used by ConsolePrinterActivity for real-time PM3 command output,
    LUA script output, and Read key recovery progress.

    white monospace text, no title/button bar.

    Key handling (from read_console_common.sh lines 27-35):
        UP/M2:    textfontsizeup (zoom in, max 14)
        DOWN/M1:  textfontsizedown (zoom out, min 6)
        RIGHT:    horizontal scroll right
        LEFT:     horizontal scroll left

    Default font size: 14 (max). Range: 6-14.
    """

    _FONT_SIZE_MIN = 6
    _FONT_SIZE_MAX = 14
    _FONT_SIZE_DEFAULT = 14
    _H_SCROLL_STEP = 20  # pixels per horizontal scroll step

    def __init__(self, canvas, x=0, y=0, width=SCREEN_W, height=SCREEN_H):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            x: Left edge x-coordinate.
            y: Top edge y-coordinate (0 for full-screen console).
            width: Width of the console area.
            height: Height of the console area.
        """
        self._canvas = canvas
        self._x = x
        self._y = y
        self._width = width
        self._height = height

        # Text storage
        self._lines = []

        # Font size (zoom level)
        self._font_size = self._FONT_SIZE_DEFAULT
        self._line_height = self._font_size + 2  # approximate

        # Scroll state
        self._scroll_offset = 0  # first visible line index (vertical)
        self._h_offset = 0       # horizontal scroll offset in pixels
        self._max_visible = self._height // self._line_height

        # Visibility
        self._showing = False

        # Canvas tags
        self._tag_line = createTag(self, 'console_line')
        self._tag_bg = createTag(self, 'console_bg')
        self._tag_scrollbar = createTag(self, 'console_scrollbar')

    # -----------------------------------------------------------------
    # Text manipulation
    # -----------------------------------------------------------------

    def addLine(self, text: str):
        """Add a single line of text. Auto-scroll if at bottom."""
        at_bottom = self._is_at_bottom()
        self._lines.append(text)
        if at_bottom:
            self.scrollToBottom()
        if self._showing:
            self._redraw()

    def addText(self, text: str):
        """Add text that may contain newlines. Split into individual lines."""
        parts = text.split('\n')
        at_bottom = self._is_at_bottom()
        self._lines.extend(parts)
        if at_bottom:
            self.scrollToBottom()
        if self._showing:
            self._redraw()

    def clear(self):
        """Remove all stored text and clear the canvas."""
        self._lines.clear()
        self._scroll_offset = 0
        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Scrolling
    # -----------------------------------------------------------------

    def scrollUp(self):
        """Scroll up one line (if possible)."""
        if self._scroll_offset > 0:
            self._scroll_offset -= 1
            if self._showing:
                self._redraw()

    def scrollDown(self):
        """Scroll down one line (if possible)."""
        max_offset = max(0, len(self._lines) - self._max_visible)
        if self._scroll_offset < max_offset:
            self._scroll_offset += 1
            if self._showing:
                self._redraw()

    def scrollToBottom(self):
        """Jump scroll offset to show the last lines."""
        self._scroll_offset = max(0, len(self._lines) - self._max_visible)

    def _is_at_bottom(self):
        """Check if currently scrolled to bottom."""
        max_offset = max(0, len(self._lines) - self._max_visible)
        return self._scroll_offset >= max_offset

    # -----------------------------------------------------------------
    # Zoom (font size control)
    # -----------------------------------------------------------------

    def textfontsizeup(self):
        """Increase font size (zoom in). Max 14.

        """
        if self._font_size < self._FONT_SIZE_MAX:
            self._font_size += 1
            self._update_metrics()
            if self._showing:
                self._redraw()

    def textfontsizedown(self):
        """Decrease font size (zoom out). Min 6.

        """
        if self._font_size > self._FONT_SIZE_MIN:
            self._font_size -= 1
            self._update_metrics()
            if self._showing:
                self._redraw()

    def _update_metrics(self):
        """Recalculate line height and visible lines after font change."""
        self._line_height = self._font_size + 2
        self._max_visible = self._height // self._line_height
        # Clamp scroll offset
        max_offset = max(0, len(self._lines) - self._max_visible)
        if self._scroll_offset > max_offset:
            self._scroll_offset = max_offset

    def autofit_font_size(self):
        """Calculate font size so the longest line fits within screen width.

        Tries font sizes 14 down to 6, picks largest where longest line
        fits within self._width. Uses tkinter font metrics.
        """
        if not self._lines:
            return
        longest = max(self._lines, key=len)
        if not longest:
            return
        try:
            import tkinter.font as tkfont
            for size in range(self._FONT_SIZE_MAX, self._FONT_SIZE_MIN - 1, -1):
                f = tkfont.Font(family='mononoki', size=size)
                if f.measure(longest) <= self._width - 8:  # 4px padding each side
                    self._font_size = size
                    self._update_metrics()
                    return
            # Even min size doesn't fit — use min
            self._font_size = self._FONT_SIZE_MIN
            self._update_metrics()
        except Exception:
            pass  # tkinter.font not available (test env)

    def _get_max_h_offset(self):
        """Max horizontal offset: longest line width minus visible width."""
        if not self._lines:
            return 0
        longest = max(self._lines, key=len)
        # Approximate: char_width ~ font_size * 0.6 for monospace
        char_w = self._font_size * 0.6
        content_w = len(longest) * char_w
        return max(0, int(content_w - self._width + 8))

    # -----------------------------------------------------------------
    # Horizontal scroll
    # -----------------------------------------------------------------

    def scrollRight(self):
        """Scroll right (shift text left to reveal overflow).

        Clamps to content extent — cannot scroll beyond the longest line.
        """
        max_h = self._get_max_h_offset()
        if self._h_offset < max_h:
            self._h_offset = min(self._h_offset + self._H_SCROLL_STEP, max_h)
            if self._showing:
                self._redraw()

    def scrollLeft(self):
        """Scroll left (shift text right, min 0)."""
        if self._h_offset > 0:
            self._h_offset = max(0, self._h_offset - self._H_SCROLL_STEP)
            if self._showing:
                self._redraw()

    # -----------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------

    def getLineCount(self):
        """Return total number of stored lines."""
        return len(self._lines)

    @property
    def font_size(self):
        """Current font size (for testing)."""
        return self._font_size

    # -----------------------------------------------------------------
    # Visibility
    # -----------------------------------------------------------------

    def show(self):
        """Render background + all visible lines to the canvas."""
        self._showing = True
        self._redraw()

    def hide(self):
        """Remove all console items from the canvas."""
        self._showing = False
        self._canvas.delete(self._tag_line)
        self._canvas.delete(self._tag_bg)
        self._canvas.delete(self._tag_scrollbar)

    # -----------------------------------------------------------------
    # Internal rendering
    # -----------------------------------------------------------------

    def _redraw(self):
        """Clear and redraw background + visible lines.

        """
        self._canvas.delete(self._tag_line)
        self._canvas.delete(self._tag_bg)
        if not self._showing:
            return

        # Black background (ground truth: lua_console screenshots — pure black #000000)
        self._canvas.create_rectangle(
            self._x, self._y,
            self._x + self._width, self._y + self._height,
            fill='#000000', outline='',
            tags=self._tag_bg,
        )

        end = min(self._scroll_offset + self._max_visible, len(self._lines))
        font_spec = resources.get_font(self._font_size)

        for i, line_idx in enumerate(range(self._scroll_offset, end)):
            y_pos = self._y + i * self._line_height
            self._canvas.create_text(
                self._x + 4 - self._h_offset, y_pos,
                text=self._lines[line_idx],
                fill=CONSOLE_TEXT_COLOR,
                font=font_spec,
                anchor='nw',
                tags=self._tag_line,
            )

        # Scrollbar (4px wide, right edge)
        self._canvas.delete(self._tag_scrollbar)
        total = len(self._lines)
        if total > self._max_visible:
            sb_w = 4
            sb_x = self._x + self._width - sb_w
            sb_h = self._height
            # Track
            self._canvas.create_rectangle(
                sb_x, self._y, sb_x + sb_w, self._y + sb_h,
                fill='#444444', outline='', tags=self._tag_scrollbar)
            # Thumb
            thumb_h = max(8, int(sb_h * self._max_visible / total))
            thumb_y = self._y + int(sb_h * self._scroll_offset / total)
            self._canvas.create_rectangle(
                sb_x, thumb_y, sb_x + sb_w, thumb_y + thumb_h,
                fill='#AAAAAA', outline='', tags=self._tag_scrollbar)


# =====================================================================
# InputMethods
# =====================================================================

class InputMethods:
    """Hex/text per-character input editor.

    Used for manual MIFARE key entry (KeyEnterM1Activity) and
    Simulation UID entry.  Shows a row of character boxes with one
    focused/highlighted character that can be changed via roll-up/down.

    Parameters from SPEC:
        bakcolor='#ffffff', datacolor='#000000', highlightcolor='#cccccc'
    """

    # Hex character set for roll selection
    _HEX_CHARS = '0123456789ABCDEF'

    def __init__(self, canvas, x=0, y=CONTENT_Y0, h=CONTENT_H,
                 format='hex', length=12, placeholder='FFFFFFFFFFFF'):
        """
        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            x: Left edge x-coordinate.
            y: Top edge y-coordinate.
            h: Height of the input area.
            format: Input format -- ``'hex'`` for hexadecimal characters,
                    ``'text'`` for general text.
            length: Number of characters in the input field.
            placeholder: Default value to display.
        """
        self._canvas = canvas
        self._x = x
        self._y = y
        self._h = h
        self._format = format
        self._length = length

        # Character state
        self._chars = list(
            placeholder[:length].ljust(length, '0' if format == 'hex' else ' ')
        )
        self._focus = 0

        # Appearance
        self._bg_color = INPUT_BG_COLOR
        self._data_color = INPUT_DATA_COLOR
        self._highlight_color = INPUT_HIGHLIGHT_COLOR

        # Box dimensions
        self._box_w = 18 if format == 'hex' else 14
        # Center the row of boxes horizontally
        total_w = self._box_w * self._length
        self._box_x0 = self._x + (SCREEN_W - total_w) // 2
        self._box_y0 = self._y + (self._h - 24) // 2  # center vertically, box h ~24

        # Visibility
        self._showing = False

        # Canvas tags
        self._tag_box = createTag(self, 'input_box')
        self._tag_char = createTag(self, 'input_char')
        self._tag_cursor = createTag(self, 'input_cursor')

    # -----------------------------------------------------------------
    # Value management
    # -----------------------------------------------------------------

    def setValue(self, value: str):
        """Set the current value. Truncates or pads to length."""
        if self._format == 'hex':
            padded = value.upper()[:self._length].ljust(self._length, '0')
        else:
            padded = value[:self._length].ljust(self._length, ' ')
        self._chars = list(padded)
        if self._showing:
            self._redraw()

    def getValue(self) -> str:
        """Get the current value as a string."""
        return ''.join(self._chars)

    # -----------------------------------------------------------------
    # Focus / navigation
    # -----------------------------------------------------------------

    def setFocus(self, idx: int):
        """Set which character index is focused."""
        self._focus = max(0, min(idx, self._length - 1))
        if self._showing:
            self._redraw()

    def getFocus(self) -> int:
        """Get the currently focused character index."""
        return self._focus

    def nextChar(self):
        """Move focus one position to the right (wraps)."""
        self._focus = (self._focus + 1) % self._length
        if self._showing:
            self._redraw()

    def prevChar(self):
        """Move focus one position to the left (wraps)."""
        self._focus = (self._focus - 1) % self._length
        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Character roll
    # -----------------------------------------------------------------

    _DEC_CHARS = '0123456789'

    def rollUp(self):
        """Increment the focused character.

        For hex: 0->1->...->9->A->...->F->0 (wraps).
        For dec: 0->1->...->9->0 (wraps within digits).
        For text: increment ASCII value (wraps within printable range).
        """
        ch = self._chars[self._focus]
        if self._format == 'hex':
            idx = self._HEX_CHARS.find(ch.upper())
            if idx < 0:
                idx = 0
            self._chars[self._focus] = self._HEX_CHARS[(idx + 1) % 16]
        elif self._format == 'dec':
            idx = self._DEC_CHARS.find(ch)
            if idx < 0:
                idx = 0
            self._chars[self._focus] = self._DEC_CHARS[(idx + 1) % 10]
        else:
            # Printable ASCII range 0x20-0x7E
            code = ord(ch)
            code = code + 1 if code < 0x7E else 0x20
            self._chars[self._focus] = chr(code)
        if self._showing:
            self._redraw()

    def rollDown(self):
        """Decrement the focused character.

        For hex: 0->F->E->...->1->0 (wraps).
        For dec: 0->9->8->...->1->0 (wraps within digits).
        For text: decrement ASCII value (wraps within printable range).
        """
        ch = self._chars[self._focus]
        if self._format == 'hex':
            idx = self._HEX_CHARS.find(ch.upper())
            if idx < 0:
                idx = 0
            self._chars[self._focus] = self._HEX_CHARS[(idx - 1) % 16]
        elif self._format == 'dec':
            idx = self._DEC_CHARS.find(ch)
            if idx < 0:
                idx = 0
            self._chars[self._focus] = self._DEC_CHARS[(idx - 1) % 10]
        else:
            code = ord(ch)
            code = code - 1 if code > 0x20 else 0x7E
            self._chars[self._focus] = chr(code)
        if self._showing:
            self._redraw()

    # -----------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------

    def isComplete(self) -> bool:
        """Check if all characters are filled (non-placeholder).

        For hex: all characters must be valid hex digits.
        For text: all characters must be non-space.
        """
        if self._format == 'hex':
            return all(c.upper() in self._HEX_CHARS for c in self._chars)
        return all(c != ' ' for c in self._chars)

    # -----------------------------------------------------------------
    # Visibility
    # -----------------------------------------------------------------

    def show(self):
        """Render input boxes on the canvas."""
        self._showing = True
        self._redraw()

    def hide(self):
        """Remove all input items from canvas."""
        self._showing = False
        self._canvas.delete(self._tag_box)
        self._canvas.delete(self._tag_char)
        self._canvas.delete(self._tag_cursor)

    # -----------------------------------------------------------------
    # Internal rendering
    # -----------------------------------------------------------------

    def _redraw(self):
        """Clear and redraw all input boxes and characters."""
        self._canvas.delete(self._tag_box)
        self._canvas.delete(self._tag_char)
        self._canvas.delete(self._tag_cursor)

        if not self._showing:
            return

        font_spec = resources.get_font(12)

        for i in range(self._length):
            bx = self._box_x0 + i * self._box_w
            by = self._box_y0
            bx2 = bx + self._box_w
            by2 = by + 24

            # Box background -- highlighted if focused
            is_focused = (i == self._focus)
            bg = self._highlight_color if is_focused else self._bg_color

            self._canvas.create_rectangle(
                bx, by, bx2, by2,
                fill=bg,
                outline='#999999',
                width=1,
                tags=self._tag_box,
            )

            # Character text
            cx = bx + self._box_w // 2
            cy = by + 12  # vertical center of 24px box
            self._canvas.create_text(
                cx, cy,
                text=self._chars[i],
                fill=self._data_color,
                font=font_spec,
                anchor='center',
                tags=self._tag_char,
            )


# =====================================================================
# SimFields — Simulation input fields (gray box per field)
# =====================================================================

class SimFields:
    """Simulation input fields matching real device rendering.

      state_075 (AWID): gray boxes with "Format: 40 <", "FC: 2001", "CN: 13371337"
      state_005 (Nedap): "Subtype: 15 <", "Code: 999", "ID: 99999"
      state_050 (FDX-B): "Country: 999 <", "NC: 112233445566"
      state_004 (M1 S50 1k): "UID: 12345678"

    Each field: gray rounded-rect box, label left inside, value right inside.
    Focus arrow "<" on right side of focused field.
    OK enters/exits edit. UP/DOWN change digit. LEFT/RIGHT move cursor.
    """

    # Layout constants from FB pixel measurements (simulation_multi_20260403)
    # Box dimensions vary by content:
    #   AWID 3 fields: x=40-199 (159px), h=29, gap=10
    #   FDX-B 2 fields: x=20-199 (179px), h=29, gap=10
    #   M1 S50 1 field: x=10-229 (219px), h=39
    # Box bg: RGB(216,216,216) = #D8D8D8, NO border
    BOX_RIGHT = 199       # right edge consistent for multi-field
    BOX_H = 26
    BOX_GAP = 10          # user spec: 10px gap between boxes
    BOX_COLOR = '#F8FCF8'  # user spec: editable area bg #f8fcf8
    BOX_EDIT_COLOR = '#F0F4F0'
    LABEL_COLOR = '#000000'
    VALUE_COLOR = '#1C1C28'
    FOCUS_ARROW = '<'
    FONT_LABEL = ('mononoki', 14)       # user spec: same as content font (36% bigger = 14pt)
    FONT_VALUE = ('mononoki', 11, 'bold')  # user spec: 1pt larger than base 10
    FONT_ARROW = ('mononoki', 16)       # user spec: 65% larger (10 * 1.65 ≈ 16)

    _DEC_CHARS = '0123456789'
    _HEX_CHARS = '0123456789ABCDEF'

    def __init__(self, canvas, y_start=65):
        self._canvas = canvas
        self._y_start = y_start
        self._fields = []       # list of (label, chars, fmt, max_val)
        self._focus_idx = 0
        self._editing = False
        self._cursor = 0        # cursor position within value during edit
        self._showing = False
        self._tag = createTag(self, 'simfields')

    def addField(self, label, default, fmt, max_val):
        """Add a field row.

        Args:
            label: Field label (e.g. "UID:", "FC:")
            default: Default value string
            fmt: 'hex' or 'dec' or 'sel'
            max_val: For hex=char count, dec=max int, sel=max int
        """
        if fmt == 'hex':
            length = max_val
            chars = list(default[:length].ljust(length, '0').upper())
        elif fmt == 'dec':
            length = len(default)
            chars = list(default[:length])
        else:  # sel
            chars = list(default[:1])
            length = 1
        self._fields.append({
            'label': label,
            'chars': chars,
            'fmt': fmt,
            'max_val': max_val,
            'length': length,
        })

    def show(self):
        self._showing = True
        self._redraw()

    def hide(self):
        self._showing = False
        self._canvas.delete(self._tag)

    def setFocus(self, idx):
        self._focus_idx = max(0, min(idx, len(self._fields) - 1))
        self._cursor = 0
        if self._showing:
            self._redraw()

    def focusNext(self):
        if self._focus_idx < len(self._fields) - 1:
            self._focus_idx += 1
            self._cursor = 0
            if self._showing:
                self._redraw()

    def focusPrev(self):
        if self._focus_idx > 0:
            self._focus_idx -= 1
            self._cursor = 0
            if self._showing:
                self._redraw()

    def enterEdit(self):
        self._editing = True
        self._cursor = 0
        if self._showing:
            self._redraw()

    def exitEdit(self):
        self._editing = False
        if self._showing:
            self._redraw()

    @property
    def editing(self):
        return self._editing

    def cursorRight(self):
        if not self._editing:
            return
        f = self._fields[self._focus_idx]
        if self._cursor < f['length'] - 1:
            self._cursor += 1
            if self._showing:
                self._redraw()

    def cursorLeft(self):
        if not self._editing:
            return
        if self._cursor > 0:
            self._cursor -= 1
            if self._showing:
                self._redraw()

    def rollUp(self):
        if not self._editing:
            return
        f = self._fields[self._focus_idx]
        ch = f['chars'][self._cursor]
        if f['fmt'] == 'hex':
            idx = self._HEX_CHARS.find(ch.upper())
            if idx < 0:
                idx = 0
            f['chars'][self._cursor] = self._HEX_CHARS[(idx + 1) % 16]
        elif f['fmt'] == 'dec':
            idx = self._DEC_CHARS.find(ch)
            if idx < 0:
                idx = 0
            f['chars'][self._cursor] = self._DEC_CHARS[(idx + 1) % 10]
        if self._showing:
            self._redraw()

    def rollDown(self):
        if not self._editing:
            return
        f = self._fields[self._focus_idx]
        ch = f['chars'][self._cursor]
        if f['fmt'] == 'hex':
            idx = self._HEX_CHARS.find(ch.upper())
            if idx < 0:
                idx = 0
            f['chars'][self._cursor] = self._HEX_CHARS[(idx - 1) % 16]
        elif f['fmt'] == 'dec':
            idx = self._DEC_CHARS.find(ch)
            if idx < 0:
                idx = 0
            f['chars'][self._cursor] = self._DEC_CHARS[(idx - 1) % 10]
        if self._showing:
            self._redraw()

    def getValue(self, idx):
        """Get the current value string for field at index."""
        if idx < 0 or idx >= len(self._fields):
            return ''
        return ''.join(self._fields[idx]['chars']).strip()

    def getAllValues(self):
        """Get all field values as a list of strings."""
        return [self.getValue(i) for i in range(len(self._fields))]

    def fieldCount(self):
        return len(self._fields)

    def _calcBoxWidth(self, f):
        """Calculate box width based on content.

        FB measurements:
          1 field (M1 S50, UL): x=10-229, width=219
          2 fields (FDX-B): x=20-199, width=179
          3 fields (AWID, Nedap): x=40-199, width=159
        Box width shrinks for more fields. Right edge ~199 for multi.
        """
        n = len(self._fields)
        if n <= 1:
            return 219  # single field spans wide
        elif n == 2:
            return 179
        else:
            return 159

    def _calcBoxX(self, box_w):
        """Calculate box left x, centered relative to right edge ~199."""
        if len(self._fields) <= 1:
            return 10   # single field starts left
        return self.BOX_RIGHT - box_w

    # Select Box / Input Field constants
    SELECT_BG = '#D8D8D8'     # outer Select Box background
    SELECT_PAD = 3            # Select Box internal padding/gutter
    INPUT_BG = '#F8FCF8'      # inner Input Field background
    INPUT_PAD_X = 7           # Input Field internal x-padding
    INPUT_PAD_Y = 6           # Input Field internal y-padding

    def _redraw(self):
        self._canvas.delete(self._tag)
        y = self._y_start
        for i, f in enumerate(self._fields):
            is_focused = (i == self._focus_idx)
            is_editing = is_focused and self._editing

            box_w = self._calcBoxWidth(f)
            box_x = self._calcBoxX(box_w)

            # --- Select Box (outer gray container) ---
            self._canvas.create_rectangle(
                box_x, y, box_x + box_w, y + self.BOX_H,
                fill=self.SELECT_BG, outline='',
                tags=self._tag)

            # Label (inside Select Box, left of Input Field)
            self._canvas.create_text(
                box_x + 8, y + self.BOX_H // 2,
                text=f['label'], fill=self.LABEL_COLOR,
                font=self.FONT_LABEL, anchor='w',
                tags=self._tag)

            # --- Input Field (inner white box, sized to content) ---
            # Width grows with value content (real device: dynamic sizing)
            val_str = ''.join(f['chars'])
            char_w = 8  # approx char width at 11pt bold
            val_text_w = len(val_str) * char_w
            input_w = val_text_w + 2 * self.INPUT_PAD_X
            input_h = self.BOX_H - 2 * self.SELECT_PAD
            input_y = y + self.SELECT_PAD
            # Right-align Input Field within Select Box
            input_x = box_x + box_w - self.SELECT_PAD - input_w

            # Input Field background
            self._canvas.create_rectangle(
                input_x, input_y, input_x + input_w, input_y + input_h,
                fill=self.INPUT_BG, outline='',
                tags=self._tag)

            # Edit cursor — bg highlight on active digit BEFORE text
            # has #C4C9C4 background, rest is #F8FCF8
            if is_editing:
                val_left = input_x + self.INPUT_PAD_X
                cx = val_left + self._cursor * char_w
                self._canvas.create_rectangle(
                    cx, input_y + 1, cx + char_w, input_y + input_h - 1,
                    fill='#C4C9C4', outline='',
                    tags=self._tag)

            # Value text (centered in Input Field) — drawn AFTER cursor bg
            self._canvas.create_text(
                input_x + input_w // 2,
                input_y + input_h // 2,
                text=val_str, fill=self.VALUE_COLOR,
                font=self.FONT_VALUE, anchor='center',
                tags=self._tag)

            # Focus arrow "<" right of Select Box — multi-field only
            if is_focused and len(self._fields) > 1:
                self._canvas.create_text(
                    box_x + box_w + 4, y + self.BOX_H // 2,
                    text=self.FOCUS_ARROW, fill='#404050',
                    font=self.FONT_ARROW, anchor='w',
                    tags=self._tag)

            y += self.BOX_H + self.BOX_GAP


# =====================================================================
# SlidingToggle
# =====================================================================

class SlidingToggle:
    """Sliding toggle switch widget — canvas-based ON/OFF control.

    Renders a track (rounded rectangle via overlapping shapes) with a
    circular thumb that slides between left (OFF) and right (ON) positions.

    Dimensions:
        Track: 46px wide, 22px tall, with rounded ends
        Thumb: 18px diameter white circle

    Colors:
        OFF: Track fill #666666 (grey), thumb on LEFT
        ON:  Track fill COLOR_ACCENT (#1C6AEB blue), thumb on RIGHT
    """

    TRACK_W = 46
    TRACK_H = 22
    THUMB_D = 18
    TRACK_RADIUS = TRACK_H // 2  # 11px — fully rounded ends
    THUMB_MARGIN = (TRACK_H - THUMB_D) // 2  # 2px inset

    COLOR_OFF = '#666666'
    COLOR_ON = COLOR_ACCENT  # #1C6AEB from _constants.py

    def __init__(self, canvas, x, y, initial_state=False, on_change=None):
        """Create a sliding toggle at position (x, y).

        Args:
            canvas: tkinter Canvas (or MockCanvas for tests).
            x: Left edge of the toggle track.
            y: Top edge of the toggle track.
            initial_state: True for ON, False for OFF.
            on_change: Optional callback(new_state: bool) called after toggle.
        """
        self._canvas = canvas
        self._x = x
        self._y = y
        self._state = bool(initial_state)
        self._on_change = on_change

        # Canvas tags for cleanup
        self._tag_track = createTag(self, 'toggle_track')
        self._tag_thumb = createTag(self, 'toggle_thumb')

        self._draw()

    def _draw(self):
        """Render the toggle in its current state."""
        canvas = self._canvas
        x, y = self._x, self._y
        r = self.TRACK_RADIUS
        w = self.TRACK_W
        h = self.TRACK_H

        # Clear previous items
        canvas.delete(self._tag_track)
        canvas.delete(self._tag_thumb)

        track_color = self.COLOR_ON if self._state else self.COLOR_OFF

        # --- Track: rounded rectangle via left circle + center rect + right circle ---
        # Left rounded end
        canvas.create_oval(
            x, y, x + h, y + h,
            fill=track_color, outline='',
            tags=self._tag_track,
        )
        # Right rounded end
        canvas.create_oval(
            x + w - h, y, x + w, y + h,
            fill=track_color, outline='',
            tags=self._tag_track,
        )
        # Center rectangle (connects the two circles)
        canvas.create_rectangle(
            x + r, y, x + w - r, y + h,
            fill=track_color, outline='',
            tags=self._tag_track,
        )

        # --- Thumb: white circle ---
        m = self.THUMB_MARGIN
        d = self.THUMB_D
        if self._state:
            # ON: thumb on right side
            tx = x + w - m - d
        else:
            # OFF: thumb on left side
            tx = x + m
        ty = y + m

        canvas.create_oval(
            tx, ty, tx + d, ty + d,
            fill='white', outline='',
            tags=self._tag_thumb,
        )

    def toggle(self):
        """Switch state and redraw. Calls on_change callback."""
        self._state = not self._state
        self._draw()
        if self._on_change is not None:
            self._on_change(self._state)

    def set_state(self, state):
        """Set state without triggering callback.

        Args:
            state: bool — True for ON, False for OFF.
        """
        new_state = bool(state)
        if new_state != self._state:
            self._state = new_state
            self._draw()

    def get_state(self):
        """Return current state.

        Returns:
            bool: True if ON, False if OFF.
        """
        return self._state

    def destroy(self):
        """Remove all canvas items."""
        self._canvas.delete(self._tag_track)
        self._canvas.delete(self._tag_thumb)
