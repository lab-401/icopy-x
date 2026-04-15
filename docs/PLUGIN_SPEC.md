# Plugin System Specification

## Directory Layout

Each plugin lives in its own subdirectory under `plugins/`:

```
plugins/
  my_plugin/
    manifest.json      # REQUIRED — plugin metadata
    plugin.py          # REQUIRED — code entry point
    ui.json            # OPTIONAL — JSON UI screens (if not canvas_mode)
    app_icon.png       # OPTIONAL — 20x20 menu icon (fallback: res/img/plugin.png)
    res/               # OPTIONAL — plugin-local resources (images, sounds, WADs)
    lib/               # OPTIONAL — plugin-local Python helpers
```

## manifest.json Schema

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "Plugin Author",
  "description": "One-line description of what this plugin does",
  "min_fw_version": "1.0.0",
  "promoted": false,
  "canvas_mode": false,
  "fullscreen": false,
  "entry_class": "MyPluginActivity",
  "permissions": ["pm3", "shell"]
}
```

### Required Fields

| Field         | Type   | Description                                    |
|---------------|--------|------------------------------------------------|
| `name`        | string | Display name (shown in menu). Max 20 chars.    |
| `version`     | string | Semantic version (X.Y.Z)                       |
| `entry_class` | string | Class name in plugin.py that extends BaseActivity or PluginActivity |

### Optional Fields

| Field            | Type    | Default | Description                                              |
|------------------|---------|---------|----------------------------------------------------------|
| `author`         | string  | ""      | Plugin author name                                       |
| `description`    | string  | ""      | One-line description                                     |
| `min_fw_version` | string  | "1.0.0" | Minimum firmware version required                        |
| `promoted`       | boolean | false   | If true, appears on Main Menu instead of Plugins submenu |
| `canvas_mode`    | boolean | false   | If true, plugin gets raw canvas access (e.g. DOOM)       |
| `fullscreen`     | boolean | false   | If true, title/button bars are hidden (canvas_mode implies this) |
| `entry_class`    | string  | —       | Class name exported from plugin.py                       |
| `permissions`    | list    | []      | Required capabilities: "pm3", "shell"                    |
| `icon`           | string  | null    | Custom icon filename (relative to plugin dir)            |
| `key_map`        | object  | null    | For canvas_mode: maps device keys to subprocess keys     |
| `binary`         | string  | null    | For canvas_mode: subprocess binary path (relative)       |
| `args`           | list    | []      | For canvas_mode: subprocess arguments                    |
| `order`          | integer | 100     | Sort order in Plugins menu (lower = higher)              |

## plugin.py Contract

```python
"""plugins/my_plugin/plugin.py"""
from lib.actbase import BaseActivity

class MyPluginActivity(BaseActivity):
    """Entry class name must match manifest.json entry_class."""

    ACT_NAME = 'plugin_my_plugin'  # Convention: 'plugin_' + directory name

    def onCreate(self, bundle=None):
        # Set up UI — either manually or via self.load_ui_json()
        pass

    def onKeyEvent(self, key):
        # Handle keys — PWR is NEVER delivered here (framework intercepts)
        pass
```

### What plugins CAN do:
- Use all BaseActivity methods (setTitle, setLeftButton, setRightButton, etc.)
- Use all widgets (ListView, Toast, ProgressBar, BigTextListView, ConsoleView)
- Dispatch PM3 commands via `executor.startPM3Task(cmd, timeout)`
- Execute shell commands via `subprocess.run()`
- Load their own ui.json for declarative screen definitions
- Access their own `res/` directory for images, sounds, data files
- Use `startBGTask()` for background operations

### What plugins CANNOT do:
- Bind to PWR key (silently stripped — framework enforces exit)
- Access other plugins' directories
- Modify system files outside their own directory
- Call `actstack` directly to manipulate the activity stack
- Override `_handlePWR()` — the method is final in BaseActivity

## ui.json Contract

Same schema as docs/UI_JSON_SCHEMA.md with plugin-specific rules:

```json
{
  "entry_screen": "main",
  "screens": {
    "main": {
      "title": "My Plugin",
      "content": { "type": "text", "lines": [{"text": "Hello!"}] },
      "buttons": { "left": "Back", "right": null },
      "keys": { "M1": "finish" }
    }
  }
}
```

### Plugin UI Linting Rules (enforced at load time)

1. All `push:<id>` targets must exist in the plugin's own `screens` map
2. No `keys.PWR` — silently stripped if present
3. All `run:<fn>` targets must exist in plugin.py's entry class
4. `buttons` must be present on every screen
5. All `{variable}` references must be resolvable from plugin state
6. Icon/resource references must exist relative to the plugin directory

## Promotion (Main Menu Integration)

Plugins with `"promoted": true` in manifest.json appear directly on the
Main Menu, appended after the 14 built-in items. The Main Menu pagination
(5 items per page) handles this automatically via ListView.

Non-promoted plugins appear under the "Plugins" menu item (icon: plugins.png),
which is itself added to the Main Menu as the 15th item.

## Permissions

| Permission | Grants                                          |
|------------|-------------------------------------------------|
| `pm3`      | Access to executor.startPM3Task and related fns |
| `shell`    | Access to subprocess execution                  |

Plugins without declared permissions can still use the full Python stdlib
and all UI widgets. Permissions serve as documentation and future-proofing
for sandboxing.

## Plugin Lifecycle

1. **Discovery**: `plugin_loader.discover_plugins()` scans `plugins/` subdirs
2. **Validation**: manifest.json parsed and validated; ui.json linted
3. **Registration**: Valid plugins registered in plugin registry
4. **Menu Build**: Promoted plugins added to Main Menu; others to Plugins submenu
5. **Launch**: User selects plugin → `PluginActivity` instantiated → `onCreate()`
6. **Running**: Plugin handles keys, dispatches commands, updates UI
7. **Exit**: PWR pressed → framework calls `finish()` → plugin's `onDestroy()`

## canvas_mode Plugins

Canvas mode plugins (like DOOM) bypass the JSON UI entirely:

1. Framework hides the tkinter UI
2. Plugin launches a subprocess (specified by `binary` + `args`)
3. Device key events are translated via `key_map` and sent via xdotool
4. PWR always kills the subprocess and restores the UI
5. The plugin class manages the subprocess lifecycle
