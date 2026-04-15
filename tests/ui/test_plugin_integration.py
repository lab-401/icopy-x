"""Integration tests for the plugin system end-to-end.

Covers:
  - init_plugins discovers real plugins
  - Main menu includes "Plugins" entry when plugins exist
  - Promoted plugins appear on main menu
  - Full navigation flow: Main -> Plugins -> select -> PWR back

All tests run headless via MockCanvas and actstack._canvas_factory.
"""

import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_PWR, KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2
import actmain
from actmain import MainActivity


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def reset_actstack():
    """Reset actstack state before each test."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


@pytest.fixture(autouse=True)
def reset_discovered_plugins():
    """Ensure _discovered_plugins is reset after each test."""
    original = actmain._discovered_plugins[:]
    yield
    actmain._discovered_plugins = original


# =====================================================================
# Tests
# =====================================================================

class TestPluginIntegration:
    """End-to-end plugin system integration tests."""

    def test_init_plugins_discovers_real_plugins(self):
        """init_plugins() populates _discovered_plugins from disk."""
        actmain._discovered_plugins = []
        actmain.init_plugins()
        assert len(actmain._discovered_plugins) >= 4
        names = [p.name for p in actmain._discovered_plugins]
        assert 'PM3 Raw' in names
        assert 'DOOM' in names

    def test_main_menu_with_plugins_has_entry(self):
        """MainActivity menu includes 'Plugins' when non-promoted plugins exist."""
        actmain.init_plugins()
        act = actstack.start_activity(MainActivity)
        labels = [item[0] for item in act._menu_items]
        assert 'Plugins' in labels

    def test_main_menu_promoted_plugin_visible(self, monkeypatch):
        """A promoted plugin appears directly on the main menu."""
        from plugin_loader import PluginInfo

        promoted = PluginInfo(
            name='PromoTest',
            version='1.0.0',
            author='Test',
            description='',
            key='promo_test',
            plugin_dir='/tmp/promo_test',
            promoted=True,
            canvas_mode=False,
            fullscreen=False,
            order=50,
            permissions=[],
            icon_path=None,
            entry_class_name='PromoPlugin',
            activity_class=type('PromoPlugin', (), {}),
            manifest={'name': 'PromoTest', 'version': '1.0.0'},
            ui_definition=None,
            key_map=None,
            binary=None,
            args=[],
        )
        non_promoted = PluginInfo(
            name='RegularPlugin',
            version='1.0.0',
            author='Test',
            description='',
            key='regular',
            plugin_dir='/tmp/regular',
            promoted=False,
            canvas_mode=False,
            fullscreen=False,
            order=100,
            permissions=[],
            icon_path=None,
            entry_class_name='RegPlugin',
            activity_class=type('RegPlugin', (), {}),
            manifest={'name': 'RegularPlugin', 'version': '1.0.0'},
            ui_definition=None,
            key_map=None,
            binary=None,
            args=[],
        )

        monkeypatch.setattr(actmain, '_discovered_plugins', [promoted, non_promoted])
        act = actstack.start_activity(MainActivity)
        labels = [item[0] for item in act._menu_items]
        # Promoted plugin name should appear directly on menu
        assert 'PromoTest' in labels
        # "Plugins" submenu for non-promoted
        assert 'Plugins' in labels

    def test_full_navigation_flow(self):
        """Navigate Main -> Plugins -> select -> PWR back -> PWR back to Main."""
        actmain.init_plugins()
        # Start at main menu
        main_act = actstack.start_activity(MainActivity)
        assert actstack.get_stack_size() == 1

        # Find "Plugins" position in the menu
        plugins_idx = None
        for i, item in enumerate(main_act._menu_items):
            if item[0] == 'Plugins':
                plugins_idx = i
                break

        if plugins_idx is None:
            pytest.skip('No non-promoted plugins discovered')

        # Navigate to Plugins position in the ListView
        if main_act.lv_main_page is not None:
            for _ in range(plugins_idx):
                main_act.callKeyEvent(KEY_DOWN)
            # Launch Plugins submenu
            main_act.callKeyEvent(KEY_OK)
        else:
            # Direct launch
            main_act._launchActivity(plugins_idx)

        assert actstack.get_stack_size() == 2
        plugins_act = actstack.get_current_activity()

        # Select first plugin (OK on first item)
        plugins_act.callKeyEvent(KEY_OK)
        assert actstack.get_stack_size() >= 3

        # PWR back from plugin activity
        current = actstack.get_current_activity()
        current.callKeyEvent(KEY_PWR)
        # Should be back at Plugins menu or fewer
        assert actstack.get_stack_size() <= 3

        # PWR back from Plugins menu (if still there)
        if actstack.get_stack_size() > 1:
            current = actstack.get_current_activity()
            current.callKeyEvent(KEY_PWR)

        # Should be back at main menu
        assert actstack.get_stack_size() >= 1
        assert isinstance(actstack.get_current_activity(), MainActivity)
