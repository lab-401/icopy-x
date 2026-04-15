# AboutActivity — Exhaustive UI Mapping

Source: `activity_main.so` decompiled via Ghidra (`activity_main_ghidra_raw.txt`)
String table: `resources.py` StringEN
Binary strings: `docs/v1090_strings/activity_main_strings.txt`

---

## 1. Activity Identity

### Module Location

Binary: `orig_so/lib/activity_main.so`
Decompiled: `decompiled/activity_main_ghidra_raw.txt`

### Class Methods (from binary string table and decompiled symbols)

```
AboutActivity.__init__              @0x0005dd7c  (activity_main_ghidra_raw.txt:45487)
AboutActivity.getManifest           @0x0005e37c  (activity_main_ghidra_raw.txt:45808)
AboutActivity.onCreate              @0x0005b5d8  (activity_main_ghidra_raw.txt:43292)
AboutActivity.onKeyEvent            @0x0005a368  (activity_main_ghidra_raw.txt:42201)
AboutActivity.onResume              @0x0003ae88  (activity_main_ghidra_raw.txt:14417)
AboutActivity.getKernel             @0x0005da08  (activity_main_ghidra_raw.txt:45288)
AboutActivity.checkUpdate                       (activity_main_strings.txt:21154)
AboutActivity.showErr                            (activity_main_strings.txt:21255)
AboutActivity.init_info                          (activity_main_strings.txt:21204)
AboutActivity.start_init_data_to_view            (activity_main_strings.txt:20991)
```

---

## 2. State Machine

### STATE: INFO_DISPLAY (Initial and primary — page 1 of 2)

- **Title**: "About 1/2" (resources.py StringEN.title.about, line 7, with page indicator appended)
- **View type**: ListView (read-only display list, no selection)
- **Pages**: 2 pages minimum. Title shows "About N/M" with page indicator.
- **Items** (page 1): 6 lines showing device identity and firmware/hardware version info
- **Item format** (resources.py StringEN.itemmsg, line 11):

| Index | Resource Key | Format String | Real-Device Example |
|-------|-------------|--------------|---------------------|
| 0 | aboutline1 | "    {}" | "    iCopy-XS" |
| 1 | aboutline2 | "   HW  {}" | "   HW  1.7" |
| 2 | aboutline3 | "   HMI {}" | "   HMI 1.4" |
| 3 | aboutline4 | "   OS  {}" | "   OS  1.0.90" |
| 4 | aboutline5 | "   PM  {}" | "   PM  3.1" |
| 5 | aboutline6 | "   SN  {}" | "   SN  02150004" |

Note: The first line (aboutline1) is the device name "iCopy-XS" (NOT a version number with "v" prefix). Leading spaces in format strings provide consistent left-margin alignment. The `{}` placeholder is filled by `init_info()` with actual version data.

**Page 1 citation:** `about_1_2.png` shows title "About 1/2" and content: "iCopy-XS", "HW 1.7", "HMI 1.4", "OS 1.0.90", "PM 3.1", "SN 02150004".

- **Page 2**: "About 2/2" shows firmware update instructions (same content as UPDATE_AVAILABLE state below). This page exists by default on devices, showing update instructions as informational content.

**Page 2 citation:** `about_2_2.png` shows title "About 2/2" with "Firmware update", "1.Download firmware", "icopy-x.com/update", "2.Plug USB, Copy firmware to device.", "3.Press 'OK' start update."

- **Footer**: None (display-only screen)
- **Navigation**:
  - PWR: Exit activity (universal back)
  - OK: Check for firmware update (triggers `checkUpdate()`)
  - UP/DOWN: Page navigation between About 1/2 and About 2/2

### STATE: UPDATE_AVAILABLE (If firmware update detected)

- **Title**: "About" (unchanged)
- **Items change to update instructions** (resources.py StringEN.itemmsg, line 11):

| Index | Resource Key | Display Text |
|-------|-------------|-------------|
| 0 | aboutline1_update | "Firmware update" |
| 1 | aboutline2_update | "1.Download firmware" |
| 2 | aboutline3_update | " icopy-x.com/update" |
| 3 | aboutline4_update | "2.Plug USB, Copy firmware to device." |
| 4 | aboutline5_update | "3.Press 'OK' start update." |

- **Navigation**:
  - OK: Start firmware update process (launches OTAActivity)
  - PWR: Return to INFO_DISPLAY

### STATE: ERROR (If version info retrieval fails)

- **Content**: Error message via `showErr()` (activity_main_strings.txt:21255)
- **Navigation**:
  - PWR: Exit activity

---

## 3. Key Methods Detail

### __init__ (line 45487)

Takes `(self, parent)` as arguments (decompiled line 45519: expects 2 positional args).

Initialization sequence (reconstructed from lines 45587-45803):
1. Calls super().__init__(parent) via base class constructor
2. Sets up `self.__init__()` call chain
3. Initializes `self.checkUpdateResult = None` (attribute set at line 45661-45672)
4. Initializes `self.update_info = None` (attribute set at line 45673)
5. Looks up resources module for string formatting
6. Calls resources.get_str() to prepare aboutline1-6 format strings

### onCreate (line 43292)

Takes `(self)` as single argument (decompiled line 43327: expects 1 positional arg).

Sequence (reconstructed from lines 43380-43891):
1. Calls super().onCreate() (attribute lookup at line 43382)
2. Gets resources.get_str() for title string "about" (line 43399-43413)
3. Builds title via `resources.get_str('about')` -> "About"
4. Calls `initList()` with title and item configuration
5. Calls `self.init_info()` to populate version data
6. Sets up version info display:
   - Gets firmware version from config module
   - Gets hardware version
   - Gets HMI version (self reference)
   - Calls `getKernel()` for OS version (line 43549+)
   - Gets PM3 version
   - Gets serial number
7. Formats each line with the appropriate aboutline format string
8. Populates the list view with formatted strings

### onKeyEvent (line 42201)

Takes `(self, key)` as arguments (decompiled line 42235: expects 2 positional args).

Key handling (reconstructed from lines 42304-42400):

```
if key == KEY_OK:           (line 42344, RichCompare)
    self.checkUpdate()      (line 42389-42399, attribute call)
    return True

elif key == KEY_PWR:        (second comparison block)
    self.finish()           (exit activity)
    return True
```

Note: OK and PWR are explicitly handled. UP/DOWN are handled by the parent ListView for page navigation between About 1/2 and About 2/2 (the display has 2 pages as confirmed by `about_1_2.png` and `about_2_2.png`).

### onResume (line 14417)

Called when activity returns to foreground. Re-reads version info in case
of changes (e.g., after firmware update).

### getKernel (line 45288)

Reads the Linux kernel version string for the OS line.
Reads from `/proc/version` or equivalent system interface.
Returns a formatted version string (e.g., "5.4.31").

### checkUpdate (activity_main_strings.txt:21154)

Checks if a firmware update is available:
1. Scans for update files in device storage
2. If found, transitions display to update instructions
3. If not found, shows "No update available" toast
   (resources.py StringEN.toastmsg.update_unavailable, line 8)

### init_info (activity_main_strings.txt:21204)

Populates version data into the 6-line display:
1. Reads firmware version from config
2. Reads hardware version from hardware identifier
3. Reads HMI (human-machine interface) version
4. Calls `getKernel()` for OS version
5. Reads PM3 firmware version
6. Reads device serial number

### start_init_data_to_view (activity_main_strings.txt:20991)

Async wrapper that runs `init_info()` on a background thread,
then updates the UI on the main thread.

### showErr (activity_main_strings.txt:21255)

Displays an error message if version info cannot be retrieved.

---

## 4. String Resource Cross-Reference

| Category | Key | Value | resources.py line |
|----------|-----|-------|-------------------|
| title | about | "About" | 7 |
| itemmsg | aboutline1 | "    {}" | 11 |
| itemmsg | aboutline2 | "   HW  {}" | 11 |
| itemmsg | aboutline3 | "   HMI {}" | 11 |
| itemmsg | aboutline4 | "   OS  {}" | 11 |
| itemmsg | aboutline5 | "   PM  {}" | 11 |
| itemmsg | aboutline6 | "   SN  {}" | 11 |
| itemmsg | aboutline1_update | "Firmware update" | 11 |
| itemmsg | aboutline2_update | "1.Download firmware" | 11 |
| itemmsg | aboutline3_update | " icopy-x.com/update" | 11 |
| itemmsg | aboutline4_update | "2.Plug USB, Copy firmware to device." | 11 |
| itemmsg | aboutline5_update | "3.Press 'OK' start update." | 11 |
| toastmsg | update_unavailable | "No update available" | 8 |
| toastmsg | update_finish | "Update finish." | 8 |

---

## Corrections Applied

| Date | Correction | Evidence |
|------|-----------|----------|
| 2026-03-31 | Corrected from "single page with no pagination" to "2 pages: About 1/2 (device info) and About 2/2 (firmware update instructions)". Title includes page indicator "About N/M". | `about_1_2.png`, `about_2_2.png` |
| 2026-03-31 | Corrected first line from "version number with v prefix" to device name "iCopy-XS" (no v prefix). Version lines are: HW 1.7, HMI 1.4, OS 1.0.90, PM 3.1, SN 02150004. | `about_1_2.png` |
| 2026-03-31 | Retained UPDATE_AVAILABLE conditional state as valid per decompiled code. | Binary analysis |

---

## Key Bindings

### AboutActivity.onKeyEvent (actmain_ghidra_raw.txt)

Two pages: Page 0 (device info), Page 1 (update instructions).

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| PAGE 0 | no-op | page 1 | no-op | no-op | checkUpdate() | no-op | checkUpdate() | finish() |
| PAGE 1 | page 0 | no-op | no-op | no-op | checkUpdate() | page 0 | checkUpdate() | finish() |

**Notes:**
- UP/DOWN navigate between pages (2-page document).
- M1 goes to previous page (no-op on page 0).
- M2/OK launches UpdateActivity (checks for firmware updates).
- PWR exits at any page.

**Source:** `src/lib/activity_main.py` lines 508-532.
