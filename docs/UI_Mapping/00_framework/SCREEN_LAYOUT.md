# Screen Layout -- BaseActivity Framework

## Source

- **actbase.so decompiled:** `decompiled/actbase_ghidra_raw.txt` (13,389 lines, 72 functions, all decompiled)
- **SUMMARY:** `decompiled/SUMMARY.md` (Section 1: actbase.so - BaseActivity Framework)
- **hmi_driver.so decompiled:** `decompiled/hmi_driver_ghidra_raw.txt` (19,941 lines, 105 functions)
- **batteryui.so decompiled:** `decompiled/batteryui_ghidra_raw.txt`
- **String tables:** `docs/v1090_strings/actbase_strings.txt`, `docs/v1090_strings/hmi_driver_strings.txt`

---

## Screen Zones (240x240 LCD)

The display is a 240x240 pixel LCD, driven over UART at 57600 baud to an STM32 HMI
MCU (`/dev/ttyS0`). The framebuffer format is RGB565 on the real device (`/dev/fb1`).

The BaseActivity framework divides the screen into three zones: title bar, content
area, and button bar. Canvas tags control layer ordering (`tags_title`, `tags_btn_bg`,
`tags_btn_left`, `tags_btn_right`).

### Title Bar

- **Rectangle:** (0, 0) to (240, 40) -- full width, 40 pixels tall
- **Background color:** `#788098` (R=120, G=128, B=152 measured from framebuffer)
  - The SUMMARY says `#222222`, and that string exists in the binary at `STR@0x000200f4`.
    However, pixel measurement from the real device framebuffer capture shows
    `rgb(120, 128, 152)` = `#788098`.
    This discrepancy means `#222222` may be the canvas fill color in tkinter
    (development environment), while the HMI MCU renders with `#788098` on real hardware.
    **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0000.png`]**
  - The `#222222` string is confirmed in the binary at address `0x000200f4`
    **[Source: `actbase_ghidra_raw.txt` line 402]**
- **Text position:** Title text is horizontally centered, vertically centered within
  the 40px bar
  - Text vertical extent: y=10 to y=33 (24 pixels of glyph rendering)
    **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0000.png`]**
  - Text horizontal range for "Read Tag": x=70 to x=169 (title text only, excluding
    battery icon) -- approximately centered around x=120
    **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0084.png`]**
- **Text color:** `white` (string at `STR@0x00020104`)
  - Measured: `rgb(248, 252, 248)` = `#f8fcf8` (near-white, LCD panel color accuracy)
    **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0000.png`]**
- **Font:** `Consolas 18` (string at `STR@0x0001fed4`)
  **[Source: `actbase_ghidra_raw.txt` line 351; SUMMARY.md line 63]**
- **Canvas tag:** `tags_title` (string at `STR@0x0001feec`)
  **[Source: `actbase_ghidra_raw.txt` line 353]**
- **Initialization guard:** `_is_title_inited` (string at `STR@0x0001fd9c`) --
  setTitle checks this flag to avoid duplicate rendering
  **[Source: `actbase_ghidra_raw.txt` line 332; SUMMARY.md line 66]**

#### setTitle method

- **Entry point:** `__pyx_pw_7actbase_12BaseActivity_19setTitle` at `0x0001c73c`
  **[Source: `actbase_ghidra_raw.txt` line 10716]**
- **Signature:** `setTitle(self, title, color=None)`
  **[Source: SUMMARY.md line 60]**
- **Behavior:**
  1. Gets canvas via `self.getCanvas()` (attribute lookup at DAT offset)
  2. Calls `canvas.create_rectangle(...)` with `fill=color` (or default `#222222`)
     and `tags=tags_title`
  3. Calls `canvas.create_text(...)` with the title string, `anchor`, and font
  4. Returns the result of `self._battery_bar` access (final attribute lookup at
     line ~11100)
- **Color parameter:** The `color` kwarg is looked up via `_PyDict_GetItem_KnownHash`
  in the keyword args dict. When not provided, defaults to the global constant
  `#222222` (on desktop) / `#788098` (on HMI hardware).
  **[Source: `actbase_ghidra_raw.txt` lines 10953-10954, PyDict_SetItem call]**

#### Page indicator

- The page indicator (e.g., "1/3") is part of the title string itself. The caller
  formats it as `"Main Page 1/3"` before passing to `setTitle()`.
- In `actmain.so`, `MainActivity.onCreate` uses a `PageIndicator` widget for
  multi-page navigation, and the page string is concatenated into the title text.
  **[Source: SUMMARY.md lines 326-327]**
- There is no separate rendering call within `setTitle` for the page number -- it is
  rendered as part of the single `create_text` call with `Consolas 18`.
- Visual evidence: In the framebuffer capture `0000.png`, the "1/3" text appears
  slightly smaller/lighter than "Main Page", but this is likely font rendering of
  digits vs. letters at the same size, not a separate font size.
  **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0000.png`]**

### Battery Icon

- **Position:** Upper-right corner of the title bar
- **Bounding box:** Approximately x=207 to x=232, y=14 to y=27
  **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0000.png`]**
- **Shape:** Rectangular battery outline with fill level
  - Outer border: x=207-230, y=14-27 (rectangular)
  - Terminal nub: x=229-232, y=19-22 (small protrusion on right side)
  - Fill bars inside the rectangle (visible as solid white blocks)
- **Managed by:** `batteryui.BatteryBar` class (separate module)
  - Instance variable: `_battery_bar` (string at `STR@0x0001fec4`)
    **[Source: `actbase_ghidra_raw.txt` line 350]**
  - Created in `BaseActivity.__init__`: `self._battery_bar = batteryui.BatteryBar()`
    **[Source: SUMMARY.md line 44]**
  - Show/hide lifecycle: `onResume` calls `_battery_bar.show()`, `onPause` calls
    `_battery_bar.hide()`
    **[Source: SUMMARY.md lines 52-53]**
- **batteryui.so module functions:**
  - `register`, `unregister` -- register/unregister battery bar instances
  - `__update_views` -- update all registered battery bars
  - `__run__` -- background update loop
  - `notifyCharging` -- charging state change handler
  - Reads battery via `hmi_driver.readbatpercent()`
  - Variables: `__BATTERY_VALUE`, `__BATTERY_UPDATE`, `__BATTERY_RUN`,
    `__CHARGING_STATE`, `__BATTERY_BAR`
  **[Source: `batteryui_ghidra_raw.txt` string table lines 263-319]**

### Content Area

- **Position:** (0, 40) to (240, 200) -- when button bar is visible
  (0, 40) to (240, 240) -- when button bar is hidden
- **Height:** 160 pixels (with button bar) or 200 pixels (without button bar)
- **Background color:** `#f8fcf8` (near-white)
  **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0000.png`]**
  - Canvas background is set to `white` (`bg='white'`) in `Activity.start()`
    **[Source: SUMMARY.md line 147]**
  - The LCD panel produces `rgb(248, 252, 248)` for pure white
- **Content rendering:** Handled by subclass `onCreate` methods, not by BaseActivity.
  Subclasses use `ListView`, `Toast`, `ProgressBar`, and direct canvas operations.

### Button Bar

- **Rectangle:** (0, 200) to (240, 240) -- full width, 40 pixels tall
  **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0084.png`]**
- **Background color:** `#202020` (R=32, G=32, B=32)
  **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0084.png`]**
  - The binary contains `#222222` at `STR@0x000200f4` -- the measured `#202020` is
    within LCD color quantization tolerance of `#222222` (RGB565 5-bit red channel:
    32 = 0x20 maps to 1 in 5-bit)
- **Canvas tag:** `tags_btn_bg` (referenced in SUMMARY.md line 84)
  **[Source: SUMMARY.md line 84]**
- **Outline:** `#222222` (same as fill)
  **[Source: SUMMARY.md line 86]**
- **Visibility:** The button bar is NOT always visible. It can be:
  1. **Shown** -- via `setLeftButton()` and/or `setRightButton()`, which first call
     `_setupButtonBg()` to create the background rectangle if not already present
  2. **Dismissed** -- via `dismissButton()`, which removes all items tagged
     `tags_btn_left`, `tags_btn_right`, and `tags_btn_bg`
  3. **Disabled** -- via `disableButton()`, which changes button text colors to grey
     using `canvas.itemconfig()`

#### setLeftButton / setRightButton

- **Entry points:**
  - `__pyx_pw_7actbase_12BaseActivity_33setLeftButton` at `0x0001d93c`
    **[Source: `actbase_ghidra_raw.txt` line 11774]**
  - `__pyx_pw_7actbase_12BaseActivity_35setRightButton` at `0x0001e6b4`
    **[Source: `actbase_ghidra_raw.txt` line 12571]**
- **Signature:** `setLeftButton(self, text, color)` / `setRightButton(self, text, color)`
  **[Source: SUMMARY.md lines 68-75]**
- **Behavior (from decompiled code):**
  1. Calls `_setupButtonBg()` to ensure button background exists
     (checked via `_is_button_inited` flag, `STR@0x0001fd74`)
  2. Calls `_getBtnFontAndY()` to get font name and Y position
  3. Calls `canvas.create_text()` with:
     - Text content from parameter
     - Font from `_getBtnFontAndY()` result (first element of returned tuple)
     - Y position from `_getBtnFontAndY()` result (second element)
     - Tag: `tags_btn_left` or `tags_btn_right`
  4. For left button: text is positioned on the left side
  5. For right button: text is positioned on the right side (`btnRight` string
     at `STR@0x0001ffdc`)
- **M1 (left) button:** Position `[UNRESOLVED FROM DECOMPILATION]`
  - From photo captures: left-aligned, approximately x=10-20, vertically centered
    in button bar
    **[MEASURED FROM SCREENSHOT: `v1090_captures/090-Time-Select.png` -- "Cancel" at left,
    `framebuffer_captures/Step - Watch - 1.png` -- "Cancel" at left]**
- **M2 (right) button:** Position `[UNRESOLVED FROM DECOMPILATION]`
  - From photo captures: right-aligned, approximately x=180-230
    **[MEASURED FROM SCREENSHOT: `v1090_captures/090-Time-Select.png` -- "Save" at right]**
- **Font:** `mononoki 16` (string at `STR@0x0001feac`)
  **[Source: `actbase_ghidra_raw.txt` line 348; SUMMARY.md line 89]**
- **Text color:** `color_normal` variable (string at `STR@0x0001fe70`) -- the normal
  button text color. The exact value is `[UNRESOLVED FROM DECOMPILATION]` but
  appears white in screenshots.
  **[Source: `actbase_ghidra_raw.txt` line 345]**

#### _setupButtonBg

- **Entry point:** `__pyx_pw_7actbase_12BaseActivity_31_setupButtonBg` at `0x00017448`
  **[Source: `actbase_ghidra_raw.txt` line 5856]**
- **Behavior:**
  1. Checks `_is_button_inited` flag
  2. If not initialized: calls `canvas.create_rectangle()` with `fill=#222222`,
     `outline=#222222`, and `tags=tags_btn_bg`
  3. Sets `_is_button_inited = True`
  4. If already initialized: skips rectangle creation, returns immediately
- **Rectangle coordinates:** `[UNRESOLVED FROM DECOMPILATION]` -- the exact (x0, y0,
  x1, y1) arguments to `create_rectangle` are passed through DAT-offset indirection
  that cannot be resolved without runtime analysis. From framebuffer measurement:
  (0, 200, 240, 240).
  **[MEASURED FROM SCREENSHOT: `framebuffer_captures/read_mf1k_4b/0084.png`]**

#### _getBtnFontAndY

- **Entry point:** `__pyx_pw_7actbase_12BaseActivity_29_getBtnFontAndY` at `0x00019518`
  **[Source: `actbase_ghidra_raw.txt` line 7853]**
- **Returns:** `(font, y_position)` tuple
  **[Source: SUMMARY.md line 89]**
- **Font:** `mononoki 16` (resolved from string table)
- **Y position calculation (from decompiled code):**
  - Gets `canvas.metrics(font)` to obtain the `linespace` value
    (`linespace` string at `STR@0x0001ff70`)
  - Computes: `y = linespace / 2 + 0xde` where `0xde` = **222** decimal
    **[Source: `actbase_ghidra_raw.txt` lines 8227-8233]**
  - The constant `0xde` (222) appears at multiple points in the function
    (lines 8227, 8233, 8272, 8278)
  - `linespace / 2 + 222` places the button text baseline in the button bar.
    For `mononoki 16` with a typical linespace of ~20px, this gives
    y = 10 + 222 = 232, which is vertically centered in the 200-240 button bar.
  - The division by 2 uses `PyNumber_TrueDivide` (line 8211) or equivalent
    integer ops, and the result is added to the literal constant 222.

#### dismissButton

- **Entry point:** `__pyx_pw_7actbase_12BaseActivity_37dismissButton` at `0x00016a8c`
  **[Source: `actbase_ghidra_raw.txt` line 5262]**
- **Signature:** `dismissButton(self, left=None, right=None, bg=None)`
  - Takes three optional boolean parameters controlling which elements to remove
- **Behavior (from decompiled code):**
  1. Accepts up to 3 keyword args: first controls left button removal, second
     controls right button removal, third controls background removal
  2. For each truthy parameter, calls `canvas.find_withtag(tag)` then
     `canvas.delete(tag)` to remove the items
     (`find_withtag` string at `STR@0x0001fe60`)
  3. Tags used: `tags_btn_left`, `tags_btn_right`, `tags_btn_bg`
  4. Uses `PyDict_SetItem` with `state`/`hidden` to configure items
     (strings at `STR@0x0002011c` and `STR@0x000200ac`)
  5. Final attribute access suggests it also sets `_is_button_inited = False`
  **[Source: `actbase_ghidra_raw.txt` lines 5262-5854]**

#### disableButton

- **Entry point:** `__pyx_pw_7actbase_12BaseActivity_39disableButton` at `0x000185bc`
  **[Source: `actbase_ghidra_raw.txt` line 6939]**
- **Signature:** `disableButton(self, target, *, left_color=None, right_color=None,
  bg_color=None, left_state=None, right_state=None)` (5 keyword args possible from
  switch cases 0-5)
  **[Source: `actbase_ghidra_raw.txt` lines 6982-6998]**
- **Behavior:**
  1. Uses `canvas.itemconfig()` (`itemconfig` string at `STR@0x0001ff10`) to change
     the visual properties of existing button items
  2. Can change the `fill` color of button text (greying out)
  3. Can change `state` to `normal`/`hidden`
  4. The `color_normal` variable (string at `STR@0x0001fe70`) and `#7C829A`
     (string at `STR@0x000200ec`) appear to be the normal and disabled colors
     respectively
  5. `#7C829A` is a grey color (R=124, G=130, B=154) used to visually
     disable/grey-out button text
  **[Source: `actbase_ghidra_raw.txt` lines 6939-7630]**

---

## HMI Rendering Primitives

The HMI driver communicates with the STM32 display controller over UART serial
(`/dev/ttyS0` at 57600 baud). Display commands are dispatched through the
`_content_com` function.

### Serial Port Configuration

- **Port:** `/dev/ttyS0` (`PORT_DEFAULT` string at `STR@0x0002bf68`)
  **[Source: `hmi_driver_ghidra_raw.txt` line 399; SUMMARY.md line 429]**
- **Baud rate:** `57600`
  **[Source: SUMMARY.md line 430]**
- **Protocol:** Custom command/response protocol over UART
  **[Source: SUMMARY.md lines 435-445]**

### Command Names (from string table)

All confirmed in `hmi_driver_ghidra_raw.txt` string table:

| Command | String Address | Description |
|---------|---------------|-------------|
| `fillscreen` | `STR@0x0002c098` | Fill entire 240x240 screen with one color |
| `fillsquare` | `STR@0x0002c08c` | Fill rectangular area with color |
| `showstring` | `STR@0x0002c014` | Display text string at position |
| `showsimbol` | `STR@0x0002c020` | Display symbol/icon at position |
| `showpicture` | `STR@0x0002bf90` | Display image/bitmap at position |
| `givemelcd` | `STR@0x0002c17c` | Request LCD control from STM32 |
| `giveyoulcd` | `STR@0x0002c074` | Release LCD control to STM32 |
| `i'm alive` | `STR@0x0002c170` | Heartbeat/keepalive (HTBT) |
| `startscreen` | `STR@0x0002bf78` | Turn on display |
| `stopscreen` | `STR@0x0002bff0` | Turn off display |
| `setbaklight` | `STR@0x0002bf9c` | Set backlight brightness |

### _content_com dispatcher

- **Entry point:** `__pyx_pw_10hmi_driver_31_content_com` at `0x000295d0`
  **[Source: `hmi_driver_ghidra_raw.txt` line 18304]**
- **Signature:** `_content_com(cmd, data)`
  **[Source: SUMMARY.md line 437]**
- **Behavior (from decompiled code):**
  1. Looks up `cmd` in a command registry (using `PySequence_Contains` at line 18426)
  2. If found: retrieves the command handler tuple via index lookup
     (`__Pyx_PyObject_GetIndex` / `__Pyx_GetItemInt_Fast`)
  3. Calls `data.encode()` (attribute lookup `encode` at line 18461) to convert
     string data to bytes
  4. Gets the format function from the handler tuple (index 1)
  5. Calls the format function with the encoded data
  6. Stores the result in a global dict via `PyDict_SetItem`
  7. If command not found: returns `None` (Py_None increment and return)
  **[Source: `hmi_driver_ghidra_raw.txt` lines 18304-18711]**

### Communication Flow (from SUMMARY)

```
1. _set_com(cmd)         -- Build command packet header
2. _content_com(data)    -- Add content/parameter data
3. _addbaklight(bklt)    -- Append backlight control byte
4. _addend()             -- Append end marker
5. _start_direct()       -- Send command (no response expected)
   OR _start_resp()      -- Send command and wait for response
6. _read_resp_com()      -- Read and parse response
```
**[Source: SUMMARY.md lines 436-444]**

### Response Status Codes

```
"ok"         -> Command succeeded
"ng"         -> Command failed
"para"       -> Parameter response (has data)
"nodata"     -> No data available
"retransmit" -> Retry needed
"key"        -> Key event received
```
**[Source: SUMMARY.md lines 447-453]**

### Command Argument Formats

The exact byte-level encoding of `fillsquare`, `showstring`, and `showsimbol`
arguments could not be resolved from the Ghidra decompilation alone. The command
data passes through `_content_com` which delegates to format functions stored in
a command registry dictionary. The format functions are defined in the module
initialization (`PyInit_hmi_driver`) and their exact byte-packing logic is
interleaved with Cython reference counting boilerplate.

**[UNRESOLVED FROM DECOMPILATION]** -- The exact wire format of each rendering
command (byte order, field widths, color encoding) requires either:
- Runtime interception via strace on the serial port
- Or analysis of the STM32 firmware that receives these commands

Based on the command names and the debug trace format `[comm]-> ` followed by
the command, the protocol appears to be text-based (ASCII command names + encoded
parameters), not purely binary.

---

## Key Constants

All values confirmed from the decompiled binary string table and function analysis:

### Colors

| Constant | Value | Address | Usage |
|----------|-------|---------|-------|
| Title bar bg (desktop) | `#222222` | `STR@0x000200f4` | `canvas.create_rectangle(fill=...)` in setTitle |
| Title bar bg (hardware) | `#788098` | n/a | Measured from real device framebuffer |
| Button bar bg (desktop) | `#222222` | `STR@0x000200f4` | `canvas.create_rectangle(fill=...)` in _setupButtonBg |
| Button bar bg (hardware) | `#202020` | n/a | Measured from real device framebuffer |
| Title text color | `white` | `STR@0x00020104` | setTitle create_text |
| Content area bg | `white` | Activity.start() | Canvas creation |
| Disabled button color | `#7C829A` | `STR@0x000200ec` | disableButton itemconfig |
| Normal button state | `normal` | `STR@0x00020084` | itemconfig state value |
| Hidden state | `hidden` | `STR@0x000200ac` | dismissButton state value |

### Fonts

| Constant | Value | Address | Usage |
|----------|-------|---------|-------|
| Title font | `Consolas 18` | `STR@0x0001fed4` | setTitle create_text |
| Button font | `mononoki 16` | `STR@0x0001feac` | _getBtnFontAndY return |

### Canvas Tags

| Tag | Address | Usage |
|-----|---------|-------|
| `tags_title` | `STR@0x0001feec` | Title bar rectangle + text |
| `tags_btn_left` | `STR@0x0001fdf0` | Left button text |
| `tags_btn_right` | `STR@0x0001fdb0` | Right button text |
| `tags_btn_bg` | (referenced in SUMMARY) | Button bar background rectangle |

### Instance Variables

| Variable | Address | Type | Init Value |
|----------|---------|------|------------|
| `_canvas` | `STR@0x0001ffd4` | Canvas ref | (from widget.getCanvas()) |
| `_is_busy` | `STR@0x00020050` | bool | `False` |
| `_lock_busy` | `STR@0x0001ff64` | Lock | `threading.Lock()` |
| `_is_title_inited` | `STR@0x0001fd9c` | bool | `False` |
| `_is_button_inited` | `STR@0x0001fd74` | bool | `False` |
| `_battery_bar` | `STR@0x0001fec4` | BatteryBar | `batteryui.BatteryBar()` |
| `event_ret` | `STR@0x0001ff88` | any | `False` |
| `resumed` | `STR@0x0002001c` | bool | `False` |

### Numeric Constants

| Constant | Value | Context |
|----------|-------|---------|
| Button Y base | `0xde` (222) | `_getBtnFontAndY`: `y = linespace/2 + 222` |
| Canvas width | 240 | Implied from framebuffer/LCD size |
| Canvas height | 240 | Implied from framebuffer/LCD size |
| Title bar height | 40 | Measured from framebuffer |
| Button bar height | 40 | Measured from framebuffer |
| Content area height | 160 (with btns) / 200 (without) | Derived |
| HMI baud rate | 57600 | `__pyx_int_57600` in hmi_driver |
| HMI serial port | `/dev/ttyS0` | `PORT_DEFAULT` |

---

## Evidence

### Framebuffer captures used for measurement (240x240, RGB, from /dev/fb1)

| File | Content | Measurements extracted |
|------|---------|----------------------|
| `framebuffer_captures/read_mf1k_4b/0000.png` | Main Page 1/3 (title bar, no buttons) | Title bar height=40px, title bg color=#788098, content bg=#f8fcf8, battery icon position x=207-232 y=14-27, title text y=10-33 |
| `framebuffer_captures/read_mf1k_4b/0084.png` | Read Tag result (title bar + empty button bar) | Button bar y=200-239 (40px), button bar bg=#202020, title bar confirmed 40px |

### Photo captures used for visual reference (not 240x240, not pixel-precise)

| File | Content | Observations |
|------|---------|-------------|
| `v1090_captures/090-Time-Select.png` | Time Settings with Cancel/Save buttons | Left button "Cancel" at left edge, right button "Save" at right edge, white text on dark bar |
| `v1090_captures/090-Erase-Types-Erase-Failed.png` | Erase with Erase/Erase buttons | Both button positions visible, title bar with battery icon |
| `framebuffer_captures/Step - 5.png` | Write Tag with Verify/Rewrite buttons | Confirms button text positioning pattern (left-aligned left, right-aligned right) |
| `framebuffer_captures/Step - Watch - 1.png` | Watch 1/3 with Cancel/Start buttons | Confirms button bar layout with dark background |
| `v1090_captures/090-Home-Page3.png` | Main Page 3/3 | Confirms page indicator is part of title string |

---

## Architectural Notes

### Canvas vs HMI rendering

The BaseActivity code uses tkinter Canvas operations (`create_rectangle`,
`create_text`, `find_withtag`, `itemconfig`, `delete`) as its rendering API.
On the development machine (Windows), these render directly to a tkinter window.
On the real device (Linux/ARM), the `widget` module translates these canvas
operations into HMI serial commands (`fillsquare`, `showstring`, etc.) that are
sent to the STM32 MCU over `/dev/ttyS0`.

This explains the color discrepancy: `#222222` is the value passed to
`canvas.create_rectangle(fill='#222222')`, but the STM32 HMI MCU may render it
differently based on its own color mapping or LCD gamma correction.

### Button bar symmetry

The title bar and button bar are both exactly 40 pixels tall, creating a symmetric
frame around the 160-pixel content area. The constant `0xde` (222) in
`_getBtnFontAndY` is `240 - 18 = 222`, where 18 is the font size -- this places
the text baseline at the bottom of the screen minus one font-size unit, then adds
half a linespace to vertically center it.

### Lifecycle integration

The battery bar is tightly coupled to the activity lifecycle:
- `onResume` -> `_battery_bar.show()` (start updating)
- `onPause` -> `_battery_bar.hide()` (stop updating)
- The battery bar runs on a background thread via `ThreadPoolExecutor`
  with `max_workers` parameter, polling `hmi_driver.readbatpercent()`
  **[Source: `batteryui_ghidra_raw.txt` string table]**
