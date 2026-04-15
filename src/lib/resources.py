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

"""
resources.py — Drop-in replacement for resources.so

Exports the EXACT same API as the original Cython-compiled resources.so module.
All string values are copied from the verified QEMU shim (tools/qemu_shims/resources.py)
and cross-checked against .so binary string dumps.

Classes: StringEN, StringZH, StringXSC, DrawParEN, DrawParZH
Functions: get_str, get_font, get_font_force_en, get_font_force_zh, get_font_type,
           get_text_size, get_xy, get_int, get_par, get_fws,
           force_check_str_res, is_keys_same, getLanguage, setLanguage
"""

# ---------------------------------------------------------------------------
# Language state
# ---------------------------------------------------------------------------
_current_language = 0  # 0 = EN, 1 = ZH


# ---------------------------------------------------------------------------
# Font names (from /res/font/ on the device)
# ---------------------------------------------------------------------------
_FONT_EN = 'mononoki'
_FONT_ZH = '\u6587\u6cc9\u9a7f\u7b49\u5bbd\u6b63\u9ed1'  # 文泉驿等宽正黑


# ===================================================================
# StringEN — all English locale string resources
# ===================================================================
class StringEN:
    """English string resources. All values verified against QEMU screenshots."""

    button = {
        'button': 'Button',
        'back': 'Back',
        'read': 'Read',
        'scan': 'Scan',
        'stop': 'Stop',
        'start': 'Start',
        'ok': 'OK',
        'reread': 'Reread',
        'rescan': 'Rescan',
        'retry': 'Retry',
        'sniff': 'Sniff',
        'write': 'Write',
        'simulate': 'Simulate',
        'finish': 'Finish',
        'save': 'Save',
        'enter': 'Enter',
        'pc-m': 'PC-M',
        'cancel': 'Cancel',
        'rewrite': 'Rewrite',
        'force': 'Force',
        'verify': 'Verify',
        'forceuse': 'Force-Use',
        'clear': 'Clear',
        'shutdown': 'Shutdown',
        'yes': 'Yes',
        'no': 'No',
        'fail': 'Fail',
        'pass': 'Pass',
        'save_log': 'Save',
        'wipe': 'Erase',
        'edit': 'Edit',
        'delete': 'Delete',
        'details': 'Details',
    }

    title = {
        'main_page': 'Main Page',
        'auto_copy': 'Auto Copy',
        'about': 'About',
        'backlight': 'Backlight',
        'key_enter': 'Key Enter',
        'network': 'Network',
        'update': 'Update',
        'pc-mode': 'PC-Mode',
        'read_tag': 'Read Tag',
        'scan_tag': 'Scan Tag',
        'sniff_tag': 'Sniff TRF',
        'sniff_notag': 'Sniff TRF',
        'volume': 'Volume',
        'settings': 'Settings',
        'warning': 'Warning',
        'missing_keys': 'Missing keys',
        'no_valid_key': 'No valid key',
        'no_valid_key_t55xx': 'No valid key',
        'data_ready': 'Data ready!',
        'write_tag': 'Write Tag',
        'disk_full': 'Disk Full',
        'snakegame': 'Greedy Snake',
        'trace': 'Trace',
        'simulation': 'Simulation',
        'diagnosis': 'Diagnosis',
        'buttons_test': 'Buttons',
        'sound_test': 'Sound',
        'hf_reader_test': 'HF reader',
        'lf_reader_test': 'LF reader',
        'usb_port_test': 'USB port',
        'wipe_tag': 'Erase Tag',
        'time_sync': 'Time Settings',
        'se_decoder': 'SE Decoder',
        'write_wearable': 'Watch',
        'card_wallet': 'Dump Files',
        'tag_info': 'Tag Info',
        'lua_script': 'LUA Script',
        'error': 'Error',
        'searching': 'Searching...',
        'checking': 'Checking...',
    }

    toastmsg = {
        'update_finish': 'Update finished.',
        'update_unavailable': 'No update available',
        'pcmode_running': 'PC-Mode Running...',
        'pcmode_mirror_conflict': 'PC-Mode &\nScreen Mirroring\ncan\'t be used\nat the same time',
        'read_ok_2': 'Read\nSuccessful!\nPartial data\nsaved',
        'read_ok_1': 'Read\nSuccessful!\nFile saved',
        'read_failed': 'Read Failed!',
        'no_tag_found2': 'No tag found \nOr\n Wrong type found!',
        'no_tag_found': 'No tag found',
        'tag_found': 'Tag Found',
        'tag_multi': 'Multiple tags detected!',
        'processing': 'Processing...',
        'trace_saved': 'Trace file\nsaved',
        'sniffing': 'Sniffing in progress...',
        't5577_sniff_finished': 'T5577 Sniff Finished',
        'write_success': 'Write successful!',
        'write_verify_success': 'Write and Verify successful!',
        'write_failed': 'Write failed!',
        'verify_success': 'Verification successful!',
        'verify_failed': 'Verification failed!',
        'you_win': 'You win',
        'game_over': 'Game Over',
        'game_tips': "Press 'OK' to start game.",
        'pausing': 'Pausing',
        'trace_loading': 'Trace\nLoading...',
        'simulating': 'Simulation in progress...',
        'sim_valid_input': "Input invalid:\n'{}' greater than {}",
        'sim_valid_param': 'Invalid parameter',
        'bcc_fix_failed': 'BCC repair failed',
        'wipe_success': 'Erase successful',
        'wipe_failed': 'Erase failed',
        'keys_check_failed': 'Time out',
        'wipe_no_valid_keys': "No valid keys\uff0cPlease use 'Auto Copy' first, Then erase",
        'err_at_wiping': 'Unknown error',
        'time_syncing': 'Synchronizing system time',
        'time_syncok': 'Synchronization successful!',
        'device_disconnected': 'USB device is removed!',
        'plz_remove_device': 'Please remove USB device!',
        'start_clone_uid': 'Start writing UID',
        'unknown_error': 'Unknown error.',
        'write_wearable_err1': 'The original tag and tag(new)\n type is not the same.',
        'write_wearable_err2': 'Encrypted cards are not supported.',
        'write_wearable_err3': 'Change tag position on the antenna.',
        'write_wearable_err4': 'UID write failed. Make sure the tag is placed on the antenna.',
        'delete_confirm': 'Delete?',
        'no_scripts_found': 'No scripts found',
        'opera_unsupported': 'Invalid command',
    }

    tipsmsg = {
        'enter_known_keys_55xx': 'Enter a known key for \nT5577 or EM4305',
        'enter_55xx_key_tips': 'Key:',
        'connect_computer': 'Please connect to\nthe computer.Then\npress start button',
        'screen_mirroring': 'Mirror Screen?',
        'place_empty_tag': 'Data ready for copy!\nPlease place new tag\nfor copy.',
        'type_tips': 'TYPE:',
        'disk_full_tips': 'The disk space is full.\nPlease clear it after backup.',
        'start_diagnosis_tips': 'Press start button to start diagnosis.',
        'installation': 'During installation\ndo not turn off the device.',
        'start_install_tips': "Press 'Start' to install",
        'testing_with': 'Testing with: \n{}',
        'test_music_tips': 'Do you hear the music?',
        'test_screen_tips': "Press 'OK' to start test.\nPress 'OK' again to stop test.\n\n'UP' and 'DOWN' change screen color.",
        'test_screen_isok_tips': 'Is the screen OK?',
        'test_usb_connect_tips': 'Please connect to charger.',
        'test_usb_found_tips': 'Does the computer have a USBSerial(Gadget Serial) found?',
        'test_usb_otg_tips': '1. Connect to OTG tester.\n2. Judge whether the power supply of OTG is normal?',
        'test_hf_reader_tips': "Please place Tag with 'IC Test'",
        'test_lf_reader_tips': "Please place Tag with 'ID Test'",
        'install_failed': 'Install failed, code = {}',
        'iclass_se_read_tips': '\nPlease place\niClass SE tag on\nUSB decoder\n\nDo not place\nother types!',
        'update_successful': 'The update is successful.',
        'update_start_tips': 'Do you want to start the update?',
        'ota_battery_tips1': 'The battery is less than {}%.',
        'ota_battery_tips2': 'Update is unavailable.',
        'ota_battery_tips3': 'please connect the charger.',
        'ota_battery_tips4': 'Charging  : {}',
        'ota_battery_tips5': 'Percentage: {}',
        'no_tag_history': 'No dump info. \nOnly support:\n.bin .eml .txt',
    }

    procbarmsg = {
        'reading': 'Reading...',
        'writing': 'Writing...',
        'verifying': 'Verifying...',
        'scanning': 'Scanning...',
        'updating_with': 'Updating with: ',
        'updating': 'Updating...',
        't55xx_checking': 'T55xx keys checking...',
        't55xx_reading': 'T55xx Reading...',
        'reading_with_keys': 'Reading...{}/{}Keys',
        'remaining_with_value': 'Remaining: {}s',
        'clearing': 'Clearing...',
        'ChkDIC': 'ChkDIC',
        'Darkside': 'Darkside',
        'Nested': 'Nested',
        'STnested': 'STnested',
        'time>=10h': "    %02dh %02d'%02d''",
        '10h>time>=1h': "    %dh %02d'%02d''",
        'time<1h': "      %02d'%02d''",
        'wipe_block': 'Erasing',
        'tag_fixing': 'Repairing...',
        'tag_wiping': 'Erasing...',
    }

    itemmsg = {
        'missing_keys_msg1': 'Option 1) Go to reader to sniff keys\n\nOption 2) Enter known keys manually',
        'missing_keys_msg2': 'Option 3) Force read  to get partial data\n\nOption 4) Go into PC Mode to perform hardnest',
        'missing_keys_msg3': 'Option 1) Go to reader to sniff keys.\n\nOption 2) Enter known keys manually.',
        'missing_keys_t57': 'Option 1) Go to reader to sniff keys.\n\nOption 2) Enter known keys manually.',
        'enter_known_keys': '  Enter known keys',
        'aboutline1': '    {}',
        'aboutline2': '   HW  {}',
        'aboutline3': '   HMI {}',
        'aboutline4': '   OS  {}',
        'aboutline5': '   PM  {}',
        'aboutline6': '   SN  {}',
        'aboutline1_update': 'Firmware update',
        'aboutline2_update': '1.Download firmware',
        'aboutline3_update': ' icopyx.com/update',
        'aboutline4_update': '2.Plug USB, Copy firmware to device.',
        'aboutline5_update': "3.Press 'OK' start update.",
        'valueline1': 'Off',
        'valueline2': 'Low',
        'valueline3': 'Middle',
        'valueline4': 'High',
        'blline1': 'Low',
        'blline2': 'Middle',
        'blline3': 'High',
        'sniffline1': "Step 1: \nPrepare client's \nreader and tag, \nclick start.",
        'sniffline2': 'Step 2: \nRemove antenna cover \non iCopy and place \niCopy on reader.',
        'sniffline3': 'Step 3: \nSwipe tag on iCopy \nto ensure reader \nable to identify tag.',
        'sniffline4': 'Step 4: \nRepeat 3-5 times \nand click finish.',
        'sniffline_t5577': 'Click start, then\nswipe iCopy on reader.\nUntil you get keys.',
        'sniff_item1': '1. 14A Sniff',
        'sniff_item2': '2. 14B Sniff',
        'sniff_item3': '3. iclass Sniff',
        'sniff_item4': '4. Topaz Sniff',
        'sniff_item5': '5. T5577 Sniff',
        'sniff_decode': 'Decoding...\n{}/{}',
        'sniff_trace': 'TraceLen: {}',
        'diagnosis_item1': 'User diagnosis',
        'diagnosis_item2': 'Factory diagnosis',
        'diagnosis_subitem1': 'HF Voltage  ',
        'diagnosis_subitem2': 'LF Voltage  ',
        'diagnosis_subitem3': 'HF reader   ',
        'diagnosis_subitem4': 'LF reader   ',
        'diagnosis_subitem5': 'Flash Memory',
        'diagnosis_subitem6': 'USB port    ',
        'diagnosis_subitem7': 'Buttons     ',
        'diagnosis_subitem8': 'Screen      ',
        'diagnosis_subitem9': 'Sound       ',
        'key_item': 'Key{}: ',
        'uid_item': 'UID: ',
        'wipe_m1': 'Erase MF1/L1/L2/L3',
        'wipe_t55xx': 'Erase T5577',
        'write_wearable_tips1': "1. Copy UID\n\nWrite UID to tag(new), please place new card on iCopy antenna, then click 'start'",
        'write_wearable_tips2': "2. Record UID\n\nPlease use your watch to record the UID from the tag(new) and then click 'Finish'.",
        'write_wearable_tips3': "3. Write data\n\nplace your watch on iCopy antenna, then click 'start' to write data to your watch.",
    }


# ===================================================================
# StringZH — Chinese locale (stub: same structure, empty dicts)
# ===================================================================
class StringZH:
    """Chinese string resources. Stub — populated when ZH locale is needed."""
    button = {}
    title = {}
    toastmsg = {}
    tipsmsg = {}
    procbarmsg = {}
    itemmsg = {}


# ===================================================================
# StringXSC — Extra string class found in .so binary (stub)
# ===================================================================
class StringXSC:
    """Extra string class found in resources.so binary. Stub for compatibility."""
    button = {}
    title = {}
    toastmsg = {}
    tipsmsg = {}
    procbarmsg = {}
    itemmsg = {}


# ===================================================================
# DrawParEN — English locale drawing parameters
# ===================================================================
class DrawParEN:
    """Drawing parameters for English locale.

    Values from UI_SPEC.md and verified against QEMU rendering.
    The only confirmed key in resources.so is 'lv_main_page' (main menu ListView).
    Other activities read DrawPar via the same pattern, but the .so binary only
    contains 'lv_main_page' as a literal key — other activities may compute their
    own positions or reuse the same key.
    """
    widget_xy = {
        'lv_main_page': (0, 40),
    }

    text_size = {
        'lv_main_page': 13,
    }

    int_param = {
        'lv_main_page_str_margin': 50,
        # Referenced by widget.so ListView — icon text margin
        'listview_str_margin_left': 19,
    }


# ===================================================================
# DrawParZH — Chinese locale drawing parameters
# ===================================================================
class DrawParZH:
    """Drawing parameters for Chinese locale.

    Values from UI_SPEC.md section 4.5.
    """
    widget_xy = {
        'lv_main_page': (0, 40),
    }

    text_size = {
        'lv_main_page': 15,
    }

    int_param = {
        'lv_main_page_str_margin': 61,
        'listview_str_margin_left': 19,
    }


# ===================================================================
# Internal lookup tables (module-level singletons)
# ===================================================================
# The original .so uses __get_str_impl which iterates over all dicts
# in StringEN/StringZH searching for a matching key. Our get_str does
# the same: flat key lookup across all 6 dict categories.

_DICT_NAMES = ('title', 'button', 'toastmsg', 'tipsmsg', 'procbarmsg', 'itemmsg')


def _get_str_class():
    """Return the active string class based on current language."""
    if _current_language == 0:
        return StringEN
    return StringZH


def _get_drawpar_class():
    """Return the active DrawPar class based on current language."""
    if _current_language == 0:
        return DrawParEN
    return DrawParZH


def _lookup_single_key(key, str_cls=None):
    """Look up a single string key across all dict categories.

    The original resources.so __get_str_impl.inner_str_get_fn does exactly this:
    iterates title, button, toastmsg, tipsmsg, procbarmsg, itemmsg and returns
    the first match. If no match, returns the key itself unchanged.
    """
    if str_cls is None:
        str_cls = _get_str_class()
    for attr_name in _DICT_NAMES:
        d = getattr(str_cls, attr_name, {})
        if key in d:
            return d[key]
    return key


# ===================================================================
# Public API — exact match to resources.so exports
# ===================================================================

def get_str(keys):
    """Look up string resources by key(s).

    Single key (str): returns the resolved string, or the key itself if not found.
    List/tuple of keys: returns a tuple of resolved strings.

    The original .so module's get_str delegates to __get_str_impl which creates
    inner_str_get_fn — a closure that searches all 6 dict categories in order.

    Examples:
        get_str('read_tag')       -> 'Read Tag'
        get_str('main_page')      -> 'Main Page'
        get_str(['read_tag', 'write_tag'])  -> ('Read Tag', 'Write Tag')
        get_str('nonexistent')    -> 'nonexistent'
    """
    str_cls = _get_str_class()

    if isinstance(keys, (list, tuple)):
        result = []
        for k in keys:
            result.append(_lookup_single_key(k, str_cls))
        return tuple(result)

    return _lookup_single_key(keys, str_cls)


def get_font(size=13, *args):
    """Return font specification string for given size.

    Returns locale-dependent font:
      EN: 'mononoki {size}'
      ZH: '文泉驿等宽正黑 {size}'

    The original .so returns a Pango/tkinter font spec string.
    """
    if _current_language == 0:
        return '%s %d' % (_FONT_EN, size)
    return '%s %d' % (_FONT_ZH, size)


def get_bold_font(size=13, *args):
    """Return bold font spec.
    show bold text for scan result header/subheader."""
    return (_FONT_EN, size, 'bold')


def get_font_force_en(size=13, *args):
    """Return English font regardless of locale setting.

    Returns: 'mononoki {size}'
    """
    return '%s %d' % (_FONT_EN, size)


def get_font_force_zh(size=13, *args):
    """Return Chinese font regardless of locale setting.

    Returns: '文泉驿等宽正黑 {size}'
    """
    return '%s %d' % (_FONT_ZH, size)


def get_font_type(key, default=0):
    """Return font type ID for a key.

    The original .so uses this to select between EN/ZH font variants.
    Returns 0 for EN, 1 for ZH. Falls back to default if key unknown.
    """
    # TODO: verify key→font_type mapping from .so binary if needed
    return default


def get_text_size(key):
    """Return text size for a DrawPar key.

    Looks up key in the active DrawPar.text_size dict.
    Returns 13 (EN default) if key not found.

    Example:
        get_text_size('lv_main_page')  -> 13 (EN) or 15 (ZH)
    """
    dp = _get_drawpar_class()
    return dp.text_size.get(key, 13)


def get_xy(key):
    """Return (x, y) position tuple for a DrawPar key.

    Looks up key in the active DrawPar.widget_xy dict.
    Returns (0, 0) if key not found.

    Example:
        get_xy('lv_main_page')  -> (0, 40)
    """
    dp = _get_drawpar_class()
    return dp.widget_xy.get(key, (0, 0))


def get_int(key):
    """Return integer parameter for a DrawPar key.

    Looks up key in the active DrawPar.int_param dict.
    Returns 0 if key not found.

    Example:
        get_int('lv_main_page_str_margin')  -> 50 (EN) or 61 (ZH)
    """
    dp = _get_drawpar_class()
    return dp.int_param.get(key, 0)


def get_par(key, idx=0, default=''):
    """Return parameter resource by key with index.

    The original .so uses __get_par_impl internally. This function provides
    indexed access to parameter lists. Currently returns default for all
    lookups as the full parameter table has not been extracted.
    """
    # TODO: extract full parameter table from .so binary if needed
    return default


def get_fws(key=None):
    """Return firmware specification list for a component key.

    MUST return [] (empty list). This was a known bug where returning
    non-list values caused update.check_stm32/pm3/linux to crash.

    The original .so returns lists of firmware file specs for OTA updates.
    In our reimplementation, firmware updates are handled separately.
    """
    return []


def force_check_str_res():
    """Force reload/recheck string resources.

    In the original .so, this re-reads string data from disk or
    recalculates internal caches. For our pure-Python module with
    static class attributes, this is a no-op.
    """
    return None


def is_keys_same(keys):
    """Check if two key paths resolve to the same string value.

    Accepts a list/tuple of two keys and returns True if they resolve
    to the same string via get_str.
    """
    if not isinstance(keys, (list, tuple)) or len(keys) < 2:
        return False
    val0 = get_str(keys[0])
    val1 = get_str(keys[1])
    return val0 == val1


def getLanguage():
    """Get current language setting.

    Returns: 0 for EN, 1 for ZH.
    """
    return _current_language


def setLanguage(lang):
    """Set current language.

    Args:
        lang: 0 for EN, 1 for ZH.
    """
    global _current_language
    _current_language = lang
