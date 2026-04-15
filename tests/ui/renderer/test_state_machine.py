"""Tests for StateMachine — multi-state flow engine.

Uses the real scan_tag.json and main_menu.json definitions from the archive.
"""

import json
import pytest

from src.lib._state_machine import StateMachine, StateMachineError


# ══════════════════════════════════════════════════════════════════════
# Fixtures — load real JSON definitions
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def scan_def():
    """Load the real scan_tag.json definition."""
    with open('/home/qx/archive/ui/screens/scan_tag.json', 'r') as f:
        return json.load(f)


@pytest.fixture
def menu_def():
    """Load the real main_menu.json definition (single-screen)."""
    with open('/home/qx/archive/ui/screens/main_menu.json', 'r') as f:
        return json.load(f)


@pytest.fixture
def sm(scan_def):
    """StateMachine initialized with scan_tag.json."""
    return StateMachine(scan_def)


@pytest.fixture
def sm_menu(menu_def):
    """StateMachine initialized with main_menu.json (single-screen)."""
    return StateMachine(menu_def)


# ══════════════════════════════════════════════════════════════════════
# 1. Initial state
# ══════════════════════════════════════════════════════════════════════

class TestInitialState:

    def test_initial_state_is_scanning(self, sm):
        """scan_tag.json declares initial_state: 'scanning'."""
        sm.start()
        assert sm.current_state == 'scanning'

    def test_not_started_state_is_none(self, sm):
        assert sm.current_state is None

    def test_is_not_single_screen(self, sm):
        assert sm.is_single_screen is False


# ══════════════════════════════════════════════════════════════════════
# 2. get_action returns correct action for each key
# ══════════════════════════════════════════════════════════════════════

class TestGetAction:

    def test_scanning_has_no_keys(self, sm):
        """Scanning state has empty keys dict."""
        sm.start()
        assert sm.get_action('M1') is None
        assert sm.get_action('OK') is None

    def test_found_state_keys(self, sm):
        sm.start()
        sm.transition_to('found')
        assert sm.get_action('M1') == 'set_state:scanning'
        assert sm.get_action('M2') == 'push:simulation_with_tag'

    def test_not_found_state_keys(self, sm):
        sm.start()
        sm.transition_to('not_found')
        assert sm.get_action('M1') == 'set_state:scanning'
        assert sm.get_action('M2') == 'set_state:scanning'

    def test_unbound_key_returns_none(self, sm):
        sm.start()
        sm.transition_to('found')
        assert sm.get_action('UP') is None


# ══════════════════════════════════════════════════════════════════════
# 3. execute_action parses all action types
# ══════════════════════════════════════════════════════════════════════

class TestExecuteAction:

    def test_scroll_positive(self, sm):
        sm.start()
        assert sm.execute_action('scroll:1') == ('scroll', 1)

    def test_scroll_negative(self, sm):
        sm.start()
        assert sm.execute_action('scroll:-1') == ('scroll', -1)

    def test_select(self, sm):
        sm.start()
        assert sm.execute_action('select') == ('select', None)

    def test_finish(self, sm):
        sm.start()
        assert sm.execute_action('finish') == ('finish', None)

    def test_push(self, sm):
        sm.start()
        sm.transition_to('found')
        result = sm.execute_action('push:simulation_with_tag')
        assert result == ('push', 'simulation_with_tag')

    def test_set_state(self, sm):
        sm.start()
        sm.transition_to('found')
        result = sm.execute_action('set_state:scanning')
        assert result == ('set_state', 'scanning')
        assert sm.current_state == 'scanning'

    def test_run_with_handler(self, sm):
        calls = []
        sm.set_action_handler(lambda action: calls.append(action) or 'ok')
        sm.start()  # on_enter fires here too
        calls.clear()
        result = sm.execute_action('run:scan.scan_all')
        assert result == ('run', 'ok')
        assert calls == ['scan.scan_all']

    def test_run_without_handler(self, sm):
        sm.start()
        result = sm.execute_action('run:scan.scan_all')
        assert result == ('run', None)

    def test_noop(self, sm):
        sm.start()
        assert sm.execute_action('noop') == ('noop', None)

    def test_none_action(self, sm):
        sm.start()
        assert sm.execute_action(None) is None

    def test_unknown_action(self, sm):
        sm.start()
        assert sm.execute_action('bogus_action') == ('noop', None)


# ══════════════════════════════════════════════════════════════════════
# 4. process_result: found=true transitions to 'found'
# ══════════════════════════════════════════════════════════════════════

class TestProcessResultFound:

    def test_found_true_transitions_to_found(self, sm):
        sm.start()
        assert sm.current_state == 'scanning'
        sm.process_result({'found': True})
        assert sm.current_state == 'found'


# ══════════════════════════════════════════════════════════════════════
# 5. process_result: found=false transitions to 'not_found'
# ══════════════════════════════════════════════════════════════════════

class TestProcessResultNotFound:

    def test_found_false_transitions_to_not_found(self, sm):
        sm.start()
        sm.process_result({'found': False})
        assert sm.current_state == 'not_found'


# ══════════════════════════════════════════════════════════════════════
# 6. transition_to triggers state_change_handler
# ══════════════════════════════════════════════════════════════════════

class TestStateChangeHandler:

    def test_handler_called_on_transition(self, sm):
        changes = []
        sm.set_state_change_handler(
            lambda old, new, screen: changes.append((old, new))
        )
        sm.start()  # None -> scanning
        sm.transition_to('found')
        assert changes == [(None, 'scanning'), ('scanning', 'found')]

    def test_handler_receives_screen_def(self, sm):
        screens = []
        sm.set_state_change_handler(
            lambda old, new, screen: screens.append(screen)
        )
        sm.start()
        sm.transition_to('found')
        # The found screen has a template content type
        assert screens[-1]['content']['type'] == 'template'

    def test_handler_not_called_when_not_set(self, sm):
        """No crash when handler is None."""
        sm.start()
        sm.transition_to('found')  # Should not raise


# ══════════════════════════════════════════════════════════════════════
# 7. on_enter action triggers action_handler
# ══════════════════════════════════════════════════════════════════════

class TestOnEnter:

    def test_on_enter_fires_on_start(self, sm):
        """scanning state has on_enter: run:scan.scan_all_synchronous."""
        actions = []
        sm.set_action_handler(lambda a: actions.append(a))
        sm.start()
        assert 'run:scan.scan_all_synchronous' in actions

    def test_on_enter_fires_on_transition(self, sm):
        """Transitioning back to scanning fires on_enter again."""
        actions = []
        sm.set_action_handler(lambda a: actions.append(a))
        sm.start()
        sm.transition_to('found')  # no on_enter
        sm.transition_to('scanning')  # has on_enter
        assert actions.count('run:scan.scan_all_synchronous') == 2

    def test_no_on_enter_does_not_call_handler(self, sm):
        """found state has no on_enter — handler should not be called for it."""
        actions = []
        sm.set_action_handler(lambda a: actions.append(a))
        sm.start()  # fires scanning on_enter
        actions.clear()
        sm.transition_to('found')
        assert actions == []


# ══════════════════════════════════════════════════════════════════════
# 8. Single-screen mode (main_menu.json)
# ══════════════════════════════════════════════════════════════════════

class TestSingleScreen:

    def test_is_single_screen(self, sm_menu):
        assert sm_menu.is_single_screen is True

    def test_current_state_is_none(self, sm_menu):
        assert sm_menu.current_state is None

    def test_current_screen_returns_top_level_screen(self, sm_menu):
        screen = sm_menu.current_screen
        assert screen['title'] == 'Main Page'
        assert screen['content']['type'] == 'list'

    def test_current_keys(self, sm_menu):
        keys = sm_menu.current_keys
        assert keys['UP'] == 'scroll:-1'
        assert keys['DOWN'] == 'scroll:1'
        assert keys['OK'] == 'select'

    def test_start_is_noop(self, sm_menu):
        """Starting a single-screen machine does nothing."""
        sm_menu.start()
        assert sm_menu.current_state is None

    def test_reset_is_noop(self, sm_menu):
        sm_menu.reset()
        assert sm_menu.current_state is None

    def test_process_result_is_noop(self, sm_menu):
        """No transitions in single-screen mode."""
        sm_menu.process_result({'found': True})
        assert sm_menu.current_state is None

    def test_execute_scroll(self, sm_menu):
        result = sm_menu.execute_action('scroll:-1')
        assert result == ('scroll', -1)

    def test_execute_select(self, sm_menu):
        result = sm_menu.execute_action('select')
        assert result == ('select', None)


# ══════════════════════════════════════════════════════════════════════
# 9. Reset returns to initial state
# ══════════════════════════════════════════════════════════════════════

class TestReset:

    def test_reset_to_initial(self, sm):
        sm.start()
        sm.transition_to('found')
        assert sm.current_state == 'found'
        sm.reset()
        assert sm.current_state == 'scanning'

    def test_reset_does_not_trigger_on_enter(self, sm):
        actions = []
        sm.set_action_handler(lambda a: actions.append(a))
        sm.start()
        actions.clear()
        sm.transition_to('found')
        sm.reset()
        # on_enter should NOT fire from reset
        assert actions == []


# ══════════════════════════════════════════════════════════════════════
# 10. Unknown state raises error
# ══════════════════════════════════════════════════════════════════════

class TestUnknownState:

    def test_transition_to_unknown_raises(self, sm):
        sm.start()
        with pytest.raises(StateMachineError, match="Unknown state 'bogus'"):
            sm.transition_to('bogus')

    def test_set_state_action_unknown_raises(self, sm):
        sm.start()
        with pytest.raises(StateMachineError):
            sm.execute_action('set_state:nonexistent')


# ══════════════════════════════════════════════════════════════════════
# 11. No matching transition leaves state unchanged
# ══════════════════════════════════════════════════════════════════════

class TestNoMatchingTransition:

    def test_unmatched_result_stays_in_state(self, sm):
        sm.start()
        assert sm.current_state == 'scanning'
        # Neither found==true nor found==false
        sm.process_result({'something_else': 'value'})
        assert sm.current_state == 'scanning'

    def test_error_from_non_error_state(self, sm):
        """found state has no transitions — process_error is a no-op."""
        sm.start()
        sm.transition_to('found')
        sm.process_error(Exception("oops"))
        assert sm.current_state == 'found'


# ══════════════════════════════════════════════════════════════════════
# Additional edge cases
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_current_screen_before_start(self, sm):
        """Before start, current_screen is empty dict."""
        assert sm.current_screen == {}

    def test_current_keys_before_start(self, sm):
        assert sm.current_keys == {}

    def test_no_initial_state_raises(self):
        """Definition with states but no initial_state raises on start."""
        definition = {'states': {'a': {'screen': {}}}}
        sm = StateMachine(definition)
        with pytest.raises(StateMachineError, match="No initial_state"):
            sm.start()

    def test_multi_tags_state_noop_key(self, sm):
        """multi_tags state in scan_tag.json has M2 bound to noop."""
        sm.start()
        sm.transition_to('multi_tags')
        assert sm.get_action('M2') == 'noop'
        result = sm.execute_action('noop')
        assert result == ('noop', None)

    def test_process_error_transitions_when_on_error_exists(self):
        """A state with on_error transition should handle errors."""
        definition = {
            'initial_state': 'working',
            'states': {
                'working': {
                    'screen': {'keys': {}},
                    'transitions': {
                        'on_error': 'broken',
                    },
                },
                'broken': {
                    'screen': {'title': 'Error', 'keys': {}},
                },
            },
        }
        sm = StateMachine(definition)
        sm.start()
        sm.process_error(RuntimeError("boom"))
        assert sm.current_state == 'broken'

    def test_scroll_invalid_number(self, sm):
        """scroll: with non-numeric value returns 0."""
        sm.start()
        result = sm.execute_action('scroll:abc')
        assert result == ('scroll', 0)
