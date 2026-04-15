"""Tests for TimeSyncActivity.

Validates against the exhaustive UI mapping in
docs/UI_Mapping/13_time_settings/README.md and V1090_SETTINGS_FLOWS_COMPLETE.md.

Ground truth:
    - Title: "Time Settings" (resources key: time_sync)
    - 6 fields: year, month, day, hour, minute, second
    - Two states: DISPLAY and EDIT
    - DISPLAY: M1/M2="Edit", PWR=finish
    - EDIT: UP/DOWN change value, LEFT/RIGHT move cursor, M2="Save", PWR=back
    - Value wrapping: month 12->1, hour 23->0, minute 59->0, etc.
    - Day max depends on month/year (leap year support)
    - Save shows toast "Synchronizing system time" then "Synchronization successful!"
"""

import sys
import time
import types
import pytest

from tests.ui.conftest import MockCanvas
import actstack
from _constants import (
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
    KEY_OK, KEY_M1, KEY_M2, KEY_PWR,
)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture(autouse=True)
def _setup_actstack():
    """Reset actstack and install MockCanvas factory for each test."""
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


def _create_time_sync():
    """Start a TimeSyncActivity."""
    from activity_main import TimeSyncActivity
    act = actstack.start_activity(TimeSyncActivity)
    return act


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestTimeSyncActivity:
    """TimeSyncActivity unit tests -- 12 scenarios covering all states."""

    def test_title_is_time_settings(self):
        """Title bar must read 'Time Settings' (resources key: time_sync)."""
        act = _create_time_sync()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Time Settings' in texts

    def test_reads_current_time(self):
        """onCreate populates fields from the current system time."""
        act = _create_time_sync()
        now = time.localtime()
        vals = act.get_values()
        # Year and month should match current time (within a second of test start)
        assert vals['year'] == now.tm_year
        assert vals['month'] == now.tm_mon

    def test_6_fields(self):
        """Activity must have exactly 6 fields in correct order."""
        act = _create_time_sync()
        assert act.FIELDS == ['year', 'month', 'day', 'hour', 'minute', 'second']
        vals = act.get_values()
        assert len(vals) == 6
        for field in act.FIELDS:
            assert field in vals

    def test_initial_state_is_display(self):
        """Activity starts in DISPLAY mode."""
        act = _create_time_sync()
        assert act.get_state() == 'display'

    def test_m1_enters_edit_mode(self):
        """M1 in DISPLAY mode switches to EDIT mode."""
        act = _create_time_sync()
        assert act.get_state() == 'display'
        act.onKeyEvent(KEY_M1)
        assert act.get_state() == 'edit'

    def test_m2_enters_edit_mode(self):
        """M2 in DISPLAY mode switches to EDIT mode."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M2)
        assert act.get_state() == 'edit'

    def test_edit_mode_cursor_starts_at_year(self):
        """Entering EDIT mode places cursor on field 0 (year)."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        assert act.get_cursor() == 0

    def test_cursor_navigation_right(self):
        """RIGHT moves cursor from year(0) to month(1)."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit
        assert act.get_cursor() == 0
        act.onKeyEvent(KEY_RIGHT)
        assert act.get_cursor() == 1
        act.onKeyEvent(KEY_RIGHT)
        assert act.get_cursor() == 2

    def test_cursor_navigation_left(self):
        """LEFT moves cursor backward, wrapping from year(0) to second(5)."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit, cursor at 0
        act.onKeyEvent(KEY_LEFT)  # wrap to 5
        assert act.get_cursor() == 5

    def test_cursor_wraps_right(self):
        """RIGHT from field 5 (second) wraps to field 0 (year)."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        # Navigate to last field
        for _ in range(5):
            act.onKeyEvent(KEY_RIGHT)
        assert act.get_cursor() == 5
        act.onKeyEvent(KEY_RIGHT)
        assert act.get_cursor() == 0

    def test_increment_field(self):
        """UP increments the focused field."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit, cursor on year
        original_year = act.get_field_value('year')
        act.onKeyEvent(KEY_UP)
        assert act.get_field_value('year') == original_year + 1

    def test_decrement_field(self):
        """DOWN decrements the focused field."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        original_year = act.get_field_value('year')
        act.onKeyEvent(KEY_DOWN)
        assert act.get_field_value('year') == original_year - 1

    def test_field_value_wrapping_month_up(self):
        """Month wraps from 12 -> 1 on UP."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        # Move cursor to month (field 1)
        act.onKeyEvent(KEY_RIGHT)
        assert act.get_cursor() == 1
        # Set month to 12
        act._values['month'] = 12
        act.onKeyEvent(KEY_UP)
        assert act.get_field_value('month') == 1

    def test_field_value_wrapping_month_down(self):
        """Month wraps from 1 -> 12 on DOWN."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        act.onKeyEvent(KEY_RIGHT)  # cursor to month
        act._values['month'] = 1
        act.onKeyEvent(KEY_DOWN)
        assert act.get_field_value('month') == 12

    def test_field_value_wrapping_hour(self):
        """Hour wraps from 23 -> 0 on UP."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        # Move to hour (field 3)
        for _ in range(3):
            act.onKeyEvent(KEY_RIGHT)
        assert act.get_cursor() == 3
        act._values['hour'] = 23
        act.onKeyEvent(KEY_UP)
        assert act.get_field_value('hour') == 0

    def test_field_value_wrapping_minute(self):
        """Minute wraps from 59 -> 0 on UP, 0 -> 59 on DOWN."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        # Move to minute (field 4)
        for _ in range(4):
            act.onKeyEvent(KEY_RIGHT)
        act._values['minute'] = 59
        act.onKeyEvent(KEY_UP)
        assert act.get_field_value('minute') == 0
        act.onKeyEvent(KEY_DOWN)
        assert act.get_field_value('minute') == 59

    def test_field_value_wrapping_second(self):
        """Second wraps from 59 -> 0 on UP."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        # Move to second (field 5)
        for _ in range(5):
            act.onKeyEvent(KEY_RIGHT)
        act._values['second'] = 59
        act.onKeyEvent(KEY_UP)
        assert act.get_field_value('second') == 0

    def test_day_max_depends_on_month(self):
        """Day max for February is 28 (non-leap) or 29 (leap)."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        # Set to Feb 2025 (non-leap)
        act._values['year'] = 2025
        act._values['month'] = 2
        act._values['day'] = 28
        # Move cursor to day (field 2)
        act.onKeyEvent(KEY_RIGHT)
        act.onKeyEvent(KEY_RIGHT)
        act.onKeyEvent(KEY_UP)  # day 28 -> wraps to 1 (max=28)
        assert act.get_field_value('day') == 1

    def test_day_max_leap_year(self):
        """Feb in a leap year allows day 29."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        act._values['year'] = 2024
        act._values['month'] = 2
        act._values['day'] = 28
        act.onKeyEvent(KEY_RIGHT)
        act.onKeyEvent(KEY_RIGHT)
        act.onKeyEvent(KEY_UP)  # day 28 -> 29 (leap year)
        assert act.get_field_value('day') == 29

    def test_ok_saves_time(self):
        """M2 in EDIT mode saves time and returns to DISPLAY."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit
        assert act.get_state() == 'edit'
        act.onKeyEvent(KEY_M2)  # save
        assert act.get_state() == 'display'

    def test_save_toast(self):
        """Saving shows toast messages on canvas."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit
        act.onKeyEvent(KEY_M2)  # save
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # The success toast should be visible
        assert any('Synchronization successful' in t for t in texts)

    def test_pwr_cancels_in_display(self):
        """PWR in DISPLAY mode finishes the activity."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_pwr_cancels_in_edit(self):
        """PWR in EDIT mode returns to DISPLAY without saving."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit
        assert act.get_state() == 'edit'
        act.onKeyEvent(KEY_PWR)  # cancel
        assert act.get_state() == 'display'
        # Activity should still be alive
        assert not act.life.destroyed

    def test_year_range(self):
        """Year wraps from 2099 -> 2000 on UP, 2000 -> 2099 on DOWN."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        act._values['year'] = 2099
        act.onKeyEvent(KEY_UP)
        assert act.get_field_value('year') == 2000
        act.onKeyEvent(KEY_DOWN)
        assert act.get_field_value('year') == 2099

    def test_display_shows_date_time_strings(self):
        """Canvas should contain formatted date and time strings."""
        act = _create_time_sync()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # JsonRenderer time_editor renders individual fields and separators:
        # '-' separators between date fields, ':' separators between time fields
        has_date_sep = any('-' == t for t in texts)
        has_time_sep = any(':' == t for t in texts)
        assert has_date_sep, "Date separator '-' not found in canvas texts"
        assert has_time_sep, "Time separator ':' not found in canvas texts"

    def test_edit_mode_shows_cursor_indicator(self):
        """In EDIT mode, the cursor caret '^' should be shown on canvas."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)  # enter edit
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        # JsonRenderer time_editor renders a '^' caret under the focused field
        assert any('^' in t for t in texts)

    def test_buttons_display_mode(self):
        """In DISPLAY mode, buttons should be Edit/Edit."""
        act = _create_time_sync()
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        edit_count = sum(1 for t in texts if t == 'Edit')
        assert edit_count >= 2, "Expected two 'Edit' buttons in display mode"

    def test_buttons_edit_mode(self):
        """In EDIT mode, right button should be Save."""
        act = _create_time_sync()
        act.onKeyEvent(KEY_M1)
        canvas = act.getCanvas()
        texts = canvas.get_all_text()
        assert 'Save' in texts
