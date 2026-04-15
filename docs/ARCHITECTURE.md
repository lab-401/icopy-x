# Architecture

## Hardware

The iCopy-X is a handheld RFID tag copier built around three main components:

- **Allwinner H3 SoC** (NanoPi NEO) -- runs Linux, Python UI, PM3 client
- **GD32 MCU** -- manages buttons, battery, backlight, LCD handoff, PM3 power
- **Proxmark3 module** -- RFID hardware (125kHz LF + 13.56MHz HF), XC3S100E FPGA
- **240x240 LCD** -- SPI display, initial control by GD32, handed to H3 at boot
- **8 buttons** -- UP, DOWN, LEFT, RIGHT, OK, M1, M2, PWR (active-low, via GD32)

## Software Stack

```
+------------------------------------------------------------+
|  Python 3.8 Application  (src/app.py -> main.main())       |
|                                                             |
|  Activities (UI screens)       Middleware (RFID operations)  |
|  src/lib/activity_*.py         src/middleware/scan.py        |
|  src/lib/actstack.py           src/middleware/read.py        |
|  src/lib/json_renderer.py      src/middleware/write.py       |
|                                src/middleware/executor.py     |
+------------------------------------------------------------+
|  tkinter Canvas (240x240)    PM3 compat layer               |
|  Renders UI to framebuffer   src/middleware/pm3_compat.py    |
+------------------------------------------------------------+
|  HMI Driver (serial)        RemoteTaskManager (TCP:8888)     |
|  src/lib/hmi_driver.py      src/main/rftask.py              |
|  /dev/ttyS0 @ 57600 baud    stdin/stdout to PM3 subprocess   |
+------------------------------------------------------------+
|  GD32 MCU (buttons/battery)  Proxmark3 (/dev/ttyACM0)       |
+------------------------------------------------------------+
```

## Boot Chain

```
app.py -> main.main()
  1. _bootstrap_gd32()     -- send h3start + givemelcd over /dev/ttyS0
  2. gadget_linux setup    -- configure USB gadget (mass storage)
  3. rftask.startManager() -- spawn PM3 subprocess, start TCP server on :8888
  4. hmi_driver.starthmi() -- open serial port, start key event read thread
  5. application.startApp()-- create Tk root (240x240), push MainActivity, mainloop
```

## Activity System

Activities are screen-level UI components managed by a navigation stack.

### Class Hierarchy

```
Activity (actstack.py)
  - Lifecycle: onCreate -> onResume -> onPause -> onDestroy
  - Navigation: finish() pops, start_activity() pushes
  - Thread-safe lifecycle state (LifeCycle class with RLock)

BaseActivity (actbase.py) extends Activity
  - Title bar rendering (setTitle)
  - Button bar rendering (setLeftButton, setRightButton)
  - Busy state management
  - Battery bar integration

Concrete activities (activity_main.py, activity_read.py, etc.)
  - Screen-specific logic and key handling
```

### Navigation Stack

`actstack.py` maintains a module-level stack. `start_activity(cls, bundle)`
pushes a new activity (pausing the current one). `finish()` pops back.
The stack enforces lifecycle ordering: `onCreate -> onResume` on push,
`onPause -> onDestroy` on pop.

### Key Dispatch

```
GD32 button press
  -> /dev/ttyS0 serial line (e.g. "KEYOK_PRES!\r\n")
  -> hmi_driver read thread
  -> keymap.key.onKey(raw_event)
  -> _COMPAT_MAP translates to logical key (UP/DOWN/OK/M1/M2/PWR/ALL)
  -> top activity's callKeyEvent() -> onKeyEvent(key)
```

Keys: UP, DOWN, LEFT, RIGHT, OK, M1, M2, PWR, ALL, SHUTDOWN, APO.
PWR is universal back/exit -- every activity handles it. M1 and M2 are
screen-dependent (typically mapped to left/right soft buttons).

## JSON UI Schema

Screen layouts are defined as JSON files in `src/screens/`. The
`JsonRenderer` reads these definitions and translates them into tkinter
canvas draw calls.

### Screen Definition Structure

```json
{
    "id": "screen_id",
    "initial_state": "state_name",
    "states": {
        "state_name": {
            "screen": {
                "title": "Screen Title",
                "content": { "type": "list|text|progress|time_editor", ... },
                "buttons": { "left": "Back", "right": "OK" },
                "keys": { "OK": "action_string", "M1": "finish" }
            },
            "transitions": {
                "on_result.status==found": "next_state",
                "on_error": "error_state"
            }
        }
    }
}
```

Content types: `list` (scrollable menu/checklist), `text` (static text
lines), `progress` (progress bar with message), `time_editor` (date/time
input fields).

Single-screen activities omit the `states` wrapper and expose `screen`
at the top level.

### Variable Resolution

Screens support `{placeholder}` syntax for dynamic values. The renderer
resolves these from activity state (e.g., `{uid}`, `{tag_family}`,
`{version}`).

## PM3 Compatibility Layer

`src/middleware/pm3_compat.py` translates between two PM3 command formats:

- **Original** (iCopy-X factory): positional arguments, Nikola protocol
- **Iceman** (RRG/Iceman): CLI-flag syntax (`--key`, `-a`, etc.)

The layer auto-detects the PM3 version by checking `hw version` output for
a `NIKOLA:` line (original) vs `Iceman/master/` (RRG).

### Translation Flow

```
Middleware module (e.g., scan.py)
  -> executor.startPM3Task("hf 14a raw ...")   # old-style command
  -> pm3_compat.translate(cmd)                  # rewrites flags
  -> TCP:8888 -> rftask -> PM3 subprocess
  -> PM3 stdout
  -> pm3_compat.translate_response(output)      # normalizes output format
  -> executor caches result
  -> middleware reads via hasKeyword() / getContentFromRegex()
```

### Executor

`src/middleware/executor.py` manages PM3 communication over TCP to the
`RemoteTaskManager` (rftask). Key functions:

- `startPM3Task(cmd, timeout)` -- send command, wait for completion, return 1/-1
- `hasKeyword(pattern)` -- regex search on cached PM3 output
- `getContentFromRegex(pattern)` -- extract capturing group from output
- `getPrintContent()` -- return raw cached output

## RemoteTaskManager

`src/main/rftask.py` runs a TCP server on port 8888 and manages the PM3
subprocess. The Nikola protocol wraps commands:

```
Request:  "Nikola.D.CMD = hf search"
Response: <PM3 stdout lines>
          "Nikola.D: 0"       (return code)
```

The PM3 subprocess runs as `sudo -s proxmark3 /dev/ttyACM0 -w --flush`.
It must use `shell=True` and `stderr=STDOUT` (the process tree is
`python -> sh -> sudo -> pm3`).
