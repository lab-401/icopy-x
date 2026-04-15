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

"""Plugin activity runners — PluginActivity and CanvasModeActivity.

Provides two BaseActivity subclasses for running user-installed plugins:

  PluginActivity     — JSON-driven state-machine runner (ui.json)
  CanvasModeActivity — subprocess-based runner (DOOM, etc.)

Both enforce the #1 UX law: **PWR ALWAYS EXITS**.  Plugin code never
receives PWR events.  The framework intercepts PWR before dispatch.

Architecture:
    PluginLoader discovers plugins -> PluginActivity(bundle) launched
    -> onCreate loads ui.json state machine (or delegates to entry_class)
    -> onKeyEvent dispatches actions from JSON key bindings
    -> run:<method> calls plugin methods in background threads
    -> PWR intercepted at framework level, always calls finish()

Import convention: ``from lib.plugin_activity import PluginActivity``

Python 3.8 compatible.
"""

import json
import logging
import os
import subprocess
import threading
import traceback

from lib.actbase import BaseActivity
from lib import actstack
from lib._constants import (
    KEY_PWR,
    KEY_UP,
    KEY_DOWN,
    KEY_OK,
    KEY_M1,
    KEY_M2,
    CONTENT_Y0,
    BTN_BAR_Y0,
    SCREEN_W,
    BG_COLOR,
)
from lib.json_renderer import JsonRenderer

logger = logging.getLogger(__name__)


# ======================================================================
# PluginActivity — JSON-driven plugin runner
# ======================================================================

class PluginActivity(BaseActivity):
    """JSON-driven plugin activity runner.

    Loads a plugin's ui.json state machine and drives screen rendering,
    key dispatch, state transitions, and background task execution.

    If the plugin provides an entry_class (a Python class in plugin.py),
    an instance is created and ``run:<method>`` actions invoke methods on
    it.  If the plugin provides no ui.json, the entry_class is expected
    to be a BaseActivity subclass and is launched directly.

    PWR ALWAYS EXITS.  The onKeyEvent method intercepts PWR before any
    plugin code can see it.  This is non-negotiable.

    Bundle keys:
        plugin_dir   — absolute path to the plugin directory
        manifest     — parsed manifest.json dict
        ui_definition — parsed ui.json dict, or None
        entry_class  — the plugin's Python class (from plugin.py), or None
        plugin_key   — unique plugin identifier string
    """

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self._plugin_dir = None
        self._manifest = {}
        self._ui_def = None
        self._plugin_instance = None
        self._renderer = None
        self._state = {}              # variable state for {placeholder} resolution
        self._current_state_id = None
        self._screens = {}            # state_id -> state definition dict
        self._screen_stack = []       # internal screen stack for push/pop
        self._list_state = {}         # per-screen list state: screen_id -> {selected, scroll_offset}
        self._permissions = []
        self._entry_class = None
        self._bg_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def onCreate(self, bundle=None):
        """Initialize the plugin from its bundle.

        Loads the ui.json state machine if provided.  Creates an instance
        of the plugin's entry_class if provided.  If both are absent,
        shows an error toast and finishes.
        """
        super().onCreate(bundle)

        if bundle is None:
            bundle = self._bundle or {}

        self._plugin_dir = bundle.get('plugin_dir', '')
        self._manifest = bundle.get('manifest', {})
        self._ui_def = bundle.get('ui_definition')
        self._entry_class = bundle.get('entry_class')
        self._permissions = self._manifest.get('permissions', [])

        plugin_name = self._manifest.get('name', 'Plugin')

        # Set up the renderer on our canvas
        canvas = self.getCanvas()
        if canvas is not None:
            self._renderer = JsonRenderer(canvas)
            self._renderer.set_state(self._state)

        # If entry_class is a BaseActivity subclass with no ui.json,
        # delegate entirely: launch it as a child activity.
        if self._entry_class is not None and self._ui_def is None:
            if _is_activity_subclass(self._entry_class):
                # Launch the plugin's own activity class directly.
                # Pass the bundle through so the plugin has its context.
                child_bundle = dict(bundle)
                child_bundle['_host'] = self
                actstack.start_activity(self._entry_class, child_bundle)
                # We finish ourselves since the child takes over.
                self.finish()
                return

        # Create plugin instance (for run:<method> dispatch) if we have
        # an entry_class that is NOT a full BaseActivity subclass.
        if self._entry_class is not None:
            try:
                self._plugin_instance = self._entry_class()
                # Inject host reference so plugin methods can call helpers.
                self._plugin_instance.host = self
            except Exception:
                logger.error("Failed to instantiate plugin entry_class: %s",
                             traceback.format_exc())
                self._plugin_instance = None

        # Load ui.json state machine
        if self._ui_def is not None:
            self._load_ui_definition(self._ui_def)
        elif self._plugin_instance is None:
            # No UI definition and no plugin instance — nothing to run.
            self.setTitle(plugin_name)
            self._show_error_toast("Plugin has no UI definition or entry class.")
            return

        # Set title and render initial screen
        self.setTitle(plugin_name)
        if self._current_state_id is not None:
            self._render_current_screen()
            # Execute on_enter for initial state if defined
            self._execute_on_enter(self._current_state_id)

    def onResume(self):
        """Re-render current screen when activity regains focus."""
        super().onResume()
        if self._current_state_id is not None and self._renderer is not None:
            self._render_current_screen()

    def onDestroy(self):
        """Clean up plugin resources."""
        # Give the plugin instance a chance to clean up
        if self._plugin_instance is not None:
            cleanup = getattr(self._plugin_instance, 'on_destroy', None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    logger.error("Plugin on_destroy error: %s",
                                 traceback.format_exc())
        self._plugin_instance = None
        self._renderer = None
        super().onDestroy()

    # ------------------------------------------------------------------
    # Key handling — PWR ALWAYS EXITS
    # ------------------------------------------------------------------

    def onKeyEvent(self, key):
        """Dispatch key events.

        PWR is NEVER passed to the plugin.  It is intercepted here
        unconditionally.  _handlePWR() is called first to dismiss
        toasts or check busy state.  If not handled, finish() is called.
        """
        # -------------------------------------------------------
        # PWR ALWAYS EXITS — this is the #1 law.
        # -------------------------------------------------------
        if key == KEY_PWR:
            if self._handlePWR():
                return
            self.finish()
            return

        # Busy state — swallow all keys
        if self.isbusy():
            return

        # Look up key action in current screen definition
        state_def = self._screens.get(self._current_state_id)
        if state_def is None:
            return

        screen = state_def.get('screen', state_def)
        keys_map = screen.get('keys', {})

        action = keys_map.get(key)
        if action is not None:
            self._execute_action(action)

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def _execute_action(self, action_str):
        """Parse and execute an action string.

        Supported actions:
            scroll:N        — scroll list selection by N positions
            select          — activate the currently selected list item
            finish          — call self.finish()
            push:<screen_id> — push a screen onto the internal stack
            pop             — pop the internal screen stack
            set_state:<id>  — transition to a new state
            run:<method>    — call method on plugin instance in bg thread
            noop            — do nothing
        """
        if not action_str or not isinstance(action_str, str):
            return

        action_str = action_str.strip()

        if action_str == 'noop':
            return

        if action_str == 'finish':
            self.finish()
            return

        if action_str == 'select':
            self._handle_select()
            return

        if action_str == 'pop':
            self._handle_pop()
            return

        if action_str.startswith('scroll:'):
            try:
                n = int(action_str[7:])
                self._handle_scroll(n)
            except ValueError:
                logger.warning("Invalid scroll value: %s", action_str)
            return

        if action_str.startswith('push:'):
            screen_id = action_str[5:]
            self._handle_push(screen_id)
            return

        if action_str.startswith('set_state:'):
            state_id = action_str[10:]
            self._set_state(state_id)
            return

        if action_str.startswith('run:'):
            method_name = action_str[4:]
            self._handle_run(method_name)
            return

        logger.warning("Unknown plugin action: %s", action_str)

    # ------------------------------------------------------------------
    # UI state machine
    # ------------------------------------------------------------------

    def _load_ui_definition(self, ui_def):
        """Load the ui.json state machine definition.

        Supports two formats:
        1. State machine: {"entry_screen"/"initial_state", "screens"/"states": {...}}
        2. Flat screens: {"entry_screen", "screens": {"id": {screen_def}}}
        """
        # Normalize: support both "states" and "screens" keys
        states = ui_def.get('states', ui_def.get('screens', {}))
        entry = ui_def.get('initial_state', ui_def.get('entry_screen'))

        if not states:
            logger.error("Plugin ui.json has no states/screens")
            return

        # Strip any PWR key bindings from all screens (enforced at load time)
        for state_id, state_def in states.items():
            screen = state_def.get('screen', state_def)
            keys = screen.get('keys', {})
            keys.pop('PWR', None)
            keys.pop(KEY_PWR, None)

        self._screens = states

        if entry and entry in states:
            self._current_state_id = entry
        else:
            # Fall back to first state
            self._current_state_id = next(iter(states))

    def _set_state(self, state_id):
        """Transition to a new state.

        Updates current_state_id and re-renders.  Executes the new
        state's on_enter action if defined.
        """
        if state_id not in self._screens:
            logger.warning("Plugin state not found: %s", state_id)
            self._show_error_toast("Screen not found: %s" % state_id)
            return

        self._current_state_id = state_id
        self._render_current_screen()
        self._execute_on_enter(state_id)

    def _execute_on_enter(self, state_id):
        """Execute the on_enter action for a state, if defined."""
        state_def = self._screens.get(state_id, {})
        on_enter = state_def.get('on_enter')
        if on_enter:
            self._execute_action(on_enter)

    # ------------------------------------------------------------------
    # Screen rendering
    # ------------------------------------------------------------------

    def _render_current_screen(self):
        """Render the current state's screen definition.

        Resolves {variable} placeholders from the plugin state dict,
        clears the content area, and renders via JsonRenderer.
        """
        if self._renderer is None:
            return

        state_def = self._screens.get(self._current_state_id)
        if state_def is None:
            return

        # The state definition may be a full state (with 'screen' key)
        # or a bare screen definition.
        screen = state_def.get('screen', state_def)

        canvas = self.getCanvas()
        if canvas is None:
            return

        # Update renderer state for variable resolution
        self._renderer.set_state(self._state)

        # Clear previous content (preserve title bar and button bar bg)
        canvas.delete('_jr_content')
        canvas.delete('_jr_content_bg')
        canvas.delete('_jr_buttons')

        # Inject list state (selected index, scroll offset) into content
        screen = self._inject_list_state(screen)

        # Resolve title
        title = screen.get('title')
        if title:
            resolved_title = self._renderer.resolve(title)
            page = screen.get('page')
            if page:
                resolved_title = '%s %s' % (resolved_title, self._renderer.resolve(page))
            self.setTitle(resolved_title)

        # Render content and buttons
        self._renderer.render(screen)

        # Handle buttons for M1/M2 active state
        buttons = screen.get('buttons', {})
        left_btn = buttons.get('left')
        right_btn = buttons.get('right')
        if left_btn:
            resolved = self._renderer.resolve(
                left_btn if isinstance(left_btn, str)
                else left_btn.get('text', '')
            )
            self.setLeftButton(resolved)
        else:
            self.dismissButton(left=True)
        if right_btn:
            resolved = self._renderer.resolve(
                right_btn if isinstance(right_btn, str)
                else right_btn.get('text', '')
            )
            self.setRightButton(resolved)
        else:
            self.dismissButton(right=True)

        # Show toast if defined in screen
        toast_def = screen.get('toast')
        if toast_def:
            self._show_screen_toast(toast_def)

    def _inject_list_state(self, screen):
        """Inject persisted list selection/scroll into screen content.

        Returns a shallow copy of the screen with updated content if
        the content type is 'list' and we have saved state for this
        screen.
        """
        content = screen.get('content', {})
        if content.get('type') != 'list':
            return screen

        state_id = self._current_state_id
        if state_id in self._list_state:
            saved = self._list_state[state_id]
            # Shallow copy screen and content to avoid mutating originals
            screen = dict(screen)
            content = dict(content)
            content['selected'] = saved.get('selected', 0)
            content['scroll_offset'] = saved.get('scroll_offset', 0)
            screen['content'] = content
        return screen

    def _show_screen_toast(self, toast_def):
        """Show a toast defined in a screen's toast field."""
        text = self._renderer.resolve(toast_def.get('text', ''))
        icon = toast_def.get('icon')
        timeout = toast_def.get('timeout', 3000)
        if text:
            self._ensure_toast()
            try:
                duration = timeout if timeout else 0
                self._toast.show(text, duration_ms=duration, icon=icon)
            except Exception:
                logger.error("Toast show error: %s", traceback.format_exc())

    def _ensure_toast(self):
        """Lazily create the Toast widget if needed."""
        if getattr(self, '_toast', None) is None:
            canvas = self.getCanvas()
            if canvas is not None:
                from lib.widget import Toast
                self._toast = Toast(canvas)

    # ------------------------------------------------------------------
    # List handling
    # ------------------------------------------------------------------

    def _handle_scroll(self, n):
        """Scroll the list selection by n positions."""
        state_def = self._screens.get(self._current_state_id)
        if state_def is None:
            return

        screen = state_def.get('screen', state_def)
        content = screen.get('content', {})
        if content.get('type') != 'list':
            return

        items = content.get('items', [])
        if not items:
            return

        page_size = content.get('page_size', 5)
        state_id = self._current_state_id

        # Get current list state
        saved = self._list_state.get(state_id, {'selected': 0, 'scroll_offset': 0})
        selected = saved.get('selected', 0)
        scroll_offset = saved.get('scroll_offset', 0)

        # Compute new selection
        new_selected = selected + n
        new_selected = max(0, min(new_selected, len(items) - 1))

        # Adjust scroll offset to keep selection visible
        if new_selected < scroll_offset:
            scroll_offset = new_selected
        elif new_selected >= scroll_offset + page_size:
            scroll_offset = new_selected - page_size + 1

        self._list_state[state_id] = {
            'selected': new_selected,
            'scroll_offset': scroll_offset,
        }

        self._render_current_screen()

    def _handle_select(self):
        """Activate the currently selected list item."""
        state_def = self._screens.get(self._current_state_id)
        if state_def is None:
            return

        screen = state_def.get('screen', state_def)
        content = screen.get('content', {})
        if content.get('type') != 'list':
            return

        items = content.get('items', [])
        if not items:
            return

        state_id = self._current_state_id
        saved = self._list_state.get(state_id, {'selected': 0, 'scroll_offset': 0})
        selected = saved.get('selected', 0)

        if selected < 0 or selected >= len(items):
            return

        item = items[selected]
        action = item.get('action')
        if action:
            self._execute_action(action)

    # ------------------------------------------------------------------
    # Screen stack (push/pop within plugin screens)
    # ------------------------------------------------------------------

    def _handle_push(self, screen_id):
        """Push current screen onto internal stack, navigate to screen_id."""
        if screen_id not in self._screens:
            logger.warning("Plugin push target not found: %s", screen_id)
            self._show_error_toast("Screen not found: %s" % screen_id)
            return

        # Save current state on stack
        self._screen_stack.append(self._current_state_id)
        self._set_state(screen_id)

    def _handle_pop(self):
        """Pop the internal screen stack, returning to previous screen."""
        if self._screen_stack:
            prev_state = self._screen_stack.pop()
            self._set_state(prev_state)
        else:
            # No screens on stack — finish the activity
            self.finish()

    # ------------------------------------------------------------------
    # Background task execution (run:<method>)
    # ------------------------------------------------------------------

    def _handle_run(self, method_name):
        """Call a method on the plugin instance in a background thread.

        The method is looked up on self._plugin_instance.  It runs in
        a daemon thread via startBGTask.  The activity enters busy state
        during execution and transitions based on the result.
        """
        if self._plugin_instance is None:
            logger.warning("No plugin instance for run:%s", method_name)
            self._show_error_toast("Plugin has no entry class")
            return

        method = getattr(self._plugin_instance, method_name, None)
        if method is None or not callable(method):
            logger.warning("Plugin method not found: %s", method_name)
            self._show_error_toast("Method not found: %s" % method_name)
            return

        self.setbusy()

        def _bg_task():
            result = None
            error = None
            try:
                result = method()
            except Exception as exc:
                error = exc
                logger.error("Plugin run:%s error: %s",
                             method_name, traceback.format_exc())
            finally:
                # Always return to UI thread for state updates
                root = actstack._root
                if root is not None:
                    root.after(0, lambda: self._on_run_complete(
                        method_name, result, error))
                else:
                    # No root (headless) — call directly
                    self._on_run_complete(method_name, result, error)

        self.startBGTask(_bg_task)

    def _on_run_complete(self, method_name, result, error):
        """Handle completion of a run:<method> background task.

        Called on the UI thread.  Updates state variables from the
        result and checks transition conditions.

        Transition priority:
            1. on_result.<field>==<value> (most specific)
            2. on_complete (general)
        If a result-based transition fires, on_complete is skipped to
        avoid checking the NEW state's transitions by mistake.
        """
        self.setidle()

        if error is not None:
            self._state['_error'] = str(error)
            self._check_transitions('on_error', error=error)
            return

        # Remember state before transitions to detect if one fired
        state_before = self._current_state_id

        # If result is a dict, merge into state variables
        if isinstance(result, dict):
            self._state.update(result)
            # Check field-specific transitions (most specific first)
            self._check_transitions_from_result(result)
        elif result is not None:
            self._state['_result'] = result

        # Only check on_complete if no result-based transition already fired
        if self._current_state_id == state_before:
            self._check_transitions('on_complete', result=result)

        # Re-render with updated state (only if no transition already rendered)
        if self._current_state_id == state_before and self._current_state_id is not None:
            self._render_current_screen()

    def _check_transitions(self, condition, result=None, error=None):
        """Check the current state's transitions map for a matching condition.

        Transition conditions:
            on_error          — run method raised an exception
            on_complete       — run method completed (any result)
            on_result.<field>==<value> — result dict field matches value
            on_timeout:<ms>   — (handled separately by timer)
        """
        state_def = self._screens.get(self._current_state_id, {})
        transitions = state_def.get('transitions', {})

        if not transitions:
            return

        # Direct condition match
        target = transitions.get(condition)
        if target is not None:
            self._set_state(target)
            return

    def _check_transitions_from_result(self, result):
        """Check transitions with on_result.<field>==<value> conditions."""
        state_def = self._screens.get(self._current_state_id, {})
        transitions = state_def.get('transitions', {})

        for condition, target in transitions.items():
            if not condition.startswith('on_result.'):
                continue

            # Parse "on_result.<field>==<value>"
            remainder = condition[10:]  # strip "on_result."
            if '==' not in remainder:
                continue

            field, expected = remainder.split('==', 1)

            # Get actual value from result
            actual = result.get(field)
            if actual is None:
                continue

            # Compare as strings for simplicity (JSON values)
            if str(actual).lower() == expected.lower():
                self._set_state(target)
                return

    # ------------------------------------------------------------------
    # Helpers exposed to plugin code
    # ------------------------------------------------------------------

    def pm3_command(self, cmd, timeout=5000):
        """Execute a PM3 command via the executor.

        Only available if the plugin declared 'pm3' permission.

        Args:
            cmd: PM3 command string (e.g. 'hf 14a info')
            timeout: Timeout in milliseconds (default 5000).

        Returns:
            tuple: (success: bool, output: str)
                success is True if startPM3Task returned 1.
                output is the cached command output.
        """
        if 'pm3' not in self._permissions:
            logger.warning("Plugin lacks 'pm3' permission for: %s", cmd)
            return (False, 'Permission denied: pm3 not declared')

        try:
            import executor
            ret = executor.startPM3Task(cmd, timeout)
            output = executor.getPrintContent()
            return (ret == 1, output)
        except Exception as exc:
            logger.error("pm3_command error: %s", traceback.format_exc())
            return (False, str(exc))

    def shell_command(self, cmd, timeout=10):
        """Execute a shell command via subprocess.run.

        Only available if the plugin declared 'shell' permission.

        Args:
            cmd: Command string or list of args.
            timeout: Timeout in seconds (default 10).

        Returns:
            tuple: (returncode: int, stdout: str, stderr: str)
        """
        if 'shell' not in self._permissions:
            logger.warning("Plugin lacks 'shell' permission for: %s", cmd)
            return (-1, '', 'Permission denied: shell not declared')

        try:
            result = subprocess.run(
                cmd,
                shell=isinstance(cmd, str),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, '', 'Command timed out after %d seconds' % timeout)
        except Exception as exc:
            logger.error("shell_command error: %s", traceback.format_exc())
            return (-1, '', str(exc))

    def set_var(self, key, value):
        """Set a variable for {placeholder} resolution in screen templates.

        Thread-safe.  Can be called from background tasks.

        Args:
            key: Variable name (used as {key} in JSON templates).
            value: Variable value (will be converted to string for display).
        """
        self._state[key] = value

    def get_var(self, key, default=None):
        """Get a variable value from the plugin state dict.

        Args:
            key: Variable name.
            default: Value returned if key is not found.

        Returns:
            The variable value, or default.
        """
        return self._state.get(key, default)

    def show_toast(self, text, timeout=3000, icon=None):
        """Show a toast message.

        Thread-safe: if called from a background thread, schedules the
        toast on the UI thread.

        Args:
            text: Toast message text.
            timeout: Auto-dismiss in milliseconds (0 = persistent).
            icon: Icon name ('check', 'error', 'warning', 'info', or None).
        """
        def _show():
            self._ensure_toast()
            try:
                self._toast.show(text, duration_ms=timeout, icon=icon)
            except Exception:
                logger.error("show_toast error: %s", traceback.format_exc())

        root = actstack._root
        if root is not None and threading.current_thread() is not threading.main_thread():
            root.after(0, _show)
        else:
            _show()

    def update_screen(self):
        """Re-render the current screen after state variable changes.

        Thread-safe: if called from a background thread, schedules the
        render on the UI thread.
        """
        def _render():
            if self._current_state_id is not None:
                self._render_current_screen()

        root = actstack._root
        if root is not None and threading.current_thread() is not threading.main_thread():
            root.after(0, _render)
        else:
            _render()

    def set_progress(self, value, message=None):
        """Update progress bar value and optional message text.

        Convenience method for plugins running long operations.
        Sets the state variables and re-renders.

        Args:
            value: Progress value (0-100 or custom range).
            message: Optional status message.
        """
        self._state['progress_value'] = value
        if message is not None:
            self._state['progress_message'] = message
        self.update_screen()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _show_error_toast(self, text):
        """Show an error toast (convenience for internal errors)."""
        self.show_toast(text, timeout=5000, icon='error')


# ======================================================================
# CanvasModeActivity — subprocess-based plugin runner
# ======================================================================

class CanvasModeActivity(BaseActivity):
    """Subprocess-based plugin activity for raw canvas / fullscreen apps.

    Used for plugins like DOOM that run their own rendering process.
    The framework hides the tkinter canvas, launches the subprocess,
    and translates device key events to the subprocess via xdotool.

    PWR ALWAYS EXITS.  It kills the subprocess and calls finish().

    Bundle keys:
        plugin_dir — absolute path to the plugin directory
        manifest   — parsed manifest.json dict
        binary     — subprocess binary path (relative to plugin_dir)
        args       — subprocess arguments list
        key_map    — dict mapping device keys to xdotool key names
    """

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self._plugin_dir = None
        self._manifest = {}
        self._process = None
        self._binary = None
        self._args = []
        self._key_map = {}
        self._display = os.environ.get('DISPLAY', ':0')
        self._keepalive_timer = None

    def onCreate(self, bundle=None):
        """Launch the subprocess and hide the tkinter canvas."""
        super().onCreate(bundle)

        if bundle is None:
            bundle = self._bundle or {}

        self._plugin_dir = bundle.get('plugin_dir', '')
        self._manifest = bundle.get('manifest', {})
        self._binary = bundle.get('binary', '')
        self._args = bundle.get('args', [])
        self._key_map = bundle.get('key_map', {})

        # Resolve xdotool: prefer bundled bin/xdotool in plugin dir, fall back to system
        self._xdotool = 'xdotool'
        self._xdotool_env = {'DISPLAY': self._display}
        bundled = os.path.join(self._plugin_dir, 'bin', 'xdotool')
        if os.path.isfile(bundled):
            self._xdotool = bundled
            lib_dir = os.path.join(self._plugin_dir, 'bin')
            self._xdotool_env['LD_LIBRARY_PATH'] = lib_dir

        # Resolve binary path relative to plugin directory
        binary_path = self._binary
        if not os.path.isabs(binary_path):
            binary_path = os.path.join(self._plugin_dir, binary_path)

        if not os.path.isfile(binary_path):
            logger.error("Canvas mode binary not found: %s", binary_path)
            self._show_error_toast("Binary not found: %s" % self._binary)
            return

        # Detect the X display from the running environment.
        self._display = os.environ.get('DISPLAY', ':0')

        # Hide the tkinter canvas to give the subprocess the display
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.grid_remove()

        # Launch the subprocess with DISPLAY inherited
        try:
            env = os.environ.copy()
            env['DISPLAY'] = self._display
            cmd = [binary_path] + list(self._args)
            self._process = subprocess.Popen(
                cmd,
                cwd=self._plugin_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Canvas mode subprocess launched: PID %d, cmd=%s",
                        self._process.pid, cmd)
        except Exception:
            logger.error("Failed to launch canvas mode subprocess: %s",
                         traceback.format_exc())
            self._show_error_toast("Failed to launch: %s" % self._binary)
            if canvas is not None:
                canvas.grid()
            return

        # Start GD32 backlight keepalive — the GD32 MCU dims the
        # LCD after ~10s of no serial activity.  Periodically poke
        # the backlight to prevent screen blanking during gameplay.
        self._start_keepalive()

        # Monitor subprocess — if it dies (crash/exit), clean up and
        # return to the previous activity instead of leaving a grey screen.
        self._start_process_monitor()

    def _start_keepalive(self):
        """Send periodic keepalive pings to prevent GD32 screen dimming.

        The GD32 MCU greys out the LCD after ~10s of no serial activity.
        Sending 'i'm alive' over the UART keeps it awake without
        changing any hardware state (unlike setbaklight which alters
        brightness).
        """
        def _ping():
            if self._process is not None and self._process.poll() is None:
                try:
                    import hmi_driver
                    if hmi_driver._ser is not None and hmi_driver._ser.is_open:
                        hmi_driver._ser.write(b"i'm alive\r\n")
                        hmi_driver._ser.flush()
                except Exception:
                    pass
                # Reschedule every 5 seconds
                try:
                    root = actstack._root
                    if root is not None:
                        self._keepalive_timer = root.after(5000, _ping)
                except Exception:
                    pass
        _ping()

    def _stop_keepalive(self):
        """Cancel the backlight keepalive timer."""
        if self._keepalive_timer is not None:
            try:
                root = actstack._root
                if root is not None:
                    root.after_cancel(self._keepalive_timer)
            except Exception:
                pass
            self._keepalive_timer = None

    def _start_process_monitor(self):
        """Poll subprocess every 1s — if it dies, exit the activity."""
        self._monitor_timer = None

        def _check():
            if self._process is not None and self._process.poll() is not None:
                rc = self._process.returncode
                logger.warning("Canvas mode subprocess exited: rc=%d", rc)
                self._process = None
                self._stop_keepalive()
                # Restore canvas and finish
                canvas = self.getCanvas()
                if canvas is not None:
                    canvas.grid()
                self.finish()
                return
            # Reschedule
            try:
                root = actstack._root
                if root is not None:
                    self._monitor_timer = root.after(1000, _check)
            except Exception:
                pass
        try:
            root = actstack._root
            if root is not None:
                self._monitor_timer = root.after(1000, _check)
        except Exception:
            pass

    def _stop_process_monitor(self):
        """Cancel the process monitor timer."""
        if getattr(self, '_monitor_timer', None) is not None:
            try:
                root = actstack._root
                if root is not None:
                    root.after_cancel(self._monitor_timer)
            except Exception:
                pass
            self._monitor_timer = None

    def onKeyEvent(self, key):
        """Translate device keys to subprocess keys via xdotool.

        PWR ALWAYS EXITS — kills the subprocess and finishes.
        _handlePWR() is called first to dismiss toasts; regardless of
        whether it handles the event, the subprocess is killed and
        finish() is called.  Canvas mode never swallows PWR.
        """
        if key == KEY_PWR:
            self._handlePWR()
            self._kill_subprocess()
            self.finish()
            return

        # Translate key through the key_map
        xdo_key = self._key_map.get(key)
        if xdo_key and self._process is not None and self._process.poll() is None:
            self._send_key(xdo_key)

    # Movement keys get sustained press (keydown + 150ms + keyup) so
    # DOOM registers them as held.  Action keys (fire, enter, strafe)
    # get a single instant tap so they don't get stuck.
    _SUSTAINED_KEYS = frozenset({'Up', 'Down', 'Left', 'Right', 'comma', 'period'})

    def _send_key(self, xdo_key):
        """Send a key event to the subprocess via xdotool.

        Movement keys (Up/Down/Left/Right) use sustained keydown+keyup
        for responsive movement.  All other keys use a single tap to
        avoid getting stuck (e.g. fire key never releasing).
        """
        xdt = self._xdotool
        env = self._xdotool_env

        if xdo_key in self._SUSTAINED_KEYS:
            # Sustained press for movement
            try:
                subprocess.Popen(
                    [xdt, 'keydown', '--clearmodifiers', xdo_key],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                logger.error("xdotool keydown failed: %s",
                             traceback.format_exc())
                return

            def _release():
                try:
                    subprocess.Popen(
                        [xdt, 'keyup', '--clearmodifiers', xdo_key],
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass

            try:
                root = actstack._root
                if root is not None:
                    root.after(150, _release)
                else:
                    _release()
            except Exception:
                _release()
        else:
            # Instant tap for action keys (fire, enter, strafe, etc.)
            try:
                subprocess.Popen(
                    [xdt, 'key', '--clearmodifiers', xdo_key],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                logger.error("xdotool key failed: %s",
                             traceback.format_exc())

    def _kill_subprocess(self):
        """Kill the subprocess if it is still running."""
        self._stop_keepalive()
        self._stop_process_monitor()
        if self._process is not None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=1)
            except Exception:
                logger.error("Subprocess kill error: %s",
                             traceback.format_exc())
            finally:
                self._process = None

    def onDestroy(self):
        """Ensure subprocess is killed and canvas is restored."""
        self._stop_keepalive()
        self._stop_process_monitor()
        self._kill_subprocess()

        # Restore the canvas visibility
        canvas = self.getCanvas()
        if canvas is not None:
            try:
                canvas.grid()
            except Exception:
                pass

        super().onDestroy()

    def _show_error_toast(self, text):
        """Show error toast and schedule finish."""
        canvas = self.getCanvas()
        if canvas is not None:
            canvas.grid()
        try:
            from lib.widget import Toast
            self._toast = Toast(canvas)
            self._toast.show(text, duration_ms=5000, icon='error')
        except Exception:
            logger.error("CanvasMode toast error: %s", traceback.format_exc())


# ======================================================================
# Module-level helpers
# ======================================================================

def _is_activity_subclass(cls):
    """Check if cls is a BaseActivity subclass (but not BaseActivity itself).

    Used to decide whether to delegate entirely to the plugin class
    or to wrap it in PluginActivity's JSON state machine.
    """
    try:
        return (
            isinstance(cls, type)
            and issubclass(cls, BaseActivity)
            and cls is not BaseActivity
        )
    except TypeError:
        return False
