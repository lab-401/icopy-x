# BatteryBar Widget — Pixel-Exact Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Key Functions

| Function | Decompiled Line | Address |
|----------|----------------|---------|
| `BatteryBar.__init__` | 62510 | 0x00062a1c |
| `BatteryBar._draw_init` | 43331 | 0x0004d774 |
| `BatteryBar._draw_internal` | 49375 | 0x0005446c |
| `BatteryBar._set_state` | 17311 | 0x00031594 |
| `BatteryBar.setBattery` | 35303 | 0x00044c90 |
| `BatteryBar.setCharging` | 62010 | 0x00062148 |
| `BatteryBar._charging_run` | STR@0x000797e0 | — |
| `BatteryBar.show` | 22898 | 0x00037440 |
| `BatteryBar.hide` | 8237 | 0x000273fc |
| `BatteryBar.destroy` | 7887 | 0x00026e08 |
| `BatteryBar.isShowing` | 5262 | 0x00023ec4 |
| `BatteryBar.isDestroy` | 5171 | 0x00023d10 |

## Constructor Signature

`BatteryBar.__init__(self, canvas, x, y, width, height, color)`

**Parameter analysis** (line 62510-63009):
- Takes **6 positional arguments** (self + 6): canvas, x, y, width, height, color
- Line 62556: `if (iVar12 != 6)` — expects exactly 6 args (beyond self)
- Switch at line 62577 shows cases 0-6 for positional arg counts
- Positional args extracted at lines 62563-62568:
  - `local_4c = param_2 + 0x18` — arg 4 (width)
  - `local_48 = param_2 + 0x1c` — arg 5 (height)
  - `local_44 = param_2 + 0x20` — arg 6 (color)
  - `piVar3 = param_2 + 0xc` — arg 1 (canvas/self ref)
  - `iVar12 = param_2 + 0x10` — arg 2 (x position)
  - `iVar15 = param_2 + 0x14` — arg 3 (y position)

### Initialization Sequence (lines 62706-63009)

1. **Create canvas rectangle for battery outline** (lines 62706-62784):
   - Looks up a global function (likely `createTag` or `Rectangle`) via `__Pyx__GetModuleGlobalName` (line 62719-62722)
   - Creates a 2-tuple `(canvas, position)` (line 62728: `PyTuple_New(2)`)
   - Sets tuple[0] = self/canvas reference (line 62735-62742)
   - Sets tuple[1] = a constant (line 62743-62750) — likely a position or size constant
   - Calls the constructor function with the tuple (line 62753)
   - Stores result as `self._outline_rect` (line 62766-62771: `PyObject_SetAttr(piVar3, ..., piVar5)`)

2. **Create canvas rectangle for battery fill** (lines 62789-62893):
   - Same pattern: lookup global, create tuple, call constructor
   - Stores result as `self._fill_rect` (line 62889: `PyObject_SetAttr(piVar3, ..., piVar8)`)

3. **Create canvas rectangle for battery nub/tip** (lines 62909-62981):
   - Third rectangle creation with same pattern
   - Stores result as `self._nub_rect` (line 62978: `PyObject_SetAttr(piVar3, ..., piVar5)`)

4. **Store position/size parameters** (lines 62993-63009):
   - Sets `self._x = x` (line 62994: `PyObject_SetAttr(piVar3, ..., iVar12)`)
   - Sets `self._y = y` (line 63004-63005: `PyObject_SetAttr(piVar3, ..., iVar15)`)

The battery bar consists of 3 canvas rectangles: outline, fill level, and the positive terminal nub.

## Visual Measurement

**[MEASURED FROM SCREENSHOT: 0000.png]**: The battery icon is visible in the **top-right corner** of the title bar:
- **Position**: Right-aligned in title bar, approximately x=210, y=5 (relative to screen)
- **Width**: Approximately 22-25px for the main rectangle
- **Height**: Approximately 12-14px
- **Nub**: Small rectangle (~3x6px) extending from the right side of the main rectangle
- **Fill color**: The battery fill appears as a lighter shade inside the outline
- **Outline**: Dark border around the battery shape

**[MEASURED FROM SCREENSHOT: 0050.png]**: Same battery icon position and size, consistent with first screenshot.

**[MEASURED FROM SCREENSHOT: 090-Home-Dump.png]**: Battery icon in same position, appears to show a partially filled state.

## _draw_internal — Battery Fill Rendering

**Function**: `__pyx_pw_6widget_10BatteryBar_5_draw_internal` @ line 49375, address 0x0005446c

This function updates the battery fill level based on the current battery percentage. It adjusts the fill rectangle's width proportionally.

## _set_state — Color Thresholds

**Function**: `__pyx_pw_6widget_10BatteryBar_13_set_state` @ line 17311, address 0x00031594

This function determines the battery color based on charge level. The exact threshold values are stored in DAT_ constants, but the function structure shows it checks multiple conditions to set different colors for different battery levels.

`[UNRESOLVED FROM DECOMPILATION]` — The color threshold percentages (e.g., red < 20%, yellow < 50%, green >= 50%) are stored as Python integer objects at DAT_ addresses and cannot be directly read from Ghidra pseudocode.

## setCharging

**Function**: `__pyx_pw_6widget_10BatteryBar_11setCharging` @ line 62010, address 0x00062148

Sets the charging state. When charging, the `_charging_run` method is likely called periodically to animate the battery fill.

## _charging_run

**Function**: Referenced at STR@0x000797e0

Handles charging animation — likely cycles the battery fill level to show a charging animation.

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Position | Top-right corner of title bar (~x=210, y=5) | [MEASURED FROM SCREENSHOT: 0000.png] |
| Width | ~22-25px (main body) | [MEASURED FROM SCREENSHOT: 0000.png] |
| Height | ~12-14px | [MEASURED FROM SCREENSHOT: 0000.png] |
| Nub size | ~3x6px extending right | [MEASURED FROM SCREENSHOT: 0000.png] |
| Constructor args | 6 (canvas, x, y, width, height, color) | line 62556, widget_ghidra_raw.txt |
| Canvas elements | 3 rectangles (outline, fill, nub) | lines 62706-62981, widget_ghidra_raw.txt |
| Color thresholds | [UNRESOLVED FROM DECOMPILATION] | _set_state @ line 17311 |
| Charging animation | _charging_run method | STR@0x000797e0 |
| __init__ fn | line 62510 @ 0x00062a1c | widget_ghidra_raw.txt |
| _draw_internal fn | line 49375 @ 0x0005446c | widget_ghidra_raw.txt |
| _set_state fn | line 17311 @ 0x00031594 | widget_ghidra_raw.txt |
| setBattery fn | line 35303 @ 0x00044c90 | widget_ghidra_raw.txt |
