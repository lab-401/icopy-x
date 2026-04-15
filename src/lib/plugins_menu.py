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

"""Plugins submenu activity — shows non-promoted plugins in a ListView.

Provides PluginsMenuActivity, a BaseActivity subclass that displays all
non-promoted plugins discovered by the plugin loader.  Promoted plugins
appear directly on the main menu and are NOT shown here.

Architecture:
    MainActivity "Plugins" entry -> PluginsMenuActivity -> PluginActivity
                                                       -> CanvasModeActivity

Import convention: ``from lib.plugins_menu import PluginsMenuActivity``

Python 3.8 compatible.
"""

import logging

from lib.actbase import BaseActivity
from lib import actstack
from lib import resources
from lib.widget import ListView
from lib._constants import (
    LIST_ITEM_H,
    KEY_UP,
    KEY_DOWN,
    KEY_OK,
    KEY_M1,
    KEY_M2,
    KEY_PWR,
)

logger = logging.getLogger(__name__)


class PluginsMenuActivity(BaseActivity):
    """Submenu listing all non-promoted plugins.

    Uses a standard ListView identical in style to the main menu.
    Each item shows the plugin name with its icon (or the default
    'plugin' icon).

    Instance variables (beyond BaseActivity):
        lv_plugins  -- ListView widget for the plugin list
        _plugins    -- list of PluginInfo objects (non-promoted only)
    """

    ACT_NAME = 'plugins_menu'

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self._plugins = []
        self.lv_plugins = None

    def onCreate(self, bundle=None):
        """Set up the plugins submenu.

        Sequence:
            1. setLeftButton("Back") -- M1 goes back
            2. setRightButton("") -- no right button
            3. Populate _plugins from actmain._discovered_plugins (non-promoted)
            4. Create ListView with plugin names and icons
            5. Set title with page indicator
        """
        # Buttons
        self.setLeftButton("")
        self.setRightButton("")

        # Get non-promoted plugins from actmain module state
        try:
            from lib import actmain
            self._plugins = [
                p for p in actmain._discovered_plugins
                if not p.promoted
            ]
        except Exception:
            logger.error("Failed to load plugin list from actmain")
            self._plugins = []

        # Build ListView
        canvas = self.getCanvas()
        if canvas is not None:
            xy = resources.get_xy('lv_main_page')
            text_size = resources.get_text_size('lv_main_page')
            self.lv_plugins = ListView(
                canvas, xy=xy, text_size=text_size, item_height=LIST_ITEM_H,
            )
            labels = [p.name for p in self._plugins]
            self.lv_plugins.setItems(labels)
            icons = [p.icon_path or 'plugin' for p in self._plugins]
            self.lv_plugins.setIcons(icons)
            self.lv_plugins.setOnPageChangeCall(self._onPageChange)
            self.lv_plugins.show()

        # Title with page indicator: "Plugins N/M"
        self._updateTitle()

    def onResume(self):
        """Refresh battery, restore list display and title."""
        super().onResume()
        if self.lv_plugins is not None and not self.lv_plugins.isShowing():
            self.lv_plugins.show()
        self._updateTitle()

    def onKeyEvent(self, key):
        """Handle key input on the plugins submenu."""
        if self.isbusy():
            return

        if key == KEY_UP:
            if self.lv_plugins is not None:
                old_page = self.lv_plugins.getPagePosition()
                self.lv_plugins.prev()
                if self.lv_plugins.getPagePosition() != old_page:
                    self._updateTitle()

        elif key == KEY_DOWN:
            if self.lv_plugins is not None:
                old_page = self.lv_plugins.getPagePosition()
                self.lv_plugins.next()
                if self.lv_plugins.getPagePosition() != old_page:
                    self._updateTitle()

        elif key in (KEY_OK, KEY_M2):
            if self.lv_plugins is not None:
                pos = self.lv_plugins.selection()
                self._launchPlugin(pos)

        elif key == KEY_M1:
            self.finish()

        elif key == KEY_PWR:
            if not self._handlePWR():
                self.finish()

    def _launchPlugin(self, index):
        """Launch the plugin at list position *index*.

        Determines whether to use CanvasModeActivity or PluginActivity
        based on the plugin's canvas_mode flag, and builds the
        appropriate bundle.
        """
        if index < 0 or index >= len(self._plugins):
            logger.warning("Plugin index %d out of range", index)
            return

        info = self._plugins[index]

        if info.canvas_mode:
            from lib.plugin_activity import CanvasModeActivity
            bundle = {
                'plugin_dir': info.plugin_dir,
                'manifest': info.manifest,
                'binary': info.binary,
                'args': info.args,
                'key_map': info.key_map,
            }
            actstack.start_activity(CanvasModeActivity, bundle)
        else:
            from lib.plugin_activity import PluginActivity
            bundle = {
                'plugin_dir': info.plugin_dir,
                'manifest': info.manifest,
                'ui_definition': info.ui_definition,
                'entry_class': info.activity_class,
                'plugin_key': info.key,
            }
            actstack.start_activity(PluginActivity, bundle)

    def _onPageChange(self, page):
        """Callback from ListView when page changes."""
        self._updateTitle()

    def _updateTitle(self):
        """Update title: "Plugins N/M"."""
        base_title = "Plugins"
        if self.lv_plugins is not None:
            total = self.lv_plugins.getPageCount()
            current = self.lv_plugins.getPagePosition() + 1
            self.setTitle('%s %d/%d' % (base_title, current, total))
        else:
            self.setTitle(base_title)
