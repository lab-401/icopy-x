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
"""Paxton Clone&Down plugin for iCopy-XS.
Copyright (c) 2026: jareckib

Explicit user attempts renew the executor recovery budget when supported.
Transport failures during reads request one managed reader restart, followed
by the original error and a manual retry. A failed restart offers Exit only.
Writes are never replayed automatically, and verification never renews the
recovery budget.
"""

import re
import os
import tempfile
import time
import functools



from lib._constants import SCREEN_W
from lib import resources

PAXTON_KEY = 'BDF5E846'

DUMP_DIR = '/mnt/upan/dump/paxton'
LOG_PATH = os.path.join(DUMP_DIR, 'Paxton_log.txt')

READ_TIMEOUT = 20000
WRITE_TIMEOUT = 10000
CLONE_TIMEOUT = 15000
SEARCH_TIMEOUT = 5000
VERIFY_TIMEOUT = 5000

PICK_ROWS = 5
LOG_SEP = '--------------------------'

try:
    from lib.input_txt import FreeTextInput
except Exception:
    FreeTextInput = None


class PaxtonTextInput(FreeTextInput if FreeTextInput is not None else object):
    """Keep long names inside the native editor without shrinking the font."""
    def _redraw(self):
        import tkinter.font as tkfont
        c = self._canvas
        c.delete('_txt_input')
        self._font = ('Courier New', 12)
        f = tkfont.Font(font=self._font)
        label = self._label + ' '
        x = 10 + f.measure(label)
        available = 230 - x
        start = 0
        while start < self._cursor and sum(f.measure(ch) + 2 for ch in self._chars[start:self._cursor + 1]) > available:
            start += 1
        c.create_text(8, self._y_offset, text=label, font=self._font,
                      fill='#606060', anchor='w', tags='_txt_input')
        for index in range(start, len(self._chars)):
            ch = self._chars[index]
            width = f.measure(ch) + 2
            if x + width > 230:
                break
            item = c.create_text(x, self._y_offset, text=ch, font=self._font,
                                 fill=self._text_color, anchor='w', tags='_txt_input')
            box = c.bbox(item)
            if index == self._cursor and box:
                c.create_line(box[0], box[3] + 1, box[2], box[3] + 1,
                              fill=self._text_color, tags='_txt_input')
            x += width


def _hex_to_bin(hex_string):
    return ''.join('{:04b}'.format(int(c, 16)) for c in hex_string.upper())


def _process_block(block_hex):
    binary = _hex_to_bin(block_hex)[:-2]
    chunks = [binary[i:i+5] for i in range(0, len(binary), 5)]
    return [c[1:] for c in chunks if len(c) == 5]


def calculate_id_net(blocks):
    nibbles = [format(int(n, 2), 'X') for blk in blocks for n in _process_block(blk)]
    selected = []
    for h in nibbles:
        if h == 'F':
            break
        selected.append(h)
    if not selected:
        return None, None
    combined = ''.join(selected)
    if not combined.isdigit():
        return None, None
    d = int(combined)
    return d, '{:010X}'.format(d)


def calculate_id_switch(blocks):
    dec = [int(n, 2) for blk in blocks for n in _process_block(blk)]
    if len(dec) < 15:
        return None, None
    nums = [str(dec[p - 1]) for p in [9, 11, 13, 15, 2, 4, 6, 8]]
    d = int(''.join(nums))
    return d, '{:010X}'.format(d)


def _parse_hitag_blocks(output):
    blocks = {}
    if not output:
        return blocks
    for line in output.splitlines():
        m = re.match(r'\s*(\d+)\s*/0x0[0-7]\s*\|\s*([0-9A-Fa-f]{2}\s+){3}[0-9A-Fa-f]{2}', line)
        if not m:
            m = re.match(r'\s*(\d+)\s*\|\s*([0-9A-Fa-f]{8})', line)
        if m:
            blk = int(m.group(1))
            data = re.search(r'([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})', line)
            if data:
                blocks[blk] = ''.join(data.groups()).upper()
            else:
                data2 = re.search(r'\|\s*([0-9A-Fa-f]{8})', line)
                if data2:
                    blocks[blk] = data2.group(1).upper()
    return blocks


def _parse_uid(output):
    if not output:
        return ''
    for line in output.splitlines():
        m = re.search(r'UID[\.\s]+([0-9A-Fa-f]{8})', line)
        if m:
            return m.group(1).upper()
    return ''


def _parse_type(output):
    if not output:
        return ''
    for line in output.splitlines():
        m = re.search(r'TYPE[\.\s]+(.+)', line)
        if m:
            t = m.group(1).strip()
            if t:
                return t
    return ''


def _ensure_dirs():
    try:
        if not os.path.exists('/mnt/upan'):
            return False
        os.makedirs(DUMP_DIR, mode=0o775, exist_ok=True)
        return True
    except Exception:
        return False


def _log_read_entries():
    try:
        with open(LOG_PATH, 'r') as f:
            lines = f.read().splitlines()
    except Exception:
        return []

    entries = []
    cur = None

    def _new(name):
        return {'name': name, 'date': '', 'mode': 'paxton', 'blocks': {},
                'em_id': '', 'variant': '', 'uid': ''}

    for raw in lines:
        line = raw.strip()
        if line.startswith('Name:'):
            if cur is not None:
                entries.append(cur)
            cur = _new(line[5:].strip())
            continue
        if cur is None:
            continue
        if line.startswith('---'):
            entries.append(cur)
            cur = None
            continue
        m = re.match(r'Mode:\s*(.+)$', line)
        if m:
            cur['mode'] = m.group(1).strip().lower()
            continue
        m = re.match(r'Date:\s*(.+)$', line)
        if m:
            cur['date'] = m.group(1).strip()
            continue
        m = re.match(r'Block\s+(\d+):\s*([0-9A-Fa-f]{8})\b', line)
        if m:
            cur['blocks'][int(m.group(1))] = m.group(2).upper()
            continue
        m = re.match(r'EM4102 ID:\s*([0-9A-Fa-f]{10})\b', line)
        if m:
            cur['em_id'] = m.group(1).upper()
            continue
        m = re.match(r'Variant:\s*(.+)$', line)
        if m:
            v = m.group(1).strip()
            cur['variant'] = '' if v.lower() == 'nil' else v
            continue
        m = re.match(r'UID:\s*([0-9A-Fa-f]{8})\b', line)
        if m:
            cur['uid'] = m.group(1).upper()
            continue
    if cur is not None:
        entries.append(cur)
    return entries


def _log_paxton_entries():
    good = []
    for e in _log_read_entries():
        if e['mode'] != 'paxton' or not e['name']:
            continue
        if not all(re.match(r'^[0-9A-F]{8}$', e['blocks'].get(i, ''))
                   for i in range(4, 8)):
            continue
        good.append(e)
    good.sort(key=lambda e: e['name'])
    return good


def _log_name_exists(name):
    for e in _log_paxton_entries():
        if e['name'] == name:
            return True
    return False


def _log_save(name, blocks, em_id, variant, uid):
    if not _ensure_dirs():
        return False
    try:
        from datetime import datetime
        record = ['Name: {}'.format(name),
                  'Date: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                  'Mode: paxton']
        record.extend('Block {}: {}'.format(i, blocks[i]) for i in range(1, 8)
                      if re.fullmatch(r'[0-9A-Fa-f]{8}', blocks.get(i, '')))
        record.extend(['EM4102 ID: {}'.format(em_id or 'nil'),
                       'Variant: {}'.format(variant or 'nil'),
                       'UID: {}'.format(uid or 'nil'), LOG_SEP])
        if not all(re.fullmatch(r'[0-9A-Fa-f]{8}', blocks.get(i, '')) for i in range(4, 8)):
            return False
        existing = b''
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'rb') as f:
                existing = f.read()
        # Preserve legacy records and incomplete tails instead of silently deleting data.
        # A new record starts on a fresh line; readers ignore invalid old entries.
        if existing and not existing.endswith(b'\n'):
            existing += b'\n'
        fd, tmp = tempfile.mkstemp(prefix='.paxton_', dir=DUMP_DIR)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(existing)
                f.write(('\n'.join(record) + '\n').encode('utf-8'))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, LOG_PATH)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True
    except Exception:
        return False


def _dump_save(blocks, uid, variant):
    if not _ensure_dirs():
        return None
    try:
        if not re.fullmatch(r'[0-9A-Fa-f]{8}', uid or '') or not all(
                re.fullmatch(r'[0-9A-Fa-f]{8}', blocks.get(i, '')) for i in range(1, 8)):
            return None  # Never fabricate missing memory in a complete dump.
        uid = uid.upper()
        b5 = blocks[5]
        prefix = 'Paxton-ID_{}_{}_'.format(uid, b5)
        top = 0
        for fn in os.listdir(DUMP_DIR):
            m = re.match(r'^' + re.escape(prefix) + r'(\d+)\.txt$', fn)
            if m:
                top = max(top, int(m.group(1)))
        fname = '{}{}.txt'.format(prefix, top + 1)
        raw = ''.join(blocks[i] for i in range(1, 8))
        ptype = 'switch2' if (variant or '').lower().startswith('switch') else 'net2'
        with open(os.path.join(DUMP_DIR, fname), 'w') as f:
            f.write('{}\n{}\ntype={}\n'.format(raw, uid, ptype))
        return fname
    except Exception:
        return None


class PaxtonCloneDownPlugin(object):

    def __init__(self, host=None):
        self.host = host
        self._pick = []
        self._pick_idx = 0
        self._txt = None
        self._txt_mode = None
        self._pending_log_name = ''
        self._pending_find_query = ''
        self._paxton_search_output = ''
        self._paxton_search_chipset = ''
        self._read_transport_failed = False

    _screen_actions = {'error_retry_processing': 'run:do_error_retry', 'init': 'call:do_init', 'find_name': 'call:show_txt_input_find', 'log_name': 'call:show_txt_input_log', 'log_name_processing': 'run:do_save_captured_log', 'find_name_processing': 'run:do_find_captured', 'paxton_prepare': 'run:do_prepare_paxton', 'paxton_writing': 'run:do_write_paxton', 'paxton_verifying': 'run:do_verify_paxton', 'em_prepare': 'run:do_prepare_em4102', 'em_search': 'run:do_quick_search_t5577', 'em_detect': 'run:do_detect_t5577', 'em_writing': 'run:do_write_em4102', 'em_verifying': 'run:do_verify_em4102', 'paxton_detect': 'run:do_detect_pcf7936', 'paxton_search': 'run:do_search_pcf7936', 'recovering_reader': 'run:do_recover_reader', 'loading_logs': 'run:do_load_log'}

    _hint_templates = ['OK - read original fob', 'OK - write next PCF7936', 'OK - Next T5577', 'A+OK - open list', 'Name+OK - search', 'SRW - back to menu', 'OK - Save log']

    def enter_screen(self):
        state = self.host._current_state_id
        if state not in ('find_name', 'log_name') and self._txt is not None:
            self._txt.hide()
            self._txt = None
        self._clear_mode_label()
        self.draw_screen()
        action = self._screen_actions.get(state)
        if action:
            self.host._execute_action(action)

    def on_destroy(self):
        if self._txt is not None:
            self._txt.hide()
            self._txt = None
        self._clear_mode_label()

    def draw_menu(self):
        c = self.host.getCanvas()
        for item in c.find_withtag('_jr_content'):
            if c.type(item) == 'text':
                c.itemconfigure(item, font=('Courier New', 12))

    def menu_up(self):
        self.host._execute_action('scroll:-1')
        self.draw_menu()

    def menu_down(self):
        self.host._execute_action('scroll:1')
        self.draw_menu()

    def _wrap_ui(self, text, font, width=222):
        rows = []
        line = ''
        for word in text.split():
            if line and font.measure(line + ' ' + word) > width:
                rows.append(line)
                line = ''
            while font.measure(word) > width:
                stop = 1
                while stop < len(word) and font.measure(word[:stop + 1]) <= width:
                    stop += 1
                rows.append(word[:stop])
                word = word[stop:]
            line += (' ' if line else '') + word
        if line:
            rows.append(line)
        return rows

    def draw_screen(self):
        import tkinter.font as tkfont
        c = self.host.getCanvas()
        state = self.host._current_state_id
        if state == 'menu':
            self.draw_menu()
            return
        if state in ('readed_clone', 'readed_down', 'loaded', 'clone_ok'):
            self._draw_paxton_result(state)
            return
        texts = [c.itemcget(i, 'text').strip() for i in c.find_withtag('_jr_content')
                 if c.type(i) == 'text' and c.itemcget(i, 'text').strip()]
        error = state in ('error', 'recovery_failed')
        large_body = state in (
            'pick', 'read_down', 'down_ok', 'saved', 'paxton_prepare',
            'paxton_writing', 'paxton_verifying', 'paxton_detect',
            'paxton_search', 'paxton_found', 'paxton_other',
            'em_prepare', 'em_search', 'em_detect', 'em_writing',
            'em_verifying', 'recovering_reader', 'loading_logs',
        )
        size = 16 if error or state == 'read_clone' else 14 if large_body else 12
        self._ui_face = ('Courier New', size)
        font = tkfont.Font(font=self._ui_face)
        self._ui_step = max(19, font.metrics('linespace') + 1)
        hints = []
        hint_texts = {self.host.tr(t).strip() for t in self._hint_templates}
        groups = []
        for text in texts:
            if not error and text in hint_texts:
                hints.extend(self._wrap_ui(text, tkfont.Font(font=('Courier New', 12))))
                continue
            for field in text.split(' | '):
                if state == 'pick':
                    # Abbreviate only the list preview; the loaded name stays complete.
                    selected = field.startswith('> ') and field.endswith(' <')
                    name = field[2:-2] if selected else field
                    suffix = ' <' if selected else ''
                    prefix = '> ' if selected else ''
                    if font.measure(prefix + name + suffix) > 222:
                        while name and font.measure(prefix + name + '…' + suffix) > 222:
                            name = name[:-1]
                        field = prefix + name + '…' + suffix
                    groups.append([('text', field, '#303030')])
                    continue
                if error:
                    groups.extend([[('text', row, '#D62636')] for row in self._wrap_ui(field, font)])
                    continue
                match = re.match(r'^([^:]+:)\s*(.*)$', field)
                if match:
                    label, value = match.groups()
                    numeric = bool(re.fullmatch(r'(?:[0-9A-Fa-f]{8,}|[0-9]+)', value))
                    if state in ('paxton_found', 'log_name'):
                        label = label.rstrip(': ') + ':'
                        if (state == 'log_name' or label == 'UID:') and re.fullmatch(r'(?:[0-9A-Fa-f]{2})+', value):
                            value = ' '.join(value[i:i+2].upper() for i in range(0, len(value), 2))
                    color = '#1647D6' if numeric else '#303030'
                    if font.measure(label + ' ' + value) <= 222:
                        groups.append([('pair', label, value, color)])
                    else:
                        groups.append([('text', label, '#606060')] +
                                      [('text', row, color) for row in self._wrap_ui(value, font)])
                else:
                    groups.extend([[('text', row, '#303030')] for row in self._wrap_ui(field, font)])
        if state == 'log_name':
            hints = [self.host.tr('OK - Save log')]
        self._ui_hints = hints
        # Reserve editor, hints and the native DD2 page indicator separately.
        bottom = 103 if state == 'log_name' else 151 if state == 'find_name' else (174 - 19 * max(0, len(hints) - 1) if hints else 196)
        capacity = PICK_ROWS + 1 if state == 'pick' else max(1, min(6, int((bottom - 43) / self._ui_step)))
        total = sum(len(g) for g in groups)
        if total > capacity:
            bottom = min(bottom, 154 - 19 * max(0, len(hints) - 1))
            capacity = max(1, int((bottom - 43) / self._ui_step) - 1)
        pages = [[]]
        for group in groups:
            if pages[-1] and len(pages[-1]) + len(group) > capacity:
                pages.append([])
            # Field labels and their complete values remain together.
            pages[-1].extend(group)
        self._ui_pages = pages
        self._ui_page = 0
        self._draw_ui_page()

    def _draw_paxton_result(self, state):
        """DD2 Paxton Details font, spaced bytes and complete memory sections."""
        import tkinter.font as tkfont
        self._ui_face = ('Courier New', 14 if state == 'clone_ok' else 12)
        font = tkfont.Font(font=self._ui_face)
        self._ui_step = max(19, font.metrics('linespace') + 1)

        def field(label, value, is_hex=False, is_number=False):
            label = label.rstrip(': ') + ':'
            value = str(value or '')
            if is_hex and re.fullmatch(r'(?:[0-9A-Fa-f]{2})+', value):
                value = ' '.join(value[i:i+2].upper() for i in range(0, len(value), 2))
            elif is_hex:
                value = 'N/A'
            color = '#1647D6' if (is_hex and value != 'N/A') or is_number else '#303030'
            if font.measure(label + ' ' + value) <= 222:
                return [('pair', label, value, color)]
            return [('text', label, '#606060')] + [
                ('text', row, color) for row in self._wrap_ui(value, font)]

        meta = [field(self.host.tr('Type:'), self.host.get_var('tag_variant', '')),
                field(self.host.tr('UID:'), self.host.get_var('uid', ''), True)]
        if self.host.get_var('em_id', ''):
            meta.append(field(self.host.tr('EM ID:'), self.host.get_var('em_id'), True))
        sections = [meta,
                    [field(label, self.host.get_var('block{}'.format(i), ''), True)
                     for i, label in ((1, self.host.tr('Password:')),
                                      (2, self.host.tr('Key/Pwd:')),
                                      (3, self.host.tr('Config:')))],
                    [field(self.host.tr('User B{}:').format(i),
                           self.host.get_var('block{}'.format(i), ''), True)
                     for i in range(4, 8)]]
        if state == 'readed_clone':
            sections = [sections[0] + sections[1], sections[2]]
        if state == 'clone_ok':
            # Preserve Clone OK fields; no extra metadata from the source dump.
            sections = [[meta[0], meta[1],
                         field(self.host.tr('Fobs written:'),
                               self.host.get_var('clone_count', '0'), is_number=True)],
                        [field('B{}:'.format(i), self.host.get_var('block{}'.format(i), ''), True)
                         for i in range(4, 8)]]
        pages = []
        for section in sections:
            page = []
            for group in section:
                if page and len(page) + len(group) > (6 if state == 'readed_clone' else 4):
                    pages.append(page)
                    page = []
                page.extend(group)
            if page:
                pages.append(page)
        self._ui_pages = pages
        self._ui_page = 0
        hint = (self.host.tr('Put PCF7936 to write') if state == 'readed_clone' else
                self.host.tr('OK - Next PCF7936') if state == 'clone_ok' else
                self.host.tr('Put T5577 to write') if state == 'readed_down' else
                self.host.tr('SRW - back to menu'))
        self._ui_hints = self._wrap_ui(hint, tkfont.Font(font=('Courier New', 10 if state in ('readed_clone', 'readed_down') else 12)))
        self._draw_ui_page()

    def _draw_ui_page(self):
        import tkinter.font as tkfont
        c = self.host.getCanvas()
        c.delete('_jr_content')
        rows = self._ui_pages[self._ui_page]
        font = tkfont.Font(font=self._ui_face)
        step = self._ui_step
        state = self.host._current_state_id
        pages = max(1, (len(self._pick) + PICK_ROWS - 1) // PICK_ROWS) if state == 'pick' else len(self._ui_pages)
        display_page = self._pick_idx // PICK_ROWS if state == 'pick' else self._ui_page
        editor = state == 'log_name'
        y = 43 if editor or len(rows) >= 5 else 62 if len(rows) == 4 else 81 if len(rows) >= 2 else 120 - font.metrics('linespace') / 2
        if state == 'pick' or (state == 'readed_clone' and self._ui_page == 0):
            y = 43
        pairs = [row for row in rows if row[0] == 'pair']
        label_width = max((font.measure(row[1]) for row in pairs), default=0)
        value_width = max((font.measure(row[2]) for row in pairs), default=0)
        gap = font.measure(' ')
        aligned = label_width + gap + value_width <= 222
        x = (240 - label_width - gap - value_width) / 2
        first_items = []
        for index, row in enumerate(rows):
            before = set(c.find_withtag('_jr_content'))
            if row[0] == 'pair':
                left = x if aligned else (240 - font.measure(row[1] + ' ' + row[2])) / 2
                value_x = left + (label_width if aligned else font.measure(row[1])) + gap
                if state in ('readed_clone', 'readed_down', 'loaded', 'clone_ok', 'paxton_found', 'log_name'):
                    left = gap
                    value_x = left + font.measure(row[1]) + gap
                c.create_text(left, y, text=row[1], font=self._ui_face, fill='#606060', anchor='nw', tags='_jr_content')
                c.create_text(value_x, y, text=row[2], font=self._ui_face, fill=row[3], anchor='nw', tags='_jr_content')
            else:
                c.create_text(120, y, text=row[1], font=self._ui_face, fill=row[2], anchor='n', tags='_jr_content')
            created = set(c.find_withtag('_jr_content')) - before
            if index == 0:
                first_items = list(created)
            y += step
        # Positions and style match Dump Diff 2 _auto_draw_memory.
        if pages > 1:
            c.create_text(120, 190, text=self.host.tr('Page {}/{}').format(display_page + 1, pages),
                          anchor='center', fill='#1647D6', font=('Courier New', 9), tags=('_jr_content', '_paxton_nav'))
            if display_page > 0:
                arrow = c.create_text(235, 43, text='▲', anchor='ne', fill='#1647D6', font=('Arial', 9), tags=('_jr_content', '_paxton_nav'))
                box = c.bbox(arrow)
                if any(c.bbox(i)[2] > box[0] and c.bbox(i)[1] < box[3] for i in first_items):
                    for item in c.find_withtag('_jr_content'):
                        if '_paxton_nav' not in c.gettags(item):
                            c.move(item, 0, step)
            if display_page + 1 < pages:
                c.create_text(235, 198, text='▼', anchor='se', fill='#1647D6', font=('Arial', 9), tags=('_jr_content', '_paxton_nav'))
        bottom = 178 if pages > 1 else 195
        if state == 'log_name':
            bottom = 180
        if state == 'down_ok' or (state in ('clone_ok', 'log_name') and pages > 1):
            bottom = 181
        for index, text in enumerate(reversed(self._ui_hints)):
            hint_item = c.create_text(120, bottom - index * 19, text=text, anchor='s',
                          font=('Courier New', 9 if state == 'find_name' else 10 if state in ('clone_ok', 'down_ok', 'readed_clone', 'readed_down') else 12),
                          fill='#1647D6' if state == 'find_name' else '#606060', tags=('_jr_content', '_paxton_hint'))
        if pages > 1 and self._ui_hints:
            page_text = self.host.tr('Page {}/{}').format(display_page + 1, pages)
            navigation = [c.bbox(i) for i in c.find_withtag('_paxton_nav')
                          if c.type(i) == 'text' and c.itemcget(i, 'text') == page_text]
            hint_items = c.find_withtag('_paxton_hint')
            if navigation and hint_items:
                target_bottom = min(box[1] for box in navigation) - 3
                hint_bottom = max(c.bbox(i)[3] for i in hint_items)
                for item in hint_items:
                    c.move(item, 0, target_bottom - hint_bottom)

        if state == 'paxton_found':
            for item in c.find_withtag('_jr_content'):
                if c.type(item) == 'text' and c.itemcget(item, 'text') == self.host.tr('Ready to write'):
                    c.coords(item, 120, 195)
                    c.itemconfigure(item, anchor='s')

    def page_up(self):
        if self._ui_page > 0:
            self._ui_page -= 1
            self._draw_ui_page()

    def page_down(self):
        if self._ui_page + 1 < len(self._ui_pages):
            self._ui_page += 1
            self._draw_ui_page()

    def _begin_user_operation(self):
        """Worker-only fresh budget for a user-initiated RF attempt."""
        self._read_transport_failed = False
        try:
            import executor
        except ImportError:
            return
        reset = getattr(executor, 'resetReworkCount', None)
        if callable(reset):
            reset()

    def _pm3(self, cmd, timeout=WRITE_TIMEOUT):
        read_command = (cmd == 'lf search' or cmd.startswith((
            'lf hitag read ', 'lf hitag info ', 'lf t55xx detect',
            'lf em 410x read')))
        try:
            ok, out = self.host.pm3_command(cmd, timeout=timeout)
        except Exception:
            if not read_command:
                raise
            ok, out = False, ''
        if read_command and (not ok or re.search(
                r'(?i)\b(?:BUSY|timeout|timed out|connection lost|device disconnected)\b', out or '')):
            self._read_transport_failed = True
            return False, out
        return ok, out

    def start_reader_recovery(self):
        self.draw_reader_notice()
        self.host._execute_action('run:do_recover_reader')

    def draw_reader_notice(self):
        canvas = self.host.getCanvas()
        for item in canvas.find_withtag('_jr_content'):
            if canvas.type(item) == 'text':
                canvas.coords(item, SCREEN_W // 2, 120)
                canvas.itemconfigure(item, anchor='center', width=222,
                                     justify='center', font=('Courier New', 16))

    def do_recover_reader(self):
        """One restart only; never automatically replay a read or write."""
        try:
            import executor
            recovered = executor.reworkPM3All() is True
        except Exception:
            recovered = False
        return {'status': 'recovered' if recovered else 'recovery_failed'}

    @staticmethod
    def _pm3_failed(ok, out):
        return (not ok or bool(re.search(
            r'(?i)\b(?:BUSY|timeout|timed out|connection lost|device disconnected)\b', out or ''))
            or bool(re.search(r'(?im)^\s*\[-\]\s*(?:error|failed)\b', out or '')))

    def _toast(self, text):
        try:
            self.host.show_toast(text, timeout=2500)
        except Exception:
            pass

    def _fail(self, msg, back, retry_action=None, retry_kind='normal'):
        self.host.set_var('error_msg', msg)
        self.host.set_var('err_return', back)
        self.host.set_var('err_retry', retry_action or '')
        self.host.set_var('err_retry_kind', retry_kind)
        if self._read_transport_failed:
            self._read_transport_failed = False
            return {'status': 'recover_reader'}
        return {'status': 'error'}

    def _blank(self):
        s = self.host.set_var
        for i in range(1, 4):
            s('block{}'.format(i), '')
        for k in ('error_msg', 'err_return', 'flow', 'uid', 'tag_variant',
                  'em_id', 'id_line', 'block4', 'block5', 'block6', 'block7',
                  'src_name', 'src_line', 'saved_name', 'dump_line',
                  'pick_pos', 'pick_view', 'txt_charset', 'detected_type',
                  'detected_chipset', 'detected_uid', 'paxton_status'):
            s(k, '')
        s('clone_count', '0')
        s('down_count', '0')
        s('err_retry', '')
        s('err_retry_kind', 'normal')
        self._txt = None
        self._txt_mode = None
        # Initialization may run in a worker; do not touch Tk Canvas here.

    def _clear_read_write_cache(self):
        for i in range(1, 4):
            self.host.set_var('block{}'.format(i), '')
        for k in ('uid', 'tag_variant', 'em_id', 'id_line',
                  'src_name', 'src_line', 'block4', 'block5', 'block6', 'block7'):
            self.host.set_var(k, '')

    def _get_blocks(self):
        return {i: self.host.get_var('block{}'.format(i), '') for i in range(4, 8)}

    def _blocks_ok(self, blocks):
        return all(re.match(r'^[0-9A-Fa-f]{8}$', blocks.get(i, '')) for i in range(4, 8))

    def _read_blocks(self):
        cmd = 'lf hitag read --ht2 --k {}'.format(PAXTON_KEY)
        last_out = ''
        for _ in range(2):
            ok, out = self._pm3(cmd, READ_TIMEOUT)
            last_out = out or last_out
            if self._read_transport_failed:
                break  # A transport failure must recover before any retry.
            if ok and out:
                blocks = _parse_hitag_blocks(out)
                if all(i in blocks for i in range(4, 8)):
                    return blocks, _parse_uid(out), _parse_type(out), out
        try:
            self.host.set_var('last_pm3_out', last_out or '')
        except Exception:
            pass
        return None, '', '', last_out or ''

    def _detect_paxton(self, blocks):
        try:
            b5 = blocks.get(5, '')
            if len(b5) >= 4 and b5[3].upper() == 'F':
                variant = 'Net2'
                _, hex_id = calculate_id_net([blocks[4], blocks[5]])
            else:
                variant = 'Switch2'
                _, hex_id = calculate_id_switch([blocks[4], blocks[5], blocks[6], blocks[7]])
            return variant, hex_id
        except Exception:
            return '', None

    def _store(self, blocks, uid, variant, hex_id, src_name, src_line):
        s = self.host.set_var
        s('uid', uid or blocks.get(0, ''))
        for i in range(1, 8):
            s('block{}'.format(i), blocks.get(i, ''))
        s('tag_variant', variant or '')
        s('em_id', hex_id or '')
        s('id_line', self.host.tr('EM ID {}').format(hex_id) if hex_id else self.host.tr('EM ID n/a'))
        s('src_name', src_name or '')
        s('src_line', src_line or '')
        s('clone_count', '0')
        s('down_count', '0')

    def _clear_mode_label(self):
        try:
            self.host.getCanvas().delete('_mode_lbl')
        except Exception:
            pass

    def _update_mode_label(self):
        """Refresh both the {txt_charset} var and the on-canvas 'Mode: xyz'
        label from the active FreeTextInput's charset. Combines what used
        to be two separate calls (_set_txt_charset + _draw_mode_label) kept
        in sync by hand at every call site."""
        mode = self._set_txt_charset()
        self._clear_mode_label()
        try:
            self.host.getCanvas().create_text(
                SCREEN_W // 2,
                81 if self._txt_mode == 'log' else 43,
                text=self.host.tr('Mode: {}').format(mode),
                fill='#000000',
                font=('Courier New', 12),
                anchor='n',
                tags='_mode_lbl',
            )
        except Exception:
            pass

    def do_init(self):
        self._blank()
        self._pick = []
        self._pick_idx = 0
        return {'status': 'ok'}

    def do_start_clone(self):
        self._clear_mode_label()
        self.host.set_var('flow', 'clone')
        self.host.set_var('src_name', '')
        return {'status': 'clone'}

    def do_start_down(self):
        self._clear_mode_label()
        self.host.set_var('flow', 'down')
        self.host.set_var('src_name', '')
        return {'status': 'down'}

    def do_start_log(self):
        self._clear_mode_label()
        return {'status': 'loading_logs'}

    def do_load_log(self):
        """Scan user storage in a worker; editor creation stays on UI."""
        if not _log_paxton_entries():
            return self._fail(self.host.tr('No saved Paxton entries in the log.'), 'menu')
        return {'status': 'log'}

    def _do_read(self, flow, need_id):
        self.host.set_var('flow', flow)
        self._toast(self.host.tr('Reading fob...'))
        self._begin_user_operation()
        blocks, uid, typ, out = self._read_blocks()
        back = 'read_' + flow
        if blocks is None:
            retry_action = 'do_read_clone' if flow == 'clone' else 'do_read_down'
            return self._fail(
                self.host.tr('No fob detected.\nAdjust position\nand try again.'),
                back,
                retry_action=retry_action,
                retry_kind='readwrite'
            )
        variant, hex_id = self._detect_paxton(blocks)
        if need_id and not hex_id:
            retry_action = 'do_read_down' if flow == 'down' else 'do_read_clone'
            return self._fail(
                self.host.tr('ID calculation failed.\nIs it a Paxton fob?'),
                back,
                retry_action=retry_action,
                retry_kind='readwrite'
            )
        self._store(blocks, uid, variant, hex_id, '', self.host.tr('Read OK: {}').format(variant or 'Paxton'))
        return {'status': 'found'}

    def do_read_clone(self):
        return self._do_read('clone', False)

    def do_read_down(self):
        return self._do_read('down', True)

    def do_prepare_paxton(self):
        self._paxton_verified = False
        self.host.set_var('flow', 'clone')
        blocks = self._get_blocks()
        if not self._blocks_ok(blocks):
            return self._fail(self.host.tr('No valid block data.\nRead a fob first.'), 'menu')
        self._paxton_write_blocks = blocks
        return {'status': 'ok'}

    def do_search_pcf7936(self):
        """Identify a destination without writing; lf search is not proof of Paxton auth."""
        self.host.set_var('detected_type', 'Unknown')
        self.host.set_var('detected_chipset', 'Unknown')
        self.host.set_var('detected_uid', '-')
        self.host.set_var('paxton_status', self.host.tr('Paxton not detected'))
        self._paxton_verified = False
        self.host.set_var('paxton_detail', '')
        self._paxton_search_output = ''
        self._paxton_search_chipset = ''
        try:
            self._begin_user_operation()
            ok, out = self._pm3('lf search', SEARCH_TIMEOUT)
        except Exception:
            return self._fail(self.host.tr('Blank PCF7936 search failed'), 'readed_clone')
        if not ok or re.search(r'\b(?:BUSY|timeout|timed out)\b', out or '', re.I):
            return self._fail(self.host.tr('Blank PCF7936 search failed'), 'readed_clone')
        self._paxton_search_output = out or ''
        for key, pattern in (
            ('detected_type', r'(?im)^\s*(?:\[\+\]\s*)?TYPE\.{2,}\s*(.+?)\s*$'),
            ('detected_chipset', r'(?im)^\s*(?:\[\+\]\s*)?Chipset\.{2,}\s*(.+?)\s*$'),
            ('detected_uid', r'(?im)^\s*(?:\[\+\]\s*)?UID\.{2,}\s*([0-9A-Fa-f]+)\s*$'),
        ):
            m = re.search(pattern, out or '')
            if m:
                self.host.set_var(key, m.group(1).strip())
        # Use the same extracted chipset for display and the safety decision.
        chipset = (self.host.get_var('detected_chipset', '') or '').strip()
        self._paxton_search_chipset = chipset
        if re.fullmatch(r'T55(?:xx|x7|77)', chipset, re.I):
            self.host.set_var('paxton_status', self.host.tr('Paxton not detected. Write rejected.'))
            return {'status': 'info'}
        # Never identify an unrelated known chipset as a Hitag2 candidate.
        if chipset and chipset.lower() not in ('unknown', 'hitag 2', 'hitag2'):
            self.host.set_var('paxton_status', self.host.tr('Paxton not detected. Write rejected.'))
            return {'status': 'info'}
        return {'status': 'candidate'}

    def do_detect_pcf7936(self):
        """Check the destination fob before writing any Hitag2 blocks."""
        blocks = getattr(self, '_paxton_write_blocks', None)
        if not blocks or not self._blocks_ok(blocks):
            return self._fail(self.host.tr('No valid block data.\nRead a fob first.'), 'readed_clone')
        # Second guard: no Hitag command after a positive T55xx detection.
        chipset = (getattr(self, '_paxton_search_chipset', '') or '').strip()
        if re.fullmatch(r'T55(?:xx|x7|77)', chipset, re.I):
            self.host.set_var('paxton_status', self.host.tr('Paxton not detected. Write rejected.'))
            return {'status': 'info'}
        try:
            ok, out = self._pm3('lf hitag info -k {}'.format(PAXTON_KEY), READ_TIMEOUT)
        except Exception:
            return self._fail(self.host.tr('Hitag2 communication error.\nCheck fob position.'), 'readed_clone')
        out = out or ''
        # Do not classify a transport failure or an incomplete response as a
        # different password. A PCF7936 detected by lf search is only a candidate.
        if not ok or re.search(r'\b(?:BUSY|timeout|timed out)\b', out, re.I):
            return self._fail(self.host.tr('Hitag2 communication error.\nCheck fob position.'), 'readed_clone')
        type_ok = bool(re.search(r'(?im)^\s*(?:\[\+\]\s*)?TYPE\.{2,}\s*PCF\s*7936\b', out))
        config_ok = bool(re.search(r'(?im)^\s*(?:\[=\]\s*)?Configuration read with password\s+' + re.escape(PAXTON_KEY) + r'\b', out))
        if type_ok and config_ok:
            self.host.set_var('detected_type', 'PCF 7936')
            self.host.set_var('detected_chipset', 'Hitag 2')
            uid = _parse_uid(out) or _parse_uid(self._paxton_search_output)
            if uid:
                self.host.set_var('detected_uid', uid)
                self.host.set_var('uid', uid)
            self._paxton_verified = True
            self.host.set_var('paxton_status', self.host.tr('Paxton detected'))
            return {'status': 'ok'}
        # Authentication was not established. We cannot prove a different
        # password solely from a failed read; describe it as unconfirmed.
        self._paxton_verified = False
        self.host.set_var('paxton_status', self.host.tr('Paxton not detected. Write rejected.'))
        return {'status': 'info'}

    def do_write_paxton(self):
        if not getattr(self, '_paxton_verified', False):
            return self._fail(self.host.tr('Paxton not confirmed.\nWrite rejected.'), 'readed_clone')
        self._paxton_verified = False
        blocks = getattr(self, '_paxton_write_blocks', None)
        if not blocks or not self._blocks_ok(blocks):
            return self._fail(self.host.tr('No valid block data.\nRead a fob first.'), 'menu')
        for page in range(4, 8):
            cmd = 'lf hitag wrbl --ht2 -p {} -d {} -k {}'.format(page, blocks[page], PAXTON_KEY)
            ok, out = self._pm3(cmd, WRITE_TIMEOUT)
            if self._pm3_failed(ok, out):
                return self._fail(
                    self.host.tr('PCF7936 block {} failed\nCheck fob position').format(page),
                    'readed_clone', retry_kind='write_retry')
        return {'status': 'ok'}

    def do_verify_paxton(self):
        blocks = getattr(self, '_paxton_write_blocks', None)
        if not blocks:
            return self._fail(self.host.tr('No valid block data.'), 'readed_clone')
        read_blocks, uid, typ, out = self._read_blocks()
        if read_blocks is None:
            return self._fail(self.host.tr('PCF7936 verify failed.\nCheck fob position.'),
                              'readed_clone', retry_kind='write_retry')
        failed = [str(i) for i in range(4, 8) if read_blocks.get(i, '') != blocks.get(i, '')]
        if failed:
            return self._fail(
                self.host.tr('Verify failed:\nblock {} differs.\nAdjust and retry.').format(', '.join(failed)),
                'readed_clone', retry_kind='write_retry')
        count = int(self.host.get_var('clone_count', '0') or '0') + 1
        self.host.set_var('clone_count', str(count))
        return {'status': 'done'}

    def do_clone_paxton(self):
        # Compatibility for any external callers; the UI uses staged screens.
        result = self.do_prepare_paxton()
        if result.get('status') != 'ok':
            return result
        result = self.do_search_pcf7936()
        if result.get('status') != 'candidate':
            return result
        result = self.do_detect_pcf7936()
        if result.get('status') != 'ok':
            return result
        result = self.do_write_paxton()
        if result.get('status') != 'ok':
            return result
        return self.do_verify_paxton()

    def do_prepare_em4102(self):
        self.host.set_var('flow', 'down')
        em_id = self.host.get_var('em_id', '')
        if not re.fullmatch(r'[0-9A-Fa-f]{10}', em_id or ''):
            return self._fail(self.host.tr('No valid EM4102 ID.\nRead a Paxton fob.'), 'menu')
        self._pending_em_id = em_id.upper()
        return {'status': 'ok'}

    def do_quick_search_t5577(self):
        """Only a fresh, positive LF T55xx identification permits detect."""
        started = time.monotonic()
        try:
            self._begin_user_operation()
            ok, out = self._pm3('lf search', SEARCH_TIMEOUT)
        except Exception as exc:
            return self._fail(self.host.tr('Blank T5577 search failed'), 'readed_down', retry_kind='t55_scan')
        failed = self._pm3_failed(ok, out)
        chipset = re.search(
            r'(?im)^\s*(?:\[\+\]\s*)?Chipset\s*\.{2,}\s*(T55xx|T55x7|T5577)\b',
            out or ''
        )
        if failed:
            return self._fail(self.host.tr('Blank T5577 search failed'), 'readed_down', retry_kind='t55_scan')
        if not chipset:
            return self._fail(self.host.tr('T5577 not detected.\nCheck tag position.'),
                              'readed_down', retry_kind='t55_scan')
        return {'status': 'ok'}

    def do_detect_t5577(self):
        started = time.monotonic()
        try:
            ok, out = self._pm3('lf t55xx detect', CLONE_TIMEOUT)
        except Exception as exc:
            return self._fail(self.host.tr('T5577 detection failed.\nRetry with the tag.'),
                              'readed_down', retry_kind='t55_scan')
        matched = bool(re.search(r'(?im)\bChip\s+type\s*\.{2,}\s*T55(?:x7|77)\b', out or ''))
        failed = self._pm3_failed(ok, out)
        if failed or not matched:
            return self._fail(self.host.tr('T5577 not detected.\nCheck tag position.'),
                              'readed_down', retry_kind='t55_scan')
        return {'status': 'ok'}

    def do_write_em4102(self):
        em_id = getattr(self, '_pending_em_id', '')
        if not re.fullmatch(r'[0-9A-F]{10}', em_id):
            return self._fail(self.host.tr('No valid EM4102 ID.\nRead a Paxton fob.'), 'readed_down')
        ok, out = self._pm3('lf em 410x clone --id {}'.format(em_id), CLONE_TIMEOUT)
        if self._pm3_failed(ok, out):
            return self._fail(self.host.tr('T5577 write failed.\nCheck tag position.'),
                              'readed_down', retry_kind='write_retry')
        return {'status': 'ok'}

    def do_verify_em4102(self):
        """Read back the EM410x ID; never treat command success as verification."""
        em_id = getattr(self, '_pending_em_id', '')
        if not re.fullmatch(r'[0-9A-F]{10}', em_id):
            return self._fail(self.host.tr('No valid EM4102 ID.\nRead a Paxton fob.'), 'readed_down')
        started = time.monotonic()
        try:
            ok, out = self._pm3('lf em 410x reader', VERIFY_TIMEOUT)
        except Exception as exc:
            return self._fail(self.host.tr('EM4102 verification failed.\nRetry with the tag.'),
                              'readed_down', retry_kind='write_retry')
        found = None
        if not self._pm3_failed(ok, out):
            for line in (out or '').splitlines():
                m = re.search(
                    r'(?i)^\s*(?:\[\+\]\s*)?EM\s*410x\s+ID\s*[:=]?\s*'
                    r'([0-9A-F]{10})(?![0-9A-F])\s*$', line)
                if m:
                    found = m.group(1).upper()
                    break
        if not found:
            return self._fail(self.host.tr('EM4102 verification failed.\nNo valid ID read.\nRetry.'),
                              'readed_down', retry_kind='write_retry')
        if found != em_id:
            return self._fail(self.host.tr('Tag data mismatch.\nExp: {}\nGot: {}').format(em_id, found),
                              'readed_down', retry_kind='write_retry')
        count = int(self.host.get_var('down_count', '0') or '0') + 1
        self.host.set_var('down_count', str(count))
        return {'status': 'done'}

    def do_clone_em4102(self):
        # Compatibility entry point; staged UI invokes each step separately.
        for step in (self.do_prepare_em4102, self.do_quick_search_t5577, self.do_detect_t5577,
                     self.do_write_em4102, self.do_verify_em4102):
            result = step()
            if result.get('status') not in ('ok', 'done'):
                return result
        return result

    def _set_txt_charset(self):
        mode = 'ABC'
        if self._txt is not None:
            try:
                mode = self._txt.getCharsetName()
            except Exception:
                mode = 'ABC'
        self.host.set_var('txt_charset', mode)
        return mode

    def show_txt_input_log(self):
        if FreeTextInput is None:
            self._txt = None
            self._txt_mode = None
            self._set_txt_charset()
            self._clear_mode_label()
            return {'status': 'ok'}

        canvas = self.host.getCanvas()
        self._txt = PaxtonTextInput(
            canvas,
            label=self.host.tr('Name:'),
            max_length=20,
            y_offset=128,
            font_size=12,
            text_color='#0000FF'
        )
        self._txt_mode = 'log'
        self._txt.show()
        self._update_mode_label()
        return {'status': 'ok'}

    def show_txt_input_find(self):
        if FreeTextInput is None:
            self._txt = None
            self._txt_mode = None
            self._set_txt_charset()
            self._clear_mode_label()
            return {'status': 'ok'}

        canvas = self.host.getCanvas()
        self._txt = PaxtonTextInput(
            canvas,
            label=self.host.tr('Find:'),
            max_length=20,
            y_offset=105,
            font_size=12,
            text_color='#FF0000'
        )
        self._txt_mode = 'find'
        self._txt.show()
        self._update_mode_label()
        return {'status': 'ok'}

    def txt_roll_up(self):
        if self._txt is not None:
            try:
                self._txt.rollUp()
                self._update_mode_label()
            except Exception:
                pass

    def txt_roll_down(self):
        if self._txt is not None:
            try:
                self._txt.rollDown()
                self._update_mode_label()
            except Exception:
                pass

    def txt_move_left(self):
        if self._txt is not None:
            try:
                self._txt.moveLeft()
            except Exception:
                pass

    def txt_move_right(self):
        if self._txt is not None:
            try:
                self._txt.moveRight()
            except Exception:
                pass

    def txt_next_charset(self):
        if self._txt is not None:
            try:
                self._txt.nextCharset()
                self._update_mode_label()
            except Exception:
                pass

    def do_capture_log_name(self):
        name = ''
        if self._txt is not None:
            try:
                name = self._txt.getValue().rstrip()
                self._txt.hide()
            except Exception:
                pass
            finally:
                self._txt = None
                self._txt_mode = None
                self._clear_mode_label()
                self._set_txt_charset()
        else:
            name = (self.host.get_input() or '').rstrip()

        self._pending_log_name = name
        return {'status': 'captured'}

    def do_capture_find(self):
        query = ''
        if self._txt is not None:
            try:
                query = self._txt.getValue().strip()
                self._txt.hide()
            except Exception:
                pass
            finally:
                self._txt = None
                self._txt_mode = None
                self._clear_mode_label()
                self._set_txt_charset()
        else:
            query = (self.host.get_input() or '').strip()

        self._pending_find_query = query
        return {'status': 'captured'}

    def do_save_captured_log(self):
        return self._do_save_log_with_name(self._pending_log_name)

    def do_find_captured(self):
        return self._do_find_with_query(self._pending_find_query)

    def _do_save_log_with_name(self, name):
        name = (name or '').rstrip()
        if name.startswith(' '):
            return self._fail(self.host.tr('Name cannot start\nwith a space.'), 'log_name')
        if not name:
            return self._fail(self.host.tr('Name cannot be\nempty.'), 'log_name')
        if len(name) < 2:
            return self._fail(self.host.tr('Name too short.\nMin 2 chars.'), 'log_name')
        if _log_name_exists(name):
            return self._fail(self.host.tr('Name already exists:\n{}').format(name), 'log_name')
        blocks = self._get_blocks()
        if not self._blocks_ok(blocks):
            return self._fail(self.host.tr('No valid block data.'), 'menu')
        blocks.update({i: self.host.get_var('block{}'.format(i), '') for i in range(1, 4)})
        em_id = self.host.get_var('em_id', '')
        variant = self.host.get_var('tag_variant', '')
        uid = self.host.get_var('uid', '')
        if not _log_save(name, blocks, em_id, variant, uid):
            return self._fail(self.host.tr('Could not save log.\nWrite failed.'), 'log_name',
                              retry_action='do_retry_save_log', retry_kind='logname')
        dump = _dump_save(blocks, uid, variant)
        self.host.set_var('saved_name', name)
        self.host.set_var('dump_line', self.host.tr('Dump entry saved' if dump else 'Dump NOT saved'))
        return {'status': 'done'}

    def do_retry_save_log(self):
        return self._do_save_log_with_name(self._pending_log_name)

    @staticmethod
    def _match_log_entries(entries, query):
        """A is the input widget's default: show the full log list.

        A single character is never an exact-name lookup. Other one-letter
        queries list names beginning with that letter, case-sensitively.
        For 2+ chars prefer an exact name, then initial-letter suggestions.
        """
        if query == 'A':
            return entries
        if not query:
            return []
        if len(query) == 1:
            return [e for e in entries if e['name'].startswith(query)]
        exact = [e for e in entries if e['name'] == query]
        if exact:
            return exact
        return [e for e in entries if e['name'].startswith(query[0])]

    def _do_find_with_query(self, query):
        q = (query or '').strip()
        if not q:
            return self._fail(self.host.tr('Enter a search letter.'), 'find_name')
        entries = _log_paxton_entries()
        if not entries:
            return self._fail(self.host.tr('No saved Paxton entries in the log.'), 'menu')
        matches = self._match_log_entries(entries, q)
        if not matches:
            return self._fail(self.host.tr('Not found:\n{}').format(q), 'find_name')
        # Never auto-load on a one-character query, even with one result.
        if len(q) >= 2 and len(matches) == 1:
            self._pick = matches
            self._load_entry(matches[0])
            return {'status': 'loaded'}
        self._pick = matches
        self._pick_idx = 0
        self._pick_refresh()
        return {'status': 'pick'}

    def do_back_from_write(self):
        if self.host.get_var('src_name', ''):
            return {'status': 'loaded'}
        flow = self.host.get_var('flow', 'clone')
        return {'status': 'read_down' if flow == 'down' else 'read_clone'}

    def do_back_to_result(self):
        flow = self.host.get_var('flow', 'clone')
        return {'status': 'down' if flow == 'down' else 'clone'}

    def do_error_retry(self):
        retry = self.host.get_var('err_retry', '')
        if retry in ('do_clone_paxton', 'do_clone_em4102', 'do_write_paxton', 'do_write_em4102'):
            self.host.set_var('err_retry', '')
            return {'status': self.host.get_var('err_return', '') or 'menu'}
        retry_kind = self.host.get_var('err_retry_kind', 'normal')
        if retry_kind == 't55_scan':
            self.host.set_var('err_retry_kind', 'normal')
            return {'status': 'em_search'}

        if retry_kind == 'readwrite':
            self._clear_read_write_cache()

        if not retry:
            return {'status': self.host.get_var('err_return', '') or 'menu'}

        fn = getattr(self, retry, None)
        if not callable(fn):
            return {'status': self.host.get_var('err_return', '') or 'menu'}

        self.host.set_var('err_retry', '')
        self.host.set_var('err_retry_kind', 'normal')

        try:
            result = fn()
        except Exception:
            return {'status': self.host.get_var('err_return', '') or 'menu'}

        return self._resolve_retry_result(result, retry_kind)

    def _resolve_retry_result(self, result, retry_kind='normal'):
        """Translate a retried action's raw status ('found'/'done'/'error')
        into an explicit status the `error` screen's transitions can match.
        A bare 'found'/'done' is ambiguous on its own (both read_clone and
        read_down report 'found', both write actions report 'done'), so
        disambiguate using the current flow."""
        status = (result or {}).get('status', '')
        if status == 'error':
            # fn() already called self._fail(...) again, which refreshed
            # error_msg / err_retry / err_retry_kind for another attempt.
            return {'status': 'error'}
        flow = self.host.get_var('flow', 'clone')
        if status == 'found':
            return {'status': 'readed_down' if flow == 'down' else 'readed_clone'}
        if status == 'done':
            if retry_kind == 'logname':
                return {'status': 'saved'}
            return {'status': 'down_ok' if flow == 'down' else 'clone_ok'}
        return result or {'status': self.host.get_var('err_return', '') or 'menu'}

    def _load_entry(self, e):
        blocks = e['blocks']
        variant, hex_id = self._detect_paxton(blocks)
        if not hex_id:
            hex_id = e.get('em_id', '')
            variant = e.get('variant', '') or variant
        self._store(blocks, e.get('uid', ''), variant, hex_id, e['name'], self.host.tr('Log: {}').format(e['name']))

    def _pick_refresh(self):
        n = len(self._pick)
        idx = self._pick_idx
        start = (idx // PICK_ROWS) * PICK_ROWS
        rows = []
        for i in range(start, min(n, start + PICK_ROWS)):
            nm = self._pick[i]['name'][:14]
            rows.append('> {} <'.format(nm) if i == idx else '  {}  '.format(nm))
        self.host.set_var('pick_pos', '{}/{}'.format(idx + 1, n))
        self.host.set_var('pick_view', '\n'.join(rows))

    def do_find(self):
        return self._do_find_with_query(self.host.get_input() or '')

    def do_pick_up(self):
        if self._pick:
            self._pick_idx = (self._pick_idx - 1) % len(self._pick)
            self._pick_refresh()
        self.host._render_current_screen()
        self.draw_screen()
        return {'status': 'stay'}

    def do_pick_down(self):
        if self._pick:
            self._pick_idx = (self._pick_idx + 1) % len(self._pick)
            self._pick_refresh()
        self.host._render_current_screen()
        self.draw_screen()
        return {'status': 'stay'}

    def do_pick_select(self):
        if not self._pick:
            return self._fail(self.host.tr('Nothing selected.'), 'find_name')
        self._load_entry(self._pick[self._pick_idx])
        return {'status': 'loaded'}

    def do_loaded_back(self):
        return {'status': 'pick' if len(self._pick) > 1 else 'find'}

    def do_load_clone(self):
        self.host.set_var('flow', 'clone')
        return {'status': 'clone'}

    def do_load_down(self):
        self.host.set_var('flow', 'down')
        return {'status': 'down'}

# UI progress screens: keep each successful stage visible for at least 2 seconds.
# These methods are executed by run: (worker), never by call: (UI thread).
# Do not delay errors, user-controlled screens, or the underlying RF operations.
def _minimum_progress_display(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        started = time.monotonic()
        result = method(self, *args, **kwargs)
        if isinstance(result, dict) and result.get('status') in ('ok', 'done', 'candidate'):
            remaining = 2.0 - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
        return result
    return wrapped


for _stage in (
    'do_prepare_paxton', 'do_search_pcf7936', 'do_detect_pcf7936',
    'do_write_paxton', 'do_verify_paxton', 'do_prepare_em4102',
    'do_quick_search_t5577', 'do_detect_t5577',
    'do_write_em4102', 'do_verify_em4102',
):
    setattr(PaxtonCloneDownPlugin, _stage,
            _minimum_progress_display(getattr(PaxtonCloneDownPlugin, _stage)))
