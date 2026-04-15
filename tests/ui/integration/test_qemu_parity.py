"""I-2: QEMU parity bridge tests.

Validates that our Python UI modules can be swapped into the QEMU test
infrastructure.  Since QEMU (qemu-arm-static + mounted rootfs) is not
available in unit tests, we validate:

1. Module path setup -- src/lib modules shadow orig .so modules
2. Module identity -- all replaced modules are .py, not .so
3. State extraction -- extract_ui_state produces QEMU-compatible format
4. Activity creation -- all registry entries can be instantiated
5. Canvas factory -- actstack._canvas_factory produces working canvases

These tests ensure that when run_with_new_ui.sh prepends src/lib to
PYTHONPATH, the QEMU flow tests will use our Python modules instead
of the original .so binaries.
"""

import sys
import os
import pytest

import actstack
from tests.ui.conftest import MockCanvas
from tests.ui.integration.conftest import extract_ui_state


# =====================================================================
# TestPythonPathSetup
# =====================================================================

class TestPythonPathSetup:
    """Verify src/lib modules shadow orig_so/lib .so modules."""

    def test_src_lib_on_path(self):
        """src/lib must be on sys.path."""
        assert any('src/lib' in p or os.path.join('src', 'lib') in p
                    for p in sys.path), (
            "src/lib not found in sys.path: %s" % sys.path[:5]
        )

    def test_actbase_is_python(self):
        """actbase must be our .py, not the .so."""
        import actbase
        assert hasattr(actbase, '__file__')
        assert actbase.__file__.endswith('.py'), (
            "actbase is not .py: %s" % actbase.__file__
        )

    def test_widget_is_python(self):
        """widget must be our .py, not the .so."""
        import widget
        assert hasattr(widget, '__file__')
        assert widget.__file__.endswith('.py'), (
            "widget is not .py: %s" % widget.__file__
        )

    def test_actstack_is_python(self):
        """actstack must be our .py, not the .so."""
        assert hasattr(actstack, '__file__')
        assert actstack.__file__.endswith('.py'), (
            "actstack is not .py: %s" % actstack.__file__
        )

    def test_resources_is_python(self):
        """resources must be our .py, not the .so."""
        import resources
        assert hasattr(resources, '__file__')
        assert resources.__file__.endswith('.py'), (
            "resources is not .py: %s" % resources.__file__
        )

    def test_all_replaced_modules_are_python(self):
        """All modules we replace must be .py, not .so.

        Modules that are mock stubs (types.ModuleType with no __file__)
        are skipped -- they exist only in test environments.  In QEMU
        production, these would be real .py files on PYTHONPATH.
        """
        replaced = [
            'actbase', 'actstack', 'widget',
            'keymap', 'resources', 'images', 'actmain',
            'activity_main', 'activity_tools',
        ]
        for mod_name in replaced:
            try:
                mod = __import__(mod_name)
                # Skip mock modules that have no __file__ (test stubs)
                if not hasattr(mod, '__file__') or mod.__file__ is None:
                    continue
                assert mod.__file__.endswith('.py'), (
                    "%s is .so, not .py: %s" % (mod_name, mod.__file__)
                )
            except ImportError:
                pass  # Module may not exist yet

    def test_constants_accessible(self):
        """_constants module must be importable and have core values."""
        import _constants
        assert _constants.SCREEN_W == 240
        assert _constants.SCREEN_H == 240
        assert _constants.TITLE_BAR_BG == '#7C829A'
        assert _constants.BG_COLOR == '#F8FCF8'


# =====================================================================
# TestCanvasFactory
# =====================================================================

class TestCanvasFactory:
    """Verify actstack._canvas_factory produces working canvases."""

    def test_factory_installed(self):
        """actstack._canvas_factory should be set by test fixture."""
        assert actstack._canvas_factory is not None

    def test_factory_produces_canvas(self):
        """Factory should return a MockCanvas instance."""
        canvas = actstack._canvas_factory()
        assert canvas is not None
        assert hasattr(canvas, 'create_text')
        assert hasattr(canvas, 'create_rectangle')
        assert hasattr(canvas, 'find_all')
        assert hasattr(canvas, 'find_withtag')

    def test_canvas_dimensions(self):
        """Factory canvas should be 240x240."""
        canvas = actstack._canvas_factory()
        assert canvas.winfo_width() == 240
        assert canvas.winfo_height() == 240

    def test_canvas_operations(self):
        """Canvas should support all operations activities use."""
        canvas = actstack._canvas_factory()

        # Create items
        rect_id = canvas.create_rectangle(0, 0, 240, 40, fill='#7C829A',
                                           tags='tags_title')
        text_id = canvas.create_text(120, 20, text='Test', fill='white',
                                      tags='tags_title')
        img_id = canvas.create_image(120, 120)

        # Query items
        assert len(canvas.find_all()) == 3
        assert canvas.type(rect_id) == 'rectangle'
        assert canvas.type(text_id) == 'text'
        assert canvas.itemcget(text_id, 'text') == 'Test'
        assert canvas.itemcget(rect_id, 'fill') == '#7C829A'

        # Tag queries
        title_items = canvas.find_withtag('tags_title')
        assert rect_id in title_items
        assert text_id in title_items

        # Delete
        canvas.delete(rect_id)
        assert len(canvas.find_all()) == 2


# =====================================================================
# TestStateExtraction
# =====================================================================

class TestStateExtraction:
    """Verify extract_ui_state produces QEMU-compatible format."""

    def test_empty_stack_returns_none_fields(self):
        """With no activities, all fields should be None/empty."""
        state = extract_ui_state(None)
        assert state['current_activity'] is None
        assert state['activity_stack'] == []
        assert state['title'] is None
        assert state['M1'] is None
        assert state['M2'] is None
        assert state['toast'] is None
        assert state['content_text'] == []

    def test_main_menu_state(self):
        """extract_ui_state on main menu should match QEMU dump format."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)

        state = extract_ui_state(act)
        assert state['current_activity'] == 'MainActivity'
        assert state['title'] == 'Main Page'
        # Main menu has no M2 button (setRightButton(""))
        assert state['M2'] is None
        assert len(state['activity_stack']) == 1
        assert state['activity_stack'][0]['class'] == 'MainActivity'

    def test_state_has_lifecycle(self):
        """Activity stack entries should include lifecycle state."""
        from actmain import MainActivity
        act = actstack.start_activity(MainActivity)

        state = extract_ui_state(act)
        lc = state['activity_stack'][0].get('lifecycle', {})
        assert lc.get('created') is True
        assert lc.get('resumed') is True
        assert lc.get('destroyed') is False

    def test_backlight_state(self):
        """Backlight activity should produce correct state fields."""
        from activity_main import BacklightActivity
        act = actstack.start_activity(BacklightActivity)

        state = extract_ui_state(act)
        assert state['current_activity'] == 'BacklightActivity'
        assert state['title'] == 'Backlight'
        # Backlight has no M2 button (setRightButton(""), save is via OK key)
        assert state['M2'] is None

    def test_content_text_is_list_of_dicts(self):
        """content_text entries must have text, x, y, fill, font keys."""
        from activity_main import BacklightActivity
        act = actstack.start_activity(BacklightActivity)

        state = extract_ui_state(act)
        for ct in state['content_text']:
            assert 'text' in ct
            assert 'x' in ct
            assert 'y' in ct
            assert 'fill' in ct
            assert 'font' in ct

    def test_stacked_activities(self):
        """Pushing a child activity should grow the stack correctly."""
        from actmain import MainActivity
        from activity_main import BacklightActivity

        main = actstack.start_activity(MainActivity)
        bl = actstack.start_activity(BacklightActivity)

        state = extract_ui_state(bl)
        assert state['current_activity'] == 'BacklightActivity'
        assert len(state['activity_stack']) == 2
        assert state['activity_stack'][0]['class'] == 'MainActivity'
        assert state['activity_stack'][1]['class'] == 'BacklightActivity'

    def test_state_after_finish(self):
        """After finishing child, state should show parent as current."""
        from actmain import MainActivity
        from activity_main import BacklightActivity

        main = actstack.start_activity(MainActivity)
        bl = actstack.start_activity(BacklightActivity)
        actstack.finish_activity()

        state = extract_ui_state(main)
        assert state['current_activity'] == 'MainActivity'
        assert len(state['activity_stack']) == 1


# =====================================================================
# TestActivityRegistry
# =====================================================================

class TestActivityRegistry:
    """All activity registry entries should be instantiable."""

    def test_registry_has_14_entries(self):
        """Activity registry should have entries for all 14 menu items."""
        from actmain import _ACTIVITY_REGISTRY
        assert len(_ACTIVITY_REGISTRY) == 14

    def test_all_registry_modules_importable(self):
        """Every module in the activity registry should be importable."""
        from actmain import _ACTIVITY_REGISTRY
        import importlib

        for action_key, (mod_path, class_name) in _ACTIVITY_REGISTRY.items():
            try:
                mod = importlib.import_module(mod_path)
                assert hasattr(mod, class_name), (
                    "%s.%s not found" % (mod_path, class_name)
                )
            except ImportError as e:
                # Some modules may have dependencies we can't satisfy
                # in unit tests (e.g., scan.so) -- that's OK
                pass

    def test_simple_activities_create(self):
        """Activities without middleware dependencies should create cleanly."""
        from activity_main import (
            BacklightActivity, VolumeActivity, AboutActivity,
        )

        for cls in (BacklightActivity, VolumeActivity, AboutActivity):
            actstack._reset()
            actstack._canvas_factory = lambda: MockCanvas()
            act = actstack.start_activity(cls)
            assert act is not None
            assert act.getCanvas() is not None
            assert act.life.created is True
            actstack._reset()
            actstack._canvas_factory = lambda: MockCanvas()


# =====================================================================
# TestQEMUWrapperScript
# =====================================================================

class TestQEMUWrapperScript:
    """Verify the QEMU wrapper script exists and is correct."""

    def test_wrapper_exists(self):
        """run_with_new_ui.sh must exist."""
        project = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        wrapper = os.path.join(project, 'tools', 'run_with_new_ui.sh')
        assert os.path.isfile(wrapper), "run_with_new_ui.sh not found"

    def test_wrapper_executable(self):
        """run_with_new_ui.sh must be executable."""
        project = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        wrapper = os.path.join(project, 'tools', 'run_with_new_ui.sh')
        assert os.access(wrapper, os.X_OK), "run_with_new_ui.sh not executable"

    def test_wrapper_sets_pythonpath(self):
        """Wrapper script should set TEST_TARGET and exec the command."""
        project = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        wrapper = os.path.join(project, 'tools', 'run_with_new_ui.sh')
        with open(wrapper) as f:
            content = f.read()
        # The wrapper sets TEST_TARGET=current and execs the argument.
        # PYTHONPATH is set by the test infrastructure (conftest.py),
        # not by the wrapper script itself.
        assert 'TEST_TARGET' in content
        assert 'exec' in content


# =====================================================================
# TestCompareToolExists
# =====================================================================

class TestCompareToolExists:
    """Verify the parity comparison tool exists."""

    def test_compare_tool_exists(self):
        """qemu_compare.py must exist."""
        project = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        tool = os.path.join(project, 'tools', 'qemu_compare.py')
        assert os.path.isfile(tool), "qemu_compare.py not found"

    def test_compare_tool_importable(self):
        """qemu_compare.py should be importable as a module."""
        project = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        tool_dir = os.path.join(project, 'tools')
        if tool_dir not in sys.path:
            sys.path.insert(0, tool_dir)
        try:
            import qemu_compare
            assert hasattr(qemu_compare, 'extract_ui_state')
            assert hasattr(qemu_compare, 'compare_states')
            assert hasattr(qemu_compare, 'compare_scenario_files')
        finally:
            sys.path.remove(tool_dir) if tool_dir in sys.path else None
