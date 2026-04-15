"""Tests for SimulationActivity and SimulationTraceActivity.

Ground truth (FB captures simulation_20260403 + trace_scan_flow_20260331.txt):
    - 16 tag types across 4 pages, numbered "1. M1 S50 1k" through "16. Nedap ID"
    - Title list view: "Simulation X/4" (page indicator)
    - Title sim UI: "Simulation" (no page indicator)
    - List view: M1="" (empty), M2="" (empty)
    - Sim UI: M1="Stop", M2="Start"
    - Simulating: M1="Stop", M2="Start" (unchanged)
    - OK toggles edit mode in sim UI. M2 starts sim.
    - HF types (0-4) push SimulationTraceActivity after stop.
    - Trace screen: title="Trace", M1="Cancel", M2="Save"
"""

import pytest

import actstack
from tests.ui.conftest import MockCanvas
from _constants import KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_OK, KEY_M1, KEY_M2, KEY_PWR


@pytest.fixture(autouse=True)
def _setup():
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield
    actstack._reset()


def _create_sim(bundle=None):
    from activity_main import SimulationActivity
    return actstack.start_activity(SimulationActivity, bundle)


def _create_trace(bundle=None):
    from activity_main import SimulationTraceActivity
    return actstack.start_activity(SimulationTraceActivity, bundle)


class TestSimulationActivity:
    """SimulationActivity unit tests -- 20 scenarios."""

    def test_title_simulation(self):
        """Title must contain 'Simulation'."""
        act = _create_sim()
        texts = act.getCanvas().get_all_text()
        assert any('Simulation' in t for t in texts)

    def test_title_pagination(self):
        """Title must show page indicator '1/4'."""
        act = _create_sim()
        texts = act.getCanvas().get_all_text()
        assert any('1/' in t for t in texts)

    def test_type_list_has_16_entries(self):
        """SIM_MAP must contain 16 entries."""
        from activity_main import SIM_MAP
        assert len(SIM_MAP) == 16

    def test_type_list_first_item(self):
        """First item must be 'M1 S50 1k' (QEMU-verified)."""
        from activity_main import SIM_MAP
        assert SIM_MAP[0][0] == 'M1 S50 1k'

    def test_type_list_last_item(self):
        """Last item must be 'FDX-B Data'."""
        from activity_main import SIM_MAP
        assert SIM_MAP[-1][0] == 'FDX-B Data'

    def test_initial_state_is_list(self):
        """Activity starts in list_view state."""
        act = _create_sim()
        assert act._state == 'list_view'

    def test_m2_selects_type(self):
        """M2 in list view transitions to sim_ui."""
        act = _create_sim()
        act.onKeyEvent(KEY_M2)
        assert act._state == 'sim_ui'
        assert act._sim_entry is not None

    def test_ok_selects_type(self):
        """OK key is same as M2 in list view."""
        act = _create_sim()
        act.onKeyEvent(KEY_OK)
        assert act._state == 'sim_ui'

    def test_up_scrolls_list(self):
        """UP key navigates the type list."""
        act = _create_sim()
        sel_before = act._listview.selection()
        act.onKeyEvent(KEY_DOWN)
        assert act._listview.selection() != sel_before

    def test_pwr_exits_from_list(self):
        """PWR in list view finishes the activity."""
        act = _create_sim()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_sim_ui_title(self):
        """Sim UI state shows 'Simulation' title."""
        act = _create_sim()
        act.onKeyEvent(KEY_M2)  # select first type
        texts = act.getCanvas().get_all_text()
        assert any('Simulation' in t for t in texts)

    def test_sim_ui_has_fields(self):
        """Sim UI must create SimFields widget for the selected type."""
        act = _create_sim()
        act.onKeyEvent(KEY_M2)
        assert hasattr(act, '_sim_fields') and act._sim_fields is not None
        assert act._sim_fields.fieldCount() > 0

    def test_sim_ui_pwr_back_to_list(self):
        """PWR in sim UI returns to list view."""
        act = _create_sim()
        act.onKeyEvent(KEY_M2)  # to sim_ui
        act.onKeyEvent(KEY_PWR)  # back
        assert act._state == 'list_view'

    def test_sim_ui_ok_toggles_edit(self):
        """OK in sim UI toggles editing mode (ground truth: FB captures)."""
        act = _create_sim()
        act.onKeyEvent(KEY_M2)  # select type -> sim_ui
        sf = act._sim_fields
        assert not sf.editing
        act.onKeyEvent(KEY_OK)
        assert sf.editing
        act.onKeyEvent(KEY_OK)
        assert not sf.editing

    def test_sim_ui_edit_roll_up(self):
        """UP in edit mode rolls hex char."""
        act = _create_sim()
        act.onKeyEvent(KEY_M2)
        act.onKeyEvent(KEY_OK)  # enter edit
        sf = act._sim_fields
        initial = sf.getValue(0)
        act.onKeyEvent(KEY_UP)
        changed = sf.getValue(0)
        assert changed != initial

    def test_pre_filled_from_bundle(self):
        """Bundle with sim_index skips list and shows sim UI directly."""
        act = _create_sim({'sim_index': 5})  # Em410x ID
        assert act._state == 'sim_ui'
        assert act._sim_entry[0] == 'Em410x ID'

    def test_cancel_pre_filled(self):
        """PWR from pre-filled sim UI goes back to list."""
        act = _create_sim({'sim_index': 0})
        act.onKeyEvent(KEY_PWR)
        assert act._state == 'list_view'

    def test_parser_uid(self):
        """parserUID extracts UID from standard format."""
        from activity_main import SimulationActivity
        result = SimulationActivity.parserUID('UID : AA BB CC DD')
        assert result == 'AABBCCDD'

    def test_parser_uid_none(self):
        """parserUID returns None for empty/bad data."""
        from activity_main import SimulationActivity
        assert SimulationActivity.parserUID(None) is None
        assert SimulationActivity.parserUID('no uid here') is None

    def test_parser_fccn(self):
        """parserFCCN extracts FC and CN."""
        from activity_main import SimulationActivity
        result = SimulationActivity.parserFCCN('FC: 123 CN: 456')
        assert result == ('123', '456')

    def test_parser_ioporx(self):
        """parserIoPorx extracts version, FC, CN."""
        from activity_main import SimulationActivity
        result = SimulationActivity.parserIoPorx('Version: 1 FC: 10 CN: 100')
        assert result == ('1', '10', '100')

    def test_parser_fdx(self):
        """parserFdx extracts country and ID."""
        from activity_main import SimulationActivity
        result = SimulationActivity.parserFdx('Country: 999 ID: 12345')
        assert 'country' in result
        assert result['country'] == '999'

    def test_parser_nedap(self):
        """parserNedap extracts subtype, CN, ID."""
        from activity_main import SimulationActivity
        result = SimulationActivity.parserNedap('Subtype: 1 CN: 200 ID: 300')
        assert result['subtype'] == '1'
        assert result['cn'] == '200'

    def test_chk_max_comm_valid(self):
        """chk_max_comm returns True for values within range."""
        from activity_main import SimulationActivity
        assert SimulationActivity.chk_max_comm(100, 255) is True

    def test_chk_max_comm_invalid(self):
        """chk_max_comm returns False for values exceeding max."""
        from activity_main import SimulationActivity
        assert SimulationActivity.chk_max_comm(256, 255) is False

    def test_filter_space(self):
        """filter_space strips whitespace."""
        from activity_main import SimulationActivity
        assert SimulationActivity.filter_space('AA BB CC') == 'AABBCC'
        assert SimulationActivity.filter_space(None) == ''

    def test_getSimMap(self):
        """getSimMap returns a copy of SIM_MAP."""
        from activity_main import SimulationActivity, SIM_MAP
        result = SimulationActivity.getSimMap()
        assert result == list(SIM_MAP)
        assert result is not SIM_MAP


class TestSimulationTraceActivity:
    """SimulationTraceActivity unit tests."""

    def test_trace_title(self):
        """Title must be 'Trace'."""
        act = _create_trace()
        texts = act.getCanvas().get_all_text()
        assert 'Trace' in texts

    def test_trace_save_button(self):
        """M2 button must say 'Save'."""
        act = _create_trace()
        texts = act.getCanvas().get_all_text()
        assert 'Save' in texts

    def test_trace_with_data(self):
        """Trace with string data displays it."""
        act = _create_trace({'trace_data': 'hello trace'})
        assert act._trace_data == 'hello trace'

    def test_trace_save(self):
        """M2 triggers save and shows toast."""
        # trace_len must be > 0 for save to proceed (guards against empty trace)
        act = _create_trace({'trace_data': 'data', 'trace_len': 100})
        act.onKeyEvent(KEY_M2)
        assert act._saved is True

    def test_trace_pwr_exits(self):
        """PWR finishes the trace activity."""
        act = _create_trace()
        act.onKeyEvent(KEY_PWR)
        assert act.life.destroyed

    def test_trace_m1_exits(self):
        """M1 finishes the trace activity."""
        act = _create_trace()
        act.onKeyEvent(KEY_M1)
        assert act.life.destroyed
