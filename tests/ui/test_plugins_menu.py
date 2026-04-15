"""Tests for PluginsMenuActivity — plugin submenu.

Covers:
  - Title display
  - List population (non-promoted only)
  - M1/PWR finish behavior
  - UP/DOWN scrolling
  - OK launches plugin activity
  - Empty plugin list

All tests run headless via MockCanvas and actstack._canvas_factory.
"""

import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import KEY_PWR, KEY_UP, KEY_DOWN, KEY_OK, KEY_M1, KEY_M2
from plugin_loader import PluginInfo
from plugins_menu import PluginsMenuActivity


# =====================================================================
# Helpers
# =====================================================================

def _make_plugin_info(name, key, promoted=False, canvas_mode=False, order=100):
    """Create a minimal PluginInfo for testing."""
    return PluginInfo(
        name=name,
        version='1.0.0',
        author='',
        description='',
        key=key,
        plugin_dir='/tmp/' + key,
        promoted=promoted,
        canvas_mode=canvas_mode,
        fullscreen=False,
        order=order,
        permissions=[],
        icon_path=None,
        entry_class_name='X',
        activity_class=type('X', (), {}),
        manifest={'name': name, 'version': '1.0.0'},
        ui_definition=None,
        key_map=None,
        binary=None,
        args=[],
    )


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


@pytest.fixture
def mock_plugins(monkeypatch):
    """Populate actmain._discovered_plugins with test plugins."""
    import actmain
    plugins = [
        _make_plugin_info('Alpha', 'alpha', promoted=False, order=10),
        _make_plugin_info('Beta', 'beta', promoted=False, order=20),
        _make_plugin_info('Gamma', 'gamma', promoted=True, order=5),
    ]
    monkeypatch.setattr(actmain, '_discovered_plugins', plugins)
    return plugins


@pytest.fixture
def empty_plugins(monkeypatch):
    """Set actmain._discovered_plugins to empty."""
    import actmain
    monkeypatch.setattr(actmain, '_discovered_plugins', [])


# =====================================================================
# Tests
# =====================================================================

class TestPluginsMenu:
    """Tests for PluginsMenuActivity."""

    def test_title_shows_plugins(self, mock_plugins):
        """Title contains 'Plugins'."""
        act = actstack.start_activity(PluginsMenuActivity)
        canvas = act.getCanvas()
        title_items = canvas.find_withtag('tags_title_text')
        assert len(title_items) > 0
        title = canvas.itemcget(title_items[0], 'text')
        assert 'Plugins' in title

    def test_lists_non_promoted_only(self, mock_plugins):
        """Only non-promoted plugins appear in the submenu list."""
        act = actstack.start_activity(PluginsMenuActivity)
        # _plugins should exclude promoted (Gamma)
        assert len(act._plugins) == 2
        names = [p.name for p in act._plugins]
        assert 'Alpha' in names
        assert 'Beta' in names
        assert 'Gamma' not in names

    def test_m1_finishes(self, mock_plugins):
        """M1 key finishes the activity."""
        act = actstack.start_activity(PluginsMenuActivity)
        assert actstack.get_stack_size() == 1
        act.callKeyEvent(KEY_M1)
        assert actstack.get_stack_size() == 0

    def test_pwr_finishes(self, mock_plugins):
        """PWR key finishes the activity."""
        act = actstack.start_activity(PluginsMenuActivity)
        assert actstack.get_stack_size() == 1
        act.callKeyEvent(KEY_PWR)
        assert actstack.get_stack_size() == 0

    def test_up_down_scrolls(self, mock_plugins):
        """UP/DOWN keys change the ListView selection."""
        act = actstack.start_activity(PluginsMenuActivity)
        assert act.lv_plugins is not None
        initial_sel = act.lv_plugins.selection()
        act.callKeyEvent(KEY_DOWN)
        new_sel = act.lv_plugins.selection()
        assert new_sel == initial_sel + 1

    def test_ok_launches_plugin(self, mock_plugins):
        """OK key launches a plugin activity (stack grows)."""
        act = actstack.start_activity(PluginsMenuActivity)
        assert actstack.get_stack_size() == 1
        # OK on first item should launch a plugin
        act.callKeyEvent(KEY_OK)
        assert actstack.get_stack_size() >= 2

    def test_empty_plugins_no_crash(self, empty_plugins):
        """Empty plugin list doesn't crash, just shows empty menu."""
        act = actstack.start_activity(PluginsMenuActivity)
        assert act._plugins == []
        # Key events should not crash
        act.callKeyEvent(KEY_DOWN)
        act.callKeyEvent(KEY_OK)
        # M1 exits cleanly
        act.callKeyEvent(KEY_M1)
        assert actstack.get_stack_size() == 0
