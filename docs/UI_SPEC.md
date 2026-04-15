# iCopy-X UI Specification

## Extracted from Original Firmware v1.0.90 via QEMU

All values verified by running original `actbase.so`, `widget.so`, and `resources.so` under
QEMU user-mode emulation with ARM Python 3.8, inspecting tkinter Canvas items.

---

## 1. Screen Dimensions

- **Canvas**: 240x240 pixels
- **Display**: 240x240 IPS LCD (1.3" square)
- **Background**: `#222222` (dark grey, RGB 34,34,34)

---

## 2. Layout Zones

```
+------------------------------------------+
|  TITLE BAR           [Battery]  |  40px  |
|  (0,0) to (240,40)             |         |
|  fill: #7C829A                 |         |
+------------------------------------------+
|                                 |         |
|  CONTENT AREA                   |  160px  |
|  (0,40) to (240,200)           |         |
|  fill: #222222                 |         |
|                                 |         |
+------------------------------------------+
|  [Left Btn]         [Right Btn] |  40px  |
|  (0,200) to (240,240)          |         |
|  fill: #222222                 |         |
+------------------------------------------+
```

### 2.1 Title Bar
- **Position**: Rectangle (0, 0, 240, 40)
- **Background color**: `#7C829A` (muted blue-grey, RGB 124,130,154)
- **Title text position**: (120, 20) centered
- **Title text color**: `white`
- **Title text font**: mononoki (EN) / WenQuanYi Zen Hei Mono (ZH), size varies
  - On real device uses `resources.get_font(size)` which returns mononoki for EN
  - Title font reference in code: "Consolas 18" tag in analysis but actual rendering uses the resources font system
- **Title text anchor**: `center`
- **Tag**: `ID:{uid}-title`

### 2.2 Button Bar
- **Background**: Rectangle (0, 200, 240, 240), fill `#222222`
- **Tag**: `ID:{uid}-btnBg`

#### Left Button
- **Text position**: (15, 228)
- **Anchor**: `sw` (southwest -- text baseline at bottom-left)
- **Text color**: `white` (normal), `grey` (disabled)
- **Font**: `font1` (resolved via resources font system -- mononoki on EN locale)
- **Tag**: `ID:{uid}-btnLeft`

#### Right Button
- **Text position**: (225, 228)
- **Anchor**: `se` (southeast -- text baseline at bottom-right)
- **Text color**: `white` (normal), `grey` (disabled)
- **Font**: `font2` (resolved via resources font system -- mononoki on EN locale)
- **Tag**: `ID:{uid}-btnRight`

### 2.3 Content Area
- **Position**: (0, 40) to (240, 200)
- **Height**: 160px
- **Background**: `#222222` (same as main background)

---

## 3. Colors

### 3.1 Core Palette (verified from canvas items)
| Element               | Color     | RGB           |
|-----------------------|-----------|---------------|
| Screen background     | `#222222` | (34, 34, 34)  |
| Title bar background  | `#7C829A` | (124,130,154) |
| Title text            | `white`   | (255,255,255) |
| Button text (normal)  | `white`   | (255,255,255) |
| Button text (disabled)| `grey`    | (128,128,128) |
| Button bar background | `#222222` | (34, 34, 34)  |
| Selection highlight   | `#EEEEEE` | (238,238,238) |
| Selection outline     | `black`   | (0, 0, 0)     |
| Selected item text    | `black`   | (0, 0, 0)     |
| Non-selected text     | `black`   | (0, 0, 0) *   |
| Battery outline       | `white`   | (255,255,255) |
| ProgressBar bg        | `#eeeeee` | (238,238,238) |
| ProgressBar fill      | `#1C6AEB` | (28,106,235)  |
| ProgressBar msg text  | `#1C6AEB` | (28,106,235)  |

\* Non-selected text is `black` per the canvas data. On the original device with the dark
`#222222` background, the ListView uses icons/images for color contrast. The text items
that appear dark are intentional -- the images module recolors icons to provide visual
contrast (white icons on dark bg, dark icons on light selection).

### 3.2 Color Notes
- **IMPORTANT**: Our reimplementation currently uses `#000000` for background instead of `#222222`
- **IMPORTANT**: Our title bar uses `#222222` instead of `#7C829A`
- **IMPORTANT**: Our selection highlight uses `#0F3460` instead of `#EEEEEE`

---

## 4. Fonts

### 4.1 Font Files (from `/res/font/`)
- `mononoki-Regular.ttf` -- English text, monospaced (90KB)
- `monozhwqy.ttf` -- WenQuanYi Zen Hei Mono, Chinese/CJK text (8.8MB)

### 4.2 Font Resolution System
The `resources.so` module provides font resolution:
```
resources.get_font_force_en(size)  -> "mononoki {size}"
resources.get_font_force_zh(size)  -> "文泉驿等宽正黑 {size}"
resources.get_font(size)           -> locale-dependent (EN or ZH)
```

### 4.3 Font Usage by Element
| Element            | Font Spec            | Typical Size |
|--------------------|---------------------|-------------|
| Title text         | resources.get_font  | varies       |
| Button text        | font1 / font2       | ~16          |
| ListView items     | resources.get_font  | 13 (EN), 15 (ZH) |
| ProgressBar msg    | resources.get_font  | varies       |
| Console output     | mononoki            | 8            |

### 4.4 DrawParEN (English locale parameters)
```python
DrawParEN.widget_xy  = {'lv_main_page': (0, 40)}
DrawParEN.text_size  = {'lv_main_page': 13}
DrawParEN.int_param  = {'lv_main_page_str_margin': 50}
```

### 4.5 DrawParZH (Chinese locale parameters)
```python
DrawParZH.widget_xy  = {'lv_main_page': (0, 40)}
DrawParZH.text_size  = {'lv_main_page': 15}
DrawParZH.int_param  = {'lv_main_page_str_margin': 61}
```

---

## 5. Widgets

### 5.1 BatteryBar

**Positioned in the title bar, top-right corner.**

```
Battery body:
  External rect: (208, 15) to (230, 27)  -- outline=white, width=2, no fill
  Contact pip:   (230, 19.2) to (232.4, 22.8) -- fill=white, outline=white
  Internal fill: (210, 17) to (210+fill_w, 25) -- fill=color based on level
```

- Battery body width: 22px, height: 12px
- Contact pip: 2.4px wide, 3.6px tall
- Fill starts at x=210, width proportional to battery percent
- Fill colors: green (high), yellow (medium), red (low), green (charging)
- Tags: `{uid}:external`, `{uid}:contact`, `{uid}:internal`

### 5.2 ListView

**The primary navigation widget. Shows a scrollable list of items.**

#### Layout
- **Starting position**: (0, 40) for main page (from `DrawParEN.widget_xy`)
- **Default item height**: 40px
- **Items per page**: 4 (160px content area / 40px per item)
  - Note: The original actually renders 5 items extending into button bar area at y=220
- **Text x-position**: x=19 (without icons), x=50 (with icons, per `str_margin`)
- **Text y-position**: centered in item (y = item_top + item_height/2)
- **Text anchor**: `w` (west -- left-aligned)
- **Page count**: ceil(total_items / items_per_page)

#### Selection
- **Highlight rect**: full-width rectangle at item position
  - coords: (0, item_y, 240, item_y + item_height)
  - fill: `#EEEEEE`, outline: `black`, width: 0
- **Selected text color**: `black`
- **Non-selected text color**: `black` (same -- icons provide contrast)
- **Tags**: `{uid}:bg` for selection rect, `{uid}:text` for text items

#### Menu Item Icons
- Size: 20x20 pixels (RGBA)
- Position: (icon_x, item_y + center_offset)
- Files: `1.png` through `10.png` (numbered by menu position)
- Additional: `diagnosis.png`, `factory.png`, `network.png`, `sleep.png`, `snake.png`, etc.
- Image processing: `images.load(name, rgb=((102,102,102), (255,255,255)))` recolors icons

### 5.3 CheckedListView (extends ListView)

Same as ListView but with check indicators:
- Check mark: drawn before item text
- `auto_show_chk()`: toggles check on current selection
- `getCheckPosition()`: returns set of checked indices

### 5.4 ProgressBar

#### Layout
- **Background rect**: (20, 100) to (220, 120) -- fill `#eeeeee`, no outline
- **Progress fill rect**: (20, 100) to (20 + fill_width, 120) -- fill `#1C6AEB`
- **Message text**: (120, 98), anchor `s` (bottom-center, above bar)
- **Message color**: `#1C6AEB` (matches progress fill)
- **Tags**: `{uid}:bg`, `{uid}:pb`, `{uid}:msg`

#### Parameters
```python
ProgressBar(canvas, xy=(20, 100), width=200, height=20, max_v=100)
```

### 5.5 Toast

#### Modes
- `MASK_CENTER = 'mask_center'`
- `MASK_FULL = 'mask_full'`
- `MASK_TOP_CENTER = 'mask_top_center'`

#### Rendering
- Uses a semi-transparent mask overlay (image layer)
- Text centered on mask
- Optional icon
- Tags: `{uid}:mask_layer`, `{uid}:msg`, `{uid}:icon`

### 5.6 PageIndicator

- Shows up/down arrows or page dots for multi-page lists
- Position: typically at top or bottom of content area
- Uses original icon images: `up.png` (16x8), `down.png` (16x8), `up_down.png` (34x8)

### 5.7 BigTextListView (extends ListView)

- For displaying large text blocks
- Uses larger font size (text_size=13 default)
- Draws strings with base_y offset

### 5.8 InputMethods

- For hex/text input on simulation screens
- Parameters: `bakcolor='#ffffff'`, `datacolor='#000000'`, `highlightcolor='#cccccc'`
- Uses per-character focus with roll selection

---

## 6. Activity Screens

### 6.1 Main Page (MainActivity)
- **Title**: "Main Page" (EN) / "主页面" (ZH)
- **Left button**: (none -- no back from main)
- **Right button**: "OK"
- **Content**: ListView with menu items + icons

Menu items (original order):
1. Scan
2. Read
3. Write
4. Copy (Auto Copy)
5. Simulate
6. Sniff
7. Saved
8. PC Mode
9. Settings
10. About

Additional items (hardware version >= 1.5):
- Diagnosis
- Greedy Snake
- Erase Tag
- Time Settings
- SE Decoder
- Watch (Write Wearable)
- Dump Files
- Tag Info
- LUA Script

### 6.2 Scan Tag (ScanActivity)
- **Title**: "Scan Tag"
- **Left button**: "Back"
- **Right button**: "Scan" -> "Stop" (during scan)
- **Content**: Progress bar during scan, results list after scan
- **Toast messages**: "Tag Found", "No tag found", "Multiple tags detected!"

### 6.3 Read Tag (ReadActivity)
- **Title**: "Read Tag"
- **Left button**: "Back"
- **Right button**: "Read" / "Stop"
- **Content**: ConsolePrinterActivity output, ProgressBar during read
- **Toast messages**: "Read Successful! File saved", "Read Failed!"
- **Progress messages**: "Reading...", "Reading...{}/{}Keys"

### 6.4 Write Tag (WriteActivity)
- **Title**: "Write Tag"
- **Left button**: "Back"
- **Right button**: "Write" / "Stop"
- **Content**: Progress bar, verification result
- **Toast messages**: "Write successful!", "Write failed!"
- **Progress messages**: "Writing...", "Verifying..."

### 6.5 Auto Copy (AutoCopyActivity)
- **Title**: "Auto Copy"
- **Left button**: "Back"
- **Right button**: "Scan"
- **Content**: Scan + Read + Write workflow in sequence

### 6.6 Simulation (SimulationActivity)
- **Title**: "Simulation"
- **Left button**: "Back"
- **Right button**: "Sim"
- **Content**: ListView of simulation types, then InputMethods for UID entry
- **Simulation types**: HF MF Classic (4B/7B UID), HF MF Ultralight, LF EM410x, LF HID, etc.

### 6.7 Sniff (SniffActivity)
- **Title**: "Sniff TRF"
- **Left button**: "Back"
- **Right button**: "Start" / "Finish"
- **Content**: Step-by-step instructions, then trace results
- **Sniff types**: 14A Sniff, 14B Sniff, iclass Sniff, Topaz Sniff, T5577 Sniff

### 6.8 About (AboutActivity)
- **Title**: "About"
- **Left button**: "Back"
- **Right button**: "Update"
- **Content**: ListView with device info:
  - `    {version_str}` (e.g., "1.0.90")
  - `   HW  {hw_ver}` (e.g., "1.7")
  - `   HMI {hmi_ver}`
  - `   OS  {os_ver}`
  - `   PM  {pm_ver}`
  - `   SN  {serial_num}`

### 6.9 PC-Mode (PCModeActivity)
- **Title**: "PC-Mode"
- **Left button**: "Back"
- **Right button**: "Start"
- **Content**: Tips text "Please connect to the computer. Then press start button"

### 6.10 Volume (VolumeActivity)
- **Title**: "Volume"
- **Left button**: "Back"
- **Right button**: "OK"
- **Content**: ListView with levels: Off, Low, Middle, High

### 6.11 Backlight (BacklightActivity)
- **Title**: "Backlight"
- **Left button**: "Back"
- **Right button**: "OK"
- **Content**: ListView with levels: Low, Middle, High

### 6.12 Diagnosis (DiagnosisActivity)
- **Title**: "Diagnosis"
- **Left button**: "Back"
- **Right button**: "Start"
- **Content**: Checklist of test items with pass/fail status

### 6.13 Key Enter (KeyEnterM1Activity)
- **Title**: "Key Enter"
- **Left button**: "Back"
- **Right button**: "Enter"
- **Content**: InputMethods for entering Mifare keys

### 6.14 Warning Screens
- **Title**: "Warning" / "Missing keys" / "No valid key" / "Data ready!"
- **Left button**: varies
- **Right button**: varies
- **Content**: Multi-page text with warning/instruction content

### 6.15 Update (UpdateActivity)
- **Title**: "Update"
- **Left button**: "Back"
- **Right button**: "Start"
- **Content**: ProgressBar during installation

### 6.16 Console Printer (ConsolePrinterActivity)
- **Title**: inherits from parent activity
- **Font**: mononoki 8
- **Text color**: white on `#222222` background
- **Scroll**: automatic text scrolling for long output

---

## 7. Button Behaviors

### 7.1 setLeftButton / setRightButton
```python
setLeftButton(text, color='white')   # text at (15, 228) anchor='sw'
setRightButton(text, color='white')  # text at (225, 228) anchor='se'
```

### 7.2 disableButton
```python
disableButton(left=True, right=True, color='grey', color_normal='white')
```
- Sets disabled button text to `'grey'`
- Sets enabled button text to `color_normal` (default `'white'`)

### 7.3 dismissButton
```python
dismissButton(left=True, right=True)
```
- Removes button text from canvas entirely

---

## 8. Key Differences: Original vs Current Reimplementation

| Aspect                  | Original              | Current Reimpl         | Action Needed |
|-------------------------|-----------------------|------------------------|---------------|
| Screen background       | `#222222`             | `#222222`              | Correct       |
| Title bar color         | `#7C829A`             | `#222222`              | **FIX**       |
| Title bar height        | 40px                  | 30px                   | **FIX**       |
| Button bar height       | 40px                  | 30px                   | **FIX**       |
| Content area            | y=40 to y=200 (160px) | y=30 to y=210 (180px)  | **FIX**       |
| Button left position    | (15, 228) anchor=sw   | center of left half    | **FIX**       |
| Button right position   | (225, 228) anchor=se  | center of right half   | **FIX**       |
| Selection highlight     | `#EEEEEE` (light grey)| `#0F3460` (dark blue)  | **FIX**       |
| Selection outline       | `black`               | none                   | **FIX**       |
| Selected text color     | `black`               | `#FFFFFF`              | **FIX**       |
| ListView item height    | 40px                  | 28px                   | **FIX**       |
| ListView text x         | 19px (no icon)        | 10px                   | **FIX**       |
| ProgressBar fill color  | `#1C6AEB` (blue)      | `#E94560` (red/pink)   | **FIX**       |
| ProgressBar bg          | `#eeeeee`             | `#333333`              | **FIX**       |
| Battery position        | (208, 15)             | (205, 5)               | **FIX**       |
| Battery size            | 22x12 + pip           | 25x12 + pip            | **FIX**       |
| Font for EN             | mononoki              | mononoki               | Correct       |
| Button bar bg color     | `#222222`             | `#222222`              | Correct       |

---

## 9. Reference Screenshots

Screenshots rendered using the ORIGINAL firmware's `actbase.so` and `widget.so` under QEMU:

| Screenshot                          | Description                                    |
|-------------------------------------|------------------------------------------------|
| `orig_main_page.png`               | Main menu with ListView and battery icon       |
| `orig_main_page_h40.png`           | Main menu with 40px item height               |
| `orig_scan_tag.png`                | Scan Tag screen (empty, with Back/Scan btns)  |
| `orig_read_tag.png`                | Read Tag screen                                |
| `orig_write_tag.png`               | Write Tag screen                               |
| `orig_about.png`                   | About screen with device info list             |
| `orig_simulate.png`                | Simulation screen with type list               |
| `orig_sniff.png`                   | Sniff screen with protocol list                |
| `orig_sniff_checklist.png`         | Sniff CheckedListView                          |
| `orig_volume.png`                  | Volume settings screen                         |
| `orig_pcmode.png`                  | PC-Mode screen                                 |
| `orig_diagnosis.png`               | Diagnosis screen                               |
| `orig_autocopy.png`                | Auto Copy screen                               |
| `orig_progressbar.png`             | Progress bar during read operation             |
| `orig_console_output.png`          | Console printer output (PM3 commands)          |
| `orig_disabled_btn.png`            | Screen with disabled buttons                   |

---

## 10. String Resources (English)

### 10.1 Screen Titles
```
main_page     = "Main Page"
auto_copy     = "Auto Copy"
about         = "About"
backlight     = "Backlight"
key_enter     = "Key Enter"
network       = "Network"
update        = "Update"
pc-mode       = "PC-Mode"
read_tag      = "Read Tag"
scan_tag      = "Scan Tag"
sniff_tag     = "Sniff TRF"
sniff_notag   = "Sniff TRF"
volume        = "Volume"
warning       = "Warning"
missing_keys  = "Missing keys"
no_valid_key  = "No valid key"
data_ready    = "Data ready!"
write_tag     = "Write Tag"
disk_full     = "Disk Full"
snakegame     = "Greedy Snake"
trace         = "Trace"
simulation    = "Simulation"
diagnosis     = "Diagnosis"
wipe_tag      = "Erase Tag"
time_sync     = "Time Settings"
se_decoder    = "SE Decoder"
write_wearable= "Watch"
card_wallet   = "Dump Files"
tag_info      = "Tag Info"
lua_script    = "LUA Script"
```

### 10.2 Button Labels
```
read      = "Read"
stop      = "Stop"
start     = "Start"
reread    = "Reread"
rescan    = "Rescan"
retry     = "Retry"
sniff     = "Sniff"
write     = "Write"
simulate  = "Simulate"
finish    = "Finish"
save      = "Save"
enter     = "Enter"
pc-m      = "PC-M"
cancel    = "Cancel"
rewrite   = "Rewrite"
force     = "Force"
verify    = "Verify"
forceuse  = "Force-Use"
clear     = "Clear"
shutdown  = "Shutdown"
yes       = "Yes"
no        = "No"
wipe      = "Erase"
edit      = "Edit"
delete    = "Delete"
details   = "Details"
```

### 10.3 Progress Bar Messages
```
reading         = "Reading..."
writing         = "Writing..."
verifying       = "Verifying..."
scanning        = "Scanning..."
clearing        = "Clearing..."
wipe_block      = "Erasing"
tag_fixing      = "Repairing..."
tag_wiping      = "Erasing..."
```

### 10.4 Toast Messages
```
tag_found            = "Tag Found"
no_tag_found         = "No tag found"
tag_multi            = "Multiple tags detected!"
read_ok_1            = "Read\nSuccessful!\nFile saved"
read_failed          = "Read Failed!"
write_success        = "Write successful!"
write_failed         = "Write failed!"
verify_success       = "Verification successful!"
verify_failed        = "Verification failed!"
processing           = "Processing..."
simulating           = "Simulation in progress..."
sniffing             = "Sniffing in progress..."
wipe_success         = "Erase successful"
wipe_failed          = "Erase failed"
```

---

## 11. Icon Reference

### 11.1 Menu Icons (20x20 RGBA)
| File           | Menu Item    |
|----------------|-------------|
| `1.png`        | Scan        |
| `2.png`        | Read        |
| `3.png`        | Write       |
| `4.png`        | Copy        |
| `5.png`        | Simulate    |
| `6.png`        | Sniff       |
| `7.png`        | Saved       |
| `8.png`        | PC Mode     |
| `9.png`        | Settings    |
| `10.png`       | About       |

### 11.2 Navigation Icons
| File           | Usage        | Size   |
|----------------|-------------|--------|
| `up.png`       | Page up      | 16x8   |
| `down.png`     | Page down    | 16x8   |
| `up_down.png`  | Both arrows  | 34x8   |
| `right.png`    | Selection    | 23x23  |

### 11.3 Status Icons
| File           | Usage        | Size   |
|----------------|-------------|--------|
| `new_blue.png` | New (active) | 20x20  |
| `new_grey.png` | New (inactive)| 20x20 |
| `wrong.png`    | Error/fail   | 23x23  |
| `sleep.png`    | Sleep mode   | 20x20  |
| `diagnosis.png`| Self-test    | 20x20  |
| `factory.png`  | Factory test | 20x20  |
| `erase.png`    | Erase tag    | 20x20  |
| `network.png`  | Network      | 20x20  |
| `script.png`   | LUA script   | 20x20  |
| `list.png`     | Dump files   | 20x20  |
| `time.png`     | Time sync    | 20x20  |
| `snake.png`    | Snake game   | 20x20  |
| `tag_release.png`| Tag release | 20x20 |

---

## 12. Precise Canvas Item Specifications

### 12.1 BaseActivity.setTitle(title, xy=(120, 20))
```
Item 1: rectangle  coords=[0, 0, 240, 40]       fill='#7C829A'  outline=''
Item 2: text        coords=[120, 20]              fill='white'    anchor='center'
                    font=resources.get_font(size)
                    tags=('ID:{uid}-title',)
```

### 12.2 BaseActivity.setLeftButton(text, color='white')
```
Item: text  coords=[15, 228]  fill=color  anchor='sw'  font='font1'
            tags=('ID:{uid}-btnLeft',)
```

### 12.3 BaseActivity.setRightButton(text, color='white')
```
Item: text  coords=[225, 228]  fill=color  anchor='se'  font='font2'
            tags=('ID:{uid}-btnRight',)
```

### 12.4 BaseActivity._setupButtonBg()
```
Item: rectangle  coords=[0, 200, 240, 240]  fill='#222222'  outline=''
                 tags=('ID:{uid}-btnBg',)
```

### 12.5 BatteryBar (created automatically with setTitle)
```
External: rectangle  coords=[208, 15, 230, 27]       outline='white'  width=2  fill=''
Contact:  rectangle  coords=[230, 19.2, 232.4, 22.8] fill='white'   outline='white' width=1
Internal: rectangle  coords=[210, 17, 210+fw, 25]    fill=level_color outline='' width=0
```

### 12.6 ListView item rendering
```
Selection BG: rectangle coords=[0, item_y, 240, item_y+40]
              fill='#EEEEEE' outline='black' width=0
              tags=('{uid}:bg',)

Item text:    text coords=[19, item_y+20]
              fill='black' anchor='w'
              font=resources.get_font(text_size)
              tags=('{uid}:text',)
```

### 12.7 ProgressBar rendering
```
Background: rectangle coords=[20, 100, 220, 120]  fill='#eeeeee' outline=''
Fill:       rectangle coords=[20, 100, 20+fw, 120] fill='#1C6AEB' outline=''
Message:    text      coords=[120, 98]              fill='#1C6AEB' anchor='s'
```
