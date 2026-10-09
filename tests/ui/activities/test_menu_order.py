import json

import pytest

import actstack
from lib import menu_order
from lib.actmain import MainActivity
from tests.ui.conftest import MockCanvas


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    values = {}
    monkeypatch.setattr(menu_order.config, 'getValue',
                        lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(menu_order.config, 'setKeyValue',
                        lambda key, value: values.__setitem__(key, value))
    actstack._reset()
    actstack._canvas_factory = lambda: MockCanvas()
    yield values
    actstack._reset()


def start():
    return actstack.start_activity(MainActivity)


def ids(activity):
    return [item[2] for item in activity._menu_items]


def test_ok_opens_and_m1_pickup_does_not_launch(environment, monkeypatch):
    activity = start()
    launched = []
    monkeypatch.setattr(activity, '_launchActivity', lambda index: launched.append(index))
    activity.callKeyEvent('OK')
    assert launched == [0]
    activity.callKeyEvent('M1')
    assert activity._move_snapshot is not None
    assert launched == [0]
    assert activity.lv_main_page._items[0].startswith('[Move] ')
    assert 'Move Item' in activity.getCanvas().get_all_text()


def test_move_boundaries_repetition_place_and_reload(environment):
    activity = start()
    activity.lv_main_page.setSelection(1)
    moved = ids(activity)[1]
    activity.callKeyEvent('M1')
    activity.callKeyEvent('UP')
    assert ids(activity)[0] == moved
    assert activity.lv_main_page.selection() == 0
    activity.callKeyEvent('UP')
    assert ids(activity)[0] == moved
    activity.callKeyEvent('DOWN')
    activity.callKeyEvent('DOWN')
    assert ids(activity)[2] == moved
    assert activity.lv_main_page.selection() == 2
    assert activity.lv_main_page._items[2].startswith('[Move] ')
    activity.callKeyEvent('M1')
    assert activity._move_snapshot is None
    assert not any(label.startswith('[Move] ') for label in activity.lv_main_page._items)
    assert activity.lv_main_page.selection() == 2
    assert json.loads(environment[menu_order.SETTING_KEY]) == ids(activity)
    expected = ids(activity)
    actstack._reset()
    assert ids(start()) == expected


def test_m2_cancels_without_persisting(environment):
    activity = start()
    original = ids(activity)
    activity.lv_main_page.setSelection(3)
    picked = original[3]
    activity.callKeyEvent('M1')
    activity.callKeyEvent('DOWN')
    assert ids(activity) != original
    activity.callKeyEvent('M2')
    assert ids(activity) == original
    assert activity.lv_main_page.selection() == 3
    assert ids(activity)[3] == picked
    assert activity._move_snapshot is None
    assert not any(label.startswith('[Move] ') for label in activity.lv_main_page._items)
    assert menu_order.SETTING_KEY not in environment


def test_last_boundary_and_normal_navigation_resume(environment, monkeypatch):
    activity = start()
    last = len(activity._menu_items) - 1
    activity.lv_main_page.setSelection(last)
    activity.callKeyEvent('M1')
    activity.callKeyEvent('DOWN')
    assert activity.lv_main_page.selection() == last
    activity.callKeyEvent('M1')
    launched = []
    monkeypatch.setattr(activity, '_launchActivity', lambda index: launched.append(index))
    activity.callKeyEvent('UP')
    activity.callKeyEvent('OK')
    assert launched == [last - 1]


def test_saved_identifiers_reconcile_missing_new_and_plugins(environment):
    environment[menu_order.SETTING_KEY] = json.dumps([
        'scan', 'plugin:temporarily-missing', 'removed', 'autocopy'
    ])
    items = [('Auto', '1', 'autocopy'), ('Scan', '2', 'scan'),
             ('New', '3', 'new')]
    assert [item[2] for item in menu_order.ordered_items(items)] == [
        'scan', 'autocopy', 'new'
    ]
    menu_order.save_items(items)
    assert 'plugin:temporarily-missing' in menu_order.saved_ids()
    returned = items + [('Plugin', '4', 'plugin:temporarily-missing')]
    assert 'plugin:temporarily-missing' in [
        item[2] for item in menu_order.ordered_items(returned)
    ]


def test_corrupt_preference_is_ignored(environment):
    environment[menu_order.SETTING_KEY] = '{broken'
    activity = start()
    assert ids(activity)[0] == 'autocopy'
    assert 'iclass_se' in ids(activity)


def test_reorder_is_only_on_main_menu(environment):
    from activity_main import ICSDecoderActivity
    main = start()
    child = actstack.start_activity(ICSDecoderActivity)
    original = ids(main)
    child.callKeyEvent('M1')
    assert ids(main) == original
    assert main._move_snapshot is None


def test_move_ignores_open_shortcuts_until_placed(environment, monkeypatch):
    activity = start()
    launched = []
    monkeypatch.setattr(activity, '_launchActivity', lambda index: launched.append(index))
    activity.callKeyEvent('M1')
    activity.callKeyEvent('OK')
    activity.callKeyEvent('ALL')
    assert launched == []
    assert actstack.get_current_activity() is activity
    assert activity._move_snapshot is not None


def test_failed_save_keeps_move_cancellable(environment, monkeypatch):
    activity = start()
    original = ids(activity)
    def fail(items):
        raise OSError('disk full')

    monkeypatch.setattr(menu_order, 'save_items', fail)
    activity.callKeyEvent('M1')
    activity.callKeyEvent('DOWN')
    activity.callKeyEvent('M1')
    assert activity._move_snapshot is not None
    assert 'Menu order not saved' in activity.getCanvas().get_all_text()
    activity.callKeyEvent('M2')
    assert ids(activity) == original
    assert menu_order.SETTING_KEY not in environment


def test_four_rows_leave_room_for_move_softkeys(environment):
    activity = start()
    assert activity.lv_main_page._max_display == 4
    activity.lv_main_page.setSelection(3)
    activity.callKeyEvent('M1')
    activity.callKeyEvent('DOWN')
    assert activity.lv_main_page.selection() == 4
    assert activity.lv_main_page.getPagePosition() == 1
    assert activity.lv_main_page._items[4].startswith('[Move] ')


def test_disk_persistence_preserves_other_preferences(environment, tmp_path, monkeypatch):
    import importlib
    config = importlib.reload(menu_order.config)
    monkeypatch.setattr(config, '_CONF_PATH', str(tmp_path / 'conf.ini'))
    config.setKeyValue('volume', '0')
    items = [('Scan', '3', 'scan'), ('Auto Copy', '1', 'autocopy')]
    menu_order.save_items(items)
    config = importlib.reload(config)
    monkeypatch.setattr(config, '_CONF_PATH', str(tmp_path / 'conf.ini'))
    assert menu_order.ordered_items(list(reversed(items))) == items
    assert config.getValue('volume') == '0'
