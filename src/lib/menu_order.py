import json

import config


SETTING_KEY = 'main_menu_order'


def saved_ids():
    try:
        value = json.loads(config.getValue(SETTING_KEY, '[]'))
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and item not in result:
            result.append(item)
    return result


def ordered_items(items, preferred_ids=None):
    preferred = saved_ids() if preferred_ids is None else preferred_ids
    by_id = {item[2]: item for item in items}
    used = set()
    result = []
    for identifier in preferred:
        if identifier in by_id and identifier not in used:
            result.append(by_id[identifier])
            used.add(identifier)
    result.extend(item for item in items if item[2] not in used)
    return result


def save_items(items):
    present = [item[2] for item in items]
    unavailable = [identifier for identifier in saved_ids() if identifier not in present]
    config.setKeyValue(SETTING_KEY, json.dumps(present + unavailable))
