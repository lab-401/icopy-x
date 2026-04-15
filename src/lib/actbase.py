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

"""BaseActivity — Activity with UI rendering capabilities.
Extends Activity (lifecycle management from actstack.py) with:
  - Title bar rendering (setTitle)
  - Button bar rendering (setLeftButton, setRightButton, dismiss, disable)
  - Busy state management (thread-safe)
  - Battery bar integration
  - Lifecycle overrides (onResume/onPause show/hide battery)

Every pixel coordinate, color, font, and canvas tag matches the original
firmware

Import convention: ``from lib.actbase import BaseActivity``
"""

import threading

from lib import actstack
from lib.actstack import Activity
from lib._constants import (
    SCREEN_W,
    TITLE_BAR_Y0,
    TITLE_BAR_Y1,
    TITLE_BAR_BG,
    TITLE_TEXT_X,
    TITLE_TEXT_Y,
    TITLE_TEXT_COLOR,
    TITLE_TEXT_ANCHOR,
    BTN_BAR_Y0,
    BTN_BAR_Y1,
    BTN_BAR_BG,
    BTN_LEFT_X,
    BTN_LEFT_Y,
    BTN_LEFT_ANCHOR,
    BTN_RIGHT_X,
    BTN_RIGHT_Y,
    BTN_RIGHT_ANCHOR,
    BTN_TEXT_COLOR,
    BTN_TEXT_COLOR_DISABLED,
    TAG_TITLE,
    TAG_TITLE_TEXT,
    TAG_BTN_LEFT,
    TAG_BTN_RIGHT,
    TAG_BTN_BG,
    TAG_BTN_ARROWS,
    FONT_TITLE,
    FONT_BUTTON,
    BATTERY_X,
    BATTERY_Y,
    KEY_M1,
    KEY_M2,
)


class BaseActivity(Activity):
    """Activity with UI rendering: title bar, button bar, battery, busy state.

    This is the base class for ALL user-facing activities.
    Extends Activity (lifecycle) with canvas rendering.

    Instance variables:
        _is_busy        — Boolean busy flag (thread-safe via _lock_busy)
        _lock_busy      — threading.Lock for busy state
        _is_title_inited  — True after first setTitle call
        _is_button_inited — True after first button bar bg draw
        _battery_bar    — widget.BatteryBar instance (created lazily)
        event_ret       — Event return value (default False)
        resumed         — Resume state flag (default False)
    """

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self._is_busy = False
        self._lock_busy = threading.Lock()
        self._is_title_inited = False
        self._is_button_inited = False
        self._m1_active = True
        self._m2_active = True
        self._m1_visible = True
        self._m2_visible = True
        self._battery_bar = None
        self.event_ret = False
        self.resumed = False
        # Register with actstack (Matches original implementation.register(self))
        actstack.register(self)

    # ==================================================================
    # TITLE BAR
    # ==================================================================

    def setTitle(self, title, color=None):
        """Render title bar with text and optional page indicator.

        The title and page indicator are rendered as SEPARATE text
        elements. The title is centered in the title bar; the page
        indicator (e.g. "1/3") is rendered to its right in a smaller
        font. Callers may pass "Title N/M" format — the method splits
        on the last space-before-digits pattern to separate them.
        [Source: real device screenshots show page indicator as smaller
        separate text to the right of the title]

        Args:
            title: Title string, optionally with "N/M" suffix.
            color: Optional background color override.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        # Split title from page indicator (e.g. "Main Page 1/3" → "Main Page", "1/3")
        import re
        page_match = re.match(r'^(.+?)\s+(\d+/\d+)$', title)
        if page_match:
            base_title = page_match.group(1)
            page_text = page_match.group(2)
        else:
            base_title = title
            page_text = None

        if not self._is_title_inited:
            self._drawTitleBar(base_title, color, page_text)
            self._is_title_inited = True
        else:
            canvas.itemconfig(TAG_TITLE_TEXT, text=base_title)
            # Update page indicator in-place if it exists, create if not
            page_items = canvas.find_withtag('page_indicator:top')
            if page_text:
                if page_items:
                    canvas.itemconfig(page_items[0], text=page_text)
                else:
                    page_font = _get_page_font()
                    try:
                        title_items = canvas.find_withtag(TAG_TITLE_TEXT)
                        if title_items:
                            canvas.update_idletasks()
                            bbox = canvas.bbox(title_items[0])
                            page_x = bbox[2] + 2 if bbox else 180
                        else:
                            page_x = 180
                    except Exception:
                        page_x = 180
                    canvas.create_text(
                        page_x, TITLE_TEXT_Y - 5,
                        text=page_text, fill='white', anchor='nw',
                        font=page_font, tags=('page_indicator:top',),
                    )
            else:
                if page_items:
                    canvas.delete('page_indicator:top')

    def _drawTitleBar(self, title, color=None, page_text=None):
        """Internal: draw title bar elements on canvas.

        Title and page indicator are separate text elements.
        The page indicator uses a smaller font and lighter color,
        positioned to the right of the title.
        [Source: real device screenshots — page indicator is visually
        distinct from the title text]
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        bg_color = color if color is not None else TITLE_BAR_BG
        font_spec = _get_title_font()

        # Background rectangle
        canvas.create_rectangle(
            0, TITLE_BAR_Y0, SCREEN_W, TITLE_BAR_Y1,
            fill=bg_color, outline=bg_color, tags=TAG_TITLE,
        )
        # Title text
        title_id = canvas.create_text(
            TITLE_TEXT_X, TITLE_TEXT_Y,
            text=title, fill=TITLE_TEXT_COLOR, anchor=TITLE_TEXT_ANCHOR,
            font=font_spec, tags=(TAG_TITLE, TAG_TITLE_TEXT),
        )
        # Page indicator as separate widget to the right of title text
        # immediately right of "Simulation", smaller font, lighter color
        if page_text:
            page_font = _get_page_font()
            # Position page indicator right of title text.
            # FB measurement: "Simulation" at center, "1/4" at ~x=175, y=12
            # Title char width ~10px in mononoki 18. Half-width of title
            # gives offset from center to right edge of text.
            # Position: center + half title width + gap
            # mononoki 18 ~10px/char, title centered at TITLE_TEXT_X
            # Use canvas.update_idletasks() to force bbox computation
            try:
                canvas.update_idletasks()
                bbox = canvas.bbox(title_id)
                page_x = bbox[2] + 2 if bbox else 180
            except Exception:
                page_x = 180
            canvas.create_text(
                page_x, TITLE_TEXT_Y - 5,
                text=page_text, fill='white', anchor='nw',
                font=page_font, tags=('page_indicator:top',),
            )

    # ==================================================================
    # BUTTON BAR
    # ==================================================================

    def setLeftButton(self, text, color=None, active=True):
        """Render M1 (left) button text.

        Real screenshots: button bar is dark (#222222) with white text,
        but ONLY drawn when there is actual button text.

        Args:
            text: Button label. Empty string hides the button.
            color: Explicit color override (bypasses active logic).
            active: If False, renders dimmed (BTN_TEXT_COLOR_DISABLED)
                    and sets _m1_active=False so state dumps report it.
        """
        self._m1_active = active
        self._m1_visible = bool(text)
        if color is None:
            color = BTN_TEXT_COLOR if active else BTN_TEXT_COLOR_DISABLED

        canvas = self.getCanvas()
        if canvas is None:
            return

        canvas.delete(TAG_BTN_LEFT)

        if text:
            self._setupButtonBg()
            font_spec, y = self._getBtnFontAndY()
            canvas.create_text(
                BTN_LEFT_X, y,
                text=text, fill=color, anchor=BTN_LEFT_ANCHOR,
                font=font_spec, tags=TAG_BTN_LEFT,
            )

    def setRightButton(self, text, color=None, active=True):
        """Render M2 (right) button text.


        Args:
            text: Button label. Empty string hides the button.
            color: Explicit color override (bypasses active logic).
            active: If False, renders dimmed (BTN_TEXT_COLOR_DISABLED)
                    and sets _m2_active=False so state dumps report it.
        """
        self._m2_active = active
        self._m2_visible = bool(text)
        if color is None:
            color = BTN_TEXT_COLOR if active else BTN_TEXT_COLOR_DISABLED

        canvas = self.getCanvas()
        if canvas is None:
            return

        canvas.delete(TAG_BTN_RIGHT)

        if text:
            self._setupButtonBg()
            font_spec, y = self._getBtnFontAndY()
            canvas.create_text(
                BTN_RIGHT_X, y,
                text=text, fill=color, anchor=BTN_RIGHT_ANCHOR,
                font=font_spec, tags=TAG_BTN_RIGHT,
            )

    def _setupButtonBg(self):
        """Draw button bar background rect if not already done.

        Creates: (0, 200, 240, 240), fill=#222222, outline=#222222
        Tag: TAG_BTN_BG ('tags_btn_bg')
        """
        if self._is_button_inited:
            return

        canvas = self.getCanvas()
        if canvas is None:
            return

        canvas.create_rectangle(
            0, BTN_BAR_Y0, SCREEN_W, BTN_BAR_Y1,
            fill=BTN_BAR_BG, outline=BTN_BAR_BG, tags=TAG_BTN_BG,
        )
        self._is_button_inited = True

    def dismissButton(self, left=False, right=False, keep_bindings=False):
        """Remove button text(s) from canvas.

        Args:
            left: If True, remove left button text.
            right: If True, remove right button text.
            keep_bindings: If True, buttons are visually hidden but M1/M2
                keys still dispatch (e.g. ConsolePrinterActivity zoom).
                Default False: hidden buttons suppress their keys.

        If neither left nor right is specified, removes both buttons AND
        the background (Matches original implementation.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        if not left and not right:
            # Remove everything (original behavior)
            canvas.delete(TAG_BTN_LEFT)
            canvas.delete(TAG_BTN_RIGHT)
            canvas.delete(TAG_BTN_BG)
            self._is_button_inited = False
            if not keep_bindings:
                self._m1_visible = False
                self._m2_visible = False
                self._m1_active = False
                self._m2_active = False
        else:
            if left:
                canvas.delete(TAG_BTN_LEFT)
                if not keep_bindings:
                    self._m1_visible = False
                    self._m1_active = False
            if right:
                canvas.delete(TAG_BTN_RIGHT)
                if not keep_bindings:
                    self._m2_visible = False
                    self._m2_active = False

    def disableButton(self, left=False, right=False,
                      color=BTN_TEXT_COLOR_DISABLED):
        """Grey out button text(s) via itemconfig and set active flags.

        Does NOT redraw — just changes the fill color of existing text items.

        Args:
            left: If True, disable left button.
            right: If True, disable right button.
            color: Color for disabled state.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        if left:
            self._m1_active = False
            canvas.itemconfig(TAG_BTN_LEFT, fill=color)
        if right:
            self._m2_active = False
            canvas.itemconfig(TAG_BTN_RIGHT, fill=color)

    def setButtonArrows(self, page, total_pages):
        """Show/hide page arrow images centered in the button bar.

        Uses real device image resources from res/img/:
            down.png    — first page (can scroll down)
            up.png      — last page (can scroll up)
            down_up.png — middle page (can scroll both ways)

        on instruction pages 1/4 through 4/4.
        FB state_039 — no arrows on T5577 single page (1/1).

        Position: centered in button bar — x=SCREEN_W//2, y=midpoint of bar.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        canvas.delete(TAG_BTN_ARROWS)

        if total_pages <= 1:
            return

        if page == 0:
            img_name = 'down'
        elif page >= total_pages - 1:
            img_name = 'up'
        else:
            img_name = 'down_up'

        try:
            from lib import images
            img = images.load(img_name)
            if img is not None:
                mid_x = SCREEN_W // 2
                mid_y = (BTN_BAR_Y0 + BTN_BAR_Y1) // 2
                canvas.create_image(
                    mid_x, mid_y,
                    image=img, anchor='center',
                    tags=TAG_BTN_ARROWS,
                )
        except Exception:
            pass

    def clearButtonArrows(self):
        """Remove page arrows from button bar."""
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.delete(TAG_BTN_ARROWS)

    def _getBtnFontAndY(self):
        """Return (font_spec, y_position) for button text.

        Returns:
            tuple: ('mononoki 16', 228)

        The
        metrics.  On the 240px display this resolves to BTN_LEFT_Y (228).
        """
        font_spec = '%s %d' % (FONT_BUTTON[0], FONT_BUTTON[1])
        return (font_spec, BTN_LEFT_Y)

    # ==================================================================
    # BUSY STATE
    # ==================================================================

    def setbusy(self):
        """Set busy state (thread-safe).

        Optionally plays disable sound via audio.playKeyDisable().
        Audio errors are silently caught (module may not be available).
        """
        self._setbusy(True)
        try:
            import audio
            audio.playKeyDisable()
        except Exception:
            pass

    def setidle(self):
        """Clear busy state (thread-safe).

        Optionally plays enable sound via audio.playKeyEnable().
        Audio errors are silently caught (module may not be available).
        """
        self._setbusy(False)
        try:
            import audio
            audio.playKeyEnable()
        except Exception:
            pass

    def isbusy(self):
        """Check busy state.

        Returns:
            bool: True if activity is currently busy.
        """
        return self._is_busy

    def _setbusy(self, state):
        """Internal: set busy flag under lock.

        Uses threading.Lock (not RLock) matching the original implementation.

        Args:
            state: bool — new busy state.
        """
        with self._lock_busy:
            self._is_busy = state

    # ==================================================================
    # BATTERY BAR
    # ==================================================================

    def _initBatteryBar(self):
        """Create BatteryBar instance if canvas available.

        Uses widget.BatteryBar positioned at (BATTERY_X, BATTERY_Y).
        Called lazily on first onResume.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        if self._battery_bar is None:
            from lib.widget import BatteryBar
            self._battery_bar = BatteryBar(canvas, x=BATTERY_X, y=BATTERY_Y)

    def _showBatteryBar(self):
        """Show battery bar and register with batteryui poller (called in onResume).

        Original actbase.so onResume calls:
            1. self._battery_bar.show()
            2. batteryui.register(self._battery_bar)
        This ensures the bar receives periodic updates from hmi_driver.
        """
        self._initBatteryBar()
        if self._battery_bar is not None:
            self._battery_bar.show()
            try:
                from lib import batteryui
                batteryui.register(self._battery_bar)
            except Exception:
                pass

    def _hideBatteryBar(self):
        """Unregister from batteryui poller and hide battery bar (called in onPause).

        Original actbase.so onPause calls:
            1. batteryui.unregister(self._battery_bar)
            2. self._battery_bar.hide()
        """
        if self._battery_bar is not None:
            try:
                from lib import batteryui
                batteryui.unregister(self._battery_bar)
            except Exception:
                pass
            self._battery_bar.hide()

    # ==================================================================
    # LIFECYCLE OVERRIDES
    # ==================================================================

    def onResume(self):
        """Override: show battery bar, set resumed=True.

        Matches original implementation
        _battery_bar.show().
        """
        self.resumed = True
        self._showBatteryBar()

    def onPause(self):
        """Override: hide battery bar, dismiss toast, set resumed=False.

        Matches original implementation
        _battery_bar.hide().  Toast dismissal ensures no stale toasts
        persist when navigating back through the activity stack.
        """
        self.resumed = False
        self._hideBatteryBar()
        for attr in ('_toast', '_write_toast'):
            toast = getattr(self, attr, None)
            if toast is not None:
                try:
                    toast.cancel()
                except Exception:
                    pass

    def onDestroy(self):
        """Override: unregister from actstack.

        Matches original implementation.unregister(self).
        """
        actstack.unregister(self)

    def onActivity(self, bundle):
        """Receives result data from child activity.  Override in subclass."""
        pass

    def onKeyEvent(self, key):
        """Handles key input events.  Override in subclass."""
        pass

    def onData(self, event):
        """Handles data events.  Override in subclass."""
        pass

    def callKeyEvent(self, key):
        """Dispatch key event with button-state guards.

        M1 suppressed when left button is hidden or inactive.
        M2 suppressed when right button is hidden or inactive.
        All other keys (OK, UP, DOWN, PWR) always dispatch.
        """
        if key == KEY_M1 and (not self._m1_visible or not self._m1_active):
            return
        if key == KEY_M2 and (not self._m2_visible or not self._m2_active):
            return
        self.onKeyEvent(key)

    # ==================================================================
    # PWR / BACK HANDLER
    # ==================================================================

    def _handlePWR(self):
        """Standard PWR/Back behavior.  Returns True if handled (caller
        should ``return`` immediately).

        Priority order (matches original firmware actbase.so):
          1. Toast visible  -> dismiss toast, swallow key
          2. Busy state     -> ignore PWR, swallow key
          3. Otherwise      -> return False (caller does its own back nav)
        """
        # 1. Dismiss visible toast first
        for attr in ('_toast', '_write_toast'):
            toast = getattr(self, attr, None)
            if toast is not None:
                try:
                    if toast.isShow():
                        toast.cancel()
                        return True
                except Exception:
                    pass
        # 2. Busy — swallow PWR
        if self._is_busy:
            return True
        return False

    # ==================================================================
    # UTILITY
    # ==================================================================

    def unique_id(self):
        """Return unique ID string for canvas tag prefixing.

        Format: 'ID:{classname}-{id}'
        Matches original implementation.

        Returns:
            str: Unique identifier like 'ID:BaseActivity-140234567890'
        """
        return "ID:{}-{}".format(type(self).__name__, id(self))


# ======================================================================
# Module-level helpers
# ======================================================================

def _get_title_font():
    """Return font spec string for title bar text.

    Tries resources.get_font(18) first (device parity), falls back
    to FONT_TITLE constant tuple formatted as string.

    Returns:
        str: Font specification like 'mononoki 18'
    """
    try:
        from lib import resources
        return resources.get_font(18)
    except Exception:
        return '%s %d' % (FONT_TITLE[0], FONT_TITLE[1])


def _get_page_font():
    """Return font spec for page indicator (smaller than title).

    """
    return 'monospace 11'
