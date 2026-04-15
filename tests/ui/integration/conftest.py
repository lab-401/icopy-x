"""Integration test conftest — shared helpers for full-stack UI tests.

Provides:
  - extract_ui_state(activity): extracts UI state dict matching QEMU _dump_state() format
  - actstack_setup fixture: resets actstack + installs MockCanvas factory
  - mock_modules fixture: installs mock config, settings, hmi_driver, version
  - extract_canvas_colors(): extracts known color values from canvas items
"""

import sys
import types
import pytest


# ===================================================================
# extract_ui_state — matches QEMU _dump_state() format
# ===================================================================

def extract_ui_state(activity=None):
    """Extract UI state from an activity's canvas.

    Produces a dict matching the QEMU _dump_state() format from
    tools/minimal_launch_090.py lines 904-1100.

    If *activity* is None, uses actstack.get_current_activity().

    Returns dict with keys:
        current_activity  -- class name string (e.g. 'ScanActivity')
        activity_stack    -- list of dicts with 'index', 'class', 'lifecycle'
        title             -- title bar text or None
        M1                -- left button text or None
        M2                -- right button text or None
        toast             -- toast text string or None
        content_text      -- list of dicts with 'text', 'x', 'y', 'fill', 'font'
    """
    import actstack as _actstack

    stack = _actstack.get_activity_pck()

    state = {
        'current_activity': None,
        'activity_stack': [],
        'title': None,
        'M1': None,
        'M2': None,
        'toast': None,
        'content_text': [],
    }

    # Activity stack entries
    for i, act in enumerate(stack):
        entry = {'index': i, 'class': act.__class__.__name__}
        try:
            lc = act.life
            entry['lifecycle'] = {
                'created': bool(lc.created),
                'resumed': bool(lc.resumed),
                'paused': bool(lc.paused),
                'destroyed': bool(lc.destroyed),
            }
        except Exception:
            pass
        state['activity_stack'].append(entry)

    # Current activity
    if activity is None:
        activity = _actstack.get_current_activity()
    if activity is not None:
        state['current_activity'] = activity.__class__.__name__

    canvas = activity.getCanvas() if activity else None
    if canvas is None:
        return state

    # Collect item IDs by tag category
    title_ids = set()
    btn_left_ids = set()
    btn_right_ids = set()
    btn_bg_ids = set()
    toast_obj_prefixes = set()

    for item in canvas.find_all():
        tags = canvas.gettags(item)
        for tag in tags:
            tl = tag.lower()
            if '-title' in tl or tl == 'tags_title':
                title_ids.add(item)
            elif '-btnleft' in tl or tl == 'tags_btn_left':
                btn_left_ids.add(item)
            elif '-btnright' in tl or tl == 'tags_btn_right':
                btn_right_ids.add(item)
            elif '-btnbg' in tl or tl == 'tags_btn_bg':
                btn_bg_ids.add(item)
            # Toast detection: tags with ':toast_bg' or ':mask_layer'
            elif ':toast_bg' in tag or ':mask_layer' in tag:
                toast_obj_prefixes.add(tag.split(':')[0] + ':')

    # Title
    for item in title_ids:
        if canvas.type(item) == 'text':
            t = canvas.itemcget(item, 'text')
            if t:
                state['title'] = t

    # M1 (left button)
    for item in btn_left_ids:
        if canvas.type(item) == 'text':
            t = canvas.itemcget(item, 'text')
            if t:
                state['M1'] = t
    # Fallback: check by coords (y > 200, x < 120)
    if not state['M1']:
        for item in canvas.find_all():
            if canvas.type(item) == 'text' and item not in title_ids:
                coords = canvas.coords(item)
                if coords and len(coords) >= 2 and coords[1] >= 200 and coords[0] < 120:
                    t = canvas.itemcget(item, 'text')
                    if t:
                        state['M1'] = t
                        btn_left_ids.add(item)
                        break

    # M2 (right button)
    for item in btn_right_ids:
        if canvas.type(item) == 'text':
            t = canvas.itemcget(item, 'text')
            if t:
                state['M2'] = t
    # Fallback: check by coords (y > 200, x >= 120)
    if not state['M2']:
        for item in canvas.find_all():
            if canvas.type(item) == 'text' and item not in title_ids and item not in btn_left_ids:
                coords = canvas.coords(item)
                if coords and len(coords) >= 2 and coords[1] >= 200 and coords[0] >= 120:
                    t = canvas.itemcget(item, 'text')
                    if t:
                        state['M2'] = t
                        btn_right_ids.add(item)
                        break

    # Toast — items belonging to toast object prefixes
    toast_item_ids = set()
    toast_text_parts = []
    if toast_obj_prefixes:
        for item in canvas.find_all():
            for tag in canvas.gettags(item):
                if any(tag.startswith(prefix) for prefix in toast_obj_prefixes):
                    toast_item_ids.add(item)
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t:
                            toast_text_parts.append(t)
    # Also check for toast_text tags directly
    if not toast_text_parts:
        for item in canvas.find_all():
            for tag in canvas.gettags(item):
                if ':toast_text' in tag:
                    toast_item_ids.add(item)
                    if canvas.type(item) == 'text':
                        t = canvas.itemcget(item, 'text')
                        if t:
                            toast_text_parts.append(t)
    if toast_text_parts:
        state['toast'] = '\n'.join(toast_text_parts)

    # Content text — everything except title, buttons, toast, battery
    skip = title_ids | btn_left_ids | btn_right_ids | btn_bg_ids | toast_item_ids
    for item in canvas.find_all():
        if item in skip:
            continue
        if canvas.type(item) == 'text':
            txt = canvas.itemcget(item, 'text')
            if txt:
                coords = canvas.coords(item)
                y = coords[1] if len(coords) > 1 else 0
                x = coords[0] if coords else 0
                # Skip battery text (top-right, small font)
                if y < 35 and x > 170:
                    continue
                state['content_text'].append({
                    'text': txt,
                    'x': x,
                    'y': y,
                    'fill': canvas.itemcget(item, 'fill'),
                    'font': canvas.itemcget(item, 'font'),
                })

    return state


def extract_canvas_colors(canvas):
    """Extract known color values from canvas items for regression testing.

    Returns a dict mapping element names to fill color strings:
        'title_bar': fill of the title bar rectangle
        'button_bar': fill of the button bar rectangle
        'selection': fill of the selection highlight rectangle (if present)
        'title_text': fill of the title text
        'button_text_left': fill of M1 button text
        'button_text_right': fill of M2 button text
        'progress_bg': fill of progress bar background (if present)
        'progress_fill': fill of progress bar fill (if present)
    """
    colors = {}
    if canvas is None:
        return colors

    for item_id in canvas.find_all():
        tags = canvas.gettags(item_id)
        itype = canvas.type(item_id)
        for tag in tags:
            tl = tag.lower()
            if tl == 'tags_title':
                if itype == 'rectangle':
                    colors['title_bar'] = canvas.itemcget(item_id, 'fill')
                elif itype == 'text':
                    colors['title_text'] = canvas.itemcget(item_id, 'fill')
            elif tl == 'tags_btn_bg' and itype == 'rectangle':
                colors['button_bar'] = canvas.itemcget(item_id, 'fill')
            elif tl == 'tags_btn_left' and itype == 'text':
                colors['button_text_left'] = canvas.itemcget(item_id, 'fill')
            elif tl == 'tags_btn_right' and itype == 'text':
                colors['button_text_right'] = canvas.itemcget(item_id, 'fill')
            # Selection highlight (bg tag from widget)
            if ':bg' in tag and itype == 'rectangle':
                fill = canvas.itemcget(item_id, 'fill')
                if fill.upper() == '#EEEEEE':
                    colors['selection'] = fill
            # Progress bar
            if ':bg' in tag and itype == 'rectangle':
                fill = canvas.itemcget(item_id, 'fill')
                if fill.lower() == '#eeeeee':
                    coords = canvas.coords(item_id)
                    # Progress bar background is at y=100, x=20
                    if coords and len(coords) >= 4 and 95 <= coords[1] <= 105:
                        colors['progress_bg'] = fill
            if ':fill' in tag and itype == 'rectangle':
                fill = canvas.itemcget(item_id, 'fill')
                if fill.upper() == '#1C6AEB':
                    colors['progress_fill'] = fill

    return colors


def get_items_in_content_area(canvas, y_min=40, y_max=200):
    """Return all canvas items whose coordinates fall within the content area.

    Returns list of (item_id, type, tags, coords, options) tuples.
    """
    result = []
    if canvas is None:
        return result
    for item_id in canvas.find_all():
        coords = canvas.coords(item_id)
        if not coords or len(coords) < 2:
            continue
        y = coords[1]
        if y_min <= y <= y_max:
            result.append({
                'id': item_id,
                'type': canvas.type(item_id),
                'tags': canvas.gettags(item_id),
                'coords': coords,
            })
    return result


# ===================================================================
# Mock module helpers
# ===================================================================

class _MockConfig:
    """In-memory config.so replacement."""
    def __init__(self):
        self._store = {'backlight': '2', 'volume': '2'}

    def getValue(self, key):
        if key in self._store:
            return str(self._store[key])
        raise KeyError(key)

    def setKeyValue(self, key, value):
        self._store[key] = value


class _MockSettings:
    """In-memory settings.so replacement."""
    def __init__(self, config):
        self._config = config

    def getBacklight(self):
        return int(self._config.getValue('backlight'))

    def setBacklight(self, level):
        self._config.setKeyValue('backlight', level)

    def getVolume(self):
        return int(self._config.getValue('volume'))

    def setVolume(self, level):
        self._config.setKeyValue('volume', level)


class _MockVersion:
    """In-memory version.so replacement -- returns test values."""
    @staticmethod
    def getTYP(): return 'iCopy-X'
    @staticmethod
    def getHW(): return 'v2.0'
    @staticmethod
    def getHMI(): return '1.0.90'
    @staticmethod
    def getOS(): return '5.4.0'
    @staticmethod
    def getPM(): return 'v4.0'
    @staticmethod
    def getSN(): return 'TEST-SN-001'


def _install_mock_modules():
    """Install mock config, settings, hmi_driver, version into sys.modules.

    Returns a dict of {module_name: saved_original_or_None} for cleanup.
    """
    saved = {}
    for mod_name in ('config', 'settings', 'hmi_driver', 'version'):
        saved[mod_name] = sys.modules.get(mod_name)

    mock_config = _MockConfig()
    mock_settings = _MockSettings(mock_config)

    config_mod = types.ModuleType('config')
    config_mod.getValue = mock_config.getValue
    config_mod.setKeyValue = mock_config.setKeyValue
    sys.modules['config'] = config_mod

    settings_mod = types.ModuleType('settings')
    settings_mod.getBacklight = mock_settings.getBacklight
    settings_mod.setBacklight = mock_settings.setBacklight
    settings_mod.getVolume = mock_settings.getVolume
    settings_mod.setVolume = mock_settings.setVolume
    sys.modules['settings'] = settings_mod

    hmi_mod = types.ModuleType('hmi_driver')
    hmi_mod.setbaklight = lambda level: None
    hmi_mod.setvolume = lambda level: None
    hmi_mod.playaudio = lambda *a: None
    sys.modules['hmi_driver'] = hmi_mod

    version_mod = types.ModuleType('version')
    version_mod.getTYP = _MockVersion.getTYP
    version_mod.getHW = _MockVersion.getHW
    version_mod.getHMI = _MockVersion.getHMI
    version_mod.getOS = _MockVersion.getOS
    version_mod.getPM = _MockVersion.getPM
    version_mod.getSN = _MockVersion.getSN
    sys.modules['version'] = version_mod

    return saved


def _restore_modules(saved):
    """Restore original modules from saved dict."""
    for mod_name, original in saved.items():
        if original is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = original


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def actstack_setup():
    """Reset actstack, install MockCanvas factory, and mock modules for each test."""
    import actstack as _actstack
    from tests.ui.conftest import MockCanvas

    _actstack._reset()
    _actstack._canvas_factory = lambda: MockCanvas()
    saved = _install_mock_modules()
    yield
    _actstack._reset()
    _restore_modules(saved)
