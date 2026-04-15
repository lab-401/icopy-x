# ConsoleView Widget — Rendering Parameters

Source: `/home/qx/icopy-x-reimpl/decompiled/widget_ghidra_raw.txt`

## Status

**ConsoleView is NOT present in widget.so.**

A thorough search of the decompiled widget_ghidra_raw.txt string table (lines 1-641) and all function signatures (549 total functions) reveals NO function or string reference containing "ConsoleView" or "Console".

The widget.so module contains these classes only:
- ListView
- BigTextListView
- CheckedListView
- ProgressBar
- Toast
- InputMethods
- InputMethodList
- BatteryBar
- PageIndicator

ConsoleView may be implemented in a separate module (possibly `hmi.so` or `console.so`) or implemented directly in Python rather than Cython.

## Search Evidence

Grep of widget_ghidra_raw.txt for "Console" returns zero matches in function names or string references. The complete list of widget classes is enumerable from the `__pyx_pw_6widget_` function prefixes:
- `__pyx_pw_6widget_8ListView_*` (ListView methods)
- `__pyx_pw_6widget_15BigTextListView_*` (BigTextListView methods)
- `__pyx_pw_6widget_15CheckedListView_*` (CheckedListView methods)
- `__pyx_pw_6widget_11ProgressBar_*` (ProgressBar methods)
- `__pyx_pw_6widget_5Toast_*` (Toast methods)
- `__pyx_pw_6widget_12InputMethods_*` (InputMethods methods)
- `__pyx_pw_6widget_15InputMethodList_*` (InputMethodList methods)
- `__pyx_pw_6widget_10BatteryBar_*` (BatteryBar methods)
- `__pyx_pw_6widget_13PageIndicator_*` (PageIndicator methods)
- `__pyx_pw_6widget_1createTag` (module-level function)

## Recommendation

To find ConsoleView implementation, search:
1. Other .so modules in `/home/qx/icopy-x-reimpl/orig_so/lib/`
2. Pure Python files in the firmware filesystem
3. The `hmi.so` module which handles display management
