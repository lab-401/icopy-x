# ProgressBar Widget — Pixel-Exact Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Key Functions

| Function | Decompiled Line | Address |
|----------|----------------|---------|
| `ProgressBar.__init__` | 72332 | 0x0006d294 |
| `ProgressBar._draw` | 40390 | 0x0004a3c8 |
| `ProgressBar._intdraw` | 70122 | 0x0006ad04 |
| `ProgressBar.setProgress` | STR@0x0007926c | — |
| `ProgressBar.setMessage` | STR@0x000793a4 | — |
| `ProgressBar.setMax` | 31413 | 0x00040820 |
| `ProgressBar.show` | STR@0x000792cc | — |
| `ProgressBar.hide` | 47380 | 0x000520a8 |
| `ProgressBar.increment` | STR@0x00079578 | — |
| `ProgressBar.decrement` | 36273 | 0x00045e08 |
| `ProgressBar.getProgress` | STR@0x00076fb8 | — |
| `ProgressBar.getMax` | STR@0x00076fe8 | — |
| `ProgressBar._isShowing` | STR@0x00079378 | — |
| `ProgressBar._setState` | STR@0x00079320 | — |

## Constructor Signature

`ProgressBar.__init__(self, canvas, y_offset, height=default, bar_color=default, bg_color=default, msg_color=default)`

**Parameter analysis** (line 72332-72531):
- Takes self + 3 required positional args + 3 optional keyword args
- switch statement at line 72399 shows cases 3 through 6, indicating 3-6 positional args
- Default values for optional args are loaded from DAT_ constants:
  - `local_34 = *(int *)(DAT_0006deec + 0x6d7d4)` — default bar height or color (line 72364)
  - `local_30 = *(int *)(DAT_0006deec + 0x6d7b0)` — default bg color (line 72365)
  - `local_2c = *(int *)(DAT_0006deec + 0x6d650)` — default msg color (line 72367)

The 3 required args are: canvas, y_offset, height (or possibly x_offset). The 3 optional keyword args are bar/bg/msg styling values.

## _draw — Exception-Safe Rendering

**Function**: `__pyx_pw_6widget_11ProgressBar_5_draw` @ line 40390, address 0x0004a3c8

**Signature**: `_draw(self, canvas)`

This is the top-level draw function that wraps `_intdraw` in an exception handler:

1. **Enter rendering context** (lines 40499-40571):
   - Gets the canvas object (line 40501-40505)
   - Looks up `__enter__` method on the canvas (line 40514-40519: `_PyType_Lookup(iVar16, uVar17)`)
   - Looks up `__exit__` method (line 40531-40536)
   - Calls `__enter__()` (line 40552: `__Pyx_PyObject_CallNoArg(piVar4)`)

2. **Exception-safe execution** (lines 40572-40843):
   - Saves exception state via `_PyThreadState_UncheckedGet` (line 40572)
   - Sets the progress value attribute (line 40597-40602: `PyObject_SetAttr(piVar6, ..., iVar7)`)
   - Sets showing state (lines 40604-40610)
   - Calls `__exit__()` (canvas context manager) on success (line 40628: `__Pyx_PyObject_Call_constprop_211(piVar3, ...)`)
   - On exception, calls `__exit__()` with exception info as `PyTuple_Pack(3, exc_type, exc_val, exc_tb)` (line 40673)

## _intdraw — Actual Rendering Logic

**Function**: `__pyx_pw_6widget_11ProgressBar_3_intdraw` @ line 70122, address 0x0006ad04

**Signature**: `_intdraw(self)`

This is where the actual progress bar rendering happens:

1. **Enter canvas context** (lines 70224-70339):
   - Gets canvas object and enters context manager (same pattern as _draw)
   - Sets `_showing = True` attribute (line 70366-70371)
   - Sets another state attribute (line 70483-70485)

2. **Get the canvas drawing surface** (lines 70529-70603):
   - Gets `self._canvas` (line 70529-70533)
   - Gets `canvas.fillsquare` method (line 70544-70548)
   - Gets `self._message` or bar data (line 70565-70569)
   - Calls `fillsquare(message_data)` (line 70580: `__Pyx_PyObject_CallOneArg(local_48, local_4c)`)

3. **Get bar dimensions** (lines 70604-70621):
   - Gets `self._bar_rect` or position (line 70605: `__Pyx_PyObject_GetAttrStr(piVar10, ...)`)
   - Gets item at index [0] (line 70614: `__Pyx_GetItemInt_Fast_constprop_194(local_50, 0, 0)`)
   - This suggests the bar position is stored as a sequence (likely [x, y, width, height] or similar)

## Visual Measurement

**[MEASURED FROM SCREENSHOT: 090-Erase-Types-Erase.png]**: This shows an erase operation with a progress bar:
- The screen shows "Erase Tag" title at top
- "Scanning..." text is displayed in the content area
- A **thin horizontal progress bar** is visible in the upper portion of the content area
- The progress bar appears to be approximately:
  - **Y position**: ~65-70px from top (below title bar, in upper content area)
  - **Width**: ~200px (spanning most of the screen width, with small margins)
  - **Height**: ~6-8px (thin bar)
  - **Bar color**: Blue/dark blue fill
  - **Background**: White/light gray unfilled portion

**[MEASURED FROM SCREENSHOT: 0090.png]** (read_mf1k_4b):
- Shows "Reading..." text in cyan/blue color at bottom
- No visible progress bar in this state — the progress is indicated by text only ("Reading...")
- This suggests ProgressBar is used specifically for operations like Erase, not for all states

## Progress Bar Position and Size

`[UNRESOLVED FROM DECOMPILATION]` — Exact pixel coordinates are stored in DAT_ constants and Python objects that cannot be directly extracted from Ghidra pseudocode. The _intdraw function accesses position data via attribute lookups on self, not via hardcoded constants in the function itself.

Based on screenshot measurement:
- **x**: ~20px from left edge
- **y**: ~65-70px from top
- **width**: ~200px
- **height**: ~6-8px
- **bar_color**: Blue (appears as a solid blue fill)
- **bg_color**: White/light gray (unfilled portion)
- **msg_text_position**: Below the bar, centered

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Bar position y | ~65-70px from top | [MEASURED FROM SCREENSHOT: 090-Erase-Types-Erase.png] |
| Bar width | ~200px | [MEASURED FROM SCREENSHOT: 090-Erase-Types-Erase.png] |
| Bar height | ~6-8px | [MEASURED FROM SCREENSHOT: 090-Erase-Types-Erase.png] |
| Bar color | Blue fill | [MEASURED FROM SCREENSHOT: 090-Erase-Types-Erase.png] |
| Background | White/light gray | [MEASURED FROM SCREENSHOT: 090-Erase-Types-Erase.png] |
| Constructor args | 3 required + 3 optional | line 72332-72531, widget_ghidra_raw.txt |
| __init__ fn | line 72332 @ 0x0006d294 | widget_ghidra_raw.txt |
| _draw fn | line 40390 @ 0x0004a3c8 | widget_ghidra_raw.txt |
| _intdraw fn | line 70122 @ 0x0006ad04 | widget_ghidra_raw.txt |
| setMessage fn | STR@0x000793a4 | widget_ghidra_raw.txt |
| setProgress fn | STR@0x0007926c | widget_ghidra_raw.txt |
| setMax fn | line 31413 @ 0x00040820 | widget_ghidra_raw.txt |
