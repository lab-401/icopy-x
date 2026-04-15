# Toast Widget — Pixel-Exact Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Key Functions

| Function | Decompiled Line | Address |
|----------|----------------|---------|
| `Toast.__init__` | STR@0x00079224 | — |
| `Toast.show` | 63319 | 0x00063960 |
| `Toast._showMask` | 65326 | 0x00065690 |
| `Toast.cancel` | 48261 | 0x000530f4 |
| `Toast.isShow` | 5353 | 0x00024078 |

**String reference**: STR@0x00079bb8: `Exception on widget.Toast.cancel(): ` — shows there is exception handling around cancel.

## Toast.show — Main Show Function

**Function**: `__pyx_pw_6widget_5Toast_5show` @ line 63319, address 0x00063960

**Signature**: `Toast.show(self, canvas, text, icon_type=None, duration=None, dismiss_code=None)`

Parameter analysis (lines 63319-63818):
- Reads `self._dismiss_code` from `param_1 + 0x3c` (line 63360: `local_2c = (int *)**(int **)(param_1 + 0x3c)`)
- Takes self + 2 required args + up to 3 optional keyword args
- Switch on arg count shows cases 2 through 5 (lines 63371-63388)
- piVar6 = default for icon_type (None), piVar8 = default for duration

### Rendering Sequence

1. **Get canvas.createTag** (lines 63442-63447):
   - Gets `createTag` method from canvas via `PyObject_GetAttr(piVar5, ...)`

2. **Create mask group tag** (lines 63461-63527):
   - Creates a new dict with a single `state` key set to a value (likely "normal") — line 63483: `PyDict_SetItem(local_4c, ..., piVar9)`
   - Calls `canvas.createTag(state=...)` — line 63497: `__Pyx_PyObject_Call(local_50, args, local_4c)`

3. **Get canvas.fillsquare** (lines 63528-63533):
   - Gets `fillsquare` method for drawing the overlay rectangle

4. **Create overlay rectangle** (lines 63546-63603):
   - Creates a 2-element position tuple with (duration_or_position, dismiss_code) — lines 63559-63572
   - Calls `canvas.fillsquare(position_tuple)` — line 63573

5. **Determine toast height** (lines 63599-63604):
   - If `local_5c == piVar6` (icon_type is None/default): uses height `0x78` = **120 decimal**
   - Else: uses height `0x84` = **132 decimal**
   - This is the key finding: **Toast height is 120px without icon, 132px with icon**

6. **Get canvas font/size calculation** (lines 63606-63618):
   - Gets another canvas attribute (likely `getfont` or size method)
   - Gets font size attribute from that object

7. **Create font size tuple** (lines 63638-63678):
   - Creates `PyLong_FromLong(uVar13)` where uVar13 is either 0x78 (120) or 0x84 (132)
   - Creates a 2-tuple of (size_value, constant)

8. **Create draw kwargs** (lines 63679-63795):
   - Creates a dict with multiple drawing parameters
   - Sets text content key (line 63691: `PyDict_SetItem`)
   - Sets font/style key (line 63702)
   - Sets fill color key (line 63714)
   - Sets another style key (line 63726)
   - Gets and sets anchor/alignment (lines 63738-63752)
   - Sets border/outline (lines 63772-63785)

9. **Execute the drawing** (lines 63796-63818):
   - Calls the canvas drawing method with the position tuple and kwargs dict

## Toast._showMask — Overlay Rectangle

**Function**: `__pyx_pw_6widget_5Toast_3_showMask` @ line 65326, address 0x00065690

**Signature**: `_showMask(self, canvas, mask_rect=None, dismiss_code=None)`

- Takes 2 required + 1 optional args (lines 65359-65478)
- Reads `self._dismiss_code` from `param_1 + 0x3c` (line 65356)

### Rendering Logic

1. **Get canvas drawing method** (lines 65481-65493):
   - Gets method via `PyObject_GetAttr(iVar7, ...)` on the canvas arg
   - Gets sub-method for rectangle fill (line 65492-65496)

2. **Get mask position** (lines 65510-65527):
   - Gets another canvas attribute for positioning
   - Calls `CallOneArg(piVar2, piVar1)` to compute mask rectangle

3. **Check visibility conditions** (lines 65554-65571):
   - Checks against True/False/None constants (piVar1, piVar10, piVar13)
   - These are the Python singletons for boolean comparisons

4. **When mask IS needed (uVar4 != 0)** — draw filled overlay (lines 65732-65729):
   - Checks size of piVar3 (the mask content)
   - If size < 1 (empty mask): just returns the position reference

5. **Toast dismiss comparison** (lines 65741-65825):
   - Compares `dismiss_code` against two thresholds:
     - First comparison at line 65746: `PyObject_RichCompare(iVar17, piVar18, 2)` — equality check
     - If equal to first threshold: uses height `0xf0` = **240 decimal** (full screen)
     - If equal to second threshold: uses height `0xc8` = **200 decimal**
   - Then: `uVar14 = 0xf0` or `uVar14 = 200` (lines 65781-65783)
   - These represent **toast overlay heights**: 240px (full screen) or 200px

6. **Draw the mask rectangle** (lines 65639-65713):
   - Gets `canvas.fillsquare` (line 65588-65592)
   - Gets canvas position/layout method (line 65639-65644)
   - Creates a 1-element tuple (line 65655-65672)
   - Creates kwargs dict with `fill` color (line 65682-65683): `PyDict_SetItem(piVar1, ..., ...)`
   - Calls `canvas.fillsquare(position, fill=color)` (line 65689)

## Toast.cancel

**Function**: `__pyx_pw_6widget_5Toast_7cancel` @ line 48261, address 0x000530f4

- Cancels/dismisses the toast
- Exception string "Exception on widget.Toast.cancel(): " at STR@0x00079bb8 shows this has try/except handling
- The cancel method uses `TOAST_CANCEL` (canvas mask deletion), NOT the PWR key (per project memory reference_toast_dismiss.md)

## Visual Measurement

**[MEASURED FROM SCREENSHOT: Step - 5.png]**: Shows a toast overlay on the Write Tag screen:
- The toast displays "Write failed!" with an X icon on the left
- **Toast background**: White/light semi-transparent rectangle
- **Toast text**: Black text, centered
- **Toast icon**: X symbol (error/failure) on the left side of the text
- **Toast position**: Centered vertically on screen, overlaying the content
- **Toast width**: Nearly full screen width (~200px), with small horizontal margins
- **Toast height**: Approximately 40-50px (the visible text area)
- **Toast overlay**: The background behind the toast appears slightly dimmed/masked

## Toast Modes

Based on the decompiled code analysis:

1. **Standard toast** (height 120px / 0x78): No icon, text-only message
2. **Icon toast** (height 132px / 0x84): With icon (success checkmark or failure X)
3. **Full-screen mask** (height 240px / 0xf0): Full screen overlay
4. **Partial mask** (height 200px / 0xc8): Partial overlay (leaves title bar visible)

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Toast height (no icon) | 120px (0x78) | line 63600, widget_ghidra_raw.txt |
| Toast height (with icon) | 132px (0x84) | line 63603, widget_ghidra_raw.txt |
| Mask height (full) | 240px (0xf0) | line 65781, widget_ghidra_raw.txt |
| Mask height (partial) | 200px (0xc8) | line 65783, widget_ghidra_raw.txt |
| Toast appearance | White bg, black text, icon left | [MEASURED FROM SCREENSHOT: Step - 5.png] |
| Cancel mechanism | Canvas mask deletion (TOAST_CANCEL) | STR@0x00079bb8 + project reference |
| show fn | line 63319 @ 0x00063960 | widget_ghidra_raw.txt |
| _showMask fn | line 65326 @ 0x00065690 | widget_ghidra_raw.txt |
| cancel fn | line 48261 @ 0x000530f4 | widget_ghidra_raw.txt |
