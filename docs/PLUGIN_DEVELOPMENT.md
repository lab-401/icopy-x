# Plugin Development Guide

This guide covers everything you need to build plugins for the iCopy-X
open-source firmware. Plugins extend the device with new features --
from simple PM3 command wrappers to multi-step RFID workflows to
full-screen games.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Plugin Directory Structure](#2-plugin-directory-structure)
3. [manifest.json Reference](#3-manifestjson-reference)
4. [JSON UI System (ui.json)](#4-json-ui-system-uijson)
5. [Plugin Code (plugin.py)](#5-plugin-code-pluginpy)
6. [Canvas Mode](#6-canvas-mode)
7. [Promoted Plugins](#7-promoted-plugins)
8. [Testing and Validation](#8-testing-and-validation)
9. [Examples Walkthrough](#9-examples-walkthrough)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Quick Start

Five steps to a working plugin.

### Step 1: Create the plugin directory

```
plugins/
  my_tool/
    manifest.json
    plugin.py
    ui.json
```

### Step 2: Write manifest.json

```json
{
    "name": "My Tool",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "Run hw version and display output",
    "entry_class": "MyToolPlugin",
    "permissions": ["pm3"],
    "order": 99
}
```

### Step 3: Write ui.json

```json
{
    "plugin": true,
    "name": "My Tool",
    "version": "1.0.0",
    "initial_state": "idle",
    "states": {
        "idle": {
            "screen": {
                "title": "My Tool",
                "content": {
                    "type": "text",
                    "lines": [
                        {"text": "Press OK to run 'hw version'", "size": "normal"}
                    ]
                },
                "buttons": {"left": "Back", "right": null},
                "keys": {
                    "OK": "run:do_run",
                    "M1": "finish"
                }
            },
            "transitions": {
                "on_result.status==done": "done",
                "on_error": "error"
            }
        },
        "done": {
            "screen": {
                "title": "My Tool",
                "content": {
                    "type": "text",
                    "lines": [{"text": "{output}", "size": "normal"}],
                    "scrollable": true
                },
                "buttons": {"left": "Back", "right": "Again"},
                "keys": {
                    "M1": "finish",
                    "M2": "set_state:idle"
                }
            }
        },
        "error": {
            "screen": {
                "title": "My Tool",
                "content": {
                    "type": "text",
                    "lines": [{"text": "{error_msg}", "size": "normal"}]
                },
                "buttons": {"left": "Back", "right": null},
                "keys": {"M1": "finish"}
            }
        }
    }
}
```

### Step 4: Write plugin.py

```python
class MyToolPlugin(object):

    def __init__(self, host=None):
        self.host = host

    def do_run(self):
        """Called by run:do_run action. Runs in a background thread."""
        success, output = self.host.pm3_command('hw version', timeout=5000)

        if success and output:
            self.host.set_var('output', output.strip())
            return {'status': 'done'}
        else:
            self.host.set_var('error_msg', output or 'No response')
            return {'status': 'error'}
```

### Step 5: Lint and test

Run the standalone linter to validate your plugin before deploying:

```bash
python3 tools/lint_plugin.py plugins/my_tool/
```

Output:

```
Linting plugin: my_tool/
  [PASS] manifest.json exists
  [PASS] plugin.py exists
  [PASS] manifest.json: required fields present
  [PASS] manifest.json: name "My Tool" (7 chars)
  [PASS] manifest.json: version "1.0.0" matches X.Y.Z
  [PASS] manifest.json: entry_class "MyToolPlugin"
  [PASS] plugin.py: syntax OK
  [PASS] plugin.py: class "MyToolPlugin" found
  [PASS] ui.json: valid JSON
  [PASS] ui.json: initial_state "idle" exists
  [PASS] ui.json: all set_state targets valid
  [PASS] ui.json: no PWR key bindings
  [PASS] ui.json: all screens have buttons
  [PASS] ui.json: run:do_run -> method exists on MyToolPlugin
  [PASS] python 3.8 compat: no issues found

  15/15 checks passed
```

If all checks pass, deploy it: copy the plugin directory into `plugins/`
on the device and restart. The loader discovers it automatically -- no
registration needed.

See [Section 8: Testing and Validation](#8-testing-and-validation) for the
full testing workflow.

---

## 2. Plugin Directory Structure

Each plugin lives in its own subdirectory under `plugins/`:

```
plugins/
  my_plugin/
    manifest.json      # REQUIRED -- plugin metadata
    plugin.py          # REQUIRED -- code entry point
    ui.json            # OPTIONAL -- JSON UI state machine
    app_icon.png       # OPTIONAL -- 20x20 menu icon
    res/               # OPTIONAL -- plugin-local resources (images, WADs, data)
    lib/               # OPTIONAL -- plugin-local Python helpers
```

**Required files:**

| File | Purpose |
|------|---------|
| `manifest.json` | Plugin metadata, permissions, launch configuration |
| `plugin.py` | Python code with the entry class |

**Optional files:**

| File | Purpose |
|------|---------|
| `ui.json` | Declarative screen definitions and state machine |
| `app_icon.png` | 20x20 pixel icon shown in the Plugins menu (fallback: system `res/img/plugin.png`) |
| `res/` | Plugin-local resources -- images, sounds, data files |
| `lib/` | Plugin-local Python helper modules (importable from plugin.py) |

The plugin directory name becomes the plugin's unique key. Directory names
starting with `_` or `.` are ignored by the loader.

---

## 3. manifest.json Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name shown in menus. Maximum 20 characters. |
| `version` | string | Semantic version (`X.Y.Z`). Must match the pattern `^\d+\.\d+\.\d+$`. |
| `entry_class` | string | Class name in `plugin.py` that the framework instantiates. Must be non-empty. |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `author` | string | `""` | Plugin author name. |
| `description` | string | `""` | One-line description shown in plugin details. |
| `min_fw_version` | string | `"1.0.0"` | Minimum firmware version required. |
| `promoted` | boolean | `false` | If `true`, appears on the Main Menu instead of the Plugins submenu. |
| `canvas_mode` | boolean | `false` | If `true`, plugin gets raw display access (subprocess-based). Implies `fullscreen`. |
| `fullscreen` | boolean | `false` | If `true`, title and button bars are hidden. |
| `permissions` | list | `[]` | Required capabilities: `"pm3"`, `"shell"`. |
| `icon` | string/null | `null` | Custom icon filename, relative to the plugin directory. |
| `order` | integer | `100` | Sort order in the Plugins menu. Lower values appear first. |
| `key_map` | object/null | `null` | For `canvas_mode`: maps device keys to subprocess X11 key names. |
| `binary` | string/null | `null` | For `canvas_mode`: subprocess binary path, relative to plugin directory. |
| `args` | list | `[]` | For `canvas_mode`: subprocess command-line arguments. |

### Minimal Example (PM3 Raw)

```json
{
    "name": "PM3 Raw",
    "version": "1.0.0",
    "author": "Lab401",
    "description": "Run hw version and display output",
    "entry_class": "PM3RawPlugin",
    "permissions": ["pm3"],
    "order": 99
}
```

### Canvas Mode Example (DOOM)

```json
{
    "name": "DOOM",
    "version": "1.0.0",
    "author": "Lab401 / id Software (shareware)",
    "description": "DOOM Episode 1 -- Knee-Deep in the Dead",
    "canvas_mode": true,
    "entry_class": "DoomPlugin",
    "binary": "doom",
    "args": ["-iwad", "doom1.wad", "-width", "240", "-height", "240"],
    "key_map": {
        "UP": "Up",
        "DOWN": "Down",
        "LEFT": "Left",
        "RIGHT": "Right",
        "OK": "Return",
        "M1": "comma",
        "M2": "period"
    },
    "order": 200
}
```

---

## 4. JSON UI System (ui.json)

The JSON UI system lets you define multi-screen flows declaratively. The
framework renders screens, handles key events, manages state transitions,
and resolves variable placeholders -- all driven by your JSON definition.

### Top-Level Structure

```json
{
    "plugin": true,
    "name": "My Plugin",
    "version": "1.0.0",
    "initial_state": "idle",
    "states": {
        "idle": { ... },
        "running": { ... },
        "done": { ... }
    }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `plugin` | no | Marker field. Set to `true` for plugins. |
| `name` | no | Plugin name (informational). |
| `version` | no | Plugin version (informational). |
| `initial_state` | yes | The state to enter when the plugin launches. Also accepted as `entry_screen`. |
| `states` | yes | Map of state ID to state definition. Also accepted as `screens`. |

### State Definition

Each state contains a screen definition and optional lifecycle hooks:

```json
{
    "idle": {
        "on_enter": "run:start_scan",
        "screen": {
            "title": "My Plugin",
            "content": { ... },
            "buttons": { "left": "Back", "right": null },
            "keys": { ... }
        },
        "transitions": {
            "on_result.status==found": "found",
            "on_result.status==error": "error",
            "on_error": "error"
        }
    }
}
```

| Field | Description |
|-------|-------------|
| `on_enter` | Action to run automatically when this state is entered. Typically `run:<method>`. |
| `screen` | The screen definition (title, content, buttons, keys). |
| `transitions` | Map of conditions to target state IDs. |

### Screen Definition

```json
{
    "title": "Scan Tag",
    "page": "1/2",
    "content": { ... },
    "toast": { ... },
    "buttons": { "left": "Back", "right": "Scan" },
    "keys": { "OK": "run:do_scan", "M1": "finish" }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | Title bar text. Supports `{variable}` placeholders. |
| `page` | string/null | no | Page indicator (e.g. `"1/2"`). Appended to title. |
| `content` | object | yes | Content area definition. See Content Types below. |
| `toast` | object/null | no | Toast overlay. See Toast section. |
| `buttons` | object | yes | Button bar labels. **Must be present on every screen.** |
| `keys` | object | yes | Key-to-action bindings. |

### Content Types

#### `text` -- Static text block

For instructions, results, warnings, and about pages.

```json
{
    "type": "text",
    "lines": [
        {"text": "Place source tag on reader", "size": "normal"},
        {"text": ""},
        {"text": "Press OK to scan", "size": "normal"}
    ],
    "scrollable": true
}
```

Line properties:
- `text` -- the display text. Supports `{variable}` placeholders.
- `size` -- `"normal"` (default) or `"large"`.
- `align` -- `"left"` (default) or `"center"`.

#### `list` -- Scrollable item list

For menus, settings, and selection screens.

```json
{
    "type": "list",
    "items": [
        {"label": "EM410x", "action": "run:clone_em"},
        {"label": "HID Prox", "action": "run:clone_hid"},
        {"label": "Indala", "action": "run:clone_indala"}
    ],
    "style": "plain",
    "selected": 0,
    "page_size": 5
}
```

| Property | Description |
|----------|-------------|
| `items` | Array of item objects. |
| `style` | `"menu"` (icon + label), `"radio"` (single select), `"checklist"` (multi select), `"plain"` (label only). |
| `selected` | Initial selected index (default 0). |
| `page_size` | Items visible per page (default 5). |

Item properties:
- `label` -- display text
- `icon` -- icon filename (menu style only)
- `action` -- action triggered on select
- `selected` -- boolean for radio/checklist
- `enabled` -- boolean (greyed out if false)

#### `progress` -- Progress bar

For long-running operations like scanning, reading, writing, key recovery.

```json
{
    "type": "progress",
    "message": "Scanning...",
    "value": 0,
    "max": 100,
    "detail": "Sector 3/16"
}
```

| Property | Description |
|----------|-------------|
| `message` | Main status text. Supports `{variable}` placeholders. |
| `value` | Current progress value. |
| `max` | Maximum progress value. |
| `detail` | Secondary detail text (e.g. `"Key A found"`). |

Use `host.set_progress(value, message)` from plugin code to update.

#### `template` -- Tag info display

For scan results, read results, and card info.

```json
{
    "type": "template",
    "header": "MIFARE",
    "subheader": "M1 S50 1K (4B)",
    "fields": [
        {"label": "Frequency", "value": "{frequency}"},
        {"label": "UID", "value": "{uid}"},
        {"row": [
            {"label": "SAK", "value": "{sak}"},
            {"label": "ATQA", "value": "{atqa}"}
        ]}
    ]
}
```

All `{variable}` placeholders are resolved from the plugin state dict.

#### `empty` -- Blank content area

For screens that only show toast messages or buttons.

```json
{
    "type": "empty"
}
```

### Toast Overlay

Temporary or persistent message overlay:

```json
{
    "text": "Tag Found",
    "icon": "check",
    "timeout": 3000,
    "style": "success"
}
```

| Property | Description |
|----------|-------------|
| `text` | Toast message. Supports `{variable}` placeholders. |
| `icon` | `"check"`, `"error"`, `"warning"`, `"info"`, or `null`. |
| `timeout` | Auto-dismiss in milliseconds. `null` or `0` = persistent until key press. |
| `style` | Visual style: `"success"`, `"error"`, `"warning"`, `"info"`. |

You can also show toasts programmatically with `host.show_toast()`.

### Button Bar

```json
{
    "left": "Back",
    "right": "Scan"
}
```

- `left` -- label for M1 button. `null` means M1 does nothing.
- `right` -- label for M2 button. `null` means M2 does nothing.
- **PWR is never shown.** It always exits. This is enforced by the framework.

### Key Bindings

```json
{
    "UP": "scroll:-1",
    "DOWN": "scroll:1",
    "OK": "run:do_scan",
    "M1": "finish",
    "M2": "set_state:scanning"
}
```

Available keys: `UP`, `DOWN`, `OK`, `M1`, `M2`.

**You cannot bind PWR.** Any `PWR` binding in your ui.json is silently
stripped at load time. PWR always exits. This is the #1 UX law.

### Actions

| Action | Description |
|--------|-------------|
| `scroll:N` | Move list selection by N positions (e.g. `scroll:1` = down, `scroll:-1` = up). |
| `select` | Activate the currently selected list item's action. |
| `finish` | Exit the plugin (go back to the menu). |
| `push:<screen_id>` | Push a new screen onto the internal stack. M1/"Back" can later `pop`. |
| `pop` | Pop the internal screen stack, returning to the previous screen. If the stack is empty, calls `finish`. |
| `set_state:<state_id>` | Transition to a different state in the state machine. |
| `run:<method>` | Call a method on the plugin's entry class in a background thread. |
| `noop` | Explicitly do nothing. |

### Variable Resolution

`{variable}` placeholders in titles, text lines, template fields, and toast
messages are resolved from (in priority order):

1. The result dict returned by the last `run:<method>` call
2. The plugin's state dict (set via `host.set_var()`)
3. Global device state (battery, firmware version, etc.)

Example flow:
1. Plugin method calls `self.host.set_var('tag_id', '0A1B2C3D4E')`
2. Screen template contains `{"text": "ID: {tag_id}"}`
3. Renderer displays: `ID: 0A1B2C3D4E`

### Transition Conditions

Transitions are evaluated after a `run:<method>` call completes. They map
conditions to target state IDs:

```json
"transitions": {
    "on_result.status==found": "found",
    "on_result.status==error": "error",
    "on_error": "error"
}
```

| Condition | Fires when |
|-----------|------------|
| `on_result.<field>==<value>` | The method returned a dict where `result[field]` matches `value` (case-insensitive string comparison). |
| `on_error` | The method raised an exception. |
| `on_complete` | The method completed (any result). Lower priority than field-specific conditions. |
| `on_timeout:<ms>` | Auto-transition after a timeout (milliseconds). |

The returned dict from your method is merged into the plugin's state dict,
so the values are available as `{variable}` placeholders in the target
screen.

---

## 5. Plugin Code (plugin.py)

### Entry Class Structure

Your entry class is a plain Python object. It does not need to extend any
base class. The framework instantiates it and injects a `host` reference:

```python
class MyPlugin(object):

    def __init__(self, host=None):
        self.host = host

    def do_something(self):
        """Called by run:do_something action. Runs in a background thread."""
        # Use self.host to interact with the framework
        success, output = self.host.pm3_command('hf 14a info', timeout=5000)
        self.host.set_var('result', output)
        return {'status': 'done'}
```

The class name must match the `entry_class` field in `manifest.json`.

### The `host` Object

The `host` object is your plugin's interface to the framework. It is
a `PluginActivity` instance that provides these methods:

#### `host.pm3_command(cmd, timeout=5000)`

Execute a Proxmark3 command via the PM3 executor.

**Requires:** `"pm3"` in manifest permissions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `cmd` | string | PM3 command (e.g. `'hf 14a info'`, `'lf search'`). |
| `timeout` | int | Timeout in milliseconds. Default 5000. |

**Returns:** `(success, output)` tuple.
- `success` -- `True` if `startPM3Task` returned 1 (completed).
- `output` -- string containing the PM3 command output.

```python
success, output = self.host.pm3_command('hf 14a info', timeout=5000)
if success:
    # parse output
else:
    # handle failure
```

If the plugin does not declare `"pm3"` permission, returns
`(False, 'Permission denied: pm3 not declared')`.

#### `host.shell_command(cmd, timeout=10)`

Execute a shell command via `subprocess.run`.

**Requires:** `"shell"` in manifest permissions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `cmd` | string or list | Command string (runs with `shell=True`) or list of args. |
| `timeout` | int | Timeout in **seconds**. Default 10. |

**Returns:** `(returncode, stdout, stderr)` tuple.

```python
rc, stdout, stderr = self.host.shell_command('ls /mnt/upan/', timeout=5)
if rc == 0:
    files = stdout.strip().split('\n')
```

#### `host.set_var(key, value)`

Set a variable for `{placeholder}` resolution in screen templates.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | string | Variable name (used as `{key}` in JSON templates). |
| `value` | any | Variable value (converted to string for display). |

**Thread-safe.** Can be called from background tasks.

```python
self.host.set_var('tag_type', 'EM410x')
self.host.set_var('tag_id', '0A1B2C3D4E')
# Now {tag_type} and {tag_id} resolve in ui.json screens
```

#### `host.get_var(key, default=None)`

Get a variable value from the plugin state dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | string | Variable name. |
| `default` | any | Value returned if key is not found. Default `None`. |

**Returns:** The variable value, or `default`.

```python
tag_type = self.host.get_var('tag_type', '')
```

#### `host.show_toast(text, timeout=3000, icon=None)`

Show a toast message overlay.

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | string | Toast message text. |
| `timeout` | int | Auto-dismiss in milliseconds. 0 = persistent until key press. Default 3000. |
| `icon` | string/None | `"check"`, `"error"`, `"warning"`, `"info"`, or `None`. |

**Thread-safe.** If called from a background thread, the toast is
scheduled on the UI thread automatically.

```python
self.host.show_toast('Tag found!', timeout=3000, icon='check')
self.host.show_toast('Operation failed', timeout=5000, icon='error')
```

#### `host.update_screen()`

Re-render the current screen after state variable changes. Call this
when you update variables mid-operation and want the screen to reflect
the changes immediately (without a state transition).

**Thread-safe.** If called from a background thread, the render is
scheduled on the UI thread.

```python
self.host.set_var('status_text', 'Reading sector 5...')
self.host.update_screen()
```

#### `host.set_progress(value, message=None)`

Update the progress bar value and optional message. Convenience method
that sets state variables and calls `update_screen()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | int/float | Progress value (0-100 or custom range matching your `max`). |
| `message` | string/None | Optional status message. |

```python
for sector in range(16):
    self.host.set_progress(sector * 100 // 16, 'Reading sector %d...' % sector)
    # ... do work ...
self.host.set_progress(100, 'Done')
```

### Background Methods (`run:` actions)

When a `run:<method>` action fires:

1. The framework sets the activity to **busy state** (all keys are swallowed).
2. Your method is called in a **daemon background thread**.
3. When your method returns, the framework returns to the UI thread.
4. The result dict is merged into the state variables.
5. Transition conditions are evaluated.
6. The screen is re-rendered.

Your method should return a dict for state machine transitions:

```python
def do_scan(self):
    success, output = self.host.pm3_command('lf search', timeout=10000)
    if success:
        self.host.set_var('tag_id', parse_id(output))
        return {'status': 'found'}
    else:
        self.host.set_var('error_msg', 'No tag detected')
        return {'status': 'error'}
```

The returned dict is merged into the plugin's state. Then, transition
conditions like `on_result.status==found` are checked against the
result keys.

If the method raises an exception, the `on_error` transition fires and
the error message is stored in `_error`.

### Optional Lifecycle: `on_destroy`

If your entry class defines an `on_destroy` method, it is called when
the plugin is exited:

```python
def on_destroy(self):
    """Clean up resources when the plugin exits."""
    # Close file handles, kill subprocesses, etc.
```

### Thread Safety Rules

1. `set_var`, `get_var`, `show_toast`, `update_screen`, and
   `set_progress` are all **thread-safe**. Call them freely from
   background methods.

2. `pm3_command` and `shell_command` are blocking calls. They should
   only be called from background threads (which is the default when
   invoked via `run:<method>`).

3. Do not call `finish()` or manipulate the activity stack from
   background threads. Return a result dict and let the state machine
   handle transitions.

4. The framework holds a busy lock during `run:<method>` execution.
   All key events are swallowed until your method returns.

---

## 6. Canvas Mode

Canvas mode is for plugins that render their own graphics -- games,
terminal emulators, subprocess-based tools. The plugin launches a
subprocess that takes over the display.

### How It Works

1. The framework hides the tkinter canvas.
2. The plugin's subprocess (specified by `binary` + `args`) is launched.
3. Device key events are translated through `key_map` and sent to the
   subprocess via `xdotool`.
4. **PWR always kills the subprocess and restores the UI.** This is
   non-overridable.

### manifest.json for Canvas Mode

```json
{
    "name": "DOOM",
    "version": "1.0.0",
    "canvas_mode": true,
    "entry_class": "DoomPlugin",
    "binary": "doom",
    "args": ["-iwad", "doom1.wad", "-width", "240", "-height", "240"],
    "key_map": {
        "UP": "Up",
        "DOWN": "Down",
        "LEFT": "Left",
        "RIGHT": "Right",
        "OK": "Return",
        "M1": "comma",
        "M2": "period"
    }
}
```

The `key_map` maps iCopy-X device keys to X11 key names (used by
`xdotool key`). Available device keys: `UP`, `DOWN`, `LEFT`, `RIGHT`,
`OK`, `M1`, `M2`. PWR is not mappable.

The `binary` path is resolved relative to the plugin directory. Path
traversal outside the plugin directory is blocked.

### plugin.py for Canvas Mode

Canvas mode plugins implement `start()`, `send_key(key_name)`, and
`stop()`:

```python
import os
import json
import subprocess
import signal

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


class DoomPlugin(object):

    def __init__(self, host=None, display=':99'):
        self.host = host
        self.display = display
        self.process = None
        self._running = False

    def start(self):
        """Launch the subprocess."""
        binary = os.path.join(_PLUGIN_DIR, 'doom')
        args = ['-iwad', 'doom1.wad', '-width', '240', '-height', '240']

        cmd = [binary] + args
        env = os.environ.copy()
        env['DISPLAY'] = self.display

        self.process = subprocess.Popen(
            cmd, cwd=_PLUGIN_DIR, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._running = True

    def send_key(self, key_name):
        """Translate a device key to an X11 keypress."""
        if not self._running or self.process is None:
            return
        # key_name is already the X11 key name from key_map
        subprocess.Popen(
            ['xdotool', 'key', '--clearmodifiers', key_name],
            env={'DISPLAY': self.display},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def stop(self):
        """Kill the subprocess. Called by PWR key (framework-enforced)."""
        self._running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            self.process = None

    @property
    def is_running(self):
        if self.process is None:
            return False
        return self.process.poll() is None
```

### Key Points

- Canvas mode plugins do not use `ui.json`. The subprocess owns the display.
- `canvas_mode: true` implies `fullscreen: true`.
- PWR always kills the process and returns to the previous screen.
- Binary assets (executables, WAD files, etc.) go in the plugin directory.
- The `CanvasModeActivity` framework class handles the lifecycle automatically
  from the manifest fields. The entry class provides `start`/`stop`/`send_key`.

---

## 7. Promoted Plugins

### How Promotion Works

By default, plugins appear in the **Plugins** submenu (icon: `plugins.png`),
which is added to the Main Menu as the 15th item after the 14 built-in
features.

Setting `"promoted": true` in `manifest.json` moves your plugin onto the
**Main Menu** itself, appended after the built-in items. The Main Menu
pagination (5 items per page) handles additional items automatically.

```json
{
    "name": "Quick Clone",
    "version": "1.0.0",
    "entry_class": "QuickClonePlugin",
    "promoted": true,
    "order": 21
}
```

### When to Use It

Promote a plugin when:
- It represents a core workflow that users will access frequently.
- It is stable and well-tested.
- It benefits from one-tap access rather than navigating through a submenu.

Do not promote plugins that are experimental, niche, or primarily for
developers. The Main Menu should stay clean.

The `order` field controls where promoted plugins appear relative to
other items. Lower values sort first. Built-in items occupy the first
14 positions.

---

## 8. Testing and Validation

There are two tiers of testing: a **standalone linter** for rapid
development iteration, and a **pytest suite** for rigorous framework
verification.

### Standalone Linter (`tools/lint_plugin.py`)

The linter is the primary tool for plugin developers. It validates a plugin
directory without running the firmware or importing any framework code.

**Lint a single plugin:**

```bash
python3 tools/lint_plugin.py plugins/my_plugin/
```

**Lint all plugins at once:**

```bash
python3 tools/lint_plugin.py --all
```

**Exit codes:** 0 = all pass, 1 = any failure.

The linter is completely standalone -- it uses only Python stdlib. You can
copy it into any project and run it without the rest of the codebase.

#### What the linter checks

**Directory structure:**

| Check | Fail condition |
|-------|---------------|
| `manifest.json` exists | Missing file |
| `plugin.py` exists | Missing file |

**manifest.json:**

| Check | Fail condition |
|-------|---------------|
| Valid JSON | Parse error |
| Required fields present | `name`, `version`, or `entry_class` missing |
| `name` length | Exceeds 20 characters |
| `version` format | Does not match `X.Y.Z` pattern |
| `entry_class` non-empty | Empty string |
| Field types | Any field has the wrong type |

**plugin.py:**

| Check | Fail condition |
|-------|---------------|
| Python syntax | `ast.parse()` fails |
| Entry class exists | Class named in `entry_class` not found via AST inspection |

**ui.json (if present):**

| Check | Fail condition |
|-------|---------------|
| Valid JSON | Parse error |
| Entry state exists | `initial_state` or `entry_screen` references non-existent state |
| `set_state:` targets | Target state does not exist in `states` map |
| `push:` targets | Target screen does not exist |
| `run:` targets | Method not found on entry class (via AST) |
| PWR key bindings | Any `keys.PWR` found (always a fail -- PWR is reserved) |
| `buttons` present | Any screen missing the `buttons` field |

**Python 3.8 compatibility:**

| Check | Warn condition |
|-------|---------------|
| f-strings | `f"..."` or `f'...'` found in plugin.py |
| Walrus operator | `:=` found |
| match/case | `match` statement found |

#### Example output

```
Linting plugin: quick_lf_clone/
  [PASS] manifest.json exists
  [PASS] plugin.py exists
  [PASS] manifest.json: required fields present
  [PASS] manifest.json: name "Quick LF Clone" (14 chars)
  [PASS] manifest.json: version "1.0.0" matches X.Y.Z
  [PASS] manifest.json: entry_class "QuickLFClonePlugin"
  [PASS] plugin.py: syntax OK
  [PASS] plugin.py: class "QuickLFClonePlugin" found
  [PASS] ui.json: valid JSON
  [PASS] ui.json: initial_state "idle" exists
  [PASS] ui.json: all set_state targets valid
  [PASS] ui.json: no PWR key bindings
  [PASS] ui.json: all screens have buttons
  [PASS] ui.json: run:do_scan -> method exists on QuickLFClonePlugin
  [PASS] ui.json: run:do_clone -> method exists on QuickLFClonePlugin
  [PASS] python 3.8 compat: no issues found

  16/16 checks passed
```

#### Integrating into your workflow

Run the linter before every deployment:

```bash
# Lint, and only deploy if it passes
python3 tools/lint_plugin.py plugins/my_plugin/ && \
  rsync -av plugins/my_plugin/ device:/home/pi/ipk_app_main/plugins/my_plugin/
```

### Framework Test Suite (pytest)

The project includes a rigorous pytest suite that tests the plugin
framework itself -- the loader, activity runner, menu integration, and
end-to-end navigation.

**Run all plugin tests:**

```bash
python3 -m pytest tests/ui/test_plugin_*.py -v
```

**Run a specific test file:**

```bash
python3 -m pytest tests/ui/test_plugin_loader.py -v      # loader validation
python3 -m pytest tests/ui/test_plugin_activity.py -v     # activity runner + PWR
python3 -m pytest tests/ui/test_plugins_menu.py -v        # Plugins submenu
python3 -m pytest tests/ui/test_plugin_integration.py -v  # end-to-end flows
```

#### Test files and what they cover

| File | Tests | Covers |
|------|-------|--------|
| `test_plugin_loader.py` | ~23 | Manifest validation, ui.json linting, plugin discovery, sort order, error isolation |
| `test_plugin_activity.py` | ~9 | PWR enforcement, key dispatch, state transitions, set_var/get_var, toast |
| `test_plugins_menu.py` | ~7 | Menu rendering, non-promoted filtering, navigation, plugin launch |
| `test_plugin_integration.py` | ~4 | Boot discovery, main menu entry, promoted plugins, full nav flow |

All tests run headless via MockCanvas (no X11, no Tk, no device needed)
and complete in under a second.

#### Key tests for plugin authors

If you are modifying the plugin framework, pay attention to these critical
tests:

- **`test_pwr_finishes_activity`** -- Verifies PWR always pops the activity.
- **`test_pwr_never_reaches_plugin`** -- Verifies plugin code never sees PWR.
- **`test_pwr_dismisses_toast_first`** -- Verifies toast dismiss before exit.
- **`test_discovers_real_plugins`** -- Verifies all `plugins/` directories load.
- **`test_full_navigation_flow`** -- Verifies Main -> Plugins -> Plugin -> PWR back -> PWR back works end-to-end.

### Linting Rules (Runtime)

The plugin loader also validates plugins at firmware startup. Invalid
plugins are logged and excluded -- they never crash the application.

At runtime the loader performs the same checks as the standalone linter,
plus:

- **Class import** -- actually imports `plugin.py` and verifies the entry
  class is instantiable
- **Icon resolution** -- resolves `app_icon.png` or manifest `icon` field
  to an absolute path, with path-traversal guards
- **Binary path containment** -- ensures `binary` does not escape the
  plugin directory

### PWR Key Enforcement

This is the single most important rule in the plugin system:

**PWR ALWAYS EXITS. No exceptions. No overrides.**

- `keys.PWR` bindings in ui.json are silently stripped at load time.
- `PluginActivity.onKeyEvent()` intercepts PWR before any plugin code runs.
- `CanvasModeActivity.onKeyEvent()` kills the subprocess on PWR.
- `_handlePWR()` is final in `BaseActivity` -- it cannot be overridden.
- Your plugin never sees PWR events. Do not try to handle them.

This ensures the user can always escape any plugin, regardless of its
state. The pytest suite includes three dedicated tests for PWR enforcement.

### Common Validation Errors

These appear in the application log or the linter output:

```
Plugin my_tool: Missing required field: 'entry_class'
Plugin my_tool: Field 'version' must match X.Y.Z pattern, got '1.0'
Plugin my_tool: Class 'MyPlugin' not found in plugin.py
Plugin my_tool ui.json: Screen 'idle' run:'do_scan' target not found on MyPlugin
Plugin my_tool ui.json: Screen 'idle': stripped reserved keys.PWR binding
Plugin my_tool ui.json: Screen 'done' set_state:'nonexistent' targets unknown state
```

---

## 9. Examples Walkthrough

### PM3 Raw -- Simplest Possible Plugin

**What it does:** Runs `hw version` on the Proxmark3 and displays the output.

**Directory:**
```
plugins/pm3_raw/
  manifest.json
  plugin.py
  ui.json
```

**State machine (3 states):**

```
idle  --[OK: run:do_run]--> (background: hw version)
  |                              |              |
  |                        success          failure
  |                              |              |
  |                           done           error
  |                              |              |
  +--- M1: finish           M1: finish     M1: finish
                            M2: set_state:idle
```

**manifest.json:**

```json
{
    "name": "PM3 Raw",
    "version": "1.0.0",
    "author": "Lab401",
    "description": "Run hw version and display output",
    "entry_class": "PM3RawPlugin",
    "permissions": ["pm3"],
    "order": 99
}
```

**plugin.py:**

```python
class PM3RawPlugin(object):

    def __init__(self, host=None):
        self.host = host

    def do_run(self):
        self.host.set_var('error_msg', '')
        self.host.set_var('output_lines', '')

        success, output = self.host.pm3_command('hw version', timeout=5000)

        if success and output:
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            display = '\n'.join(lines[:8]) if lines else '(empty response)'
            self.host.set_var('output_lines', display)
            return {'status': 'done'}
        else:
            msg = 'PM3 not connected or no response'
            if output:
                msg = output
            self.host.set_var('error_msg', msg)
            return {'status': 'error'}
```

Key takeaways:
- Entry class is a plain `object`, not a framework subclass.
- `do_run` runs in a background thread automatically.
- Returns a dict with `status` key for state machine transitions.
- Uses `set_var` to pass data to the UI for `{placeholder}` resolution.
- Limits output to 8 lines to fit the 240x240 screen.

### Quick LF Clone -- Multi-State Flow with PM3

**What it does:** Scans an LF tag, identifies the type and ID, then clones
it to a T55xx blank.

**State machine (4 states):**

```
idle  --[OK: run:do_scan]--> (background: lf search)
  |                              |              |
  |                          found            error
  |                              |              |
  |    found --[OK: run:do_clone]--> (background: lf em 410x clone ...)
  |      |                              |              |
  |      |                           done            error
  |      |                              |
  |      |                           done --[OK: set_state:idle]
  |      |
  +------+--- M1: finish (from any state)
```

**plugin.py (key sections):**

```python
import re

_CLONE_MAP = {
    "EM410x": "lf em 410x clone --id {id}",
    "HID Prox": "lf hid clone -r {id}",
    "Indala": "lf indala clone -r {id}",
    "AWID": "lf awid clone -r {id}",
    "Viking": "lf viking clone --id {id}",
}


class QuickLFClonePlugin(object):

    def __init__(self, host=None):
        self.host = host

    def do_scan(self):
        self.host.set_var('error_msg', '')
        self.host.set_var('tag_type', '')
        self.host.set_var('tag_id', '')

        success, output = self.host.pm3_command('lf search', timeout=10000)

        if not success or not output:
            self.host.set_var('error_msg', 'No tag detected')
            return {'status': 'error'}

        tag_type, tag_id = _parse_lf_output(output)

        if tag_type and tag_id:
            self.host.set_var('tag_type', tag_type)
            self.host.set_var('tag_id', tag_id)
            return {'status': 'found'}
        else:
            self.host.set_var('error_msg', 'Could not identify tag')
            return {'status': 'error'}

    def do_clone(self):
        tag_type = self.host.get_var('tag_type', '')
        tag_id = self.host.get_var('tag_id', '')

        template = _CLONE_MAP.get(tag_type)
        if template is None:
            self.host.set_var('error_msg',
                              'Clone not supported for %s' % tag_type)
            return {'status': 'error'}

        cmd = template.format(id=tag_id)
        success, output = self.host.pm3_command(cmd, timeout=15000)

        if success and output and ('[+]' in output or 'written' in output.lower()):
            return {'status': 'done'}

        self.host.set_var('error_msg', 'Clone failed')
        return {'status': 'error'}
```

Key takeaways:
- Multiple `run:` methods drive different stages of the workflow.
- Variables set in `do_scan` persist across states and are used in `do_clone`.
- The `found` screen displays `{tag_type}` and `{tag_id}` from scan results.
- Clone command is selected by tag type from a lookup table.
- PM3 output is parsed with regex to extract structured data.

### DOOM -- Canvas Mode Subprocess

**What it does:** Launches the DOOM shareware WAD as a fullscreen
subprocess. Device keys are mapped to game controls.

**No ui.json.** Canvas mode plugins bypass the JSON UI entirely.

**manifest.json** declares `canvas_mode: true` with a `key_map` and
`binary` field. The entry class manages the subprocess lifecycle
(`start`, `send_key`, `stop`).

Key takeaways:
- `canvas_mode: true` tells the framework to use `CanvasModeActivity`.
- The framework hides the tkinter canvas and launches the binary.
- `key_map` translates device keys to X11 key names via xdotool.
- PWR kills the subprocess unconditionally.
- Binary assets must be placed in the plugin directory.
- On iCopy-X, ARM binaries run under `qemu-arm-static` with the
  appropriate `QEMU_LD_PREFIX` and library paths.

---

## 10. Troubleshooting

### Plugin does not appear in the menu

**Check the application log.** The loader logs all validation errors.
Common causes:

- Missing `manifest.json` or `plugin.py` in the plugin directory.
- Directory name starts with `_` or `.` (these are silently skipped).
- `entry_class` name does not match any class in `plugin.py`.
- JSON syntax error in `manifest.json` or `ui.json`.
- `version` field does not match `X.Y.Z` pattern (e.g. `"1.0"` is invalid,
  must be `"1.0.0"`).

### "Permission denied" when calling pm3_command

Add `"pm3"` to the `permissions` list in `manifest.json`:

```json
"permissions": ["pm3"]
```

Same for `shell_command` -- add `"shell"` to permissions.

### Method not found for run:do_something

The method name after `run:` must exist on your entry class. Check:

- The method name matches exactly (case-sensitive).
- The method is defined on the class in `plugin.py`, not on a helper module.
- The `entry_class` in `manifest.json` matches the actual class name.

The linter warns about this at load time if it can resolve the class.

### Screen shows {variable} literally instead of the value

The variable was not set before the screen rendered. Ensure:

- You call `host.set_var('key', value)` before the state transition.
- The variable name in `{...}` matches the key you set (case-sensitive).
- If setting variables mid-operation, call `host.update_screen()` afterward.

### Toast does not appear

- Check that the `toast` field in your screen definition has a `text` value.
- For programmatic toasts, ensure the `icon` parameter is one of the
  accepted values (`"check"`, `"error"`, `"warning"`, `"info"`) or `None`.

### Plugin hangs / keys unresponsive

Your `run:<method>` is still executing. The framework enters busy state
during background tasks and swallows all keys. Check:

- PM3 commands are using a reasonable timeout.
- Shell commands have a timeout set.
- No infinite loops in background methods.
- The method always returns (does not block indefinitely).

### Canvas mode binary not found

The `binary` path is resolved relative to the plugin directory. Ensure:

- The binary file exists in the plugin directory.
- The `binary` field in manifest.json is a relative path (not absolute).
- The binary has execute permissions (`chmod +x`).
- Path does not escape the plugin directory (security guard blocks this).

### Debugging Tips

1. **Run the linter first.** Before anything else:
   ```bash
   python3 tools/lint_plugin.py plugins/my_plugin/
   ```
   This catches 90% of problems (missing fields, bad references, syntax
   errors) in under a second, without starting the firmware.

2. **Run the framework tests.** If you changed framework code:
   ```bash
   python3 -m pytest tests/ui/test_plugin_*.py -v
   ```
   43 tests in 0.2 seconds. All must pass before deploying.

3. **Check the application log.** Every loader error, action dispatch,
   and transition is logged. On the device: check stdout or redirect to
   a file.

4. **Start simple.** Get a minimal plugin working first (one state, one
   button), then add complexity. Use `plugins/pm3_raw/` as your template.

5. **Test state transitions.** Print your return dicts and verify they
   match the `on_result.<field>==<value>` conditions in your transitions.

6. **Variable names are case-sensitive.** `{tag_id}` and `{Tag_ID}` are
   different variables.

7. **Background methods run in daemon threads.** Do not access tkinter
   widgets directly. Use `host.set_var()`, `host.show_toast()`,
   `host.update_screen()`, and `host.set_progress()` -- they are
   thread-safe.

8. **The 240x240 screen is small.** Limit text output to 8-10 lines.
   Use `scrollable: true` for longer content. Keep labels short.

9. **Lint all plugins before building an IPK:**
   ```bash
   python3 tools/lint_plugin.py --all && python3 tools/build_ipk.py -o my.ipk
   ```
