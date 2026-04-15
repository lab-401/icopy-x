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

"""template — scan/read result display renderer.

Reimplementation of template.so (Cython, ARM v7 LE).
              (MD5: 1b92d5017a72e8defb8c88396e1bbb19)

Renders tag info cards to the tkinter canvas after scan.so identifies a tag.
Shows tag family name, frequency, UID, SAK, ATQA, and other type-specific fields.

Imports: font (get_font_force_en lives in resources), re, resources, tagtypes
"""

import re

try:
    import resources
except ImportError:
    try:
        from lib import resources
    except ImportError:
        resources = None

try:
    from . import tagtypes
except ImportError:
    import tagtypes


# ---------------------------------------------------------------------------
# Constants — layout coordinates from original_current_ui ground truth
# (scenario_states.json, all anchor=nw, 240x240 display)
# ---------------------------------------------------------------------------
_SCREEN_W = 240
_LEFT_X = 18                 # left margin for ALL text (from ground truth)

_TITLE_Y = 48                # family name (e.g. "MIFARE")
_SUBTITLE_Y = 82             # display name (e.g. "M1 S50 1K (4B)")
_FREQ_Y = 106                # frequency line
_DATA_START_Y = 128          # first data line (UID)
_DATA_LINE_H = 23            # vertical spacing between data lines (128→151)

# Canvas tags for dedraw() cleanup
_TAG_TITLE = 'tpl_title'
_TAG_NAMESTR = 'tpl_namestr'  # display name / subtitle (must NOT contain 'title')
_TAG_FREQ = 'tpl_freq'
_TAG_DATA = 'tpl_data'

_HEX_RE = re.compile(r'[a-fA-F0-9 -]+')


# ---------------------------------------------------------------------------
# Low-level helper: __drawFinal — common header renderer
# ---------------------------------------------------------------------------
def __drawFinal(parent, family, frequency, display_name):
    """Render the common header block: family name, display name, frequency.

    Signature  0x000266c0 (4 parameters).
    Clears previous template items, then draws:
      - Family name in mononoki 22, anchor=nw at (18, 48)
      - Display name in mononoki 14, anchor=nw at (18, 82) (if not None)
      - Frequency line in mononoki 13, anchor=nw at (18, 106)
    """
    # Clear previous template content
    parent.delete(_TAG_TITLE)
    parent.delete(_TAG_NAMESTR)
    parent.delete(_TAG_FREQ)
    parent.delete(_TAG_DATA)

    # Family name — large, top-left aligned (anchor=nw)
    title_font = resources.get_font_force_en(22)
    parent.create_text(
        _LEFT_X, _TITLE_Y,
        text=family,
        font=title_font,
        anchor='nw',
        tags=_TAG_TITLE,
    )

    # Display name — medium, top-left aligned (skip if None)
    if display_name is not None:
        subtitle_font = resources.get_font_force_en(14)
        parent.create_text(
            _LEFT_X, _SUBTITLE_Y,
            text=display_name,
            font=subtitle_font,
            anchor='nw',
            tags=_TAG_NAMESTR,
        )

    # Frequency line — small, top-left aligned
    freq_font = resources.get_font_force_en(13)
    parent.create_text(
        _LEFT_X, _FREQ_Y,
        text='Frequency: {}'.format(frequency),
        font=freq_font,
        anchor='nw',
        tags=_TAG_FREQ,
    )


# ---------------------------------------------------------------------------
# Low-level helper: __drawDataLines — multi-line data renderer
# ---------------------------------------------------------------------------
def __drawDataLines(parent, lines, base_y=None, pady=None):
    """Render data lines below the header.

    Decompiled at 0x00024ba8. Iterates over a list of data items,
    rendering each non-None item with create_text at incrementing y.
    """
    if lines is None:
        return

    data_font = resources.get_font_force_en(13)
    y = base_y if base_y is not None else _DATA_START_Y
    step = pady if pady is not None else _DATA_LINE_H

    for item in lines:
        if item is not None:
            parent.create_text(
                _LEFT_X, y,
                text=item,
                font=data_font,
                anchor='nw',
                tags=_TAG_DATA,
            )
            y += step


# ---------------------------------------------------------------------------
# Low-level helper: __drawFinalByData — renders using data dict for lookup
# ---------------------------------------------------------------------------
def __drawFinalByData(data, parent):
    """Render header from data dict by looking up TYPE_TEMPLATE.

    Decompiled at 0x00025a78. Gets the tag type from data['type'],
    looks up TYPE_TEMPLATE, and calls __drawFinal with the tuple values.
    """
    if data is None:
        return
    typ = data.get('type', -1)
    if typ not in TYPE_TEMPLATE:
        return
    entry = TYPE_TEMPLATE[typ]
    frequency = entry[0]
    display_name = entry[1]
    family = entry[2]
    __drawFinal(parent, family, frequency, display_name)


# ---------------------------------------------------------------------------
# Internal draw functions — per-tag-type renderers
# ---------------------------------------------------------------------------

def __drawM1(data, parent):
    """MIFARE Classic renderer. Decompiled at 0x00023e68.

    Used for tag types: 0, 1, 25, 26, 41, 42, 43, 44.
    Renders: family header, UID, SAK + ATQA line.
    For M1_POSSIBLE types (43, 44): also renders manufacturer as subtitle
    when TYPE_TEMPLATE display_name is None.
    """
    if data is None:
        return

    typ = data.get('type', -1)

    # For M1_POSSIBLE types, use manufacturer as display_name if present
    # The TYPE_TEMPLATE has display_name=None for types 43/44 but the
    # scan result includes a manufacturer field (e.g. "Default 1K (4B)")
    if typ in TYPE_TEMPLATE:
        entry = TYPE_TEMPLATE[typ]
        frequency = entry[0]
        display_name = entry[1]
        family = entry[2]
        # Use manufacturer as display_name for POSSIBLE types
        if display_name is None and data.get('manufacturer'):
            display_name = data['manufacturer']
        __drawFinal(parent, family, frequency, display_name)
    else:
        __drawFinalByData(data, parent)

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # UID line
    uid = data.get('uid', '')
    if uid:
        parent.create_text(
            _LEFT_X, y,
            text='UID: {}'.format(uid),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # SAK + ATQA/ATS line
    sak = data.get('sak', '')
    if sak:
        ats = data.get('ats', '')
        if ats:
            # DESFire-style: show ATS instead of ATQA (single space before ATS)
            ats_display = ats
            if len(ats) > 6:
                ats_display = ats[:6] + '+'
            sak_line = 'SAK: {} ATS: {}'.format(sak, ats_display)
        else:
            # Standard M1: double space before ATQA label
            # SAK line always shows "ATQA" (verified via original firmware
            # dump_detail_mf1_1k: "SAK: 08  ATQA: 0004")
            atqa = data.get('atqa', '')
            sak_line = 'SAK: {}  ATQA: {}'.format(sak, atqa)
        parent.create_text(
            _LEFT_X, y,
            text=sak_line,
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Additional data lines if present
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawMFU(data, parent):
    """MIFARE Ultralight / NTAG renderer. Decompiled at 0x000236b0.

    Used for tag types: 2, 3, 4, 5, 6, 7.
    Renders: family header, UID, type-specific fields.
    """
    __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # UID line
    uid = data.get('uid', '')
    if uid:
        parent.create_text(
            _LEFT_X, y,
            text='UID: {}'.format(uid),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # SAK + ATQA if present (double space before ATQA label)
    sak = data.get('sak', '')
    if sak:
        atqa = data.get('atqa', '')
        parent.create_text(
            _LEFT_X, y,
            text='SAK: {}  ATQA: {}'.format(sak, atqa),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Additional data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawID(data, parent):
    """LF ID tag renderer. Decompiled at 0x00022880.

    Used for: 8-16, 19, 28-38, 45, 46 (LF ID tags + ISO15693).

        Renders header, then up to 2 data lines at fixed y positions:
        - y=128: UID/data line (from data['data'] or data['uid'])
        - y=151: Chipset line (default 'X' for 125KHZ tags)

    Data line formatting rules (from ground truth):
        - data['data'] starts with 'FC,CN:' or 'XSF(' -> render directly
        - data['data'] for Indala (type 10) -> 'RAW: <value>'
        - data['data'] otherwise -> 'UID: <value>'
        - data['uid'] (for ISO15693 types) -> 'UID: <uid>'
        - Strings > 19 chars are truncated to 13 chars + '...'

    Chipset rules (from ground truth):
        - Shown for all 125KHZ tags with chipset default 'X'
        - Skipped for 13.56MHZ tags (ISO15693 types 19, 46)
        - data['chipset'] overrides default if present
        - data['modulate'] shown instead when present (T55xx via __drawID)
    """
    __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    typ = data.get('type', -1)

    # --- Data line at y=128 ---
    data_val = data.get('data', '')
    uid_val = data.get('uid', '')
    display_line = None

    if data_val:
        # FC,CN, XSF, and Country lines are already formatted — show directly
        if (data_val.startswith('FC,CN:') or data_val.startswith('XSF(')
                or data_val.startswith('Country:')):
            display_line = data_val
        elif typ == 10:
            # Indala: prefix with 'RAW: '
            display_line = 'RAW: {}'.format(data_val)
        else:
            # Standard ID: prefix with 'UID: '
            display_line = 'UID: {}'.format(data_val)
        # Truncate long data['data'] strings: > 19 chars -> first 16 + '...'
        #
        if display_line is not None and len(display_line) > 19:
            display_line = display_line[:16] + '...'
    elif uid_val:
        # ISO15693 and similar: use 'uid' key directly
        display_line = 'UID: {}'.format(uid_val)

    if display_line is not None:
        parent.create_text(
            _LEFT_X, _DATA_START_Y,
            text=display_line,
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )

    # --- Chipset / Modulate line at y=151 ---
    # Determine frequency from TYPE_TEMPLATE to decide if chipset applies
    is_lf = False
    if typ in TYPE_TEMPLATE:
        freq = TYPE_TEMPLATE[typ][0]
        is_lf = (freq == '125KHZ')

    modulate = data.get('modulate')
    chipset = data.get('chipset')
    nc = data.get('nc')

    if nc:
        # FDX-B national code on second line
        parent.create_text(
            _LEFT_X, _DATA_START_Y + _DATA_LINE_H,
            text='NC: {}'.format(nc),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
    elif modulate:
        # Modulate line (e.g. T55xx scanned via __drawID path)
        parent.create_text(
            _LEFT_X, _DATA_START_Y + _DATA_LINE_H,
            text='Modulate: {}'.format(modulate),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
    elif chipset:
        # Explicit chipset from scan result
        parent.create_text(
            _LEFT_X, _DATA_START_Y + _DATA_LINE_H,
            text='Chipset: {}'.format(chipset),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
    elif is_lf:
        # Default chipset 'X' for LF tags
        parent.create_text(
            _LEFT_X, _DATA_START_Y + _DATA_LINE_H,
            text='Chipset: X',
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )

    # Additional data lines below chipset (if present)
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=_DATA_START_Y + 2 * _DATA_LINE_H)


def __draw_iclass(data, parent):
    """iCLASS renderer. Decompiled at 0x0001ea88.

    Used for tag types: 17, 18, 47.
    Renders: family header, manufacturer, block 7, data lines.

    'ICLASS_ELITE', 'ICLASS_LEGACY'. The original template generates
    the chip/display_name dynamically from the tag type and mutates
    data['chip']. TYPE_TEMPLATE[18] has None for display_name; the
    original overrides it with 'Elite' at render time.
    """
    if data is not None:
        try:
            import tagtypes
            typ = data.get('type', -1)
            if typ == tagtypes.ICLASS_ELITE:
                data['chip'] = 'Elite'
            elif typ == tagtypes.ICLASS_LEGACY:
                data['chip'] = 'Legacy'
        except (ImportError, AttributeError):
            pass
        # Override display_name from chip when TYPE_TEMPLATE has None
        typ = data.get('type', -1)
        if typ in TYPE_TEMPLATE:
            entry = TYPE_TEMPLATE[typ]
            frequency = entry[0]
            display_name = entry[1] or data.get('chip')
            family = entry[2]
            __drawFinal(parent, family, frequency, display_name)
    else:
        __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # CSN / UID line
    # NOT 'uid'. Fall back to 'uid' for compatibility.
    csn = data.get('csn', '') or data.get('uid', '')
    if csn:
        parent.create_text(
            _LEFT_X, y,
            text='CSN: {}'.format(csn),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Manufacturer line
    manufacturer = data.get('manufacturer', '')
    if manufacturer and manufacturer != 'unknown':
        parent.create_text(
            _LEFT_X, y,
            text=manufacturer,
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Block 7 if present
    blck7 = data.get('blck7', '')
    if blck7:
        parent.create_text(
            _LEFT_X, y,
            text='B0: {}'.format(blck7),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawT55xx(data, parent):
    """T5577 renderer. Decompiled at 0x00021640.

    Used for tag type: 23.
    T5577 has display_name = None in TYPE_TEMPLATE.

        content = [('T55x7', 82), ('Frequency: 125KHZ', 106),
                   ('Modulate: ASK', 128), ('B0: 00148040', 151)]
        cache = {chip: 'T55x7', modulate: 'ASK', b0: '00148040', ...}
    """
    if data is None:
        __drawFinalByData(data, parent)
        return

    typ = data.get('type', -1)
    if typ in TYPE_TEMPLATE:
        entry = TYPE_TEMPLATE[typ]
        frequency = entry[0]
        family = entry[2]
        # Use chip name as display_name when TYPE_TEMPLATE has None
        display_name = entry[1] or data.get('chip')
        __drawFinal(parent, family, frequency, display_name)
    else:
        __drawFinalByData(data, parent)

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # Modulate line
    modulate = data.get('modulate')
    if modulate:
        parent.create_text(
            _LEFT_X, y,
            text='Modulate: {}'.format(modulate),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Block 0 line
    b0 = data.get('b0')
    if b0:
        parent.create_text(
            _LEFT_X, y,
            text='B0: {}'.format(b0),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Additional data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawEM4x05(data, parent):
    """EM4305 renderer. Decompiled at 0x00021f60.

    Used for tag type: 24.
    EM4305 has display_name = None in TYPE_TEMPLATE.

        'SN: {}', 'CW: {}', 'chipset', 'Chipset: {}'
        EM4305 (family), EM4x05/EM4x69 (subtitle=chip),
        Frequency: 125KHZ, SN: AABBCCDD, CW: 600150E0
    """
    if data is None:
        __drawFinalByData(data, parent)
        return

    typ = data.get('type', -1)
    if typ in TYPE_TEMPLATE:
        entry = TYPE_TEMPLATE[typ]
        frequency = entry[0]
        family = entry[2]
        # Use chip name as display_name when TYPE_TEMPLATE has None
        # Same pattern as __drawT55xx (line 484)
        display_name = entry[1] or data.get('chip')
        __drawFinal(parent, family, frequency, display_name)
    else:
        __drawFinalByData(data, parent)

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # SN line — ground truth: template.so string 'SN: {}'
    sn = data.get('sn')
    if sn:
        parent.create_text(
            _LEFT_X, y,
            text='SN: {}'.format(sn),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # CW line — ground truth: template.so string 'CW: {}'
    cw = data.get('cw')
    if cw:
        parent.create_text(
            _LEFT_X, y,
            text='CW: {}'.format(cw),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Additional data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawLEGIC_MIM256(data, parent):
    """LEGIC MIM256 renderer. Decompiled at 0x00020d20.

    Used for tag type: 20.
    """
    __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # UID line
    uid = data.get('uid', '')
    if uid:
        parent.create_text(
            _LEFT_X, y,
            text='UID: {}'.format(uid),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # MCD if present
    mcd = data.get('mcd', '')
    if mcd:
        parent.create_text(
            _LEFT_X, y,
            text='MCD: {}'.format(mcd),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # MSN if present
    msn = data.get('msn', '')
    if msn:
        parent.create_text(
            _LEFT_X, y,
            text='MSN: {}'.format(msn),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawFelica(data, parent):
    """FeliCa renderer. Decompiled at 0x00020568.

    Used for tag type: 21.
    """
    __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # IDM line
    idm = data.get('idm', '') or data.get('uid', '')
    if idm:
        parent.create_text(
            _LEFT_X, y,
            text='IDM: {}'.format(idm),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __draw14B(data, parent):
    """ISO14443-B / STR512 renderer. Decompiled at 0x0001fdb0.

    Used for tag type: 22.
    """
    __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # UID line
    uid = data.get('uid', '')
    if uid:
        parent.create_text(
            _LEFT_X, y,
            text='UID: {}'.format(uid),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # Data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


def __drawTopaz(data, parent):
    """Topaz / DESFire / HF14A Other renderer. Decompiled at 0x0001f490.

    Used for tag types: 27, 39, 40.
    """
    __drawFinalByData(data, parent)
    if data is None:
        return

    data_font = resources.get_font_force_en(13)
    y = _DATA_START_Y

    # UID line
    uid = data.get('uid', '')
    if uid:
        parent.create_text(
            _LEFT_X, y,
            text='UID: {}'.format(uid),
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H

    # SAK + ATQA/ATS if present
    sak = data.get('sak', '')
    if sak:
        ats = data.get('ats', '')
        if ats:
            # DESFire-style: show ATS instead of ATQA (single space before ATS)
            ats_display = ats
            if len(ats) > 6:
                ats_display = ats[:6] + '+'
            sak_line = 'SAK: {} ATS: {}'.format(sak, ats_display)
        else:
            # Standard: double space before ATQA label
            atqa = data.get('atqa', '')
            sak_line = 'SAK: {}  ATQA: {}'.format(sak, atqa)
        parent.create_text(
            _LEFT_X, y,
            text=sak_line,
            font=data_font,
            anchor='nw',
            tags=_TAG_DATA,
        )
        y += _DATA_LINE_H
    else:
        # No SAK — check for standalone ATQA (Topaz type 27)
        atqa = data.get('atqa', '')
        if atqa:
            parent.create_text(
                _LEFT_X, y,
                text='ATQA: {}'.format(atqa),
                font=data_font,
                anchor='nw',
                tags=_TAG_DATA,
            )
            y += _DATA_LINE_H

    # Data lines
    lines = data.get('lines')
    if lines:
        __drawDataLines(parent, lines, base_y=y)


# ---------------------------------------------------------------------------
# TYPE_TEMPLATE — tag type ID -> (frequency, display_name, family, draw_func)
# Complete 48 entries from spec section 2, cross-referenced with
# ---------------------------------------------------------------------------
TYPE_TEMPLATE = {
    0:  ('13.56MHZ', 'M1 S70 4K (4B)',    'MIFARE',       __drawM1),
    1:  ('13.56MHZ', 'M1 S50 1K (4B)',    'MIFARE',       __drawM1),
    2:  ('13.56MHZ', 'Ultralight',         'MIFARE',       __drawMFU),
    3:  ('13.56MHZ', 'Ultralight C',       'MIFARE',       __drawMFU),
    4:  ('13.56MHZ', 'Ultralight EV1',     'MIFARE',       __drawMFU),
    5:  ('13.56MHZ', 'NTAG213 144b',       'NTAG',         __drawMFU),
    6:  ('13.56MHZ', 'NTAG215 504b',       'NTAG',         __drawMFU),
    7:  ('13.56MHZ', 'NTAG216 888b',       'NTAG',         __drawMFU),
    8:  ('125KHZ',   'EM410x ID',          'EM Marin',     __drawID),
    9:  ('125KHZ',   'HID Prox ID',        'HID Prox',     __drawID),
    10: ('125KHZ',   'Indala ID',           'HID Indala',   __drawID),
    11: ('125KHZ',   'AWID ID',             'AWID',         __drawID),
    12: ('125KHZ',   'IO Prox ID',          'IoProx',       __drawID),
    13: ('125KHZ',   'G-Prox II ID',        'G-Prox',       __drawID),
    14: ('125KHZ',   'Securakey ID',         'SecuraKey',    __drawID),
    15: ('125KHZ',   'Viking ID',            'Viking',       __drawID),
    16: ('125KHZ',   'Pyramid ID',           'Pyramid',      __drawID),
    17: ('13.56MHZ', 'Legacy',              'iCLASS',       __draw_iclass),
    18: ('13.56MHZ', None,                  'iCLASS',       __draw_iclass),
    19: ('13.56MHZ', 'ISO15693 ICODE',      'ICODE',        __drawID),
    20: ('13.56MHZ', 'Legic MIM256',        'Legic',        __drawLEGIC_MIM256),
    21: ('13.56MHZ', 'Felica',              'Felica',       __drawFelica),
    22: ('13.56MHZ', 'ISO14443-B',          'STR512',       __draw14B),
    23: ('125KHZ',   None,                  'T5577',        __drawT55xx),
    24: ('125KHZ',   None,                  'EM4305',       __drawEM4x05),
    25: ('13.56MHZ', 'M1 Mini 0.3K',       'MIFARE',       __drawM1),
    26: ('13.56MHZ', 'M1 Mini 0.3K',       'MIFARE',       __drawM1),
    27: ('13.56MHZ', 'Topaz',              'TOPAZ',        __drawTopaz),
    28: ('125KHZ',   'Animal ID',           'FDX-B',        __drawID),
    29: ('125KHZ',   'GALLAGHER ID',        'Gallagher',    __drawID),
    30: ('125KHZ',   'Jablotron ID',        'Jablotron',    __drawID),
    31: ('125KHZ',   'KERI ID',             'Keri',         __drawID),
    32: ('125KHZ',   'NEDAP ID',            'Nedap',        __drawID),
    33: ('125KHZ',   'Noralsy ID',          'Noralsy',      __drawID),
    34: ('125KHZ',   'PAC/Stanley ID',      'PAC/Stanley',  __drawID),
    35: ('125KHZ',   'Paradox ID',           'Paradox',      __drawID),
    36: ('125KHZ',   'Presco ID',            'Presco',       __drawID),
    37: ('125KHZ',   'Visa2000 ID',          'Visa2000',     __drawID),
    38: ('125KHZ',   'Hitag',               'HITAG',        __drawID),
    39: ('13.56MHZ', 'DESFire',             'MIFARE',       __drawTopaz),
    40: ('13.56MHZ', 'ISO/IEC 14443-A',     'ISO14443-A',   __drawTopaz),
    41: ('13.56MHZ', 'M1 S70 4K (7B)',      'MIFARE',       __drawM1),
    42: ('13.56MHZ', 'M1 S50 1K (7B)',      'MIFARE',       __drawM1),
    43: ('13.56MHZ', None,                  'MF POSSIBLE',  __drawM1),
    44: ('13.56MHZ', None,                  'MF POSSIBLE',  __drawM1),
    45: ('125KHZ',   'NexWatch ID',          'NexWatch',     __drawID),
    46: ('13.56MHZ', 'ISO15693 ST SA',       'ISO15693',     __drawID),
    47: ('13.56MHZ', 'iCLASS SE',           'iCLASS',       __draw_iclass),
}


# ---------------------------------------------------------------------------
# Exported functions
# ---------------------------------------------------------------------------

def draw(typ, data, parent):
    """Draw a tag info card on the canvas.

    Signature  at 0x0001e1d0.

    Args:
        typ:    integer tag type ID (0-47)
        data:   dict with scan result data (keys depend on tag type),
                or None for header-only rendering
        parent: tkinter Canvas to draw on

    Behavior
    1. Looks up typ in TYPE_TEMPLATE
    2. If not found: returns None (silent)
    3. If draw_func is None: returns None
    4. If data is None: renders just the header (family, display name, frequency)
    5. If data is not None: calls draw_func(data, parent) for full rendering
    """
    if typ not in TYPE_TEMPLATE:
        return None

    entry = TYPE_TEMPLATE[typ]
    draw_func = entry[3]

    if draw_func is None:
        return None

    if data is None:
        # Header-only rendering: family name, display name, frequency
        frequency, display_name, family = entry[0], entry[1], entry[2]
        __drawFinal(parent, family, frequency, display_name)
        return

    # Ensure type key is set for __drawFinalByData lookup
    if 'type' not in data:
        data['type'] = typ

    draw_func(data, parent)


def dedraw(parent):
    """Clear all template-drawn items from the canvas.

    Signature  at 0x0001d710.
    Calls parent.delete() three times to remove:
      - Title/family text area
      - Frequency line
      - Data lines (UID, SAK, ATQA, etc.)
    """
    parent.delete(_TAG_TITLE)
    parent.delete(_TAG_NAMESTR)
    parent.delete(_TAG_FREQ)
    parent.delete(_TAG_DATA)


def create_by_parent(parent, tag):
    """Create a display name string from tag type.

    Signature  at 0x0001d248.

    Args:
        parent: tkinter Canvas (or widget)
        tag:    integer tag type ID

    Returns:
        str: display name string for the tag type
    """
    name = tagtypes.getName(tag)
    if name is not None:
        return name
    return str(tag)
