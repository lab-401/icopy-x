# ListView Widget — Pixel-Exact Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Class Hierarchy

```
ListView (base)
  ├── BigTextListView (subclass, overrides drawStr)
  └── CheckedListView (subclass, overrides _updateViews)
```

Defined at:
- `__pyx_pw_6widget_8ListView_1__init__` @ line 77703 (address 0x00073754)
- `__pyx_pw_6widget_15BigTextListView_1__init__` @ line 46681 (address 0x00051440)

## Constructor Signature

`ListView.__init__(self, canvas, y_offset, page_indicator=None)`

- **canvas**: The HMI canvas object (provides fillsquare, showstring, showimage, createTag)
- **y_offset**: Vertical offset from top of display area
- **page_indicator**: Optional PageIndicator instance

Parameters parsed at `__init__` (line 77703-78202). The constructor accepts 3 positional args with 1 optional keyword arg. The switch on `param_2+8` shows cases 0-4 for argument counts.

## Item Height

**Function**: `setItemHeight(self, height)` — line 6175, address 0x00024ff0
- Sets the `_listview_item_height` attribute on the self object (line 6263-6264: `PyObject_SetAttr(piVar5, ..., iVar6)`)
- The height value is passed as a single positional argument (the function expects exactly 2 args: self + height)

**Default value**: `[UNRESOLVED FROM DECOMPILATION]` — The __init__ function at line 77893 sets an attribute via `PyObject_SetAttr(piVar9, DAT_00074448 + 0x73890, DAT_00074448 + 0x73d28)` which is a resolved constant from the data section. The actual numeric value is not directly visible in the Ghidra pseudocode because it is stored as a Python integer object at a DAT_ address.

**[MEASURED FROM SCREENSHOT: 0000.png]**: The display is 240x240 pixels. The title bar occupies approximately 36px at the top. The remaining ~204px contains 5 visible items, giving approximately **40-41px per item**. Measured from `read_mf1k_4b/0000.png` — 5 items ("Auto Copy", "Dump Files", "Scan Tag", "Read Tag", "Sniff TRF") spanning the content area below the title bar.

## Items Per Page (setDisplayItemMax)

**Function**: `setDisplayItemMax(self, max_items)` — line 11574, address 0x0002af24
- Sets `_listview_max_display_item` (STR@0x00079f84) attribute on self
- Also computes and sets a derived max height value: fetches item_height and item_width, adds them, then stores the result as `_listview_max_height` (lines 11683-11746)

**Default value**: `[UNRESOLVED FROM DECOMPILATION]` — set during __init__ at line 77928-77937 via `PyObject_SetAttr(piVar9, DAT_00074454 + 0x73a00, DAT_00074454 + 0x73bec)`. The DAT_ constant references a Python integer object.

**[MEASURED FROM SCREENSHOT: 0000.png and 0050.png]**: Both screenshots show exactly **5 items per page**. The page indicator shows "1/3" (main menu) and "1/8" (Read Tag list), confirming pagination is active with 5 items visible at a time.

## Selection Highlight (setupSelectBG)

**Function**: `setupSelectBG(self, selection_idx, y_start, item_height, color)` — line 16496, address 0x00030728
- Takes 4 positional arguments: self, selection_idx (position in page), y_start (vertical start), item_height, color
- Calls `canvas.fillsquare()` with a tuple of 4 coordinates (x, y, x2, y2) and keyword arguments including `fill` color and `outline` color (lines 16881-16995)
- Coordinates are computed as:
  - x1 = piVar19 (x-start, passed from parent)
  - y1 = y_start + (item_height * selection_idx) — line 16760-16774: `PyNumber_Multiply(iVar18, piVar4)` then `PyNumber_Add(iVar12, piVar5)`
  - x2 = piVar19 + item_width — line 16788-16813: fetches item_width attribute, then `PyNumber_Add(piVar19, piVar5)`
  - y2 = y_start + (item_height * selection_idx) + item_height — line 16834-16865: multiply item_height*selection_idx, add y_start, then add item_height again
- Stores the resulting canvas rectangle as `_listview_select_bg` attribute (line 16988)
- `_listview_is_select_bg_inited` flag (STR@0x00079d24) tracked at line 16654-16693

**Selection color**: The setupSelectBG function creates a dict with `fill` and `outline` keys (lines 16929-16939). The fill and outline values come from resolved DAT_ constants. The actual color values are Python objects at those addresses.

**[MEASURED FROM SCREENSHOT: 0000.png]**: Selection highlight is a **solid dark gray/blue rectangle** spanning the full width of the item. In the screenshot, "Read Tag" (4th item) is highlighted with a darker background. The highlight appears to be approximately RGB(100, 100, 120) — a muted blue-gray.

## Text Drawing (drawStr)

**Function**: `drawStr(self, text, x, y, item_idx, font=None, color=None)` — line 10947, address 0x0002a360
- Takes 5 required args + 1-2 optional keyword args: self, text, x, y, item_idx, font, color
- The text drawing sequence:
  1. Gets and increments an internal counter `_draw_count` (line 11164: `__Pyx_PyInt_AddObjC... +1`)
  2. Gets the canvas (line 11216-11220: `PyObject_GetAttr`)
  3. Gets `canvas.showstring` method (line 11226-11229: attribute lookup on canvas)
  4. Creates a (x, y) tuple for position (line 11240-11260: `PyTuple_New(2)` with item_idx and font coords)
  5. Creates kwargs dict with: text content, font, fill color, anchor (lines 11278-11326)
  6. Calls `canvas.showstring(position_tuple, **kwargs)` (line 11332)
  7. After drawing text, also calls `canvas.showimage` if icons exist (line 11354-11446)

**Text position**: The x,y tuple is created from the function parameters passed by _draw_all_items. Y position is calculated from item_height * item_index + y_offset.

## Drawing All Items (_draw_all_items)

**Function**: `_draw_all_items(self, page)` — line 15933, address 0x0002fce4
- Gets items list and checks its size (lines 16025-16041)
- If size == 0, returns immediately (line 16058-16062)
- Gets `_titles` list and its size (lines 16064-16085)
- Iterates through items on the current page (lines 16086-16466):
  1. Gets `_getStartByPage(page)` for start/end indices
  2. For each item in page range, calls `drawStr(item)` (lines 16363-16393)
- Uses slice notation to get items for current page (line 16283: `PySlice_New(start, end, ...)`)

## Page Mode (setPageModeEnable)

**Function**: `setPageModeEnable(self, enabled)` — line 9128, address 0x00028344

**String reference**: STR@0x00079e6c: `ListView.setPageModeEnable`

When page mode is enabled, the ListView works with a PageIndicator to show page navigation.

## Page Indicator

The PageIndicator is a separate class with its own rendering:
- `PageIndicator.__init__` at line 536 (STR@0x000796c4)
- `PageIndicator._reDrawBottomIndicator` at line 540 (STR@0x000797a4)
- `PageIndicator._reDrawTopIndicator` at line 14030
- `PageIndicator._setupTopIndicator` at line 23126
- `PageIndicator.setTopIndicatorEnable/setBottomIndicatorEnable` for enabling top/bottom arrows
- `PageIndicator._setStatus` for updating page text
- `PageIndicator._get_relative_xy` at line 8765 for positioning

**[MEASURED FROM SCREENSHOT: 0000.png]**: The page indicator appears as **"1/3" text** in the title bar area, right-aligned next to "Main Page". It is NOT arrows — it is numeric text (current_page/total_pages). The font appears to be the same as the title but slightly smaller/lighter.

**[MEASURED FROM SCREENSHOT: 0050.png]**: Shows "1/8" — same pattern. The superscript-like appearance suggests it may be rendered at a smaller font size or with baseline offset.

## Navigation Methods

- `next(self)` — line 40849, address 0x0004ac04: Move selection down, handle page transitions
- `prev(self)` — line 44 (STR@0x00078744): Move selection up, handle page transitions
- `goto_page(self, page)` — STR@0x00077f08: Jump to specific page
- `goto_first_page(self)` — STR@0x000773c4
- `goto_last_page(self)` — STR@0x00077398
- `getSelection(self)` — STR@0x00078354: Returns currently selected item index
- `selection(self)` — STR@0x00078268: Triggers selection action

## _updateViews

**Function**: `_updateViews(self, page=None, force=False)` — line 37744, address 0x00047780
- Accepts self + optional page + optional force flag (3 optional keyword args, lines 37779-37901)
- If items list is empty (size==0), calls a cleanup/reset function (line 38002)
- Sets `_showing` attribute to True (line 38003-38009)
- Calls `_item_clear_reset()` to clear previous draw state (line 38014-38019)
- Calls `_hidden_all_group()` to hide previous canvas elements (line 38046-38054)
- Gets `_draw_all_items` method and calls it (line 38104-38157) — this is the main loop that calls drawStr for each visible item
- After drawing items, calls `setupSelectBG()` to set up selection highlight (within the unpacked tuple handling at lines 38157-38243)

## BigTextListView

**Function**: `BigTextListView.__init__` — line 46681, address 0x00051440
**Function**: `BigTextListView.drawStr` — line 14266, address 0x0002de00

BigTextListView overrides `drawStr` to use a larger font. The selection behavior is at STR@0x00077a20 (`BigTextListView.selection`).

## Summary Table

| Parameter | Value | Source |
|-----------|-------|--------|
| Items per page | 5 | [MEASURED FROM SCREENSHOT: 0000.png, 0050.png] |
| Item height | ~40-41px | [MEASURED FROM SCREENSHOT: 0000.png] (204px / 5 items) |
| Display dimensions | 240x240 | [MEASURED FROM SCREENSHOT: 0000.png] |
| Title bar height | ~36px | [MEASURED FROM SCREENSHOT: 0000.png] |
| Page indicator | Numeric "N/M" text | [MEASURED FROM SCREENSHOT: 0000.png] "1/3" |
| Selection highlight | Full-width dark rectangle | [MEASURED FROM SCREENSHOT: 0000.png] item 4 highlighted |
| Icon position | Left of text | [MEASURED FROM SCREENSHOT: 0000.png] small square icons |
| setItemHeight fn | line 6175 @ 0x00024ff0 | widget_ghidra_raw.txt |
| setDisplayItemMax fn | line 11574 @ 0x0002af24 | widget_ghidra_raw.txt |
| setupSelectBG fn | line 16496 @ 0x00030728 | widget_ghidra_raw.txt |
| drawStr fn | line 10947 @ 0x0002a360 | widget_ghidra_raw.txt |
| _draw_all_items fn | line 15933 @ 0x0002fce4 | widget_ghidra_raw.txt |
| _updateViews fn | line 37744 @ 0x00047780 | widget_ghidra_raw.txt |
