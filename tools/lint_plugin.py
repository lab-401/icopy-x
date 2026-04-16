#!/usr/bin/env python3

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

"""Standalone plugin linter for iCopy-X plugin developers.

Validates a plugin directory for structural correctness, manifest fields,
Python syntax, class existence, ui.json integrity, and Python 3.8 compat.

Usage:
    python3 tools/lint_plugin.py plugins/my_plugin/
    python3 tools/lint_plugin.py --all

Exit codes:
    0 — all checks passed
    1 — one or more checks failed

This tool is COMPLETELY standalone. It does NOT import any modules from
src/lib/. All validation logic uses only Python stdlib (json, ast, re,
os, sys, argparse, struct).

Python 3.8 compatible.
"""

import argparse
import ast
import json
import os
import re
import struct
import sys


# -- Colors (ANSI escape codes, disabled if not a TTY) --------------------

_USE_COLOR = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def _green(text):
    if _USE_COLOR:
        return '\033[32m%s\033[0m' % text
    return text


def _red(text):
    if _USE_COLOR:
        return '\033[31m%s\033[0m' % text
    return text


def _yellow(text):
    if _USE_COLOR:
        return '\033[33m%s\033[0m' % text
    return text


def _bold(text):
    if _USE_COLOR:
        return '\033[1m%s\033[0m' % text
    return text


# -- Result tracking ------------------------------------------------------

class LintResults:
    """Accumulates pass/fail/warn results for a single plugin."""

    def __init__(self):
        self.results = []  # list of (status, message) where status in ('PASS', 'FAIL', 'WARN')

    def passed(self, msg):
        self.results.append(('PASS', msg))

    def failed(self, msg):
        self.results.append(('FAIL', msg))

    def warned(self, msg):
        self.results.append(('WARN', msg))

    @property
    def pass_count(self):
        return sum(1 for s, _ in self.results if s == 'PASS')

    @property
    def fail_count(self):
        return sum(1 for s, _ in self.results if s == 'FAIL')

    @property
    def warn_count(self):
        return sum(1 for s, _ in self.results if s == 'WARN')

    @property
    def total(self):
        return len(self.results)

    @property
    def ok(self):
        return self.fail_count == 0

    def print_results(self):
        for status, msg in self.results:
            if status == 'PASS':
                tag = _green('[PASS]')
            elif status == 'FAIL':
                tag = _red('[FAIL]')
            else:
                tag = _yellow('[WARN]')
            print('  %s %s' % (tag, msg))

        # Summary line
        print()
        parts = []
        parts.append('%d/%d checks passed' % (self.pass_count, self.total))
        if self.warn_count > 0:
            parts.append('%d warning(s)' % self.warn_count)
        if self.fail_count > 0:
            summary = _red(', '.join(parts))
        else:
            summary = _green(', '.join(parts))
        print('  %s' % summary)


# -- Validation constants -------------------------------------------------

_SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')

_REQUIRED_FIELDS = {'name', 'version', 'entry_class'}

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'

# AST node types that indicate Python 3.10+ match/case
_PY310_MATCH_TYPES = set()
try:
    # Python 3.10+
    _PY310_MATCH_TYPES.add(ast.Match)  # type: ignore[attr-defined]
except AttributeError:
    pass

# Walrus operator is ast.NamedExpr (Python 3.8+)
_HAS_NAMED_EXPR = hasattr(ast, 'NamedExpr')


# -- Lint functions --------------------------------------------------------

def lint_plugin(plugin_dir):
    """Run all lint checks on a plugin directory.

    Args:
        plugin_dir: Path to the plugin directory.

    Returns:
        LintResults instance.
    """
    r = LintResults()
    plugin_dir = os.path.abspath(plugin_dir)

    # 1. Directory structure: manifest.json
    manifest_path = os.path.join(plugin_dir, 'manifest.json')
    if not os.path.isfile(manifest_path):
        r.failed('manifest.json exists')
        # Cannot continue without manifest
        return r
    r.passed('manifest.json exists')

    # 1b. Directory structure: plugin.py
    plugin_py = os.path.join(plugin_dir, 'plugin.py')
    if not os.path.isfile(plugin_py):
        r.failed('plugin.py exists')
        return r
    r.passed('plugin.py exists')

    # 2. manifest.json validation
    manifest = _lint_manifest(manifest_path, r)
    if manifest is None:
        return r

    entry_class_name = manifest.get('entry_class', '')

    # 3. plugin.py syntax check
    source = _lint_plugin_syntax(plugin_py, r)
    if source is None:
        return r

    # 4. plugin.py class check
    class_names = _lint_plugin_class(source, entry_class_name, plugin_py, r)

    # 5. ui.json validation (if present)
    ui_json_path = os.path.join(plugin_dir, 'ui.json')
    if os.path.isfile(ui_json_path):
        _lint_ui_json(ui_json_path, class_names, entry_class_name, r)

    # 6. app_icon.png (if present)
    icon_path = os.path.join(plugin_dir, 'app_icon.png')
    if os.path.isfile(icon_path):
        _lint_icon(icon_path, r)

    # 7. Python 3.8 compatibility
    _lint_py38_compat(source, plugin_py, r)

    return r


def _lint_manifest(manifest_path, r):
    """Validate manifest.json. Returns parsed dict or None on fatal error."""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            raw = f.read()
    except (OSError, IOError) as exc:
        r.failed('manifest.json: readable (%s)' % exc)
        return None

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        r.failed('manifest.json: valid JSON (%s)' % exc)
        return None

    if not isinstance(manifest, dict):
        r.failed('manifest.json: is a JSON object (got %s)' % type(manifest).__name__)
        return None

    # Required fields
    missing = _REQUIRED_FIELDS - set(manifest.keys())
    if missing:
        r.failed('manifest.json: required fields present (missing: %s)' % ', '.join(sorted(missing)))
        return None
    r.passed('manifest.json: required fields present')

    # name validation
    name = manifest.get('name', '')
    if not isinstance(name, str) or not name:
        r.failed('manifest.json: name is a non-empty string')
    elif len(name) > 20:
        r.failed('manifest.json: name "%s" (%d chars, max 20)' % (name, len(name)))
    else:
        r.passed('manifest.json: name "%s" (%d chars)' % (name, len(name)))

    # version validation
    version = manifest.get('version', '')
    if not isinstance(version, str):
        r.failed('manifest.json: version is a string')
    elif not _SEMVER_RE.match(version):
        r.failed('manifest.json: version "%s" does not match X.Y.Z' % version)
    else:
        r.passed('manifest.json: version "%s" matches X.Y.Z' % version)

    # entry_class validation
    entry_class = manifest.get('entry_class', '')
    if not isinstance(entry_class, str) or not entry_class:
        r.failed('manifest.json: entry_class is non-empty')
    else:
        r.passed('manifest.json: entry_class "%s"' % entry_class)

    # Type checks on optional fields
    _optional_type_checks = {
        'author': str,
        'description': str,
        'min_fw_version': str,
        'promoted': bool,
        'canvas_mode': bool,
        'fullscreen': bool,
        'order': int,
    }
    for field, expected in _optional_type_checks.items():
        if field in manifest:
            val = manifest[field]
            if val is not None and not isinstance(val, expected):
                r.warned('manifest.json: optional field "%s" has wrong type '
                         '(expected %s, got %s)' % (field, expected.__name__, type(val).__name__))

    return manifest


def _lint_plugin_syntax(plugin_py, r):
    """Check plugin.py for syntax errors. Returns source string or None."""
    try:
        with open(plugin_py, 'r', encoding='utf-8') as f:
            source = f.read()
    except (OSError, IOError) as exc:
        r.failed('plugin.py: readable (%s)' % exc)
        return None

    try:
        ast.parse(source, filename=plugin_py)
    except SyntaxError as exc:
        r.failed('plugin.py: syntax OK (line %s: %s)' % (exc.lineno, exc.msg))
        return None

    r.passed('plugin.py: syntax OK')
    return source


def _lint_plugin_class(source, entry_class_name, plugin_py, r):
    """Check that entry_class exists in plugin.py. Returns set of class names."""
    try:
        tree = ast.parse(source, filename=plugin_py)
    except SyntaxError:
        return set()

    class_names = set()
    method_names = {}  # class_name -> set of method names

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_names.add(node.name)
            methods = set()
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.add(item.name)
                elif isinstance(item, ast.AsyncFunctionDef):
                    methods.add(item.name)
            method_names[node.name] = methods

    if entry_class_name in class_names:
        r.passed('plugin.py: class "%s" found' % entry_class_name)
    else:
        r.failed('plugin.py: class "%s" found (classes: %s)' % (
            entry_class_name,
            ', '.join(sorted(class_names)) if class_names else 'none',
        ))

    # Return method names for the entry class (used by ui.json validation)
    return method_names.get(entry_class_name, set())


def _lint_ui_json(ui_json_path, entry_class_methods, entry_class_name, r):
    """Validate ui.json structure."""
    try:
        with open(ui_json_path, 'r', encoding='utf-8') as f:
            raw = f.read()
    except (OSError, IOError) as exc:
        r.failed('ui.json: readable (%s)' % exc)
        return

    try:
        ui = json.loads(raw)
    except json.JSONDecodeError as exc:
        r.failed('ui.json: valid JSON (%s)' % exc)
        return
    r.passed('ui.json: valid JSON')

    if not isinstance(ui, dict):
        r.failed('ui.json: is a JSON object')
        return

    # Normalize: support both "states" and "screens" keys
    screens = ui.get('states', ui.get('screens', {}))
    if not isinstance(screens, dict) or not screens:
        r.failed('ui.json: has states/screens')
        return

    # initial_state / entry_screen
    entry = ui.get('initial_state', ui.get('entry_screen'))
    if entry is None:
        r.failed('ui.json: initial_state/entry_screen defined')
    elif entry not in screens:
        r.failed('ui.json: initial_state "%s" exists in screens' % entry)
    else:
        r.passed('ui.json: initial_state "%s" exists' % entry)

    screen_ids = set(screens.keys())

    # Collect all actions and validate targets
    all_set_state_ok = True
    has_pwr_binding = False
    all_screens_have_buttons = True
    run_targets = []  # list of (screen_id, method_name)

    for screen_id, state_def in screens.items():
        if not isinstance(state_def, dict):
            continue

        screen = state_def.get('screen', state_def)

        # Check buttons
        if 'buttons' not in screen:
            all_screens_have_buttons = False
            r.warned('ui.json: screen "%s" missing "buttons"' % screen_id)

        # Gather all actions from keys, buttons, and items
        actions = []
        keys_map = screen.get('keys', {})
        if isinstance(keys_map, dict):
            # Check for PWR bindings
            if 'PWR' in keys_map:
                has_pwr_binding = True
            actions.extend(keys_map.values())

        buttons = screen.get('buttons', {})
        if isinstance(buttons, dict):
            actions.extend(v for v in buttons.values() if isinstance(v, str))

        items = screen.get('items', [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    act = item.get('action')
                    if isinstance(act, str):
                        actions.append(act)

        # Check transitions
        transitions = state_def.get('transitions', {})
        if isinstance(transitions, dict):
            for cond, target in transitions.items():
                if isinstance(target, str) and target not in screen_ids:
                    r.warned('ui.json: screen "%s" transition "%s" targets unknown state "%s"' % (
                        screen_id, cond, target))

        # Validate action targets
        for act in actions:
            if not isinstance(act, str):
                continue

            if act.startswith('set_state:'):
                target = act[10:]
                if target not in screen_ids:
                    all_set_state_ok = False
                    r.warned('ui.json: set_state:"%s" targets unknown state' % target)

            elif act.startswith('push:'):
                target = act[5:]
                if target not in screen_ids:
                    r.warned('ui.json: push:"%s" targets unknown screen' % target)

            elif act.startswith('run:'):
                method_name = act[4:]
                run_targets.append((screen_id, method_name))

    # Report aggregate checks
    if all_set_state_ok:
        r.passed('ui.json: all set_state targets valid')

    if has_pwr_binding:
        r.failed('ui.json: no PWR key bindings (PWR is reserved for system exit)')
    else:
        r.passed('ui.json: no PWR key bindings')

    if all_screens_have_buttons:
        r.passed('ui.json: all screens have buttons')

    # Validate run:<fn> targets against entry class methods
    for screen_id, method_name in run_targets:
        if entry_class_methods:
            if method_name in entry_class_methods:
                r.passed('ui.json: run:%s -> method exists on %s' % (method_name, entry_class_name))
            else:
                r.failed('ui.json: run:%s -> method NOT found on %s' % (method_name, entry_class_name))
        else:
            r.warned('ui.json: run:%s -> cannot verify (class not parsed)' % method_name)


def _lint_icon(icon_path, r):
    """Validate app_icon.png is a valid PNG."""
    try:
        with open(icon_path, 'rb') as f:
            header = f.read(8)
    except (OSError, IOError) as exc:
        r.failed('app_icon.png: readable (%s)' % exc)
        return

    if header[:8] == _PNG_MAGIC:
        r.passed('app_icon.png: valid PNG header')
    else:
        r.failed('app_icon.png: valid PNG header (bad magic bytes)')


def _lint_py38_compat(source, plugin_py, r):
    """Warn about Python 3.8 incompatibilities."""
    try:
        tree = ast.parse(source, filename=plugin_py)
    except SyntaxError:
        return

    warnings = []

    for node in ast.walk(tree):
        # Walrus operator (:=) — Python 3.8 has it, but warn as some
        # targets may not support it
        if _HAS_NAMED_EXPR and isinstance(node, ast.NamedExpr):
            warnings.append('line %d: walrus operator (:=)' % node.lineno)

        # Match/case — Python 3.10+
        if _PY310_MATCH_TYPES:
            for match_type in _PY310_MATCH_TYPES:
                if isinstance(node, match_type):
                    warnings.append('line %d: match/case statement (Python 3.10+)' % node.lineno)

    if warnings:
        for w in warnings:
            r.warned('python 3.8 compat: %s' % w)
    else:
        r.passed('python 3.8 compat: no issues found')


# -- Main ------------------------------------------------------------------

def find_all_plugins(base_dir=None):
    """Find all plugin directories under base_dir/plugins/."""
    if base_dir is None:
        # Walk up from this script to find the project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    plugins_dir = os.path.join(base_dir, 'plugins')
    if not os.path.isdir(plugins_dir):
        return []

    result = []
    for entry in sorted(os.listdir(plugins_dir)):
        if entry.startswith('_') or entry.startswith('.'):
            continue
        path = os.path.join(plugins_dir, entry)
        if os.path.isdir(path):
            result.append(path)
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Lint an iCopy-X plugin directory for correctness.',
    )
    parser.add_argument(
        'plugin_dir',
        nargs='?',
        help='Path to the plugin directory to lint.',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        dest='lint_all',
        help='Lint all plugins in the plugins/ directory.',
    )

    args = parser.parse_args()

    if not args.lint_all and not args.plugin_dir:
        parser.error('Provide a plugin directory or use --all')

    if args.lint_all:
        plugin_dirs = find_all_plugins()
        if not plugin_dirs:
            print('No plugins found in plugins/')
            sys.exit(1)
    else:
        plugin_dirs = [args.plugin_dir]

    all_ok = True

    for plugin_dir in plugin_dirs:
        dirname = os.path.basename(os.path.abspath(plugin_dir))
        print(_bold('Linting plugin: %s/' % dirname))
        results = lint_plugin(plugin_dir)
        results.print_results()
        if not results.ok:
            all_ok = False
        if len(plugin_dirs) > 1:
            print()

    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
