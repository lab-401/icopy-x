"""Tests for plugin_loader — discover, validate, and lint plugins.

Covers:
  - validate_manifest: required fields, types, name length, version format
  - lint_ui_json: structure, targets, PWR stripping, buttons, run: targets
  - discover_plugins: real plugins, sort order, skip rules, error handling

All tests run headless.  Tests that need filesystem fixtures use tmp_path.
"""

import json
import os
import sys
import pytest

from plugin_loader import validate_manifest, lint_ui_json, discover_plugins, PluginInfo


# =====================================================================
# TestValidateManifest
# =====================================================================

class TestValidateManifest:
    """Tests for validate_manifest()."""

    def _write_manifest(self, tmp_path, data):
        """Helper: write a manifest dict to tmp_path/manifest.json."""
        p = tmp_path / 'manifest.json'
        p.write_text(json.dumps(data), encoding='utf-8')
        return str(p)

    def test_valid_manifest_passes(self, tmp_path):
        """A manifest with all required fields and valid values passes."""
        path = self._write_manifest(tmp_path, {
            'name': 'Test Plugin',
            'version': '1.0.0',
            'entry_class': 'TestPlugin',
        })
        manifest, errors = validate_manifest(path)
        assert manifest is not None
        assert errors == []

    @pytest.mark.parametrize('missing_field', ['name', 'version', 'entry_class'])
    def test_missing_required_fields(self, tmp_path, missing_field):
        """Missing a required field produces an error."""
        data = {
            'name': 'Test',
            'version': '1.0.0',
            'entry_class': 'TestPlugin',
        }
        del data[missing_field]
        path = self._write_manifest(tmp_path, data)
        manifest, errors = validate_manifest(path)
        assert len(errors) > 0
        # The error should mention the missing field
        assert any(missing_field in e for e in errors)

    def test_name_too_long(self, tmp_path):
        """Name exceeding 20 characters produces an error."""
        path = self._write_manifest(tmp_path, {
            'name': 'A' * 21,
            'version': '1.0.0',
            'entry_class': 'TestPlugin',
        })
        manifest, errors = validate_manifest(path)
        assert len(errors) > 0
        assert any('20' in e for e in errors)

    def test_bad_version_format(self, tmp_path):
        """Version not matching X.Y.Z produces an error."""
        path = self._write_manifest(tmp_path, {
            'name': 'Test',
            'version': '1.0',
            'entry_class': 'TestPlugin',
        })
        manifest, errors = validate_manifest(path)
        assert len(errors) > 0
        assert any('X.Y.Z' in e for e in errors)

    def test_empty_entry_class(self, tmp_path):
        """Empty entry_class string produces an error."""
        path = self._write_manifest(tmp_path, {
            'name': 'Test',
            'version': '1.0.0',
            'entry_class': '',
        })
        manifest, errors = validate_manifest(path)
        assert len(errors) > 0
        assert any('entry_class' in e for e in errors)

    def test_optional_field_defaults(self, tmp_path):
        """Manifest with only required fields returns a valid dict."""
        path = self._write_manifest(tmp_path, {
            'name': 'Test',
            'version': '1.0.0',
            'entry_class': 'TestPlugin',
        })
        manifest, errors = validate_manifest(path)
        assert manifest is not None
        assert errors == []
        # Optional fields not present — loader provides defaults at load time
        assert 'author' not in manifest

    def test_wrong_type_promoted(self, tmp_path):
        """Optional 'promoted' with wrong type produces an error."""
        path = self._write_manifest(tmp_path, {
            'name': 'Test',
            'version': '1.0.0',
            'entry_class': 'TestPlugin',
            'promoted': 'yes',  # should be bool
        })
        manifest, errors = validate_manifest(path)
        assert len(errors) > 0
        assert any('promoted' in e for e in errors)

    def test_invalid_json_file(self, tmp_path):
        """Malformed JSON produces a fatal error."""
        p = tmp_path / 'manifest.json'
        p.write_text('{bad json', encoding='utf-8')
        manifest, errors = validate_manifest(str(p))
        assert manifest is None
        assert len(errors) > 0


# =====================================================================
# TestLintUiJson
# =====================================================================

class TestLintUiJson:
    """Tests for lint_ui_json()."""

    def _write_ui(self, tmp_path, data):
        """Helper: write a ui.json dict to tmp_path/ui.json."""
        p = tmp_path / 'ui.json'
        p.write_text(json.dumps(data), encoding='utf-8')
        return str(p)

    def _valid_ui(self):
        """Return a minimal valid ui.json dict."""
        return {
            'initial_state': 'main',
            'states': {
                'main': {
                    'screen': {
                        'title': 'Test',
                        'content': {'type': 'text', 'lines': [{'text': 'Hello'}]},
                        'buttons': {'left': 'Back', 'right': None},
                        'keys': {'M1': 'finish', 'OK': 'set_state:second'},
                    },
                },
                'second': {
                    'screen': {
                        'title': 'Second',
                        'content': {'type': 'text', 'lines': [{'text': 'Page 2'}]},
                        'buttons': {'left': 'Back', 'right': None},
                        'keys': {'M1': 'set_state:main'},
                    },
                },
            },
        }

    def test_valid_ui_json_passes(self, tmp_path):
        """A well-formed ui.json returns a dict with no warnings."""
        path = self._write_ui(tmp_path, self._valid_ui())
        ui, warnings = lint_ui_json(path, str(tmp_path))
        assert ui is not None
        assert warnings == []

    def test_pwr_key_stripped(self, tmp_path):
        """PWR key bindings are stripped and produce a warning."""
        data = self._valid_ui()
        data['states']['main']['screen']['keys']['PWR'] = 'finish'
        path = self._write_ui(tmp_path, data)
        ui, warnings = lint_ui_json(path, str(tmp_path))
        assert ui is not None
        assert any('PWR' in w for w in warnings)
        # PWR should be removed from the returned dict
        main_keys = ui['states']['main']['screen']['keys']
        assert 'PWR' not in main_keys

    def test_bad_push_target_warned(self, tmp_path):
        """push: targeting a nonexistent screen produces a warning."""
        data = self._valid_ui()
        data['states']['main']['screen']['keys']['OK'] = 'push:nonexistent'
        # push target is checked in buttons values too, let's use keys
        path = self._write_ui(tmp_path, data)
        ui, warnings = lint_ui_json(path, str(tmp_path))
        # set_state on the old 'OK' action is now push, which is checked
        # as a button/key action — the push target 'nonexistent' is not
        # in screens, but push targets are checked in _all_actions via
        # the set_state check path.  Actually push targets are only checked
        # in buttons.  Let's add it as a button instead.
        data2 = self._valid_ui()
        data2['states']['main']['screen']['buttons']['right'] = 'push:nonexistent'
        path2 = self._write_ui(tmp_path, data2)
        ui2, warnings2 = lint_ui_json(path2, str(tmp_path))
        assert any('nonexistent' in w for w in warnings2)

    def test_missing_buttons_warned(self, tmp_path):
        """Screen without 'buttons' key produces a warning."""
        data = self._valid_ui()
        del data['states']['main']['screen']['buttons']
        path = self._write_ui(tmp_path, data)
        ui, warnings = lint_ui_json(path, str(tmp_path))
        assert any('buttons' in w for w in warnings)

    def test_invalid_json(self, tmp_path):
        """Malformed JSON returns None with an error."""
        p = tmp_path / 'ui.json'
        p.write_text('{bad', encoding='utf-8')
        ui, warnings = lint_ui_json(str(p), str(tmp_path))
        assert ui is None
        assert len(warnings) > 0

    def test_state_machine_format_validated(self, tmp_path):
        """State machine transitions targeting unknown states are warned."""
        data = self._valid_ui()
        data['states']['main']['transitions'] = {
            'on_complete': 'nonexistent_state',
        }
        path = self._write_ui(tmp_path, data)
        ui, warnings = lint_ui_json(path, str(tmp_path))
        assert any('nonexistent_state' in w for w in warnings)

    def test_run_target_validated(self, tmp_path):
        """run:<fn> targets are checked against the activity class."""
        data = self._valid_ui()
        data['states']['main']['screen']['keys']['OK'] = 'run:do_something'
        path = self._write_ui(tmp_path, data)

        # With a class that has the method — no warning
        class FakePlugin:
            def do_something(self):
                pass

        ui, warnings = lint_ui_json(path, str(tmp_path), activity_class=FakePlugin)
        assert not any('do_something' in w for w in warnings)

        # With a class that lacks the method — warning
        class EmptyPlugin:
            pass

        ui2, warnings2 = lint_ui_json(path, str(tmp_path), activity_class=EmptyPlugin)
        assert any('do_something' in w for w in warnings2)

    def test_bad_set_state_target_warned(self, tmp_path):
        """set_state: targeting a nonexistent state produces a warning."""
        data = self._valid_ui()
        data['states']['main']['screen']['keys']['OK'] = 'set_state:ghost'
        path = self._write_ui(tmp_path, data)
        ui, warnings = lint_ui_json(path, str(tmp_path))
        assert any('ghost' in w for w in warnings)


# =====================================================================
# TestDiscoverPlugins
# =====================================================================

class TestDiscoverPlugins:
    """Tests for discover_plugins()."""

    def test_discovers_real_plugins(self):
        """discover_plugins() finds the real plugins in the project."""
        plugins = discover_plugins()
        assert len(plugins) >= 4
        names = [p.name for p in plugins]
        assert 'PM3 Raw' in names
        assert 'DOOM' in names

    def test_sort_by_order_then_name(self):
        """Plugins are sorted by (order, name)."""
        plugins = discover_plugins()
        orders = [(p.order, p.name) for p in plugins]
        assert orders == sorted(orders)

    def test_skips_dot_and_underscore_dirs(self, tmp_path):
        """Directories starting with . or _ are skipped."""
        # Create a hidden dir and a private dir alongside a valid plugin
        hidden = tmp_path / '.hidden'
        hidden.mkdir()
        (hidden / 'manifest.json').write_text('{}')

        private = tmp_path / '_private'
        private.mkdir()
        (private / 'manifest.json').write_text('{}')

        valid = tmp_path / 'valid_plugin'
        valid.mkdir()
        (valid / 'manifest.json').write_text(json.dumps({
            'name': 'Valid',
            'version': '1.0.0',
            'entry_class': 'ValidPlugin',
        }))
        (valid / 'plugin.py').write_text(
            'class ValidPlugin(object):\n    pass\n'
        )

        plugins = discover_plugins(str(tmp_path))
        keys = [p.key for p in plugins]
        assert '.hidden' not in keys
        assert '_private' not in keys

    def test_missing_directory_returns_empty(self, tmp_path):
        """Non-existent plugin directory returns empty list."""
        plugins = discover_plugins(str(tmp_path / 'nonexistent'))
        assert plugins == []

    def test_bad_plugin_skipped_others_load(self, tmp_path):
        """A broken plugin doesn't prevent others from loading."""
        # Bad plugin: missing plugin.py
        bad = tmp_path / 'bad_plugin'
        bad.mkdir()
        (bad / 'manifest.json').write_text(json.dumps({
            'name': 'Bad',
            'version': '1.0.0',
            'entry_class': 'BadPlugin',
        }))
        # No plugin.py

        # Good plugin
        good = tmp_path / 'good_plugin'
        good.mkdir()
        (good / 'manifest.json').write_text(json.dumps({
            'name': 'Good',
            'version': '1.0.0',
            'entry_class': 'GoodPlugin',
        }))
        (good / 'plugin.py').write_text(
            'class GoodPlugin(object):\n    pass\n'
        )

        plugins = discover_plugins(str(tmp_path))
        assert len(plugins) == 1
        assert plugins[0].name == 'Good'
