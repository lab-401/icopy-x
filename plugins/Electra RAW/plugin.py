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
Copyright (c) 2026: jareckib
Electra RAW Clone for iCopy-X/XS.

Reads an EM4100-compatible 64-bit base and its 64-bit extension using
PM3 LF acquisition and ASK/Manchester demodulation. The plugin validates
row/column parity and requires three consecutive identical 128-bit frames.
Known markers 7E71 and 0030 (source: Flipper Zero protocol documentation)
and 7E1E (source: Flipper Forum reports) are labelled Electra format.
Other stable extensions are labelled Possible Electra.
All six filler bytes are retained, including mixed filler. 
A marker match does not establish authenticity.

The plugin can write recognized Electra and Possible Electra to T5577 when
the capture contains at least three consecutive identical 128-bit frames.
The captured RAW is preserved exactly. Data blocks are written before
configuration block 0, then verified by block readback and a fresh full RAW
RF capture. An ordinary 64-bit EM4100/4102 stream is not treated as Electra.
Incomplete or conflicting captures cannot be written.

RF/storage operations run outside the UI thread. Each explicit RF attempt
renews the executor recovery budget when supported. Failed transport requests
one managed reader restart. Recovery must succeed before Retry is offered;
writes are never replayed automatically. The last RAW is saved atomically.

Sources and community reports:
- Flipper Forum, "Electra intercom": 7E1EAAAA + AAAAAAAA reported by
  dcaprita (14 May 2023) and later July 2023 reports
- Flipper's format documentation lists markers 7E71 and 0030 by Leptopt1los
- iKey.ru discussions provide additional Electra background, including
  July 2023 read/write reports.
The parser uses the EM4100 Manchester-64 layout and preserves captured RAW;
forum observations do not establish compatibility with every reader.

"""

import re
import os
import functools
import time

LAST_RAW_DIR  = '/mnt/upan/dump/electra'
LAST_RAW_FILE = os.path.join(LAST_RAW_DIR, 'last_raw.txt')

TIMEOUT_ACQUIRE  = 10000
TIMEOUT_WRITE    = 8000
TIMEOUT_DET      = 15000
TIMEOUT_PRECHECK = 5000
TIMEOUT_VERIFY_DETECT = 15000  # Post-write detection can take longer
MIN_WRITE_VERIFY_SCREEN_SECONDS = 3.0  # Combined writing/verifying display minimum

BLOCK0_CONFIG = 0x00148080

def _ensure_dir():
    try:
        if not os.path.exists('/mnt/upan'):
            return False
        os.makedirs(LAST_RAW_DIR, mode=0o775, exist_ok=True)
        return True
    except Exception:
        return False

def _save_last_raw(raw):
    """Save the complete 128-bit Electra RAW as 32 hexadecimal characters."""
    raw = (raw or '').strip().upper()
    if not _valid_electra_raw(raw):
        return False
    if not _ensure_dir():
        return False
    import tempfile
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.electra-', suffix='.tmp', dir=LAST_RAW_DIR)
        with os.fdopen(fd, 'w', encoding='ascii') as f:
            f.write(raw + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, LAST_RAW_FILE)
        temporary = None
        return True
    except (OSError, IOError):
        return False
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass



def _load_last_raw():
    """Load and validate the last saved 128-bit Electra RAW."""
    try:
        with open(LAST_RAW_FILE, 'r') as f:
            raw = f.read().strip().upper()
        if _valid_electra_raw(raw):
            return raw
    except (OSError, IOError, UnicodeError):
        pass
    return None


# Explicit EM4100 parity/layout and complete-frame stability checks.
ELECTRA_EPILOGUES = ('7E71', '0030', '7E1E')
MAX_BITS = 65536

def em_identity(bits):
    if len(bits) != 64 or set(bits) - {'0', '1'} or bits[:9] != '1' * 9 or bits[-1] != '0':
        return None
    rows = [bits[9 + 5 * n:14 + 5 * n] for n in range(10)]
    if any(row.count('1') % 2 for row in rows):
        return None
    if any((sum(row[c] == '1' for row in rows) + int(bits[59+c])) % 2 for c in range(4)):
        return None
    return ''.join('%X' % int(row[:4], 2) for row in rows)

def frame(bits, allow_mixed=False):
    if len(bits) != 128 or set(bits) - {'0', '1'}:
        return None
    uid = em_identity(bits[:64])
    if uid is None or bits[64:73] == '1' * 9:
        return None
    filler = [bits[i:i+8] for i in range(80, 128, 8)]
    uniform = len(set(filler)) == 1
    if not uniform and not allow_mixed:
        return None
    raw = '%032X' % int(bits, 2)
    return dict(raw=raw, uid=uid, marker=raw[16:20], filler=raw[20:32],
                uniform=uniform, reference_compatible=uniform,
                known_marker=raw[16:20] in ('7E71', '0030', '7E1E'),
                decoded=uid + raw[16:22])

def analyze(bits, allow_mixed=True):
    if not isinstance(bits, str) or not bits or len(bits) > MAX_BITS or set(bits) - {'0', '1'}:
        return dict(status='invalid', hits=[])
    bases, hits = [], []
    offset = bits.find('1' * 9)
    while offset >= 0:
        uid = em_identity(bits[offset:offset+64])
        if uid is not None:
            bases.append((offset, uid))
            candidate = frame(bits[offset:offset+128], allow_mixed=allow_mixed)
            if candidate:
                hits.append(dict(offset=offset, **candidate))
        offset = bits.find('1' * 9, offset + 1)
    if len({uid for _, uid in bases}) > 1:
        return dict(status='ambiguous', hits=hits)
    if not hits:
        ordinary = any(all((pos + delta, uid) in bases for delta in (64, 128))
                       for pos, uid in bases)
        return dict(status='ordinary_em' if ordinary else ('incomplete_or_unsupported' if bases else 'missing'),
                    hits=[], base_count=len(bases))
    distinct = {hit['raw'] for hit in hits}
    if len(distinct) > 1 or len({uid for _, uid in bases}) > 1:
        return dict(status='ambiguous', hits=hits, variants=len(distinct))
    offsets = {hit['offset'] for hit in hits}
    runs = {}
    for pos in sorted(offsets):
        runs[pos] = runs.get(pos - 128, 0) + 1
    best = max(runs.values())
    selected = hits[0]
    # Quality is separate from detection; a long noisy prefix does not veto
    # a stable series. Preserve diagnostics about every complete base+suffix.
    unmatched = [pos for pos, _ in bases if pos + 128 <= len(bits) and pos not in offsets]
    return dict(status='stable' if best >= 3 else 'candidate', hits=hits,
                raw=selected['raw'], uid=selected['uid'], repeats=len(hits),
                profile='known_epilogue' if selected['known_marker'] else 'possible_electra',
                marker=selected['marker'], filler=selected['filler'],
                uniform=selected['uniform'], reference_compatible=selected['reference_compatible'],
                consecutive=best, prefix_bits=min(offsets),
                unmatched_base_offsets=unmatched,
                gaps=sum(b-a != 128 for a, b in zip(sorted(offsets), sorted(offsets)[1:])))

_em_payload = em_identity

def _inspect_raw(raw):
    if not isinstance(raw, str) or re.fullmatch(r'[0-9a-fA-F]{32}', raw) is None:
        return None
    parsed = frame(format(int(raw, 16), '0128b'), allow_mixed=True)
    if parsed:
        parsed.update(facility=parsed['uid'][:4], card_id=parsed['uid'][4:],
                      epilogue=parsed['marker'])
    return parsed

def _valid_electra_raw(raw):
    return _inspect_raw(raw) is not None

def _classify_capture(bitstream):
    result = analyze(bitstream)
    if result['status'] == 'stable':
        return 'recognized', _inspect_raw(result['raw'])
    return {'ordinary_em': 'ordinary', 'ambiguous': 'ambiguous',
            'candidate': 'possible', 'incomplete_or_unsupported': 'possible'}.get(
                result['status'], 'missing'), None

def _extract_demod_bits(output):
    """Keep one contiguous buffer, including its short final binary line."""
    parts, started, finished = [], False, False
    for line in (output or '').splitlines():
        text = re.sub(r'^\s*\[[+=]\]\s*', '', line).strip()
        if re.fullmatch(r'[01]+', text):
            if finished:
                return None  # Never splice two buffers across diagnostics.
            if not started and len(text) < 32:
                continue
            started = True
            parts.append(text)
        elif started:
            finished = True
    bits = ''.join(parts)
    return bits if bits and len(bits) <= MAX_BITS else None


def _has_valid_em4100(bitstream):
    return any(_em_payload(bitstream[i:i+64]) is not None
               for i in range(max(0, len(bitstream or '')-63)))


def _find_raw128_from_preamble(bitstream):
    status, parsed = _classify_capture(bitstream)
    return parsed['raw'] if status == 'recognized' else None


def _tag_detected(output):
    if not output:
        return False
    for line in output.splitlines():
        low = line.lower()
        if re.search(r'chip\s*type.*t55', low):
            return True
        if re.search(r'chipset.*t55', low):
            return True
        if 't55' in low:
            return True
    return False

def _extract_block_hex(output, block_num):
    """Parse a numbered PM3 Page 0 block row, with or without '[+]'."""
    if not output:
        return None
    page = None
    for line in output.splitlines():
        if re.search(r'\bPage\s+([01])\b', line, re.IGNORECASE):
            page = int(re.search(r'\bPage\s+([01])\b', line, re.IGNORECASE).group(1))
            continue
        if page == 1:
            continue
        cleaned = re.sub(r'^\s*\[\s*\+\s*\]\s*', '', line).strip()
        match = re.fullmatch(r'(0?[0-7])\s*\|\s*([0-9A-Fa-f]{8})\s*\|.*', cleaned)
        if match and int(match.group(1)) == block_num:
            return match.group(2).upper()
    return None

def _rf_worker(handler):
    """Route transport failures to managed recovery; never replay RF."""
    @functools.wraps(handler)
    def wrapped(self, *args, **kwargs):
        result = handler(self, *args, **kwargs)
        if result.get('status') == 'error' and self._transport_failed:
            self._recovery_pending = True
            return {'status': 'recover_reader'}
        return result
    return wrapped


class ElectraPlugin(object):
    WARNING_COLOR = '#E58A19'
    VALUE_COLOR = '#1647D6'

    def __init__(self, host=None):
        self.host = host
        self._page = 0
        self._menu_cursor = 0
        self._transport_failed = False
        self._recovery_pending = False
        self._reader_blocked = False
        self._closed = False
        self._menu_renderer = None
        self._original_list_renderer = None
        self._status_blink_job = None
        self._status_blink_epoch = 0
        self._status_blink_visible = True
        self._write_verify_start = None

    def _pm3(self, cmd, timeout=TIMEOUT_WRITE):
        if self._closed or self._reader_blocked or self._transport_failed:
            return False, ''
        # The host adapter covers canonical read/write commands, but these
        # two client-side commands have no factory mappings in current Lab401.
        # Syntax verified against the supplied no-flash client's help strings.
        try:
            import pm3_compat
            if pm3_compat.get_version() == pm3_compat.PM3_VERSION_ORIGINAL:
                cmd = {
                    'data rawdemod --am': 'data rawdemod am',
                    'lf t55xx config --ASK --rate 64 -o 33 --st':
                        'lf t55xx config d ASK b 64 o 33 ST 1',
                }.get(cmd, cmd)
        except ImportError:
            pass
        try:
            ok, output = self.host.pm3_command(cmd, timeout=timeout)
        except Exception:
            ok, output = False, ''
        if not ok or re.search(r'\b(?:BUSY|timed out|timeout)\b', output or '', re.I):
            self._transport_failed = True
            return False, output
        return ok, output

    def _begin_user_operation(self):
        self._transport_failed = False
        try:
            import executor
        except ImportError:
            return
        reset = getattr(executor, 'resetReworkCount', None)
        if callable(reset):
            reset()

    def do_recover_reader(self):
        pending = self._recovery_pending
        self._recovery_pending = False
        try:
            import executor
            recovered = pending and executor.reworkPM3All() is True
        except Exception:
            recovered = False
        self._reader_blocked = not recovered
        if recovered:
            self._transport_failed = False
            return {'status': 'error'}
        self.host.set_var('error_msg', self.host.tr('Reader restart failed.\nRestart device.'))
        self.host.set_var('error_color', '#D62636')
        return {'status': 'recovery_failed'}

    def on_destroy(self):
        self._closed = True
        self._stop_status_blink()
        if self._menu_renderer is not None:
            self._menu_renderer._render_list = self._original_list_renderer
            self._menu_renderer = None
        self.host.getCanvas().delete('_electra')

    def _install_menu_renderer(self):
        """Use one native render pass for the menu, including onResume().

        This patches only this plugin's JsonRenderer instance; system firmware
        and the rendering of all other content types remain unchanged.
        """
        renderer = self.host._renderer
        if renderer is None or self._menu_renderer is not None:
            return
        native_list = renderer._render_list

        def render_list(content):
            if not content.get('electra_menu'):
                return native_list(content)
            canvas = self.host.getCanvas()
            canvas.delete('_electra')
            for index, item in enumerate(content.get('items', ())):
                label = item['label'] if isinstance(item, dict) else item
                y = 81 + index * 32
                if index == self._menu_cursor:
                    canvas.create_rectangle(
                        10, y - 3, 235, y + 21,
                        fill='#D7E7D8', outline='', tags='_jr_content')
                canvas.create_text(
                    22, y, text=self.host.tr(label), anchor='nw',
                    fill='#222222', font=('Courier New', 14), tags='_jr_content')

        self._original_list_renderer = native_list
        self._menu_renderer = renderer
        renderer._render_list = render_list

    def enter_screen(self):
        """Draw on Tk, then hand slow operations to the native run dispatcher."""
        state_id = self.host._current_state_id
        if state_id == 'writing':
            self._write_verify_start = time.monotonic()
        elif state_id != 'verifying':
            self._write_verify_start = None
        self._page = 0
        self.draw_screen()
        worker = self.host._screens[self.host._current_state_id].get('worker')
        if worker:
            self.host._execute_action('run:' + worker)

    def _stop_status_blink(self):
        """Cancel a pending UI blink when redrawing, leaving a state or exiting."""
        self._status_blink_epoch += 1
        job = self._status_blink_job
        self._status_blink_job = None
        if job is not None:
            try:
                self.host.getCanvas().after_cancel(job)
            except Exception:
                pass

    def _start_status_blink(self, canvas, state_id):
        """Blink only the status line every 750 ms; never redraw the RF UI."""
        token = self._status_blink_epoch
        self._status_blink_visible = True

        def toggle():
            if (self._closed or token != self._status_blink_epoch or
                    self.host._current_state_id != state_id):
                self._status_blink_job = None
                return
            try:
                self._status_blink_visible = not self._status_blink_visible
                canvas.itemconfigure(
                    '_electra_blink',
                    state='normal' if self._status_blink_visible else 'hidden')
                self._status_blink_job = canvas.after(750, toggle)
            except Exception:
                self._status_blink_job = None

        self._status_blink_job = canvas.after(750, toggle)

    def _text_rows(self, text, measure, width=220):
        rows = []
        for paragraph in str(text).split('\n'):
            line = ''
            for word in paragraph.split():
                if line and measure(line + ' ' + word) > width:
                    rows.append(line)
                    line = ''
                while measure(word) > width:
                    end = 1
                    while end < len(word) and measure(word[:end+1]) <= width:
                        end += 1
                    rows.append(word[:end])
                    word = word[end:]
                if word:
                    line += (' ' if line else '') + word
            if line:
                rows.append(line)
        return rows

    def draw_screen(self):
        from tkinter import font as tkfont
        from lib import resources
        canvas = self.host.getCanvas()
        self._stop_status_blink()
        canvas.delete('_electra')
        canvas.delete('_jr_content')
        name = self.host._current_state_id
        content = self.host._screens[name]['screen']['content']
        message = name in ('error', 'recovery_failed')
        information = name in ('reading', 'loading', 'retrying', 'recovering',
                               'checking', 'detecting', 'writing', 'verifying', 'clone_ok')
        sizes = (16, 14, 12) if message or information else ((14,) if name == 'read_tag' else (12,))
        status_screen = name in ('writing', 'verifying')
        footer = content.get('hint')
        for size in sizes:
            font = resources.get_font(size) if message or information else ('Courier New', size)
            face = tkfont.Font(root=canvas, font=font)
            measure = face.measure
            step = max(19, face.metrics('linespace') + 1)
            groups = []
            for row in content.get('lines', []):
                source = row.get('text', '')
                color = row.get('color', '#111111')
                if status_screen and row.get('spacer'):
                    groups.append([('spacer', '', '', color)])
                    continue
                if source == '{error_msg}':
                    text = self.host.tr(self.host.get_var('error_msg') or 'Operation failed.')
                    color = self.host.get_var('error_color', '#D62636')
                elif source == '{profile}':
                    text = self.host.get_var('profile', '')
                    color = self.host.get_var('profile_color', '#1647D6')
                else:
                    text = self.host.tr(source)
                if 'variable' in row:
                    value = str(self.host.get_var(row['variable'], ''))
                    label = text.rstrip(' :') + ':'
                    if '\n' not in value and measure(label + ' ' + value) <= 220:
                        groups.append([('pair', label, value, color)])
                    else:
                        groups.append([('label', label, '', '#64748B')] +
                                      [('value', line, '', color) for line in self._text_rows(value, measure, 232)])
                else:
                    kind = 'blink' if status_screen and row.get('blink') else 'text'
                    groups.append([(kind, line, '', color) for line in
                                   self._text_rows(text, measure, 220)])
            # Both messages must stay on one line, separated by a blank row.
            # Try a smaller font rather than wrapping the blinking label.
            if status_screen and any(len(group) != 1 for group in groups):
                continue
            count = sum(len(group) for group in groups)
            y = (240-face.metrics('linespace'))/2 if count == 1 else 81 if count <= 3 else 62 if count == 4 else 43
            if y + max(0, count-1)*step + face.metrics('linespace') <= 185:
                break
        capacity = min(6, max(1, int((180-43-face.metrics('linespace'))/step)+1))
        pages, page = [], []
        for group in groups:
            if page and len(page)+len(group) > capacity:
                pages.append(page)
                page = []
            # All current fields have at most three rows; retain the whole field.
            page.extend(group)
        if page:
            pages.append(page)
        pages = pages or [[('text', self.host.tr('Operation failed.'), '', '#D62636')]]
        self._page = max(0, min(self._page, len(pages)-1))
        rows = pages[self._page]
        height = face.metrics('linespace')
        y = (240-height)/2 if len(rows)==1 else 81 if len(rows)<=3 else 62 if len(rows)==4 else 43
        pair_rows = [row for row in rows if row[0] == 'pair']
        label_width = max([measure(row[1]) for row in pair_rows] or [0])
        value_width = max([measure(row[2]) for row in pair_rows] or [0])
        # Align fitting pairs; a long label cannot force other rows off screen.
        aligned = label_width + measure(' ') + value_width <= 220
        for index, (kind, text, value, color) in enumerate(rows):
            if kind == 'pair':
                width = label_width if aligned else measure(text)
                total = width + measure(' ') + (value_width if aligned else measure(value))
                x = (240-total)/2
                canvas.create_text(x,y,text=text,anchor='nw',fill='#64748B',font=font,tags='_electra')
                canvas.create_text(x+width+measure(' '),y,text=value,anchor='nw',fill=color,font=font,tags='_electra')
            elif kind == 'spacer':
                pass  # Deliberate empty line between prompt and status.
            else:
                tags = ('_electra', '_electra_blink') if kind == 'blink' else '_electra'
                canvas.create_text(120, y, text=text, anchor='n',
                                   fill=color, font=font, tags=tags)
            y += step
        page_top = 190
        if len(pages)>1:
            item = canvas.create_text(120,190,text=self.host.tr('Page {}/{}').format(self._page+1,len(pages)),
                                      fill='#1647D6',font=('Courier New',9),tags='_electra')
            page_top = canvas.bbox(item)[1]
            if self._page:
                canvas.create_text(235,43,text='▲',anchor='ne',fill='#1647D6',font=('Arial',9),tags='_electra')
            if self._page+1<len(pages):
                canvas.create_text(235,198,text='▼',anchor='se',fill='#1647D6',font=('Arial',9),tags='_electra')
        if footer:
            canvas.create_text(120,page_top-3,text=self.host.tr(footer),anchor='s',
                               fill='#1647D6',font=('Courier New',10),tags='_electra')
        if status_screen:
            self._start_status_blink(canvas, name)


    def move_up(self):
        if self.host._current_state_id == 'menu':
            self._menu_cursor = max(0, self._menu_cursor - 1)
            self.host._render_current_screen()
        else:
            self._page = max(0, self._page - 1)
            self.draw_screen()

    def move_down(self):
        if self.host._current_state_id == 'menu':
            self._menu_cursor = min(1, self._menu_cursor + 1)
            self.host._render_current_screen()
        else:
            self._page += 1
            self.draw_screen()

    def select_menu(self):
        self.host._set_state('read_tag' if self._menu_cursor == 0 else 'loading')

    def _detect_t5577(self):
        ok, out = self._pm3('lf t55xx detect', TIMEOUT_DET)
        if ok and _tag_detected(out):
            return True
        ok2, out2 = self._pm3('lf search', TIMEOUT_DET)
        if ok2 and _tag_detected(out2):
            return True
        return False

    # ---------- EM4100 / Electra decode (for display only) ----------

    def _decode_and_store_raw(self, raw):
        parsed = _inspect_raw(raw)
        if parsed is None:
            self.host.set_var('error_msg', self.host.tr('Invalid Electra RAW.'))
            return False
        self.host.set_var('profile', self.host.tr('Electra format') if parsed['known_marker'] else self.host.tr('Possible Electra'))
        self.host.set_var('profile_color', self.VALUE_COLOR if parsed['known_marker'] else self.WARNING_COLOR)
        self.host.set_var('filler_hex', ' '.join(parsed['filler'][i:i+2] for i in range(0, 12, 2)))
        self.host.set_var('uid_hex', ' '.join(parsed['uid'][i:i+2] for i in range(0, 10, 2)))
        self.host.set_var('raw_hex', '\n'.join(' '.join(raw[j:j+2] for j in range(i,i+16,2)) for i in (0,16)))
        for key, value in (('electra_raw', parsed['raw']), ('current_id', parsed['uid']),
                           ('electra_facility', parsed['facility']), ('electra_id', parsed['card_id']),
                           ('electra_epilogue', parsed['epilogue'])):
            self.host.set_var(key, value)
        return True

    # ---------- READ Electra (RAW via single-pass rawdemod) ----------

    @_rf_worker
    def do_read_tag(self):
        self._begin_user_operation()
        self.host.set_var('error_color', '#D62636')
        self._retry_action = 'read'
        self.host.set_var('error_msg', '')
        self.host.set_var('electra_raw', '')
        self.host.set_var('electra_facility', '')
        self.host.set_var('electra_id', '')
        self.host.set_var('electra_epilogue', '')
        self.host.set_var('current_id', '')

        acquired, _ = self._pm3('lf read', TIMEOUT_ACQUIRE)
        if not acquired:
            self.host.set_var('error_msg', 'LF capture failed.')
            return {'status': 'error'}
        ok, out = self._pm3('data rawdemod --am', TIMEOUT_DET)
        if not ok:
            self.host.set_var('error_msg', 'RAW demod failed.')
            return {'status': 'error'}

        bitstream = _extract_demod_bits(out)
        status, parsed = _classify_capture(bitstream)
        if status != 'recognized':
            if status in ('possible', 'ambiguous'):
                self.host.set_var('error_color', self.WARNING_COLOR)
            messages = {
                'ambiguous': self.host.tr('Conflicting RAW frames.\nRead one tag only.'),
                'possible': self.host.tr('Possible Electra.\nInvalid or incomplete frame.\nRead again.'),
                'ordinary': self.host.tr('EM4100/4102 detected.\nNo supported Electra frame.'),
                'missing': self.host.tr('No Tag Found\nCheck tag position.'),
            }
            self.host.set_var('error_msg', messages[status])
            return {'status': 'error'}
        raw = parsed['raw']

        if not self._decode_and_store_raw(raw):
            return {'status': 'error'}

        if not _save_last_raw(raw):
            self.host.set_var('error_color', self.WARNING_COLOR)
            self._retry_action = 'save'
            self.host.set_var('error_msg', self.host.tr('RAW read, not saved.\nRetry saving.'))
            return {'status': 'error'}

        return {
            'status': 'found',
            'raw': raw,
        }

    # ---------- Show last saved RAW (before cloning it again) ----------

    def do_show_last_raw(self):
        self.host.set_var('error_color', '#D62636')
        self._retry_action = 'load'
        self.host.set_var('error_msg', '')
        self.host.set_var('electra_raw', '')
        self.host.set_var('electra_facility', '')
        self.host.set_var('electra_id', '')
        self.host.set_var('electra_epilogue', '')
        self.host.set_var('current_id', '')

        raw = _load_last_raw()
        if not raw:
            self.host.set_var('error_msg', 'No saved RAW found.\nRead a tag first.')
            return {'status': 'error'}

        if not self._decode_and_store_raw(raw):
            return {'status': 'error'}

        return {
            'status': 'found_last',
            'raw': raw,
        }

    # ---------- RAW -> T5577 (direct passthrough clone) ----------

    def _write_blocks(self, b0, b1, b2, b3, b4):
        for n, b in ((1, b1), (2, b2), (3, b3), (4, b4), (0, b0)):
            ok, output = self._pm3(f'lf t55xx write -b {n} -d {b:08X}')
            if not ok or re.search(r'\b(?:error|failed|failure)\b', output or '', re.I):
                return False
        return True

    def _verify(self, b0, b1, b2, b3, b4):
        """Refresh post-write demod settings, then verify every written block."""
        expected = (b0, b1, b2, b3, b4)
        # Writing block 0 changes the tag configuration. Detect it again before
        # reading; a successful PM3 command alone does not prove an RF read.
        detected, detect_out = self._pm3('lf t55xx detect', TIMEOUT_VERIFY_DETECT)
        if not detected or not re.search(r'Chip\s*type[^\n]*T55', detect_out or '', re.I):
            self.host.set_var('error_msg', 'T5577 not detected after write.\nCheck tag position.')
            return False

        # Keep the proven Electra read profile, as in the original plugin.
        configured, _ = self._pm3('lf t55xx config --ASK --rate 64 -o 33 --st')
        if not configured:
            self.host.set_var('error_msg', 'T5577 read configuration failed.')
            return False

        # A single dump reduces command overhead. Missing blocks are read
        # individually, but mismatching values never count as success.
        dump_ok, dump_out = self._pm3('lf t55xx dump', TIMEOUT_ACQUIRE)
        if not dump_ok:
            self.host.set_var('error_msg', self.host.tr('T5577 read failed.'))
            return False
        for number, value in enumerate(expected):
            found = _extract_block_hex(dump_out, number) if dump_ok else None
            if found is None:
                read_ok, read_out = self._pm3('lf t55xx read -b {}'.format(number), TIMEOUT_ACQUIRE)
                if not read_ok:
                    self.host.set_var('error_msg', self.host.tr('Block {} read command failed.').format(number))
                    return False
                found = _extract_block_hex(read_out, number)
            if found is None:
                self.host.set_var('error_msg', self.host.tr('Cannot read block {}.\nCheck tag position.').format(number))
                return False
            if found != '{:08X}'.format(value):
                self.host.set_var('error_msg', self.host.tr('Block {} mismatch.\nVerify failed.').format(number))
                return False
        acquired, _ = self._pm3('lf read', TIMEOUT_ACQUIRE)
        if not acquired:
            self.host.set_var('error_msg', self.host.tr('LF capture failed.'))
            return False
        ok, output = self._pm3('data rawdemod --am', TIMEOUT_DET)
        result = analyze(_extract_demod_bits(output)) if ok else {'status': 'invalid'}
        wanted = ''.join('{:08X}'.format(value) for value in expected[1:])
        if result['status'] != 'stable' or result['raw'] != wanted:
            self.host.set_var('error_msg', self.host.tr('RF RAW mismatch.\nVerify failed.'))
            return False
        return True

    def _clone_blocks(self):
        raw = (self.host.get_var('electra_raw', '') or '').strip().upper()
        if not _valid_electra_raw(raw):
            self.host.set_var('error_msg', 'No valid Electra RAW.\nRead a tag first.')
            return None
        base = int(raw[:16], 16)
        epi = int(raw[16:], 16)
        return (BLOCK0_CONFIG, (base >> 32) & 0xFFFFFFFF,
                base & 0xFFFFFFFF, (epi >> 32) & 0xFFFFFFFF,
                epi & 0xFFFFFFFF)

    def do_prepare_clone(self):
        self.host.set_var('error_color', '#D62636')
        self._retry_action = 'clone'
        self.host.set_var('error_msg', '')
        return {'status': 'ready' if self._clone_blocks() is not None else 'error'}

    @_rf_worker
    def do_precheck_clone(self):
        """Fail closed if LF search does not positively identify a T55xx chipset."""
        self._begin_user_operation()
        self.host.set_var('error_msg', '')
        if self._clone_blocks() is None:
            return {'status': 'error'}
        try:
            ok, output = self._pm3('lf search', TIMEOUT_PRECHECK)
        except Exception:
            ok, output = False, ''
        if not ok:
            self.host.set_var('error_msg', 'T5577 check failed or wrong tag')
            return {'status': 'error'}
        if not re.search(r'\bChipset\s*\.{0,4}\s*[:=]?\s*T55(?:xx|x7|57|77)\b',
                         output or '', re.IGNORECASE):
            self.host.set_var('error_msg', 'No T55xx chipset found.\nCheck tag position.')
            return {'status': 'error'}
        return {'status': 'ok'}

    @_rf_worker
    def do_detect_clone(self):
        """Confirm T5577 after precheck, before issuing any write command."""
        self.host.set_var('error_msg', '')
        try:
            ok, output = self._pm3('lf t55xx detect', TIMEOUT_DET)
        except Exception:
            ok, output = False, ''
        if not ok or not re.search(r'Chip\s*type[^\n]*T55x7\b', output or '', re.I):
            self.host.set_var('error_msg', 'T5577 detection failed.\nCheck tag position.')
            return {'status': 'error'}
        return {'status': 'ok'}

    @_rf_worker
    def do_write_raw(self):
        self.host.set_var('error_msg', '')
        blocks = self._clone_blocks()
        if blocks is None:
            return {'status': 'error'}
        if not self._write_blocks(*blocks):
            self.host.set_var('error_msg', 'Replace T5577 tag.\nWrite failed.')
            return {'status': 'error'}
        return {'status': 'written'}

    @_rf_worker
    def do_verify_raw(self):
        blocks = self._clone_blocks()
        if blocks is None:
            return {'status': 'error'}
        if not self._verify(*blocks):
            if not self.host.get_var('error_msg', ''):
                self.host.set_var('error_msg', 'T5577 verification failed.')
            return {'status': 'error'}
        # Preserve a 3-second minimum for the combined writing/verifying
        # screen. This only waits after successful RF verification, in the
        # background worker; the UI blink continues every 750 ms and a long
        # RF operation is never cut short. Errors still surface immediately.
        if self._write_verify_start is not None:
            remaining = MIN_WRITE_VERIFY_SCREEN_SECONDS - (time.monotonic() - self._write_verify_start)
            if remaining > 0:
                time.sleep(remaining)
        count = int(self.host.get_var('clone_count', '0')) + 1
        self.host.set_var('clone_count', str(count))
        return {'status': 'done'}

    def do_clone_raw(self):
        # Compatibility entry point for callers outside ui.json.
        result = self.do_prepare_clone()
        if result['status'] != 'ready':
            return result
        for worker in (self.do_precheck_clone, self.do_detect_clone):
            result = worker()
            if result['status'] != 'ok':
                return result
        result = self.do_write_raw()
        if result['status'] != 'written':
            return result
        return self.do_verify_raw()

    def do_error_retry(self):
        action = getattr(self, '_retry_action', '')
        if action == 'save':
            raw = self.host.get_var('electra_raw', '')
            if _valid_electra_raw(raw) and _save_last_raw(raw):
                return {'status': 'found'}
            self.host.set_var('error_msg', self.host.tr('RAW read, not saved.\nRetry saving.'))
            return {'status': 'error'}
        if action == 'read':
            return self.do_read_tag()
        if action == 'load':
            return self.do_show_last_raw()
        if action == 'clone':
            return self.do_prepare_clone()
        self.host.set_var('error_msg', 'Nothing to retry.')
        return {'status': 'error'}

    def do_init(self):
        self._menu_cursor = 0
        self._install_menu_renderer()
        self.host.set_var('error_msg', '')
        self.host.set_var('electra_raw', '')
        self.host.set_var('electra_facility', '')
        self.host.set_var('electra_id', '')
        self.host.set_var('electra_epilogue', '')
        self.host.set_var('current_id', '')
        self.host.set_var('clone_count', '0')
        self._retry_action = ''
        return {'status': 'ok'}
