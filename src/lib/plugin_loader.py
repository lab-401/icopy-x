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

"""Plugin loader — discovers, validates, and loads plugins from plugins/ subdirectories.

Each plugin lives in its own subdirectory of the project-level plugins/ directory:

    plugins/
      my_plugin/
        manifest.json      # REQUIRED — plugin metadata
        plugin.py          # REQUIRED — code entry point
        ui.json            # OPTIONAL — JSON UI screens
        app_icon.png       # OPTIONAL — 20x20 menu icon

The loader validates manifest.json fields, optionally lints ui.json,
imports the entry class from plugin.py, and returns a sorted list of
PluginInfo objects ready for registration with the activity stack.

All errors are logged but never propagated — a bad plugin must not
crash the application.

Import convention: ``from lib.plugin_loader import discover_plugins, PluginInfo``
"""

import importlib
import importlib.util
import json
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

# Pattern for semantic version: X.Y.Z where X, Y, Z are non-negative integers.
_SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')

# Required manifest fields and their expected types.
_REQUIRED_FIELDS = {
    'name': str,
    'version': str,
    'entry_class': str,
}

# Optional manifest fields with (type, default) pairs.
_OPTIONAL_FIELDS = {
    'author': (str, ''),
    'description': (str, ''),
    'min_fw_version': (str, '1.0.0'),
    'promoted': (bool, False),
    'canvas_mode': (bool, False),
    'fullscreen': (bool, False),
    'permissions': (list, []),
    'icon': ((str, type(None)), None),
    'order': (int, 100),
    'key_map': ((dict, type(None)), None),
    'binary': ((str, type(None)), None),
    'args': (list, []),
}


class PluginInfo:
    """Metadata and loaded class for a single plugin."""

    __slots__ = (
        'name', 'version', 'author', 'description', 'key',
        'plugin_dir', 'promoted', 'canvas_mode', 'fullscreen',
        'order', 'permissions', 'icon_path', 'entry_class_name',
        'activity_class', 'manifest', 'ui_definition',
        'key_map', 'binary', 'args',
    )

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))

    def __repr__(self):
        return (
            "PluginInfo(name={!r}, key={!r}, order={}, "
            "entry_class={!r}, promoted={})".format(
                self.name, self.key, self.order,
                self.entry_class_name, self.promoted,
            )
        )


def _find_project_root():
    """Walk up from this file to find the project root containing plugins/.

    The project root is the first ancestor directory that contains a
    ``plugins/`` subdirectory. Falls back to two levels up from this
    file (src/lib/plugin_loader.py -> project root).
    """
    current = os.path.dirname(os.path.abspath(__file__))
    # Walk up at most 10 levels to avoid infinite loops.
    for _ in range(10):
        candidate = os.path.join(current, 'plugins')
        if os.path.isdir(candidate):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # Fallback: assume src/lib/plugin_loader.py -> ../../ is project root.
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    )))


def validate_manifest(manifest_path):
    """Validate a plugin manifest.json file.

    Args:
        manifest_path: Absolute path to manifest.json.

    Returns:
        Tuple of (manifest_dict, errors_list).
        On fatal errors, manifest_dict may be None.
        errors_list is empty when the manifest is fully valid.
    """
    errors = []

    # --- Parse JSON ---
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except (OSError, IOError) as exc:
        return None, ['Cannot read manifest: {}'.format(exc)]
    except json.JSONDecodeError as exc:
        return None, ['Invalid JSON in manifest: {}'.format(exc)]

    if not isinstance(manifest, dict):
        return None, ['Manifest must be a JSON object, got {}'.format(
            type(manifest).__name__)]

    # --- Required fields ---
    for field, expected_type in _REQUIRED_FIELDS.items():
        value = manifest.get(field)
        if value is None:
            errors.append('Missing required field: {!r}'.format(field))
            continue
        if not isinstance(value, expected_type):
            errors.append(
                'Field {!r} must be {}, got {}'.format(
                    field, expected_type.__name__, type(value).__name__))
            continue

    # Field-specific validation (only if the field exists and has correct type).
    name = manifest.get('name')
    if isinstance(name, str):
        if not name:
            errors.append('Field \'name\' must be non-empty')
        elif len(name) > 20:
            errors.append(
                'Field \'name\' exceeds 20 chars (got {})'.format(len(name)))

    version = manifest.get('version')
    if isinstance(version, str):
        if not _SEMVER_RE.match(version):
            errors.append(
                'Field \'version\' must match X.Y.Z pattern, got {!r}'.format(
                    version))

    entry_class = manifest.get('entry_class')
    if isinstance(entry_class, str) and not entry_class:
        errors.append('Field \'entry_class\' must be non-empty')

    # --- Optional fields: type-check if present ---
    for field, (expected_types, default) in _OPTIONAL_FIELDS.items():
        if field not in manifest:
            continue
        value = manifest[field]
        # Allow None for nullable fields.
        if value is None:
            continue
        if not isinstance(expected_types, tuple):
            expected_types = (expected_types,)
        if not isinstance(value, expected_types):
            errors.append(
                'Optional field {!r} has wrong type: expected {}, got {}'.format(
                    field,
                    '/'.join(t.__name__ for t in expected_types),
                    type(value).__name__,
                ))

    return manifest, errors


def lint_ui_json(ui_json_path, plugin_dir, activity_class=None):
    """Lint a plugin's ui.json for structural correctness.

    Checks:
    - Valid JSON
    - ``entry_screen`` exists and references a screen in ``screens``
    - All ``push:<id>`` targets reference existing screens
    - ``keys.PWR`` bindings are stripped (PWR is reserved for system exit)
    - Every screen has a ``buttons`` key
    - All ``run:<fn>`` targets exist on the activity class (if provided)

    Args:
        ui_json_path: Absolute path to ui.json.
        plugin_dir: Absolute path to the plugin directory (for context).
        activity_class: Optional loaded class to validate ``run:<fn>`` targets.

    Returns:
        Tuple of (cleaned_ui_dict, warnings_list).
        On fatal errors, cleaned_ui_dict is None.
    """
    warnings = []

    # --- Parse JSON ---
    try:
        with open(ui_json_path, 'r', encoding='utf-8') as f:
            ui = json.load(f)
    except (OSError, IOError) as exc:
        return None, ['Cannot read ui.json: {}'.format(exc)]
    except json.JSONDecodeError as exc:
        return None, ['Invalid JSON in ui.json: {}'.format(exc)]

    if not isinstance(ui, dict):
        return None, ['ui.json must be a JSON object, got {}'.format(
            type(ui).__name__)]

    # Normalize: support both "states" and "screens" keys, and
    # "initial_state" / "entry_screen" (mirrors _load_ui_definition).
    screens = ui.get('states', ui.get('screens', {}))
    if not isinstance(screens, dict):
        return None, ['ui.json "screens"/"states" must be an object']

    # --- entry_screen / initial_state ---
    entry_screen = ui.get('initial_state', ui.get('entry_screen'))
    if entry_screen is None:
        warnings.append('Missing "entry_screen"/"initial_state" in ui.json')
    elif entry_screen not in screens:
        warnings.append(
            '"entry_screen"/"initial_state" {!r} not found in screens'.format(
                entry_screen))

    # --- Validate each screen ---
    screen_ids = set(screens.keys())

    for screen_id, state_def in screens.items():
        if not isinstance(state_def, dict):
            warnings.append(
                'Screen {!r} is not a JSON object'.format(screen_id))
            continue

        # State-machine format may nest the screen inside a 'screen' key;
        # flat format puts buttons/keys/content directly on the state_def.
        screen_def = state_def.get('screen', state_def)

        # Check buttons present.
        if 'buttons' not in screen_def:
            warnings.append(
                'Screen {!r} is missing "buttons"'.format(screen_id))

        # Check push targets in buttons.
        buttons = screen_def.get('buttons', {})
        if isinstance(buttons, dict):
            for btn_key, btn_action in buttons.items():
                if isinstance(btn_action, str) and btn_action.startswith('push:'):
                    target = btn_action[len('push:'):]
                    if target not in screen_ids:
                        warnings.append(
                            'Screen {!r} button {!r} targets unknown screen '
                            '{!r}'.format(screen_id, btn_key, target))

        # Check set_state targets in keys and buttons.
        _all_actions = []
        if isinstance(buttons, dict):
            _all_actions.extend(buttons.values())
        keys_map = screen_def.get('keys', {})
        if isinstance(keys_map, dict):
            _all_actions.extend(keys_map.values())

        # Check push targets in list items.
        items = screen_def.get('items', [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    action = item.get('action', '')
                    if isinstance(action, str) and action.startswith('push:'):
                        target = action[len('push:'):]
                        if target not in screen_ids:
                            warnings.append(
                                'Screen {!r} item action targets unknown '
                                'screen {!r}'.format(screen_id, target))
                    if isinstance(action, str):
                        _all_actions.append(action)

        # Validate set_state targets.
        for act in _all_actions:
            if isinstance(act, str) and act.startswith('set_state:'):
                target = act[10:]
                if target not in screen_ids:
                    warnings.append(
                        'Screen {!r} set_state:{!r} targets unknown '
                        'state'.format(screen_id, target))

        # Validate run:<fn> targets.
        for act in _all_actions:
            if isinstance(act, str) and act.startswith('run:'):
                fn_name = act[len('run:'):]
                if activity_class is not None and not hasattr(activity_class, fn_name):
                    warnings.append(
                        'Screen {!r} run:{!r} target not found on '
                        '{}'.format(screen_id, fn_name,
                                    activity_class.__name__))

        # Validate transition targets (state-machine format).
        transitions = state_def.get('transitions', {})
        if isinstance(transitions, dict):
            for condition, target in transitions.items():
                if isinstance(target, str) and target not in screen_ids:
                    warnings.append(
                        'Screen {!r} transition {!r} targets unknown '
                        'state {!r}'.format(screen_id, condition, target))

        # Strip keys.PWR bindings.
        keys_section = screen_def.get('keys', {})
        if isinstance(keys_section, dict) and 'PWR' in keys_section:
            warnings.append(
                'Screen {!r}: stripped reserved keys.PWR binding'.format(
                    screen_id))
            del keys_section['PWR']

    return ui, warnings


def load_plugin_class(plugin_dir, entry_class_name):
    """Import plugin.py from a plugin directory and return the entry class.

    Uses importlib to load the module without requiring it to be on
    sys.path. The module is registered in sys.modules as
    ``plugins.<dirname>`` so that intra-plugin imports work.

    Args:
        plugin_dir: Absolute path to the plugin subdirectory.
        entry_class_name: Name of the class to extract from the module.

    Returns:
        Tuple of (class_object, error_string_or_None).
    """
    dirname = os.path.basename(plugin_dir)
    module_name = 'plugins.{}'.format(dirname)
    plugin_py = os.path.join(plugin_dir, 'plugin.py')

    try:
        spec = importlib.util.spec_from_file_location(module_name, plugin_py)
        if spec is None or spec.loader is None:
            return None, 'importlib could not create spec for {}'.format(
                plugin_py)

        module = importlib.util.module_from_spec(spec)

        # Make the plugin directory importable for relative imports within
        # the plugin (e.g. helper modules alongside plugin.py).
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            return None, 'Failed to execute {}: {}: {}'.format(
                plugin_py, type(exc).__name__, exc)

    except Exception as exc:
        return None, 'Failed to import {}: {}: {}'.format(
            plugin_py, type(exc).__name__, exc)

    # Extract the entry class.
    cls = getattr(module, entry_class_name, None)
    if cls is None:
        return None, 'Class {!r} not found in {}'.format(
            entry_class_name, plugin_py)

    return cls, None


def _resolve_icon_path(plugin_dir, manifest):
    """Resolve the icon path for a plugin.

    Checks the manifest ``icon`` field first, then falls back to
    ``app_icon.png`` in the plugin directory.

    Returns:
        Absolute path string if an icon file exists, else None.
    """
    # Explicit icon in manifest.
    icon_field = manifest.get('icon')
    if icon_field:
        candidate = os.path.abspath(os.path.join(plugin_dir, icon_field))
        # Path traversal guard — icon must stay inside plugin_dir.
        abs_plugin_dir = os.path.abspath(plugin_dir) + os.sep
        if not candidate.startswith(abs_plugin_dir):
            logger.warning(
                'Plugin %s: icon path %r escapes plugin directory — ignored',
                os.path.basename(plugin_dir), icon_field,
            )
        elif os.path.isfile(candidate):
            return candidate
        else:
            logger.warning(
                'Plugin %s: manifest icon %r not found',
                os.path.basename(plugin_dir), icon_field,
            )

    # Default icon.
    default_icon = os.path.join(plugin_dir, 'app_icon.png')
    if os.path.isfile(default_icon):
        return os.path.abspath(default_icon)

    return None


def _load_single_plugin(plugin_dir):
    """Attempt to load a single plugin from its directory.

    Args:
        plugin_dir: Absolute path to a plugin subdirectory.

    Returns:
        PluginInfo on success, None on failure.
    """
    dirname = os.path.basename(plugin_dir)

    # --- manifest.json ---
    manifest_path = os.path.join(plugin_dir, 'manifest.json')
    if not os.path.isfile(manifest_path):
        logger.warning('Plugin %s: missing manifest.json — skipped', dirname)
        return None

    manifest, errors = validate_manifest(manifest_path)
    if manifest is None:
        for err in errors:
            logger.warning('Plugin %s: %s', dirname, err)
        return None
    if errors:
        for err in errors:
            logger.warning('Plugin %s: %s', dirname, err)
        return None

    # --- plugin.py ---
    plugin_py = os.path.join(plugin_dir, 'plugin.py')
    if not os.path.isfile(plugin_py):
        logger.warning('Plugin %s: missing plugin.py — skipped', dirname)
        return None

    # --- Extract manifest values with defaults ---
    name = manifest['name']
    version = manifest['version']
    entry_class_name = manifest['entry_class']

    author = manifest.get('author', '')
    description = manifest.get('description', '')
    promoted = manifest.get('promoted', False)
    canvas_mode = manifest.get('canvas_mode', False)
    fullscreen = manifest.get('fullscreen', False)
    order = manifest.get('order', 100)
    permissions = manifest.get('permissions', [])
    key_map = manifest.get('key_map', None)
    binary = manifest.get('binary', None)
    args = manifest.get('args', [])

    # Coerce order to int defensively.
    if not isinstance(order, int):
        try:
            order = int(order)
        except (ValueError, TypeError):
            logger.warning(
                'Plugin %s: invalid order value, defaulting to 100', dirname)
            order = 100

    # Path traversal guard — binary must stay inside plugin_dir.
    if binary is not None:
        abs_binary = os.path.abspath(os.path.join(plugin_dir, binary))
        abs_plugin_dir = os.path.abspath(plugin_dir) + os.sep
        if not abs_binary.startswith(abs_plugin_dir):
            logger.warning(
                'Plugin %s: binary path %r escapes plugin directory — cleared',
                dirname, binary)
            binary = None

    # --- Load entry class (before ui.json so run:<fn> targets can be validated) ---
    activity_class, load_error = load_plugin_class(plugin_dir, entry_class_name)
    if load_error is not None:
        logger.warning('Plugin %s: %s — skipped', dirname, load_error)
        return None

    # --- ui.json (optional) ---
    ui_definition = None
    ui_json_path = os.path.join(plugin_dir, 'ui.json')
    if os.path.isfile(ui_json_path):
        ui_definition, ui_warnings = lint_ui_json(
            ui_json_path, plugin_dir, activity_class=activity_class)
        for warn in ui_warnings:
            logger.warning('Plugin %s ui.json: %s', dirname, warn)

    # --- Icon ---
    icon_path = _resolve_icon_path(plugin_dir, manifest)

    return PluginInfo(
        name=name,
        version=version,
        author=author,
        description=description,
        key=dirname,
        plugin_dir=os.path.abspath(plugin_dir),
        promoted=promoted,
        canvas_mode=canvas_mode,
        fullscreen=fullscreen,
        order=order,
        permissions=permissions,
        icon_path=icon_path,
        entry_class_name=entry_class_name,
        activity_class=activity_class,
        manifest=manifest,
        ui_definition=ui_definition,
        key_map=key_map,
        binary=binary,
        args=args,
    )


def discover_plugins(plugin_dir=None):
    """Discover, validate, and load all plugins.

    Scans each subdirectory of *plugin_dir* for a valid plugin structure
    (manifest.json + plugin.py). Directories starting with ``_`` or ``.``
    are silently skipped. Invalid plugins are logged and excluded from the
    result.

    Args:
        plugin_dir: Absolute path to the plugins/ directory.
                    Defaults to ``<project_root>/plugins/``.

    Returns:
        list[PluginInfo] sorted by (order, name). May be empty.
    """
    if plugin_dir is None:
        project_root = _find_project_root()
        plugin_dir = os.path.join(project_root, 'plugins')

    if not os.path.isdir(plugin_dir):
        logger.debug('Plugin directory does not exist: %s', plugin_dir)
        return []

    plugins = []
    seen_keys = set()

    try:
        entries = sorted(os.listdir(plugin_dir))
    except OSError as exc:
        logger.warning('Cannot list plugin directory %s: %s', plugin_dir, exc)
        return []

    for entry in entries:
        # Skip hidden and private directories.
        if entry.startswith('_') or entry.startswith('.'):
            continue

        subdir = os.path.join(plugin_dir, entry)
        if not os.path.isdir(subdir):
            continue

        info = _load_single_plugin(subdir)
        if info is None:
            continue

        # Duplicate key check (directory name is the key).
        if info.key in seen_keys:
            logger.warning(
                'Duplicate plugin key %r — skipping %s',
                info.key, subdir,
            )
            continue
        seen_keys.add(info.key)

        plugins.append(info)

    # Sort by (order, name) — lower order first, alphabetical within same order.
    plugins.sort(key=lambda p: (p.order, p.name))

    if plugins:
        logger.info(
            'Discovered %d plugin(s): %s',
            len(plugins),
            ', '.join(p.name for p in plugins),
        )
    else:
        logger.debug('No plugins discovered in %s', plugin_dir)

    return plugins
