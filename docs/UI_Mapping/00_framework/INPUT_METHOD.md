# InputMethods / InputMethodList Widget — Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Class Structure

Two related classes:
- **InputMethods**: Manages a single input field (character cycling, cursor, drawing)
- **InputMethodList**: Manages a list of InputMethods fields (multi-field input, tab navigation)

## InputMethods — Key Functions

| Function | Decompiled Line | Address | Description |
|----------|----------------|---------|-------------|
| `InputMethods.__init__` | 60258 | 0x00060534 | Constructor |
| `InputMethods.show` | 21318 | 0x00035a1c | Show input field |
| `InputMethods.hide` | 21095 | 0x0003565c | Hide input field |
| `InputMethods.setdata` | 50507 | 0x00055884 | Set field data/value |
| `InputMethods.getdata` | 6882 | 0x00025cf4 | Get field data/value |
| `InputMethods.setfocus` | 20724 | 0x0003502c | Set focus on field |
| `InputMethods.unsetfocus` | 20538 | 0x00034d04 | Remove focus |
| `InputMethods.rollfocus` | 20860 | 0x00035270 | Toggle focus state |
| `InputMethods.isfocuing` | 4989 | 0x000239a8 | Check if focused |
| `InputMethods.isshowing` | 5080 | 0x00023b5c | Check if visible |
| `InputMethods.upword` | 22681 | 0x000370bc | Cycle character up |
| `InputMethods.downword` | 22464 | 0x00036d38 | Cycle character down |
| `InputMethods.nextitem` | 22182 | 0x00036888 | Move to next char position |
| `InputMethods.lastitem` | 21912 | 0x0003640c | Move to prev char position |
| `InputMethods.resetselection` | 21776 | 0x000361c8 | Reset character selection |
| `InputMethods.rollshowhide` | 21541 | 0x00035ddc | Toggle visibility |
| `InputMethods._intdraw_word` | 36536 | 0x000462a8 | Draw a single character |
| `InputMethods._intdraw_flush` | 58592 | 0x0005e8f0 | Flush/clear drawn state |
| `InputMethods._intdraw_bg` | STR@0x00079548 | — | Draw background |
| `InputMethods._setstate` | 34038 | 0x00043508 | Internal state management |
| `InputMethods._findnextword` | 7512 | 0x00026784 | Find next valid character |
| `InputMethods._findlastword` | 7120 | 0x000260c8 | Find previous valid character |

## InputMethodList — Key Functions

| Function | Decompiled Line | Address | Description |
|----------|----------------|---------|-------------|
| `InputMethodList.__init__` | 57364 | 0x0005d1a4 | Constructor |
| `InputMethodList.add_method` | 30584 | 0x0003fab8 | Add an input field |
| `InputMethodList.add_method_if_new` | 6603 | 0x0002580c | Add field if not duplicate |
| `InputMethodList.selection` | 56984 | 0x0005cb3c | Select/confirm current value |
| `InputMethodList.next` | 56358 | 0x0005c060 | Move to next field |
| `InputMethodList.prev` | 55791 | 0x0005b6c4 | Move to prev field |
| `InputMethodList.up` | 29478 | 0x0003e830 | Cycle char up in current field |
| `InputMethodList.down` | 29214 | 0x0003e39c | Cycle char down in current field |
| `InputMethodList.left` | 18898 | 0x00033028 | Move cursor left |
| `InputMethodList.right` | 19247 | 0x00033644 | Move cursor right |
| `InputMethodList.update_focus` | 19754 | 0x00033f04 | Update focus state |
| `InputMethodList.focus_exit` | 19596 | 0x00033c60 | Exit focus mode |
| `InputMethodList.has_focus` | 25710 | 0x0003a4e8 | Check if any field focused |
| `InputMethodList.get_all_input_text` | 26140 | 0x0003ac88 | Get all entered text |
| `InputMethodList.get_input_method_count` | 6487 | 0x00025610 | Get field count |
| `InputMethodList.set_input_method_max` | 4666 | 0x00023380 | Set max visible fields |
| `InputMethodList.set_input_method_height` | 4782 | 0x000235b8 | Set field height |
| `InputMethodList._draw_input_method` | 55099 | 0x0005aa64 | Draw a single field |
| `InputMethodList._setup_method_new` | 54355 | 0x00059d84 | Initialize new field |
| `InputMethodList._show_for_position` | 53723 | 0x000591a4 | Show field at position |
| `InputMethodList._show_current_page` | 52630 | 0x00057ee0 | Show current page of fields |
| `InputMethodList._hidden_all_group` | 53287 | 0x000589cc | Hide all field groups |
| `InputMethodList._focus_new_item` | STR@0x00079654 | — | Focus newly created item |
| `InputMethodList._get_focus_method` | 25280 | 0x00039d50 | Get currently focused field |
| `InputMethodList._set_focus_state` | 27432 | 0x0003c374 | Set focus state on field |
| `InputMethodList._act_item_and_selection` | 42732 | 0x0004cce4 | Act on item + selection |
| `InputMethodList._goto_create_mode` | 35839 | 0x00045644 | Enter create/edit mode |

## String References

Key attribute names:
- `_input_method_selection` (STR@0x0007a1d0) — current selection index
- `_input_method_count_max` (STR@0x0007a1e8) — max number of input fields
- `set_input_method_height` (STR@0x0007a128) — field height setter
- `get_input_method_count` (STR@0x0007a200) — field count getter

## Rendering Details

### set_input_method_max

**Function**: `__pyx_pw_6widget_15InputMethodList_5set_input_method_max` @ line 4666, address 0x00023380

Sets the `_input_method_count_max` attribute — controls how many input fields are visible at once on screen.

`[UNRESOLVED FROM DECOMPILATION]` — The actual default max value is stored as a Python int object at a DAT_ address.

### set_input_method_height

**Function**: `__pyx_pw_6widget_15InputMethodList_3set_input_method_height` @ line 4782, address 0x000235b8

Sets the per-field height — controls vertical spacing between input fields.

`[UNRESOLVED FROM DECOMPILATION]` — The actual default height value is stored as a Python int object at a DAT_ address.

### Character Cycling

The input method supports cycling through characters:
- `upword()` / `downword()` — cycle the current character position up/down through valid characters
- `_findnextword()` / `_findlastword()` — find the next/previous valid character in the character set
- Character sets are passed during initialization and stored as internal state

### Cursor Rendering

`[UNRESOLVED FROM DECOMPILATION]` — The cursor rendering is handled within `_intdraw_word` and `_intdraw_bg` functions. These use canvas drawing primitives (fillsquare, showstring) but the exact coordinates are computed from runtime attribute values, not hardcoded constants visible in the Ghidra pseudocode.

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Field max (attribute) | `_input_method_count_max` | STR@0x0007a1e8 |
| Selection (attribute) | `_input_method_selection` | STR@0x0007a1d0 |
| set_input_method_max fn | line 4666 @ 0x00023380 | widget_ghidra_raw.txt |
| set_input_method_height fn | line 4782 @ 0x000235b8 | widget_ghidra_raw.txt |
| _draw_input_method fn | line 55099 @ 0x0005aa64 | widget_ghidra_raw.txt |
| _intdraw_word fn | line 36536 @ 0x000462a8 | widget_ghidra_raw.txt |
| Character cycling | upword/downword | lines 22464/22681 |
| Cursor movement | left/right on InputMethodList | lines 18898/19247 |
| Default height | [UNRESOLVED FROM DECOMPILATION] | DAT_ constants in __init__ |
| Default max fields | [UNRESOLVED FROM DECOMPILATION] | DAT_ constants in __init__ |
