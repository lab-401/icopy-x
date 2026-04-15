# PCModeActivity UI Mapping

Source: `decompiled/activity_main_ghidra_raw.txt`, `docs/v1090_strings/activity_main_strings.txt`,
`src/lib/resources.py` StringEN

---

## 1. PCModeActivity Overview

PCModeActivity enables PC-side access to the iCopy-X's Proxmark3 hardware via USB gadget
serial bridge. It sets up the USB serial gadget (`ttyGS0`), runs `socat` to bridge between
the gadget and the PM3 TCP socket, and presents a simple Start/Stop interface.

### 1.1 Exported Method Inventory

Methods extracted from `docs/v1090_strings/activity_main_strings.txt`:

| # | Method Name | String Table Line | Ghidra Symbol |
|---|-------------|-------------------|---------------|
| 1 | `getManifest` | 21117 | `__pyx_pw_13activity_main_14PCModeActivity_1getManifest` (STR@0x000cb8e4) |
| 2 | `__init__` | 21250 | `__pyx_pw_13activity_main_14PCModeActivity_3__init__` (STR@0x000c9c3c) |
| 3 | `onCreate` | 21199 | `__pyx_pw_13activity_main_14PCModeActivity_5onCreate` (line 23980) |
| 4 | `print_warning_on_windows` | 21008 | `__pyx_pw_13activity_main_14PCModeActivity_7print_warning_on_windows` (STR@0x000c99c0) |
| 5 | `wait_for_pm3_online` | 20957 | `__pyx_pw_13activity_main_14PCModeActivity_9wait_for_pm3_online` (line 23955) |
| 6 | `kill_child_processes` | 20959 | `__pyx_pw_13activity_main_14PCModeActivity_11kill_child_processes` (STR@0x000cb85c) |
| 7 | `start_socat` | 21115 | `__pyx_pw_13activity_main_14PCModeActivity_13start_socat` (line 24115) |
| 8 | `stop_socat` | 21145 | `__pyx_pw_13activity_main_14PCModeActivity_15stop_socat` (STR@0x000cc2c8) |
| 9 | `startPCMode` | 21116 | `__pyx_pw_13activity_main_14PCModeActivity_17startPCMode` (line 24073) |
| 10 | `stopPCMode` | 21146 | `__pyx_pw_13activity_main_14PCModeActivity_19stopPCMode` (STR@0x000cc370) |
| 11 | `onKeyEvent` | 21148 | `__pyx_pw_13activity_main_14PCModeActivity_21onKeyEvent` (line 24147) |
| 12 | `showRunningToast` | 21007 | `__pyx_pw_13activity_main_14PCModeActivity_23showRunningToast` (STR@0x000cb81c) |
| 13 | `showButton` | 21147 | `__pyx_pw_13activity_main_14PCModeActivity_25showButton` (STR@0x000cc290) |

Internal closures from onKeyEvent:
- `onKeyEvent.<locals>.run_press` (line 20958, symbol line 23896)
- `onKeyEvent.<locals>.run_finish` (line 20882/22900, symbols lines 23964/23983)

### 1.2 mdef Table (from activity_main_strings.txt:31001-31013)

```
__pyx_mdef_13activity_main_14PCModeActivity_1getManifest
__pyx_mdef_13activity_main_14PCModeActivity_3__init__
__pyx_mdef_13activity_main_14PCModeActivity_5onCreate
__pyx_mdef_13activity_main_14PCModeActivity_7print_warning_on_windows
__pyx_mdef_13activity_main_14PCModeActivity_9wait_for_pm3_online
__pyx_mdef_13activity_main_14PCModeActivity_11kill_child_processes
__pyx_mdef_13activity_main_14PCModeActivity_13start_socat
__pyx_mdef_13activity_main_14PCModeActivity_15stop_socat
__pyx_mdef_13activity_main_14PCModeActivity_17startPCMode
__pyx_mdef_13activity_main_14PCModeActivity_19stopPCMode
__pyx_mdef_13activity_main_14PCModeActivity_21onKeyEvent
__pyx_mdef_13activity_main_14PCModeActivity_23showRunningToast
__pyx_mdef_13activity_main_14PCModeActivity_25showButton
```

Inner closures (from activity_main_strings.txt:31337-31339):
```
__pyx_mdef_13activity_main_14PCModeActivity_10onKeyEvent_1run_press
__pyx_mdef_13activity_main_14PCModeActivity_10onKeyEvent_3run_finish
__pyx_mdef_13activity_main_14PCModeActivity_10onKeyEvent_5run_finish
```

Note: TWO `run_finish` variants (indices 3 and 5) indicate separate code paths for
M1/M2 stop vs PWR stop.

---

## 2. State Machine

PCModeActivity has four states:

```
   +--------+    M1/M2/OK     +-----------+   (background)   +---------+
   |  IDLE  | -------------> | STARTING  | ----------------> | RUNNING |
   +---+----+   (run_press)  | (thread)  |   (success)       +----+----+
       |                      +-----+-----+                        |
       | PWR                        |                              | M1/M2/PWR
       v                            | (failure)                    | (run_finish)
   finish()                         v                              v
                                  IDLE                        +-----------+
                                                              | STOPPING  |
                                                              | (thread)  |
                                                              +-----+-----+
                                                                    |
                                                                    v
                                                                finish()
```

### 2.1 STATE: IDLE

**Screen layout**:
- Title: `"PC-Mode"` (resources.py:78, title key `'pc-mode'`)
- Content: BigTextListView showing connection instructions
  - Text: `"Please connect to\nthe computer.Then\npress start button"`
    (resources.py:151, tipsmsg key `'connect_computer'`)
- M1: `"Start"` (resources.py:37, button key `'start'`)
- M2: `"Start"` (resources.py:37, button key `'start'`)

**Key behavior**:
- M1/M2/OK: transition to STARTING, launch `run_press` background thread
- PWR: `finish()` (exit to main menu)

### 2.2 STATE: STARTING (background thread active)

**Screen layout**:
- Title: `"PC-Mode"`
- Content: unchanged (connection instructions)
- Toast: `"Processing..."` (resources.py:108, toastmsg key `'processing'`)
- M1: disabled
- M2: disabled

**Key behavior**: ALL keys ignored (background thread busy)

**Background thread (`run_press`)** (activity_main_strings.txt:20958):
1. `gadget_linux.upan_and_serial()` -- sets up USB mass storage + serial gadget
2. `start_socat()` -- bridges ttyGS0 to PM3 via socat
3. `wait_for_pm3_online()` -- polls until PM3 responds
4. `hmi_driver.presspm3()` -- presses PM3 power button
5. `executor.startPM3Ctrl()` -- starts PM3 control channel
6. On success: transition to RUNNING
   - `showRunningToast()` -- shows "PC-mode Running..."
   - `audio.playPCModeRunning()` -- plays audio notification
   - `showButton()` -- updates button labels
7. On failure: transition back to IDLE, showButton()

### 2.3 STATE: RUNNING

**Screen layout**:
- Title: `"PC-Mode"`
- Content: unchanged
- Toast: `"PC-mode Running..."` (resources.py:103, toastmsg key `'pcmode_running'`)
- M1: `"Stop"` (resources.py:36, button key `'stop'`)
- M2: `"Button"` (resources.py:33, button key `'button'`)

**Key behavior**:
- M1/M2: transition to STOPPING, launch `run_finish` background thread
- PWR: transition to STOPPING, launch `run_finish` background thread

### 2.4 STATE: STOPPING (background thread active)

**Screen layout**:
- Title: `"PC-Mode"`
- M1: disabled
- M2: disabled

**Key behavior**: ALL keys ignored (background thread busy)

**Background thread (`run_finish`)** (activity_main_strings.txt:20882/22900):
1. `stopPCMode()`:
   a. `stop_socat()` -- kill socat process
   b. `kill_child_processes()` -- kill all child PIDs
   c. `gadget_linux.kill_all_module()` -- tear down USB gadget
   d. `hmi_driver.restartpm3()` -- restart PM3
   e. `executor.reworkPM3All()` -- reinitialize PM3 connection
2. `finish()` -- exit activity

---

## 3. socat Bridge Details

### 3.1 start_socat (decompiled at ghidra_raw.txt, symbol line 24115)

Builds and executes the socat command to bridge the USB serial gadget to PM3.

From string table:
- `"sudo socat "` (activity_main_strings.txt:21886)
- `"ttyGS0"` (activity_main_strings.txt:22363) -- USB gadget serial device
- `"ttyACM0"` (activity_main_strings.txt:22277) -- USB ACM device (PC-side reference)

Internal attribute: `process_socat` (activity_main_strings.txt:21634/25279)

The exact socat command bridges `/dev/ttyGS0` (the USB gadget serial port exposed to the
connected PC) to the PM3 TCP socket on localhost.

### 3.2 stop_socat (decompiled at ghidra_raw.txt, STR@0x000cc2c8)

Kills the socat process by sending SIGKILL to the stored PID.

### 3.3 kill_child_processes (decompiled at ghidra_raw.txt:46446-47132)

Large function (~686 lines). Enumerates and kills all child processes spawned during
PC mode operation. Uses psutil-style process tree walking.

---

## 4. showRunningToast (decompiled at ghidra_raw.txt:46128-46444)

Flow (from decompiled code):
1. Gets the canvas/toast object from `self` attributes
2. Looks up `resources.get_str('pcmode_running')` = `"PC-mode Running..."`
3. Calls toast.show() with the message
4. Looks up audio module and calls `playPCModeRunning`

The decompiled function shows two sequential lookups:
- First: `resources.get_str` for the toast message string
- Second: `audio` module for `playPCModeRunning`

Both lookups use the standard Cython `__Pyx__GetModuleGlobalName` pattern.

---

## 5. showButton (string table line 21147, STR@0x000cc290)

Updates M1/M2 button labels based on current state:

| State | M1 Button | M2 Button |
|-------|-----------|-----------|
| IDLE | `"Start"` (resources `'start'`) | `"Start"` (resources `'start'`) |
| RUNNING | `"Stop"` (resources `'stop'`) | `"Button"` (resources `'button'`) |
| STARTING | disabled | disabled |
| STOPPING | disabled | disabled |

---

## 6. print_warning_on_windows (decompiled at ghidra_raw.txt:6834-7169)

Shows a warning about Windows USB serial gadget driver requirements.
Non-blocking informational display. This function is likely called during
`wait_for_pm3_online` when detecting a Windows host.

---

## 7. External Module Dependencies

### 7.1 gadget_linux (activity_main_strings.txt:21746)

- `upan_and_serial()` (line 21469): Sets up USB mass storage + serial gadget
- `kill_all_module()` (line 21500): Tears down all USB gadget modules

### 7.2 hmi_driver

- `presspm3()` (line 22200): Presses PM3 power button to wake it
- `restartpm3()` (line 21917): Restarts PM3 hardware

### 7.3 executor

- `startPM3Ctrl()` (line 21706): Starts PM3 control/command channel
- `reworkPM3All()` (line 21716): Reinitializes all PM3 connections
- `stopPM3Task()`: Stops any running PM3 task

### 7.4 audio

- `playPCModeRunning` (line 21382): Plays audio notification when PC mode starts

### 7.5 subprocess

- Used by `start_socat()` to spawn the socat process

---

## 8. WarningM1Activity Integration

From string table (activity_main_strings.txt:21057/22817):
- `WarningM1Activity.gotoPCMode` -- WarningM1Activity can navigate to PCModeActivity

This means the "Enter PC Mode" option may appear in WarningM1Activity (the missing keys
warning flow for M1-class cards), giving users an alternative path to reach PC mode
for advanced operations like Hardnested attacks.

---

## 9. String Resources Summary

### Title strings (resources.py StringEN.title):
- `'pc-mode'` -> `"PC-Mode"` (line 78)

### Button strings (resources.py StringEN.button):
- `'start'` -> `"Start"` (line 37)
- `'stop'` -> `"Stop"` (line 36)
- `'button'` -> `"Button"` (line 33)
- `'pc-m'` -> `"PC-M"` (line 48 -- abbreviation used on main menu)

### Toast strings (resources.py StringEN.toastmsg):
- `'pcmode_running'` -> `"PC-mode Running..."` (line 103)
- `'processing'` -> `"Processing..."` (line 108)

### Tips strings (resources.py StringEN.tipsmsg):
- `'connect_computer'` -> `"Please connect to\nthe computer.Then\npress start button"` (line 151)

### Internal string table (activity_main_strings.txt):
- `PCModeActivity` (line 21595/25240)
- `process_socat` (line 21634) -- socat process handle attribute
- `kill_child_processes` (line 21269) -- child PID cleanup method
- `stop_pcmode` (line 21800) -- internal state attribute
- `start_socat` / `stop_socat` (lines 21802/21888)
- `startPCMode` / `stopPCMode` (lines 21804/21889)
- `sudo socat ` (line 21886) -- socat command prefix
- `ttyGS0` (line 22363) -- USB gadget serial device
- `ttyACM0` (line 22277) -- USB ACM device
- `gadget_linux` (line 21746) -- external module
- `upan_and_serial` (line 21469) -- gadget setup function
- `kill_all_module` (line 21500) -- gadget teardown function
- `presspm3` / `restartpm3` (lines 22200/21917) -- HMI driver functions
- `startPM3Ctrl` / `reworkPM3All` (lines 21706/21716) -- executor functions
- `playPCModeRunning` (line 21382) -- audio function
- `text_connect_computer` (line 21237) -- resource lookup key
- `text_pcmode_running` (line 21293) -- resource lookup key
- `pc-mode` (line 22300) -- resource key for title

---

## 10. Decompiled Function Cross-Reference

| Function | Start Line | End Line | Address |
|----------|-----------|----------|---------|
| `print_warning_on_windows` | 6834 | 7169 | 0x00032660 |
| `__init__` | 8519 | 8798 | 0x000344f8 |
| `showRunningToast` | 46128 | 46444 | 0x0005e8f4 |
| `kill_child_processes` | 46446 | 47132 | 0x0005ee78 |
| `getManifest` | 47134 | 47454 | 0x0005fb98 |

Note: `onCreate`, `onKeyEvent`, `startPCMode`, `stopPCMode`, `start_socat`, `stop_socat`,
`wait_for_pm3_online`, and `showButton` are referenced in the string table but their
decompiled bodies are in sections of the file not explicitly marked with `===FUNC` headers
(they may be at addresses covered by other function blocks or in the module init section).

Their symbols are confirmed at:
- `onCreate` -> line 23980 (`__pyx_pw_13activity_main_14PCModeActivity_5onCreate`)
- `onKeyEvent` -> line 24147 (`__pyx_pw_13activity_main_14PCModeActivity_21onKeyEvent`)
- `startPCMode` -> line 24073 (`__pyx_pw_13activity_main_14PCModeActivity_17startPCMode`)
- `stopPCMode` -> line 24039 (`__pyx_pw_13activity_main_14PCModeActivity_19stopPCMode`)
- `start_socat` -> line 24115 (`__pyx_pw_13activity_main_14PCModeActivity_13start_socat`)
- `stop_socat` -> STR@0x000cc2c8 (`__pyx_pw_13activity_main_14PCModeActivity_15stop_socat`)
- `wait_for_pm3_online` -> line 23955 (`__pyx_pw_13activity_main_14PCModeActivity_9wait_for_pm3_online`)
- `showButton` -> STR@0x000cc290 (`__pyx_pw_13activity_main_14PCModeActivity_25showButton`)

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | Verified: IDLE state M1="Start" M2="Start" (both same label) is CORRECT as documented. No change needed. | `pc_mode.png` |

---

## Key Bindings

### PCModeActivity.onKeyEvent (activity_main_ghidra_raw.txt line 24147)

Four states: IDLE, STARTING, RUNNING, STOPPING.

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | _run_press() | _run_press() | _run_press() | finish() |
| STARTING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | no-op |
| RUNNING | no-op | no-op | no-op | no-op | no-op | _run_finish() | _run_finish() | _run_finish() |
| STOPPING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | no-op |

**Notes:**
- IDLE: All action keys (M1/M2/OK) start PC mode. PWR exits.
- STARTING: All keys blocked (background thread initializing gadget + socat + PM3).
- RUNNING: M1/M2 stop PC mode. PWR also stops then finishes. OK has no action.
- STOPPING: All keys blocked (background thread cleaning up).
- Button labels: IDLE = "Start"/"Start", RUNNING = "Stop"/"Button".

**Source:** `src/lib/activity_main.py` lines 1402-1424.
