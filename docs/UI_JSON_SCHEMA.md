# Declarative JSON UI Schema — iCopy-X

## Design Goals

1. Express EVERY original screen in JSON (proven by screenshot comparison)
2. Support multi-screen flows driven by middleware state machines
3. Serve as the plugin contract (plugins describe UI in JSON, renderer enforces rules)
4. PWR key always exits — enforced by renderer, not by screen definitions
5. Lintable — reject malformed UI definitions before deployment

---

## Screen Definition

Every screen is a JSON object:

```json
{
  "id": "scan_found_mf1k",
  "title": "Scan Tag",
  "page": null,
  "content": { ... },
  "toast": null,
  "buttons": { "left": null, "right": null },
  "keys": { ... },
  "transitions": { ... }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique screen identifier |
| `title` | string | yes | Title bar text |
| `page` | string/null | no | Page indicator (e.g. "1/2", "1/4") |
| `content` | object | yes | Content area definition (see Content Types) |
| `toast` | object/null | no | Toast overlay (auto-dismiss or persistent) |
| `buttons` | object | yes | Left/right button labels (null = no button) |
| `keys` | object | yes | Key-to-action mapping |
| `transitions` | object | no | State machine transitions |

---

## Content Types

### `list` — Scrollable item list (menus, settings, card types)

Used by: Main Menu, Volume, Backlight, Diagnosis, Simulation, Sniff TRF

```json
{
  "type": "list",
  "items": [
    {"label": "Auto Copy", "icon": "icon_autocopy.png", "action": "push:autocopy"},
    {"label": "Scan Tag", "icon": "icon_scan.png", "action": "push:scan"},
    {"label": "Read Tag", "icon": "icon_read.png", "action": "push:readlist"}
  ],
  "style": "menu",
  "selected": 0,
  "page_size": 5
}
```

**Styles:**
- `menu` — icon + label, highlight on selection (main menu)
- `radio` — label + checkbox, one selected at a time (Volume, Backlight)
- `checklist` — label + checkbox, multiple selections (Sniff TRF)
- `plain` — label only, no decorations (Diagnosis, Simulation)

**Item fields:**
- `label`: Display text
- `icon`: Icon filename (menu style only, optional)
- `action`: What happens when item is selected (see Actions)
- `selected`: Boolean for radio/checklist styles
- `enabled`: Boolean (greyed out if false)

### `template` — Tag info display

Used by: Scan result, Auto Copy result, Read result

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

**Fields can use `{variable}` placeholders** that are resolved from the middleware result dict.

### `progress` — Progress bar with message

Used by: Scanning, Reading, Writing, Key Recovery

```json
{
  "type": "progress",
  "message": "Scanning...",
  "value": 0,
  "max": 100,
  "detail": null
}
```

- `value`/`max`: Progress bar position (0-100 or custom range)
- `message`: Main status text
- `detail`: Secondary detail text (e.g. "Sector 3/16", "Key A found")

### `text` — Static text block

Used by: About page, PC-Mode instructions, warnings

```json
{
  "type": "text",
  "lines": [
    {"text": "ICopy-XS", "size": "large", "align": "center"},
    {"text": ""},
    {"text": "HW  1.0.4", "size": "normal"},
    {"text": "HMI 1.0.2"},
    {"text": "OS  1.0.3"},
    {"text": "PM  1.0.2"},
    {"text": "SN  01350002"}
  ],
  "scrollable": true
}
```

### `input` — Data entry (hex key input)

Used by: Manual key entry for MIFARE

```json
{
  "type": "input",
  "label": "Enter Key A:",
  "format": "hex",
  "length": 12,
  "placeholder": "FFFFFFFFFFFF",
  "value": ""
}
```

### `empty` — Blank content area

Used by: Screens that only show toast/buttons

```json
{
  "type": "empty"
}
```

---

## Toast Overlay

Temporary or persistent message overlay on top of content:

```json
{
  "text": "Tag Found",
  "icon": "check",
  "timeout": 3000,
  "style": "success"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Toast message |
| `icon` | string/null | Icon: "check", "error", "warning", "info", null |
| `timeout` | int/null | Auto-dismiss ms (null = persistent until key press) |
| `style` | string | Visual style: "success", "error", "warning", "info" |

---

## Button Bar

```json
{
  "left": "Rescan",
  "right": "Simulate"
}
```

- `left`: M1 button label (null = M1 does nothing)
- `right`: M2 button label (null = M2 does nothing)
- **PWR is NEVER shown** — it always works and always exits

---

## Key Bindings

```json
{
  "UP": "scroll:-1",
  "DOWN": "scroll:1",
  "OK": "select",
  "M1": "rescan",
  "M2": "push:simulation"
}
```

**Built-in actions:**
- `scroll:N` — move selection by N in list
- `select` — activate selected list item
- `finish` — exit current screen (go back)
- `push:<screen_id>` — push new screen onto stack
- `run:<middleware_fn>` — call middleware function
- `set_state:<state_id>` — transition to state
- `noop` — explicitly do nothing

**PWR is implicitly `finish` on every screen.** The renderer enforces this. Screens CANNOT override PWR. This is the UX law.

---

## State Machine (Multi-Screen Flows)

For activities with multiple states (scanning → found → reading → done):

```json
{
  "id": "scan_activity",
  "initial_state": "idle",
  "states": {
    "idle": {
      "screen": {
        "title": "Scan Tag",
        "content": {"type": "empty"},
        "toast": {"text": "Place tag on reader", "icon": "info", "timeout": null},
        "buttons": {"left": "Back", "right": "Scan"},
        "keys": {
          "M1": "finish",
          "M2": "set_state:scanning"
        }
      }
    },
    "scanning": {
      "on_enter": "run:scan.scan_all_synchronous",
      "screen": {
        "title": "Scan Tag",
        "content": {
          "type": "progress",
          "message": "Scanning...",
          "value": "{scan_progress}",
          "max": 100
        },
        "buttons": {"left": null, "right": null},
        "keys": {}
      },
      "transitions": {
        "on_result.found==true": "found",
        "on_result.found==false": "not_found",
        "on_error": "error"
      }
    },
    "found": {
      "screen": {
        "title": "Scan Tag",
        "content": {
          "type": "template",
          "header": "{tag_type_name}",
          "subheader": "{tag_subtype}",
          "fields": [
            {"label": "Frequency", "value": "{frequency}"},
            {"label": "UID", "value": "{uid}"},
            {"row": [
              {"label": "SAK", "value": "{sak}"},
              {"label": "ATQA", "value": "{atqa}"}
            ]}
          ]
        },
        "toast": {"text": "Tag Found", "icon": "check", "timeout": 3000},
        "buttons": {"left": "Rescan", "right": "Simulate"},
        "keys": {
          "M1": "set_state:scanning",
          "M2": "push:simulation_with_tag"
        }
      }
    },
    "not_found": {
      "screen": {
        "title": "Scan Tag",
        "content": {"type": "empty"},
        "toast": {"text": "No tag found", "icon": "error", "timeout": null},
        "buttons": {"left": "Rescan", "right": "Rescan"},
        "keys": {
          "M1": "set_state:scanning",
          "M2": "set_state:scanning"
        }
      }
    },
    "error": {
      "screen": {
        "title": "Scan Tag",
        "content": {"type": "empty"},
        "toast": {"text": "Scan error", "icon": "error", "timeout": null},
        "buttons": {"left": "Retry", "right": null},
        "keys": {
          "M1": "set_state:scanning"
        }
      }
    }
  }
}
```

### State Machine Fields

| Field | Description |
|-------|-------------|
| `initial_state` | State to enter on activity launch |
| `on_enter` | Action to run when entering this state |
| `screen` | Screen definition for this state |
| `transitions` | Map of conditions → target states |

### Transition Conditions

- `on_result.<field>==<value>` — middleware callback returned a result with field matching value
- `on_error` — middleware callback raised an exception
- `on_timeout:<ms>` — auto-transition after timeout
- `on_progress:<value>` — transition when progress reaches value

### Variable Resolution

`{variable}` placeholders in screen definitions are resolved from:
1. The middleware result dict (highest priority)
2. The activity's state context
3. Global device state (battery, version, etc.)

---

## Plugin Contract

Plugins use the SAME schema. A plugin's `ui.json` contains:

```json
{
  "plugin": true,
  "name": "My RFID Tool",
  "version": "1.0.0",
  "entry_screen": "main",
  "screens": {
    "main": { ... },
    "scan": { ... },
    "result": { ... }
  }
}
```

**Enforced constraints on plugins:**
1. PWR always exits — renderer intercepts before plugin sees it
2. M1/M2 only active when `buttons.left`/`buttons.right` is non-null
3. No `run:` actions that call internal framework functions (only plugin's own module)
4. No `push:` to screens outside the plugin's `screens` map
5. Canvas-mode plugins (like DOOM) declare `"canvas_mode": true` and get raw canvas access, but PWR still exits

### Linting Rules

Before a plugin is loaded, the JSON is validated:
- All `id` values are unique
- All `push:<id>` targets exist in the screens map
- All `run:<fn>` targets are in the plugin's own module
- `buttons` is always present
- No `keys.PWR` override (silently stripped if present)
- All `{variable}` placeholders are documented in the plugin's variable declarations
- Icons/resources referenced exist in the plugin directory

---

## Renderer Architecture

```
┌─────────────────────────────────┐
│         Key Interceptor         │ ← PWR always calls finish()
│         (framework level)       │ ← M1/M2 checked against buttons
├─────────────────────────────────┤
│         Screen Renderer         │ ← Reads JSON, draws to Canvas
│  ┌───────────┐ ┌─────────────┐  │
│  │ Title Bar │ │ Battery Icon│  │
│  ├───────────┴─┴─────────────┤  │
│  │                           │  │
│  │     Content Renderer      │  │ ← Dispatches by content.type
│  │  (list/template/progress/ │  │
│  │   text/input/empty)       │  │
│  │                           │  │
│  ├───────────────────────────┤  │
│  │      Button Bar           │  │
│  │  [M1 label]  [M2 label]  │  │
│  └───────────────────────────┘  │
├─────────────────────────────────┤
│     State Machine Engine        │ ← Manages transitions
│     Variable Resolver           │ ← Fills {placeholders}
│     Toast Manager               │ ← Overlay lifecycle
└─────────────────────────────────┘
```

The renderer is ~500 lines. Every screen type is a function that draws to a tkinter Canvas at 240x240. The state machine engine drives transitions based on middleware callbacks. The variable resolver fills placeholders from the result dict.

---

## Migration Path

1. Capture every screen state from original app (Phase 1 — in progress)
2. For each screenshot, write the JSON screen definition
3. Verify: renderer + JSON produces output that matches the original screenshot
4. Replace hardcoded activity UI code with JSON definitions one by one
5. Once all activities are JSON-driven, open the schema for plugins
