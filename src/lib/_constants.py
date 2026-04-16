##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""UI framework constants — layout, colors, fonts, keys, canvas tags.

Every value is traceable to UI_SPEC.md (extracted from the real v1.0.90
firmware running under QEMU) or to the decompiled actbase.c / widget.so
binaries.  When a value appears in both UI_SPEC.md and the prototype
code, UI_SPEC.md wins — it was measured from the real firmware.

Source key:
    SPEC  = docs/UI_SPEC.md (QEMU-verified canvas items)
    ACT   = decompiled/actbase.c (string table)
    WID   = decompiled/widget_ghidra_raw.txt (string table)
    API   = archive/root_old/qemu_api_dump_filtered.txt
"""

# ═══════════════════════════════════════════════════
# SCREEN DIMENSIONS                            [SPEC §1]
# ═══════════════════════════════════════════════════
SCREEN_W = 240
SCREEN_H = 240

# ═══════════════════════════════════════════════════
# BACKGROUND                                   [SPEC §3.1]
# ═══════════════════════════════════════════════════
BG_COLOR = '#F8FCF8'            # off-white — real device FB pixel (248,252,248)

# ═══════════════════════════════════════════════════
# TITLE BAR                                    [SPEC §2.1, §12.1]
# ═══════════════════════════════════════════════════
# Rectangle (0, 0, 240, 40) fill='#7C829A'
# Text (120, 20) fill='white' anchor='center'
TITLE_BAR_Y0 = 0
TITLE_BAR_Y1 = 40
TITLE_BAR_H = 40
TITLE_BAR_BG = '#7C829A'        # RGB(124,130,154) muted blue-grey
TITLE_TEXT_X = 105                  # user spec: -15px from center
TITLE_TEXT_Y = 20
TITLE_TEXT_COLOR = 'white'
TITLE_TEXT_ANCHOR = 'center'

# ═══════════════════════════════════════════════════
# CONTENT AREA                                 [SPEC §2.3]
# ═══════════════════════════════════════════════════
CONTENT_Y0 = 40
CONTENT_Y1 = 200
CONTENT_H = 160                 # 240 - 40 title - 40 buttons
CONTENT_BG = '#F8FCF8'          # off-white — real device FB pixel (248,252,248)

# ═══════════════════════════════════════════════════
# BUTTON BAR                                   [SPEC §2.2, §12.2-§12.4]
# ═══════════════════════════════════════════════════
# Background: rectangle (0, 200, 240, 240) — same light bg as content on real device
# Left text:  (15, 228) anchor='sw'
# Right text: (225, 228) anchor='se'
BTN_BAR_Y0 = 200
BTN_BAR_Y1 = 240
BTN_BAR_H = 40
BTN_BAR_BG = '#222222'            # Ground truth: actbase_strings.txt line 1228

BTN_LEFT_X = 15
BTN_LEFT_Y = 233                   # Ground truth: real device comparison — 5px lower
BTN_LEFT_ANCHOR = 'sw'

BTN_RIGHT_X = 225
BTN_RIGHT_Y = 233                  # Ground truth: real device comparison — 5px lower
BTN_RIGHT_ANCHOR = 'se'

BTN_TEXT_COLOR = 'white'           # Ground truth: actbase_strings.txt line 1230
BTN_TEXT_COLOR_DISABLED = '#808080'  # Ground truth: FB state_010 dimmed "Start" during sim

# ═══════════════════════════════════════════════════
# LISTVIEW                                     [SPEC §5.2, §12.6]
# ═══════════════════════════════════════════════════
# Default item height 40px → 5 items per page.
# Selection rect: (0, y, 240, y+40) fill='#EEEEEE' outline='black' width=0
# Text: (19, y+20) or (50, y+20) anchor='w'
LIST_ITEM_H = 40
LIST_ITEMS_PER_PAGE = 5
LIST_TEXT_X_NO_ICON = 19
LIST_TEXT_X_WITH_ICON = 50      # DrawParEN.int_param['lv_main_page_str_margin']
LIST_ICON_X = 15                # icon center x, ~15px from left edge
LIST_ICON_SIZE = 20             # 20x20 RGBA icons
LIST_TEXT_ANCHOR = 'w'

# Selection highlight                          [SPEC §3.1, §12.6]
SELECT_BG = '#EEEEEE'          # RGB(238,238,238) — original .so value, verified via test expectations
SELECT_OUTLINE = 'black'       # outline='black' width=0
SELECT_OUTLINE_WIDTH = 0
SELECT_TEXT_COLOR = 'black'    # selected item text is black

# Non-selected text color is also 'black' per SPEC §3.1.
# On the real device, icon recoloring provides contrast on the dark bg.
NORMAL_TEXT_COLOR = 'black'    # SPEC: "Non-selected text is `black`"

# Icon recolor mappings (images.load rgb parameter)
# Ground truth: main_page_1_3_1.png — icons are dark grey on light bg.
# Original icons are grey (102,102,102). On white bg, keep dark.
ICON_RECOLOR_NORMAL = ((102, 102, 102), (80, 80, 80))      # grey→dark grey
ICON_RECOLOR_SELECTED = ((102, 102, 102), (0, 0, 0))       # grey→black

# ═══════════════════════════════════════════════════
# CHECKED LISTVIEW                             [SPEC §5.3]
# ═══════════════════════════════════════════════════
CHECK_BOX_SIZE = 16
CHECK_BOX_MARGIN_RIGHT = 15
CHECK_COLOR_UNCHECKED_BORDER = 'grey'
CHECK_COLOR_CHECKED_BORDER = '#1C6AEB'
CHECK_COLOR_CHECKED_FILL = '#1C6AEB'
CHECK_INNER_INSET = 3
CHECK_COLOR = CHECK_COLOR_CHECKED_FILL  # backward compat

# ═══════════════════════════════════════════════════
# PROGRESS BAR
# ═══════════════════════════════════════════════════
# Ground truth: scan_tag_scanning_2.png pixel measurement:
#   Bar:  y=210..229 (20px tall), x=20..220 (200px wide)
#   Text: "Scanning..." at y≈196, centered, blue (#1C6AEB)
#   Bar is anchored to BOTTOM of screen (inside button bar zone)
#   No percentage counter (% only in Erase flow)
PROGRESS_X = 20
PROGRESS_Y = 210
PROGRESS_W = 200
PROGRESS_H = 20
PROGRESS_BG = '#eeeeee'        # RGB(238,238,238)
PROGRESS_FG = '#1C6AEB'        # RGB(28,106,235) blue
PROGRESS_MSG_X = 120
PROGRESS_MSG_Y = 208
PROGRESS_MSG_ANCHOR = 's'      # bottom-center, just above the bar
PROGRESS_MSG_COLOR = '#1C6AEB' # matches progress fill color

# ═══════════════════════════════════════════════════
# BATTERY BAR                                  [SPEC §5.1, §12.5]
# ═══════════════════════════════════════════════════
# External rect: (208, 15, 230, 27) outline='white' width=2 fill=''
# Contact pip:   (230, 19.2, 232.4, 22.8) fill='white' outline='white' width=1
# Internal fill: (210, 17, 210+fw, 25) fill=color outline='' width=0
BATTERY_X = 208
BATTERY_Y = 15
BATTERY_W = 22                  # body width: 230-208
BATTERY_H = 12                  # body height: 27-15
BATTERY_OUTLINE_COLOR = 'white'
BATTERY_OUTLINE_WIDTH = 2

# Contact pip (positive terminal nub on right side)
BATTERY_PIP_X0 = 230
BATTERY_PIP_Y0 = 19.2
BATTERY_PIP_X1 = 232.4
BATTERY_PIP_Y1 = 22.8
BATTERY_PIP_COLOR = 'white'
BATTERY_PIP_WIDTH = 1

# Internal fill area (inset by 2px from body edges)
BATTERY_FILL_X0 = 210
BATTERY_FILL_Y0 = 17
BATTERY_FILL_Y1 = 25
BATTERY_FILL_MAX_W = 18        # 228-210 (inset 2px each side from 22px body)

# Color thresholds
BATTERY_COLOR_HIGH = '#00FF00'  # green  — > 50%
BATTERY_COLOR_MED = '#FFFF00'   # yellow — 20-50%
BATTERY_COLOR_LOW = '#FF0000'   # red    — < 20%
BATTERY_COLOR_CHARGING = '#00FF00'  # green while charging
BATTERY_THRESHOLD_HIGH = 50
BATTERY_THRESHOLD_LOW = 20

# ═══════════════════════════════════════════════════
# TOAST                                        [SPEC §5.5, API, WID]
# ═══════════════════════════════════════════════════
# Three overlay modes (class constants on widget.Toast)
TOAST_MASK_CENTER = 'mask_center'
TOAST_MASK_FULL = 'mask_full'
TOAST_MASK_TOP_CENTER = 'mask_top_center'
TOAST_DEFAULT_MODE = 'mask_top_center'  # API: show(text, icon=None, mask=True, mode='mask_top_center')

# Toast uses a semi-transparent mask overlay (image layer).
# Tags: '{uid}:mask_layer', '{uid}:msg', '{uid}:icon'
# The mask_layer tag is also referenced as 'tags_mask_layer' in widget.so.
TOAST_MASK_TAG_SUFFIX = 'mask_layer'
TOAST_MSG_TAG_SUFFIX = 'msg'
TOAST_ICON_TAG_SUFFIX = 'icon'

# Toast rendering constants (from reference implementation)
TOAST_BG = '#1A1A2E'           # dark navy overlay background
TOAST_BORDER = '#555555'       # subtle border
TOAST_TEXT_COLOR = '#FFFFFF'
TOAST_MARGIN = 20              # x margin from screen edges
TOAST_H = 50                   # total overlay height
TOAST_CENTER_Y = SCREEN_H // 2  # 120 — vertical center for MASK_CENTER

# ═══════════════════════════════════════════════════
# PAGE INDICATOR                               [SPEC §5.6]
# ═══════════════════════════════════════════════════
# Arrow icons: up.png (16x8), down.png (16x8), up_down.png (34x8)
PAGE_ARROW_UP_W = 16
PAGE_ARROW_UP_H = 8
PAGE_ARROW_DOWN_W = 16
PAGE_ARROW_DOWN_H = 8
PAGE_ARROW_BOTH_W = 34
PAGE_ARROW_BOTH_H = 8
PAGE_INDICATOR_COLOR = '#1C6AEB'  # blue accent, same as progress

# ═══════════════════════════════════════════════════
# INPUT METHODS                                [API, SPEC §5.8]
# ═══════════════════════════════════════════════════
# InputMethods(canvas, xy, h, infont, defdata='',
#              bakcolor='#ffffff', datacolor='#000000',
#              highlightcolor='#cccccc', mode=2, usefill=False)
INPUT_BG_COLOR = '#ffffff'
INPUT_DATA_COLOR = '#000000'
INPUT_HIGHLIGHT_COLOR = '#cccccc'
INPUT_DEFAULT_MODE = 2
INPUT_FIELD_BG = '#E5E5E5'      # Ground truth: Time Settings container background

# ═══════════════════════════════════════════════════
# TIME EDITOR                     [Real device screenshots time_settings_*.png]
# ═══════════════════════════════════════════════════
# The time editor has:
#   - Page background: BG_COLOR (light off-white)
#   - Container boxes: INPUT_FIELD_BG (#E5E5E5, light grey) with thin border
#   - Individual input boxes: INPUT_BG_COLOR (#ffffff, white) inside containers
#   - Field text: INPUT_DATA_COLOR (#000000) at ~13pt
#   - Separators: NORMAL_TEXT_COLOR (black/dark) dashes and colons

# Date container box (outer grey rectangle)
TE_DATE_BOX = (20, 60, 220, 100)
# Time container box
TE_TIME_BOX = (48, 120, 198, 160)

# Individual input field boxes (white boxes inside containers)
# Measured from time_settings_1.png: each field has a white rounded box
TE_YEAR_BOX = (24, 64, 82, 96)    # wider for 4 digits
TE_MONTH_BOX = (108, 64, 146, 96)
TE_DAY_BOX = (164, 64, 216, 96)
TE_HOUR_BOX = (52, 124, 90, 156)
TE_MINUTE_BOX = (108, 124, 146, 156)
TE_SECOND_BOX = (160, 124, 194, 156)

# Field text font size (from real device: ~13pt, NOT 18pt)
TE_FIELD_FONT_SIZE = 14

# Date field text positions — CENTER of each white input box
# Boxes: YEAR(24,64,82,96) MONTH(108,64,146,96) DAY(164,64,216,96)
TE_DATE_Y = 80                    # vertical center of date boxes
TE_YEAR_X = 53                    # (24+82)/2
TE_MONTH_X = 127                  # (108+146)/2
TE_DAY_X = 190                    # (164+216)/2
# Date separator positions (between input boxes)
TE_DATE_SEP_Y = 78
TE_DATE_SEP_X = (98, 150)
TE_DATE_SEP_FONT_SIZE = 14
TE_DATE_SEP_COLOR = 'white'       # original .so: white separators on gray bg

# Time field text positions — CENTER of each white input box
# Boxes: HOUR(52,124,90,156) MINUTE(108,124,146,156) SECOND(160,124,194,156)
TE_TIME_Y = 140                   # vertical center of time boxes
TE_HOUR_X = 71                    # (52+90)/2
TE_MINUTE_X = 127                 # (108+146)/2
TE_SECOND_X = 177                 # (160+194)/2
# Time separator positions
TE_TIME_SEP_Y = 138
TE_TIME_SEP_X = (99, 149)
TE_TIME_SEP_FONT_SIZE = 14
TE_TIME_SEP_COLOR = 'white'       # original .so: white separators on gray bg

# Caret position — y depends on row (date=111, time=172)
TE_CARET_DATE_Y = 111
TE_CARET_TIME_Y = 172
TE_CARET_FONT_SIZE = 18
TE_CARET_X = {
    0: 60,    # year
    1: 123,   # month
    2: 176,   # day
    3: 72,    # hour
    4: 123,   # minute
    5: 174,   # second
}
TE_CARET_Y = {
    0: 111, 1: 111, 2: 111,       # date row
    3: 172, 4: 172, 5: 172,       # time row
}

# ═══════════════════════════════════════════════════
# ABOUT PAGE INDICATOR                         [QEMU ground truth 20260405]
# ═══════════════════════════════════════════════════
ABOUT_PAGE_IND_X = 165
ABOUT_PAGE_IND_Y = 8
ABOUT_PAGE_IND_FONT_SIZE = 11
ABOUT_CONTENT_Y = 140

# ═══════════════════════════════════════════════════
# CONSOLE PRINTER                              [SPEC §6.16]
# ═══════════════════════════════════════════════════
CONSOLE_TEXT_COLOR = 'white'
CONSOLE_BG_COLOR = '#FFFFFF'    # same as BG_COLOR

# ═══════════════════════════════════════════════════
# ACCENT / MISC COLORS                        [ACT actmain.c]
# ═══════════════════════════════════════════════════
COLOR_ACCENT = '#1C6AEB'       # blue accent used for progress, indicators
COLOR_DARK_ALT = '#2B2B2B'     # secondary dark bg found in actmain.c
COLOR_PASS = '#00FF00'         # green — diagnosis test pass result
COLOR_NOT_TESTED = '#EEEEEE'   # grey — diagnosis test not-yet-run
COLOR_BLACK = '#000000'        # pure black — screen test, sleep overlay
COLOR_WHITE = '#FFFFFF'        # pure white — screen test

# ═══════════════════════════════════════════════════
# FONTS                                        [SPEC §4, ACT]
# ═══════════════════════════════════════════════════
# actbase.c string table: "Consolas 18" for title, "mononoki 16" for buttons.
# On the real device, resources.get_font(size) returns "mononoki {size}" for
# EN locale.  The "Consolas 18" tag appears in the analysis code but the
# actual rendering path goes through the resources font system.
#
# For reimplementation we use mononoki everywhere (matching the device).
# The Consolas 18 constant is kept for reference/fallback.
FONT_TITLE = ('mononoki', 16)       # user spec: 7% smaller (17 * 0.93 ≈ 16)
FONT_TITLE_FALLBACK = ('Consolas', 16)
FONT_BUTTON = ('mononoki', 16)         # actbase.c: "mononoki 16"
FONT_CONTENT = ('mononoki', 13)        # SPEC §4.3: ListView EN size=13
FONT_CONTENT_ZH = ('mononoki', 15)     # SPEC §4.5: ListView ZH size=15
FONT_CONSOLE = ('mononoki', 8)         # SPEC §6.16: ConsolePrinterActivity
FONT_TOAST = ('mononoki', 11)          # toast message font
FONT_PROGRESS = ('mononoki', 10)       # progress bar percentage/message
FONT_PAGE_ARROW = ('mononoki', 8)      # page indicator arrows

# Font names as plain strings (for resources.get_font / tkinter font spec)
FONT_NAME_EN = 'mononoki'
FONT_NAME_ZH = '文泉驿等宽正黑'  # WenQuanYi Zen Hei Mono

# Font file basenames (in /res/font/)
FONT_FILE_EN = 'mononoki-Regular.ttf'
FONT_FILE_ZH = 'monozhwqy.ttf'

# ═══════════════════════════════════════════════════
# KEY CONSTANTS                                [SPEC §7, API]
# ═══════════════════════════════════════════════════
# Physical keys on the iCopy-X device, mapped through keymap.so.
# PWR is universal back/exit (MEMORY: feedback_pwr_universal_back.md).
# M1 is screen-dependent (left soft key).
KEY_UP = 'UP'
KEY_DOWN = 'DOWN'
KEY_LEFT = 'LEFT'
KEY_RIGHT = 'RIGHT'
KEY_OK = 'OK'
KEY_M1 = 'M1'
KEY_M2 = 'M2'
KEY_PWR = 'PWR'
KEY_SHUTDOWN = 'SHUTDOWN'
KEY_ALL = 'ALL'
KEY_APO = 'APO'                 # auto-power-off

# ═══════════════════════════════════════════════════
# CANVAS TAGS                                  [ACT, SPEC §12]
# ═══════════════════════════════════════════════════
# actbase.c string table provides the exact tag names.
# Format on real device: "ID:{uid}-{suffix}" for base activity items,
# "{uid}:{suffix}" for widget items.
TAG_TITLE = 'tags_title'        # ACT: STR@0x0001feec
TAG_TITLE_TEXT = 'tags_title_text'  # sub-tag for title text (itemconfig updates)
TAG_BTN_LEFT = 'tags_btn_left'  # ACT: STR@0x0001fdf0
TAG_BTN_RIGHT = 'tags_btn_right'  # ACT: STR@0x0001fdb0
TAG_BTN_BG = 'tags_btn_bg'     # implied by _setupButtonBg tag pattern
TAG_BTN_ARROWS = 'tags_btn_arrows'  # page arrows in button bar (▼▲)

# Widget tag suffixes (used as "{uid}:{suffix}")
TAG_SUFFIX_BG = 'bg'           # selection rect, progress bg
TAG_SUFFIX_TEXT = 'text'        # text items
TAG_SUFFIX_PB = 'pb'           # progress bar fill
TAG_SUFFIX_MSG = 'msg'         # progress bar / toast message
TAG_SUFFIX_MASK = 'mask_layer' # toast overlay
TAG_SUFFIX_ICON = 'icon'       # toast icon
TAG_SUFFIX_EXTERNAL = 'external'  # battery outline
TAG_SUFFIX_CONTACT = 'contact'   # battery pip
TAG_SUFFIX_INTERNAL = 'internal'  # battery fill

# ═══════════════════════════════════════════════════
# DRAWPAR RESOURCE KEYS                       [SPEC §4.4, §4.5]
# ═══════════════════════════════════════════════════
# These are the dictionary keys used in DrawParEN / DrawParZH to
# look up widget positions, text sizes, and margins.
DRAWPAR_KEY_MAIN_PAGE = 'lv_main_page'
DRAWPAR_KEY_MAIN_PAGE_STR_MARGIN = 'lv_main_page_str_margin'
DRAWPAR_KEY_LISTVIEW_MARGIN_LEFT = 'listview_str_margin_left'

# DrawParEN values (English locale)
DRAWPAR_EN_WIDGET_XY = {DRAWPAR_KEY_MAIN_PAGE: (0, 40)}
DRAWPAR_EN_TEXT_SIZE = {DRAWPAR_KEY_MAIN_PAGE: 13}
DRAWPAR_EN_INT_PARAM = {DRAWPAR_KEY_MAIN_PAGE_STR_MARGIN: 50}

# DrawParZH values (Chinese locale)
DRAWPAR_ZH_WIDGET_XY = {DRAWPAR_KEY_MAIN_PAGE: (0, 40)}
DRAWPAR_ZH_TEXT_SIZE = {DRAWPAR_KEY_MAIN_PAGE: 15}
DRAWPAR_ZH_INT_PARAM = {DRAWPAR_KEY_MAIN_PAGE_STR_MARGIN: 61}

# ═══════════════════════════════════════════════════
# NAVIGATION ICON SIZES                       [SPEC §11.2]
# ═══════════════════════════════════════════════════
ICON_UP_SIZE = (16, 8)
ICON_DOWN_SIZE = (16, 8)
ICON_UP_DOWN_SIZE = (34, 8)
ICON_RIGHT_SIZE = (23, 23)

# Menu icon size                               [SPEC §11.1]
MENU_ICON_SIZE = (20, 20)

# ═══════════════════════════════════════════════════
# DISK / PATH CONSTANTS                       [ACT actmain.c]
# ═══════════════════════════════════════════════════
PATH_UPAN = 'PATH_UPAN'        # SD card / USB storage mount point key
