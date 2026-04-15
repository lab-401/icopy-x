# Plugins

The plugin system allows extending the iCopy-X with custom functionality.
Plugins appear in the Tools menu on the device.

## How It Works

1. `plugin_loader.py` scans the `plugins/` directory at startup
2. Each subdirectory with a valid `manifest.json` is loaded
3. Plugins are sorted by `order` field and appear in the Tools menu
4. Selecting a plugin launches either `PluginActivity` (JSON-driven) or
   `CanvasModeActivity` (fullscreen subprocess)
5. PWR always exits -- the framework intercepts PWR before any plugin code

## Directory Layout

```
plugins/
  my_plugin/
    manifest.json       # REQUIRED -- plugin metadata
    plugin.py           # REQUIRED -- Python entry point
    ui.json             # OPTIONAL -- JSON UI state machine
    app_icon.png        # OPTIONAL -- 20x20 menu icon
```

## manifest.json Schema

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name in Tools menu |
| `version` | string | Semantic version (X.Y.Z) |
| `entry_class` | string | Python class name in plugin.py |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `author` | string | `""` | Plugin author |
| `description` | string | `""` | Short description |
| `min_fw_version` | string | `"1.0.0"` | Minimum firmware version required |
| `promoted` | bool | `false` | Show in main menu (not just Tools) |
| `canvas_mode` | bool | `false` | Fullscreen subprocess mode |
| `fullscreen` | bool | `false` | Hide title/button bars |
| `permissions` | list | `[]` | Required permissions (e.g., `["pm3"]`) |
| `icon` | string | `null` | Icon filename (relative to plugin dir) |
| `order` | int | `100` | Sort order in menu (lower = higher) |
| `key_map` | dict | `null` | Key translation for canvas_mode (see below) |
| `binary` | string | `null` | Subprocess binary name for canvas_mode |
| `args` | list | `[]` | Subprocess arguments for canvas_mode |

## Two Plugin Types

### JSON Schema Plugins (Normal)

The standard plugin type. Define UI screens in `ui.json` using the same
JSON schema as built-in activities. The `PluginActivity` runner handles
rendering, key dispatch, state transitions, and background task execution.

The `plugin.py` file exports a class with methods that `ui.json` invokes
via `run:<method>` actions. The class instance receives a `host` reference
to the `PluginActivity` for accessing the canvas and showing toasts.

### Canvas Mode Plugins (Fullscreen Subprocess)

For plugins that need raw display access (games, custom renderers). Set
`canvas_mode: true` in the manifest. The framework:

1. Hides the tkinter canvas
2. Launches the binary specified in `binary` as a subprocess
3. Translates device button presses to the subprocess via `xdotool`
4. Kills the subprocess when PWR is pressed

The `key_map` field maps device keys to xdotool key names:

```json
"key_map": {
    "UP": "Up",
    "DOWN": "Down",
    "OK": "Return",
    "M1": "comma",
    "M2": "period",
    "ALL": "Control_L"
}
```

Binary assets (executables, WAD files, etc.) are placed directly in the
plugin directory and bundled into the IPK.

## Creating a New Plugin

### Step 1: Create the directory

```bash
mkdir -p plugins/my_plugin
```

### Step 2: Write manifest.json

```json
{
    "name": "My Plugin",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "What this plugin does",
    "entry_class": "MyPlugin",
    "permissions": ["pm3"],
    "order": 50
}
```

### Step 3: Write plugin.py

```python
class MyPlugin:
    """Plugin entry class. Methods are called by ui.json via run: actions."""

    def do_scan(self):
        """Called when ui.json triggers 'run:do_scan'."""
        import executor
        executor.startPM3Task("hf search", 10000)
        output = executor.getPrintContent()
        # Return a dict -- keys become {placeholders} in the UI
        if executor.hasKeyword("UID"):
            uid = executor.getContentFromRegex(r"UID\s*:\s*([\w\s]+)")
            return {"status": "found", "uid": uid}
        return {"status": "not_found"}
```

### Step 4: Write ui.json

```json
{
    "plugin": true,
    "initial_state": "idle",
    "states": {
        "idle": {
            "screen": {
                "title": "My Plugin",
                "content": {
                    "type": "text",
                    "lines": [{"text": "Press OK to scan"}]
                },
                "buttons": {"left": "Back", "right": null},
                "keys": {
                    "OK": "run:do_scan",
                    "M1": "finish"
                }
            },
            "transitions": {
                "on_result.status==found": "result",
                "on_error": "error"
            }
        },
        "result": {
            "screen": {
                "title": "My Plugin",
                "content": {
                    "type": "text",
                    "lines": [{"text": "UID: {uid}"}]
                },
                "buttons": {"left": "Back", "right": null},
                "keys": {"M1": "finish"}
            }
        }
    }
}
```

### Step 5: Test

```bash
python3 tools/lint_plugin.py plugins/my_plugin
```

The linter validates the manifest schema, checks that `entry_class` exists
in `plugin.py`, and validates `ui.json` screen definitions if present.

## Included Plugins

### DOOM

Runs the DOOM shareware (Episode 1) as a fullscreen subprocess.
`canvas_mode: true`. Requires `doom` binary and `doom1.wad` in the plugin
directory. Keys are translated via xdotool (arrows for movement, OK for
action, M1/M2 for strafe, ALL for fire).

### HF Deep Scan

Runs `hf search` with extended options and displays detailed tag information.
JSON-driven plugin with `pm3` permission.

### PM3 Raw

Runs `hw version` and displays the raw PM3 client output. Useful for
verifying PM3 connectivity and version.

### Quick LF Clone

One-button LF tag clone workflow: scan tag -> identify type/ID -> prompt
user -> clone to T55xx blank. Supports EM410x, HID Prox, Indala, AWID,
and Viking tag types.

## Plugin Safety

- PWR **always** exits. Plugin code never receives PWR events.
- Plugins cannot modify the activity stack directly.
- Bad plugins (import errors, missing manifest fields, runtime exceptions)
  are caught and logged but never crash the main application.
- The `permissions` field is declarative -- plugins requesting `pm3` access
  will not load if the PM3 subsystem is unavailable.
