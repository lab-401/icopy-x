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

"""State machine — manages multi-state flows for JSON-defined activities.

An activity like scan_tag.json declares states (scanning, found, not_found)
with transitions between them.  This module handles:

- Tracking the current state
- Returning the screen definition for the current state
- Parsing and dispatching action strings (scroll:N, select, run:module.func, ...)
- Evaluating transition conditions against middleware results
- Calling registered handlers when state changes or actions fire

Single-screen activities (e.g., main_menu.json with no ``states`` key)
are also supported — they expose the top-level ``screen`` directly.
"""

from src.lib._variable_resolver import VariableResolver


class StateMachineError(Exception):
    """Raised for invalid state transitions or missing states."""


class StateMachine:
    """Multi-state flow engine driven by a JSON activity definition."""

    def __init__(self, definition: dict):
        """Initialize from a JSON activity definition.

        Parameters
        ----------
        definition : dict
            Must contain either:
            - ``states`` and ``initial_state`` for multi-state activities, or
            - ``screen`` at top level for single-screen activities.
        """
        self._definition = definition
        self._states = definition.get('states', {})
        self._initial_state = definition.get('initial_state')
        self._is_single_screen = 'states' not in definition
        self._current_state = None
        self._action_handler = None       # callback for 'run:' actions
        self._state_change_handler = None  # callback when state changes
        self._resolver = VariableResolver()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_state(self) -> str:
        """Current state name, or None if not started / single-screen."""
        return self._current_state

    @property
    def current_screen(self) -> dict:
        """Current state's screen definition.

        For single-screen activities, returns the top-level ``screen``.
        """
        if self._is_single_screen:
            return self._definition.get('screen', {})
        if self._current_state and self._current_state in self._states:
            return self._states[self._current_state].get('screen', {})
        return {}

    @property
    def current_keys(self) -> dict:
        """Current state's key bindings (from screen.keys)."""
        return self.current_screen.get('keys', {})

    @property
    def is_single_screen(self) -> bool:
        """True if this is a single-screen activity (no state machine)."""
        return self._is_single_screen

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def set_action_handler(self, handler):
        """Set callback for ``run:`` actions.

        ``handler(action_str) -> result``
        """
        self._action_handler = handler

    def set_state_change_handler(self, handler):
        """Set callback when state changes.

        ``handler(old_state, new_state, screen_def)``
        """
        self._state_change_handler = handler

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Enter initial state.  Triggers ``on_enter`` if defined."""
        if self._is_single_screen:
            return
        if not self._initial_state:
            raise StateMachineError("No initial_state defined")
        self.transition_to(self._initial_state)

    def reset(self):
        """Reset to initial state *without* triggering ``on_enter``."""
        if self._is_single_screen:
            return
        self._current_state = self._initial_state

    # ------------------------------------------------------------------
    # Key / action handling
    # ------------------------------------------------------------------

    def get_action(self, key: str) -> str:
        """Get the action string for a key press in current state.

        Returns the action string or ``None`` if key is not bound.
        """
        return self.current_keys.get(key)

    def execute_action(self, action: str):
        """Execute an action string and return ``(action_type, data)``.

        Action types:

        - ``scroll:N`` — returns ``('scroll', N)``
        - ``select`` — returns ``('select', None)``
        - ``finish`` — returns ``('finish', None)``
        - ``push:screen_id`` — returns ``('push', screen_id)``
        - ``set_state:state_name`` — transitions, returns ``('set_state', state_name)``
        - ``run:module.function`` — delegates to action_handler, returns ``('run', result)``
        - ``noop`` — returns ``('noop', None)``
        """
        if action is None:
            return None

        if action == 'noop':
            return ('noop', None)

        if action == 'select':
            return ('select', None)

        if action == 'finish':
            return ('finish', None)

        if action.startswith('scroll:'):
            try:
                n = int(action.split(':', 1)[1])
            except (ValueError, IndexError):
                n = 0
            return ('scroll', n)

        if action.startswith('push:'):
            screen_id = action.split(':', 1)[1]
            return ('push', screen_id)

        if action.startswith('set_state:'):
            state_name = action.split(':', 1)[1]
            self.transition_to(state_name)
            return ('set_state', state_name)

        if action.startswith('run:'):
            action_str = action.split(':', 1)[1]
            result = None
            if self._action_handler:
                result = self._action_handler(action_str)
            return ('run', result)

        # Unknown action — treat as noop
        return ('noop', None)

    # ------------------------------------------------------------------
    # Result / transition processing
    # ------------------------------------------------------------------

    def process_result(self, result: dict):
        """Process a middleware result and check for transitions.

        Evaluates each transition condition in the current state against
        *result*.  If a condition matches, transitions to the target state.
        """
        if self._is_single_screen or self._current_state is None:
            return

        state_def = self._states.get(self._current_state, {})
        transitions = state_def.get('transitions', {})

        for condition, target_state in transitions.items():
            if self._resolver.resolve_condition(condition, result):
                self.transition_to(target_state)
                return

    def process_error(self, error):
        """Process an error and check for ``on_error`` transitions.

        Creates a synthetic result dict ``{'error': str(error)}`` and
        delegates to :meth:`process_result`.
        """
        self.process_result({'error': str(error)})

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition_to(self, state_name: str):
        """Explicitly transition to a named state.

        1. Validates the target state exists
        2. Stores old state
        3. Sets current_state
        4. Calls state_change_handler(old, new, screen_def)
        5. If new state has ``on_enter``, calls action_handler
        """
        if state_name not in self._states:
            raise StateMachineError(
                f"Unknown state '{state_name}'. "
                f"Valid states: {list(self._states.keys())}"
            )

        old_state = self._current_state
        self._current_state = state_name
        screen_def = self.current_screen

        if self._state_change_handler:
            self._state_change_handler(old_state, state_name, screen_def)

        # Execute on_enter action if present
        state_def = self._states[state_name]
        on_enter = state_def.get('on_enter')
        if on_enter and self._action_handler:
            self._action_handler(on_enter)
