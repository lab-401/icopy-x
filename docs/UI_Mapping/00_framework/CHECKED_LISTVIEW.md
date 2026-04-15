# CheckedListView Widget — Pixel-Exact Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Class Hierarchy

```
ListView
  └── CheckedListView (subclass)
```

CheckedListView extends ListView and overrides `_updateViews` to add check mark indicators.

## Key Functions

| Function | Decompiled Line | Address |
|----------|----------------|---------|
| `CheckedListView.__init__` | 57951 | 0x0005dcc0 |
| `CheckedListView._updateViews` | 75162 | 0x0007091c |
| `CheckedListView.auto_show_chk` | 20025 (STR@0x00077bfc) | — |
| `CheckedListView.check` | line ref STR@0x0007848c | — |
| `CheckedListView.getCheckPosition` | line ref STR@0x00076e70 | — |

## _updateViews — The Full Redraw

**Function**: `__pyx_pw_6widget_15CheckedListView_3_updateViews` @ line 75162, address 0x0007091c

**Signature**: `_updateViews(self, page=None, force=False)`

The function accepts self + 2 optional keyword args (lines 75200-75331). Parameter parsing matches the parent ListView pattern.

### Rendering Sequence (lines 75332-75661)

1. **Get the parent class's `_updateViews` method** (line 75333-75346):
   - Reads `self.__class__.__mro__` from `param_1 + 0x38` (piVar19)
   - If null, raises SystemError (line 75336-75338)
   - Increments reference count and creates a 2-element tuple (line 75347-75374)
   - Calls `super()._updateViews(page, force)` via the MRO chain (lines 75376-75378: `PyObject_Call(mro_method, tuple, 0)`)

2. **After parent _updateViews completes** (line 75380-75468):
   - Gets the result from super().__updateViews
   - Gets `self._items` via `PyObject_GetAttr` (line 75387-75390)
   - Creates a new 2-tuple with (page, force) args for the check drawing call (lines 75409-75435)
   - Calls an internal method to draw check indicators (lines 75437-75453)

3. **Get check items data** (lines 75469-75501):
   - Gets `self._items` attribute (line 75469-75473: `PyObject_GetAttr(piVar20, ...)`)
   - Gets item at index [1] via `__Pyx_GetItemInt_Fast_constprop_194(piVar17, 1, 0)` (line 75487)
   - This suggests items are stored as (title, check_state) tuples

4. **Get the canvas for drawing** (lines 75502-75531):
   - Gets `self._canvas` (line 75502-75506: `PyObject_GetAttr(piVar20, ...)`)
   - Gets `canvas.fillsquare` method from the canvas (line 75517-75521)
   - Gets `self._check_positions` or similar (line 75532-75536)
   - Calls `canvas.fillsquare(...)` with the check position via `__Pyx_PyObject_CallOneArg(piVar19, piVar17)` (line 75549)

5. **Get checked state and render** (lines 75576-75661):
   - Gets `self._check_items` (line 75576-75580: `PyObject_GetAttr(piVar20, ...)`)
   - Calls `_item_clear_reset()` equivalent (line 75591: `__Pyx_PyObject_CallNoArg(piVar1)`)
   - Gets `self._check_label` or similar attribute (line 75598-75602)
   - Calls `canvas.showstring(...)` to draw check indicator text (line 75611-75619: `__Pyx_PyObject_CallOneArg(piVar17, piVar4)`)
   - Then calls `int(result)` to get numeric check position (line 75618-75619: `__Pyx_PyObject_CallOneArg(int_func, piVar1)`)
   - Iterates over check states (lines 75634-75661): determines if using list or tuple iteration

## Check Indicator Rendering

Based on the decompiled _updateViews and confirmed by real-device screenshots:

**Check shape**: Two-part rendering on the RIGHT side of each item row:
- **Unchecked items:** grey-stroked square outline (border only, no fill) on the RIGHT side of the item row
- **Checked/selected item:** blue-stroked square outline with inner blue-filled square on the RIGHT side of the item row

This is likely two `fillsquare` HMI calls: one for the border stroke, one for the inner fill. The code at line 75549 calls `canvas.fillsquare(...)` with position data, confirming the `fillsquare` rendering method.

**Check position**: The function `getCheckPosition` (STR@0x00076e70) returns the position. The _updateViews reads position data from the item's attributes at index [1] (line 75487), suggesting the check state is stored as the second element of each item tuple.

**Check color**: Confirmed from screenshots:
- Unchecked border: grey stroke
- Checked border: blue stroke
- Checked fill: blue fill (inner square)

**Citation:** `backlight_1.png` and `volume_1.png` show the two-part check indicator rendering. All unchecked items show grey square outlines; the checked item shows a blue square outline with blue inner fill.

## auto_show_chk

**Function**: `auto_show_chk(self)` — STR@0x00077bfc (line 386), STR@0x00079ce4
- Toggles the check mark state for the currently selected item
- Called when the user presses the OK/selection key on a CheckedListView item

## check

**Function**: `check(self, index)` — STR@0x0007848c
- Sets the check state for a specific item by index

## Visual Measurement

**Now resolved from real-device screenshots.** The CheckedListView is used for settings screens (Backlight, Volume).

Based on the code analysis and screenshot evidence (`backlight_1.png` through `backlight_5.png`, `volume_1.png` through `volume_6.png`):
- CheckedListView inherits all ListView rendering (5 items per page, same item height, same selection highlight)
- It adds a check indicator element per item, drawn via `canvas.fillsquare()` on the RIGHT side
- Unchecked: grey-stroked square outline (border only)
- Checked: blue-stroked square outline + inner blue-filled square (two fillsquare calls)
- The check is positioned based on `getCheckPosition()` return value

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Inherits from | ListView | decompiled class structure |
| Check drawing method | canvas.fillsquare() | line 75549, widget_ghidra_raw.txt |
| Check shape | Unchecked: grey-stroked square outline. Checked: blue-stroked square outline + inner blue fill. | `backlight_1.png`, `volume_1.png` |
| Check position source | getCheckPosition() | STR@0x00076e70 |
| Check state storage | Item tuple index [1] | line 75487, __Pyx_GetItemInt_Fast index=1 |
| Items per page | 5 (inherited) | Inherited from ListView |
| __init__ fn | line 57951 @ 0x0005dcc0 | widget_ghidra_raw.txt |
| _updateViews fn | line 75162 @ 0x0007091c | widget_ghidra_raw.txt |
| auto_show_chk fn | STR@0x00077bfc | widget_ghidra_raw.txt |

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | Replaced generic "filled square" / "[UNRESOLVED]" check indicator description with precise two-part rendering: unchecked = grey-stroked square outline on RIGHT side; checked = blue-stroked square outline + inner blue-filled square on RIGHT side. Resolved Visual Measurement section from "[UNRESOLVED]" status. | `backlight_1.png`, `volume_1.png` |
