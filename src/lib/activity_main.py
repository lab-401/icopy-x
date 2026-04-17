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

"""Main application activities — replaces activity_main.so.

Contains BacklightActivity, VolumeActivity, SleepModeActivity,
AboutActivity, WarningDiskFullActivity, ConsolePrinterActivity,
TimeSyncActivity, PCModeActivity, LUAScriptCMDActivity,
ScanActivity, ReadListActivity, WipeTagActivity, SniffActivity,
WriteActivity, WarningWriteActivity, WarningM1Activity, AutoCopyActivity,
SimulationActivity, SimulationTraceActivity, CardWalletActivity,
KeyEnterM1Activity, UpdateActivity, OTAActivity, and hidden activities
(SniffForMfReadActivity, SniffForT5XReadActivity, SniffForSpecificTag,
IClassSEActivity, WearableDeviceActivity, ReadFromHistoryActivity,
AutoExceptCatchActivity, SnakeGameActivity, WarningT5XActivity,
WarningT5X4X05KeyEnterActivity).

Replaces relevant classes from actmain.so (252KB, 129 functions)
and activity_main.so.  Each class matches the original behavior
documented in the UI mapping docs.

Import convention: ``from lib.activity_main import BacklightActivity`` etc.
"""

import logging
import os
import shutil

from lib.actbase import BaseActivity

logger = logging.getLogger(__name__)
from lib.activity_read import ConsoleMixin
from lib.widget import CheckedListView, ProgressBar, Toast, SlidingToggle, createTag
from lib import actstack, resources
from lib._constants import (
    SCREEN_W,
    SCREEN_H,
    CONTENT_Y0,
    CONTENT_H,
    LIST_ITEM_H,
    NORMAL_TEXT_COLOR,
    COLOR_ACCENT,
    COLOR_BLACK,
    KEY_UP,
    KEY_DOWN,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_OK,
    KEY_M1,
    KEY_M2,
    KEY_PWR,
)


# =====================================================================
# Simulatable tag type IDs — derived from SIM_MAP (audit finding 3)
# =====================================================================
# Built dynamically from SIM_MAP type IDs rather than hardcoding.
# SIM_MAP is the ground truth (from activity_main.so simulate_map).
# Deferred initialization: set after SIM_MAP is defined (line ~4670).
_SIMULATE_TYPES = frozenset()


# =====================================================================
# Config access helpers
# =====================================================================

def _get_config_value(key, default=1):
    """Read an integer from config.so / settings.so.

    Falls back gracefully when running under test or QEMU without
    the real config.so / settings.so modules.

    Args:
        key: config key name (e.g. 'backlight', 'volume').
        default: fallback value if key not found or module unavailable.

    Returns:
        int: the stored config value, or *default*.
    """
    try:
        import settings
        if key == 'backlight':
            return settings.getBacklight()
        elif key == 'volume':
            return settings.getVolume()
    except Exception:
        pass
    try:
        import config
        val = config.getValue(key)
        return int(val)
    except Exception:
        pass
    return default


def _set_config_value(key, value):
    """Write an integer to config.so / settings.so.

    Args:
        key: config key name.
        value: integer value to persist.
    """
    try:
        import settings
        if key == 'backlight':
            settings.setBacklight(value)
            return
        elif key == 'volume':
            settings.setVolume(value)
            return
    except Exception:
        pass
    try:
        import config
        config.setKeyValue(key, value)
    except Exception:
        pass


# =====================================================================
# BacklightActivity
# =====================================================================

class BacklightActivity(BaseActivity):
    """Backlight level setting: Low / Middle / High.

    Uses CheckedListView with radio-style selection.
    3 levels, NO "Off" option.

    Binary source: activity_main.so BacklightActivity
    Verified: QEMU screenshots, real device traces (20260330)
    Spec: docs/UI_Mapping/08_backlight/README.md

    Key behavior (from binary):
        UP/DOWN: scroll through levels in CheckedListView + instant
                 preview via hmi_driver.setbaklight() (on_selection_change)
        M2/OK:   save selected level (settings + hmi_driver), stay on screen
        PWR:     recovery_backlight() restores original hw, then finish()
        M1:      no action (empty label)

    Screen layout:
        Title: "Backlight" (#7C829A bar)
        Content: CheckedListView with 3 items at y=40
        M1: "" (empty), M2: "" (empty)
    """

    ACT_NAME = 'backlight'

    # Level labels from resources.so: blline1, blline2, blline3
    _KEYS = ('blline1', 'blline2', 'blline3')
    _CONFIG_KEY = 'backlight'
    _DEFAULT_LEVEL = 2  # High -- factory default

    def onCreate(self, bundle):
        """Set up title, buttons, radio list with current setting.

        Flow (from binary onCreate):
            1. settings.getBacklight() -> current level (int)
            2. items = [blline1, blline2, blline3] from resources.so
            3. Create CheckedListView with items
            4. Set check mark on item[current_level]
            5. Store original_level for recovery
        """
        # Resolve item labels from resources
        self._item_labels = list(resources.get_str(list(self._KEYS)))

        # Read current level
        self._original_level = _get_config_value(
            self._CONFIG_KEY, self._DEFAULT_LEVEL
        )
        # Clamp to valid range
        if not (0 <= self._original_level < len(self._item_labels)):
            self._original_level = self._DEFAULT_LEVEL

        # Title and buttons (from binary: M1="" empty, M2="OK")
        self.setTitle(resources.get_str('backlight'))
        self.setLeftButton('')
        self.setRightButton('')  # was OK, fixed per HANDOVER.md

        # Create CheckedListView
        canvas = self.getCanvas()
        if canvas is None:
            return

        self._listview = CheckedListView(canvas)
        self._listview.setItems(self._item_labels)
        self._listview.setSelection(self._original_level)
        self._listview.check(self._original_level)
        # Wire instant preview: brightness changes on each UP/DOWN
        # Ground truth: UI_Mapping/10_backlight/README.md line 82-83
        self._listview.setOnSelectionChangeCall(self._on_preview)
        self._listview.show()

        # Toast for visual feedback (updateBacklight lambda in binary)
        self._toast = Toast(canvas)

    def _on_preview(self, new_idx):
        """Instant backlight preview on selection change (UP/DOWN).

        Ground truth (trace_original_backlight_volume_20260410.txt):
        Original firmware calls settings.setBacklight(level) on EVERY
        UP/DOWN navigation. settings.setBacklight() both persists to
        conf.ini AND applies the hardware change via hmi_driver.
        """
        try:
            import settings
            settings.setBacklight(new_idx)
        except Exception:
            pass

    def onKeyEvent(self, key):
        """Handle UP/DOWN (scroll + preview), M2/OK (save), PWR (cancel).

        From binary onKeyEvent:
            UP:   CheckedListView.scrollUp()  (prev) + instant preview
            DOWN: CheckedListView.scrollDown() (next) + instant preview
            M2:   save selected level -> updateBacklight()
            OK:   same as M2
            PWR:  recovery_backlight() -> finish()
        """
        if key == KEY_UP:
            if hasattr(self, '_listview'):
                self._listview.prev()
        elif key == KEY_DOWN:
            if hasattr(self, '_listview'):
                self._listview.next()
        elif key in (KEY_M2, KEY_OK):
            self._save()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._cancel()

    def _save(self):
        """Save selected level via settings.setBacklight(level).

        Ground truth (trace_original_backlight_volume_20260410.txt):
            SETTINGS.setBacklight((1,))  — UI level only (0/1/2)
        settings.setBacklight() handles BOTH config persist AND
        hardware application via hmi_driver internally.
        Does NOT finish -- stays on screen.
        """
        if not hasattr(self, '_listview'):
            return

        selected = self._listview.selection()

        # Update check mark (radio style: uncheck old, check new)
        self._listview.check(self._original_level, False)
        self._listview.check(selected)

        # Persist + apply hardware (settings.so handles both)
        _set_config_value(self._CONFIG_KEY, selected)

        # Update original_level so future PWR cancels use the new value
        self._original_level = selected

    def _cancel(self):
        """Revert to original hardware level, finish.

        Ground truth (trace_original_backlight_volume_20260410.txt):
            On PWR, original calls settings.getBacklight() then finish.
            The recovery sends the original UI level (0/1/2) back to
            settings.setBacklight() to revert hardware.
        """
        try:
            import settings
            settings.setBacklight(self._original_level)
        except Exception:
            pass
        self.finish()


# =====================================================================
# VolumeActivity
# =====================================================================

class VolumeActivity(BaseActivity):
    """Volume level setting: Off / Low / Middle / High.

    Uses CheckedListView with radio-style selection.
    4 levels, includes "Off" option.

    Binary source: activity_main.so VolumeActivity
    Verified: QEMU screenshots, real device Session 1 trace
    Spec: docs/UI_Mapping/10_volume/README.md

    Key behavior (from binary):
        UP/DOWN: scroll through levels in CheckedListView + instant
                 audio preview via audio.setVolume() + playVolumeExam()
        M2/OK:   saveSetting() -- persist + audio preview, stay on screen
        PWR:     finish() -- exit WITHOUT reverting (unlike Backlight)
        M1:      no action (empty label)

    Screen layout:
        Title: "Volume" (#7C829A bar)
        Content: CheckedListView with 4 items at y=40
        M1: "" (empty), M2: "" (empty)
    """

    ACT_NAME = 'volume'

    _KEYS = ('valueline1', 'valueline2', 'valueline3', 'valueline4')
    _CONFIG_KEY = 'volume'
    _DEFAULT_LEVEL = 2  # Middle -- reasonable default

    def onCreate(self, bundle):
        """Set up title, buttons, radio list with current setting.

        Flow (from binary onCreate):
            1. settings.getVolume() -> current level (int)
            2. items = [valueline1..4] from resources.so
            3. Create CheckedListView with items
            4. Set check mark on item[current_level]
        """
        self._item_labels = list(resources.get_str(list(self._KEYS)))

        self._original_level = _get_config_value(
            self._CONFIG_KEY, self._DEFAULT_LEVEL
        )
        if not (0 <= self._original_level < len(self._item_labels)):
            self._original_level = self._DEFAULT_LEVEL

        # Title and buttons (from binary: M1="" empty, M2="OK")
        self.setTitle(resources.get_str('volume'))
        self.setLeftButton('')
        self.setRightButton('')  # was OK, fixed per HANDOVER.md

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._listview = CheckedListView(canvas)
        self._listview.setItems(self._item_labels)
        self._listview.setSelection(self._original_level)
        self._listview.check(self._original_level)
        # Wire instant audio preview: volume changes on each UP/DOWN
        # Ground truth: volume_common.sh line 11, UI_Mapping/11_volume/README.md
        self._listview.setOnSelectionChangeCall(self._on_preview)
        self._listview.show()

        self._toast = Toast(canvas)

    def _on_preview(self, new_idx):
        """Instant volume preview on selection change (UP/DOWN).

        Ground truth (trace_original_backlight_volume_20260410.txt):
        On each UP/DOWN, original calls audio.playVolumeExam(alsa_value)
        with the ALSA percentage (0/20/50/100). The actual setVolume +
        settings persist happen on OK, not on navigation.
        """
        try:
            import audio
            import settings
            alsa_val = settings.fromLevelGetVolume(new_idx)
            audio.playVolumeExam(alsa_val)
        except Exception:
            pass

    def onKeyEvent(self, key):
        """Handle UP/DOWN (scroll + preview), M2/OK (save), PWR (exit).

        From binary onKeyEvent:
            UP:   CheckedListView.scrollUp()  (prev) + instant preview
            DOWN: CheckedListView.scrollDown() (next) + instant preview
            M2:   saveSetting()
            OK:   same as M2
            PWR:  finish() -- NO recovery
        """
        if key == KEY_UP:
            if hasattr(self, '_listview'):
                self._listview.prev()
        elif key == KEY_DOWN:
            if hasattr(self, '_listview'):
                self._listview.next()
        elif key in (KEY_M2, KEY_OK):
            self._save()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._cancel()

    def _save(self):
        """Save selected volume level + play preview.

        From binary saveSetting():
            1. Get selected level from CheckedListView
            2. settings.setVolume(level)
            3. audio.setVolume(level)
            4. audio.playVolumeExam()
            5. If level==0: audio.setKeyAudioEnable(false)
               Else: audio.setKeyAudioEnable(true)
            6. Update check mark
        Does NOT finish -- stays on screen.
        """
        if not hasattr(self, '_listview'):
            return

        selected = self._listview.selection()

        # Update check mark (radio style)
        self._listview.check(self._original_level, False)
        self._listview.check(selected)

        # Persist + apply (matches original trace: setVolume then setVolume then playVolumeExam)
        try:
            import settings
            import audio
            alsa_val = settings.fromLevelGetVolume(selected)
            settings.setVolume(selected)
            audio.setVolume(alsa_val)
            audio.playVolumeExam(alsa_val)
            if selected == 0:
                audio.setKeyAudioEnable(False)
            else:
                audio.setKeyAudioEnable(True)
        except Exception:
            pass

        self._original_level = selected

    def _cancel(self):
        """Exit without reverting.

        From binary: PWR -> finish() with NO recovery.
        Unlike BacklightActivity, volume is NOT restored on cancel.
        """
        self.finish()


# ═══════════════════════════════════════════════════════════════════════
# SettingsMenuActivity
# ═══════════════════════════════════════════════════════════════════════

class SettingsMenuActivity(BaseActivity):
    """Settings menu with image-based toggle items.

    Currently contains: Mirror Screen? toggle.
    Layout: label text on the left, enabled/disabled icon on the right.
    OK key toggles the current item. PWR exits.
    Uses res/img/enabled.png and res/img/disabled.png for toggle state.
    """

    ACT_NAME = 'settings_menu'

    _IMG_PATHS = [
        'res/img',
        '/mnt/sdcard/root2/root/home/pi/ipk_app_main/res/img',
    ]

    def __init__(self, bundle=None):
        self._mirror_state = False
        self._tk_img = None  # prevent GC of PhotoImage
        super().__init__(bundle)

    def _load_toggle_image(self, enabled):
        """Load the toggle icon as a PhotoImage."""
        import os
        fname = 'enabled.png' if enabled else 'disabled.png'
        for d in self._IMG_PATHS:
            p = os.path.join(d, fname)
            if os.path.isfile(p):
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(p).convert('RGBA')
                    return ImageTk.PhotoImage(img)
                except Exception:
                    pass
        return None

    def onCreate(self, bundle=None):
        self.setTitle(resources.get_str('settings'))
        self.setLeftButton('')
        self.setRightButton('')

        canvas = self.getCanvas()
        if canvas is None:
            return

        # Load current state
        try:
            import settings as _settings
            self._mirror_state = bool(_settings.getScreenMirror())
        except Exception:
            self._mirror_state = False

        # Draw label — left-aligned, first item row
        item_y = CONTENT_Y0 + LIST_ITEM_H // 2
        canvas.create_text(
            15, item_y,
            text=resources.get_str('screen_mirroring'),
            fill=NORMAL_TEXT_COLOR,
            font=resources.get_font(14),
            anchor='w',
            tags='settings_label',
        )

        # Draw toggle image on right side
        self._draw_toggle()

    def _draw_toggle(self):
        """Draw the toggle icon based on current state."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete('settings_toggle')
        self._tk_img = self._load_toggle_image(self._mirror_state)
        if self._tk_img is not None:
            toggle_x = SCREEN_W - 15
            toggle_y = CONTENT_Y0 + LIST_ITEM_H // 2
            canvas.create_image(
                toggle_x, toggle_y,
                image=self._tk_img,
                anchor='e',
                tags='settings_toggle',
            )

    def onKeyEvent(self, key):
        if key == KEY_OK:
            self._mirror_state = not self._mirror_state
            try:
                import settings as _settings
                _settings.setScreenMirror(1 if self._mirror_state else 0)
            except Exception:
                pass
            self._draw_toggle()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()


# ═══════════════════════════════════════════════════════════════════════
# SleepModeActivity
# ═══════════════════════════════════════════════════════════════════════

class SleepModeActivity(BaseActivity):
    """Sleep mode -- dims screen, any key wakes.

    From actmain.so SleepModeActivity:
    - onCreate: sets backlight to 0, fills screen black, no title/buttons
    - onKeyEvent: any key restores backlight and finishes
    - onDestroy: restores previous backlight level

    The original uses hmi_driver.setbaklight(0) to dim and restores
    the saved level on wake.
    """

    ACT_NAME = 'sleep'

    def __init__(self, bundle=None):
        self._prev_backlight = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Dim backlight and paint screen black.

        No title bar, no button bar -- pure black screen.
        Saves current backlight level for restoration on wake.
        """
        # Save current backlight level from config/settings
        self._prev_backlight = self._read_backlight_level()

        # Dim backlight to 0 (hardware only, no config persistence)
        self._set_backlight_hw(0)

        # Black screen -- no title, no buttons
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.create_rectangle(
                0, 0, SCREEN_W, SCREEN_H,
                fill=COLOR_BLACK, outline=COLOR_BLACK,
                tags='sleep_bg',
            )

    def onKeyEvent(self, key):
        """Any key wakes from sleep -- restore backlight and finish."""
        self._restore_backlight()
        self.finish()

    def onDestroy(self):
        """Ensure backlight is restored even if finish wasn't clean."""
        self._restore_backlight()
        super().onDestroy()

    def _read_backlight_level(self):
        """Read current backlight UI level (0/1/2) from settings."""
        try:
            import settings
            return settings.getBacklight()
        except Exception:
            return 2  # High (factory default)

    def _set_backlight_hw(self, hw_val):
        """Set backlight hardware directly (no config persistence).

        The original SleepModeActivity calls hmi_driver.setbaklight()
        directly — it does NOT go through settings.setBacklight() which
        would corrupt the saved config with the sleep-dim value.
        """
        try:
            import hmi_driver
            hmi_driver.setbaklight(hw_val)
        except Exception:
            pass

    def _restore_backlight(self):
        """Restore previous backlight level (hardware only)."""
        if self._prev_backlight is not None:
            try:
                import settings
                hw_val = settings.fromLevelGetBacklight(self._prev_backlight)
                import hmi_driver
                hmi_driver.setbaklight(hw_val)
            except Exception:
                pass
            self._prev_backlight = None


# ═══════════════════════════════════════════════════════════════════════
# AboutActivity
# ═══════════════════════════════════════════════════════════════════════

class AboutActivity(BaseActivity):
    """Device information display -- 2 pages (info + update instructions).

    From actmain.so AboutActivity and UI mapping docs:

    Page 0 (Device Info):
        - 6 lines from resources.itemmsg: aboutline1..aboutline6
        - Data from version module: getTYP, getHW, getHMI, getOS, getPM, getSN
        - M2 = "Update" (launches UpdateActivity)
        - PWR = finish (back to main menu)
        - DOWN = page 1

    Page 1 (Update Instructions):
        - 5 lines from resources.itemmsg: aboutline1_update..aboutline5_update
        - M2 = "Update" (launches UpdateActivity)
        - UP = page 0
        - PWR = finish

    Key handling:
        - M1: (empty label on page 0) -- navigate to previous page if not page 0
        - M2: checkUpdate() -> launch UpdateActivity
        - PWR: finish()
        - UP: prev page
        - DOWN: next page
    """

    ACT_NAME = 'about'

    def __init__(self, bundle=None):
        self._page_new = 0
        self._page_max = 2  # 3 pages: 0, 1, and 2 (scroller easter egg)
        self._btlv = None   # BigTextListView for content
        self._version_info = {}
        self._scroller = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, buttons, and device info.

        Ground truth (QEMU 20260405): title is always "About" (no page
        indicator in the title -- the indicator is in the content area).
        Buttons are hidden.  A brief "Processing..." toast appears on
        entry while version data loads.
        """
        self.setTitle(resources.get_str('about'))
        self.setLeftButton('')
        self.setRightButton('')

        canvas = self.getCanvas()
        self._toast = None
        if canvas is not None:
            from lib.widget import Toast
            self._toast = Toast(canvas)

        # Show page with placeholder values, then fetch real data in background.
        # "Processing..." toast stays visible until data arrives.
        self._version_info = {
            'typ': '...', 'hw': '', 'hmi': '...', 'os': '...', 'pm': '...',
        }
        self._show_page()

        if self._toast is not None:
            self._toast.show(resources.get_str('processing'), duration_ms=0)

        import threading
        def _fetch():
            self._load_version_info()
            try:
                if actstack._root is not None:
                    actstack._root.after(0, self._on_version_loaded)
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def onKeyEvent(self, key):
        """Handle navigation keys.

        Ground truth (QEMU 20260405):
        M1: no-op (buttons are hidden)
        M2/OK: launch UpdateActivity (only from page 2, index 1)
        PWR: finish
        UP: previous page
        DOWN: next page
        """
        if key in (KEY_M2, KEY_OK):
            if self._page_new == 1:
                self._check_update()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._stop_scroller()
            self.finish()
        elif key == KEY_UP:
            if self._page_new > 0:
                self._page_new -= 1
                self._show_page()
        elif key == KEY_DOWN:
            if self._page_new < self._page_max:
                self._page_new += 1
                self._show_page()

    def _on_version_loaded(self):
        """Tk-thread callback: redraw page with real data, dismiss toast."""
        if self._page_new <= 1:
            self._show_page()
        if self._toast is not None:
            self._toast.cancel()

    def _load_version_info(self):
        """Load version info from the version module.

        Uses try/except for each field since the module may not be
        available (e.g. in tests or on non-device environments).
        """
        info = {}
        try:
            import version
            info['typ'] = version.getTYP()
        except Exception:
            info['typ'] = 'iCopy-X'
        try:
            import version
            info['hw'] = version.getHW()
        except Exception:
            info['hw'] = '?'
        try:
            import version
            info['hmi'] = version.getHMI()
        except Exception:
            info['hmi'] = '?'
        try:
            import version
            info['os'] = version.getOS()
        except Exception:
            info['os'] = '?'
        try:
            import version
            info['pm'] = version.getPM()
        except Exception:
            info['pm'] = '?'
        try:
            import version
            info['sn'] = version.getSN()
        except Exception:
            info['sn'] = '?'

        self._version_info = info

    def _show_page(self):
        """Render current page content plus a page indicator.

        Ground truth (QEMU 20260405): content_text always has 3 items:
          [0] = page 0 text at (19, 140), fill=black, font=13, anchor=w
          [1] = page 1 text at (19, 140), fill=black, font=13, anchor=w
          [2] = page indicator at (165, 8), fill=white, font=11, anchor=nw
        Visible page at y=140, other page off-screen at y=500.
        Page 2 is the embedded scroller easter egg.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        from lib._constants import (
            NORMAL_TEXT_COLOR, TITLE_TEXT_COLOR,
            LIST_TEXT_X_NO_ICON, SCREEN_W,
            ABOUT_PAGE_IND_X, ABOUT_PAGE_IND_Y,
            ABOUT_PAGE_IND_FONT_SIZE, ABOUT_CONTENT_Y,
        )

        self._stop_scroller()
        canvas.delete('about_content')

        page_indicator = '%d/%d' % (self._page_new + 1, self._page_max + 1)
        ind_font = resources.get_font(ABOUT_PAGE_IND_FONT_SIZE)

        if self._page_new <= 1:
            info = self._version_info
            lines = [resources.get_str('aboutline1').format(info.get('typ', '?')), '']
            if info.get('hw'):
                lines.append(resources.get_str('aboutline2').format(info['hw']))
            lines.append(resources.get_str('aboutline3').format(info.get('hmi', '?')))
            lines.append(resources.get_str('aboutline4').format(info.get('os', '?')))
            lines.append(resources.get_str('aboutline5').format(info.get('pm', '?')))
            lines.append('')
            page0_text = '\n'.join(lines)
            page1_text = (
                resources.get_str('aboutline1_update') + '\n'
                '\n'
                + resources.get_str('aboutline2_update') + '\n'
                + resources.get_str('aboutline3_update') + '\n'
                + resources.get_str('aboutline4_update') + '\n'
                + resources.get_str('aboutline5_update')
            )

            content_font = resources.get_font(13)
            text_x = LIST_TEXT_X_NO_ICON
            text_w = SCREEN_W - 2 * LIST_TEXT_X_NO_ICON

            y_page0 = ABOUT_CONTENT_Y if self._page_new == 0 else 500
            y_page1 = ABOUT_CONTENT_Y if self._page_new == 1 else 500

            canvas.create_text(text_x, y_page0, text=page0_text,
                               fill=NORMAL_TEXT_COLOR, font=content_font,
                               anchor='w', width=text_w, tags='about_content')
            canvas.create_text(text_x, y_page1, text=page1_text,
                               fill=NORMAL_TEXT_COLOR, font=content_font,
                               anchor='w', width=text_w, tags='about_content')
            canvas.create_text(ABOUT_PAGE_IND_X, ABOUT_PAGE_IND_Y,
                               text=page_indicator,
                               fill=TITLE_TEXT_COLOR, font=ind_font,
                               anchor='nw', tags='about_content')
        else:
            self._start_scroller()

    def _start_scroller(self):
        """Create and embed the about scroller easter egg."""
        canvas = self.getCanvas()
        if canvas is None:
            return
        try:
            from lib.scroller import EmbeddedScroller
            self._scroller = EmbeddedScroller(actstack._root)
            canvas.create_window(
                0, 0, window=self._scroller.canvas,
                anchor='nw', tags='about_content',
            )
            self._scroller.start()
        except Exception:
            logger.exception("Failed to start about scroller")
            self._scroller = None

    def _stop_scroller(self):
        """Stop and destroy the embedded scroller if running."""
        if self._scroller is not None:
            self._scroller.stop()
            try:
                self._scroller.canvas.destroy()
            except Exception:
                pass
            self._scroller = None

    def _check_update(self):
        """Launch UpdateActivity for firmware update.

        Ground truth (activity_update.so):
        OK from About page 2 pushes UpdateActivity which has its own
        UI: "Start" confirmation → progress → result.  The install
        must NOT run inline on AboutActivity — it blocks the UI thread
        and provides no feedback.
        """
        actstack.start_activity(UpdateActivity, None)

    def get_page(self):
        """Return current page index (for testing)."""
        return self._page_new


# ═══════════════════════════════════════════════════════════════════════
# WarningDiskFullActivity
# ═══════════════════════════════════════════════════════════════════════

class WarningDiskFullActivity(BaseActivity):
    """Disk full warning -- shows message, offers to clear dump files.

    From actmain.so WarningDiskFullActivity:
    - onCreate: setTitle("Warning"), show disk_full_tips, buttons Ignore/Clear
    - onKeyEvent: M1 = finish (ignore), M2/OK = startClear
    - startClear: uses shutil.rmtree on dump directories, shows clearing toast

    The original uses resources.get_str('disk_full') for the title and
    resources.get_str('disk_full_tips') for the warning message.
    """

    ACT_NAME = 'warning_diskfull'

    # Default path for USB storage (from original constants)
    UPAN_PATH = '/mnt/upan'
    DUMP_DIRS = ['dump', 'dumps', 'data']

    def __init__(self, bundle=None):
        self._btlv = None
        self._cleared = False
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show disk full warning with Ignore/Clear buttons."""
        self.setTitle(resources.get_str('warning'))
        self.setLeftButton(resources.get_str('cancel') if resources.get_str('cancel') != 'cancel' else 'Ignore')
        self.setRightButton(resources.get_str('clear') if resources.get_str('clear') != 'clear' else 'Clear')

        # Display warning message
        canvas = self.getCanvas()
        if canvas is not None:
            from lib.widget import BigTextListView
            self._btlv = BigTextListView(canvas)
            self._btlv.drawStr(resources.get_str('disk_full_tips'))

    def onKeyEvent(self, key):
        """Handle button presses.

        M1/PWR: finish (ignore the warning)
        M2/OK: clear files and finish
        """
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK):
            self._start_clear()

    def _start_clear(self):
        """Delete dump directories to free space.

        Uses shutil.rmtree on each known dump directory under UPAN_PATH.
        Shows a clearing progress message, then finishes.
        """
        canvas = self.getCanvas()

        # Show clearing message
        if canvas is not None and self._btlv is not None:
            self._btlv.drawStr(resources.get_str('clearing') if resources.get_str('clearing') != 'clearing' else 'Clearing...')

        # Clear dump directories
        for dirname in self.DUMP_DIRS:
            dirpath = os.path.join(self.UPAN_PATH, dirname)
            if os.path.isdir(dirpath):
                try:
                    shutil.rmtree(dirpath)
                except Exception:
                    pass

        self._cleared = True
        self.finish()


# ═══════════════════════════════════════════════════════════════════════
# ConsolePrinterActivity
# ═══════════════════════════════════════════════════════════════════════

class ConsolePrinterActivity(BaseActivity):
    """Full-screen PM3 command output console.

    Ground truth: lua_console_*.png — full-screen black background,
    white monospace text, NO title bar, NO button bar.

    Key handling (read_console_common.sh lines 27-35):
        UP / M2:   textfontsizeup (zoom in, max 14)
        DOWN / M1: textfontsizedown (zoom out, min 6)
        RIGHT:     horizontal scroll right
        LEFT:      horizontal scroll left
        PWR:       exit console (finish activity)

    Binary symbols: textfontsizeup, textfontsizedown, updatefontinfo,
    updatetextfont, update_progress, add_text, on_exec_print, clear
    """

    ACT_NAME = 'console_printer'

    def onCreate(self, bundle):
        """Set up full-screen console with executor PM3 output.

        Ground truth: lua_console_*.png shows NO title bar, NO button bar.
        Full 240x240 black background with white monospace text.

        If bundle contains 'cmd', execute it via executor.startPM3Task.
        Evidence: real device trace shows PM3-TASK> script run hf_read timeout=-1
        is issued by ConsolePrinterActivity, not by the launcher.
        """
        # No title bar, no button bar — full screen console.
        # keep_bindings=True: M1/M2 are invisible but still dispatch
        # (used for zoom in/out — ground truth: read_console_common.sh)
        self.dismissButton(keep_bindings=True)

        self._poll_thread = None
        self._last_cache_len = 0
        self._bundle = bundle

        canvas = self.getCanvas()
        if canvas is None:
            return

        from lib.widget import ConsoleView
        self._console = ConsoleView(canvas, x=0, y=0,
                                    width=SCREEN_W, height=SCREEN_H)

        # Load current PM3 output cache
        try:
            import executor
            cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if cache:
                self._console.addText(cache)
                self._last_cache_len = len(cache)
        except Exception:
            pass

        self._console.show()
        self._autofit_done = False

        # Execute PM3 command from bundle if present
        # Ground truth: trace_misc_flows_session2_20260330.txt line 31:
        #   PM3-TASK> script run hf_read timeout=-1
        cmd = (bundle or {}).get('cmd', '')
        if cmd:
            import executor
            self.startBGTask(lambda: executor.startPM3Task(cmd, -1))

        # Start polling for new content (live updates during execution)
        import threading
        def _poll_content():
            import time
            while True:
                try:
                    import executor
                    cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
                    if len(cache) > self._last_cache_len:
                        new_text = cache[self._last_cache_len:]
                        self._last_cache_len = len(cache)
                        self._console.addText(new_text)
                        # Auto-zoom once after first content arrives
                        if not self._autofit_done:
                            self._autofit_done = True
                            self._console.autofit_font_size()
                            if self._console._showing:
                                self._console._redraw()
                except Exception:
                    pass
                time.sleep(0.3)
        self._poll_thread = threading.Thread(target=_poll_content, daemon=True)
        self._poll_thread.start()

    def onKeyEvent(self, key):
        """Console key handling.

        M1:    zoom out (textfontsizedown)
        M2:    zoom in (textfontsizeup)
        UP:    scroll up
        DOWN:  scroll down
        LEFT:  scroll left
        RIGHT: scroll right
        PWR:   exit console
        """
        if key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()
        elif key == KEY_M2:
            if hasattr(self, '_console'):
                self._console.textfontsizeup()
        elif key == KEY_M1:
            if hasattr(self, '_console'):
                self._console.textfontsizedown()
        elif key == KEY_UP:
            if hasattr(self, '_console'):
                self._console.scrollUp()
        elif key == KEY_DOWN:
            if hasattr(self, '_console'):
                self._console.scrollDown()
        elif key == KEY_RIGHT:
            if hasattr(self, '_console'):
                self._console.scrollRight()
        elif key == KEY_LEFT:
            if hasattr(self, '_console'):
                self._console.scrollLeft()


# ═══════════════════════════════════════════════════════════════════════
# ScanActivity
# ═══════════════════════════════════════════════════════════════════════

class ScanActivity(BaseActivity):
    """Tag scanning activity with multi-state flow.

    States:
    1. IDLE -- Tag type list (48 types, paginated) with Scan button
       OR direct scan (if launched from AutoCopy or Erase with tag_type)
    2. SCANNING -- Progress bar, "Scanning..." message, middleware running
    3. FOUND -- Tag info displayed, "Tag Found" toast
    4. NOT_FOUND -- Empty content, "No tag found" toast
    5. WRONG_TYPE -- Empty content, "No tag found Or Wrong type found!" toast
    6. MULTI_TAGS -- Empty content, "Multiple tags detected!" toast

    The scan.so module handles ALL RFID detection logic.
    We just orchestrate the UI states.

    Binary source: activity_main.so ScanActivity
    Verified: docs/UI_Mapping/03_scan_tag/README.md (exhaustive)
    Spec: 48 scannable types, 6 states, 5 toast variants

    Key behavior (from binary onKeyEvent):
        SCANNING state:
            M1/M2: cancel scan, return to IDLE
            PWR:   cancel scan, exit activity
            UP/DOWN/OK: ignored
        IDLE state:
            M1:    finish (back)
            M2/OK: start scan for selected type
            UP:    scroll up in type list
            DOWN:  scroll down in type list
            PWR:   finish (exit)
        Result states (FOUND/NOT_FOUND/WRONG_TYPE/MULTI):
            M1:    rescan (back to IDLE->SCANNING)
            M2/OK: rescan
            PWR:   exit activity
    """

    ACT_NAME = 'scan'

    # State constants
    STATE_IDLE = 'idle'
    STATE_SCANNING = 'scanning'
    STATE_FOUND = 'found'
    STATE_NOT_FOUND = 'not_found'
    STATE_WRONG_TYPE = 'wrong_type'
    STATE_MULTI = 'multi_tags'

    # Return codes from scan.so (verified via QEMU: getattr(scan, 'CODE_TAG_*'))
    CODE_TAG_LOST = -2
    CODE_TAG_MULT = -3
    CODE_TAG_NO = -4
    CODE_TAG_TYPE_WRONG = -5
    CODE_TIMEOUT = -1

    def __init__(self, bundle=None):
        self._state = self.STATE_IDLE
        self._scan_cache = None
        self._scan_result = None
        self._is_scanning = False
        self._directed_type = None
        self._listview = None
        self._progress = None
        self._toast = None
        self._btlv = None
        self._tag_type_list = []
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Start scanning immediately on entry.

        Ground truth: scan_tag_scanning_1..5.png, trace_scan_flow_20260331.txt
        START(ScanActivity, None) → immediate PM3 commands.
        """
        self.setTitle(resources.get_str('scan_tag'))

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._toast = Toast(canvas)

        # JSON renderer for declarative content rendering
        from lib.json_renderer import JsonRenderer
        self._jr = JsonRenderer(canvas)

        self._startScan()

    def onResume(self):
        super().onResume()

    def onKeyEvent(self, key):
        """Handle keys based on current state.

        From binary onKeyEvent -- see docs/UI_Mapping/03_scan_tag/README.md
        section 6 for complete key handler logic.
        """
        # PWR: always works, even during scanning.
        # Ground truth (spec): "SCANNING state: PWR = cancel scan, exit activity"
        # Must abort any in-flight PM3 command before finishing.
        if key == KEY_PWR:
            # Dismiss toast if showing (but don't swallow the key)
            for attr in ('_toast',):
                toast = getattr(self, attr, None)
                if toast is not None:
                    try:
                        if toast.isShow():
                            toast.cancel()
                    except Exception:
                        pass
            if self._state == self.STATE_SCANNING:
                try:
                    import hmi_driver
                    hmi_driver.presspm3()
                except Exception:
                    pass
                try:
                    import executor
                    executor.stopPM3Task()
                except Exception:
                    pass
            self.finish()
            return

        if self._state == self.STATE_SCANNING:
            # During scan: all keys except PWR ignored
            return

        # Result states: FOUND, NOT_FOUND, WRONG_TYPE, MULTI
        # Ground truth (original trace line 84):
        #   FOUND state: M1="Rescan", M2="Simulate" → pushes SimulationActivity
        #   Other states: M1/M2="Rescan"
        if key == KEY_M2 and self._state == self.STATE_FOUND:
            # Simulate — push SimulationActivity with full scan cache
            # Ground truth: original passes entire scan result dict as bundle
            # e.g. {'found':True,'uid':'5E5BCE4C','type':1,'len':4,'sak':'08',...}
            tag_type = -1
            if isinstance(self._scan_result, dict):
                tag_type = self._scan_result.get('type', -1)
            if tag_type in _SIMULATE_TYPES:
                actstack.start_activity(SimulationActivity, dict(self._scan_result))
            else:
                self._clearContent()
                self._startScan()
        elif self._state in (self.STATE_NOT_FOUND, self.STATE_WRONG_TYPE):
            # M1 hidden, OK unmapped — only M2 rescans
            if key == KEY_M2:
                self._clearContent()
                self._startScan()
        elif key in (KEY_M1, KEY_M2, KEY_OK):
            # MULTI / FOUND(M1): rescan
            self._clearContent()
            self._startScan()

    def _setupIdleState(self):
        """Configure UI for IDLE state: tag type list with Back/Scan buttons."""
        self._state = self.STATE_IDLE
        self._is_scanning = False

        # Clear any previous content
        self._clearContent()

        self.setLeftButton(resources.get_str('cancel'))
        self.setRightButton(resources.get_str('rescan') if self._scan_result else resources.get_str('start'))

        # Build tag type list if not yet built
        if not self._tag_type_list:
            self._buildTagTypeList()

        canvas = self.getCanvas()
        if canvas is None:
            return

        # Show buttons for idle
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('scan'))

        # Create tag type ListView
        from lib.widget import ListView
        self._listview = ListView(canvas)
        self._listview.setItems(self._tag_type_list)
        self._listview.setOnPageChangeCall(self._onScanPageChange)
        self._listview.show()
        self._updateScanTitle()

    def _onScanPageChange(self, page):
        """Callback from ListView when page changes."""
        self._updateScanTitle()

    def _updateScanTitle(self):
        """Update title: 'Scan Tag N/M'.

        [Source: UI_MAP_COMPLETE.md row 21]
        """
        if self._listview is None:
            self.setTitle(resources.get_str('scan_tag'))
            return
        total = self._listview.getPageCount()
        current = self._listview.getPagePosition() + 1
        if total > 1:
            self.setTitle('%s %d/%d' % (
                resources.get_str('scan_tag'), current, total))
        else:
            self.setTitle(resources.get_str('scan_tag'))

    def _buildTagTypeList(self):
        """Build the list of scannable tag type names.

        Uses tagtypes.getScannable() if available, otherwise a minimal list.
        """
        try:
            import tagtypes
            scannable = tagtypes.getScannable()
            for type_id in scannable:
                name = tagtypes.getTypeName(type_id)
                self._tag_type_list.append(name)
        except Exception:
            # Fallback: minimal list for testing
            self._tag_type_list = [
                'M1 S70 4K (4B)', 'M1 S50 1K (4B)', 'Ultralight',
                'Ultralight C', 'Ultralight EV1', 'NTAG213',
                'NTAG215', 'NTAG216', 'EM410X', 'HID Prox',
                'Indala', 'AWID', 'IO ProxXSF', 'G-Prox II',
                'Securakey', 'Viking', 'Pyramid',
            ]

    def _startScanFromList(self):
        """Rescan — restart the scan operation."""
        self._clearContent()
        self._startScan()

    def _startScan(self):
        """Start scan — calls scan.scan_all_asynchronous(self).

        The real scan.so handles ALL RFID detection logic.
        It calls back self.onScanFinish(result) when done,
        and self.onScanning(progress) during scan.

        Source: activity_main.so ScanActivity.onCreate calls
        scan.scan_all_asynchronous(self)
        """
        self._state = self.STATE_SCANNING
        self._is_scanning = True
        self.setbusy()
        self._scan_result = None

        # Render scanning screen via JSON
        # Ground truth: original firmware immediately fills to 50%
        self._jr.set_state({'scan_progress': 50})
        self._jr.render({
            'content': {
                'type': 'progress',
                'message': resources.get_str('scanning'),
                'value': 50,
                'max': 100,
            },
            'buttons': {'left': None, 'right': None},
        })
        self.dismissButton()

        # Call scan.so to start scanning.
        #
        # Correct call pattern (discovered via probing scan.so under QEMU):
        #   scanner = scan.Scanner()       # no args
        #   scanner.call_progress = self   # listener for progress callbacks
        #   scanner.call_resulted = self   # listener for result callbacks
        #   scanner.call_exception = self  # listener for exception callbacks
        #   scanner.scan_all_asynchronous()  # starts scan thread, no args
        #
        # The Scanner calls back:
        #   self.onScanning(progress)   — via call_progress
        #   self.onScanFinish(result)   — via call_resulted
        #
        # Source: scan.so probing + activity_main.so symbol table
        try:
            import scan as _scan_mod
            self._scanner = _scan_mod.Scanner()
            self._scanner.call_progress = self.onScanning
            self._scanner.call_resulted = self.onScanFinish
            self._scanner.call_exception = self.onScanFinish
            self._scanner.scan_all_asynchronous()
        except Exception as e:
            import traceback as _tb
            print('[SCAN] scan start error: %s' % e, flush=True)
            _tb.print_exc()

    def _cancelScan(self):
        """Cancel an in-progress scan."""
        self._is_scanning = False
        self.setidle()
        try:
            if hasattr(self, '_scanner') and self._scanner:
                self._scanner.scan_stop()
        except Exception:
            pass

    def onScanning(self, progress):
        """Callback from scan.so -- update progress bar.

        scan.so passes a tuple (current, max) for progress.
        Fires from scanner background thread — schedule on Tk main thread.
        """
        if isinstance(progress, (list, tuple)) and len(progress) >= 2:
            pct = int(progress[0] * 100 / max(progress[1], 1))
        else:
            pct = int(progress) if progress else 0

        def _update():
            if hasattr(self, '_jr'):
                self._jr.render_content_only({
                    'type': 'progress',
                    'message': resources.get_str('scanning'),
                    'value': pct,
                    'max': 100,
                })

        try:
            from lib import actstack
            if actstack._root is not None:
                actstack._root.after(0, _update)
            else:
                _update()
        except Exception:
            pass

    def onScanFinish(self, result):
        """Callback from scan.so -- process scan result.

        scan.so may pass a string (error/traceback) or dict (tag info).
        """
        import executor as _ex, threading as _thr
        cache_now = (getattr(_ex, 'CONTENT_OUT_IN__TXT_CACHE', '') or '')[:80]
        print('[SCAN-RESULT] type=%s cache=%r thread=%s' % (
            result.get('type', '?') if isinstance(result, dict) else '?',
            cache_now, _thr.current_thread().name), flush=True)
        self._is_scanning = False
        self.setidle()
        self._scan_result = result
        self._onScanResult(result)

    def _onScanResult(self, result):
        """Process scan result and transition to appropriate state.

        scan.so may return:
        - A string code: 'CODE_TAG_NO', 'CODE_TIMEOUT', etc.
        - A dict with scan data: {'found': True, 'type': 1, 'uid': '...', ...}
        - An int code: -1 (no tag), -2 (multi), etc.
        - None
        """
        self._clearContent()

        if result is None:
            result = {'found': False, 'return': self.CODE_TAG_NO}

        # Handle string result codes from scan.so
        if isinstance(result, str):
            code_map = {
                'CODE_TAG_NO': self.CODE_TAG_NO,
                'CODE_TAG_MULT': self.CODE_TAG_MULT,
                'CODE_TAG_LOST': self.CODE_TAG_LOST,
                'CODE_TAG_TYPE_WRONG': self.CODE_TAG_TYPE_WRONG,
                'CODE_TIMEOUT': self.CODE_TIMEOUT,
            }
            ret_code = code_map.get(result, self.CODE_TAG_NO)
            result = {'found': False, 'return': ret_code}

        # Handle int result codes
        if isinstance(result, int):
            result = {'found': False, 'return': result}

        # Determine state based on result (predicate priority from binary)
        # Multi-tag MUST be checked before found — multi-tag has found=True
        # but return=CODE_TAG_MULT (-3), so it must be caught first.
        ret_code = result.get('return', self.CODE_TAG_NO)
        found = result.get('found', False)
        has_multi = result.get('hasMulti', False)

        if has_multi or ret_code == self.CODE_TAG_MULT:
            self._state = self.STATE_MULTI
            # Render empty + buttons via JSON
            if hasattr(self, '_jr'):
                self._jr.render({
                    'content': {'type': 'empty'},
                    'buttons': {'left': resources.get_str('rescan'),
                                'right': resources.get_str('simulate')},
                })
            self.showScanToast(found=False, multi=True)
            self.setScanCache(result)
        elif found:
            self._state = self.STATE_FOUND
            self._showFoundState(result)
            self.showScanToast(found=True)
            self.setScanCache(result)
        elif ret_code == self.CODE_TAG_TYPE_WRONG:
            self._state = self.STATE_WRONG_TYPE
            if hasattr(self, '_jr'):
                self._jr.render({
                    'content': {'type': 'empty'},
                    'buttons': {'left': '',
                                'right': resources.get_str('rescan')},
                })
            # Update BaseActivity button flags (_jr.render is visual only)
            self.setLeftButton('')
            self.setRightButton(resources.get_str('rescan'))
            self.showScanToast(found=False, wrong_type=True)
        else:
            self._state = self.STATE_NOT_FOUND
            if hasattr(self, '_jr'):
                self._jr.render({
                    'content': {'type': 'empty'},
                    'buttons': {'left': '',
                                'right': resources.get_str('rescan')},
                })
            # Update BaseActivity button flags (_jr.render is visual only)
            self.setLeftButton('')
            self.setRightButton(resources.get_str('rescan'))
            self.showScanToast(found=False)

    def _showFoundState(self, result):
        """Display tag info by delegating to template.so.

        Ground truth: template.so (Cython .so on device) owns ALL scan
        result rendering.  It picks the right __drawXxx method based on
        tag type and formats every field (UID, SAK, ATQA, Frequency, …)
        using its internal string table.

        API: template.draw(typ, data, parent)
            typ   — integer tag type from scan result
            data  — the raw scan result dict from scan.so
            parent — the activity instance (has canvas via getCanvas())
        """
        tag_type = result.get('type', -1)

        # template.so renders all tag info directly to the canvas.
        # API: template.draw(typ, data, canvas) — canvas is the parent.
        # Ground truth: template.__drawFinal calls parent.create_text()
        # Ground truth: trace_lf_scan_flow_20260331.txt shows template.so
        # reads executor.CONTENT_OUT_IN__TXT_CACHE for LF tag display data.
        canvas = self.getCanvas()
        if canvas is not None:
            try:
                import template, executor
                print('[TEMPLATE] cache=%r' % (getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '')[:100],), flush=True)
                template.draw(tag_type, result, canvas)
            except Exception as e:
                print('[TEMPLATE] draw failed: %s' % e, flush=True)

        # Set buttons: M1=Rescan, M2=Simulate always (active only if simulatable)
        # Ground truth: original .so shows M2="Simulate" for ALL types,
        # with M2_active=False for non-simulatable types.
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('simulate'), active=(tag_type in _SIMULATE_TYPES))

    def _showResultButtons(self):
        """Update M1/M2 buttons based on scan result.

        Ground truth — real device screenshots:
          scan_tag_scanning_5.png (found MFC 1K): M1="Rescan" M2="Simulate"
          scan_tag_no_tag_found_2.png (not found): M1="Rescan" M2="Rescan"

        Ground truth — QEMU API dump (qemu_api_dump_filtered.txt line 223):
          showButton(self, found, cansim=False)

        Ground truth — activity_main_strings.txt:
          text_rescan, text_simulate
        """
        if self._state == self.STATE_FOUND:
            self.setLeftButton(resources.get_str('rescan'))
            tag_type = -1
            if isinstance(self._scan_result, dict):
                tag_type = self._scan_result.get('type', -1)
            self.setRightButton(resources.get_str('simulate'), active=(tag_type in _SIMULATE_TYPES))
        else:
            self.setLeftButton(resources.get_str('rescan'))
            self.setRightButton(resources.get_str('rescan'))

    def showScanToast(self, found, multi=False, wrong_type=False):
        """Show the appropriate scan result toast.

        This is the critical method that bridges middleware result to UI.
        Toast messages from resources.py (verified against binary):
            tag_found:      "Tag Found"
            no_tag_found:   "No tag found"
            no_tag_found2:  "No tag found \\nOr\\n Wrong type found!"
            tag_multi:      "Multiple tags detected!"

        Audio cues (from binary):
            found:      audio.playTagfound()
            not_found:  audio.playTagNotfound()
            wrong_type: audio.playwrongTagfound()
            multi:      audio.playMultiCard()
        """
        if self._toast is None:
            return

        if found:
            self._toast.show(
                resources.get_str('tag_found'),
                mode=Toast.MASK_CENTER,
                icon='check',
            )
            try:
                import audio
                audio.playTagfound()
            except Exception:
                pass
        elif multi:
            self._toast.show(
                resources.get_str('tag_multi'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
            try:
                import audio
                audio.playMultiCard()
            except Exception:
                pass
        elif wrong_type:
            self._toast.show(
                resources.get_str('no_tag_found2'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
            try:
                import audio
                audio.playwrongTagfound()
            except Exception:
                pass
        else:
            self._toast.show(
                resources.get_str('no_tag_found'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
            try:
                import audio
                audio.playTagNotfound()
            except Exception:
                pass

    def setScanCache(self, result):
        """Store scan result for use by downstream activities."""
        self._scan_cache = result
        # Also set in scan module cache if available
        try:
            import scan
            scan.setScanCache(result)
        except Exception:
            pass

    def getScanCache(self):
        """Retrieve stored scan result."""
        return self._scan_cache

    def canidle(self):
        """Return whether activity is idle (not scanning).

        From binary: returns True when not in SCANNING state.
        """
        return not self._is_scanning

    def _clearContent(self):
        """Clear all content-area widgets."""
        if self._progress is not None:
            self._progress.hide()
            self._progress = None
        if self._btlv is not None:
            self._btlv.hide()
            self._btlv = None
        if self._listview is not None:
            self._listview.hide()
            self._listview = None
        if self._toast is not None:
            self._toast.cancel()
        canvas = self.getCanvas()
        if canvas is not None:
            # Clear JSON renderer items (progress bar, etc.)
            canvas.delete('_jr_content')
            canvas.delete('_jr_content_bg')
            canvas.delete('_jr_buttons')
            # Clear scan result rendered by template.so
            try:
                import template
                template.dedraw(canvas)
            except Exception:
                pass

    @property
    def state(self):
        """Current state (for testing)."""
        return self._state


# ═══════════════════════════════════════════════════════════════════════
# PCModeActivity
# ═══════════════════════════════════════════════════════════════════════

class PCModeActivity(BaseActivity):
    """USB mass storage + serial bridge mode.

    Enables PC-side access to the Proxmark3 via USB gadget serial and
    exposes the user partition as USB mass storage.

    4 states: IDLE -> STARTING -> RUNNING -> STOPPING -> finish()

    Binary source: activity_main.so PCModeActivity
    Verified: QEMU walker screenshots
    Spec: docs/UI_Mapping/07_pc_mode/README.md

    State machine:
        IDLE:     M1/M2/OK -> STARTING (run_press thread)
                  PWR -> finish()
        STARTING: all keys ignored (background thread active)
        RUNNING:  M1/M2 -> STOPPING (run_finish thread)
                  PWR -> STOPPING then finish()
        STOPPING: all keys ignored (background thread active)

    Button labels:
        IDLE:     M1="Start", M2="Start"
        STARTING: M1=disabled, M2=disabled
        RUNNING:  M1="Stop",  M2="Button"
        STOPPING: M1=disabled, M2=disabled
    """

    ACT_NAME = 'pcmode'

    # State constants
    STATE_IDLE = 'idle'
    STATE_STARTING = 'starting'
    STATE_RUNNING = 'running'
    STATE_STOPPING = 'stopping'

    def __init__(self, bundle=None):
        self._state = self.STATE_IDLE
        self._toast = None
        self._btlv = None
        self._process_socat = None
        self._child_pid = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set title, show connection prompt, init buttons.

        From binary PCModeActivity.onCreate:
            1. setTitle("PC-Mode")
            2. Show text_connect_computer prompt
            3. Both buttons = "Start"
        """
        self.setTitle(resources.get_str('pc-mode'))

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._toast = Toast(canvas)

        # Show connection prompt centered (ground truth: x=120, y=120, anchor=center)
        from lib._constants import NORMAL_TEXT_COLOR
        canvas.create_text(
            120, 120,
            text=resources.get_str('connect_computer'),
            fill=NORMAL_TEXT_COLOR,
            font=resources.get_font(14),
            anchor='center',
            tags='pcmode_content',
        )

        # Both buttons = "Start"
        self.showButton()

    def onKeyEvent(self, key):
        """State-dependent key dispatch.

        From binary PCModeActivity.onKeyEvent:
            IDLE:     M1/M2/OK -> start PC mode
                      PWR -> finish()
            STARTING: all ignored
            RUNNING:  M1/M2 -> stop PC mode
                      PWR -> stop PC mode + finish()
            STOPPING: all ignored
        """
        if self._state == self.STATE_IDLE:
            if key in (KEY_M1, KEY_M2):
                self._run_press()
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
        elif self._state == self.STATE_RUNNING:
            if key in (KEY_M1, KEY_M2):
                self._run_finish()
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self._run_finish()

        # STARTING and STOPPING: all keys ignored

    def _run_press(self):
        """Background thread: start PC mode sequence.

        From binary run_press():
            1. Show "Processing..." toast
            2. gadget_linux.upan_and_serial()
            3. start_socat()
            4. wait_for_pm3_online()
            5. hmi_driver.presspm3()
            6. executor.startPM3Ctrl()
            7. showRunningToast()
            8. audio.playPCModeRunning()
            9. showButton()
        """
        # Block if Screen Mirroring is active (mutual exclusion on USB gadget)
        try:
            import settings
            if settings.getScreenMirror():
                if self._toast is not None:
                    self._toast.show(resources.get_str('pcmode_mirror_conflict'))
                return
        except Exception:
            pass

        self._state = self.STATE_STARTING

        # Set button labels to Stop/Button (disabled) and show Processing toast
        self.showButton()

        if self._toast is not None:
            self._toast.show(resources.get_str('processing'), duration_ms=0)

        def _do_start():
            try:
                self.startPCMode()
                self._state = self.STATE_RUNNING
                # UI updates from BG thread must go through Tk main thread
                root = actstack._root
                if root is not None:
                    root.after(0, self.showRunningToast)
                    root.after(0, self.showButton)
                try:
                    import audio
                    audio.playPCModeRunning()
                except Exception:
                    pass
            except Exception:
                self._state = self.STATE_IDLE
                root = actstack._root
                if root is not None:
                    root.after(0, self.showButton)

        self.startBGTask(_do_start)

    def _run_finish(self):
        """Background thread: stop PC mode and cleanup.

        From binary run_finish():
            1. stopPCMode()
            2. finish()
        """
        self._state = self.STATE_STOPPING

        # Disable buttons
        self.disableButton(left=True, right=True)

        def _do_stop():
            try:
                self.stopPCMode()
            except Exception:
                pass
            root = actstack._root
            if root is not None:
                root.after(0, self.finish)
            else:
                self.finish()

        self.startBGTask(_do_stop)

    def startPCMode(self):
        """Start PC mode: gadget + socat + PM3.

        From binary startPCMode():
            1. gadget_linux.upan_and_serial()
            2. start_socat()
            3. wait_for_pm3_online()
            4. hmi_driver.presspm3()
            5. executor.startPM3Ctrl()
        """
        try:
            import gadget_linux
            gadget_linux.upan_and_serial()
        except Exception:
            pass

        self.start_socat()

        self.wait_for_pm3_online()

        try:
            import hmi_driver
            hmi_driver.presspm3()
        except Exception:
            pass

        try:
            import executor
            executor.startPM3Ctrl()
        except Exception:
            pass

    def stopPCMode(self):
        """Stop PC mode: kill socat, gadget, restart PM3.

        From binary stopPCMode():
            1. stop_socat()
            2. kill_child_processes()
            3. gadget_linux.kill_all_module()
            4. hmi_driver.restartpm3()
            5. executor.reworkPM3All()
        """
        self.stop_socat()
        self.kill_child_processes()

        try:
            import gadget_linux
            gadget_linux.kill_all_module()
        except Exception:
            pass

        try:
            import hmi_driver
            hmi_driver.restartpm3()
        except Exception:
            pass

        try:
            import executor
            executor.reworkPM3All()
        except Exception:
            pass

    def start_socat(self):
        """Start socat bridge: ttyGS0 <-> ttyACM0 (direct serial).

        From binary start_socat() string table:
            dev1 = '/dev/ttyGS0,raw,echo=0'  (USB gadget serial → host PC)
            dev2 = '/dev/ttyACM0,raw,echo=0'  (PM3 hardware serial)
        Live device confirmation: socat fd5=ttyGS0, fd6=ttyACM0
        Process tree: python3 → sh -c → sudo → socat (shell=True)
        See: docs/Real_Hardware_Intel/pcmode_live_audit_20260411.txt §3
        """
        try:
            import subprocess
            self._process_socat = subprocess.Popen(
                'sudo socat /dev/ttyGS0,raw,echo=0 /dev/ttyACM0,raw,echo=0',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
            self._child_pid = self._process_socat.pid
        except Exception:
            pass

    def stop_socat(self):
        """Kill socat process."""
        if self._process_socat is not None:
            try:
                self._process_socat.kill()
            except Exception:
                pass
            self._process_socat = None

    def kill_child_processes(self):
        """Kill all tracked child PIDs via psutil."""
        if self._child_pid is not None:
            try:
                import psutil
                proc = psutil.Process(self._child_pid)
                proc.kill()
            except Exception:
                pass
            self._child_pid = None

    def wait_for_pm3_online(self):
        """Poll until PM3 responds after gadget setup."""
        # On real device: polls executor until PM3 connection established
        # In test/QEMU: no-op (PM3 is always "online")
        pass

    def showRunningToast(self):
        """Show 'PC-mode Running...' persistent toast."""
        if self._toast is not None:
            self._toast.show(resources.get_str('pcmode_running'), duration_ms=0)

    def showButton(self):
        """Update M1/M2 button labels based on current state.

        IDLE:     M1="Start", M2="Start" (active)
        STARTING: disabled (labels unchanged)
        RUNNING:  M1=hidden,  M2="Stop" (active)
        STOPPING: disabled (labels unchanged)
        """
        if self._state == self.STATE_IDLE:
            self.setLeftButton(resources.get_str('start'))
            self.setRightButton(resources.get_str('start'))
        elif self._state == self.STATE_RUNNING:
            self.setLeftButton('')
            self.setRightButton(resources.get_str('stop'))
        else:
            # STARTING/STOPPING: just disable, don't change labels
            self.disableButton(left=True, right=True)

    def print_warning_on_windows(self):
        """Show Windows USB driver warning if applicable.

        Non-blocking informational display about Windows serial gadget
        driver requirements.
        """
        pass

    def get_state(self):
        """Return current state (for testing)."""
        return self._state


# ═══════════════════════════════════════════════════════════════════════
# TimeSyncActivity
# ═══════════════════════════════════════════════════════════════════════

import time as _time_module
import calendar as _calendar_module


class TimeSyncActivity(BaseActivity):
    """6-field cursor date/time editor: YYYY-MM-DD HH:MM:SS.

    Two states:
        DISPLAY — shows current time, auto-updates. M1/M2="Edit", PWR=exit.
        EDIT    — cursor on one of 6 fields, UP/DOWN change value,
                  LEFT/RIGHT move cursor. M2="Save", PWR=back to display.

    Binary source: activity_main.so TimeSyncActivity
    Verified: QEMU screenshots, docs/UI_Mapping/13_time_settings/README.md

    Screen layout:
        Title: "Time Settings" (resources key: time_sync)
        Content: 6 boxed numeric fields (YYYY--MM--DD / HH:MM:SS)
        DISPLAY: M1="Edit", M2="Edit"
        EDIT:    M1="Cancel", M2="Save"
    """

    ACT_NAME = 'time_settings'

    FIELDS = ['year', 'month', 'day', 'hour', 'minute', 'second']

    # Field ranges: (min, max) — day max is context-sensitive
    _FIELD_RANGES = {
        'year':   (2000, 2099),
        'month':  (1, 12),
        'day':    (1, 31),
        'hour':   (0, 23),
        'minute': (0, 59),
        'second': (0, 59),
    }

    STATE_DISPLAY = 'display'
    STATE_EDIT = 'edit'

    def onCreate(self, bundle):
        """Read current system time and display 6 fields.

        Flow (from binary onCreate):
            1. init_views() — create 6 input field views
            2. Read current system time (Python time module)
            3. Populate fields with YYYY, MM, DD, HH, MM, SS
            4. Start in DISPLAY mode
        """
        self.setTitle(resources.get_str('time_sync'))
        self.setLeftButton(resources.get_str('edit'))
        self.setRightButton(resources.get_str('edit'))

        self._state = self.STATE_DISPLAY
        self._cursor = 0  # field index: 0=year .. 5=second

        # Read current time
        now = _time_module.localtime()
        self._values = {
            'year':   now.tm_year,
            'month':  now.tm_mon,
            'day':    now.tm_mday,
            'hour':   now.tm_hour,
            'minute': now.tm_min,
            'second': now.tm_sec,
        }

        canvas = self.getCanvas()
        if canvas is None:
            return

        from lib.json_renderer import JsonRenderer
        self._jr = JsonRenderer(canvas)
        self._toast = Toast(canvas)
        self._drawTimeFields()

    def onKeyEvent(self, key):
        """Handle keys based on DISPLAY/EDIT state.

        From binary onKeyEvent:
            DISPLAY mode:
                M1/M2: enter EDIT mode, focus first field
                PWR:   finish()
            EDIT mode:
                UP:    increment focused field value
                DOWN:  decrement focused field value
                LEFT:  move cursor to previous field (wraps)
                RIGHT: move cursor to next field (wraps)
                M2:    save time, show toast, return to display
                M1:    cancel edit, discard changes, return to DISPLAY
                PWR:   discard changes, return to DISPLAY
        """
        if self._state == self.STATE_DISPLAY:
            if key in (KEY_M1, KEY_M2):
                self._enterEditMode()
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
        elif self._state == self.STATE_EDIT:
            if key == KEY_UP:
                self._incrementField()
            elif key == KEY_DOWN:
                self._decrementField()
            elif key == KEY_LEFT:
                self._moveCursorLeft()
            elif key == KEY_RIGHT:
                self._moveCursorRight()
            elif key == KEY_M2:
                self._saveTime()
            elif key == KEY_M1:
                self._exitEditMode()
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self._exitEditMode()

    def _enterEditMode(self):
        """Switch to EDIT state, focus first field (year), show arrows."""
        self._state = self.STATE_EDIT
        self._cursor = 0
        self.setLeftButton(resources.get_str('cancel'))  # EDIT: M1=Cancel
        self.setRightButton(resources.get_str('save'))
        self._drawTimeFields()

    def _exitEditMode(self):
        """Discard changes, re-read current time, return to DISPLAY."""
        self._state = self.STATE_DISPLAY
        self.setLeftButton(resources.get_str('edit'))
        self.setRightButton(resources.get_str('edit'))
        # Re-read current time
        now = _time_module.localtime()
        self._values = {
            'year':   now.tm_year,
            'month':  now.tm_mon,
            'day':    now.tm_mday,
            'hour':   now.tm_hour,
            'minute': now.tm_min,
            'second': now.tm_sec,
        }
        self._drawTimeFields()

    def _incrementField(self):
        """Increment the focused field, wrapping at max -> min."""
        field = self.FIELDS[self._cursor]
        lo, hi = self._getFieldRange(field)
        val = self._values[field]
        if val >= hi:
            self._values[field] = lo
        else:
            self._values[field] = val + 1
        # Original .so sets day = max_days_in_month on year/month change
        # Ground truth: April-09 + UP year → April-30 (not April-09)
        if field in ('year', 'month'):
            self._setDayToMonthMax()
        self._drawTimeFields()

    def _decrementField(self):
        """Decrement the focused field, wrapping at min -> max."""
        field = self.FIELDS[self._cursor]
        lo, hi = self._getFieldRange(field)
        val = self._values[field]
        if val <= lo:
            self._values[field] = hi
        else:
            self._values[field] = val - 1
        # Original .so sets day = max_days_in_month on year/month change
        if field in ('year', 'month'):
            self._setDayToMonthMax()
        self._drawTimeFields()

    def _moveCursorLeft(self):
        """Move cursor to previous field, wrapping around."""
        if self._cursor <= 0:
            self._cursor = len(self.FIELDS) - 1
        else:
            self._cursor -= 1
        self._drawTimeFields()

    def _moveCursorRight(self):
        """Move cursor to next field, wrapping around."""
        if self._cursor >= len(self.FIELDS) - 1:
            self._cursor = 0
        else:
            self._cursor += 1
        self._drawTimeFields()

    def _getFieldRange(self, field):
        """Return (min, max) for a field. Day max depends on month/year."""
        if field == 'day':
            year = self._values['year']
            month = self._values['month']
            max_day = _calendar_module.monthrange(year, month)[1]
            return (1, max_day)
        return self._FIELD_RANGES[field]

    def _clampDay(self):
        """Clamp day value if it exceeds max for current month/year."""
        year = self._values['year']
        month = self._values['month']
        max_day = _calendar_module.monthrange(year, month)[1]
        if self._values['day'] > max_day:
            self._values['day'] = max_day

    def _setDayToMonthMax(self):
        """Set day to max days in current month/year.

        Ground truth: original .so always sets day = max_days_in_month
        when year or month field changes (not just clamping down).
        Evidence: time_increment_field trace: April-09 + UP year → April-30.
        """
        year = self._values['year']
        month = self._values['month']
        self._values['day'] = _calendar_module.monthrange(year, month)[1]

    def _saveTime(self):
        """Write edited time to system + show success toasts.

        From binary sync_time_to_system():
            1. Show toast "Synchronizing system time"
            2. Set system time via subprocess
            3. Send time to GD32 RTC via hmi_driver
            4. Show toast "Synchronization successful!"
            5. Return to DISPLAY mode
        """
        # Show syncing toast
        if hasattr(self, '_toast'):
            self._toast.show(resources.get_str('time_syncing'))

        # Apply system time (best-effort, will fail on non-root / test)
        try:
            date_str = '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(
                self._values['year'],
                self._values['month'],
                self._values['day'],
                self._values['hour'],
                self._values['minute'],
                self._values['second'],
            )
            os.system('date -s "%s"' % date_str)
        except Exception:
            pass

        # Send to GD32 RTC (best-effort)
        try:
            import hmi_driver
            hmi_driver._set_com('TIME:%s' % date_str)
        except Exception:
            pass

        # Show success toast
        if hasattr(self, '_toast'):
            self._toast.show(resources.get_str('time_syncok'))

        # Return to display mode
        self._state = self.STATE_DISPLAY
        self.setLeftButton(resources.get_str('edit'))
        self.setRightButton(resources.get_str('edit'))
        self._drawTimeFields()

    def _drawTimeFields(self):
        """Draw date/time editor via JsonRenderer time_editor content type.

        Ground truth (QEMU 20260405): 11 text items + 2 background boxes.
        All rendering delegated to JsonRenderer._render_time_editor.
        """
        if not hasattr(self, '_jr'):
            return

        v = self._values
        content = {
            'type': 'time_editor',
            'mode': self._state,
            'values': [v['year'], v['month'], v['day'],
                       v['hour'], v['minute'], v['second']],
            'cursor': self._cursor if self._state == self.STATE_EDIT else -1,
        }
        self._jr.render_content_only(content)

    # ------------------------------------------------------------------
    # Public accessors for testing
    # ------------------------------------------------------------------

    def get_state(self):
        """Return current state string."""
        return self._state

    def get_cursor(self):
        """Return current cursor field index."""
        return self._cursor

    def get_values(self):
        """Return dict of current field values."""
        return dict(self._values)

    def get_field_value(self, field):
        """Return value for a specific field name."""
        return self._values.get(field)


# ═══════════════════════════════════════════════════════════════════════
# LUAScriptCMDActivity
# ═══════════════════════════════════════════════════════════════════════

class LUAScriptCMDActivity(BaseActivity):
    """File list of .lua scripts, select to run via ConsolePrinterActivity.

    Shows a paginated ListView of .lua files from the scripts directory.
    Selecting a script launches ConsolePrinterActivity with
    'script run <filename>'.

    Binary source: activity_main.so LUAScriptCMDActivity
    Verified: QEMU screenshots, docs/UI_Mapping/14_lua_script/README.md

    Screen layout:
        Title: "LUA Script X/Y" (paginated)
        Content: ListView with .lua file names (5 per page)
        M1: "" (empty), M2: "" (empty)
        UP/DOWN: scroll, LEFT/RIGHT: page, OK/M2: run, PWR: exit

    Script directory: /mnt/upan/luascripts/ on real device
    """

    ACT_NAME = 'lua_script'

    # Default script directory (overridable for testing)
    SCRIPT_DIR = '/mnt/upan/luascripts'

    def onCreate(self, bundle):
        """Scan for .lua files and populate the ListView.

        Flow (from binary):
            1. setTitle("LUA Script")
            2. listLUAFiles() — enumerate .lua files
            3. Create BigTextListView (paginated) with file names
            4. If no files: show "No scripts found" toast
        """
        self.setTitle(resources.get_str('lua_script'))
        self.setLeftButton('')
        self.setRightButton('')  # was OK, fixed per HANDOVER.md

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._toast = Toast(canvas)

        # Enumerate .lua files
        self._scripts = self._listLUAFiles()

        if not self._scripts:
            self._toast.show(resources.get_str('no_scripts_found'))
            self._listview = None
            return

        # Create ListView for script selection
        from lib.widget import ListView
        self._listview = ListView(canvas)
        self._listview.setDisplayItemMax(5)
        self._listview.setItems(self._scripts)
        self._listview.setPageModeEnable(True)
        self._listview.show()

        # Update title with pagination
        self._updateTitle()

        # Register page change callback
        self._listview._on_page_change = lambda _pg: self._updateTitle()

    def onKeyEvent(self, key):
        """Handle file list navigation and script execution.

        From binary onKeyEvent:
            UP:       scroll up in list
            DOWN:     scroll down in list
            LEFT:     previous page (PageIndicator)
            RIGHT:    next page (PageIndicator)
            M2/OK:    runScriptTask() — execute selected script
            PWR:      finish() — exit to Main Menu
        """
        if key == KEY_UP:
            if self._listview:
                self._listview.prev()
                self._updateTitle()
        elif key == KEY_DOWN:
            if self._listview:
                self._listview.next()
                self._updateTitle()
        elif key == KEY_LEFT:
            if self._listview:
                page = self._listview.getPagePosition()
                if page > 0:
                    self._listview.goto_page(page - 1)
                    self._updateTitle()
        elif key == KEY_RIGHT:
            if self._listview:
                page = self._listview.getPagePosition()
                if page < self._listview.getPageCount() - 1:
                    self._listview.goto_page(page + 1)
                    self._updateTitle()
        elif key in (KEY_M2, KEY_OK):
            self._runScript()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()

    def _listLUAFiles(self):
        """Enumerate .lua files from the scripts directory.

        Returns a sorted list of filenames without extension.
        Filter: only files ending with .lua.
        """
        script_dir = self.SCRIPT_DIR
        files = []
        try:
            for f in os.listdir(script_dir):
                if f.endswith('.lua'):
                    files.append(f[:-4])  # strip .lua extension
        except (OSError, FileNotFoundError):
            pass
        files.sort()
        return files

    def _runScript(self):
        """Launch ConsolePrinterActivity with 'script run <selected>'.

        From binary runScriptTask():
            1. Get selected filename from list
            2. Build PM3 command: "script run <scriptname>"
            3. Launch ConsolePrinterActivity with cmd
        """
        if not self._listview:
            return

        selected = self._listview.getSelection()
        if not selected:
            return

        cmd = 'script run %s' % selected
        bundle = {
            'cmd': cmd,
            'title': resources.get_str('lua_script'),
        }
        actstack.start_activity(ConsolePrinterActivity, bundle)

    def _updateTitle(self):
        """Update title with pagination: "LUA Script X/Y"."""
        if not self._listview:
            return
        page = self._listview.getPagePosition() + 1
        total = self._listview.getPageCount()
        if total > 1:
            self.setTitle('%s %d/%d' % (
                resources.get_str('lua_script'), page, total
            ))
        else:
            self.setTitle(resources.get_str('lua_script'))

    def get_scripts(self):
        """Return the list of discovered script names (for testing)."""
        return list(self._scripts) if hasattr(self, '_scripts') else []

    def get_listview(self):
        """Return the internal ListView (for testing)."""
        return self._listview if hasattr(self, '_listview') else None


# ═══════════════════════════════════════════════════════════════════════
# ReadListActivity
# ═══════════════════════════════════════════════════════════════════════

class ReadListActivity(BaseActivity):
    """Read Tag type selector. Shows 40 readable tag types across 8 pages.

    When the user selects a type, launches ReadActivity with that type.
    Also serves as the base pattern for CardWalletActivity (Dump Files).

    Binary source: activity_main.so ReadListActivity
    Verified: QEMU screenshots (Read Tag 1/8 .. 8/8), real device captures
    Spec: docs/UI_Mapping/04_read_tag/V1090_READ_UI_STATES.md
    Data: tools/read_list_map.json (40 readable types)

    Key behavior (from binary onKeyEvent):
        UP:     scroll up in type list
        DOWN:   scroll down in type list
        M2/OK:  launch ReadActivity with selected type
        M1:     finish() (back to main menu)
        PWR:    finish() (exit)

    Screen layout:
        Title: "Read Tag" with page indicator (e.g. "Read Tag 1/8")
        Content: ListView with 5 items per page, 8 pages total
        M1: "Back", M2: "Read"
    """

    ACT_NAME = 'read_list'

    # The 40 readable tag types in exact firmware order.
    # Source: tools/read_list_map.json (verified on real device 2026-03-25)
    READABLE_TYPES = [
        (1, 'M1 S50 1K 4B'),
        (42, 'M1 S50 1K 7B'),
        (0, 'M1 S70 4K 4B'),
        (41, 'M1 S70 4K 7B'),
        (25, 'M1 Mini'),
        (26, 'M1 Plus 2K'),
        (2, 'Ultralight'),
        (3, 'Ultralight C'),
        (4, 'Ultralight EV1'),
        (5, 'NTAG213 144b'),
        (6, 'NTAG215 504b'),
        (7, 'NTAG216 888b'),
        (19, 'ISO15693 ICODE'),
        (46, 'ISO15693 ST SA'),
        (20, 'Legic MIM256'),
        (21, 'Felica'),
        (17, 'iClass Legacy'),
        (18, 'iClass Elite'),
        (8, 'EM410x ID'),
        (9, 'HID Prox ID'),
        (10, 'Indala ID'),
        (11, 'AWID ID'),
        (12, 'IO Prox ID'),
        (13, 'GProx II ID'),
        (14, 'Securakey ID'),
        (15, 'Viking ID'),
        (16, 'Pyramid ID'),
        (28, 'FDXB ID'),
        (29, 'GALLAGHER ID'),
        (30, 'Jablotron ID'),
        (31, 'KERI ID'),
        (32, 'NEDAP ID'),
        (33, 'Noralsy ID'),
        (34, 'PAC ID'),
        (35, 'Paradox ID'),
        (36, 'Presco ID'),
        (37, 'Visa2000 ID'),
        (45, 'NexWatch ID'),
        (23, 'T5577'),
        (24, 'EM4305'),
    ]

    def __init__(self, bundle=None):
        self._listview = None
        self._tag_type_list = []
        self._type_ids = []
        self._last_launch_bundle = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, buttons, and tag type list.

        Flow (from binary onCreate):
            1. setTitle("Read Tag")
            2. Call initList() to populate tag types
            3. setLeftButton("Back"), setRightButton("Read")
            4. Create ListView with type names
        """
        self.setTitle(resources.get_str('read_tag'))
        # Ground truth: read_tag_list_1_8.png shows NO button bar.
        # The list occupies the full content area with no M1/M2 buttons.
        self.dismissButton()

        self._initList()

        canvas = self.getCanvas()
        if canvas is None:
            return

        from lib.widget import ListView
        self._listview = ListView(canvas)
        self._listview.setItems(self._tag_type_list)
        self._listview._on_page_change = self._onPageChange
        self._listview.show()

        # Update title with page indicator
        self._updateTitle()

    def _initList(self):
        """Populate the tag type list from READABLE_TYPES or tagtypes module.

        From binary initList():
            Calls tagtypes.getReadable() to get all readable type IDs,
            then tagtypes.getTypeName() for each to build display list.
            Falls back to hardcoded READABLE_TYPES if module unavailable.
        """
        try:
            import tagtypes
            readable = list(tagtypes.getReadable())
            for type_id in readable:
                name = tagtypes.getTypeName(type_id)
                self._type_ids.append(type_id)
                self._tag_type_list.append(name)
        except Exception:
            # Fallback: use hardcoded list from real device verification
            for type_id, name in self.READABLE_TYPES:
                self._type_ids.append(type_id)
                self._tag_type_list.append(name)

    def onKeyEvent(self, key):
        """Handle keys for tag type selection.

        From binary onKeyEvent:
            UP:     ListView.scrollUp()
            DOWN:   ListView.scrollDown()
            M2/OK:  _launchRead() with selected type
            M1:     finish() (back)
            PWR:    finish() (exit)
        """
        if key == KEY_UP:
            if self._listview is not None:
                self._listview.prev()
                self._updateTitle()
        elif key == KEY_DOWN:
            if self._listview is not None:
                self._listview.next()
                self._updateTitle()
        elif key == KEY_RIGHT:
            # Page forward in list (ground truth: read_mf1k_no_console_in_list
            # test expects RIGHT does page navigation, NOT console)
            if self._listview is not None:
                # Jump 5 items forward (one page)
                for _ in range(5):
                    self._listview.next()
                self._updateTitle()
        elif key == KEY_LEFT:
            # Page backward in list
            if self._listview is not None:
                for _ in range(5):
                    self._listview.prev()
                self._updateTitle()
        elif key in (KEY_M2, KEY_OK):
            self._launchRead()
        elif key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()

    def _launchRead(self):
        """Launch ReadActivity with the selected tag type.

        From binary how2Scan():
            1. Get selected index from ListView
            2. Map to type_id and type_name
            3. start_activity(ReadActivity, {'tag_type': type_id, 'tag_name': name})
        """
        if self._listview is None:
            return

        sel = self._listview.selection()
        if 0 <= sel < len(self._type_ids):
            type_id = self._type_ids[sel]
            type_name = self._tag_type_list[sel]
            bundle = {'tag_type': type_id, 'tag_name': type_name}
            self._last_launch_bundle = bundle
            # Import ReadActivity and push it onto the activity stack
            try:
                from lib.activity_read import ReadActivity
                actstack.start_activity(ReadActivity, bundle)
            except ImportError:
                # ReadActivity module unavailable -- bundle stored for testing
                pass

    def _onPageChange(self, page):
        """Callback from ListView when page changes -- update title."""
        self._updateTitle()

    def _updateTitle(self):
        """Update title bar with current page indicator.

        From binary/QEMU: title shows "Read Tag 1/8" format.
        Total pages = ceil(len(items) / items_per_page).
        """
        if self._listview is None:
            return
        total_items = len(self._tag_type_list)
        items_per_page = self._listview._max_display
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        current_page = (self._listview.selection() // items_per_page) + 1
        self.setTitle('{} {}/{}'.format(
            resources.get_str('read_tag'), current_page, total_pages))

    @property
    def tag_type_list(self):
        """Return the tag type name list (for testing)."""
        return list(self._tag_type_list)


# ═══════════════════════════════════════════════════════════════════════
# WipeTagActivity (Erase Tag)
# ═══════════════════════════════════════════════════════════════════════

class WipeTagActivity(BaseActivity):
    """Erase tag data -- 2-item type selection + scan + erase operation.

    Binary source: activity_main.so WipeTagActivity
    Spec: docs/UI_Mapping/13_erase_tag/README.md
    State table: docs/flows/erase/README.md lines 130-137
    Screenshots: docs/Real_Hardware_Intel/Screenshots/erase_tag_*.png

    States:
        TYPE_SELECT -- Choose erase method: MF1 or T5577
        SCANNING    -- ProgressBar "Scanning..." (MF1 only)
        ERASING     -- ProgressBar "ChkDIC" / "Erasing N%"
        SUCCESS     -- Toast "Erase successful", M1/M2="Erase"
        FAILED      -- Toast "Erase failed"/"Unknown error"/"No tag found"
        NO_KEYS     -- Toast "No valid keys...", M1/M2="Erase"

    Key behavior (state table lines 130-137):
        TYPE_SELECT:      M2/OK=startErase, M1/PWR=finish, UP/DOWN=scroll
        SCANNING/ERASING: PWR=cancel+finish
        SUCCESS/FAILED/NO_KEYS: M1/M2/OK=startErase (re-erase), PWR=finish
    """

    ACT_NAME = 'erase'

    # State constants
    STATE_TYPE_SELECT = 'type_select'
    STATE_SCANNING = 'scanning'
    STATE_ERASING = 'erasing'
    STATE_SUCCESS = 'success'
    STATE_FAILED = 'failed'
    STATE_NO_KEYS = 'no_keys'

    # Erase type indices
    ERASE_MF1 = 0
    ERASE_T5577 = 1

    def __init__(self, bundle=None):
        self._state = self.STATE_TYPE_SELECT
        self._listview = None
        self._toast = None
        self._progress = None
        self._selected_type = None
        self._writing_blocks = False  # True during block writes, False during fchk
        self._fake_timer = None       # Timer ID for fake progress animation
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, buttons, and 2-item erase type list.

        Ground truth (screenshot erase_tag_menu_1.png):
            Title: "Erase Tag"
            List: "1. Erase MF1/L1/L2/L3", "2. Erase T5577"
            M1="Back", M2="Erase"
        """
        self.setTitle(resources.get_str('wipe_tag'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('wipe'))

        canvas = self.getCanvas()
        if canvas is None:
            return

        self._toast = Toast(canvas)

        # ProgressBar for scanning/erasing phases
        # Ground truth (screenshots menu_2..5): bar at bottom of content area
        from lib.widget import ProgressBar
        self._progress = ProgressBar(canvas)

        from lib.widget import ListView
        self._listview = ListView(canvas)
        # Ground truth (screenshot menu_1): numbered items
        items = [
            '1. ' + resources.get_str('wipe_m1'),
            '2. ' + resources.get_str('wipe_t55xx'),
        ]
        self._listview.setItems(items)
        self._listview.show()

    def onKeyEvent(self, key):
        """State-dependent key dispatch.

        Ground truth: state table docs/flows/erase/README.md lines 130-137
        TYPE_SELECT: UP/DOWN scroll, M2/OK start, M1/PWR back
        SCANNING/ERASING: PWR cancel+finish
        SUCCESS/FAILED/NO_KEYS: M1/M2/OK re-erase, PWR finish
        """
        if self._state == self.STATE_TYPE_SELECT:
            if key == KEY_UP:
                if self._listview is not None:
                    self._listview.prev()
            elif key == KEY_DOWN:
                if self._listview is not None:
                    self._listview.next()
            elif key in (KEY_M2, KEY_OK):
                self._startErase()
            elif key in (KEY_M1, KEY_PWR):
                if key == KEY_PWR and self._handlePWR():
                    return
                self.finish()

        elif self._state == self.STATE_SCANNING:
            # PWR cancels scanning/fchk and exits
            if key == KEY_PWR:
                try:
                    import hmi_driver
                    hmi_driver.presspm3()
                except Exception:
                    pass
                try:
                    import executor
                    executor.stopPM3Task()
                except Exception:
                    pass
                self.finish()

        elif self._state == self.STATE_ERASING:
            if key == KEY_PWR and not self._writing_blocks:
                # Cancel fchk/key-check phase — safe to abort
                try:
                    import hmi_driver
                    hmi_driver.presspm3()
                except Exception:
                    pass
                try:
                    import executor
                    executor.stopPM3Task()
                except Exception:
                    pass
                self.finish()
            # else: PWR ignored during active block writes

        elif self._state in (self.STATE_SUCCESS, self.STATE_FAILED,
                             self.STATE_NO_KEYS):
            # M1/M2/OK: re-erase with saved type (state table)
            if key in (KEY_M1, KEY_M2, KEY_OK):
                self._startErase()
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()

    def _startErase(self):
        """Begin erase for selected type.

        Ground truth: screenshots menu_2 (Scanning), menu_3 (ChkDIC)
        MF1: SCANNING state with ProgressBar → detect → ERASING
        T5577: direct to ERASING with ProgressBar "Processing..."
        """
        if self._listview is None:
            return

        sel = self._listview.selection()
        self._selected_type = sel

        # Hide list and buttons
        if self._listview is not None:
            self._listview.hide()
        self.dismissButton()

        self.setbusy()

        # Clear any previous toast
        if self._toast is not None:
            self._toast.cancel()

        # Dispatch erase in background
        if sel == self.ERASE_MF1:
            self._state = self.STATE_SCANNING
            if self._progress is not None:
                self._progress.setMessage(
                    resources.get_str('scanning'))
                self._progress.setProgress(0)
                self._progress.show()
            self._eraseMF1()
        elif sel == self.ERASE_T5577:
            self._state = self.STATE_ERASING
            if self._progress is not None:
                self._progress.setMessage(
                    resources.get_str('processing'))
                self._progress.setProgress(0)
                self._progress.show()
            self._eraseT5577()

    def _start_fake_progress(self, ceiling=80):
        """Animate progress bar at ~1%/s until real callbacks arrive."""
        self._cancel_fake_progress()
        if actstack._root is None:
            return
        self._fake_pct = 0

        def _tick():
            if self._state not in (self.STATE_SCANNING, self.STATE_ERASING):
                self._fake_timer = None
                return
            if self._fake_pct < ceiling:
                self._fake_pct += 1
                if self._progress is not None:
                    self._progress.setProgress(self._fake_pct)
                self._fake_timer = actstack._root.after(1000, _tick)
            else:
                self._fake_timer = None
        self._fake_timer = actstack._root.after(1000, _tick)

    def _cancel_fake_progress(self):
        """Stop fake progress animation."""
        if self._fake_timer is not None:
            try:
                actstack._root.after_cancel(self._fake_timer)
            except Exception:
                pass
            self._fake_timer = None

    def _eraseMF1(self):
        """Erase MF1 tag — scan then erase with progress.

        Middleware: src/middleware/erase.py (detect_mf1_tag, erase_mf1_detected)
        """
        def _do_erase():
            try:
                import erase as _erase

                # Phase 1: Detect tag (SCANNING state)
                detect_result = _erase.detect_mf1_tag()
                if detect_result == 'no_tag':
                    self._onEraseResult('no_tag')
                    return

                # Phase 2: Erase (transition to ERASING)
                self._state = self.STATE_ERASING
                is_gen1a = detect_result['is_gen1a']

                if is_gen1a:
                    # Gen1a: no progress callbacks from erase middleware.
                    # Show formatting label and fake progress animation.
                    if self._progress is not None:
                        self._progress.setMessage(
                            resources.get_str('wipe_block'))
                    self._start_fake_progress(ceiling=80)

                def _on_progress(phase, current, total):
                    if self._progress is None:
                        return
                    if phase == 'chkdic':
                        self._writing_blocks = False
                        self._progress.setMessage('ChkDIC')
                        # Fake progress during key check (fchk wait)
                        self._start_fake_progress(ceiling=60)
                    elif phase == 'erasing':
                        self._writing_blocks = True
                        # Real block progress — cancel fake animation
                        self._cancel_fake_progress()
                        pct = (current * 100) // total if total else 0
                        self._progress.setMessage(
                            '%s %d%%' % (
                                resources.get_str('wipe_block'), pct))
                        self._progress.setProgress(pct)

                result = _erase.erase_mf1_detected(
                    detect_result['info_cache'],
                    is_gen1a,
                    on_progress=_on_progress,
                )
                self._cancel_fake_progress()
                self._onEraseResult(result)
            except Exception as e:
                print('[ERASE] MF1 error: %s' % e, flush=True)
                self._cancel_fake_progress()
                self._onEraseResult('error')

        self.startBGTask(_do_erase)

    def _eraseT5577(self):
        """Erase T5577 tag — delegates to middleware erase module.

        Middleware: src/middleware/erase.py (erase_t5577)
        """
        def _do_erase():
            try:
                import erase as _erase
                result = _erase.erase_t5577()
                self._onEraseResult(result)
            except Exception as e:
                print('[ERASE] T5577 error: %s' % e, flush=True)
                self._onEraseResult('failed')

        self.startBGTask(_do_erase)

    def _cancelErase(self):
        """Cancel in-progress erase operation."""
        self._cancel_fake_progress()
        self.setidle()
        try:
            import executor
            executor.stopPM3Task()
        except Exception:
            pass

    def _onEraseResult(self, result):
        """Handle erase completion -- show toast, restore buttons.

        Args:
            result: 'success', 'no_keys', 'no_tag', 'error', or 'failed'

        Ground truth (screenshots menu_6, unknown_error):
            Result screens show M1="Erase", M2="Erase" buttons.
            State table: M1/M2/OK re-erase, PWR exits.
        """
        self.setidle()

        # Hide progress bar
        if self._progress is not None:
            self._progress.hide()

        # Show result toast
        if result == 'success':
            self._state = self.STATE_SUCCESS
            if self._toast is not None:
                self._toast.show(
                    resources.get_str('wipe_success'),
                    mode=Toast.MASK_CENTER,
                    icon='check',
                    duration_ms=0,
                )
        elif result == 'no_keys':
            self._state = self.STATE_NO_KEYS
            if self._toast is not None:
                self._toast.show(
                    resources.get_str('wipe_no_valid_keys'),
                    mode=Toast.MASK_CENTER,
                    icon='error',
                    duration_ms=0,
                )
        elif result == 'no_tag':
            self._state = self.STATE_FAILED
            if self._toast is not None:
                self._toast.show(
                    resources.get_str('no_tag_found'),
                    mode=Toast.MASK_CENTER,
                    icon='error',
                    duration_ms=0,
                )
        elif result == 'error':
            self._state = self.STATE_FAILED
            if self._toast is not None:
                self._toast.show(
                    resources.get_str('err_at_wiping'),
                    mode=Toast.MASK_CENTER,
                    icon='error',
                    duration_ms=0,
                )
        else:
            self._state = self.STATE_FAILED
            if self._toast is not None:
                self._toast.show(
                    resources.get_str('wipe_failed'),
                    mode=Toast.MASK_CENTER,
                    icon='error',
                    duration_ms=0,
                )

        # Restore buttons: M1="Erase", M2="Erase"
        # Ground truth: screenshots menu_6, unknown_error
        self.setLeftButton(resources.get_str('wipe'))
        self.setRightButton(resources.get_str('wipe'))

    @property
    def state(self):
        """Current state (for testing)."""
        return self._state


# ═══════════════════════════════════════════════════════════════════════
# SniffActivity
# ═══════════════════════════════════════════════════════════════════════

class SniffActivity(BaseActivity):
    """RF sniff/trace capture -- 5 sniff protocol types.

    Shows a 5-item list of sniff types. User selects one, starts sniff,
    views results after stop. Results can be saved to file.

    Binary source: activity_main.so SniffActivity (19 methods)
    Spec: docs/UI_Mapping/05_sniff/V1090_SNIFF_FLOW_COMPLETE.md
    Verified: QEMU screenshots ("Sniff TRF 1/1" with 5 items)

    5 sniff types (from sniff.so binary):
        0: "1. 14A Sniff"    -> hf 14a sniff  -> hf 14a list
        1: "2. 14B Sniff"    -> hf 14b sniff  -> hf list 14b
        2: "3. iclass Sniff" -> hf iclass sniff -> hf list iclass
        3: "4. Topaz Sniff"  -> hf topaz sniff  -> hf list topaz
        4: "5. T5577 Sniff"  -> lf sniff        -> (auto on 125k_sniff_finished)

    States:
        TYPE_SELECT  -- 5-item list, no softkey labels
        INSTRUCTION  -- 4-step guide (HF) or 1-step (T5577), M1="Start" M2="Finish"
        SNIFFING     -- Sniff in progress, M1="Start" M2="Finish", toast overlay
        RESULT       -- Decoded trace, M1="Start" M2="Save"

    Key behavior (from binary onKeyEvent + QEMU-verified + screenshots):
        TYPE_SELECT:
            UP/DOWN: scroll list
            M2/OK:  setupOnTypeSelected() -> showInstruction()
            M1/PWR: finish()
        INSTRUCTION:
            UP/DOWN: navigate instruction pages
            M1:     startSniff()
            PWR:    back to TYPE_SELECT
        SNIFFING:
            M2:     stopSniff() -> showResult()
            M1:     stopSniff() -> finish()
            PWR:    stopSniff() -> back to TYPE_SELECT
        RESULT:
            UP/DOWN: scroll results
            M1:     restart sniff
            M2/OK:  saveSniffData()
            PWR:    back to TYPE_SELECT
    """

    ACT_NAME = 'sniff'

    # State constants
    STATE_TYPE_SELECT = 'type_select'
    STATE_INSTRUCTION = 'instruction'
    STATE_SNIFFING = 'sniffing'
    STATE_RESULT = 'result'

    # Sniff type definitions: (resource_key, pm3_start_cmd, pm3_list_cmd, type_id)
    # Ground truth: trace_sniff_flow_20260403.txt — real device PM3 commands
    SNIFF_TYPES = [
        ('sniff_item1', 'hf 14a sniff', 'hf mf list', '14a'),        # iceman: hf mf list (factory was: hf list mf)
        ('sniff_item2', 'hf 14b sniff', 'hf 14b list', '14b'),       # iceman: hf 14b list
        ('sniff_item3', 'hf iclass sniff', 'hf iclass list', 'iclass'),
        ('sniff_item4', 'hf topaz sniff', 'hf topaz list', 'topaz'),
        ('sniff_item5', 'lf t55xx sniff', None, '125k'),
    ]

    # Instruction pages for HF types (Steps 1-4)
    # Ground truth: sniff_trf_1_4_1.png through sniff_trf_4_4.png
    _HF_INSTRUCTIONS = ['sniffline1', 'sniffline2', 'sniffline3', 'sniffline4']
    # Single instruction page for T5577
    _T5577_INSTRUCTIONS = ['sniffline_t5577']

    def __init__(self, bundle=None):
        self._state = self.STATE_TYPE_SELECT
        self._listview = None
        self._toast = None
        self._btlv = None
        self._sniffing = False
        self._trace_len = 0
        self._trace_len_known = False
        self._selected_index = 0
        self._selected_type_id = None
        self._result_data = []
        self._result_page = 0
        self._instruction_pages = []
        self._instruction_page = 0
        self._decode_pb = None
        self._decode_count = 0
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, buttons, and 5-item sniff type list.

        Flow (from binary onCreate):
            1. setTitle("Sniff TRF 1/1")
            2. Build 5-item ListView from sniff_item1..5
            3. M1="Back", M2="Start"
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        self._toast = Toast(canvas)

        # Build sniff type items from resources
        items = []
        for res_key, _, _, _ in self.SNIFF_TYPES:
            items.append(resources.get_str(res_key))

        from lib.widget import ListView
        self._listview = ListView(canvas)
        self._listview.setItems(items)
        self._listview.show()

        self._updateSniffTitle()
        self.setLeftButton('')  # no labels in TYPE_SELECT
        self.setRightButton('')  # no labels in TYPE_SELECT

    def onKeyEvent(self, key):
        """State-dependent key dispatch.

        See class docstring for full key mapping per state.
        """
        if self._state == self.STATE_TYPE_SELECT:
            self._onKeyTypeSelect(key)
        elif self._state == self.STATE_INSTRUCTION:
            self._onKeyInstruction(key)
        elif self._state == self.STATE_SNIFFING:
            self._onKeySniffing(key)
        elif self._state == self.STATE_RESULT:
            self._onKeyResult(key)

    def _updateSniffTitle(self):
        """Update title with page indicator for type list."""
        if self._listview is not None:
            import math
            total_items = len(self.SNIFF_TYPES)
            ipp = self._listview._max_display
            total_pages = max(1, math.ceil(total_items / ipp))
            current_page = (self._listview.selection() // ipp) + 1
            self.setTitle('{} {}/{}'.format(
                resources.get_str('sniff_notag'), current_page, total_pages))
        else:
            self.setTitle('{} 1/1'.format(resources.get_str('sniff_notag')))

    def _onKeyTypeSelect(self, key):
        """Handle keys in TYPE_SELECT state.

        Ground truth: sniff_common.sh — OK selects type → shows instruction screen.
        """
        if key == KEY_UP:
            if self._listview is not None:
                self._listview.prev()
                self._updateSniffTitle()
        elif key == KEY_DOWN:
            if self._listview is not None:
                self._listview.next()
                self._updateSniffTitle()
        elif key in (KEY_M2, KEY_OK):
            self._setupOnTypeSelected()
            self._showInstruction()
        elif key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()

    def _onKeyInstruction(self, key):
        """Handle keys in INSTRUCTION state.

        Ground truth: sniff_trf_1_4_1.png — M1="Start", M2="Finish"
        sniff_common.sh line 161: M1 triggers startSniff()
        UP/DOWN navigate instruction pages (4 for HF, 1 for T5577)
        PWR: back to TYPE_SELECT
        """
        if key == KEY_UP:
            if self._instruction_page > 0:
                self._instruction_page -= 1
                self._renderInstructionPage()
        elif key == KEY_DOWN:
            if self._instruction_page < len(self._instruction_pages) - 1:
                self._instruction_page += 1
                self._renderInstructionPage()
        elif key == KEY_M1:
            # M1 = "Start" → begin sniffing
            self._startSniff()
        elif key == KEY_M2:
            # M2 = "Finish" — dimmed during instruction, but still handled
            # Ground truth: sniff_trf_1_4_1.png shows "Finish" dimmed
            pass
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._backToTypeSelect()

    def _showInstruction(self):
        """Show instruction screen after type selection.

        Ground truth: sniff_trf_1_4_1.png through sniff_trf_4_4.png
        Title: "Sniff TRF N/4" (HF) or "Sniff TRF 1/1" (T5577)
        Content: Step-by-step sniff instructions
        Buttons: M1="Start", M2="Finish"
        """
        self._state = self.STATE_INSTRUCTION

        # Determine instruction pages based on type
        if self._selected_type_id == '125k':
            self._instruction_pages = self._T5577_INSTRUCTIONS
        else:
            self._instruction_pages = self._HF_INSTRUCTIONS
        self._instruction_page = 0

        # Hide type list
        if self._listview is not None:
            self._listview.hide()

        # Set buttons: M1="Start" (active), M2="Finish" (INACTIVE)
        # Ground truth: FB capture sniff_14a_instruction_step1.png — Finish is dimmed
        self.setLeftButton(resources.get_str('start'), active=True)
        self.setRightButton(resources.get_str('finish'), active=False)

        # Render first instruction page
        self._renderInstructionPage()

    def _renderInstructionPage(self):
        """Render current instruction page with page indicator.

        Ground truth: sniff_trf_1_4_1.png title "Sniff TRF 1/4"
        """
        total = len(self._instruction_pages)
        current = self._instruction_page + 1
        self.setTitle('{} {}/{}'.format(
            resources.get_str('sniff_notag'), current, total))

        # Render instruction text
        canvas = self.getCanvas()
        if canvas is None:
            return
        if self._btlv is not None:
            self._btlv.hide()
        from lib.widget import BigTextListView
        self._btlv = BigTextListView(canvas)
        res_key = self._instruction_pages[self._instruction_page]
        self._btlv.drawStr(resources.get_str(res_key))

        # Page arrows in button bar — only when multiple instruction pages
        # Ground truth: FB state_006 (1/4) has ▼▲, state_039 (1/1) has none
        self.setButtonArrows(self._instruction_page, total)

    def _onKeySniffing(self, key):
        """Handle keys in SNIFFING state.

        M2 = stop sniff + show result (HF types only in practice —
        T5577 auto-finishes via onData before M2 can be pressed).
        Ground truth: trace_sniff_t5577_enhanced_20260404.txt — T5577 blocks
        until PM3 completes (timeout=-1), so M2 is never pressed during T5577.
        """
        if key == KEY_M2:
            self._stopSniff()
            self._showResult()
        elif key == KEY_M1:
            self._stopSniff()
            self.finish()
        elif key == KEY_PWR:
            # PWR = stop sniff + back to type select
            # Ground truth: sniff.json — PWR = "run:stopAndBack"
            # Do NOT use _handlePWR here: it would swallow PWR due to
            # the persistent toast + busy flag, blocking the user.
            self._stopSniff()
            self._backToTypeSelect()

    def _onKeyResult(self, key):
        """Handle keys in RESULT state.

        Ground truth: sniff_trf_1_4_2.png — M1="Start", M2="Save"
        UI Mapping: M1=restart sniff, M2/OK=save, UP/DOWN=scroll, PWR=back
        """
        if key == KEY_UP:
            self._prevIfShowing()
        elif key == KEY_DOWN:
            self._nextIfShowing()
        elif key == KEY_M1:
            # M1 = "Start" → restart sniffing
            self._startSniff()
        elif key in (KEY_M2, KEY_OK):
            self._saveSniffData()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._backToTypeSelect()

    def _setupOnTypeSelected(self):
        """Configure sniff mode from list selection (0-4).

        Sets _selected_index and _selected_type_id from the list.
        """
        if self._listview is not None:
            self._selected_index = self._listview.selection()
        if 0 <= self._selected_index < len(self.SNIFF_TYPES):
            self._selected_type_id = self.SNIFF_TYPES[self._selected_index][3]

    def _startSniff(self):
        """Start sniff capture for the selected type.

        From binary startSniff():
            1. Hide instruction text (if showing)
            2. Show "Sniffing in progress..." toast
            3. Dispatch PM3 sniff command
            4. Set state to SNIFFING

        Ground truth: sniff_trf_sniffing.png — toast overlays instruction text,
        M1="Start", M2="Finish", title keeps instruction page indicator.
        """
        self._state = self.STATE_SNIFFING
        self._sniffing = True
        self.setbusy()
        self._trace_len = 0
        self._trace_len_known = False
        self._result_data = []
        self._result_page = 0

        # Clear instruction page arrows
        self.clearButtonArrows()

        # Buttons: M1="Start" (INACTIVE), M2="Finish" (active)
        # Ground truth: FB capture — Start dimmed during sniff, Finish bold
        self.setLeftButton(resources.get_str('start'), active=False)
        self.setRightButton(resources.get_str('finish'), active=True)

        # Show sniffing toast — persistent until Stop/Finish is pressed.
        # Ground truth: sniff.json state "sniffing" has "timeout: 0" (persistent).
        if self._toast is not None:
            self._toast.show(resources.get_str('sniffing'), duration_ms=0)

        # Dispatch PM3 command in background
        if 0 <= self._selected_index < len(self.SNIFF_TYPES):
            _, pm3_cmd, _, _ = self.SNIFF_TYPES[self._selected_index]
            self._dispatchSniffCommand(pm3_cmd)

    def _dispatchSniffCommand(self, cmd):
        """Dispatch sniff via sniff.so module functions.

        Ground truth: trace_sniff_flow_20260403.txt
        sniff.so handles ALL PM3 commands internally:
        - sniff14AStart() sends hf 14a sniff (timeout=8000)
        - sniff125KStart() sends lf config + lf t55xx sniff
        - etc.

        Our Python does NOT send PM3 commands. sniff.so IS the logic.
        """
        def _do_sniff():
            try:
                import sniff as sniff_mod
                idx = self._selected_index
                if idx == 0:
                    sniff_mod.sniff14AStart()
                elif idx == 1:
                    sniff_mod.sniff14BStart()
                elif idx == 2:
                    sniff_mod.sniffIClassAStart()
                elif idx == 3:
                    sniff_mod.sniffTopazStart()
                elif idx == 4:
                    sniff_mod.sniffT5577Start()  # NOT sniff125KStart — trace_sniff_flow_20260403.txt
            except ImportError:
                pass  # sniff.so not available (test env) — no PM3 commands
            except Exception:
                pass

            # After .so function returns, check executor cache for data.
            # sniff.so normally calls onData() via callback, but under
            # QEMU the mock returns instantly. Check cache as fallback.
            try:
                import executor
                cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
                if cache and self._sniffing:
                    self.onData(cmd, cache)
            except Exception:
                pass

        self.startBGTask(_do_sniff)

    def _stopSniff(self):
        """Stop sniff capture.

        From binary stopSniff():
            1. presspm3 to physically stop PM3
            2. Stop PM3 task
            3. Clear sniffing flag

        Ground truth (trace_original_sniff_serial_20260412.txt lines 83.011-83.437):
            PRESSPM3> called → SERIAL_TX> b'presspm3' → PM3 stops cleanly
        """
        self._sniffing = False
        self.setidle()
        try:
            import hmi_driver
            hmi_driver.presspm3()
        except Exception:
            pass
        try:
            import executor
            executor.stopPM3Task()
        except Exception:
            pass

    def _showResult(self):
        """Stop sniff and display trace results.

        Ground truth:
            trace_sniff_enhanced_20260404.txt:
                HF: hf list mf (timeout=-1, listener=YES(method)), 47 listener calls
                T5577: lf t55xx sniff (listener=None), no parse command
            FB captures sniff_20260403:
                Decoding: "TraceLen: 9945" + "Decoding... 288/9945" + blue ProgressBar
                Result: "TraceLen: 9945" + "UID: 2CADC272" + "Key1: FFFFFFFFFFFF"
            Ghidra analysis (sniff_ghidra_raw.txt line 4548):
                parserHfTraceLen() takes ZERO args — reads executor cache internally
            Original .so QEMU (TEST_TARGET=original):
                State 5: content includes 'Decoding...\\n0/9945', 'UID: 2CADC272', 'Key1: FFFFFFFFFFFF'

        Architecture:
            HF: show Decoding with ProgressBar → startPM3Task(list_cmd, -1, listener)
                → listener updates progress → _finishHfResult renders parsed data
            T5577: data in cache from sniff → parsers read cache → render
        """
        self._state = self.STATE_RESULT
        self._result_page = 0

        # Dismiss sniffing toast
        if self._toast is not None:
            self._toast.cancel()

        # Clear instruction text
        if self._btlv is not None:
            self._btlv.hide()
            self._btlv = None

        if 0 <= self._selected_index < len(self.SNIFF_TYPES):
            _, _, list_cmd, type_id = self.SNIFF_TYPES[self._selected_index]

            if type_id == '125k':
                # T5577: no listener, no parse command — data in cache
                # Ground truth: trace_sniff_t5577_enhanced_20260404.txt — listener=None
                self._showT5577Result()
                return

            # HF types: show Decoding + ProgressBar, issue parse with listener
            # Ground truth: trace_sniff_enhanced_20260404.txt line 8:
            #   PM3> hf list mf (timeout=-1, listener=YES(method))
            # Ground truth: FB sniff_14a_decoding_288_of_9945.png:
            #   "TraceLen: 9945" top, "Decoding... 288/9945" blue, blue ProgressBar
            if list_cmd is not None:
                self._hf_list_cmd = list_cmd
                self._decode_count = 0
                self._decode_pb = None

                # Remove button bar entirely during parse
                # Ground truth: FB states 014-029 have NO button bar at all
                self.dismissButton()

                # Decoding display created lazily in listener callbacks.
                # Ground truth (QEMU canvas trace):
                #   Empty/failed trace: zero trace data lines → zero callbacks
                #     with trace data → no Decoding created → straight to result
                #   Data trace: listener fires per trace line → creates Decoding
                #     on first trace data line, updates on subsequent lines
                # Decoding items persist until _finishHfResult cleans them up.
                _DECODE_TAG = 'sniff_decode_display'
                # Legacy: "trace len = 1066", Iceman: "Recorded activity ( 1066 bytes )"
                _re_trace_len = __import__('re').compile(r'(?:trace len = |Recorded activity \( )(\d+)')
                _decode_created = [False]

                def _do_hf_parse():
                    def _on_decode_line(line):
                        line_str = str(line)
                        # Extract trace_len from early lines
                        if not self._trace_len:
                            m = _re_trace_len.search(line_str)
                            if m:
                                self._trace_len = int(m.group(1))

                        # Only count actual trace data lines (with | separators)
                        if '|' not in line_str:
                            return
                        self._decode_count += 1

                        # Schedule ALL canvas ops on Tk thread (thread safety).
                        # Callback fires from bg thread — direct canvas ops crash.
                        count = self._decode_count
                        tlen = self._trace_len
                        def _update_ui():
                            try:
                                if self._state != self.STATE_RESULT:
                                    return
                                canvas = self.getCanvas()
                                if canvas is None:
                                    return
                                # Progress bar at bottom of screen (default position,
                                # same as Read/Scan flows: y=210)
                                if not _decode_created[0]:
                                    _decode_created[0] = True
                                    from lib.widget import ProgressBar
                                    self._decode_pb = ProgressBar(
                                        canvas, max_v=max(1, tlen))
                                    self._decode_pb.show()
                                    self._decode_tl_id = canvas.create_text(
                                        SCREEN_W // 2, 68,
                                        text=resources.get_str('sniff_trace').format(tlen),
                                        fill=NORMAL_TEXT_COLOR,
                                        font=resources.get_font(13),
                                        anchor='center', tags=_DECODE_TAG)
                                    self._decode_txt_id = canvas.create_text(
                                        SCREEN_W // 2, 206,
                                        text=resources.get_str('sniff_decode').format(count, tlen),
                                        fill=COLOR_ACCENT,
                                        font=resources.get_font(13),
                                        anchor='s', tags=_DECODE_TAG)
                                else:
                                    if hasattr(self, '_decode_tl_id'):
                                        canvas.itemconfigure(self._decode_tl_id,
                                            text=resources.get_str('sniff_trace').format(tlen))
                                    if hasattr(self, '_decode_txt_id'):
                                        canvas.itemconfigure(self._decode_txt_id,
                                            text=resources.get_str('sniff_decode').format(count, tlen))
                                if self._decode_pb is not None:
                                    self._decode_pb.setProgress(count)
                            except Exception:
                                pass
                        if actstack._root is not None:
                            actstack._root.after(0, _update_ui)

                    try:
                        import executor
                        executor.startPM3Task(self._hf_list_cmd, -1, _on_decode_line)
                    except Exception:
                        pass

                    # Guard: only render result if we're still the active activity
                    if self._state == self.STATE_RESULT:
                        if actstack._root is not None:
                            actstack._root.after(0, self._finishHfResult)
                        else:
                            self._finishHfResult()

                self.startBGTask(_do_hf_parse)
                return

    def _finishHfResult(self):
        """Render final HF result after parse command completes.

        Ground truth (QEMU canvas trace):
            Empty trace: 'TraceLen: 0' at (120,120) centered — single item
            Data trace:  'TraceLen: 2298' at (19,60), 'UID: 8D2D6F67' at (19,100),
                         '  Key1: FFFFFFFFFFFF' at (19,140) — left-aligned, 40px spacing
        """
        # Clean up Decoding display and ProgressBar before rendering result.
        # Ground truth: FB captures show clean result screens (no Decoding bleed).
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.delete('sniff_decode_display')
        if self._decode_pb is not None:
            self._decode_pb.hide()
            self._decode_pb = None

        # Call sniff.so parsers — read executor cache internally
        trace_len = self._trace_len
        display_lines = []

        try:
            import sniff as sniff_mod
            tl = sniff_mod.parserHfTraceLen()
            if tl is not None:
                trace_len = int(tl)
                self._trace_len = trace_len
        except Exception:
            pass

        display_lines.append(resources.get_str('sniff_trace').format(trace_len))

        # Parse UID/CSN and keys — parserKeyForM1() returns dict {uid: [keys]}
        # Protocol-aware label: iClass uses "CSN:", others use "UID:"
        uid_label = 'CSN' if self._selected_type_id == 'iclass' else 'UID'
        try:
            import sniff as sniff_mod
            key_data = sniff_mod.parserKeyForM1()
            if key_data and isinstance(key_data, dict):
                for uid, keys in key_data.items():
                    display_lines.append('%s: %s' % (uid_label, uid))
                    if isinstance(keys, (list, tuple)):
                        for i, k in enumerate(keys):
                            display_lines.append('  Key%d: %s' % (i + 1, k))
        except Exception:
            pass

        # Buttons
        self.setLeftButton(resources.get_str('start'), active=True)
        self.setRightButton(resources.get_str('save'), active=(trace_len > 0))

        # Render result
        # Rules:
        #   1. "TraceLen: X" always horizontally centered
        #   2. TraceLen > 0 with no data (no UID/Keys): V+H centered
        #   3. TraceLen = 0: V+H centered (QEMU trace: xy=(120,120))
        #   4. TraceLen > 0 with data: TraceLen centered at top,
        #      data lines left-aligned at x=19, y=100+ with 40px spacing
        #      (QEMU trace: UID at (19,100), Key at (19,140))
        canvas = self.getCanvas()
        if canvas is not None:
            self._result_tag = 'sniff_result_text'
            canvas.delete(self._result_tag)

            has_data = len(display_lines) > 1  # more than just TraceLen

            if not has_data:
                # TraceLen only (empty, failed, or no keys): V+H centered
                canvas.create_text(
                    SCREEN_W // 2, CONTENT_Y0 + CONTENT_H // 2,
                    text=display_lines[0],
                    fill=NORMAL_TEXT_COLOR,
                    font=resources.get_font(13),
                    anchor='center',
                    tags=self._result_tag,
                )
            else:
                # TraceLen centered at top, data left-aligned below
                # QEMU trace: TraceLen at (120,68), UID at (19,100), Key at (19,140)
                canvas.create_text(
                    SCREEN_W // 2, 68,
                    text=display_lines[0],
                    fill=NORMAL_TEXT_COLOR,
                    font=resources.get_font(13),
                    anchor='center',
                    tags=self._result_tag,
                )
                y = 100
                for line in display_lines[1:]:
                    canvas.create_text(
                        19, y,
                        text=line,
                        fill=NORMAL_TEXT_COLOR,
                        font=resources.get_font(13),
                        anchor='nw',
                        tags=self._result_tag,
                    )
                    y += 40

    def _showT5577Result(self):
        """Display T5577 sniff results.

        Ground truth:
            trace_sniff_t5577_enhanced_20260404.txt: listener=None, no parse command
            FB sniff_t5577_result_tracelen_42259.png: "TraceLen: 42259"
            V1090_MODULE_AUDIT.txt line 159: parserLfTraceLen reads 'Reading (\\d+) bytes'
            V1090_MODULE_AUDIT.txt line 166: parserKeysForT5577(parser_fun) takes a parser function
        """
        display_lines = []

        # Restore cache before calling parsers — stopPM3Task may clear it
        # Ground truth: executor_strings.txt shows stopPM3Task references CONTENT_OUT_IN__TXT_CACHE
        # Try current cache first; if empty, use saved cache from onData
        try:
            import executor
            current_cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            saved_cache = getattr(self, '_t5577_cache', '')
            if not current_cache and saved_cache:
                executor.CONTENT_OUT_IN__TXT_CACHE = saved_cache
            elif current_cache and not saved_cache:
                # Cache still valid (M2 pressed before stopPM3Task cleared it)
                pass
        except Exception:
            pass

        # Parse trace length — 0 args, reads cache internally
        # Looks for: "Reading (\d+) bytes from device memory"
        trace_len = 0
        try:
            import sniff as sniff_mod
            tl = sniff_mod.parserLfTraceLen()
            if tl is not None and int(tl) > 0:
                trace_len = int(tl)
                self._trace_len = trace_len
        except Exception:
            pass

        display_lines.append(resources.get_str('sniff_trace').format(trace_len))

        # Parse T5577 keys — takes a parser function as argument
        # Ground truth (QEMU probe):
        #   parserKeysForT5577(parserT5577OkKeyForLine) => ['20206666', '20206666', ...]
        #   Returns list of raw hex strings. Activity formats as "  Key{n}: {hex} √"
        #   Original .so QEMU state: '  Key1: 20206666 √', '  Key2: 20206666 √', etc.
        # Ground truth (QEMU cross-target comparison):
        #   Original only displays keys from "Default pwd write" lines
        #   (parserT5577OkKeyForLine). "Default write" (no pwd) lines are
        #   NOT displayed by the original showT5577Result.
        try:
            import sniff as sniff_mod
            keys = sniff_mod.parserKeysForT5577(sniff_mod.parserT5577OkKeyForLine)
            if keys and isinstance(keys, (list, tuple)):
                for i, k in enumerate(keys):
                    display_lines.append('  Key%d: %s \u221a' % (i + 1, k))
        except Exception:
            pass

        # Buttons: M1="Start" (active), M2="Save" (active only if data)
        # Ground truth: FB state_059 — Save dimmed for empty trace
        self.setLeftButton(resources.get_str('start'), active=True)
        self.setRightButton(resources.get_str('save'), active=(trace_len > 0))

        # Title: keep instruction page indicator (e.g. "Sniff TRF 1/1" for T5577)
        # Ground truth: FB state_042 shows "Sniff TRF 1/1" — unchanged from instruction
        # Title was set in _renderInstructionPage and is NOT changed here.

        # Render — same rules as HF result:
        #   TraceLen always horizontally centered
        #   TraceLen-only (no keys): V+H centered
        #   With keys: TraceLen centered at top, keys left-aligned below
        canvas = self.getCanvas()
        if canvas is not None:
            self._result_tag = 'sniff_result_text'
            canvas.delete(self._result_tag)
            has_data = len(display_lines) > 1

            if not has_data:
                canvas.create_text(
                    SCREEN_W // 2, CONTENT_Y0 + CONTENT_H // 2,
                    text=display_lines[0],
                    fill=NORMAL_TEXT_COLOR,
                    font=resources.get_font(13),
                    anchor='center',
                    tags=self._result_tag,
                )
            else:
                canvas.create_text(
                    SCREEN_W // 2, 68,
                    text=display_lines[0],
                    fill=NORMAL_TEXT_COLOR,
                    font=resources.get_font(13),
                    anchor='center',
                    tags=self._result_tag,
                )
                y = 100
                for line in display_lines[1:]:
                    canvas.create_text(
                        19, y,
                        text=line,
                        fill=NORMAL_TEXT_COLOR,
                        font=resources.get_font(13),
                        anchor='nw',
                        tags=self._result_tag,
                    )
                    y += 40

    def _backToTypeSelect(self):
        """Return to TYPE_SELECT state.

        Restores the type list, resets buttons and title.
        Ground truth: sniff_trf_list_1_1.png — no softkey labels in TYPE_SELECT
        """
        self._state = self.STATE_TYPE_SELECT
        self._sniffing = False
        self._instruction_pages = []
        self._instruction_page = 0

        # Clear instruction/result/decoding display
        if self._btlv is not None:
            self._btlv.hide()
            self._btlv = None
        canvas = self.getCanvas()
        if canvas is not None:
            if hasattr(self, '_result_tag'):
                canvas.delete(self._result_tag)
            canvas.delete('sniff_decode_display')
        if self._decode_pb is not None:
            self._decode_pb.hide()
            self._decode_pb = None
        self.clearButtonArrows()

        # Dismiss toast
        if self._toast is not None:
            self._toast.cancel()

        # Restore list
        canvas = self.getCanvas()
        if canvas is not None and self._listview is not None:
            self._listview.show()

        # Restore title and remove button bar entirely
        # TYPE_SELECT has no button labels AND no button bar background.
        # dismissButton() removes text + TAG_BTN_BG + resets _is_button_inited.
        self._updateSniffTitle()
        self.dismissButton()

    def _saveSniffData(self):
        """Save trace data to file.

        Ground truth:
            FB state_031: "Processing..." toast (14A save)
            FB state_032: "Trace file saved" toast (14A save)
            FB state_034: M2="Save" dimmed after save
            SimulationTraceActivity._saveSniffData (line 5592): same pattern
            activity_main_strings.txt line 21479: text_processing referenced
        """
        # Show "Processing..." toast before save
        # Ground truth: FB states 031, 043 — "Processing..." appears first
        if self._toast is not None:
            self._toast.show(resources.get_str('processing'), duration_ms=0)

        # Save trace data to /mnt/upan/trace/{type}_{N}.txt
        # Ground truth (QEMU file trace): original .so writes executor cache
        # to /mnt/upan/trace/ with auto-incrementing sequence numbers.
        # File naming: 14a_1.txt, 14b_1.txt, iclass_1.txt, topaz_1.txt, t5577_1.txt
        try:
            import executor
            import os
            cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if cache.strip():
                trace_dir = '/mnt/upan/trace'
                os.makedirs(trace_dir, exist_ok=True)
                # Map type_id to filename prefix
                type_prefix = {
                    '14a': '14a', '14b': '14b', 'iclass': 'iclass',
                    'topaz': 'topaz', '125k': 't5577',
                }.get(self._selected_type_id, 'unknown')
                # Find next sequence number
                existing = [f for f in os.listdir(trace_dir)
                            if f.startswith(type_prefix + '_') and f.endswith('.txt')]
                seq = len(existing) + 1
                fpath = os.path.join(trace_dir, '%s_%d.txt' % (type_prefix, seq))
                with open(fpath, 'w') as f:
                    f.write(cache)
        except Exception:
            pass

        # Show "Trace file saved" toast after save
        if self._toast is not None:
            self._toast.show(resources.get_str('trace_saved'))

        # M2="Save" becomes inactive after save
        # Ground truth: FB state_034, state_045 — Save dimmed post-save
        self.setRightButton(resources.get_str('save'), active=False)

    def _nextIfShowing(self):
        """Paginate forward through multi-page results."""
        if self._result_data:
            self._result_page += 1

    def _prevIfShowing(self):
        """Paginate backward through multi-page results."""
        if self._result_page > 0:
            self._result_page -= 1

    def onData(self, cmd, data):
        """PM3 data callback — parse trace length or T5577 auto-finish.

        Ground truth:
            trace_sniff_t5577_enhanced_20260404.txt: lf t55xx sniff (timeout=-1)
                blocks until PM3 completes, then returns with data in cache.
                T5577 always auto-finishes — no manual M2 stop.
            activity_main_strings.txt line 21264: t5577_sniff_finished (resource toast)

        For T5577: sniffT5577Start() blocks until PM3 completes. When the
        background thread returns, _dispatchSniffCommand calls onData with
        the cache. We detect T5577 data (Reading N bytes) and auto-stop.

        For HF: parserTraceLen reads executor cache for trace length.
        """
        if data and self._selected_type_id == '125k':
            # T5577 auto-finish: sniffT5577Start() returned with data
            # Save cache before stopSniff clears it
            self._t5577_cache = str(data)
            self._stopSniff()
            self._showResult()
            return

        # HF: parse trace length — parserTraceLen takes 0 args,
        # reads executor.CONTENT_OUT_IN__TXT_CACHE internally
        # Ground truth: Ghidra sniff_ghidra_raw.txt line 4548
        # HF: determine if sniff captured data from the executor cache.
        # Ground truth (QEMU canvas trace):
        #   Empty/failed sniff: cache is '\n' or contains "trace len = 0"
        #     → _trace_len_known=True, _trace_len=0 → skip Decoding
        #   Data sniff: cache is '\n' (sniff response has no trace data)
        #     → _trace_len_known=False → show Decoding during parse
        # The sniff response cache distinguishes empty from data:
        #   Empty fixture: "trace len = 0" in cache → explicitly empty
        #   Failed fixture: ret=-1, cache='\n' → no data captured
        #   Data fixture: ret=1, cache='\n' → data exists but not in sniff response
        try:
            import executor
            cache = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            if 'trace len' in cache or 'Recorded activity' in cache:
                # Explicit trace length in sniff response
                import sniff as sniff_mod
                trace_len = sniff_mod.parserHfTraceLen()
                self._trace_len = int(trace_len) if trace_len else 0
                self._trace_len_known = True
        except Exception:
            pass

    @property
    def state(self):
        """Current state (for testing)."""
        return self._state

    @property
    def sniffing(self):
        """Whether sniff is in progress (for testing)."""
        return self._sniffing


# ═══════════════════════════════════════════════════════════════════════
# WarningWriteActivity
# ═══════════════════════════════════════════════════════════════════════

class WarningWriteActivity(BaseActivity):
    """Pre-write confirmation dialog.

    Shows source tag info + warning message before writing.
    Reached after successful Read/AutoCopy/DumpFiles flow.

    Binary source: activity_main.so WarningWriteActivity
    Spec: docs/UI_Mapping/15_write_tag/V1090_WRITE_FLOW_COMPLETE.md

    Bundle (from ReadActivity or CardWalletActivity):
        'infos': dict with tag type, UID, read data, keys, flags

    States:
        INITIAL — Show tag info, M1="Cancel", M2="Write"

    Key behavior (from binary):
        M1:  finish() — cancel, back to previous activity
        M2:  finish with result {action: 'write'} -> launches WriteActivity
        OK:  same as M2
        PWR: finish() — cancel/back

    Screen layout:
        Title: "Data ready!" (resources key: data_ready)
        Content: type tips + UID + place_empty_tag instruction
        M1: "Cancel", M2: "Write"
    """

    ACT_NAME = 'warning_write'

    def __init__(self, bundle=None):
        self._btlv = None
        self._infos = {}
        self._read_bundle = None  # Raw read result (path or dict)
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Show pre-write confirmation with tag info.

        Ground truth (from traces — bundle varies by tag type):
        - MFC: bundle = dump file path string
          (full_read_write_trace_20260327.txt line 49)
        - LF:  bundle = {'return':1, 'data':..., 'raw':...}
          (awid_write_trace_20260328.txt line 11)
        """
        self.setTitle(resources.get_str('data_ready'))
        # Open-source override: always use "Cancel" (removed "Watch" wearable feature)
        self.setLeftButton(resources.get_str('cancel'))
        self.setRightButton(resources.get_str('write'))

        # Store raw bundle for WriteActivity (pass-through)
        self._read_bundle = bundle

        # Extract infos for display from scan cache
        try:
            import scan as _scan_mod
            self._infos = _scan_mod.getScanCache() or {}
        except Exception:
            self._infos = {}

        # Render content
        self._draw_and_play()

    def _draw_and_play(self):
        """Render "Data ready!" content via JSON UI schema.

        Ground truth: data_ready.png — blue text, message at top,
        "TYPE:" centered, type display name in very large bold.
        Layout defined in src/screens/warning_write.json.
        Type display name from container.get_public_id() — NOT hardcoded.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return

        # Get display name from container.so — this is the .so doing the work.
        # Ground truth: data_ready.png shows "M1-4b"; user confirms EM410x shows "ID1".
        tag_type_id = self._infos.get('type', 0)
        type_display = ''
        try:
            import container
            type_display = container.get_public_id(self._infos) or ''
        except Exception as e:
            print('[WARNING_WRITE] container.get_public_id failed: %s' % e, flush=True)
            type_display = ''

        from lib.json_renderer import JsonRenderer
        jr = JsonRenderer(canvas)
        jr.set_state({
            'place_empty_tag': resources.get_str('place_empty_tag'),
            'tag_type_display': type_display,
        })

        import json, os
        screen_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'screens', 'warning_write.json')
        try:
            with open(screen_path) as f:
                screen_def = json.load(f)
            screen = screen_def['states']['initial']['screen']
            jr.render_content_only(screen.get('content', {}))
        except Exception as e:
            print('[WARNING_WRITE] JSON render failed: %s' % e, flush=True)

    def onKeyEvent(self, key):
        """Handle button presses.

        From binary onKeyEvent:
            M1/PWR: finish() — cancel
            M2/OK:  finish with result bundle {action: 'write'}
        """
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK):
            self._confirm_write()

    def _confirm_write(self):
        """Finish with write confirmation result.

        Ground truth: full_read_write_trace_20260327.txt line 50-51 —
        FINISH(WarningWriteActivity) → START(WriteActivity, same_bundle)
        """
        self._result = {
            'action': 'write',
            'read_bundle': self._read_bundle,
        }
        self.finish()

    @property
    def infos(self):
        """Tag info dict (for testing)."""
        return self._infos


# ═══════════════════════════════════════════════════════════════════════
# WriteActivity
# ═══════════════════════════════════════════════════════════════════════

class WriteActivity(BaseActivity):
    """Tag data writing with verification.

    Binary source: activity_main.so WriteActivity
    Spec: docs/UI_Mapping/15_write_tag/V1090_WRITE_FLOW_COMPLETE.md

    Bundle (from WarningWriteActivity):
        'infos': dict with tag type, UID, read data, keys, flags

    States:
        IDLE           — Show tag info, M1="Write", M2="Verify"
        WRITING        — Progress bar, writing data, buttons disabled
        WRITE_SUCCESS  — Toast "Write successful!", M1="Rewrite", M2="Verify"
        WRITE_FAILED   — Toast "Write failed!", M1="Rewrite", M2="Verify"
        VERIFYING      — Progress bar, verifying data, buttons disabled
        VERIFY_SUCCESS — Toast "Verification successful!", M1="Rewrite", M2="Verify"
        VERIFY_FAILED  — Toast "Verification failed!", M1="Rewrite", M2="Verify"

    write.so handles ALL write logic.

    Key behavior (from binary):
        IDLE:
            M1:  startWrite()
            M2:  startVerify()
            OK:  startWrite()
            PWR: finish()
        WRITING/VERIFYING:
            All buttons disabled (btn_enabled=False)
            PWR: finish() (user can abort by leaving)
        WRITE_SUCCESS/WRITE_FAILED/VERIFY_SUCCESS/VERIFY_FAILED:
            M1:  startWrite() (rewrite)
            M2:  startVerify()
            OK:  startWrite() (rewrite)
            PWR: finish()
    """

    ACT_NAME = 'write'

    # State constants
    STATE_IDLE = 'idle'
    STATE_WRITING = 'writing'
    STATE_WRITE_SUCCESS = 'write_success'
    STATE_WRITE_FAILED = 'write_failed'
    STATE_VERIFYING = 'verifying'
    STATE_VERIFY_SUCCESS = 'verify_success'
    STATE_VERIFY_FAILED = 'verify_failed'

    def __init__(self, bundle=None):
        self._state = self.STATE_IDLE
        self._read_bundle = None
        # Ground truth: trace_write_activity_attrs_20260402.txt —
        # write.so reads these PUBLIC attributes on the activity:
        self.infos = {}                    # .infos (NOT _infos)
        self.can_verify = False            # .can_verify (NOT _can_verify)
        self._write_progressbar = None     # ._write_progressbar (NOT _progressbar)
        self._write_toast = None           # ._write_toast (NOT _toast)
        self._btn_enabled = True
        self._can_write = True
        self._fake_timer = None             # Timer ID for fake progress animation
        # Resource text strings (original exposes these as public attrs)
        self.text_rewrite = resources.get_str('rewrite')
        self.text_verify = resources.get_str('verify')
        self.text_verify_failed = resources.get_str('verify_failed')
        self.text_verify_success = resources.get_str('verify_success')
        self.text_verifying = resources.get_str('verifying')
        self.text_write_failed = resources.get_str('write_failed')
        self.text_write_success = resources.get_str('write_success')
        self.text_write_tag = resources.get_str('write_tag')
        self.text_writing = resources.get_str('writing')
        self.text_t55xx_checking = resources.get_str('t55xx_checking') if hasattr(resources, 'get_str') else 'T55xx keys checking...'
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, buttons, progress bar, and toast area.

        Ground truth: trace_write_activity_attrs_20260402.txt —
        original WriteActivity has ._bundle set to dump path,
        .infos set to scan cache, text_* resource strings, etc.
        """
        self.setTitle(resources.get_str('write_tag'))
        self.setLeftButton(resources.get_str('write'))
        self.setRightButton(resources.get_str('verify'))

        # Bundle is the raw read result (dump path or dict)
        self._read_bundle = bundle
        try:
            import scan as _scan_mod
            self.infos = _scan_mod.getScanCache() or {}
        except Exception:
            self.infos = {}

        canvas = self.getCanvas()
        if canvas is None:
            return

        # Render tag info template as the base canvas layer.
        # Ground truth: original screenshots show tag info (name, type,
        # frequency, FC/CN, chipset, UID etc.) persisted behind progress
        # bar and toast overlays through ALL write/verify phases.
        tag_type = self.infos.get('type', -1)
        if tag_type >= 0 and self.infos:
            try:
                import template
                template.draw(tag_type, self.infos, canvas)
            except Exception as e:
                print('[WRITE] template.draw failed: %s' % e, flush=True)

        from lib.widget import ProgressBar
        self._write_progressbar = ProgressBar(canvas)
        self._write_toast = Toast(canvas)

        # Ground truth: trace_autocopy_mf1k_standard.txt —
        # WriteActivity auto-starts write immediately when given a bundle.
        # PM3 hf 14a info fires at the same timestamp as START(WriteActivity).
        if self._read_bundle:
            self.startWrite()

    def onKeyEvent(self, key):
        """State-dependent key dispatch.

        From binary onKeyEvent:
            IDLE: M1/OK=write, M2=verify, PWR=back
            WRITING/VERIFYING: buttons disabled, PWR=back
            SUCCESS/FAILED: M1/OK=rewrite, M2=verify, PWR=back

        PWR abort: stop PM3 before finishing, same pattern as
        SniffActivity._stopSniff (presspm3 + stopPM3Task).  Without
        this, a long-running fchk/wrbl keeps the PM3 busy after exit
        and contaminates the pipeline for subsequent commands.
        """
        if key == KEY_PWR:
            if self._handlePWR():
                return
            # Stop any running PM3 task before exiting
            try:
                import hmi_driver
                hmi_driver.presspm3()
            except Exception:
                pass
            try:
                import executor
                executor.stopPM3Task()
            except Exception:
                pass
            self.finish()
            return

        if not self._btn_enabled:
            return

        # Ground truth: trace_write_activity_attrs_20260402.txt
        # IDLE state:      M1="Write",  M2="Verify"  → M1=startWrite, M2=startVerify
        # After completion: M1="Verify", M2="Rewrite" → M1=startVerify, M2=startWrite
        if self._state == self.STATE_IDLE:
            if key in (KEY_M1, KEY_OK):
                self.startWrite()
            elif key == KEY_M2:
                self.startVerify()
        else:
            # After write/verify completes: M1=Verify, M2=Rewrite
            if key in (KEY_M1, KEY_OK):
                self.startVerify()
            elif key == KEY_M2:
                self.startWrite()

    def setBtnEnable(self, enabled):
        """Enable/disable M1+M2 buttons.

        Ground truth: write_tag_writing_1.png — during Writing/Verifying
        the button bar is completely hidden (no dark background, no text).
        When re-enabled, setLeftButton/setRightButton recreate the bar
        via _setupButtonBg().
        """
        self._btn_enabled = enabled

        if enabled:
            # Restore visibility/active flags so keys aren't silently dropped
            # in the window between setBtnEnable(True) and setLeftButton/setRightButton.
            self._m1_visible = True
            self._m2_visible = True
            self._m1_active = True
            self._m2_active = True
        else:
            # Hide entire button bar (background + text) during write/verify
            self.dismissButton()

    def startWrite(self):
        """Initiate write: disable buttons, show progress, call write.so.

        From binary startWrite():
            1. setBtnEnable(False)
            2. playWriting() — show "Writing..." progress bar
            3. Launch write.write() on background thread
            4. Callback: on_write() with result
        """
        self._state = self.STATE_WRITING
        self.setBtnEnable(False)
        self.playWriting()

        # Ground truth: trace_write_flow_20260402.txt
        # write.write(on_write_callback, scan_cache, read_bundle)
        # Returns -9999 immediately (write.so spawns its own thread).
        # Result delivered via on_write callback. NO extra Python thread needed.
        try:
            import write as write_mod
            write_mod.write(self.on_write, self.infos, self._read_bundle)
        except ImportError:
            pass
        except Exception as e:
            print('[WRITE] exception: %s' % e, flush=True)
            import traceback; traceback.print_exc()
            self._onWriteComplete('write_failed')

    def startVerify(self):
        """Initiate verify: disable buttons, show progress, call write.so.

        From binary startVerify():
            1. setBtnEnable(False)
            2. playVerifying() — show "Verifying..." progress bar
            3. Launch write.verify() on background thread
            4. Callback: on_verify() with result
        """
        self._state = self.STATE_VERIFYING
        self.setBtnEnable(False)
        self.playVerifying()

        # Ground truth: write.so spawns its own thread. Call directly.
        try:
            import write as write_mod
            write_mod.verify(self.on_verify, self.infos, self._read_bundle)
        except ImportError:
            pass
        except Exception as e:
            print('[VERIFY] exception: %s' % e, flush=True)
            import traceback; traceback.print_exc()
            self._onVerifyComplete('verify_failed')

    def _start_fake_progress(self, ceiling=60):
        """Animate progress bar at ~1%/s until real callbacks arrive."""
        self._cancel_fake_progress()
        if actstack._root is None:
            return
        self._fake_pct = 0

        def _tick():
            if self._state not in (self.STATE_WRITING, self.STATE_VERIFYING):
                self._fake_timer = None
                return
            if self._fake_pct < ceiling:
                self._fake_pct += 1
                if self._write_progressbar is not None:
                    self._write_progressbar.setProgress(self._fake_pct)
                self._fake_timer = actstack._root.after(1000, _tick)
            else:
                self._fake_timer = None
        self._fake_timer = actstack._root.after(1000, _tick)

    def _cancel_fake_progress(self):
        """Stop fake progress animation."""
        if self._fake_timer is not None:
            try:
                actstack._root.after_cancel(self._fake_timer)
            except Exception:
                pass
            self._fake_timer = None

    def playWriting(self):
        """Show "Writing..." progress bar animation.

        Ground truth: binary symbol WriteActivity.playWriting (no underscore).
        write.so calls activity.playWriting() via callback.__self__.
        write_tag_writing_1.png: no button bar visible during writing.
        """
        if self._write_toast is not None:
            self._write_toast.cancel()
        self.dismissButton()  # Hide button bar during write
        if self._write_progressbar is not None:
            self._write_progressbar.setMessage(resources.get_str('writing'))
            self._write_progressbar.setProgress(0)
            self._write_progressbar.show()
        self._start_fake_progress(ceiling=60)

    def playVerifying(self):
        """Show "Verifying..." progress bar animation.

        Ground truth: binary symbol WriteActivity.playVerifying (no underscore).
        write.so calls activity.playVerifying() via callback.__self__.
        write_tag_writing_1.png: no button bar visible during verifying.
        """
        if self._write_toast is not None:
            self._write_toast.cancel()
        self.dismissButton()  # Hide button bar during verify
        if self._write_progressbar is not None:
            self._write_progressbar.setMessage(resources.get_str('verifying'))
            self._write_progressbar.setProgress(0)
            self._write_progressbar.show()
        self._start_fake_progress(ceiling=60)

    def on_write(self, *args):
        """Callback from write.so — progress updates AND completion.

        Ground truth: trace with DRM fixed shows write.so calls on_write
        with progress dicts {'max': 64, 'progress': N} during write,
        then completion dict {'success': True/False, ...} at the end.
        Same pattern as read.so's onReading callback.
        Binary symbol: activity_main_strings.txt line 21220.
        """
        data = args[0] if args else {}
        if not isinstance(data, dict):
            return
        # Completion: has 'success' key
        # Must dispatch to main thread — this callback runs on write.py's
        # background thread but _onWriteComplete does Tk canvas operations.
        if 'success' in data:
            self._cancel_fake_progress()
            result = 'write_success' if data.get('success') else 'write_failed'
            canvas = self.getCanvas()
            if canvas:
                canvas.after(0, lambda r=result: self._onWriteComplete(r))
            else:
                self._onWriteComplete(result)
            return
        # Progress message (from check_detect "Checking T55xx keys...")
        if 'progress_message' in data:
            msg = data['progress_message']
            if self._write_progressbar:
                canvas = self.getCanvas()
                if canvas:
                    canvas.after(0, lambda m=msg: self._write_progressbar.setMessage(m))
        # Progress: has 'max' and 'progress' keys — cancel fake timer on first real update
        if 'max' in data and 'progress' in data:
            self._cancel_fake_progress()
            pct = int(data['progress'] * 100 / max(data['max'], 1))
            if self._write_progressbar:
                canvas = self.getCanvas()
                if canvas:
                    canvas.after(0, lambda p=pct: self._write_progressbar.setProgress(p))
                else:
                    self._write_progressbar.setProgress(pct)

    def on_verify(self, *args):
        """Callback from write.so — progress updates AND completion.

        Same pattern as on_write.
        Binary symbol: activity_main_strings.txt line 21184.
        """
        data = args[0] if args else {}
        if not isinstance(data, dict):
            return
        if 'success' in data:
            self._cancel_fake_progress()
            result = 'verify_success' if data.get('success') else 'verify_failed'
            canvas = self.getCanvas()
            if canvas:
                canvas.after(0, lambda r=result: self._onVerifyComplete(r))
            else:
                self._onVerifyComplete(result)
            return
        if 'max' in data and 'progress' in data:
            self._cancel_fake_progress()
            pct = int(data['progress'] * 100 / max(data['max'], 1))
            if self._write_progressbar:
                canvas = self.getCanvas()
                if canvas:
                    canvas.after(0, lambda p=pct: self._write_progressbar.setProgress(p))
                else:
                    self._write_progressbar.setProgress(pct)

    def _onWriteComplete(self, result):
        """Handle write completion — show success/fail toast, update buttons.

        Ground truth: trace_write_flow_20260402.txt —
        on_write callback receives result string from write.so.
        """
        if self._write_progressbar is not None:
            self._write_progressbar.hide()

        if result == 'write_success':
            self._state = self.STATE_WRITE_SUCCESS
            self._playWriteSuccess()
        else:
            self._state = self.STATE_WRITE_FAILED
            self._playWriteFail()

        self.setBtnEnable(True)
        self.setLeftButton(resources.get_str('verify'))  # HANDOVER.md: M1=Verify
        self.setRightButton(resources.get_str('rewrite'))  # HANDOVER.md: M2=Rewrite

    def _onVerifyComplete(self, result):
        """Handle verify completion — show success/fail toast.

        From binary on_verify():
            if result == "verify_success":
                playVerifiSuccess()
            else:
                playVerifiFail()
            setBtnEnable(True)
            setLeftButton("Rewrite")
        """
        if self._write_progressbar is not None:
            self._write_progressbar.hide()

        if result == 'verify_success':
            self._state = self.STATE_VERIFY_SUCCESS
            self._playVerifySuccess()
        else:
            self._state = self.STATE_VERIFY_FAILED
            self._playVerifyFail()

        self.setBtnEnable(True)
        self.setLeftButton(resources.get_str('verify'))  # HANDOVER: M1=Verify
        self.setRightButton(resources.get_str('rewrite'))  # HANDOVER: M2=Rewrite

    def _playWriteSuccess(self):
        """Show "Write successful!" toast.

        Ground truth: write_tag_writing_3.png → success toast with check icon.
        """
        if self._write_toast is not None:
            self._write_toast.show(resources.get_str('write_success'),
                             mode=Toast.MASK_CENTER, icon='check',
                             duration_ms=0, wrap='auto')

    def _playWriteFail(self):
        """Show "Write failed!" toast.

        Ground truth: write_tag_write_failed.png → failure toast with error icon.
        """
        print('[WRITE-TOAST] _playWriteFail called, _write_toast=%s' % (self._write_toast is not None), flush=True)
        if self._write_toast is not None:
            self._write_toast.show(resources.get_str('write_failed'),
                             mode=Toast.MASK_CENTER, icon='error',
                             duration_ms=0, wrap='auto')
            print('[WRITE-TOAST] toast.show() called with: %r' % resources.get_str('write_failed'), flush=True)

    def _playVerifySuccess(self):
        """Show "Verification successful!" toast.

        Ground truth: binary playVerifiSuccess() → check icon, persistent.
        """
        if self._write_toast is not None:
            self._write_toast.show(resources.get_str('verify_success'),
                             mode=Toast.MASK_CENTER, icon='check',
                             duration_ms=0, wrap='auto')

    def _playVerifyFail(self):
        """Show "Verification failed!" toast.

        Ground truth: binary playVerifiFail() → error icon, persistent.
        """
        if self._write_toast is not None:
            self._write_toast.show(resources.get_str('verify_failed'),
                             mode=Toast.MASK_CENTER, icon='error',
                             duration_ms=0, wrap='auto')

    @property
    def state(self):
        """Current state (for testing)."""
        return self._state

    @property
    def btn_enabled(self):
        """Whether buttons are enabled (for testing)."""
        return self._btn_enabled

    def callServer(self, *args, **kwargs):
        """Stub — original binary has this method.
        Ground truth: trace_write_activity_attrs_20260402.txt line 34."""
        pass

    def save_log(self, *args, **kwargs):
        """Stub — original binary has this method.
        Ground truth: trace_write_activity_attrs_20260402.txt line 59."""
        pass


# ═══════════════════════════════════════════════════════════════════════
# WarningM1Activity
# ═══════════════════════════════════════════════════════════════════════

class WarningM1Activity(BaseActivity):
    """Missing MIFARE keys warning with 4 option pages.

    Displayed when read.so reports missing keys during MIFARE read.
    UP/DOWN navigates between pages. Each page offers a different
    recovery option.

    Binary source: activity_main.so WarningM1Activity
    Spec: docs/UI_Mapping/04_read_tag/V1090_MIFARE_BRANCH_STRINGS.md

    Pages:
        Page 0: "Sniff for Keys" — options 1 & 2 (sniff + enter manually)
        Page 1: "Force Read / PC Mode" — options 3 & 4
        (Each page shows 2 options in text)

    Actually from resources.itemmsg:
        missing_keys_msg1: "Option 1) Go to reader to sniff keys
                            Option 2) Enter known keys manually"
        missing_keys_msg2: "Option 3) Force read to get partial data
                            Option 4) Go into PC Mode to perform hardnest"

    M2 action depends on current page:
        Page 0: M2="Sniff"   — result {action: 'sniff'}
        Page 1: M2="Force"   — result {action: 'force'}

    Key behavior (from binary):
        UP:   prev page (min 0)
        DOWN: next page (max 1)
        M1:   finish() — cancel
        M2:   execute page-specific action, finish with result
        OK:   same as M2
        PWR:  finish() — cancel/back
    """

    ACT_NAME = 'warning_m1'

    # 2 pages, each with 2 options (M1 = left option, M2 = right option)
    # Ground truth: force-read test expects M1:Sniff on page 0,
    # M1:Force on page 1. Test sends DOWN then M1 for Force Read.
    PAGE_MAX = 1

    # Per-page button labels and actions
    # Page 0: M1=Sniff  M2=Enter    (options 1, 2)
    # Page 1: M1=Force  M2=PC-M     (options 3, 4)
    PAGE_M1_LABELS = ['sniff', 'force']
    PAGE_M2_LABELS = ['enter', 'pc-m']
    PAGE_M1_ACTIONS = ['sniff', 'force']
    PAGE_M2_ACTIONS = ['enter_key', 'pc_mode']

    def __init__(self, bundle=None):
        self._page = 0
        self._btlv = None
        self._infos = {}
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, buttons, and first page content.

        Flow (from binary onCreate):
            1. setTitle("Warning") or "Missing keys"
            2. Show page 0 content
            3. setLeftButton("Cancel"), setRightButton(page-specific)
        """
        self.setTitle(resources.get_str('missing_keys'))
        self.setLeftButton(resources.get_str('cancel'))

        # Extract infos from bundle
        if bundle and isinstance(bundle, dict):
            self._infos = bundle.get('infos', {})

        canvas = self.getCanvas()
        if canvas is None:
            return

        from lib.widget import BigTextListView
        self._btlv = BigTextListView(canvas)

        # Show initial page
        self._showPage()

    def _showPage(self):
        """Render current page content and update M1/M2 buttons.

        Ground truth: force-read test expects M1=Sniff on page 0,
        M1=Force on page 1 (after DOWN). Each page shows 2 options
        as M1/M2 button labels + descriptive text in content area.
        Page 0: missing_keys_msg1 (options 1 & 2)
        Page 1: missing_keys_msg2 (options 3 & 4)
        """
        page_content_keys = [
            'missing_keys_msg1',
            'missing_keys_msg2',
        ]

        if self._btlv is not None:
            key = page_content_keys[min(self._page, len(page_content_keys) - 1)]
            self._btlv.drawStr(resources.get_str(key))

        # Update M1 and M2 for current page's option pair
        m1_key = self.PAGE_M1_LABELS[self._page]
        m2_key = self.PAGE_M2_LABELS[self._page]
        self.setLeftButton(resources.get_str(m1_key))
        self.setRightButton(resources.get_str(m2_key))

    def onKeyEvent(self, key):
        """Handle navigation and action keys.

        Ground truth: force-read test sends DOWN then M1 for Force.
        UP/DOWN navigate pages, M1 = left action, M2/OK = right action,
        PWR = cancel.
        """
        if key == KEY_UP:
            if self._page > 0:
                self._page -= 1
                self._showPage()
        elif key == KEY_DOWN:
            if self._page < self.PAGE_MAX:
                self._page += 1
                self._showPage()
        elif key == KEY_M1:
            self._selectOption('m1')
        elif key in (KEY_M2, KEY_OK):
            self._selectOption('m2')
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()

    def _selectOption(self, button):
        """Execute page-specific action and finish with result.

        M1 = left option per page, M2 = right option per page.
        """
        if button == 'm1':
            action = self.PAGE_M1_ACTIONS[self._page]
        else:
            action = self.PAGE_M2_ACTIONS[self._page]
        self._result = {
            'action': action,
            'page': self._page,
            'infos': self._infos,
        }
        self.finish()

    @property
    def page(self):
        """Current page index (for testing)."""
        return self._page


# ═══════════════════════════════════════════════════════════════════════
# AutoCopyActivity
# ═══════════════════════════════════════════════════════════════════════

class AutoCopyActivity(ConsoleMixin, BaseActivity):
    """One-button tag clone: Scan -> Read -> Write -> Verify.

    Auto-starts scan on creation.
    After successful read, prompts to place new card.
    After write + optional verify, shows success/fail result.

    Binary source: activity_main.so AutoCopyActivity
    Verified: docs/UI_Mapping/01_auto_copy/README.md (exhaustive)
              docs/UI_Mapping/01_auto_copy/V1090_AUTOCOPY_FLOW_COMPLETE.md
    Spec: 16+ states, linear pipeline with error exits at each stage

    Instance variables (from binary attribute access strings):
        self.scan_found  — bool: True after successful scan
        self.scan_infos  — bool/dict: scan result info dict (or False)
        self.place       — bool: True when in "place new tag" prompt state

    Key behavior (from Ghidra ~900-line analysis of onKeyEvent):
        isbusy() == True:
            PWR: finish (exit)
            All other keys: ignored
        scan_found == True (post-scan phase):
            M2/OK: startWrite (in place-card state) or rescan
            M1:    startScan (rescan)
            PWR:   finish
        scan_found == False (scan/idle phase):
            M1/M2/OK: startScan (rescan)
            PWR:      finish

    Audio cues in sequence: playScanning -> playTagfound -> playReadingKeys
        -> playReadyForCopy -> playWriting -> playVerifying -> playVerifiSuccess
    """

    ACT_NAME = 'autocopy'

    # ---- State constants ----
    STATE_SCANNING = 'scanning'
    STATE_SCAN_NOT_FOUND = 'scan_not_found'
    STATE_SCAN_WRONG_TYPE = 'scan_wrong_type'
    STATE_SCAN_MULTI = 'scan_multi'
    STATE_READING = 'reading'
    STATE_READ_FAILED = 'read_failed'
    STATE_READ_NO_KEY_HF = 'read_no_key_hf'
    STATE_READ_NO_KEY_LF = 'read_no_key_lf'
    STATE_READ_MISSING_KEYS = 'read_missing_keys'
    STATE_READ_TIMEOUT = 'read_timeout'
    STATE_PLACE_CARD = 'place_card'
    STATE_WRITING = 'writing'
    STATE_WRITE_SUCCESS = 'write_success'
    STATE_WRITE_FAILED = 'write_failed'
    STATE_VERIFYING = 'verifying'
    STATE_VERIFY_SUCCESS = 'verify_success'
    STATE_VERIFY_FAILED = 'verify_failed'
    STATE_CANCELLED = 'cancelled'

    # Scan return codes (same as ScanActivity, verified via QEMU)
    CODE_TAG_LOST = -2
    CODE_TAG_MULT = -3
    CODE_TAG_NO = -4
    CODE_TAG_TYPE_WRONG = -5
    CODE_TIMEOUT = -1

    def __init__(self, bundle=None):
        self._state = self.STATE_SCANNING
        self.scan_found = False
        self.scan_infos = False
        self.place = False
        self._scan_result = None
        self._read_data = None
        self._read_bundle = None
        self._scanner = None
        self._reader = None
        self._got_progress = False
        self._progressbar = None
        self._toast = None
        self._btn_enabled = False
        self._console = None
        self._console_showing = False
        self._fake_timer = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        """Set up title, then auto-start scanning immediately.

        Flow (from binary onCreate):
            1. super().onCreate()
            2. setTitle("Auto Copy")
            3. startScan() — auto-starts scanning, no user action needed
        """
        self.setTitle(resources.get_str('auto_copy'))

        canvas = self.getCanvas()
        if canvas is None:
            return

        from lib.widget import ProgressBar
        self._progressbar = ProgressBar(canvas)
        self._toast = Toast(canvas)

        # Auto-start scan (from binary: onCreate calls startScan immediately)
        self.startScan()

    def onKeyEvent(self, key):
        """State-dependent key dispatch.

        From Ghidra analysis (~900 lines):
            CHECK 1: isbusy() — if True, only PWR works (finish)
            CHECK 2: scan_found — determines branch (scan phase vs post-scan)

        Reconstructed from docs/UI_Mapping/01_auto_copy/README.md section 6.
        """
        # Console mode: all keys go to ConsoleView (from ConsoleMixin)
        if self._handleConsoleKey(key):
            return

        # PWR: always works, even when busy.
        # Ground truth (Ghidra): "isbusy() — if True, only PWR works (finish)"
        # Original binary allows PWR to exit during scan/read/write.
        # Must abort any in-flight PM3 command before finishing.
        if key == KEY_PWR:
            # Dismiss toast if showing (but don't swallow the key)
            for attr in ('_toast', '_write_toast'):
                toast = getattr(self, attr, None)
                if toast is not None:
                    try:
                        if toast.isShow():
                            toast.cancel()
                    except Exception:
                        pass
            # Abort any in-flight PM3 command
            try:
                import hmi_driver
                hmi_driver.presspm3()
            except Exception:
                pass
            try:
                import executor
                executor.stopPM3Task()
            except Exception:
                pass
            self.finish()
            return

        # During reading: RIGHT shows console (same as ReadListActivity)
        # Ground truth: read_mf1k_console_during_read test, activity_read.py:194-196
        if self._state == self.STATE_READING and key == KEY_RIGHT:
            self._showConsole()
            return

        # During busy operations (scan/read/write/verify): ignore all other keys
        if not self._btn_enabled:
            return

        if self.scan_found:
            # Post-scan phase: tag was found, in read/write territory
            if self._state == self.STATE_PLACE_CARD:
                # Place card prompt: M2/OK = push WarningWriteActivity, M1 = reread
                # Ground truth: trace_autocopy_mf1k_standard.txt line 111-114
                # M2 → START(WarningWriteActivity, read_bundle)
                if key in (KEY_M2, KEY_OK):
                    self._launchWrite()
                elif key == KEY_M1:
                    self._startRead()
            elif self._state == self.STATE_READ_MISSING_KEYS:
                # Missing keys: M2/OK = force-use (proceed), M1 = rescan
                if key in (KEY_M2, KEY_OK):
                    self._promptSwapCard()
                elif key == KEY_M1:
                    self.startScan()
            elif self._state == self.STATE_READ_FAILED:
                # Read failed: M1 = rescan, M2/OK = reread
                if key == KEY_M1:
                    self.startScan()
                elif key in (KEY_M2, KEY_OK):
                    self._startRead()
            elif self._state == self.STATE_READ_TIMEOUT:
                # Key check timeout: M1 = rescan, M2/OK = retry read
                if key == KEY_M1:
                    self.startScan()
                elif key in (KEY_M2, KEY_OK):
                    self._startRead()
            elif self._state in (self.STATE_READ_NO_KEY_HF,
                                  self.STATE_READ_NO_KEY_LF):
                # No valid key: M1/M2/OK = rescan
                if key in (KEY_M1, KEY_M2, KEY_OK):
                    self.startScan()
            elif self._state in (self.STATE_WRITE_SUCCESS,
                                  self.STATE_VERIFY_SUCCESS):
                # Write/Verify success: M1/M2/OK = rescan (copy another)
                if key in (KEY_M1, KEY_M2, KEY_OK):
                    self.startScan()
            elif self._state == self.STATE_WRITE_FAILED:
                # Write failed: M1 = rescan, M2/OK = rewrite
                if key == KEY_M1:
                    self.startScan()
                elif key in (KEY_M2, KEY_OK):
                    self._startWrite()
            elif self._state == self.STATE_VERIFY_FAILED:
                # Verify failed: M1 = rescan, M2/OK = rewrite
                if key == KEY_M1:
                    self.startScan()
                elif key in (KEY_M2, KEY_OK):
                    self._startWrite()
        else:
            # Scan phase or scan-fail state: M1/M2/OK all -> rescan
            if key in (KEY_M1, KEY_M2, KEY_OK):
                self.startScan()

    # ------------------------------------------------------------------
    # Fake progress animation (shared by scan and read phases)
    # ------------------------------------------------------------------

    def _start_fake_progress(self, start=0, ceiling=80):
        """Animate progress bar at ~1%/s until real callbacks arrive."""
        self._cancel_fake_progress()
        if actstack._root is None:
            return
        self._fake_pct = start

        def _tick():
            if self._state not in (self.STATE_SCANNING, self.STATE_READING):
                self._fake_timer = None
                return
            if self._fake_pct < ceiling:
                self._fake_pct += 1
                if self._progressbar is not None:
                    self._progressbar.setProgress(self._fake_pct)
                self._fake_timer = actstack._root.after(1000, _tick)
            else:
                self._fake_timer = None
        self._fake_timer = actstack._root.after(1000, _tick)

    def _cancel_fake_progress(self):
        """Stop fake progress animation."""
        if self._fake_timer is not None:
            try:
                actstack._root.after_cancel(self._fake_timer)
            except Exception:
                pass
            self._fake_timer = None

    # ------------------------------------------------------------------
    # Scan phase
    # ------------------------------------------------------------------

    def startScan(self):
        """Reset state and start async scan.

        From binary startScan():
            1. self.scan_found = False
            2. self.scan_infos = False
            3. showScanToast() — show scanning progress UI
            4. Scanner.scan_all_asynchronous(self) — start async scan
        """
        self.scan_found = False
        self.scan_infos = False
        self.place = False
        self._read_data = None
        self._state = self.STATE_SCANNING
        self._btn_enabled = False
        self.setbusy()

        # Clear previous content
        if self._toast is not None:
            self._toast.cancel()

        # Hide action bar so ProgressBar is fully visible
        self.dismissButton()
        if self._progressbar is not None:
            self._progressbar.setMessage(resources.get_str('scanning'))
            self._progressbar.setProgress(0)
            self._progressbar.show()
            # Ground truth: original firmware immediately fills to 50%
            self._progressbar.setProgress(50)

        # Play scanning audio
        try:
            import audio
            audio.playScanning()
        except Exception:
            pass

        # Start async scan (scan.so handles all RFID detection)
        # Correct call pattern (same as ScanActivity, from scan.so probing):
        #   Scanner() instance with callback attributes, then scan_all_asynchronous()
        try:
            import scan as _scan_mod
            self._scanner = _scan_mod.Scanner()
            self._scanner.call_progress = self.onScanning
            self._scanner.call_resulted = self.onScanFinish
            self._scanner.call_exception = self.onScanFinish
            self._scanner.scan_all_asynchronous()
        except Exception as e:
            print('[AUTOCOPY] scan start error: %s' % e, flush=True)
            import traceback as _tb
            _tb.print_exc()

    def showScanToast(self, found, multi=False, wrong_type=False):
        """Show the appropriate scan result toast.

        Same logic as ScanActivity.showScanToast but within AutoCopy context.

        Toast messages from resources.py:
            tag_found:      "Tag Found"
            no_tag_found:   "No tag found"
            no_tag_found2:  "No tag found \\nOr\\n Wrong type found!"
            tag_multi:      "Multiple tags detected!"
        """
        if self._toast is None:
            return

        if found:
            self._toast.show(
                resources.get_str('tag_found'),
                mode=Toast.MASK_CENTER,
                icon='check',
            )
            try:
                import audio
                audio.playTagfound()
            except Exception:
                pass
        elif multi:
            self._toast.show(
                resources.get_str('tag_multi'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
            try:
                import audio
                audio.playMultiCard()
            except Exception:
                pass
        elif wrong_type:
            self._toast.show(
                resources.get_str('no_tag_found2'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
            try:
                import audio
                audio.playwrongTagfound()
            except Exception:
                pass
        else:
            self._toast.show(
                resources.get_str('no_tag_found'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
            try:
                import audio
                audio.playTagNotfound()
            except Exception:
                pass

    def onScanning(self, progress):
        """Callback from scan.so — update scanning progress bar.

        Fires from scanner background thread — schedule on Tk main thread.
        """
        if isinstance(progress, (list, tuple)) and len(progress) >= 2:
            pct = int(progress[0] * 100 / max(progress[1], 1))
        else:
            pct = int(progress) if progress else 0

        def _update():
            if self._progressbar is not None:
                self._progressbar.setProgress(pct)

        try:
            from lib import actstack
            if actstack._root is not None:
                actstack._root.after(0, _update)
            else:
                _update()
        except Exception:
            pass

    def onScanFinish(self, result):
        """Callback from scan.so — process scan result.

        ProgressBar completes to 100% before transitioning.
        """
        # Defer the actual transition until progress bar completes to 100%
        self._pending_scan_result = result
        if self._progressbar is not None:
            self._progressbar.complete(self._processScanResult)
        else:
            self._processScanResult()

    def _processScanResult(self):
        """Process scan result after progress bar completes."""
        result = getattr(self, '_pending_scan_result', None)
        if self._progressbar is not None:
            self._progressbar.hide()

        if result is None:
            result = {'found': False, 'return': self.CODE_TAG_NO}

        # Handle string result codes from scan.so
        if isinstance(result, str):
            code_map = {
                'CODE_TAG_NO': self.CODE_TAG_NO,
                'CODE_TAG_MULT': self.CODE_TAG_MULT,
                'CODE_TAG_LOST': self.CODE_TAG_LOST,
                'CODE_TAG_TYPE_WRONG': self.CODE_TAG_TYPE_WRONG,
                'CODE_TIMEOUT': self.CODE_TIMEOUT,
            }
            ret_code = code_map.get(result, self.CODE_TAG_NO)
            result = {'found': False, 'return': ret_code}

        # Handle int result codes
        if isinstance(result, int):
            result = {'found': False, 'return': result}

        self._scan_result = result

        # Use scan.so's own predicate functions to determine scan outcome.
        # Ground truth: activity_main.so string table references only
        # isTagMulti and isTagFound (lines 21937-21938, 25582-25583, 29694, 29780).
        # Live trace: trace_autocopy_multitag_wrongtype_20260402.txt line 6-7
        # confirms multi-tag collision sets internal state queried by isTagMulti().
        try:
            import scan as _scan_mod
            is_multi = _scan_mod.isTagMulti(result)
            is_found = _scan_mod.isTagFound(result)
        except Exception:
            # Fallback to dict keys if scan.so predicates unavailable
            is_multi = result.get('hasMulti', False)
            is_found = result.get('found', False)

        if is_multi:
            self._state = self.STATE_SCAN_MULTI
            self.showScanToast(found=False, multi=True)
            self._showScanFailButtons()
        elif is_found:
            # Tag found — brief toast, then auto-start read
            self.scan_found = True
            self.scan_infos = result
            self.showScanToast(found=True)
            self._startRead()
        else:
            self._state = self.STATE_SCAN_NOT_FOUND
            self.showScanToast(found=False)
            self._showScanFailButtons()

    def _showScanFailButtons(self):
        """Show Rescan/Rescan buttons for scan failure states."""
        self.setidle()
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('rescan'))
        self._btn_enabled = True

    # ------------------------------------------------------------------
    # Read phase
    # ------------------------------------------------------------------

    def _startRead(self, force=False):
        """Initiate read phase: show progress, call read.so.

        From binary: after scan success, immediately starts reading.
        Uses same Reader() pattern as ReadListActivity.
        Ground truth: trace_autocopy_mf1k_standard.txt line 16 —
        READER_START args=(1, {'infos': {scan_cache}, 'force': False})
        """
        self._state = self.STATE_READING
        self._btn_enabled = False
        self.place = False
        self._got_progress = False

        if self._toast is not None:
            self._toast.cancel()

        # Hide action bar so ProgressBar is fully visible
        self.dismissButton()
        if self._progressbar is not None:
            self._progressbar.setMessage(resources.get_str('reading'))
            self._progressbar.setProgress(0)
            self._progressbar.show()
            # Ground truth: original firmware immediately fills to 50%
            self._progressbar.setProgress(50)

        self._start_fake_progress(start=50, ceiling=80)

        # Play reading audio
        try:
            import audio
            audio.playReadingKeys()
        except Exception:
            pass

        # Get scan cache for reader
        scan_cache = self._scan_result or {}
        try:
            import scan as _scan_mod
            sc = _scan_mod.getScanCache()
            if sc:
                scan_cache = sc
        except Exception:
            pass

        tag_type = scan_cache.get('type', 0)
        bundle = {'infos': scan_cache, 'force': force}

        # Start read using Reader() pattern (same as ReadListActivity)
        try:
            import read as _read_mod
            self._reader = _read_mod.Reader()
            self._reader.call_reading = self.onReading
            self._reader.call_exception = self._onReadException
            self._reader.start(tag_type, bundle)

            # Completion poll — fallback for readers that don't use
            # onReading completion dict (mechanism 4 from ReadListActivity).
            # Must wait for _read_bundle to be set by onReading before
            # calling _promptSwapCard — otherwise WriteActivity gets None
            # as bundle and write.so can't write.
            # Bug found: MF4K (40 sectors) poll detected is_reading()==False
            # before onReading completion dict arrived → _read_bundle was None.
            import threading as _thr
            def _wait_for_completion():
                import time
                while self._reader is not None and self._state == self.STATE_READING:
                    try:
                        if not self._reader.is_reading():
                            # Wait for onReading completion to fire first
                            for _ in range(20):
                                time.sleep(0.5)
                                if self._state != self.STATE_READING:
                                    return  # onReading handled it
                            # onReading never fired — fallback
                            self._reader = None
                            if self._got_progress:
                                self._promptSwapCard()
                            else:
                                self._state = self.STATE_READ_FAILED
                                self._showReadFailed()
                            return
                    except Exception:
                        pass
                    time.sleep(0.3)
            _thr.Thread(target=_wait_for_completion, daemon=True).start()
        except Exception as e:
            print('[AUTOCOPY] read start error: %s' % e, flush=True)
            import traceback as _tb
            _tb.print_exc()
            self._state = self.STATE_READ_FAILED
            self._showReadFailed()

    def _onReadException(self, *args):
        """Handle read.so exception callback."""
        self._reader = None
        if self._progressbar is not None:
            self._progressbar.hide()
        self._state = self.STATE_READ_FAILED
        self._showReadFailed()

    def onReading(self, *args):
        """Callback from read.so — progress and completion.

        Same pattern as ReadListActivity.onReading:
        - Progress dicts: update progress bar
        - Completion dict (has 'success' key): handle read result
        Ground truth: trace_autocopy_mf1k_standard.txt lines 25-105
        """
        if not args:
            return

        data = args[0] if isinstance(args[0], dict) else {}

        # Completion check: 'success' key means read is done.
        # Schedule on Tk main thread — this fires from read background thread.
        if isinstance(data, dict) and 'success' in data:
            self._cancel_fake_progress()
            def _on_complete():
                self._reader = None
                if self._progressbar is not None:
                    self._progressbar.hide()

                success = data.get('success', False)
                ret_code = data.get('return', 0)

                if success:
                    self._read_bundle = data.get('bundle', data.get('tag_info', ''))
                    self._read_data = data
                    if data.get('force'):
                        self._showReadPartialSuccess()
                    else:
                        self._promptSwapCard()
                elif ret_code in (-3, -4):
                    self._state = self.STATE_READ_NO_KEY_HF
                    try:
                        import scan as _scan_mod
                        infos = _scan_mod.getScanCache() or self._scan_result or {}
                    except Exception:
                        infos = self._scan_result or {}
                    actstack.start_activity(WarningM1Activity, {'infos': infos})
                elif ret_code == -2:
                    self._state = self.STATE_READ_FAILED
                    self._showReadFailed()
                elif ret_code == -1:
                    sc = self._scan_result or {}
                    if sc.get('uid'):
                        self._state = self.STATE_READ_FAILED
                        self._showReadFailed()
                    else:
                        self._state = self.STATE_SCAN_WRONG_TYPE
                        self.showScanToast(found=False, wrong_type=True)
                        self._showScanFailButtons()
                else:
                    self._state = self.STATE_READ_FAILED
                    self._showReadFailed()

            try:
                from lib import actstack
                if actstack._root is not None:
                    actstack._root.after(0, _on_complete)
                else:
                    _on_complete()
            except Exception:
                _on_complete()
            return

        # Progress update — fires from read background thread
        self._cancel_fake_progress()
        self._got_progress = True
        progress = data.get('progress', 0) if isinstance(data, dict) else 0
        action = data.get('action', '') if isinstance(data, dict) else ''
        key_idx = data.get('keyIndex', 0) if isinstance(data, dict) else 0
        key_max = data.get('keyCountMax', 0) if isinstance(data, dict) else 0
        seconds = data.get('seconds', 0) if isinstance(data, dict) else 0

        # Timer string — ground truth: "01'08''" (MM'SS'')
        if seconds and int(seconds) > 0:
            mm = int(seconds) // 60
            ss = int(seconds) % 60
            timer = "%02d'%02d''" % (mm, ss)
        else:
            timer = ''

        if action == 'REC_ALL' and key_max > 0:
            msg = resources.get_str('reading_with_keys').format(key_idx, key_max)
        elif action and key_max > 0:
            msg = '%s...%d/%dkeys' % (action, key_idx, key_max)
        elif action:
            msg = action
        else:
            msg = resources.get_str('reading')

        def _update():
            if self._progressbar is not None:
                if progress:
                    self._progressbar.setProgress(int(progress))
                self._progressbar.setMessage(msg)
                self._progressbar.setTimer(timer)

        try:
            from lib import actstack
            if actstack._root is not None:
                actstack._root.after(0, _update)
            else:
                _update()
        except Exception:
            pass

    # _onReadComplete removed — dead code from old Reader API.
    # Read completion now handled by onReading() via Reader.call_reading callback.

    def _showReadFailed(self):
        """Show 'Read Failed!' toast. ProgressBar completes to 100% first."""
        def _after_complete():
            if self._progressbar is not None:
                self._progressbar.hide()
            if self._toast is not None:
                self._toast.show(
                    resources.get_str('read_failed'),
                    mode=Toast.MASK_CENTER,
                    icon='error',
                    duration_ms=0,
                )
            self.setidle()
            self.setLeftButton(resources.get_str('rescan'))
            self.setRightButton(resources.get_str('reread'))
            self._btn_enabled = True
            try:
                import audio
                audio.playReadFail()
            except Exception:
                pass

        if self._progressbar is not None:
            self._progressbar.complete(_after_complete)
        else:
            _after_complete()

    # Read failure UI is handled by Warning activities pushed by read.so
    # or by this activity via actstack.start_activity(WarningM1Activity).
    # Ground truth: read flow tests use M1:Sniff trigger for all key
    # failure states (darkside_fail, nested_fail, hardnested, etc.).

    def _showReadPartialSuccess(self):
        """Show partial read success toast with Reread/Write buttons.

        From binary: 'Read Successful! Partial data saved'
        Allows user to proceed with partial data or reread.
        """
        self._state = self.STATE_PLACE_CARD
        if self._progressbar is not None:
            self._progressbar.hide()
        if self._toast is not None:
            self._toast.show(
                resources.get_str('read_ok_2'),
                mode=Toast.MASK_CENTER,
                icon='check',
                duration_ms=0,
            )
        self.setidle()
        self.setLeftButton(resources.get_str('reread'))
        self.setRightButton(resources.get_str('write'))
        self._btn_enabled = True
        self.place = True
        try:
            import audio
            audio.playReadPart()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Console view (inline, during read)
    # ------------------------------------------------------------------

    # _showConsole, _hideConsole, _handleConsoleKey inherited from ConsoleMixin

    # ------------------------------------------------------------------
    # Place card prompt
    # ------------------------------------------------------------------

    def _promptSwapCard(self):
        """Show read success state with tag info + toast + Reread/Write buttons.

        ProgressBar completes to 100% before transitioning.
        """
        self._state = self.STATE_PLACE_CARD
        self.place = True

        def _after_complete():
            self._doPromptSwapCard()

        if self._progressbar is not None:
            self._progressbar.complete(_after_complete)
        else:
            _after_complete()

    def _doPromptSwapCard(self):
        """Render the swap card prompt after progress bar completes."""
        if self._progressbar is not None:
            self._progressbar.hide()

        # Ensure dump directory exists
        try:
            import appfiles
            appfiles.mkdirs_on_icopy()
        except Exception:
            pass

        # Draw tag info template so it's visible behind the toast
        canvas = self.getCanvas()
        if canvas is not None:
            try:
                import template
                scan_data = self._scan_result or self.scan_infos
                if isinstance(scan_data, dict):
                    tag_type = scan_data.get('type', -1)
                    template.draw(tag_type, scan_data, canvas)
            except Exception:
                pass

        if self._toast is not None:
            self._toast.show(
                resources.get_str('read_ok_1'),
                mode=Toast.MASK_CENTER,
                icon='check',
                duration_ms=0,
            )

        self.setidle()
        self.setLeftButton(resources.get_str('reread'))
        self.setRightButton(resources.get_str('write'))
        self._btn_enabled = True

        try:
            import audio_copy
            audio_copy.playReadyForCopy()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Launch WarningWriteActivity → WriteActivity
    # ------------------------------------------------------------------

    def _launchWrite(self):
        """Push WarningWriteActivity with read bundle.

        Ground truth: trace_autocopy_mf1k_standard.txt line 111-114 —
        START(WarningWriteActivity, '/mnt/upan/dump/mf1/M1-1K-4B_9C750884_1.bin')
        autocopy_mf4k_mf1k7b_t55_trace_20260329.txt lines 13, 552, 715 —
        all three tag types push WarningWriteActivity then WriteActivity.
        """
        try:
            actstack.start_activity(WarningWriteActivity,
                                    self._read_bundle)
        except Exception as e:
            print('[AUTOCOPY] launchWrite error: %s' % e, flush=True)

    def onActivity(self, result):
        """Handle results from child activities (WarningWriteActivity, WriteActivity).

        Ground truth: trace_autocopy_mf1k_standard.txt lines 115-119 —
        FINISH(WarningWriteActivity) → START(WriteActivity, same_bundle)
        Called by actstack.finish_activity() when child finishes with result.
        """
        if result is None:
            return

        action = result.get('action')
        if action == 'write':
            # WarningWriteActivity confirmed — push WriteActivity
            # Ground truth: trace_autocopy_mf1k_standard.txt lines 115-119
            try:
                actstack.start_activity(WriteActivity,
                                        result.get('read_bundle'))
            except Exception as e:
                print('[AUTOCOPY] startWriteActivity error: %s' % e, flush=True)
        elif action == 'force':
            # WarningM1Activity: force-read with partial keys
            # Ground truth: ReadListActivity.onActivity (activity_read.py:121-122)
            self._startRead(force=True)
        elif action == 'sniff':
            # WarningM1Activity: sniff for keys
            try:
                from lib.activity_main import SniffActivity
                actstack.start_activity(SniffActivity)
            except (ImportError, AttributeError):
                pass

    # ------------------------------------------------------------------
    # Write phase — REMOVED (audit finding 1+2)
    # AutoCopy pushes WriteActivity via _launchWrite() -> onActivity().
    # The internal _startWrite/_onWriteComplete/_isLFTag/_startVerify path
    # was middleware: Python reimplemented HF/LF classification that
    # write.so/tagtypes.so already owns. Dead code removed.
    # ------------------------------------------------------------------

    def _startWrite(self):
        """Initiate write: disable buttons, show progress, call write.so.

        From binary:
            1. setBtnEnabled(False)
            2. playWriting() — show "Writing..." progress bar
            3. Launch write.write() on background thread
        """
        self._state = self.STATE_WRITING
        self._btn_enabled = False
        self.place = False

        if self._toast is not None:
            self._toast.cancel()

        # Show writing progress bar
        self.setLeftButton('')
        self.setRightButton('')
        if self._progressbar is not None:
            self._progressbar.setMessage(resources.get_str('writing'))
            self._progressbar.setProgress(0)
            self._progressbar.show()

        # Play writing audio
        try:
            import audio
            audio.playWriting()
        except Exception:
            pass

        # Dispatch to write.so on background thread
        try:
            import write as _write_mod
            import threading
            def _do_write():
                try:
                    ret = _write_mod.write(self._read_data, self)
                    self._onWriteComplete(ret)
                except Exception:
                    self._onWriteComplete('write_failed')
            t = threading.Thread(target=_do_write, daemon=True)
            t.start()
        except ImportError:
            # write.so not available (test environment)
            # Stay in WRITING state — test must call _onWriteComplete() directly
            pass

    # _onWriteComplete and _isLFTag REMOVED — audit findings 1+2.
    # _isLFTag was middleware: hardcoded LF type set deciding whether to
    # auto-verify. Write/verify is now handled by WriteActivity (pushed
    # via _launchWrite -> onActivity). These methods are unreachable.

    def _showWriteSuccess(self):
        """Show 'Write successful!' toast with Rescan/Rescan buttons."""
        self.setidle()
        if self._toast is not None:
            self._toast.show(
                resources.get_str('write_success'),
                mode=Toast.MASK_CENTER,
                icon='check',
                duration_ms=0,
            )
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('rescan'))
        self._btn_enabled = True
        try:
            import audio
            audio.playWriteSuccess()
        except Exception:
            pass

    def _showWriteFailed(self):
        """Show 'Write failed!' toast with Rescan/Rewrite buttons."""
        self.setidle()
        if self._toast is not None:
            self._toast.show(
                resources.get_str('write_failed'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('rewrite'))
        self._btn_enabled = True
        try:
            import audio
            audio.playWriteFail()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Verify phase
    # ------------------------------------------------------------------

    def _startVerify(self):
        """Initiate verify: disable buttons, show progress, call write.so.

        From binary: auto-triggered after LF write success.
        """
        self._state = self.STATE_VERIFYING
        self._btn_enabled = False

        if self._toast is not None:
            self._toast.cancel()

        # Show verifying progress bar
        self.setLeftButton('')
        self.setRightButton('')
        if self._progressbar is not None:
            self._progressbar.setMessage(resources.get_str('verifying'))
            self._progressbar.setProgress(0)
            self._progressbar.show()

        # Play verifying audio
        try:
            import audio
            audio.playVerifying()
        except Exception:
            pass

        # Dispatch to write.so verify on background thread
        try:
            import write as _write_mod
            import threading
            def _do_verify():
                try:
                    ret = _write_mod.verify(self._read_data, self)
                    self._onVerifyComplete(ret)
                except Exception:
                    self._onVerifyComplete('verify_failed')
            t = threading.Thread(target=_do_verify, daemon=True)
            t.start()
        except ImportError:
            # write.so not available (test environment)
            # Stay in VERIFYING state — test must call _onVerifyComplete()
            pass

    def _onVerifyComplete(self, result):
        """Handle verify completion — show success/fail toast.

        From binary:
            verify_success -> 'Write and Verify successful!' (write_verify_success)
            verify_failed  -> 'Verification failed!'
        """
        if self._progressbar is not None:
            self._progressbar.hide()

        if result == 'verify_success':
            self._state = self.STATE_VERIFY_SUCCESS
            self._showVerifySuccess()
        else:
            self._state = self.STATE_VERIFY_FAILED
            self._showVerifyFailed()

    def _showVerifySuccess(self):
        """Show 'Write and Verify successful!' toast.

        Note: AutoCopy uses 'write_verify_success' (combined message),
        NOT the separate 'verify_success' used by WriteActivity.
        """
        self.setidle()
        if self._toast is not None:
            self._toast.show(
                resources.get_str('write_verify_success'),
                mode=Toast.MASK_CENTER,
                icon='check',
                duration_ms=0,
            )
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('rescan'))
        self._btn_enabled = True
        try:
            import audio
            audio.playVerifiSuccess()
        except Exception:
            pass

    def _showVerifyFailed(self):
        """Show 'Verification failed!' toast with Rescan/Rewrite buttons."""
        self.setidle()
        if self._toast is not None:
            self._toast.show(
                resources.get_str('verify_failed'),
                mode=Toast.MASK_CENTER,
                icon='error',
                duration_ms=0,
            )
        self.setLeftButton(resources.get_str('rescan'))
        self.setRightButton(resources.get_str('rewrite'))
        self._btn_enabled = True
        try:
            import audio
            audio.playVerifiFail()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Properties for testing
    # ------------------------------------------------------------------

    @property
    def state(self):
        """Current state (for testing)."""
        return self._state

    @property
    def btn_enabled(self):
        """Whether buttons are enabled (for testing)."""
        return self._btn_enabled



# =====================================================================
# A-21: SimulationActivity
# =====================================================================

SIM_MAP = [
    ('M1 S50 1k',     1,  'HF', 'hf_4b',     'uid',     'hf 14a sim -t 1 --uid {}'),
    ('M1 S70 4k',     0,  'HF', 'hf_4b',     'uid',     'hf 14a sim -t 2 --uid {}'),
    ('Ultralight',    2,  'HF', 'single_7b', 'uid',     'hf 14a sim -t 7 --uid {}'),
    ('Ntag215',       6,  'HF', 'single_7b', 'uid',     'hf 14a sim -t 8 --uid {}'),
    ('FM11RF005SH',   40, 'HF', 'single_4b', 'uid',     'hf 14a sim -t 9 --uid {}'),
    ('Em410x ID',     8,  'LF', 'lf_4b',     'uid',     'lf em 410x sim --id {}'),
    ('HID Prox ID',   9,  'LF', 'lf_5b',     'data',    'lf hid sim -r {}'),
    ('AWID ID',       11, 'LF', 'lf_awid',   'fccn',    'lf awid sim --fmt {} --fc {} --cn {}'),
    ('IO Prox ID',    12, 'LF', 'lf_io',     'ioporx',  'lf io sim --vn {} --fc {} --cn {}'),
    ('G-Prox II ID',  13, 'LF', 'lf_gporx',  'fccn',    'lf gproxii sim --xor 0 --fmt {} --fc {} --cn {}'),
    ('Viking ID',     15, 'LF', 'single_4b', 'uid',     'lf viking sim --cn {}'),
    ('Pyramid ID',    16, 'LF', 'lf_pyramid','pyramid', 'lf pyramid sim --fc {} --cn {}'),
    ('Jablotron ID',  30, 'LF', 'lf_jab',    'jabdat',  'lf jablotron sim --cn {}'),
    ('Nedap ID',      32, 'LF', 'lf_nedap',  'nedap',   'lf nedap sim --st {} --cc {} --id {}'),
    ('FDX-B Animal',  28, 'LF', 'lf_fdx_a',  'fdx',     'lf fdxb sim --country {} --national {} --animal'),
    ('FDX-B Data',    28, 'LF', 'lf_fdx_d',  'fdx',     'lf fdxb sim --country {} --national {} --extended {}'),
]

# QEMU-verified defaults from real .so binary (sim_common.sh lines 203-210).
# These MUST match what the binary's draw_* methods render.
# Effective max = min(doc_max, 10^field_digits - 1) for decimal fields.
# Ground truth: UI Mapping §4.5-4.12, FB state_032 (Nedap Subtype > 15),
# field length from QEMU-verified defaults (sim_common.sh lines 203-210).
SIM_FIELDS = {
    'hf_4b':     [('UID:', '12345678',         'hex', 8)],
    'single_7b': [('UID:', '123456789ABCDE',   'hex', 14)],
    'single_4b': [('UID:', '12345678',         'hex', 8)],
    'lf_4b':     [('UID:', '1234567890',       'hex', 10)],
    'lf_5b':     [('ID:',  '112233445566',     'hex', 12)],
    'lf_awid':   [('Format:', '50',   'dec', 99),       # 2 digits max 99
                  ('FC:',  '2001',    'dec', 9999),      # 4 digits max 9999
                  ('CN:',  '13371337','dec', 99999999)],  # 8 digits, .so passes raw (user confirmed)
    'lf_io':     [('Version:', '01', 'hex', 2),
                  ('FC:',  'FF',    'hex', 2),
                  ('CN:',  '65535', 'dec', 65536)],        # 5 digits, original toast: "CN greater than 65536"
    'lf_gporx':  [('Format:', '26', 'dec', 99),          # 2 digits max 99
                  ('FC:',  '255',  'dec', 999),           # 3 digits, original passes FC=346 (no validation catch)
                  ('CN:',  '65535','dec', 65535)],         # 5 digits, 0xFFFF chipset max
    'lf_pyramid':[('FC:',  '255',  'dec', 255),           # 3 digits, original toast: "FC greater than 255"
                  ('CN:',  '65536','dec', 99999)],         # 5 digits max 99999
    'lf_jab':    [('ID:',  '1C6AEB', 'hex', 6)],
    'lf_nedap':  [('Subtype:', '15', 'dec', 15),          # FB proof: max 15, decimal display
                  ('CN:',  '999',   'dec', 999),          # 3 digits max 999 (doc: 65535)
                  ('ID:',  '99999', 'dec', 65535)],        # 5 digits, doc max 65535
    'lf_fdx_a':  [('Country:', '999', 'dec', 999),        # 10-bit ISO 11784, max 999 usable
                  ('NC:',  '112233445566', 'dec', 274877906943)],  # 38-bit ISO 11784 national ID
    'lf_fdx_d':  [('Country:', '999', 'dec', 999),        # 10-bit ISO 11784, max 999 usable
                  ('NC:',  '112233445566', 'dec', 274877906943),  # 38-bit ISO 11784 national ID
                  ('Animal Bit:', '0', 'dec', 1)],         # 1-bit animal application indicator
}

# Initialize _SIMULATE_TYPES from SIM_MAP (audit finding 3)
_SIMULATE_TYPES = frozenset(entry[1] for entry in SIM_MAP)


class SimulationActivity(BaseActivity):
    """Tag emulation. Select type -> enter UID/params -> simulate.

    Binary source: activity_main.so SimulationActivity (52 methods)
    Spec: docs/UI_Mapping/06_simulation/README.md
    """
    ACT_NAME = 'simulation'
    STATE_LIST = 'list_view'
    STATE_SIM_UI = 'sim_ui'
    STATE_SIMULATING = 'simulating'

    def __init__(self, bundle=None):
        self._state = self.STATE_LIST
        self._listview = None
        self._toast = None
        self._sim_entry = None
        self._input_methods = []
        self._focus_idx = 0
        self._editing = False
        self._sim_stopping = False
        self._auto_start = False
        self._defdata = None
        self._defbundle = None
        self._trace_data = None
        self._last_pm3_cmd = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        if bundle and isinstance(bundle, dict):
            # Ground truth (original trace lines 50, 84):
            #   Scan/Dump callers pass full scan cache dict:
            #     {'uid':'DAEFB416','type':1,'len':4,'sak':'08',...}
            #   Simulation auto-starts immediately (0.45s after START).
            #   Detect scan cache format by 'type' key presence.
            tag_type = bundle.get('type')
            if tag_type is not None:
                # Scan cache dict — resolve sim_index from type ID
                sim_idx = None
                for i, entry in enumerate(SIM_MAP):
                    if entry[1] == tag_type:
                        sim_idx = i
                        break
                if sim_idx is not None:
                    self._sim_entry = SIM_MAP[sim_idx]
                    # Extract UID/data using the appropriate parser
                    data_key = self._sim_entry[4]  # 'uid', 'data', 'fccn', etc.
                    self._defdata = bundle.get('uid', bundle.get('data', ''))
                    # Keep the full scan bundle so _showSimUi can populate
                    # multi-field forms (FC/CN/Subtype/etc.) from individual
                    # keys (bundle['fc'], bundle['cn'], ...) rather than
                    # stuffing the formatted 'data' string into field 0.
                    self._defbundle = bundle
                    self._auto_start = True
                    self._showSimUi()
                    self._startSimForData()
                    return
            else:
                # Legacy format: {'sim_index': N, 'defdata': '...'}
                self._defdata = bundle.get('defdata')
                self._auto_start = bundle.get('auto_start', False)
                sim_idx = bundle.get('sim_index')
                if sim_idx is not None and 0 <= sim_idx < len(SIM_MAP):
                    self._sim_entry = SIM_MAP[sim_idx]
                    self._showSimUi()
                    if self._auto_start:
                        self._startSimForData()
                    return
        self._showListUI()

    def _showListUI(self):
        """Show 16-type list with numbered items.

        Ground truth (FB captures simulation_20260403):
          state_002: "1. M1 S50 1k" through "5. FM11RF005SH"
          state_047: "6. Em410x ID" through "10. G-Prox II ID"
          state_055: "11. Viking ID" through "15. Jablotron ID"
          state_058: "16. Nedap ID"
        Title: "Simulation X/4" (page indicator)
        No button labels in list view.
        """
        self._state = self.STATE_LIST
        self._editing = False
        self._input_methods = []
        # Clean up SimFields widget if it exists (persists across state changes)
        sf = getattr(self, '_sim_fields', None)
        if sf is not None:
            sf.hide()
            self._sim_fields = None
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete('sim_content')
        # Numbered items: "1. M1 S50 1k" (1-based, matching real device)
        items = ['%d. %s' % (i + 1, entry[0]) for i, entry in enumerate(SIM_MAP)]
        from lib.widget import ListView
        self._listview = ListView(canvas)
        self._listview.setItems(items)
        self._listview._on_page_change = self._onPageChange
        self._listview.show()
        # Ground truth (FB state_002): list view has NO button bar.
        # dismissButton() removes text AND background bar.
        # setLeftButton('') only removes text, leaving the dark bar visible.
        self.dismissButton()
        self._updateTitle()

    def _showSimUi(self):
        """Show input fields for selected type with type name + field labels.

        Ground truth (FB captures simulation_20260403):
          state_003: "M1 S50 1k" blue text + "UID:" label + input cells
          state_004: Stop/Start buttons
          state_025: "Ultralight" + "UID:" label + 14 hex cells
        Title: "Simulation" (no page indicator in sim UI)
        M1="Stop", M2="Start"
        """
        self._state = self.STATE_SIM_UI
        self._editing = False
        self._focus_idx = 0
        if self._listview is not None:
            self._listview.hide()
        # Clean up any existing SimFields before creating new ones.
        # Each _showSimUi call creates a new SimFields with a unique canvas tag.
        # Without cleanup, old instances' canvas items persist underneath.
        sf = getattr(self, '_sim_fields', None)
        if sf is not None:
            sf.hide()
            self._sim_fields = None
        self.setTitle(resources.get_str('simulation'))
        self.setLeftButton(resources.get_str('stop'), active=False)
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None or self._sim_entry is None:
            return
        canvas.delete('sim_content')

        # Type name in blue text (ground truth: FB state_003 "M1 S50 1k" in blue)
        type_name = self._sim_entry[0]
        canvas.create_text(SCREEN_W // 2, 60, text=type_name,
                           fill=COLOR_ACCENT, font=('mononoki', 14),
                           anchor='center', tags='sim_content')

        # Build fields using SimFields widget (FB ground truth: gray boxes)
        draw_key = self._sim_entry[3]
        fields = SIM_FIELDS.get(draw_key, [])
        from lib.widget import SimFields
        self._sim_fields = SimFields(canvas, y_start=78)
        # Label → scan-cache bundle key.  When the activity was entered
        # from a scan (self._defbundle is set), the field's default is
        # replaced by the matching cache key.  Without this lookup every
        # scanned multi-field tag (Pyramid, AWID, KERI, IOProx, GProxII,
        # Paradox, etc.) stuffed the formatted display string
        # (e.g. "FC,CN: 153,39312") into field 0 and the PM3 sim command
        # then rejected the bad input.  Labels that aren't mapped fall
        # through to the widget default — avoids corrupting Nedap/FDX
        # specific fields when we don't know the cache-key naming.
        _LABEL_TO_CACHE_KEY = {
            'UID:': ('uid', 'data'),
            'ID:':  ('data', 'raw'),
            'FC:':  ('fc',),
            'CN:':  ('cn',),
            'Format:': ('len',),
            'Country:': ('country',),
            'NC:':  ('nc',),
            'Version:': ('vn',),   # IO Prox XSF version field
        }
        for i, (label, default, input_type, max_val) in enumerate(fields):
            fmt = 'hex' if input_type in ('hex', 'hex_val') else ('dec' if input_type == 'dec' else 'sel')
            val = default
            # Prefer per-label lookup from scan bundle when available.
            if isinstance(self._defbundle, dict):
                for k in _LABEL_TO_CACHE_KEY.get(label, ()):
                    v = self._defbundle.get(k)
                    if v not in (None, '', 'X'):  # 'X' = lfsearch "unknown FC"
                        val = v
                        break
            # Fallback: legacy single-defdata path (first field only)
            # preserves behaviour for non-scan entrypoints (Dump Files)
            # where the bundle has {'sim_index': N, 'defdata': '...'}.
            elif i == 0 and self._defdata:
                val = self._defdata
            self._sim_fields.addField(label, val, fmt, max_val)
        self._sim_fields.show()
        self._focus_idx = 0

    def _startSimForData(self):
        if self._sim_entry is None:
            return
        values = self._getAllInput()
        draw_key = self._sim_entry[3]
        if not self._validateInputs(draw_key, values):
            return
        cmd_template = self._sim_entry[5]
        try:
            cmd = cmd_template.format(*values)
        except (IndexError, KeyError):
            cmd = cmd_template
        self._last_pm3_cmd = cmd
        self._startSim(cmd)

    def _validateInputs(self, draw_key, values):
        """Validate input fields against max values.

        Ground truth: chk_max_comm (generic), chk_ioid_input, chk_gproxid_input,
        chk_pyramid_input, chk_nedap_input (type-specific).
        FB state_032: "Input invalid: 'Subtype' greater than 15"
        """
        fields = SIM_FIELDS.get(draw_key, [])
        for i, (label, _default, input_type, max_val) in enumerate(fields):
            if i >= len(values):
                break
            if input_type == 'dec':
                try:
                    val = int(values[i])
                    if val > max_val:
                        msg = resources.get_str('sim_valid_input').format(
                            label.rstrip(':'), max_val)
                        if self._toast:
                            self._toast.show(msg, duration_ms=0)
                        return False
                except ValueError:
                    if self._toast:
                        self._toast.show(resources.get_str('sim_valid_param'), duration_ms=0)
                    return False
            elif input_type == 'hex_val':
                # Hex display but decimal max validation (Nedap Subtype: max 15)
                try:
                    val = int(values[i], 16)
                    if val > max_val:
                        msg = resources.get_str('sim_valid_input').format(
                            label.rstrip(':'), max_val)
                        if self._toast:
                            self._toast.show(msg, duration_ms=0)
                        return False
                except ValueError:
                    if self._toast:
                        self._toast.show(resources.get_str('sim_valid_param'), duration_ms=0)
                    return False
        return True

    def _getAllInput(self):
        sf = getattr(self, '_sim_fields', None)
        if sf:
            return sf.getAllValues()
        return []

    def _startSim(self, cmd):
        """Start PM3 simulation.

        Ground truth (FB state_010): buttons remain Stop/Start during sim.
        """
        self._state = self.STATE_SIMULATING
        self._sim_stopping = False
        self.setbusy()
        self.setLeftButton(resources.get_str('stop'))
        self.setRightButton(resources.get_str('start'), active=False)
        # Ground truth: original device toast persists during entire simulation
        # until Stop is pressed. duration_ms=0 = persistent (no auto-dismiss).
        if self._toast:
            self._toast.show(resources.get_str('simulating'), duration_ms=0)
        # Start PM3 simulation on background thread.
        # Ground truth: trace_scan_flow_20260331.txt line 73:
        #   PM3> hf 14a sim t 1 u 3AF73501  (timeout=-1)
        # Both HF and LF use timeout=-1 (audit finding 5: no ground truth
        # for LF 30000 value). LF commands self-terminate. HF runs until
        # stopPM3Task(). The .so binary's startSim uses the same timeout
        # for both (documented at activity_main_strings.txt line 21110).
        timeout = -1
        import threading
        def _run_sim():
            try:
                from lib import executor
                executor.startPM3Task(cmd, timeout)
            except Exception:
                pass
            self._onSim()
        threading.Thread(target=_run_sim, daemon=True).start()

    def _stopSim(self):
        self._sim_stopping = True
        self.setidle()
        # Show Processing... toast during stop
        # Ground truth: binary text_processing (line 21479),
        # FB states 045 (Nedap) + 086 (AWID) show "Processing..." on stop
        if self._toast:
            self._toast.show(resources.get_str('processing'), duration_ms=0)
        # Ground truth (activity_main_strings.txt:22200 near stopSim/sim_stopping):
        # Original .so calls hmi_driver.presspm3() BEFORE stopPM3Task().
        # presspm3 sends "presspm3" via GD32 serial, which physically presses
        # the PM3 button, causing the simulation to stop cleanly and output
        # "Emulator stopped. Trace length: N".  Without this, stopPM3Task
        # just sets STOPPING flag — PM3 never receives a stop signal,
        # returns ret=-1 with empty content, triggering rework cascade.
        # Original trace: M1 → presspm3 → PM3 returns ret=1 in 100ms.
        try:
            import hmi_driver
            hmi_driver.presspm3()
        except Exception:
            pass
        try:
            from lib import executor
            executor.stopPM3Task()
        except (ImportError, AttributeError):
            pass
        # Reset state BEFORE pushing trace activity. If TraceActivity is
        # later popped (PWR/Cancel), SimulationActivity resumes in SIM_UI
        # state — not SIMULATING (which would re-trigger _stopSim on PWR).
        self._state = self.STATE_SIM_UI
        self._sim_stopping = False
        if self._sim_entry and self._sim_entry[2] == 'HF':
            self._on14ASimStop()
        else:
            # LF sims redraw the sim UI in-place; dismiss the transient
            # "Processing..." toast once the UI is back (HF path hands off
            # to SimulationTraceActivity which shows its own toast, so
            # only LF needs the explicit cancel).  Without this the toast
            # stays visible forever over the sim fields.
            self._showSimUi()
            if self._toast:
                try:
                    self._toast.cancel()
                except Exception:
                    pass

    def _onSim(self, result=None):
        self.setidle()
        # Guard: if _stopSim() already handled the HF stop sequence,
        # don't call _on14ASimStop again from the bg thread.
        # Ground truth: original trace shows only ONE SimulationTraceActivity
        # push per stop. OSS trace showed double push → crash.
        if self._sim_stopping:
            return
        if self._sim_entry and self._sim_entry[2] == 'HF':
            self._on14ASimStop()
        else:
            self._showSimUi()

    def _on14ASimStop(self):
        """Fetch trace and push SimulationTraceActivity for HF sim.

        Ground truth:
          trace_oss_simulate_original_fw_20260412.txt lines 21-24:
            START(SimulationTraceActivity, None)
            PM3> hf 14a list (timeout=18888)
            PM3< ret=1 content_len=31486 (trace data)
          FB state_070: "Trace Loading..." toast during fetch
          FB state_015: "TraceLen: 1119" in Trace screen
        """
        # Push SimulationTraceActivity in loading state (shows "Trace Loading...")
        actstack.start_activity(SimulationTraceActivity,
                                {'trace_data': None, 'trace_len': 0, 'loading': True})

        # Fetch trace on bg thread — must NOT block Tk main thread.
        # Original trace: hf 14a list takes ~3s. Blocking the main thread
        # freezes the UI and prevents key events.
        import threading
        def _fetch_trace():
            trace_text = ''
            try:
                from lib import executor
                executor.startPM3Task('hf 14a list', 18888)
                trace_text = getattr(executor, 'CONTENT_OUT_IN__TXT_CACHE', '') or ''
            except Exception:
                pass

            # Parse trace length
            trace_len = 0
            try:
                import sniff as _sniff_mod
                trace_len = _sniff_mod.parserTraceLen() or 0
            except Exception:
                import re
                m = re.search(r'trace len\s*=\s*(\d+)', trace_text)
                if m:
                    trace_len = int(m.group(1))

            self._trace_data = trace_text
            # Update the trace activity on the Tk thread (thread safety)
            def _update():
                try:
                    top = actstack.get_current_activity()
                    if isinstance(top, SimulationTraceActivity):
                        top._trace_data = trace_text
                        top._trace_len = trace_len
                        top._showResult()
                except Exception:
                    pass
            if actstack._root is not None:
                actstack._root.after(0, _update)
            else:
                _update()
        threading.Thread(target=_fetch_trace, daemon=True).start()

    def onResume(self):
        """Restore UI when returning from SimulationTraceActivity.

        Ground truth (original trace lines 27-31): after exiting trace view,
        SimulationActivity shows sim UI with Stop (inactive) / Start buttons.
        """
        super().onResume()
        if self._state == self.STATE_SIM_UI:
            self._showSimUi()

    def onKeyEvent(self, key):
        if self._state == self.STATE_LIST:
            self._onKeyList(key)
        elif self._state == self.STATE_SIM_UI:
            self._onKeySimUi(key)
        elif self._state == self.STATE_SIMULATING:
            self._onKeySimulating(key)

    def _onKeyList(self, key):
        """List view key handlers.

        Ground truth: activity_main_strings.txt lines 22199/22210 —
        binary has prevPage/nextPage methods. RIGHT/LEFT change pages.
        """
        if key == KEY_UP:
            if self._listview:
                self._listview.prev()
                self._updateTitle()
        elif key == KEY_DOWN:
            if self._listview:
                self._listview.next()
                self._updateTitle()
        elif key == KEY_RIGHT:
            # Next page — jump forward by page size
            if self._listview:
                page_size = self._listview._max_display
                for _ in range(page_size):
                    self._listview.next()
                self._updateTitle()
        elif key == KEY_LEFT:
            # Previous page — jump back by page size
            if self._listview:
                page_size = self._listview._max_display
                for _ in range(page_size):
                    self._listview.prev()
                self._updateTitle()
        elif key in (KEY_M2, KEY_OK):
            self._selectType()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()

    def _onKeySimUi(self, key):
        """Sim UI key handlers — delegates to SimFields widget.

        Ground truth (FB captures + test infrastructure):
          UP/DOWN not editing: move focus arrow between fields
          OK: enter/exit edit mode on focused field
          UP/DOWN editing: change digit at cursor
          LEFT/RIGHT editing: move cursor within field
          M1 not editing: back to list (Stop)
          M1 editing: exit edit mode
          M2 not editing: start simulation
          PWR: back to list
        """
        sf = getattr(self, '_sim_fields', None)
        if key == KEY_OK:
            if sf:
                if sf.editing:
                    sf.exitEdit()
                else:
                    sf.enterEdit()
            self._editing = sf.editing if sf else False
        elif key == KEY_M1:
            if sf and sf.editing:
                sf.exitEdit()
                self._editing = False
            elif self._defbundle is not None:
                # Entered from scan/dump — M1 pops back to caller, not list.
                self.finish()
            else:
                self._showListUI()
        elif key == KEY_M2:
            if not (sf and sf.editing):
                self._startSimForData()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            if self._defbundle is not None:
                # Entered from scan/dump — PWR pops back to caller, not list.
                self.finish()
            else:
                self._showListUI()
        elif key == KEY_UP:
            if sf:
                if sf.editing:
                    sf.rollUp()
                else:
                    sf.focusPrev()
        elif key == KEY_DOWN:
            if sf:
                if sf.editing:
                    sf.rollDown()
                else:
                    sf.focusNext()
        elif key == KEY_LEFT:
            if sf and sf.editing:
                sf.cursorLeft()
        elif key == KEY_RIGHT:
            if sf and sf.editing:
                sf.cursorRight()

    def _onKeySimulating(self, key):
        """M1="Stop" stops simulation. PWR also stops.

        Ground truth: FB state_010 shows M1="Stop", M2="Start" during sim.
        M1 is the stop action. M2 is labeled "Start" (inactive during sim).
        Audit finding 10+11: M1 stops, not M2.
        """
        if key == KEY_M1:
            self._stopSim()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._stopSim()

    def _selectType(self):
        if self._listview is None:
            return
        sel = self._listview.selection()
        if 0 <= sel < len(SIM_MAP):
            self._sim_entry = SIM_MAP[sel]
            self._showSimUi()

    def _onPageChange(self, page):
        self._updateTitle()

    def _updateTitle(self):
        if self._listview is None:
            return
        total = len(SIM_MAP)
        ipp = self._listview._max_display
        pages = max(1, (total + ipp - 1) // ipp)
        cur = (self._listview.selection() // ipp) + 1
        self.setTitle('{} {}/{}'.format(
            resources.get_str('simulation'), cur, pages))

    @staticmethod
    def getSimMap():
        return list(SIM_MAP)

    @staticmethod
    def filter_space(text):
        return '' if text is None else text.replace(' ', '').strip()

    @staticmethod
    def parserUID(data):
        if not data:
            return None
        import re
        m = re.search(r'UID\s*[:\s]+([0-9A-Fa-f\s]+)', data)
        return m.group(1).replace(' ', '').strip() if m else None

    @staticmethod
    def parserData(data):
        if not data:
            return None
        import re
        m = re.search(r'(?:Data|RAW)\s*[:\s]+([0-9A-Fa-f\s]+)', data)
        return m.group(1).strip() if m else None

    @staticmethod
    def parserFCCN(data):
        if not data:
            return None
        import re
        fc = re.search(r'FC\s*[:\s]+(\d+)', data, re.IGNORECASE)
        cn = re.search(r'CN\s*[:\s]+(\d+)', data, re.IGNORECASE)
        return (fc.group(1), cn.group(1)) if fc and cn else None

    @staticmethod
    def parserPyramid(data):
        return SimulationActivity.parserFCCN(data)

    @staticmethod
    def parserIoPorx(data):
        if not data:
            return None
        import re
        m = re.search(
            r'Version\s*[:\s]+(\d+).*?FC\s*[:\s]+(\d+).*?CN\s*[:\s]+(\d+)',
            data, re.IGNORECASE | re.DOTALL)
        return (m.group(1), m.group(2), m.group(3)) if m else None

    @staticmethod
    def parserJabDat(data):
        if not data:
            return None
        import re
        m = re.search(r'(?:Raw|ID)\s*[:\s]+([0-9A-Fa-f\s]+)', data, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def parserFdx(data):
        if not data:
            return None
        import re
        result = {}
        co = re.search(r'Country\s*[:\s]+(\d+)', data, re.IGNORECASE)
        nid = re.search(r'(?:National|ID)\s*(?:code|id)?\s*[:\s]+(\d+)',
                        data, re.IGNORECASE)
        if co:
            result['country'] = co.group(1)
        if nid:
            result['national_id'] = nid.group(1)
        animal = re.search(r'Animal\s*[:\s]+(\d+)', data, re.IGNORECASE)
        if animal:
            result['animal'] = animal.group(1)
        return result if result else None

    @staticmethod
    def parserNedap(data):
        if not data:
            return None
        import re
        result = {}
        sub = re.search(r'Subtype\s*[:\s]+(\d+)', data, re.IGNORECASE)
        cn = re.search(r'CN\s*[:\s]+(\d+)', data, re.IGNORECASE)
        nid = re.search(r'ID\s*[:\s]+(\d+)', data, re.IGNORECASE)
        if sub:
            result['subtype'] = sub.group(1)
        if cn:
            result['cn'] = cn.group(1)
        if nid:
            result['id'] = nid.group(1)
        return result if result else None

    @staticmethod
    def chk_max_comm(value, max_val):
        try:
            return int(value) <= max_val
        except (ValueError, TypeError):
            return False


class SimulationTraceActivity(BaseActivity):
    """Trace viewer for captured HF simulation data.

    Ground truth (FB captures simulation_20260403):
      state_015: title="Trace", "TraceLen: 1119", Cancel/Save buttons
      state_063: "TraceLen: 0" — Save button inactive
      state_040: "Trace file saved" toast, Save becomes inactive
      state_070: "Trace Loading..." during fetch

    Binary: SimulationTraceActivity.showResult, SimulationTraceActivity.saveSniffData
    Resources: sniff_trace="TraceLen: {}", trace_saved="Trace file\nsaved",
               processing="Processing...", trace_loading="Trace\nLoading..."
    """
    ACT_NAME = 'simulation_trace'

    def __init__(self, bundle=None):
        self._trace_data = None
        self._trace_len = 0
        self._toast = None
        self._saved = False
        super().__init__(bundle)

    def onCreate(self, bundle):
        self.setTitle(resources.get_str('trace'))
        self.setLeftButton(resources.get_str('cancel'))  # FB: "Cancel" (not "Back")
        self.setRightButton(resources.get_str('save'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        loading = False
        if bundle and isinstance(bundle, dict):
            self._trace_data = bundle.get('trace_data')
            self._trace_len = bundle.get('trace_len', 0)
            loading = bundle.get('loading', False)
        if loading:
            # FB state_014/070: "Trace Loading..." on trace screen, NO buttons
            self.setLeftButton('')
            self.setRightButton('')
            self._toast.show(resources.get_str('trace_loading'), duration_ms=0)
        else:
            self._showResult()

    def _showResult(self):
        """Display "TraceLen: N" centered on screen.

        Ground truth (FB state_015): single line "TraceLen: 1119" centered.
        Uses resources.get_str('sniff_trace').format(N) = "TraceLen: N"
        """
        if self._toast:
            self._toast.cancel()
        canvas = self.getCanvas()
        if canvas is None:
            return
        canvas.delete('trace_content')
        display = resources.get_str('sniff_trace').format(self._trace_len)
        canvas.create_text(SCREEN_W // 2, SCREEN_H // 2, text=display,
                           fill=NORMAL_TEXT_COLOR, font=('mononoki', 13),
                           anchor='center', tags='trace_content')
        # Show buttons now that data is loaded
        self.setLeftButton(resources.get_str('cancel'))
        self._updateSaveButton()

    def _updateSaveButton(self):
        """Enable/disable Save based on trace_len and saved state.

        Ground truth: TraceLen=0 → Save inactive. After save → Save inactive.
        """
        if self._trace_len > 0 and not self._saved:
            self.setRightButton(resources.get_str('save'))
        else:
            # Show "Save" dimmed (FB state_063: text visible but inactive)
            self.setRightButton(resources.get_str('save'), active=False)

    def _saveSniffData(self):
        """Save trace data via sniff.saveSniffData().

        Ground truth (FB state_040): "Trace file saved" toast after save.
        Binary: SimulationTraceActivity.saveSniffData (line 20635).
        Audit finding 8: must call actual save, not just show toast.
        """
        if self._saved or self._trace_len == 0:
            return
        if self._toast:
            self._toast.show(resources.get_str('processing'), duration_ms=0)
        # Actual save via sniff.so (same as SniffActivity._saveSniffData)
        try:
            import sniff as _sniff_mod
            _sniff_mod.saveSniffData()
        except Exception:
            pass
        self._saved = True
        if self._toast:
            self._toast.show(resources.get_str('trace_saved'), duration_ms=0)
        self._updateSaveButton()

    def onKeyEvent(self, key):
        if key in (KEY_M2, KEY_OK):
            self._saveSniffData()
        elif key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()


# =====================================================================
# A-22: CardWalletActivity (Dump Files)
# =====================================================================

DUMP_DIRS = {
    'mf1': '/mnt/upan/dump/mf1/', 'mfu': '/mnt/upan/dump/mfu/',
    'em410x': '/mnt/upan/dump/em410x/', 'hid': '/mnt/upan/dump/hid/',
    'indala': '/mnt/upan/dump/indala/', 'awid': '/mnt/upan/dump/awid/',
    'ioprox': '/mnt/upan/dump/ioprox/', 'gproxii': '/mnt/upan/dump/gproxii/',
    'securakey': '/mnt/upan/dump/securakey/', 'viking': '/mnt/upan/dump/viking/',
    'pyramid': '/mnt/upan/dump/pyramid/', 'iclass': '/mnt/upan/dump/iclass/',
    'icode': '/mnt/upan/dump/icode/', 'legic': '/mnt/upan/dump/legic/',
    'felica': '/mnt/upan/dump/felica/', 'hf14a': '/mnt/upan/dump/hf14a/',
    't55xx': '/mnt/upan/dump/t55xx/', 'em4x05': '/mnt/upan/dump/em4x05/',
    'fdx': '/mnt/upan/dump/fdx/', 'gallagher': '/mnt/upan/dump/gallagher/',
    'jablotron': '/mnt/upan/dump/jablotron/', 'keri': '/mnt/upan/dump/keri/',
    'nedap': '/mnt/upan/dump/nedap/', 'noralsy': '/mnt/upan/dump/noralsy/',
    'pac': '/mnt/upan/dump/pac/', 'paradox': '/mnt/upan/dump/paradox/',
    'presco': '/mnt/upan/dump/presco/', 'visa2000': '/mnt/upan/dump/visa2000/',
    'nexwatch': '/mnt/upan/dump/nexwatch/',
}

# Fixed type order from original firmware (QEMU-verified, HANDOVER.md line 77).
# (display_name, dump_dir_key) — indices match test scenario type_index values.
# Display names match original firmware exactly (verified via original QEMU test
# results: dump_types_empty/scenario_states.json).
DUMP_TYPE_ORDER = [
    ('Viking ID',          'viking'),     # 0
    ('Ultralight & NTAG',  'mfu'),        # 1
    ('Visa2000 ID',        'visa2000'),   # 2
    ('HID Prox ID',        'hid'),        # 3
    ('Mifare Classic',     'mf1'),        # 4
    ('Animal ID(FDX)',     'fdx'),        # 5
    ('Paradox ID',         'paradox'),    # 6
    ('Jablotron ID',       'jablotron'),  # 7
    ('Pyramid ID',         'pyramid'),    # 8
    ('Noralsy ID',         'noralsy'),    # 9
    ('NexWatch ID',        'nexwatch'),   # 10
    ('Securakey ID',       'securakey'),  # 11
    ('Felica',             'felica'),     # 12
    ('KERI ID',            'keri'),       # 13
    ('IO Prox ID',         'ioprox'),     # 14
    ('AWID ID',            'awid'),       # 15
    ('Legic Mini 256',     'legic'),      # 16
    ('T5577 ID',           't55xx'),      # 17
    ('15693 ICODE, STSA',  'icode'),      # 18
    ('EM410x ID',          'em410x'),     # 19
    ('PAC ID',             'pac'),        # 20
    ('GProx II ID',        'gproxii'),    # 21
    ('NEDAP ID',           'nedap'),      # 22
    ('GALLAGHER ID',       'gallagher'),  # 23
    ('Presco ID',          'presco'),     # 24
    ('Indala ID',          'indala'),     # 25
    ('iClass',             'iclass'),     # 26
    ('EM4X05 ID',          'em4x05'),     # 27
]


class CardWalletActivity(BaseActivity):
    """Dump file browser: Type List -> File List -> push ReadFromHistoryActivity.

    Binary source: activity_main.so CardWalletActivity (16 methods)
    Ground truth: HANDOVER.md, trace_dump_files_20260403.txt
    """
    ACT_NAME = 'dump_files'
    MODE_TYPE_LIST = 'type_list'
    MODE_FILE_LIST = 'file_list'
    MODE_DELETE_CONFIRM = 'delete_confirm'

    def __init__(self, bundle=None):
        self._mode = self.MODE_TYPE_LIST
        self._listview = None
        self._btlv = None
        self._toast = None
        self._dump_dir = None
        self._dump_type_key = None
        self._type_index = 0
        self._file_list = []
        self._is_dump_list_empty = True
        self._selected_file = None
        self._is_dump_show_date = False
        self._visible_types = []
        super().__init__(bundle)

    def onCreate(self, bundle):
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        self._showTypeList()

    def _clearContent(self):
        canvas = self.getCanvas()
        if canvas is None:
            return
        if self._listview:
            self._listview.hide()
            self._listview = None
        if self._btlv:
            self._btlv.hide()
            self._btlv = None
        canvas.delete('dump_content')

    # ------------------------------------------------------------------
    # TYPE LIST
    # ------------------------------------------------------------------
    def _showTypeList(self):
        self._mode = self.MODE_TYPE_LIST
        self._clearContent()
        if self._toast:
            self._toast.cancel()
        self.setLeftButton('')
        self.setRightButton('')
        canvas = self.getCanvas()
        if canvas is None:
            return
        # Ground truth (user report + binary strings listdir/isdir in showDumps):
        # Original firmware ONLY shows tag types that have at least one dump
        # file in their directory.  Types with empty/missing dirs are hidden.
        # Numbers are 1-indexed and right-aligned (leading space for single digits).
        valid_ext = ('.bin', '.eml', '.txt', '.json', '.pm3')
        self._visible_types = []  # indices into DUMP_TYPE_ORDER
        for i, (name, key) in enumerate(DUMP_TYPE_ORDER):
            d = DUMP_DIRS.get(key)
            if d and os.path.isdir(d):
                try:
                    if any(f.lower().endswith(ext)
                           for f in os.listdir(d)
                           for ext in valid_ext
                           if os.path.isfile(os.path.join(d, f))):
                        self._visible_types.append(i)
                except OSError:
                    pass
        items = []
        for idx, vt in enumerate(self._visible_types):
            name = DUMP_TYPE_ORDER[vt][0]
            num = idx + 1
            if num < 10:
                items.append(' %d. %s' % (num, name))
            else:
                items.append('%d. %s' % (num, name))
        from lib.widget import ListView
        self._listview = ListView(canvas)
        self._listview.setItems(items)
        self._listview.setOnPageChangeCall(self._onPageChange)
        if self._type_index > 0:
            self._listview.setSelection(self._type_index)
        self._listview.show()
        self._updateTitle()

    # ------------------------------------------------------------------
    # FILE LIST
    # ------------------------------------------------------------------
    def _showFileList(self):
        self._mode = self.MODE_FILE_LIST
        self._clearContent()
        if self._toast:
            self._toast.cancel()
        self._file_list = []
        if self._dump_dir and os.path.isdir(self._dump_dir):
            try:
                entries = os.listdir(self._dump_dir)
                valid_ext = ('.bin', '.eml', '.txt', '.json', '.pm3')
                self._file_list = sorted(
                    [f for f in entries
                     if os.path.isfile(os.path.join(self._dump_dir, f))
                     and any(f.lower().endswith(ext) for ext in valid_ext)])
            except OSError:
                self._file_list = []
        self._is_dump_list_empty = len(self._file_list) == 0
        canvas = self.getCanvas()
        if canvas is None:
            return
        if self._is_dump_list_empty:
            self.setLeftButton('')
            self.setRightButton('')
            from lib.widget import BigTextListView
            self._btlv = BigTextListView(canvas)
            self._btlv.drawStr('No dump info. \nOnly support:\n.bin .eml .txt')
            self._updateTitle()
            return
        self.setLeftButton(resources.get_str('details'))
        self.setRightButton(resources.get_str('delete'))
        display_items = self._buildFileDisplayList()
        from lib.widget import ListView
        self._listview = ListView(canvas)
        # Ground truth (dump_files screenshots): 4 items per page so the
        # last item doesn't overlap the button bar (content area = 160px,
        # 4 × 40px = 160px exactly).  Other ListViews use the default 5.
        self._listview.setDisplayItemMax(4)
        self._listview.setItems(display_items)
        self._listview.setOnPageChangeCall(self._onPageChange)
        self._listview.show()
        self._updateTitle()

    def _buildFileDisplayList(self):
        if self._is_dump_show_date:
            import time
            result = []
            for f in self._file_list:
                try:
                    fpath = os.path.join(self._dump_dir, f)
                    ctime = os.path.getctime(fpath)
                    result.append(time.strftime('%Y-%m-%d %H:%M:%S',
                                                time.localtime(ctime)))
                except OSError:
                    result.append(f)
            return result
        return [self._formatFilename(f) for f in self._file_list]

    @staticmethod
    def _formatFilename(fname):
        """Transform raw dump filename to display format.

        Original firmware displays formatted names, not raw filenames.
        Ground truth (original QEMU test results):
          MF1:    M1-1K-4B_DAEFB416_1.bin   → 1K-4B-DAEFB416(1)
          T55xx:  T55xx_00148040_..._1.bin   → 00148040(1)
          MFU:    M0-UL_04DDEEFF001122_1.bin → 04DDEEFF001122(1)
          EM410x: EM410x-ID_0F0368568B_1.txt → 0F0368568B(1)
        """
        import re
        # Strip extension
        base = os.path.splitext(fname)[0]

        # MF1: M1-{size}-{uidLen}B_{UID}_{index}
        m = re.match(r'M1-(\S+)-(\S+)_([A-Fa-f\d]+)_(\d+)', base)
        if m:
            return '%s-%s-%s(%s)' % (m.group(1), m.group(2), m.group(3), m.group(4))

        # T55xx: T55xx_{B0}_{B1}_{B2}_{index}
        m = re.match(r'T55xx_(\S+?)_\S+_\S+_(\d+)', base)
        if m:
            return '%s(%s)' % (m.group(1), m.group(2))

        # UID-based (MFU, Felica, ICODE, HF14A): {Prefix}_{UID}_{index}
        m = re.match(r'[A-Za-z0-9]+-?[A-Za-z0-9]*_([A-Fa-f\d]+)_(\d+)', base)
        if m:
            return '%s(%s)' % (m.group(1), m.group(2))

        # ID-based (EM410x, HID, etc): {Type}-ID_{data}_{index} or {Type}_{data}_{index}
        # Also handles 4-field: {Type}_{F1}_{F2}_{F3}_{index}
        m = re.match(r'\S+?[-_](\S+?)_(\d+)$', base)
        if m:
            return '%s(%s)' % (m.group(1), m.group(2))

        # Fallback: return base without extension
        return base

    # ------------------------------------------------------------------
    # DELETE CONFIRM
    # ------------------------------------------------------------------
    def _showDeleteConfirm(self):
        if self._listview is None or self._is_dump_list_empty:
            return
        sel = self._listview.selection()
        if not (0 <= sel < len(self._file_list)):
            return
        self._selected_file = self._file_list[sel]
        self._mode = self.MODE_DELETE_CONFIRM
        self.setLeftButton(resources.get_str('no'))
        self.setRightButton(resources.get_str('yes'))
        if self._toast:
            self._toast.show(resources.get_str('delete_confirm'), duration_ms=0)

    def _cancelDelete(self):
        self._selected_file = None
        self._showFileList()

    def _confirmDelete(self):
        if self._selected_file and self._dump_dir:
            filepath = os.path.join(self._dump_dir, self._selected_file)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            except OSError:
                pass
        self._selected_file = None
        # Check if any files remain
        remaining = []
        if self._dump_dir and os.path.isdir(self._dump_dir):
            try:
                entries = os.listdir(self._dump_dir)
                valid_ext = ('.bin', '.eml', '.txt', '.json', '.pm3')
                remaining = [f for f in entries
                             if os.path.isfile(os.path.join(self._dump_dir, f))
                             and any(f.lower().endswith(ext) for ext in valid_ext)]
            except OSError:
                pass
        if remaining:
            self._showFileList()
        else:
            self._showTypeList()

    # ------------------------------------------------------------------
    # NAVIGATION
    # ------------------------------------------------------------------
    def _selectType(self):
        if self._listview is None:
            return
        sel = self._listview.selection()
        # Map visible list index back to DUMP_TYPE_ORDER index
        vt = getattr(self, '_visible_types', None)
        if vt is not None:
            if not (0 <= sel < len(vt)):
                return
            real_idx = vt[sel]
        else:
            if not (0 <= sel < len(DUMP_TYPE_ORDER)):
                return
            real_idx = sel
        self._type_index = sel
        _name, dir_key = DUMP_TYPE_ORDER[real_idx]
        self._dump_type_key = dir_key
        self._dump_dir = DUMP_DIRS.get(dir_key)
        self._showFileList()

    def _openTagInfo(self):
        if self._listview is None or self._is_dump_list_empty:
            return
        sel = self._listview.selection()
        if not (0 <= sel < len(self._file_list)):
            return
        fname = self._file_list[sel]
        file_path = os.path.join(self._dump_dir, fname)
        actstack.start_activity(ReadFromHistoryActivity, file_path)

    def _toggleDateDisplay(self):
        if self._is_dump_list_empty:
            return
        self._is_dump_show_date = not self._is_dump_show_date
        self._showFileList()

    def _backToTypeList(self):
        if self._toast:
            self._toast.cancel()
        self._showTypeList()

    # ------------------------------------------------------------------
    # TITLE
    # ------------------------------------------------------------------
    def _onPageChange(self, page):
        self._updateTitle()

    def _updateTitle(self):
        base = resources.get_str('card_wallet')
        if self._listview is not None:
            total = self._listview.getPageCount()
            if total > 1:
                current = self._listview.getPagePosition() + 1
                self.setTitle('%s %d/%d' % (base, current, total))
                return
        self.setTitle(base)

    # ------------------------------------------------------------------
    # RESUME (child activity finished)
    # ------------------------------------------------------------------
    def onResume(self):
        super().onResume()
        if self._mode == self.MODE_FILE_LIST:
            self._showFileList()

    # ------------------------------------------------------------------
    # KEY DISPATCH
    # ------------------------------------------------------------------
    def onKeyEvent(self, key):
        if self._mode == self.MODE_TYPE_LIST:
            self._onKeyTypeList(key)
        elif self._mode == self.MODE_FILE_LIST:
            self._onKeyFileList(key)
        elif self._mode == self.MODE_DELETE_CONFIRM:
            self._onKeyDeleteConfirm(key)

    def _onKeyTypeList(self, key):
        if key == KEY_UP:
            if self._listview:
                self._listview.prev()
                self._updateTitle()
        elif key == KEY_DOWN:
            if self._listview:
                self._listview.next()
                self._updateTitle()
        elif key == KEY_OK:
            self._selectType()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()

    def _onKeyFileList(self, key):
        if key == KEY_UP:
            if self._listview and not self._is_dump_list_empty:
                self._listview.prev()
                self._updateTitle()
        elif key == KEY_DOWN:
            if self._listview and not self._is_dump_list_empty:
                self._listview.next()
                self._updateTitle()
        elif key == KEY_OK:
            self._openTagInfo()
        elif key == KEY_M1:
            self._toggleDateDisplay()
        elif key == KEY_M2:
            self._showDeleteConfirm()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._backToTypeList()

    def _onKeyDeleteConfirm(self, key):
        if key == KEY_M1:
            self._cancelDelete()
        elif key == KEY_M2:
            self._confirmDelete()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self._backToTypeList()


# =====================================================================
# A-23: KeyEnterM1Activity
# =====================================================================

class KeyEnterM1Activity(BaseActivity):
    """Manual hex key entry for MIFARE Classic."""
    ACT_NAME = 'key_enter'
    DEFAULT_KEY = 'FFFFFFFFFFFF'
    KEY_LENGTH = 12

    def __init__(self, bundle=None):
        self._input_method = None
        self._result_key = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        self.setTitle(resources.get_str('key_enter'))
        self.setLeftButton(resources.get_str('cancel'))
        self.setRightButton(resources.get_str('enter'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        from lib.widget import InputMethods
        placeholder = self.DEFAULT_KEY
        if bundle and isinstance(bundle, dict):
            placeholder = bundle.get('default_key', self.DEFAULT_KEY)
        self._input_method = InputMethods(
            canvas, format='hex', length=self.KEY_LENGTH,
            placeholder=placeholder)
        self._input_method.show()

    def onKeyEvent(self, key):
        if key == KEY_UP:
            if self._input_method:
                self._input_method.rollUp()
        elif key == KEY_DOWN:
            if self._input_method:
                self._input_method.rollDown()
        elif key == KEY_LEFT:
            if self._input_method:
                self._input_method.prevChar()
        elif key == KEY_RIGHT:
            if self._input_method:
                self._input_method.nextChar()
        elif key in (KEY_M2, KEY_OK):
            self._confirm()
        elif key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()

    def _confirm(self):
        if self._input_method:
            self._result_key = self._input_method.getValue()
            self._result = {'action': 'enter_key', 'key': self._result_key}
        self.finish()

    @property
    def result_key(self):
        return self._result_key


# =====================================================================
# A-24: UpdateActivity / OTAActivity
# =====================================================================

class UpdateActivity(BaseActivity):
    """Firmware update installation with per-step ProgressBar.

    Ground truth (install.py callback values + test expected states):
      Step 1: install_font     — "检查字体" / "Font will install..." (30→100)
      Step 2: install_lua_dep  — "目录已经存在" / "LUA dep..." (30→100)
      Step 3: install_app      — "App installing..." (38→100)
      Step 4: update_permission — "Permission Updating..." (30→100)
      Step 5: restart_app      — "正在重启" / "App restarting..." (60→100)

    UI states:
      READY:      Title "Update", tips text, M2="Start"
      SEARCHING:  "Searching..." message + progress bar
      INSTALLING: Step name + progress bar advancing per callback
      DONE:       Success/fail toast, M2="OK"
    """
    ACT_NAME = 'update'
    STATE_READY = 'ready'
    STATE_SEARCHING = 'searching'
    STATE_INSTALLING = 'installing'
    STATE_DONE = 'done'

    def __init__(self, bundle=None):
        self._upd_state = self.STATE_READY
        self._progress_bar = None
        self._toast = None
        self._tips_view = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        self.setTitle(resources.get_str('update'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        self._progress_bar = ProgressBar(canvas)
        from lib.widget import BigTextListView
        self._tips_view = BigTextListView(canvas)
        self._tips_view.drawStr(resources.get_str('start_install_tips'))

    def onKeyEvent(self, key):
        if self._upd_state == self.STATE_READY:
            if key in (KEY_M2, KEY_OK):
                self._startInstall()
            elif key in (KEY_M1, KEY_PWR):
                if key == KEY_PWR and self._handlePWR():
                    return
                self.finish()
        elif self._upd_state in (self.STATE_SEARCHING, self.STATE_INSTALLING):
            pass  # All keys blocked during install
        elif self._upd_state == self.STATE_DONE:
            if key in (KEY_M2, KEY_OK, KEY_PWR):
                if key == KEY_PWR and self._handlePWR():
                    return
                self.finish()

    def _startInstall(self):
        self._upd_state = self.STATE_SEARCHING
        self.setbusy()
        self.dismissButton()

        # Replace tips text with install warning, show progress bar
        if self._tips_view is not None:
            self._tips_view.drawStr(resources.get_str('installation'))
        self._progress_bar.setMessage(resources.get_str('searching'))
        self._progress_bar.setProgress(0)
        self._progress_bar.show()

        import threading
        def _run():
            try:
                import update

                # Step 1: Search for IPK
                self._ui_progress(resources.get_str('searching'), 10)
                result = update.search('/mnt/upan/')
                if not result:
                    self._ui_complete(False, 0x01)
                    return

                # Step 2: Validate package
                self._ui_progress(resources.get_str('checking'), 20)
                if not update.checkPkg():
                    self._ui_complete(False, 0x05)
                    return

                # Step 3: Extract package
                self._ui_progress(resources.get_str('checking'), 30)
                update.unpkg()

                # Step 4: Run install pipeline (5 sub-steps with callbacks)
                self._upd_state = self.STATE_INSTALLING

                def _on_step(name, progress):
                    # Map install.py progress (0-100 per step) to overall 30-95
                    overall = 30 + int(progress * 0.65)
                    self._ui_progress(name, overall)

                update.install(_on_step)

                # Step 5: Done
                self._ui_progress(resources.get_str('update_finish'), 100)
                import time
                time.sleep(0.5)  # Let user see 100%
                self._ui_complete(True)

            except Exception as e:
                print('[UPDATE] install error: %s' % e, flush=True)
                self._ui_complete(False, 0x03)

        threading.Thread(target=_run, daemon=True).start()

    def _ui_progress(self, message, percent):
        """Update progress bar on Tk main thread."""
        try:
            if actstack._root is not None:
                actstack._root.after(0, self._do_progress, message, percent)
        except Exception:
            pass

    def _do_progress(self, message, percent):
        """Tk-thread callback: update progress bar and message."""
        if self._progress_bar is not None:
            self._progress_bar.setMessage(message)
            self._progress_bar.setProgress(percent)

    def _ui_complete(self, success, code=0):
        """Schedule completion on Tk main thread."""
        try:
            if actstack._root is not None:
                actstack._root.after(0, self._onInstallComplete, success, code)
            else:
                self._onInstallComplete(success, code)
        except Exception:
            self._onInstallComplete(success, code)

    def _onInstallComplete(self, success=True, code=0):
        self._upd_state = self.STATE_DONE
        self.setidle()
        if self._progress_bar is not None:
            self._progress_bar.hide()
        self.setLeftButton('')
        self.setRightButton(resources.get_str('ok'))
        if self._toast:
            if success:
                self._toast.show(resources.get_str('update_finish'),
                                 mode=Toast.MASK_CENTER, icon='check',
                                 duration_ms=0)
            else:
                self._toast.show(
                    resources.get_str('install_failed').format(
                        '0x%02x' % code if code else -1),
                    mode=Toast.MASK_CENTER, icon='error',
                    duration_ms=0)


class FWUpdateActivity(BaseActivity):
    """PM3 firmware flash UI — 4-state wizard with safety checks.

    States:
      STATE_INFO      — Initial info screen ("Firmware update required...")
      STATE_PREFLASH  — 3-page pre-flash wizard (pages 0/1/2)
      STATE_FLASHING  — Flash in progress, all keys blocked
      STATE_DONE      — Toast showing result

    Ground truth: middleware/pm3_flash.py (flash engine),
    project_pm3_flash_safety.md (ABSOLUTE: never flash bootrom).
    """
    ACT_NAME = 'fw_update'
    STATE_INFO = 'info'
    STATE_PREFLASH = 'preflash'
    STATE_FLASHING = 'flashing'
    STATE_DONE = 'done'

    # Progress stage -> display message mapping
    _STAGE_MESSAGES = {
        'preparing': 'Preparing...',
        'killing_pm3': 'Stopping PM3...',
        'entering_bootloader': 'Entering bootloader...',
        'flashing': 'Flashing firmware...',
        'verifying': 'Verifying...',
        'restarting': 'Restarting PM3...',
        'complete': 'Flash complete',
    }

    # Preflash state names matching fw_update.json
    _PREFLASH_STATES = ['preflash', 'preflash_2', 'preflash_3']
    _PREFLASH_TOTAL = 3

    def __init__(self, bundle=None):
        self._fw_state = self.STATE_INFO
        self._preflash_page = 0
        self._progress_bar = None
        self._toast = None
        self._jr = None
        self._screens = {}
        self._flash_percent = 0
        self._fake_timer = None
        self._destroyed = False
        super().__init__(bundle)

    def onDestroy(self):
        self._destroyed = True
        super().onDestroy()

    def onCreate(self, bundle):
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        self._progress_bar = ProgressBar(canvas)

        # Load screen definitions from JSON (same pattern as WarningWriteActivity)
        from lib.json_renderer import JsonRenderer
        self._jr = JsonRenderer(canvas)
        import json
        screen_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'screens', 'fw_update.json')
        try:
            with open(screen_path) as f:
                data = json.load(f)
            self._screens = {
                k: v.get('screen', {})
                for k, v in data.get('states', {}).items()
            }
        except Exception as e:
            print('[FW_UPDATE] JSON load failed: %s' % e, flush=True)

        # Render initial info screen from JSON
        self._renderScreen('info')
        self.setTitle('FW Update')
        self.setLeftButton('Skip')
        self.setRightButton('Install')

    def onKeyEvent(self, key):
        if self._fw_state == self.STATE_INFO:
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
            elif key == KEY_M1:
                self.finish()
            elif key in (KEY_M2, KEY_OK):
                self._enterPreflash()

        elif self._fw_state == self.STATE_PREFLASH:
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
            elif self._preflash_page == 0:
                if key == KEY_DOWN:
                    self._setPreflashPage(1)
            elif self._preflash_page == 1:
                if key == KEY_UP:
                    self._setPreflashPage(0)
                elif key == KEY_DOWN:
                    self._setPreflashPage(2)
            elif self._preflash_page == 2:
                if key == KEY_UP:
                    self._setPreflashPage(1)
                elif key == KEY_M1:
                    self.finish()
                elif key in (KEY_M2, KEY_OK):
                    self._onStartPressed()

        elif self._fw_state == self.STATE_FLASHING:
            pass  # All keys blocked during flash

        elif self._fw_state == self.STATE_DONE:
            if key in (KEY_M2, KEY_OK, KEY_PWR):
                if key == KEY_PWR and self._handlePWR():
                    return
                self.finish()

    # ------------------------------------------------------------------
    # Pre-flash wizard
    # ------------------------------------------------------------------

    def _enterPreflash(self):
        """Transition from STATE_INFO to STATE_PREFLASH page 0."""
        self._fw_state = self.STATE_PREFLASH
        self._preflash_page = 0
        self._renderPreflashPage()

    def _setPreflashPage(self, page):
        """Navigate to a specific pre-flash wizard page."""
        self._preflash_page = page
        self._renderPreflashPage()

    def _renderScreen(self, state_name):
        """Render content area from fw_update.json state definition."""
        screen = self._screens.get(state_name, {})
        content = screen.get('content', {})
        if content and self._jr is not None:
            self._jr.render_content_only(content)

    def _renderPreflashPage(self):
        """Render the current pre-flash wizard page."""
        page = self._preflash_page
        state_name = self._PREFLASH_STATES[page]

        self.setTitle('FW Update %d/%d' % (page + 1, self._PREFLASH_TOTAL))
        self._renderScreen(state_name)

        # Buttons: only on last page (Cancel/Start)
        if page == self._PREFLASH_TOTAL - 1:
            self.setLeftButton('Cancel')
            self.setRightButton('Start')
            self.clearButtonArrows()
        else:
            self.setLeftButton('')
            self.setRightButton('')
            self.setButtonArrows(page, self._PREFLASH_TOTAL)

    # ------------------------------------------------------------------
    # Safety check and flash start
    # ------------------------------------------------------------------

    def _onStartPressed(self):
        """Handle M2 'Start' press on preflash page 2: run safety check."""
        try:
            from middleware import pm3_flash
        except ImportError:
            import pm3_flash
        safe, error_msg = pm3_flash.check_safety()
        if not safe:
            if self._toast:
                self._toast.show(error_msg, mode=Toast.MASK_CENTER,
                                 icon='error', duration_ms=3000)
            return
        self._startFlash()

    def _startFlash(self):
        """Transition to STATE_FLASHING and launch background flash thread."""
        self._fw_state = self.STATE_FLASHING
        self.setbusy()
        self.dismissButton()
        self.clearButtonArrows()
        self.setTitle('FW Flash')

        self._renderScreen('flashing')

        if self._progress_bar is not None:
            self._progress_bar.setMessage('Preparing...')
            self._progress_bar.setProgress(0)
            self._progress_bar.show()

        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        import threading

        def _run():
            try:
                try:
                    from middleware import pm3_flash
                except ImportError:
                    import pm3_flash

                def _on_progress(percent, stage):
                    msg = self._STAGE_MESSAGES.get(stage, stage)
                    self._ui_progress(msg, percent)

                success, message = pm3_flash.flash_firmware(
                    app_dir, progress_cb=_on_progress)

                if success:
                    self._ui_complete(True, message)
                else:
                    self._ui_complete(False, message)

            except Exception as e:
                print('[FW_UPDATE] flash error: %s' % e, flush=True)
                self._ui_complete(False, str(e))

        threading.Thread(target=_run, daemon=True).start()

    # ------------------------------------------------------------------
    # Tk-safe UI updates (called from background flash thread)
    # ------------------------------------------------------------------

    def _ui_progress(self, message, percent):
        """Update progress bar on Tk main thread."""
        try:
            if actstack._root is not None:
                actstack._root.after(0, self._do_progress, message, percent)
        except Exception as e:
            print('[FWUpdate] _ui_progress error: %s' % e, flush=True)

    def _do_progress(self, message, percent):
        """Tk-thread callback: update progress bar and message."""
        self._flash_percent = percent
        if self._progress_bar is not None:
            self._progress_bar.setMessage(message)
            self._progress_bar.setProgress(percent)
        # Start a slow auto-advance during the flashing stage so the
        # progress bar visibly moves while block writes happen (the
        # real output is one long line of dots with no newlines).
        if 30 <= percent < 90 and not self._destroyed:
            self._start_fake_progress()

    def _start_fake_progress(self):
        """Slowly advance progress bar during block write phase."""
        if self._fake_timer is not None or actstack._root is None:
            return
        def _tick():
            if self._destroyed or self._fw_state != self.STATE_FLASHING:
                self._fake_timer = None
                return
            p = self._flash_percent
            if p < 90:
                p += 1
                self._flash_percent = p
                if self._progress_bar is not None:
                    self._progress_bar.setProgress(p)
                self._fake_timer = actstack._root.after(1000, _tick)
            else:
                self._fake_timer = None
        self._fake_timer = actstack._root.after(1000, _tick)

    def _ui_complete(self, success, message=''):
        """Schedule completion on Tk main thread."""
        try:
            if actstack._root is not None:
                actstack._root.after(0, self._onFlashComplete, success, message)
            else:
                # No Tk root — update state only, skip canvas operations
                self._fw_state = self.STATE_DONE
        except Exception:
            # Tk root may be destroyed — update state only
            self._fw_state = self.STATE_DONE

    def _onFlashComplete(self, success=True, message=''):
        """Handle flash completion — show result toast, restart on success."""
        if self._destroyed:
            return
        self._fake_timer = None  # stop fake progress
        self._fw_state = self.STATE_DONE
        self.setidle()
        if self._progress_bar is not None:
            self._progress_bar.hide()
        self.setLeftButton('')
        self.setRightButton('')
        if self._toast:
            if success:
                self._toast.show('FW Updated!\nRestarting...',
                                 mode=Toast.MASK_CENTER, icon='check',
                                 duration_ms=3000)
                # Restart service after toast — reconnects RTM to new PM3
                if actstack._root is not None:
                    actstack._root.after(3100, self._restart_service)
            else:
                # Save fail log to persistent storage
                try:
                    with open('/mnt/upan/firmware_fail.log', 'w') as f:
                        f.write(message or 'Unknown error')
                except Exception:
                    pass
                self.setRightButton('OK')
                self._toast.show('Flash Failed.\nLog file on device.',
                                 mode=Toast.MASK_CENTER, icon='error',
                                 duration_ms=0)

    @staticmethod
    def _restart_service():
        """Restart icopy service to reconnect RTM to flashed PM3."""
        import subprocess
        try:
            subprocess.Popen(
                ['sudo', 'systemctl', 'restart', 'icopy.service'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


class OTAActivity(BaseActivity):
    """OTA update check and download."""
    ACT_NAME = 'ota'

    def __init__(self, bundle=None):
        self._checking = False
        self._toast = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        self.setTitle(resources.get_str('update'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        from lib.widget import BigTextListView
        btlv = BigTextListView(canvas)
        btlv.drawStr(resources.get_str('update_start_tips'))

    def onKeyEvent(self, key):
        if key in (KEY_M2, KEY_OK):
            if not self._checking:
                self._startCheck()
        elif key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()

    def _startCheck(self):
        self._checking = True
        self.setbusy()
        if self._toast:
            self._toast.show(resources.get_str('update_unavailable'))
        self._checking = False
        self.setidle()


# =====================================================================
# A-25: Hidden / Special Activities
# =====================================================================

class SniffForMfReadActivity(BaseActivity):
    """Sniff for MIFARE keys during read flow."""
    ACT_NAME = 'sniff_for_mf_read'
    def __init__(self, bundle=None):
        self._sniffing = False
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('sniff_tag'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK) and not self._sniffing:
            self._sniffing = True
            self.setbusy()


class SniffForT5XReadActivity(BaseActivity):
    """Sniff for T55xx password during read flow."""
    ACT_NAME = 'sniff_for_t5x_read'
    def __init__(self, bundle=None):
        self._sniffing = False
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('sniff_tag'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK) and not self._sniffing:
            self._sniffing = True
            self.setbusy()


class SniffForSpecificTag(BaseActivity):
    """Sniff for a specific tag type."""
    ACT_NAME = 'sniff_specific'
    def __init__(self, bundle=None):
        self._sniffing = False
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('sniff_tag'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK) and not self._sniffing:
            self._sniffing = True
            self.setbusy()


class IClassSEActivity(BaseActivity):
    """iClass SE key server integration."""
    ACT_NAME = 'iclass_se'
    def __init__(self, bundle=None):
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('se_decoder'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        from lib.widget import BigTextListView
        BigTextListView(canvas).drawStr(resources.get_str('iclass_se_read_tips'))
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()


class WearableDeviceActivity(BaseActivity):
    """Wearable device (smart watch) emulation mode."""
    ACT_NAME = 'wearable'
    def __init__(self, bundle=None):
        self._step = 0
        self._toast = None
        self._btlv = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('write_wearable'))
        self.setLeftButton(resources.get_str('back'))
        self.setRightButton(resources.get_str('start'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        from lib.widget import BigTextListView
        self._btlv = BigTextListView(canvas)
        self._showStep()
    def _showStep(self):
        keys = ['write_wearable_tips1', 'write_wearable_tips2',
                'write_wearable_tips3']
        if self._step < len(keys) and self._btlv:
            self._btlv.drawStr(resources.get_str(keys[self._step]))
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK):
            if self._step < 2:
                self._step += 1
                self._showStep()
            else:
                self.finish()


class ReadFromHistoryActivity(BaseActivity):
    """Tag Info view for dump files — parses filename, shows info, launches sim/write.

    Binary source: activity_main.so ReadFromHistoryActivity
    Ground truth: HANDOVER.md, trace_dump_files_20260403.txt

    Bundle: file path string WITH extension (e.g., '/mnt/upan/dump/mf1/M1-1K-4B_DAEFB416_1.bin')
    """
    ACT_NAME = 'read_history'

    # dump_type_key -> scan cache type number (from READABLE_TYPES)
    _TYPE_NUMBERS = {
        'mf1': 1, 'mfu': 2, 'em410x': 8, 'hid': 9, 'indala': 10,
        'awid': 11, 'ioprox': 12, 'gproxii': 13, 'securakey': 14,
        'viking': 15, 'pyramid': 16, 'iclass': 18, 'icode': 19,
        'legic': 20, 'felica': 21, 't55xx': 23, 'em4x05': 24,
        'fdx': 28, 'gallagher': 29, 'jablotron': 30, 'keri': 31,
        'nedap': 32, 'noralsy': 33, 'pac': 34, 'paradox': 35,
        'presco': 36, 'visa2000': 37, 'nexwatch': 45, 'hf14a': 44,
    }

    # dump_type_key -> SIM_MAP index (for sim_for_info)
    _SIM_INDEX = {
        'mf1': 0, 'mfu': 2, 'em410x': 5, 'hid': 6, 'awid': 7,
        'ioprox': 8, 'gproxii': 9, 'viking': 10, 'pyramid': 11,
        'jablotron': 12, 'nedap': 13, 'fdx': 14,
    }

    # Types that use write_file_base (HF file-based writes)
    _WRITE_FILE_TYPES = {'mf1', 'mfu', 'iclass', 'felica', 'legic', 'hf14a', 'icode'}
    # Types that use write_lf_dump (raw T55xx restore)
    _WRITE_LF_DUMP_TYPES = {'t55xx', 'em4x05'}

    def __init__(self, bundle=None):
        self._file_path = None
        self._dump_type_key = None
        self._tag_info = {}
        self._scan_cache = {}
        self._toast = None
        super().__init__(bundle)

    def onCreate(self, bundle):
        import re
        self.setTitle(resources.get_str('tag_info'))
        self.setRightButton(resources.get_str('write'))

        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)

        # Bundle = file path string
        if bundle and isinstance(bundle, str):
            self._file_path = bundle
        elif bundle and isinstance(bundle, dict):
            self._file_path = bundle.get('file_path', bundle.get('dump_data'))
        if not self._file_path:
            return

        # Determine type from directory name
        self._dump_type_key = os.path.basename(os.path.dirname(self._file_path))

        # Parse filename
        fname = os.path.basename(self._file_path)
        self._tag_info = self._parseFilename(fname)

        # Build and set scan cache
        self._scan_cache = self._buildScanCache()
        try:
            import scan as _scan_mod
            _scan_mod.setScanCache(self._scan_cache)
        except Exception:
            pass

        # Set Simulate button (grayed out if type not simulatable).
        # Check by scan cache type number against SIM_MAP type IDs.
        _sim_type_ids = {entry[1] for entry in SIM_MAP}
        sim_active = self._scan_cache.get('type', -1) in _sim_type_ids
        self.setLeftButton(resources.get_str('simulate'), active=sim_active)

        # Render tag info
        self._renderInfo()

    def _parseFilename(self, fname):
        import re
        dtk = self._dump_type_key
        info = {}

        if dtk == 'mf1':
            # M1-{size}-{uidLen}B_{UID}_{index}.{ext}
            m = re.match(r'M1-(\S+)-(\S+)_([A-Fa-f\d]+)_(\d+).*\.(.*)', fname)
            if m:
                info['size'] = m.group(1)
                info['uidlen'] = m.group(2)
                info['uid'] = m.group(3).upper()
                info['index'] = m.group(4)
                info['ext'] = m.group(5)
                info['display'] = '%s-%s-%s(%s)' % (
                    m.group(1), m.group(2), m.group(3).upper(), m.group(4))
        elif dtk == 't55xx':
            # T55xx_{B0}_{B1}_{B2}_{index}.{ext}
            m = re.match(r'(\S+)_(\S+)_(\S+)_(\S+)_(\d+).*\.(.*)', fname)
            if m:
                info['chip'] = m.group(1)
                info['b0'] = m.group(2).upper()
                info['b1'] = m.group(3).upper()
                info['b2'] = m.group(4).upper()
                info['index'] = m.group(5)
                info['ext'] = m.group(6)
                info['display'] = '%s-%s(%s)' % (
                    m.group(1), m.group(2).upper(), m.group(5))
        elif dtk in ('mfu', 'felica', 'icode', 'hf14a'):
            # {Type}_{UID}_{index}.{ext}  or  {Type}-{Sub}_{UID}_{index}.{ext}
            m = re.match(r'(\S+)_([A-Fa-f\d]+)_(\d+).*\.(.*)', fname)
            if m:
                info['type_prefix'] = m.group(1)
                info['uid'] = m.group(2).upper()
                info['index'] = m.group(3)
                info['ext'] = m.group(4)
                info['display'] = '%s-%s(%s)' % (
                    m.group(1), m.group(2).upper(), m.group(3))
        elif dtk == 'legic':
            # Legic_{UID}_{index}.{ext}
            m = re.match(r'(\S+)_(\S+)_(\d+)\.(.*)', fname)
            if m:
                info['type_prefix'] = m.group(1)
                info['uid'] = m.group(2).upper()
                info['index'] = m.group(3)
                info['ext'] = m.group(4)
                info['display'] = '%s-%s(%s)' % (
                    m.group(1), m.group(2).upper(), m.group(3))
        else:
            # ID-based: {Type}_{Data}_{index}.{ext} (2-field)
            # or {Type}_{F1}_{F2}_{F3}_{index}.{ext} (4-field)
            m = re.match(r'(\S+)_(\S+)_(\S+)_(\S+)_(\d+).*\.(.*)', fname)
            if m:
                info['type_prefix'] = m.group(1)
                info['data'] = m.group(2)
                info['f2'] = m.group(3)
                info['f3'] = m.group(4)
                info['index'] = m.group(5)
                info['ext'] = m.group(6)
                info['display'] = '%s-%s(%s)' % (
                    m.group(1), m.group(2), m.group(5))
            else:
                m = re.match(r'(\S+)_(\S+)_(\d+).*\.(.*)', fname)
                if m:
                    info['type_prefix'] = m.group(1)
                    info['data'] = m.group(2)
                    info['index'] = m.group(3)
                    info['ext'] = m.group(4)
                    info['display'] = '%s-%s(%s)' % (
                        m.group(1), m.group(2), m.group(3))
        return info

    def _buildScanCache(self):
        """Build scan cache dict matching scan.so output format.

        Values use native Python types (int for type, bool for found,
        plain strings without quotes for uid/data).
        Ground truth: ScanActivity._onScanResult shows scan.so returns
        {'found': True, 'type': 1, 'uid': 'B7785E50', ...}
        """
        dtk = self._dump_type_key
        info = self._tag_info
        type_num = self._TYPE_NUMBERS.get(dtk, 0)
        cache = {'found': True, 'type': type_num}

        if dtk == 'mf1':
            uid = info.get('uid', '')
            cache['uid'] = uid
            uidlen = info.get('uidlen', '4B')
            digits = uidlen.replace('B', '') if uidlen else '4'
            cache['len'] = int(digits)
            size = info.get('size', '1K')
            if size == '4K':
                cache['sak'] = '08'
                cache['atqa'] = '0004'
                cache['nameStr'] = 'M1 S70 4K (%s)' % uidlen
                cache['type'] = 0
            elif size == 'Mini':
                cache['sak'] = '08'
                cache['atqa'] = '0004'
                cache['nameStr'] = 'M1 Mini 0.3K'
                cache['type'] = 25
            else:
                cache['sak'] = '08'
                cache['atqa'] = '0004'
                cache['nameStr'] = 'M1 S50 1K (%s)' % uidlen
        elif dtk == 'mfu':
            cache['uid'] = info.get('uid', '00000000000000')
        elif dtk == 't55xx':
            cache['b0'] = info.get('b0', '00000000')
            cache['modulate'] = '--------'
            cache['chip'] = 'T55xx/Unknown'
        elif dtk in ('em410x', 'hid', 'indala', 'awid', 'fdx', 'viking',
                      'keri', 'pyramid', 'paradox', 'jablotron', 'noralsy',
                      'nexwatch', 'securakey', 'pac', 'gproxii', 'nedap',
                      'gallagher', 'visa2000', 'presco', 'ioprox'):
            data = info.get('data', '')
            cache['data'] = data
            cache['raw'] = data
        elif dtk == 'felica':
            cache['uid'] = info.get('uid', '')
        elif dtk in ('icode', 'hf14a'):
            cache['uid'] = info.get('uid', '')
        elif dtk == 'iclass':
            cache['uid'] = info.get('data', info.get('uid', ''))
        elif dtk == 'legic':
            cache['uid'] = info.get('uid', '')

        return cache

    def _renderInfo(self):
        """Render tag info using template.so — same renderer as ScanActivity.

        Ground truth: ScanActivity._showFoundState uses template.draw()
        which picks the correct __drawXxx method per tag type and formats
        UID, SAK, ATQA, Frequency, etc. using its internal string table.
        """
        canvas = self.getCanvas()
        if canvas is None:
            return
        tag_type = self._scan_cache.get('type', 0)
        try:
            import template
            template.draw(tag_type, self._scan_cache, canvas)
            # template.draw clears the canvas and draws its own title bar
            # (e.g. "MIFARE"). Force re-init of our title bar over it.
            self._is_title_inited = False
            self.setTitle(resources.get_str('tag_info'))
        except Exception as e:
            print('[READ_HISTORY] template.draw failed: %s' % e, flush=True)
            # Fallback: plain text
            from lib.widget import BigTextListView
            btlv = BigTextListView(canvas)
            dtk = self._dump_type_key
            type_display = dtk
            for name, key in DUMP_TYPE_ORDER:
                if key == dtk:
                    type_display = name
                    break
            display = self._tag_info.get('display',
                                         os.path.basename(self._file_path))
            btlv.drawStr('%s\n%s' % (type_display, display))

    # ------------------------------------------------------------------
    # WRITE DISPATCH
    # ------------------------------------------------------------------
    def _dispatch_write(self):
        dtk = self._dump_type_key
        if dtk in self._WRITE_FILE_TYPES:
            self._write_file_base()
        elif dtk in self._WRITE_LF_DUMP_TYPES:
            self._write_lf_dump()
        else:
            self._write_id()

    def _write_file_base(self):
        # Bundle = file path WITHOUT extension
        bundle = os.path.splitext(self._file_path)[0]
        actstack.start_activity(WarningWriteActivity, bundle)

    def _write_id(self):
        # Bundle = scan cache dict (native types, no transformation needed)
        actstack.start_activity(WarningWriteActivity, dict(self._scan_cache))

    def _write_lf_dump(self):
        # Bundle = {'file': path_with_extension}
        bundle = {'file': self._file_path}
        actstack.start_activity(WarningWriteActivity, bundle)

    # ------------------------------------------------------------------
    # SIMULATE DISPATCH
    # ------------------------------------------------------------------
    def _sim_for_info(self):
        # Ground truth (original trace line 50):
        #   START(SimulationActivity, {'uid':'DAEFB416','len':4,'sak':'08',
        #         'atqa':'0004','found':True,'type':1})
        # The original passes the full scan cache dict as bundle.
        # SimulationActivity.onCreate extracts sim_index from 'type' field.
        tag_type = self._scan_cache.get('type', -1)
        if tag_type not in _SIMULATE_TYPES:
            return
        actstack.start_activity(SimulationActivity, dict(self._scan_cache))

    # ------------------------------------------------------------------
    # onActivity — handle results from WarningWriteActivity
    # ------------------------------------------------------------------
    def onActivity(self, result):
        if result is None or not isinstance(result, dict):
            return
        action = result.get('action')
        if action == 'write':
            try:
                actstack.start_activity(WriteActivity,
                                        result.get('read_bundle'))
            except Exception as e:
                print('[READ_HISTORY] WriteActivity launch error: %s' % e,
                      flush=True)

    def onKeyEvent(self, key):
        if key == KEY_M1:
            self._sim_for_info()
        elif key in (KEY_M2, KEY_OK):
            self._dispatch_write()
        elif key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()


class AutoExceptCatchActivity(BaseActivity):
    """Auto exception catch and reporting."""
    ACT_NAME = 'auto_except'
    def __init__(self, bundle=None):
        self._error_msg = ''
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('error'))
        self.setLeftButton(resources.get_str('save'))  # UI_MAP line 113: M1=Save
        self.setRightButton('')  # UI_MAP line 113: M2=empty
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        if bundle and isinstance(bundle, dict):
            self._error_msg = bundle.get('error', 'Unknown error')
        from lib.widget import BigTextListView
        BigTextListView(canvas).drawStr(self._error_msg)
    def onKeyEvent(self, key):
        if key in (KEY_M2, KEY_OK, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()


class SnakeGameActivity(BaseActivity):
    """Hidden easter egg: Snake (Greedy Snake) game."""
    ACT_NAME = 'snake_game'
    STATE_IDLE = 'idle'
    STATE_PLAYING = 'playing'
    STATE_GAME_OVER = 'game_over'
    def __init__(self, bundle=None):
        self._game_state = self.STATE_IDLE
        self._toast = None
        self._score = 0
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('snakegame'))
        self.setLeftButton('')
        self.setRightButton('')
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        self._toast.show(resources.get_str('game_tips'))
    def onKeyEvent(self, key):
        if self._game_state == self.STATE_IDLE:
            if key in (KEY_M2, KEY_OK):
                self._game_state = self.STATE_PLAYING
                self._score = 0
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()
        elif self._game_state == self.STATE_PLAYING:
            if key == KEY_PWR:
                if self._handlePWR():
                    return
                self._game_state = self.STATE_IDLE
                if self._toast:
                    self._toast.show(resources.get_str('pausing'))
        elif self._game_state == self.STATE_GAME_OVER:
            if key in (KEY_M2, KEY_OK):
                self._game_state = self.STATE_IDLE
                if self._toast:
                    self._toast.show(resources.get_str('game_tips'))
            elif key == KEY_PWR:
                if self._handlePWR():
                    return
                self.finish()


class WarningT5XActivity(BaseActivity):
    """T55xx password warning."""
    ACT_NAME = 'warning_t5x'
    def __init__(self, bundle=None):
        self._toast = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        self.setTitle(resources.get_str('no_valid_key_t55xx'))
        self.setLeftButton(resources.get_str('cancel'))
        self.setRightButton('')
        canvas = self.getCanvas()
        if canvas is None:
            return
        self._toast = Toast(canvas)
        from lib.widget import BigTextListView
        BigTextListView(canvas).drawStr(resources.get_str('missing_keys_t57'))
    def onKeyEvent(self, key):
        if key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
        elif key in (KEY_M2, KEY_OK):
            self._result = {'action': 'proceed'}
            self.finish()


class WarningT5X4X05KeyEnterActivity(BaseActivity):
    """T55xx/EM4x05 password entry activity."""
    ACT_NAME = 'warning_t5x_key_enter'
    KEY_LENGTH = 8
    DEFAULT_KEY = '00000000'
    def __init__(self, bundle=None):
        self._input_method = None
        self._result_key = None
        super().__init__(bundle)
    def onCreate(self, bundle):
        # UI_MAP_COMPLETE line 106: M1="Enter" M2="Cancel"
        self.setTitle(resources.get_str('no_valid_key_t55xx'))
        self.setLeftButton(resources.get_str('enter'))
        self.setRightButton(resources.get_str('cancel'))
        canvas = self.getCanvas()
        if canvas is None:
            return
        from lib.widget import BigTextListView
        BigTextListView(canvas).drawStr(resources.get_str('enter_known_keys_55xx'))
        from lib.widget import InputMethods
        self._input_method = InputMethods(
            canvas, format='hex', length=self.KEY_LENGTH,
            placeholder=self.DEFAULT_KEY)
        self._input_method.show()
    def onKeyEvent(self, key):
        if key == KEY_UP and self._input_method:
            self._input_method.rollUp()
        elif key == KEY_DOWN and self._input_method:
            self._input_method.rollDown()
        elif key == KEY_LEFT and self._input_method:
            self._input_method.prevChar()
        elif key == KEY_RIGHT and self._input_method:
            self._input_method.nextChar()
        elif key in (KEY_M2, KEY_OK):
            if self._input_method:
                self._result_key = self._input_method.getValue()
                self._result = {'action': 'enter_key', 'key': self._result_key}
            self.finish()
        elif key in (KEY_M1, KEY_PWR):
            if key == KEY_PWR and self._handlePWR():
                return
            self.finish()
