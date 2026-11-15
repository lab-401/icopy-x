##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Dump Diff 2 plugin for iCopy-X/XS.
Copyright (c) 2026: jareckib

Compare RFID dumps, inspect metadata and memory blocks, run Auto Scan,
and manage saved reports.

MIFARE Classic analysis combines block comparison, sequential scan analysis
and results from available PM3 client commands. Vendor-specific payloads
are decoded by the external PM3 client.

Sources and acknowledgements:

- Parklink Development Limited — quantum-x, danielebruneo and triplesprawl:
  published recognition rules for Intratone/COGELEC, Hexact, Comelit,
  Noralsy and Urmet mechanisms.
  https://github.com/flipperdevices/flipperzero-firmware/issues/1345

- TheDefender44 and other MifareClassicTool discussion contributors:
  published information and pattern adaptations.
  https://github.com/ikarus23/MifareClassicTool/issues/516

- Authors and contributors of RfidResearchGroup/proxmark3:
  analyses and decoders provided by the PM3 client.
  https://github.com/RfidResearchGroup/proxmark3

- equipter — "Mifare Classic - SAK Swapping Explained",
  referenced during earlier work on the plugin's diagnostics.
  https://gist.github.com/equipter/3022aea4e371e585ff6e46de637e7769

Functional inspiration: Dump Diff by uaih3k9x.

A pattern match or vendor identification does not prove that Anti-Clone
protection is active.

Dump Diff 2 does not implement its own key-recovery or protection-bypass
algorithms. Auto Scan delegates card acquisition to the native iCopy-X
reader, which may perform key recovery depending on the installed firmware,
client and card.

"""

import re
import os, time, json
import textwrap
import sys
import types

# A private namespace loads the three bundled helpers without changing the
# native lib package or requiring __init__.py in the installation archive.
_DD_HELPERS = os.path.join(os.path.dirname(__file__), 'lib')
if not os.path.isdir(_DD_HELPERS):
    _DD_HELPERS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lib')
if '_dump_diff_2_lib' not in sys.modules:
    _dd_helpers = types.ModuleType('_dump_diff_2_lib')
    _dd_helpers.__path__ = [_DD_HELPERS]
    sys.modules['_dump_diff_2_lib'] = _dd_helpers
from _dump_diff_2_lib.universal_screen import FORMATS, discover, compare, load, identity, detail_block_lines, json_info_lines
from _dump_diff_2_lib.dump_security import (
    scan as scan_anticopy, analyze_anticopy, anticopy_info_lines,
    analyze_security, security_info_lines, analyze_sequence,
)
from _dump_diff_2_lib.dump_security import analyze_mfc_structure, MFC_SIZES, PM3Analysis

# Language packs live beside this plugin: lang/fr.json, lang/de.json, etc.
# The firmware chooses the active language; no language is hard-coded here.
_DD_LANGUAGE_PACKS = {}
_DD_TEMPLATE_CACHE = {}


def _dd_language():
    try:
        import resources
        return str(resources.getLanguage()).lower()
    except (ImportError, AttributeError, TypeError):
        return 'en'


def _dd_pack(lang):
    if lang not in _DD_LANGUAGE_PACKS:
        # Only accept language codes, never arbitrary paths.
        if not re.fullmatch(r'[a-z]{2,8}(?:[-_][a-z0-9]{2,8})?', lang):
            return {}
        path = os.path.join(os.path.dirname(__file__), 'lang', lang + '.json')
        try:
            with open(path, 'r', encoding='utf-8') as stream:
                data = json.load(stream)
            _DD_LANGUAGE_PACKS[lang] = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _DD_LANGUAGE_PACKS[lang] = {}
    return _DD_LANGUAGE_PACKS[lang]


def _dd_translate(text):
    """Translate UI text only; never change source dump contents."""
    if not isinstance(text, str) or not text:
        return text
    lang = _dd_language()
    if lang == 'en':
        return text
    pack = _dd_pack(lang)
    try:
        import resources
        translator = lambda value: resources.tr_plugin(value, {lang: pack})
    except (ImportError, AttributeError):
        translator = lambda value: pack.get(value, value)

    # Preserve standard RFID identifiers even when a language pack contains them.
    if text.strip() in ('UID', 'HEX', 'DEC', 'SAK', 'ATQ', 'ATQA', 'BCC', 'CRC', 'ID'):
        return text

    translated = translator(text)
    if translated != text:
        return translated
    if re.fullmatch(r'[0-9A-F]{2}(?:[0-9A-F ]*)', text):
        return text
    # PM3 diagnostics retain their original data; only exact JSON labels and
    # known messages are translated, including section-qualified labels.
    if text.startswith('Diag: '):
        return translator('Diag') + ': ' + _dd_translate(text[6:])
    if ' / ' in text and ': ' in text:
        heading, value = text.split(': ', 1)
        return ' / '.join(translator(part) for part in heading.split(' / ')) + ': ' + translator(value)
    if lang not in _DD_TEMPLATE_CACHE:
        templates=[]
        for key,value in sorted(pack.items(), key=lambda x:len(x[0]), reverse=True):
            if '{' not in key:continue
            parts=re.split(r'(\{[^{}]*\})',key)
            fields=[x for x in parts if x.startswith('{') and x.endswith('}')]
            pattern='^'+''.join('(.*?)' if x in fields else re.escape(x) for x in parts)+'$'
            templates.append((re.compile(pattern),fields,value))
        _DD_TEMPLATE_CACHE[lang]=templates
    for pattern,fields,template in _DD_TEMPLATE_CACHE[lang]:
        match=pattern.match(text)
        if match:
            for field,value in zip(fields,match.groups()):template=template.replace(field,value,1)
            return template
    stripped=text.strip()
    if stripped and stripped!=text and '\n' not in text:
        return text[:len(text)-len(text.lstrip())]+_dd_translate(stripped)+text[len(text.rstrip()):]
    # Data fields (UID, block values, HEX, etc.) are never translated.
    if re.match(r'^\s*(?:B\d+|P[01] B\d+|S\d+ B\d+|UID|HEX|DEC|SAK|ATQ|ATQA|BCC|CRC|ID|Key/Pwd|Pwd|Config):', text):
        return text

    # Translate status after a known diagnostic prefix; preserve signature names.
    m = re.match(r'^(A:|B:|Anti-Copy:)\s+(NO MATCH|MATCH|EXPERIMENTAL|POSSIBLE|NOT TESTED)$', text)
    if m:
        return m.group(1) + ' ' + translator(m.group(2))

    # Translate only known labels and exact status values, not arbitrary data.
    m = re.match(r'^(\s*)([A-Za-z][A-Za-z -]*)(: *)(.*)$', text)
    if m:
        lead, label, sep, value = m.groups()
        if label in pack and label not in ('UID', 'HEX', 'DEC', 'SAK', 'ATQ', 'ATQA', 'BCC', 'CRC', 'ID'):
            return lead + translator(label) + sep + (translator(value) if value in pack else value)

    # Handle known labels with numerical values without altering those values.
    m = re.match(r'^(Diff blocks|Page|Block|Size|Modified):\s*(.*)$', text)
    if m and m.group(1) in pack:
        return translator(m.group(1)) + ': ' + m.group(2)

    # Status suffixes follow dynamically assembled headings or counts.
    m = re.match(r'^(.*?)(\s+)(ON|OFF|Disabled|CANDIDATE|ELIGIBLE|NOT TESTED|NOT FOUND|NOT ESTABLISHED|NOT IMPLEMENTED)$', text)
    if m:
        return m.group(1) + m.group(2) + translator(m.group(3))
    return text


def _dd_filename_lines(name, width=26):
    """Split display filename without leaving the .bin/.txt suffix fragmented."""
    if len(name) <= width:
        return [name]
    suffix = os.path.splitext(name)[1]
    if suffix and len(suffix) <= width and len(name) % width < len(suffix):
        # Reserve a complete extension on the last row.
        first_width = width - len(suffix)
        parts = []
        remaining = name
        while len(remaining) > width:
            parts.append(remaining[:first_width])
            remaining = remaining[first_width:]
        parts.append(remaining)
        return parts
    return [name[i:i+width] for i in range(0, len(name), width)]


# One numbered catalog of authored UI messages, in plugin.py only.
# A message screen can supply an integer ID; legacy text call sites resolve
# through the same table. Dynamic values and dump metadata are NOT cataloged.
# UI JSON retains literal strings because native Lab401 UI cannot resolve IDs.
_DD_MAX_TEXT_CHARS = 22
_DD_MESSAGE_TABLE = {
    1001: ('/dump/auto_scan/', 'message'),
    1002: ('All options', 'message'),
    1003: ('Analysis complete', 'message'),
    1004: ('Auto Scan UI missing', 'error'),
    1005: ('Auto Scan stopped', 'message'),
    1006: ('Block read failed', 'error'),
    1007: ('CRC: NOT IMPLEMENTED', 'message'),
    1008: ('Cannot read JSON', 'message'),
    1009: ('Cannot read dump dir', 'message'),
    1010: ('Closing...', 'message'),
    1011: ('Comparison running...', 'message'),
    1012: ('Continue to compare', 'message'),
    1013: ('Dump cleanup failed', 'error'),
    1014: ('Error:', 'error'),
    1015: ('Invalid JSON sidecar', 'error'),
    1016: ('Invalid scan response', 'error'),
    1017: ('JSON name conflict', 'message'),
    1018: ('Loading...', 'message'),
    1019: ('Log saved OK', 'message'),
    1020: ('M1: Delete report', 'message'),
    1021: ('M2 - Retry', 'message'),
    1022: ('M2: Save report', 'message'),
    1023: ('MIFARE Classic', 'message'),
    1024: ('Mirror: NOT TESTED', 'message'),
    1025: ('Missing native RF libs', 'error'),
    1026: ('No Tag detected !!!', 'message'),
    1027: ('No stable counter', 'message'),
    1028: ('Please wait for', 'message'),
    1029: ('Save analysis report?', 'message'),
    1030: ('Saving...', 'message'),
    1031: ('Sequential check', 'message'),
    1032: ('Some options', 'message'),
    1033: ('Structure only', 'message'),
    1034: ('Tag Info + Blocks', 'message'),
    1035: ('Unsafe JSON sidecar', 'error'),
    1036: ('Unsafe JSON type', 'error'),
    1037: ('Unsafe dump path', 'error'),
    1038: ('Unsafe dump type', 'error'),
    1039: ('available.', 'message'),
    1040: ('disabled.', 'message'),
    1041: ('enabled.', 'message'),
    1042: ('result.', 'message'),
    1043: ('unavailable.', 'message'),
}
_DD_MESSAGE_IDS = {value[0]: key for key, value in _DD_MESSAGE_TABLE.items()}
_DD_SCREEN_TEXT = {'Temporary dump cleanup failed': 'Dump cleanup failed', 'Log saved successfully': 'Log saved OK', 'Native dump JSON name collision': 'JSON name conflict', 'Unsafe or unreadable native JSON sidecar': 'Invalid JSON sidecar', 'Unsafe native JSON sidecar': 'Unsafe JSON sidecar', 'Cannot inspect new native JSON': 'Cannot read JSON', 'Cannot inspect native dump directory': 'Cannot read dump dir', 'Native iCopy-X scan/read/tagtypes missing in lib': 'Missing native RF libs', 'Auto Scan canvas unavailable': 'Auto Scan UI missing', 'Invalid scanner response': 'Invalid scan response', 'Structure only, not authenticity': 'Structure only', 'No consistent increment pattern detected.': 'No stable counter', 'Mirror: NOT TESTED (no mirror detector in this build)': 'Mirror: NOT TESTED', 'CRC scan: NOT IMPLEMENTED': 'CRC: NOT IMPLEMENTED', 'Tag Info + Memory Blocks': 'Tag Info + Blocks', 'Unsafe native dump type': 'Unsafe dump type', 'Unsafe native dump path': 'Unsafe dump path', 'Unsafe native JSON type': 'Unsafe JSON type'}

def _dd_message(message_id, **params):
    """Resolve numeric ID to message; preserve unknown dynamic diagnostics."""
    if isinstance(message_id, int):
        entry = _DD_MESSAGE_TABLE.get(message_id)
        if entry is None:
            raise KeyError('Unknown screen message ID: %s' % message_id)
        value = entry[0]
    else:
        value = str(message_id)
        value = _DD_SCREEN_TEXT.get(value, value)
        # All catalogued literals go through their numeric IDs.
        mid = _DD_MESSAGE_IDS.get(value)
        if mid is not None:
            value = _DD_MESSAGE_TABLE[mid][0]
    if params:
        value = value.format(**params)
    return value

def _dd_screen_text(value):
    return _dd_message(value)

def _dd_visible_char_count(text):
    """Count content INCLUDING internal spaces; exclude one outer margin each side."""
    return len(str(text))


def _dd_display_lines(text, width=22):
    """Do NOT auto-wrap messages. UI messages must be shortened at source.

    Return existing authored lines unchanged, so words, errors and technical
    details are never silently split, clipped or replaced with ellipses.
    """
    return str(_dd_translate(text)).split('\n')



def _dd_hex_label_rows(line, limit=26):
    """Never truncate a HEX field; keep fixed font and center each row."""
    match = re.match(r'^(.*?:)\s*([0-9A-Fa-f]+)$', line)
    if not match:
        return _dd_display_lines(line, limit)
    label, value = match.groups()
    value = value.upper()
    together = label + ' ' + value
    if len(together) <= limit:
        return [together]
    if len(value) <= limit:
        return [label, value]
    return [label] + [value[i:i+limit] for i in range(0, len(value), limit)]


DUMP_ROOT = '/mnt/upan/dump'

def compact_hex_spaces(line):
    """Display Details HEX bytes without separators; preserve the source dump."""
    if ':' not in line:
        return line
    label, data = line.split(':', 1)
    if not re.fullmatch(r'\s*[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2})+', data):
        return line
    return label + ':' + re.sub(r'\s+', '', data)


class _LocalizedCanvas:
    def __init__(self, original):
        self._original = original

    def create_text(self, *args, **kwargs):
        if 'text' in kwargs:
            kwargs['text'] = _dd_translate(kwargs['text'])
        return self._original.create_text(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._original, name)

class DumpDiff2Plugin(object):
    def __init__(self, host=None):
        self.host = host
        self._pm3 = PM3Analysis(host)
        self._pm3_results = {}
        self.category = None
        self.files = []
        self.cursor = 0
        self.selected = []
        self.result = None
        self.change_page = 0
        self.name_scroll = 0
        self.details_page = 0
        self.details_lines = []
        self.picker_top = 0
        self.type_cursor = 0
        self.compare_mode_top = 0
        self.sequential_enabled = False
        self.start_cursor = 0
        self.auto_cursor = 0
        self.auto_scan_count = None
        self.auto_completed = 0
        self.auto_captures = []
        self.auto_scan_metadata = []
        self.auto_created_files = []
        self.auto_session_id = None
        self.auto_technology = None
        self.auto_uid = None
        self.auto_error = ''
        self.auto_unsupported_reason = ''
        self.auto_result = None
        self.auto_info_page = 0
        self.auto_actions_cursor = 0
        self.auto_report_last_action = None
        self.auto_report_path = None
        self.auto_log_created = None
        self.auto_report_error = ''
        self.auto_log_files = []
        self.auto_log_cursor = 0
        self.auto_log_name_scroll = 0
        self.auto_log_page = 0
        self.auto_log_lines = []
        self.delete_log_cursor = 0
        self.delete_log_selected = set()
        self.delete_log_failed = []
        self.delete_log_deleted = 0
        self.delete_log_error = ""
        self.auto_last_capture_path = None
        self._auto_busy = False
        # Protect session ownership across native Scanner/Reader worker callbacks.
        # Reader.stop() only requests cancellation; it does NOT roll back files.
        import threading
        self._auto_io_lock = threading.RLock()
        self._auto_cancel_event = threading.Event()
        self._auto_wait_event = None
        self._auto_live_reader = None
        self._auto_stopping_reader = None  # Reader.stop() is non-blocking.
        self._auto_live_scanner = None
        self._auto_attempt_generation = 0
        self._auto_cancel_requested_ui = False

    def _pm3_key(self, data):
        import hashlib
        return hashlib.sha256(data).hexdigest()

    def _pm3_result(self, data):
        # Drawing/Read Logs never issue PM3 commands.
        return self._pm3_results.get(self._pm3_key(data), scan_anticopy(data))

    def _prepare_pm3(self, data, cancelled=None):
        # Lab401 injects host after constructing the plugin without arguments.
        self._pm3.host = self.host
        result = self._pm3.analyze(data, cancelled)
        if len(self._pm3_results) >= 24:
            self._pm3_results.clear()
        self._pm3_results[self._pm3_key(data)] = result
        return result

    def prepare_details(self):
        try:
            if not self.files or not self.selected:
                raise ValueError('No dump selected')
            path = self.files[self.selected[-1]]
            self._prepared_details_selection = (self.category, path)
            if self.category == 'MIFARE Classic':
                self._prepare_pm3(load(path, self.category))
            self._prepared_details_result = self._prepare_details_model()
            return {'status': 'details_ready'}
        except Exception as exc:
            self._dd_set_error(str(exc))
            return {'status': 'error'}

    def finish_details(self):
        # UI callback after the background command has finished.
        current = (self.category, self.files[self.selected[-1]]) if self.files and self.selected else None
        if current != getattr(self, '_prepared_details_selection', None):
            self._dd_set_error('Selection changed')
            return {'status': 'error'}
        result = self._prepared_details_result
        notice = getattr(self, '_details_notice', None)
        if notice:
            self.host.show_toast(notice[0], timeout=notice[1])
        if result['status'] == 'model_ready':
            return {'status': self._details_position()}
        return result

    # Production timeout matches native Reader budget; tests override on instance.
    AUTO_READER_TIMEOUT = 180

    # Explicit per-screen opt-in understood by the user-modified PluginActivity.
    # Other plugins, keys and states retain the original busy-key lockout.
    BUSY_KEY_ALLOWLIST = {'auto_capture': ('M1',)}

    def on_busy_key(self, key, state):
        """Fast UI-thread M1 request during an active Auto Scan run: task.

        No disk/RF/PM3 work or blocking native stop() runs on the UI thread.
        """
        if key != 'M1' or state != 'auto_capture':
            return False
        with self._auto_io_lock:
            if not self._auto_busy or self._auto_cancel_event.is_set():
                return False
            self._auto_cancel_requested_ui = True
        self._auto_signal_cancel(async_stop=True)
        # Only UI-thread side effect: update progress screen with feedback.
        self.draw_auto_capture()
        return True

    def _auto_signal_cancel(self, async_stop=False):
        """Invalidate RF attempt and request native stop without touching Tk.

        M1/PWR use async_stop=True; worker-owned cleanup runs after the RF
        function unwinds.  Stop is not guaranteed to roll back a created file.
        """
        with self._auto_io_lock:
            if self._auto_cancel_event.is_set():
                return
            self._auto_cancel_event.set()
            reader = self._auto_live_reader
            scanner = self._auto_live_scanner
            pending = self._auto_wait_event
            if reader is not None:
                self._auto_stopping_reader = reader
        if pending is not None:
            pending.set()
        def stop_native():
            if reader is not None:
                try:
                    reader.stop()
                except Exception as exc:
                    pass
            if scanner is not None and hasattr(scanner, 'scan_stop'):
                try:
                    scanner.scan_stop()
                except Exception as exc:
                    pass
        if reader is not None or scanner is not None:
            if async_stop:
                import threading
                threading.Thread(target=stop_native, name='DD2NativeStop',
                                 daemon=True).start()
            else:
                stop_native()

    def on_destroy(self):
        """PWR must not wait on slow native RF stop()."""
        self._auto_signal_cancel(async_stop=True)
        self._stop_auto_poll()
        self._stop_details_filename_scroll()

    def _dd_load_message_vars(self):
        """Supply native ui.json placeholders from numbered plugin.py catalog."""
        for message_id, (value, _kind) in _DD_MESSAGE_TABLE.items():
            self.host.set_var('dd_msg_%d' % message_id,
                              _dd_translate(value))

    def _dd_set_error(self, message):
        """Populate the native error state using the shared message catalog."""
        self.host.set_var('error_msg', _dd_translate(_dd_message(message)))

    def init(self):
        # Scan once on startup. Only validated files are exposed in the menu.
        self._dd_load_message_vars()
        self._refresh_catalog()
        self._pm3.host = self.host
        if self._pm3.check_firmware() == 'legacy_1090':
            return {'status': 'legacy_firmware'}
        return {'status': 'ok'}

    def draw_firmware_notice(self):
        from tkinter import font as tkfont
        from _dump_diff_2_lib.screen_catalog import text_rows
        canvas = self.host.getCanvas()
        canvas.delete('_dd2_firmware_notice')
        font = tkfont.Font(family='Courier New', size=12)
        lines = []
        for message in ('Older PM3 version detected.',
                        'Anti-Clone analysis unavailable.', 'Update the firmware.'):
            lines.extend(text_rows(_dd_translate(message), font.measure, 220))
        y = 43 if len(lines) >= 5 else (62 if len(lines) == 4 else 85)
        for line in lines:
            canvas.create_text(120, y, text=line, font=('Courier New', 12),
                               fill='#D62636', anchor='n', tags='_dd2_firmware_notice')
            y += 19
        bounds = canvas.bbox('_dd2_firmware_notice')
        if bounds:
            canvas.move('_dd2_firmware_notice', 0, 120 - (bounds[1] + bounds[3]) / 2)

    # Auto Scan configuration UI. RF capture is experimental and must be
    # verified on the target hardware; never simulate a successful scan.
    AUTO_COUNTS = (3, 6, 10)
    AUTO_LABELS = ('3 scans', '6 scans', '10 scans')


    # The modified PluginActivity does not call on_exit when switching states.
    # Explicitly clear ONLY our Auto Scan canvas tags from the UI thread.
    _AUTO_UI_TAGS = ('_dd2_auto_options', '_dd2_auto_capture',
                     '_dd2_auto_status', '_dd2_auto_result', '_dd2_auto_info',
                     '_dd2_auto_report_prompt', '_dd2_auto_report_done',
                     '_dd2_auto_unavailable', '_dd2_auto_unsupported',
                     '_dd2_auto_report_retry', '_dd2_auto_actions', '_dd2_auto_exit_confirm',
                     '_dd2_auto_no_tag', '_dd2_auto_log_list',
                     '_dd2_auto_log_view', '_dd2_delete_log_list')

    def _auto_clear_ui(self, except_tag=None):
        if except_tag != '_dd2_auto_capture':
            self._stop_auto_poll()
        canvas = self.host.getCanvas()
        if canvas is not None:
            for tag in self._AUTO_UI_TAGS:
                if tag != except_tag:
                    canvas.delete(tag)

    def _menu_rows(self, tag, names, cursor, y0=62, spacing=32):
        """Four-line menu in the 49..200 content area, readable 12pt text."""
        c = _LocalizedCanvas(self.host.getCanvas())
        c.delete(tag)
        c.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        for i, label in enumerate(names):
            y = y0 + i * spacing
            if i == cursor:
                c.create_rectangle(10, y - 3, 235, y + 21,
                                   fill='#D7E7D8', outline='', tags=tag)
            c.create_text(22, y, text=_dd_translate(label), anchor='nw',
                          fill='#222222', font=('Courier New', 14), tags=tag)

    def draw_start(self):
        self._auto_clear_ui()
        self._menu_rows('_dd2_start', ('Auto Scan', 'Compare Dumps', 'Read Logs', 'Delete Logs'),
                        self.start_cursor, y0=69, spacing=27)

    def clear_start(self):
        self.host.getCanvas().delete('_dd2_start')

    def start_up(self):
        self.start_cursor = max(0, self.start_cursor - 1)
        self.draw_start()

    def start_down(self):
        self.start_cursor = min(3, self.start_cursor + 1)
        self.draw_start()

    def start_choose(self):
        if self.start_cursor in (2, 3):
            self._auto_log_refresh()
            if not self.auto_log_files:
                return {'status': 'auto_log_empty' if self.start_cursor == 2 else 'delete_log_empty'}
        return {'status': ('auto_options', 'types', 'auto_log_list', 'delete_log_list')[self.start_cursor]}


    def _auto_log_refresh(self):
        import glob
        folder = self.AUTO_REPORT_DIR
        files = glob.glob(os.path.join(folder, 'Report *.log')) if os.path.isdir(folder) else []
        files += glob.glob(os.path.join(folder, 'DD2_*.log')) if os.path.isdir(folder) else []
        def sortkey(path):
            name = os.path.basename(path)
            match = re.match(r'^Report (\d+) ', name)
            return (int(match.group(1)) if match else 0, name)
        self.auto_log_files = sorted(files, key=sortkey, reverse=True)
        self.auto_log_cursor = min(self.auto_log_cursor, max(0, len(files)-1))

    def _auto_log_display_name(self, path):
        return os.path.splitext(os.path.basename(path))[0]

    def draw_auto_log_list(self):
        self._draw_log_list(False)

    def clear_auto_log_list(self):
        self.host.getCanvas().delete('_dd2_auto_log_list')

    def auto_log_up(self):
        self.auto_log_cursor=max(0,self.auto_log_cursor-1)
        self.auto_log_name_scroll=0
        self.draw_auto_log_list()

    def auto_log_down(self):
        self.auto_log_cursor=min(max(0,len(self.auto_log_files)-1),self.auto_log_cursor+1)
        self.auto_log_name_scroll=0
        self.draw_auto_log_list()

    def auto_log_name_left(self):
        self._scroll_log_name(-3)

    def auto_log_name_right(self):
        self._scroll_log_name(3)

    # Only DD2_REPORT_V2 is supported; legacy reports were retired.
    _AUTO_LOG_SNAPSHOT_PREFIX = 'DD2_REPORT_V2:'

    def _auto_log_snapshot_line(self):
        import base64
        import json
        # Auto Scan finalized this result in its worker; do not recompute it on save.
        result = dict(self.auto_result or {})
        # Per-scan block bytes are reconstructed from captures; do not stringify bytes.
        result.pop('details', None)
        payload = {'version': 2,
                   'captures': [bytes(x).hex().upper() for x in self.auto_captures],
                   'result': result}
        raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=True,
                         default=lambda obj: sorted(obj) if isinstance(obj,set) else str(obj)).encode('ascii')
        return self._AUTO_LOG_SNAPSHOT_PREFIX + base64.b64encode(raw).decode('ascii')

    def _auto_log_decode_snapshot(self, lines):
        import base64
        import json
        if not lines or not lines[-1].startswith(self._AUTO_LOG_SNAPSHOT_PREFIX):
            return None
        try:
            encoded = lines[-1][len(self._AUTO_LOG_SNAPSHOT_PREFIX):]
            if len(encoded)>350000:return None
            data=json.loads(base64.b64decode(encoded,validate=True).decode('ascii'))
            if not isinstance(data, dict) or data.get('version')!=2 or not isinstance(data.get('captures'),list):return None
            captures=[bytes.fromhex(h) for h in data['captures']]
            if not 1<=len(captures)<=10 or any(len(x) not in (320,1024,2048,4096) for x in captures):return None
            if len({len(x) for x in captures})!=1:return None
            result=data.get('result')
            if not isinstance(result,dict):return None
            # Stored report is authoritative: loading must never run analysis.
            from _dump_diff_2_lib.dump_security import valid_snapshot
            if not valid_snapshot(captures, result):return None
            return {'captures':captures,'result':result}
        except (ValueError,TypeError,KeyError,UnicodeError,OverflowError):
            return None

    def auto_log_choose(self):
        """Read only the single native Auto Scan report format."""
        if not self.auto_log_files:
            return
        self._auto_log_snapshot = None
        self._auto_log_error = ''
        try:
            with open(self.auto_log_files[self.auto_log_cursor], 'r', encoding='utf-8') as f:
                content = f.read(1048577)
            if len(content)>1048576:
                raise ValueError('Log too large')
            lines = content.splitlines()
            self._auto_log_snapshot = self._auto_log_decode_snapshot(lines)
            if self._auto_log_snapshot is None:
                self._auto_log_error = 'Invalid scan log'
        except (OSError, UnicodeError, ValueError) as exc:
            self._auto_log_error = 'Log read failed'
        self.auto_log_page = 0
        return {'status': 'auto_log_view'}

    def draw_auto_log_view(self):
        """Reuse Scan Result renderer; never use a separate text viewer."""
        snapshot = getattr(self, '_auto_log_snapshot', None)
        if snapshot is None:
            self._auto_clear_ui(except_tag='_dd2_auto_log_view')
            c = _LocalizedCanvas(self.host.getCanvas())
            tag = '_dd2_auto_log_view'
            c.delete(tag)
            c.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
            c.create_text(120, 100, text=getattr(self, '_auto_log_error', '') or 'Invalid scan log',
                          anchor='center', fill='#C62828', font=('Courier New', 10), tags=tag)
            return
        original = (self.auto_captures, self.auto_result, self.auto_info_page)
        try:
            self.auto_captures = snapshot['captures']
            self.auto_result = snapshot['result']
            self.auto_info_page = self.auto_log_page
            self._auto_draw_memory('_dd2_auto_log_view')
            self.auto_log_page = self.auto_info_page
        finally:
            self.auto_captures, self.auto_result, self.auto_info_page = original

    def clear_auto_log_view(self):
        self.host.getCanvas().delete('_dd2_auto_log_view')

    def auto_log_next(self):
        snapshot = getattr(self, '_auto_log_snapshot', None)
        if snapshot is None:
            return
        original = (self.auto_captures, self.auto_result)
        try:
            self.auto_captures, self.auto_result = snapshot['captures'], snapshot['result']
            total = len(self._auto_information_pages())
        finally:
            self.auto_captures, self.auto_result = original
        self.auto_log_page = min(total - 1, self.auto_log_page + 1)
        self.draw_auto_log_view()

    def auto_log_prev(self):
        self.auto_log_page = max(0, self.auto_log_page - 1)
        self.draw_auto_log_view()

    def draw_delete_log_list(self):
        self._draw_log_list(True)

    def _draw_log_list(self, delete):
        from _dump_diff_2_lib.screen_catalog import draw_log_list
        tag = '_dd2_delete_log_list' if delete else '_dd2_auto_log_list'
        self._auto_clear_ui(except_tag=tag)
        self.delete_log_cursor = min(self.delete_log_cursor, max(0, len(self.auto_log_files)-1))
        draw_log_list(self.host.getCanvas(), tag, self.auto_log_files,
                      self.delete_log_cursor if delete else self.auto_log_cursor,
                      self._auto_log_display_name,
                      getattr(self, 'delete_log_name_scroll', 0) if delete else self.auto_log_name_scroll,
                      _dd_translate, self.delete_log_selected if delete else None)

    def _scroll_log_name(self, step, delete=False):
        from _dump_diff_2_lib.screen_catalog import log_name_offset
        if self.auto_log_files:
            cursor = self.delete_log_cursor if delete else self.auto_log_cursor
            name = self._auto_log_display_name(self.auto_log_files[cursor]) + ('' if delete else ' ')
            attr = 'delete_log_name_scroll' if delete else 'auto_log_name_scroll'
            offset, _ = log_name_offset(name, getattr(self, attr, 0)+step, delete)
            setattr(self, attr, offset)
        self._draw_log_list(delete)

    def clear_delete_log_list(self):
        self.host.getCanvas().delete('_dd2_delete_log_list')

    def delete_log_up(self):
        self.delete_log_cursor = max(0, self.delete_log_cursor-1)
        self.delete_log_name_scroll = 0
        self.draw_delete_log_list()

    def delete_log_down(self):
        self.delete_log_cursor = min(max(0,len(self.auto_log_files)-1),self.delete_log_cursor+1)
        self.delete_log_name_scroll = 0
        self.draw_delete_log_list()

    def delete_log_name_left(self):
        self._scroll_log_name(-3, True)

    def delete_log_name_right(self):
        self._scroll_log_name(3, True)

    def delete_log_toggle(self):
        if self.auto_log_files:
            path = self.auto_log_files[self.delete_log_cursor]
            if path in self.delete_log_selected:
                self.delete_log_selected.remove(path)
            else:
                self.delete_log_selected.add(path)
            self.draw_delete_log_list()

    def delete_log_execute(self):
        if not self.delete_log_selected:
            return {'status': 'delete_log_none'}
        return self._delete_log_paths(sorted(self.delete_log_selected))

    def _delete_log_paths(self, paths):
        import stat
        deleted = 0
        failed = []
        root = os.path.realpath(self.AUTO_REPORT_DIR)
        for path in paths:
            try:
                if os.path.dirname(os.path.realpath(path)) != root or not path.endswith('.log'):
                    raise ValueError('Invalid log path')
                if not stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode) or os.path.islink(path):
                    raise ValueError('Invalid log file')
                os.unlink(path)
                deleted += 1
            except (OSError, ValueError) as exc:
                failed.append(path)
                self.delete_log_error = str(exc)
        self.delete_log_deleted = deleted
        self.delete_log_failed = failed
        self.delete_log_selected = set(failed)
        self._auto_log_refresh()
        return {'status': 'delete_log_error' if failed else 'delete_log_done'}

    def delete_log_retry(self):
        return self._delete_log_paths(list(self.delete_log_failed))

    def begin_delete_log_retry(self):
        # A distinct internal state prevents the host's same-state completion
        # render from covering the custom error notice after a failed retry.
        self.enter_screen()
        self.draw_delete_log_error()
        self.host._execute_action('run:delete_log_retry')

    def draw_delete_log_none(self):
        self._catalog_notice('delete_log_none', layout='delete')

    def draw_delete_log_done(self):
        self._catalog_notice('delete_log_done', layout='delete', deleted=self.delete_log_deleted)
        canvas = self.host.getCanvas()
        if canvas is not None and hasattr(canvas, 'after'):
            def return_to_menu():
                if getattr(self.host, '_current_state_id', None) == 'delete_log_done':
                    self.host._set_state('start_menu')
            canvas.after(3000, return_to_menu)

    def draw_delete_log_error(self):
        self._catalog_notice('delete_log_error', layout='delete', error=
            'Deleted: {} / Failed: {}\n{}'.format(self.delete_log_deleted,
                len(self.delete_log_failed), self.delete_log_error[:24]))

    def clear_delete_log_notice(self):
        c = self.host.getCanvas()
        for tag in ('_dd2_delete_log_none','_dd2_delete_log_done','_dd2_delete_log_error'):
            c.delete(tag)

    def draw_auto_options(self):
        self._auto_clear_ui(except_tag='_dd2_auto_options')
        labels = list(self.AUTO_LABELS)
        self._menu_rows('_dd2_auto_options', labels, self.auto_cursor,
                        y0=69, spacing=29)

    def clear_auto_options(self):
        self.host.getCanvas().delete('_dd2_auto_options')

    def auto_up(self):
        self.auto_cursor = max(0, self.auto_cursor - 1)
        self.draw_auto_options()

    def auto_down(self):
        self.auto_cursor = min(2, self.auto_cursor + 1)
        self.draw_auto_options()

    def auto_choose(self):
        self.auto_scan_count = self.AUTO_COUNTS[self.auto_cursor]
        # UI call must not reset state owned by a running RF worker.
        with self._auto_io_lock:
            if self._auto_busy:
                return {'status': 'busy'}
            stopping = self._auto_stopping_reader
            if stopping is not None and getattr(stopping, 'is_reading', lambda: False)():
                return {'status': 'busy'}
            self._auto_stopping_reader = None
            self._auto_cancel_event.clear()
            self._auto_cancel_requested_ui = False
        self.auto_completed = 0
        self.auto_captures = []
        self.auto_scan_metadata = []
        self.auto_created_files = []
        self.auto_last_capture_path = None
        import uuid
        self.auto_session_id = uuid.uuid4().hex[:12]
        self.auto_attempt = 0
        self.auto_technology = None
        self._auto_tag_type = None
        self.auto_uid = None
        self.auto_error = ''
        self.auto_unsupported_reason = ''
        self._auto_busy = False
        self.auto_result = None
        self.auto_report_path = None
        self.auto_log_created = None
        self.auto_report_error = ''
        self.auto_report_last_action = None
        self.host._set_state('auto_capture')
    def _native_modules(self):
        """Resolve system iCopy-X lib modules, not copies bundled with plugin."""
        import sys
        import importlib
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        native_lib = os.path.join(root, 'lib')
        if not all(os.path.isfile(os.path.join(native_lib, n + '.py')) or
                   os.path.isfile(os.path.join(native_lib, n + '.so'))
                   for n in ('scan', 'read', 'tagtypes')):
            # Firmware may ship compiled extension modules with ABI suffixes.
            import glob
            if not all(glob.glob(os.path.join(native_lib, n + '.*so')) or
                       os.path.isfile(os.path.join(native_lib, n + '.py'))
                       for n in ('scan', 'read', 'tagtypes')):
                raise ImportError('Missing native RF libs')
        if native_lib not in sys.path:
            sys.path.insert(0, native_lib)
        modules = tuple(importlib.import_module(n) for n in ('scan', 'read', 'tagtypes'))
        for name, module in zip(('scan', 'read', 'tagtypes'), modules):
            path = os.path.realpath(getattr(module, '__file__', '') or '')
            if os.path.dirname(path) != os.path.realpath(native_lib):
                raise ImportError('Wrong {} module loaded: {}'.format(name, path))
        return modules

    @staticmethod
    def _auto_type_label(tagtypes, type_id):
        """Native registry name, with numeric fallback; never guess a type."""
        try:
            name = str(tagtypes.getName(type_id)).strip()
            if name and name.lower() not in ('none', 'unknown'):
                return name[:38]
        except Exception:
            pass
        return 'Tag type {}'.format(type_id)

    pass

    def _auto_file_snapshot(self, folder):
        """Return complete MF1 BIN/JSON inventory; fail closed on errors.

        Missing or unreadable entries must never be represented by an empty
        catalogue: an existing dump could otherwise be misclassified as a
        session-created file and later deleted during cleanup.
        """
        result = {}
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if not entry.name.lower().endswith(('.bin', '.json')):
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    stat = entry.stat(follow_symlinks=False)
                    result[os.path.realpath(entry.path)] = (
                        stat.st_size, stat.st_mtime_ns, stat.st_ino)
        except OSError as exc:
            raise OSError('Cannot read dump folder') from exc
        return result

    # Native iCopy-X scan/read adapter. Never issue PM3 commands directly.
    def auto_take_scan(self):
        import threading
        with self._auto_io_lock:
            if self._auto_busy:
                # An overlapping action must never change the active attempt's error.
                return {'status': 'busy'}
            stopping = self._auto_stopping_reader
            if stopping is not None and getattr(stopping, 'is_reading', lambda: False)():
                self.auto_error = 'Reader still stopping'
                return {'status': 'error'}
            self._auto_stopping_reader = None
            if self._auto_cancel_event.is_set():
                return {'status': 'cancelled'}
            self._auto_busy = True
            self._auto_attempt_generation += 1
            attempt_generation = self._auto_attempt_generation
            session = self.auto_session_id
            cancelled = self._auto_cancel_event
        def valid_attempt():
            return (not cancelled.is_set() and self.auto_session_id == session and
                    self._auto_attempt_generation == attempt_generation)
        def cancelled_result():
            # Executed by the RF worker; never touch Tk/Canvas here.
            self.auto_result = None
            cleanup = self._auto_cleanup_captures()
            if cleanup.get('status') != 'ok':
                self.auto_error = 'Temp cleanup failed'
                return {'status': 'error'}
            return {'status': 'cancelled'}
        self.auto_error = ''  # A new attempt must not display a previous error.
        self.auto_attempt = getattr(self, 'auto_attempt', 0) + 1
        _auto_t0 = time.monotonic()

        try:
            icopy_scan, icopy_read, tagtypes = self._native_modules()

            # DD2 v262: short ISO14443-A selection first; no Magic/PRNG tests
            # during discovery. For a verified Gen1a card, hand the native
            # Reader a complete, freshly derived MIFARE Classic info dict.
            # Keep all system files untouched and preserve HF/LF fallback.
            import executor
            import re
            scan_results = []
            _scan_t0 = time.monotonic()
            def _search_step(label, func):
                started = time.monotonic()
                result = func()
                elapsed = round(time.monotonic() - started, 2)
                if not isinstance(result, dict):
                    raise ValueError('Invalid search result: ' + label)
                return result
            def _short_14a():
                # Command completion and parser cache are both owned by this
                # pm3_operation; no other worker may overwrite the response.
                ret = executor.startPM3Task('hf 14a reader --skip', 5000)
                raw = executor.getPrintContent() or ''
                if ret == -1:
                    return {'found': False, 'type': -1, 'return': -1}
                uid_m = re.search(r'(?im)^\s*(?:\[\+\]\s*)?UID:\s*((?:[0-9a-f]{2}\s+){3,9}[0-9a-f]{2})\b', raw)
                atqa_m = re.search(r'(?im)^\s*(?:\[\+\]\s*)?ATQA:\s*([0-9a-f]{2})\s+([0-9a-f]{2})\b', raw)
                sak_m = re.search(r'(?im)^\s*(?:\[\+\]\s*)?SAK:\s*([0-9a-f]{2})\b', raw)
                if not (uid_m and atqa_m and sak_m):
                    # Genuine absent 14A only; no blind inference from SAK.
                    return {'found': False, 'type': -1, 'return': -4}
                uid = re.sub(r'\s+', '', uid_m.group(1)).upper()
                atqa = (atqa_m.group(1)+atqa_m.group(2)).upper()
                sak = sak_m.group(1).upper()
                # SAK 08/18 is only a candidate, never enough for Reader.
                if len(uid) == 8 and sak in ('08', '18'):
                    probe_ret = executor.startPM3Task('hf mf cgetblk --blk 0', 5000)
                    block_out = executor.getPrintContent() or ''
                    block_m = re.search(r'(?im)^\s*(?:\[=\]\s*)?0\s*\|\s*((?:[0-9a-f]{2}\s+){15}[0-9a-f]{2})\b', block_out)
                    if probe_ret != -1 and block_m:
                        block = re.sub(r'\s+', '', block_m.group(1)).upper()
                        # UID and BCC must agree with fresh anticollision.
                        uid_bytes = bytes.fromhex(uid)
                        bcc = uid_bytes[0]^uid_bytes[1]^uid_bytes[2]^uid_bytes[3]
                        if block.startswith(uid) and int(block[8:10],16) == bcc:
                            mfc_type = (tagtypes.M1_S70_4K_4B if sak == '18'
                                        else tagtypes.M1_S50_1K_4B)
                            return {'found': True, 'uid': uid, 'len': 4,
                                'sak': sak, 'atqa': atqa, 'bbcErr': False,
                                'static': False, 'gen1a': True,
                                'type': mfc_type, 'return': mfc_type}
                # Other 14A tags retain native identification and Reader
                # behavior. This may still execute full hf 14a info, but
                # verified Gen1a avoids that problematic PRNG path.
                return _search_step('native hf 14a info (fallback)', icopy_scan.scan_14a)
            with executor.pm3_operation(cancelled):
                hf14a = _search_step('hf 14a reader --skip', _short_14a)
                scan_results.append(hf14a)
                if valid_attempt() and not hf14a.get('found') and hf14a.get('return') == -4:
                    hf = _search_step('hf sea', icopy_scan.scan_hfsea)
                    scan_results.append(hf)
                    if valid_attempt() and not hf.get('found') and hf.get('return') == -4:
                        lf = _search_step('lf sea', icopy_scan.scan_lfsea)
                        scan_results.append(lf)
                    else:
                        pass
                else:
                    pass
            scan_elapsed = time.monotonic() - _scan_t0
            if not valid_attempt():
                return cancelled_result()
            scan_elapsed = time.monotonic() - _scan_t0
            if not scan_results:
                self.auto_error = 'Scan returned no data'
                return {'status': 'error'}
            infos = scan_results[-1]
            # Some native scan revisions report found=False while retaining a
            # valid tagtypes ID. Classify that ID before treating the scan as
            # empty; never infer a card from an error string alone.
            if not isinstance(infos, dict):
                self.auto_error = 'Invalid scan response'
                return {'status': 'error'}
            tag_type = infos.get('type')
            try:
                tag_type = int(tag_type)
            except (TypeError, ValueError):
                tag_type = -1
            known_types = set()
            for registry in ('getAllLow', 'getAllHigh'):
                method = getattr(tagtypes, registry, None)
                if callable(method):
                    try:
                        known_types.update(method())
                    except Exception:
                        pass
            if not infos.get('found') and tag_type not in known_types:
                # Distinguish a transport failure from a real empty-reader scan.
                # Do not infer card technology from failed native scanner data.
                native_return = infos.get('return')
                return_text = str(native_return or '')[:300]
                error_text = str(infos.get('error') or '')[:300]
                scan_failure = (return_text + ' ' + error_text).lower()
                if native_return == -4:
                    # Native scanner: all search paths returned NO_TAG.
                    # A long HF+LF search is not a transport timeout.
                    self.auto_error = 'No tag detected'
                    return {'status': 'no_tag'}
                if infos.get('return') == -1:
                    self.auto_error = 'RF search timed out'
                    return {'status': 'error'}
                if any(marker in scan_failure for marker in (
                        'busy', 'not ready', 'blocked', 'dirty', 'uncertain')):
                    self.auto_error = 'RF scanner busy'
                    return {'status': 'error'}
                # An unusually long scan is not evidence that no card exists.
                if scan_elapsed >= 10.0:
                    self.auto_error = 'RF scan timed out'
                    return {'status': 'error'}
                self.auto_error = 'No tag detected'
                return {'status': 'no_tag'}
            # Native MIFARE Classic readers only; unsupported types are rejected.
            # M1_POSSIBLE_4B/7B: scan.py assigns these when PM3 only reports
            # a bare 'MIFARE Classic'/'MIFARE Plus' without a pinned size —
            # common for magic/gen1a/clone cards. hfmfread.sizeGuess() treats
            # both as a standard 1K read, so accept them like any other Classic.
            mf_types = set(getattr(tagtypes, name) for name in (
                'M1_MINI', 'M1_S50_1K_4B', 'M1_S50_1K_7B',
                'M1_S70_4K_4B', 'M1_S70_4K_7B', 'M1_PLUS_2K',
                'M1_POSSIBLE_4B', 'M1_POSSIBLE_7B')
                if hasattr(tagtypes, name))
            if tag_type in mf_types and not infos.get('found'):
                self.auto_error = 'MIFARE ID incomplete'
                return {'status': 'error'}
            if tag_type not in mf_types:
                # Reuse the firmware's actual LF/HF classification (not ID ranges).
                low_types = set(tagtypes.getAllLow()) if hasattr(tagtypes, 'getAllLow') else set()
                high_types = set(tagtypes.getAllHigh()) if hasattr(tagtypes, 'getAllHigh') else set()
                if tag_type in low_types:
                    self.auto_unsupported_reason = '{}'.format(self._auto_type_label(tagtypes, tag_type))
                elif tag_type in high_types:
                    self.auto_unsupported_reason = '{}'.format(self._auto_type_label(tagtypes, tag_type))
                else:
                    # Unknown/unclassified is NOT necessarily high frequency.
                    self.auto_unsupported_reason = 'Unknown type {}'.format(tag_type)
                self.auto_error = self.auto_unsupported_reason
                return {'status': 'unsupported'}
            # iCopy-X Reader.start() is asynchronous. Wait for its FINAL callback.
            done = threading.Event()
            read_results = []
            # Capture pre-existing dump paths so an old file is not accepted.
            dump_dir = '/mnt/upan/dump/mf1'
            existing_meta = self._auto_file_snapshot(dump_dir)
            existing = {path: meta[1] for path, meta in existing_meta.items()}
            reader = icopy_read.Reader()
            callback_lock = threading.Lock()
            accepting = threading.Event()
            accepting.set()
            with self._auto_io_lock:
                self._auto_live_reader = reader
                self._auto_wait_event = done
            def on_read(event):
                if not isinstance(event, dict) or 'success' not in event:
                    return
                with callback_lock:
                    if not accepting.is_set() or not valid_attempt() or read_results:
                        return
                    read_results.append(event)
                    done.set()
            reader.call_reading = on_read
            def on_exception(exc):
                with callback_lock:
                    if not accepting.is_set() or not valid_attempt() or read_results:
                        return
                    read_results.append({'success': False, 'return': str(exc)})
                    done.set()
            reader.call_exception = on_exception
            _reader_t0 = time.monotonic()
            reader.start(tag_type, {'infos': infos})
            timeout = self.AUTO_READER_TIMEOUT
            signalled = done.wait(timeout)
            accepting.clear()
            with self._auto_io_lock:
                if self._auto_wait_event is done:
                    self._auto_wait_event = None
            if not valid_attempt():
                return cancelled_result()
            if not signalled:
                self._auto_stopping_reader = reader
                reader.stop()
                self.auto_error = 'MIFARE read timed out'
                return {'status': 'read_failed'}
            if not read_results:
                self.auto_error = 'MIFARE read failed'
                return {'status': 'read_failed'}
            result = read_results[0]
            if not result.get('success') or result.get('partial'):
                self.auto_error = 'Read failed/incomplete'
                # Native Reader may write a partial .bin even on failure.
                # Reclaim ONLY a newly-created path explicitly returned by
                # this Reader callback; never glob or delete unknown files.
                if not self._auto_discard_failed_read_bundle(
                        result.get('bundle'), existing_meta):
                    self.auto_error = 'Read/cleanup failed'
                return {'status': 'read_failed'}
            bundle = result.get('bundle')
            # The system callback provides a file path for MIFARE Classic.
            candidate = bundle if isinstance(bundle, str) else (
                bundle.get('file') if isinstance(bundle, dict) else None)
            if not valid_attempt():
                return cancelled_result()
            if not candidate or not isinstance(candidate, str):
                self.auto_error = 'Unreadable MIFARE data'
                return {'status': 'read_failed'}
            if os.path.islink(candidate):
                self.auto_error = 'Unsafe dump path'
                return {'status': 'error'}
            candidate = os.path.realpath(candidate)
            # Only accept native MF1 dump files from the system dump folder.
            mf_root = os.path.realpath('/mnt/upan/dump/mf1')
            if os.path.commonpath((candidate, mf_root)) != mf_root or not candidate.endswith('.bin'):
                self.auto_error = 'Unexpected dump path'
                return {'status': 'error'}
            after_meta = self._auto_file_snapshot(dump_dir)
            if not os.path.isfile(candidate):
                self.auto_error = 'Native dump not found'
                return {'status': 'error'}
            # A native Reader must create a NEW file for each Auto attempt.
            # Even if a pre-existing file has been modified, it is not ours and
            # must never be accepted as a fresh sample or reclaimed by cleanup.
            if candidate in existing_meta:
                self.auto_error = 'Dump filename reused'
                return {'status': 'error'}
            # Register a newly created native dump BEFORE content/UID validation.
            # Reject/error paths may return early; otherwise they leak temporary dumps.
            new_native_file = (candidate not in existing_meta and candidate in after_meta)
            if new_native_file:
                st = os.stat(candidate, follow_symlinks=False)
                import stat as _auto_stat
                if not _auto_stat.S_ISREG(st.st_mode):
                    self.auto_error = 'Unsafe dump type'
                    return {'status': 'error'}
                self.auto_created_files.append((candidate, st.st_dev, st.st_ino))
            if not valid_attempt():
                return cancelled_result()
            # Native Reader may create a JSON sidecar for a standard MF1 read.
            # Bind it to THIS attempt only when it shares the BIN stem and did
            # not exist before the complete filesystem inventory.
            sidecar_status = self._auto_track_mf1_sidecar(
                candidate, existing_meta, after_meta)
            if sidecar_status != 'ok':
                self.auto_error = sidecar_status
                self._auto_discard_rejected_dump(candidate)
                return {'status': 'error'}
            with open(candidate, 'rb') as f:
                raw = f.read(4097)
            # A sidecar is not authoritative unless its memory agrees with BIN.
            sidecar = os.path.splitext(candidate)[0] + '.json'
            if sidecar in after_meta and sidecar not in existing_meta:
                try:
                    from _dump_diff_2_lib.universal_screen import _json_blocks
                    if _json_blocks(sidecar) != raw:
                        self.auto_error = 'BIN/JSON mismatch'
                        self._auto_discard_rejected_dump(candidate)
                        return {'status': 'error'}
                except (OSError, ValueError, TypeError) as exc:
                    self.auto_error = 'Native JSON invalid: {}'.format(str(exc)[:48])
                    self._auto_discard_rejected_dump(candidate)
                    return {'status': 'error'}
            import hashlib
            if len(raw) not in (320, 1024, 2048, 4096):
                self.auto_error = 'Invalid dump size'
                self._auto_discard_rejected_dump(candidate)
                return {'status': 'error'}
            # Compare the scanner-reported UID (4 or 7 bytes), not just
            # the first four bytes of manufacturer block 0.
            uid_text = infos.get('uid', '')
            if isinstance(uid_text, bytes):
                uid = uid_text
            elif isinstance(uid_text, str):
                uid_hex = ''.join(c for c in uid_text if c in '0123456789abcdefABCDEF')
                uid = bytes.fromhex(uid_hex) if len(uid_hex) in (8, 14) else b''
            else:
                uid = b''
            if len(uid) not in (4, 7):
                self.auto_error = 'Invalid scanned UID'
                self._auto_discard_rejected_dump(candidate)
                return {'status': 'error'}
            if self.auto_uid is not None and uid != self.auto_uid:
                self.auto_error = 'Different UID detected'
                self._auto_discard_rejected_dump(candidate)
                return {'status': 'reject'}
            if self.auto_technology is not None and tag_type != getattr(self, '_auto_tag_type', tag_type):
                self.auto_error = 'Card type changed'
                self._auto_discard_rejected_dump(candidate)
                return {'status': 'reject'}
            if self.auto_captures and len(raw) != len(self.auto_captures[0]):
                self.auto_error = 'Memory size changed'
                self._auto_discard_rejected_dump(candidate)
                return {'status': 'reject'}
            if not valid_attempt():
                return cancelled_result()
            # Existing or overwritten native files are NEVER eligible for deletion.
            self.auto_uid = uid
            self.auto_technology = 'MIFARE Classic'
            self._auto_tag_type = tag_type
            try:
                metadata=dict(self._json_metadata_from_obj(self._load_json_sidecar(candidate, any_category=True)))
            except (OSError,ValueError,TypeError):
                metadata={}
            for key in ('uid','atqa','sak'):
                value=infos.get(key)
                if value is not None and key.upper() not in metadata:
                    metadata[key.upper()]=value.hex().upper() if isinstance(value,bytes) else str(value)
            metadata.setdefault('UID',uid.hex().upper())
            self.auto_scan_metadata.append(metadata)
            self.auto_captures.append(raw)
            if not new_native_file:
                pass
            self.auto_last_capture_path = candidate
            self.auto_completed += 1
            if self.auto_completed == self.auto_scan_count:
                self.auto_result = analyze_sequence(self.auto_captures, 16, uid.hex().upper())
                # Heavy analysis belongs to run:auto_take_scan (worker), never
                # to call:draw_auto_info on the GUI thread.
                for cap in self.auto_captures:
                    self.auto_result['anti_copy'] = self._prepare_pm3(cap, cancelled)
                # Compute the byte mask once in the worker; UI scrolling stays cheap.
                first = self.auto_captures[0]
                self.auto_result['changed_bytes'] = [i for i in range(len(first))
                    if any(cap[i] != first[i] for cap in self.auto_captures[1:])]
                from _dump_diff_2_lib.dump_security import complete
                self.auto_result = complete(self.auto_captures, self.auto_result)
                self.auto_result['scan_metadata'] = list(self.auto_scan_metadata)
                if not valid_attempt():
                    return cancelled_result()
                self.auto_info_page = 0
                return {'status': 'complete'}
            return {'status': 'ok'}
        except Exception as exc:
            if not valid_attempt():
                return cancelled_result()
            if 'candidate' in locals():
                self._auto_discard_rejected_dump(candidate)
            self.auto_error = 'Native read error: {}'.format(str(exc)[:75])
            return {'status': 'error'}
        finally:
            # Close the native callback boundary even if the read timed out.
            if 'accepting' in locals():
                accepting.clear()
            if 'scan_accepting' in locals():
                scan_accepting.clear()
            with self._auto_io_lock:
                self._auto_live_reader = None
                self._auto_live_scanner = None
                self._auto_wait_event = None
            with self._auto_io_lock:
                self._auto_busy = False

    def draw_auto_capture(self):
        """Render progress on the UI thread; trace each canvas operation.

        Device logs previously stopped at DRAW_CAPTURE BEGIN, so capture the
        precise failing stage rather than reporting an unverified fix.
        """
        tag = '_dd2_auto_capture'
        self._stop_auto_poll()
        stage = 'clear_other_tags'
        try:
            self._auto_clear_ui(except_tag=tag)
            stage = 'get_canvas'
            canvas = self.host.getCanvas()
            if canvas is None:
                raise RuntimeError('Auto Scan UI unavailable')
            c = _LocalizedCanvas(canvas)
            stage = 'delete_old_capture'
            c.delete(tag)
            stage = 'background'
            c.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
            step = self.auto_completed + 1
            rows = ((62, 'Step {}'.format(step)),
                    (85, 'Scans: {}/{}'.format(self.auto_completed + (1 if self._auto_busy else 0), self.auto_scan_count)),
                    (108, 'Wait...' if self._auto_busy else ''),
                    (137, 'Place tag on iCopy-X' if not self.auto_completed else 'Use tag on intercom'),
                    (160, 'Press OK to scan' if not self.auto_completed else 'then place on iCopy-X'),
                    (184, ''))
            for y, line in rows:
                stage = 'text_y_{}'.format(y)
                c.create_text(120, y, text=line, anchor='center',
                              font=('Courier New', 12),
                              fill='#1647D6' if y == 108 else '#222222',
                              tags=(tag, '_dd2_busy_count') if y == 85 else (tag, '_dd2_busy_label') if y == 108 else tag)
            # Poll from the UI thread only; the worker never calls Tk methods.
            # Keep the Wait label in its reserved row while RF is active.
            def refresh_busy():
                try:
                    if getattr(self.host, '_current_state_id', None) not in ('auto_capture', 'auto_capture_next'):
                        return
                    canvas.delete('_dd2_busy_label')
                    canvas.delete('_dd2_busy_count')
                    canvas.create_text(120, 85, text=_dd_translate('Scans: {}/{}'.format(
                        self.auto_completed + (1 if self._auto_busy else 0), self.auto_scan_count)),
                        anchor='center', fill='#222222', font=('Courier New', 12),
                        tags=(tag, '_dd2_busy_count'))
                    if self._auto_busy:
                        canvas.create_text(120, 108, text=_dd_translate('Wait...'), anchor='center',
                                           fill='#1647D6', font=('Courier New', 12),
                                           tags=(tag, '_dd2_busy_label'))
                    self._auto_poll_timer = canvas.after(120, refresh_busy)
                except Exception as exc:
                    pass
            self._auto_poll_timer = canvas.after(120, refresh_busy)
            stage = 'raise_capture'
            c.tag_raise(tag)
        except Exception as exc:
            raise

    def _stop_auto_poll(self):
        timer = getattr(self, '_auto_poll_timer', None)
        self._auto_poll_timer = None
        if timer is not None:
            try:
                self.host.getCanvas().after_cancel(timer)
            except (AttributeError, ValueError, RuntimeError):
                pass

    def clear_auto_capture(self):
        self._stop_auto_poll()
        self.host.getCanvas().delete('_dd2_auto_capture')

    def enter_screen(self):
        """Clear only this plugin's content, even on hosts without on_exit."""
        from _dump_diff_2_lib.screen_catalog import SCREEN_ENTRIES
        # A picker toast must not overlay the next screen or keep re-raising.
        toast = getattr(self.host, '_toast', None)
        if toast is not None:
            toast.cancel()
        self._stop_auto_poll()
        self._stop_details_filename_scroll()
        canvas=self.host.getCanvas()
        for item in canvas.find_all():
            if any(tag.startswith('_dd2_') for tag in canvas.gettags(item)):
                canvas.delete(item)
        self._notice_page=0
        self._notice_total=1
        self._notice_spec=None
        action=SCREEN_ENTRIES.get(self.host._current_state_id)
        if action:
            self.host._execute_action(action)

    def _dd_notice(self, tag, lines, colors=None, layout='notice', page=0):
        from _dump_diff_2_lib.screen_catalog import draw_notice
        self._notice_spec=(tag,lines,colors,layout)
        result=draw_notice(self.host.getCanvas(),tag,lines,colors,
            _dd_translate,_dd_message,layout,page)
        self._notice_page=result['page'];self._notice_total=result['pages']
        self.host.set_var('screen_message',result['text'])

    def notice_next(self):
        if not getattr(self,'_notice_spec',None):return
        self._dd_notice(*self._notice_spec,page=min(self._notice_total-1,self._notice_page+1))

    def notice_prev(self):
        if not getattr(self,'_notice_spec',None):return
        self._dd_notice(*self._notice_spec,page=max(0,self._notice_page-1))

    def draw_compare_error(self):
        message=self.host.get_var('error_msg','Error')
        self._dd_notice('_dd2_error',['Error:',message],['#B91C1C','#64748B'])

    def _catalog_notice(self, name, tag=None, layout='notice', **params):
        from _dump_diff_2_lib.screen_catalog import notice_rows
        tag=tag or '_dd2_'+name
        self._auto_clear_ui(except_tag=tag)
        rows=notice_rows(name,params,_dd_translate,_dd_message)
        self._dd_notice(tag,[text for text,_ in rows],[color for _,color in rows],layout)


    def draw_auto_read_failed(self):
        self._catalog_notice('auto_read_failed', saved=self.auto_completed,
                             total=self.auto_scan_count, step=self.auto_completed+1)

    def clear_auto_read_failed(self):
        self.host.getCanvas().delete('_dd2_auto_read_failed')

    def auto_retry_read(self):
        """Return to capture screen, retaining all earlier successful reads."""
        with self._auto_io_lock:
            stopping = self._auto_stopping_reader
            if self._auto_busy or (stopping is not None and
                    getattr(stopping, 'is_reading', lambda: False)()):
                return
            self._auto_stopping_reader = None
        self.auto_error = ''
        self.host._set_state('auto_capture_next' if self.auto_completed else 'auto_capture')

    def draw_auto_status(self):
        self._catalog_notice('auto_status', error=self.auto_error or 'Scan failed')
        self._auto_schedule_result_return('auto_status')

    def clear_auto_status(self):
        self.host.getCanvas().delete('_dd2_auto_status')

    def draw_auto_no_tag(self):
        self._catalog_notice('auto_no_tag')
        self._auto_schedule_result_return('auto_no_tag')

    def clear_auto_no_tag(self):
        self.host.getCanvas().delete('_dd2_auto_no_tag')

    def _auto_source_pages(self):
        """Complete, read-only Auto Scan pages; no information is silently truncated."""
        if not self.auto_captures:
            return [('empty', [])]
        data = self.auto_captures[-1]
        result = self.auto_result or {}
        changed = self._auto_dynamic_positions()
        ac = result.get('anti_copy') or {}
        pages = []
        scans = len(self.auto_captures)
        variant = {320:'Mini',1024:'1K',2048:'2K',4096:'4K'}.get(len(data),'?')
        pages.append(('intro', [('MIFARE Classic ' + variant, 'title'),
                                 ('Scan: {}'.format(scans), 'value')]))
        from _dump_diff_2_lib.screen_catalog import pm3_display_fields
        anti = pm3_display_fields(ac)
        # The preceding Analysis Notice already states the heuristic limitation.
        pages.append(('Analysis Notice', [
            ('Detection is not', ''), ('proof of protection.', ''),
            ('No match does not', ''), ('prove its absence.', '')]))
        pages.append(('Anti-Clone Analysis',anti))
        seq = [('Source:', 'Auto Scan log'),
               ('Changed blocks:',str(len({x//16 for x in changed})),'#C62828' if changed else '#64748B'),
               ('Changed bytes:',str(len(changed)),'#C62828' if changed else '#64748B'),
               ('Sequential:',str(result.get('sequential_status','OFF')),'#C62828' if result.get('sequential_status')=='ON' else '#64748B'),
               ('Mirror:','NOT TESTED')]
        pages.append(('Sequential Analysis',seq))
        counters = result.get('possible_counters') or []
        if not counters:
            pages.append(('Counter Analysis',[('Counter:','NOT DETECTED')]))
        for idx,counter in enumerate(counters,1):
            if not isinstance(counter,dict): continue
            pages.append(('Counter {}/{}'.format(idx,len(counters)),
                          [('Block:',str(counter.get('block','?'))),
                           ('Offset:',str(counter.get('offset','?'))),
                           ('Width:',str(counter.get('width','?')))]))
            pages.append(('Counter {}/{}'.format(idx,len(counters)),
                          [('Endian:',str(counter.get('endian','?'))),
                           ('Step:',str(counter.get('step','?'))),
                           ('Status:','CANDIDATE ONLY')]))
        uid = result.get('uid') or (self.auto_uid.hex().upper() if self.auto_uid else '')
        uid = ''.join(ch for ch in str(uid).upper() if ch in '0123456789ABCDEF')
        details = [('UID:',' '.join(uid[i:i+2] for i in range(0,len(uid),2))),
                   ('Type:','mfc-'+variant.lower()),('Size:',str(len(data))+' bytes'),
                   ('Blocks:',str(len(data)//16))]
        pages.append(('Tag Details',details))
        structure = analyze_mfc_structure(data)
        if structure.get('supported'):
            security = [('Sectors:', str(structure['sectors'])),
                        ('Trailers:', str(len(structure['trailers']))),
                        ('Access bits:', 'VALID' if not structure['access_invalid'] else 'INVALID / UNKNOWN'),
                        ('Invalid trailers:', str(len(structure['access_invalid'])), '#C62828' if structure['access_invalid'] else '#64748B'),
                        ('Value blocks:', str(len(structure['value_blocks'])), '#C62828' if structure['value_blocks'] else '#64748B'),
                        ('UID BCC:', 'VALID' if structure['bcc0'] else 'INVALID')]
            for n in structure['access_invalid']:
                security.append(('Invalid B{}:'.format(n), 'CHECK TRAILER', '#C62828'))
            for n in structure['value_blocks']:
                security.append(('Value B{}:'.format(n), 'STRUCTURE MATCH', '#C62828'))
            security.append(('Note:', 'Structure only'))
            pages.append(('Classic Structure',security))
        else:
            pages.append(('Classic Structure',[('Status:','N/A')]))
        for i in range(0,len(data)//16,2):
            pages.append(('blocks',list(range(i,min(i+2,len(data)//16)))))
        return pages

    def _auto_information_pages(self):
        """Finalized scan results are immutable while their pages are browsed."""
        signature=(_dd_language(),len(self.auto_captures),self.host.getCanvas().tk.call('tk','scaling'))
        cache=getattr(self,'_auto_page_cache',[])
        for captures,result,key,pages in cache:
            if captures is self.auto_captures and result is self.auto_result and key==signature:
                return pages
        pages=self._build_auto_information_pages()
        # Keep active Auto and the last opened log, with bounded memory use.
        self._auto_page_cache=(cache+[(self.auto_captures,self.auto_result,signature,pages)])[-2:]
        return pages

    def _auto_compact_hex_pages(self, label, captures, title='', history_label=None):
        """One baseline, then byte histories in scan order, with page context."""
        from _dump_diff_2_lib.screen_catalog import field_pages, row_positions
        from tkinter import font as tkfont
        first=captures[0]
        changed=[i for i in range(len(first)) if any(raw[i]!=first[i] for raw in captures[1:])]
        fields=[(label, ' '.join('{:02X}'.format(x) for x in first),
                 '#1647D6','hex_compare' if len(first)<=8 else 'hex',changed)]
        for offset in changed:
            values=[raw[offset] for raw in captures[1:]]
            fields.append(((history_label.format(offset) if history_label else 'Scans 2-{} byte {}:'.format(len(captures),offset)),
                ' '.join('{:02X}'.format(x) for x in values),'#1647D6','hex_compare',
                [i for i,x in enumerate(values) if x!=first[offset]]))
        heading=[('heading',_dd_translate(title),'','#1647D6')] if title else []
        context=('label',_dd_translate(label).rstrip(' :')+':','','#64748B')
        pages=[];current=list(heading)
        height=tkfont.Font(family='Courier New',size=12).metrics('linespace')
        for field in fields:
            for group in field_pages([('',[field])],_dd_translate):
                trial=current+group
                if len(trial)>6 or row_positions(trial,True)[-1]+height>171:
                    if len(current)>len(heading):pages.append(('fields',current))
                    current=list(heading)+[context]
                current.extend(group)
        if len(current)>len(heading):pages.append(('fields',current))
        return pages

    def _build_auto_information_pages(self):
        from _dump_diff_2_lib.screen_catalog import field_pages
        source=self._auto_source_pages()
        pages=[];result=self.auto_result or {}
        changed={x//16 for x in self._auto_dynamic_positions()}
        if not self.auto_captures:return [('empty',[])]
        data=self.auto_captures[-1];count=len(self.auto_captures)
        variant={320:'Mini',1024:'1K',2048:'2K',4096:'4K'}.get(len(data),'?')
        pages.append(next(item for item in source if item[0]=='Analysis Notice'))
        def add_sections(sections):
            pages.extend(('fields',part) for part in field_pages(sections,_dd_translate))
        add_sections([('MIFARE Classic '+variant,[('Type:','mfc-'+variant.lower()),
            ('Size:',str(len(data))+' bytes'),('Blocks:',str(len(data)//16)),('Scans:',str(count))])])
        sequential_fields=[]
        for kind,rows in source:
            if kind=='Anti-Clone Analysis':add_sections([(kind,rows)])
            elif kind=='Sequential Analysis':sequential_fields.extend(rows)
        candidates=result.get('possible_counters') or []
        accepted=result.get('sequential_candidates') or []
        grouped={}
        for counter in candidates:
            start=counter['block']*16+counter['offset']
            vals=tuple(int.from_bytes(raw[start:start+counter['width']],counter['endian']) for raw in self.auto_captures)
            key=(counter['block'],counter['offset'],vals)
            grouped.setdefault(key,[]).append(counter)
        sections=[]
        if not grouped:sections.append(('Sequential Analysis',sequential_fields+[('Counter:','NOT DETECTED')]))
        for index,((block,offset,vals),alternatives) in enumerate(grouped.items(),1):
            steps=[b-a for a,b in zip(vals,vals[1:])]
            valid=any(all(candidate.get(k)==c.get(k) for k in ('block','offset','width','endian'))
                      for c in alternatives for candidate in accepted)
            fields=([('Counter:',str(index)+'/'+str(len(grouped)))] if len(grouped)>1 else [])
            fields.extend([('Status:','ON' if valid else 'CANDIDATE ONLY'),('Block:',str(block)),('Offset:',str(offset))])
            fields.append(('Width/endian:',', '.join(str(c['width'])+'/'+c['endian'] for c in alternatives)))
            fields.extend([('Values:',' → '.join(map(str,vals))),('Steps:',' '.join('{:+d}'.format(v) for v in steps)),
                           ('Rollback:','ON' if valid and len(set(vals))<len(vals) else 'OFF'),
                           ('Alternating:','ON' if len(steps)>1 and all(a==-b for a,b in zip(steps,steps[1:])) else 'OFF')])
            fields=[(label,value,('#C62828' if valid else '#E58A19') if value not in ('OFF','N/A') else '#64748B') for label,value in fields]
            sections.append(('Sequential Analysis',(sequential_fields if index==1 else [])+fields))
        add_sections(sections)
        for kind,rows in source:
            if kind=='Classic Structure':add_sections([(kind,rows)])
        # Snapshot metadata is authoritative; never borrow another scan/session.
        stored=result.get('scan_metadata')
        metadata=stored if stored else [{'UID':str(result.get('uid') or '')} for _ in self.auto_captures]
        keys=['UID','ATQA','SAK']
        for item in metadata:
            for key in item:
                if key not in keys and key not in ('Type','FileType','Size','Blocks','Scans','Created'):
                    keys.append(key)
        fields=[]
        def flush_metadata():
            if fields:
                add_sections([('Tag Details',list(fields))]);fields.clear()
        for key in keys:
            values=[str(item.get(key) or 'N/A') for item in metadata]
            different=len(set(values))>1
            compact=[re.sub(r'\s+','',v) for v in values]
            ishex=key.upper() in ('UID','ATQA','SAK','CSN','SIGNATURE','VERSION') and all(
                re.fullmatch('[0-9A-Fa-f]+',v) and len(v)%2==0 for v in compact)
            if different and ishex and len({len(v) for v in compact})==1:
                flush_metadata()
                pages.extend(self._auto_compact_hex_pages(key+':',[bytes.fromhex(v) for v in compact],'Tag Details'))
            elif different:
                # Group identical text values, retaining their exact scan numbers.
                grouped_values={}
                for index,value in enumerate(values,1):grouped_values.setdefault(value,[]).append(str(index))
                for value,indices in grouped_values.items():
                    fields.append(('Scans {} {}:'.format(','.join(indices),key),value,'#C62828'))
            elif ishex:
                fields.append((key+':',' '.join(compact[0][i:i+2].upper() for i in range(0,len(compact[0]),2)),'#1647D6','hex_compare',[]))
            else:fields.append((key+':',values[0],'#64748B' if values[0]=='N/A' else '#1647D6'))
        flush_metadata()
        # Each block has one owner: the memory section. Never repeat full scans.
        pending=[]
        for block in range(len(self.auto_captures[0])//16):
            if block not in changed:
                pending.append(block)
                if len(pending)==2:pages.append(('blocks',pending));pending=[]
                continue
            if pending:pages.append(('blocks',pending));pending=[]
            pages.extend(self._auto_compact_hex_pages('Block {}:'.format(block),
                [raw[block*16:(block+1)*16] for raw in self.auto_captures]))
        if pending:pages.append(('blocks',pending))
        return pages

    def _auto_memory_pages(self):
        return len(self._auto_information_pages())

    def _auto_dynamic_positions(self):
        """A->B->A is still dynamic, even when the final byte equals the first."""
        if not self.auto_captures: return set()
        cached = (self.auto_result or {}).get('changed_bytes')
        if cached is not None: return {int(x) for x in cached}
        first = self.auto_captures[0]
        return {i for i in range(len(first)) if any(i>=len(c) or c[i]!=first[i]
                for c in self.auto_captures[1:])}

    def _auto_draw_memory(self, tag):
        """Display complete analysis and two complete blocks per memory page."""
        from tkinter import font as tkfont
        self._auto_clear_ui(except_tag=tag)
        c = _LocalizedCanvas(self.host.getCanvas())
        c.delete(tag)
        c.create_rectangle(0,49,239,200,fill='white',outline='',tags=tag)
        pages = self._auto_information_pages()
        self.auto_info_page = max(0,min(self.auto_info_page,len(pages)-1))
        page = self.auto_info_page
        kind, rows = pages[page]
        blue, gray, red, orange = '#1647D6','#64748B','#C62828','#E58A19'
        font = ('Courier New',12)
        f = tkfont.Font(family='Courier New',size=12)
        if kind == 'fields':
            from _dump_diff_2_lib.screen_catalog import draw_field_page
            draw_field_page(self.host.getCanvas(), rows, page, len(pages), tag,
                'Back' if tag == '_dd2_auto_log_view' else 'Options', _dd_translate)
            return
        if kind == 'empty':
            c.create_text(120,96,text='No completed scans',anchor='n',fill=red,font=font,tags=tag)
        elif kind == 'blocks':
            data = self.auto_captures[-1]
            changed = self._auto_dynamic_positions()
            for slot,block in enumerate(rows):
                y = 43 + slot*62
                dirty = any(block*16<=x<(block+1)*16 for x in changed)
                c.create_text(120,y,text='Block {}:'.format(block),anchor='n',
                              fill=red if dirty else gray,font=font,tags=tag)
                for line_idx in range(2):
                    values = data[block*16+line_idx*8:block*16+(line_idx+1)*8]
                    parts = ['{:02X}'.format(v) for v in values]
                    width = f.measure(' '.join(parts))
                    x = (240-width)//2
                    for j,part in enumerate(parts):
                        absolute = block*16+line_idx*8+j
                        c.create_text(x,y+19+line_idx*24,text=part,anchor='nw',
                                      fill=red if absolute in changed else blue,font=font,tags=tag)
                        x += f.measure(part+(' ' if j<7 else ''))
        elif kind == 'Analysis Notice':
            from _dump_diff_2_lib.screen_catalog import analysis_notice_lines
            c.create_text(120,43,text='Analysis Notice',anchor='n',
                          fill=red,font=('Courier New',12),tags=tag)
            for i,message in enumerate(analysis_notice_lines(_dd_translate)):
                c.create_text(120,81+i*19,text=message,anchor='n',
                              fill=gray,font=('Courier New',12),tags=tag)
        elif kind == 'intro':
            for i,(value,style) in enumerate(rows):
                color = blue if style=='title' else gray if style=='value' else orange
                c.create_text(120 if i==0 else f.measure(' '),43 if i==0 else 81,text=value,anchor='n' if i==0 else 'nw',fill=color,
                              font=font,tags=tag)
        else:
            c.create_text(120,51,text=kind,anchor='n',fill=blue,font=font,tags=tag)
            # Labels and values use shared pixel-measured columns; wrap the
            # complete value instead of ellipsizing or splitting an item.
            label_width = max((f.measure(str(k)) for k,v in rows),default=0)
            gap = f.measure(' ')
            value_width = max(1,230-label_width-gap)
            packed=[]
            for label,value in rows:
                words = str(value).split(' ')
                chunks=[]; current=''
                for word in words:
                    trial = (current+' '+word).strip()
                    if current and f.measure(trial)>value_width:
                        chunks.append(current);current=word
                    else: current=trial
                if current:chunks.append(current)
                if not chunks:chunks=['']
                packed.append((str(label),chunks))
            x = max(5,(240-label_width-gap-min(value_width,max(
                (f.measure(v) for _,chunks in packed for v in chunks),default=0)))//2)
            value_x=x+label_width+gap
            y=89 if 2 <= 1+sum(len(chunks) for _,chunks in packed) <= 4 else 70
            for label,chunks in packed:
                c.create_text(x,y,text=label,anchor='nw',fill=gray,font=font,tags=tag)
                for j,chunk in enumerate(chunks):
                    c.create_text(value_x,y+j*17,text=chunk,anchor='nw',
                                  fill=(__import__('_dump_diff_2_lib.universal_screen',fromlist=['anti_clone_color']).anti_clone_color(label + ' ' + str(value), experimental=(label=='Experimental:'))
                                        if kind=='Anti-Clone Analysis' else
                                        orange if ('CANDIDATE' in chunk or 'EXPERIMENTAL' in label) else blue),
                                  font=font,tags=tag)
                y+=max(1,len(chunks))*18+3
        c.create_text(120,177,text='SRW - '+('Back' if tag == '_dd2_auto_log_view' else 'Options'),anchor='center',fill=blue,
                      font=('Arial',9),tags=tag)
        c.create_text(120,190,text='Page {}/{}'.format(page+1,len(pages)),
                      anchor='center',fill=blue,font=('Courier New',9),tags=tag)
        if page>0: c.create_text(235,43,text='▲',anchor='ne',fill=blue,font=('Arial',9),tags=tag)
        if page+1<len(pages): c.create_text(235,198,text='▼',anchor='se',fill=blue,font=('Arial',9),tags=tag)

    def draw_auto_result(self):
        self._auto_draw_memory('_dd2_auto_result')

    def clear_auto_result(self):
        self.host.getCanvas().delete('_dd2_auto_result')

    def draw_auto_info(self):
        self._auto_draw_memory('_dd2_auto_info')

    def auto_info_next(self):
        self.auto_info_page = min(self._auto_memory_pages()-1, self.auto_info_page+1)
        self._auto_draw_memory('_dd2_auto_result')

    def auto_info_prev(self):
        self.auto_info_page = max(0, self.auto_info_page-1)
        self._auto_draw_memory('_dd2_auto_result')

    def clear_auto_info(self):
        self.host.getCanvas().delete('_dd2_auto_info')

    def draw_auto_actions(self):
        self._auto_clear_ui(except_tag='_dd2_auto_actions')
        self._menu_rows('_dd2_auto_actions',
                        ('Log Saved' if self.auto_report_path else 'Save Log', 'Exit to Menu'),
                        self.auto_actions_cursor, y0=78, spacing=44)

    def clear_auto_actions(self):
        self.host.getCanvas().delete('_dd2_auto_actions')

    def auto_actions_up(self):
        self.auto_actions_cursor = max(0, self.auto_actions_cursor-1)
        self.draw_auto_actions()

    def auto_actions_down(self):
        self.auto_actions_cursor = min(1, self.auto_actions_cursor+1)
        self.draw_auto_actions()

    def auto_actions_choose(self):
        if self.auto_actions_cursor == 0 and self.auto_report_path:
            self.draw_auto_actions()
            return
        self.host._set_state('auto_report_save_busy' if self.auto_actions_cursor == 0
                             else 'auto_exit_busy')

    def draw_auto_exit_confirm(self):
        self._auto_clear_ui(except_tag='_dd2_auto_exit_confirm')
        tag = '_dd2_auto_exit_confirm'
        c = _LocalizedCanvas(self.host.getCanvas())
        c.delete(tag)
        c.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        for y, msg in ((95, 'Log not saved!'), (125, 'Discard results?')):
            c.create_text(120, y, text=msg, anchor='center',
                          fill='#B91C1C' if y == 95 else '#222222',
                          font=('Courier New', 9), tags=tag)

    def clear_auto_exit_confirm(self):
        self.host.getCanvas().delete('_dd2_auto_exit_confirm')

    def _auto_report_text(self):
        from datetime import datetime
        result = self.auto_result or {}
        lines = [
            'DUMP DIFF 2 - AUTO SCAN REPORT',
            'Date: ' + (self.auto_log_created or datetime.now().strftime('%Y.%m.%d %H:%M')),
            'Technology: ' + str(self.auto_technology or 'Unknown'),
            'UID: ' + str(result.get('uid') or 'Unknown'),
            'Scans: ' + str(result.get('scans', 0)),
            'Memory blocks: ' + str(result.get('blocks', 0)),
            'Changed blocks: ' + str(len({x//16 for x in self._auto_dynamic_positions()})),
            'Changed block IDs: ' + ', '.join(map(str, sorted({x//16 for x in self._auto_dynamic_positions()}))),
            'Changed bytes: ' + str(len(self._auto_dynamic_positions())),
            'Possible counters: ' + str(len(result.get('possible_counters', []))),
            '', 'CHANGED BLOCK VALUES (all captures)',
        ]
        for block, values in result.get('details', []):
            lines.append('Block {}'.format(block))
            for i, value in enumerate(values, 1):
                lines.append('  Scan {:02d}: {}'.format(i, bytes(value).hex().upper()))
        lines.extend(['', 'COUNTER HEURISTICS (NOT PROOF OF SECURITY)'])
        for counter in result.get('possible_counters', []):
            lines.append('Block {block}, byte offset {offset}, width {width}, '
                         '{endian}-endian, step {step}'.format(**counter))
        if not result.get('possible_counters'):
            lines.append('No stable counter')
        if self.auto_captures:
            last = self.auto_captures[-1]
            changed_offsets = self._auto_dynamic_positions()
            lines.extend(['', 'FINAL DUMP (all blocks; last scan only)',
                          'Legend: [XX] = byte changed in session'])
            for block in range(len(last)//16):
                parts = []
                for byte_pos in range(16):
                    offset = block*16+byte_pos
                    hx = '{:02X}'.format(last[offset])
                    parts.append('['+hx+']' if offset in changed_offsets else hx)
                lines.append('Block {:03d}: {}'.format(block, ' '.join(parts)))
        ac = result.get('anti_copy') or {}
        lines.extend(['', 'ANTI-CLONE ANALYSIS', 'Status: ' + str(ac.get('status','NOT TESTED'))])
        for key in ('matches','experimental','diagnostics'):
            for item in ac.get(key) or []:
                lines.append(key.upper() + ': ' + str(item))
        # Finalized once by auto_take_scan; reporting must be read-only.
        analysis=result
        lines.extend(['', 'SCAN COMPARISON',
                      'First scan: 1', 'Last scan: '+str(len(self.auto_captures)),
                      'Changed blocks: '+str(len(analysis['changed_blocks'])),
                      'Changed bytes: '+str(len(analysis['changed_bytes'])),
                      '', 'SEQUENTIAL ANALYSIS',
                      'Sequential: '+analysis['sequential_status'],
                       'Counter rollback: '+('ON' if any(c.get('counter_rollback') for c in analysis['sequential_candidates']) else 'OFF'),
                      'Scans: '+str(len(self.auto_captures)),
                      'Dynamic bytes: '+str(len(analysis['changed_bytes'])),
                      'Mirror: NOT TESTED'])
        for counter in analysis['sequential_candidates']:
            lines.extend(['Block: '+str(counter['block'])+' Offset: '+str(counter['offset']),
                          'Width: '+str(counter['width'])+' Endian: '+counter['endian'],
                          'Values: '+' -> '.join(str(x) for x in counter['values']),
                          'Steps: '+', '.join('{:+d}'.format(x) for x in counter['steps'])])
        lines.extend(['', 'SECURITY ASSESSMENT',
                      'Observed memory changes do not establish cryptographic protection.',
                      'No changes do not establish that the tag is cloneable.',
                      'Authentication, reader-side checks and inaccessible memory cannot be',
                      'verified by comparison of these dumps alone.',
                      'This report is observational; not a cloning authorization.', ''])
        return '\n'.join(lines)

    def _auto_track_mf1_sidecar(self, candidate, before, after):
        """Register a Reader-created, same-stem JSON without claiming old files.

        Do not guess a pairing from UID/mtime or from a separate native counter.
        An unrelated or misnumbered JSON must not be silently deleted.
        """
        import stat
        sidecar = os.path.splitext(candidate)[0] + '.json'
        if sidecar in before:
            # Even if unchanged, the old sidecar may contradict the new BIN.
            return 'JSON name conflict'
        if sidecar not in after:
            if os.path.lexists(sidecar):
                return 'Invalid JSON sidecar'
            # Gen1a/readers that produce only BIN are supported. However if
            # a newly created, related JSON has another number, abort safely.
            prefix = os.path.splitext(os.path.basename(candidate))[0].rsplit('_', 1)[0]
            for path in after:
                if (path not in before and path.lower().endswith('.json') and
                    os.path.splitext(os.path.basename(path))[0].rsplit('_', 1)[0] == prefix):
                    return 'Native BIN/JSON filenames differ'
            return 'ok'
        try:
            if os.path.islink(sidecar) or os.path.realpath(sidecar) != sidecar:
                return 'Unsafe JSON sidecar'
            st = os.lstat(sidecar)
            if not stat.S_ISREG(st.st_mode):
                return 'Unsafe JSON type'
            record = (sidecar, st.st_dev, st.st_ino)
            if record not in self.auto_created_files:
                self.auto_created_files.append(record)
            return 'ok'
        except OSError:
            return 'Cannot read native JSON'

    def _auto_discard_failed_read_bundle(self, bundle, existing_meta):
        """Safely discard a newly-created partial native dump, if identified.

        Only an explicit callback path absent from the complete BEFORE
        inventory is eligible. Never infer ownership from arbitrary new files
        or remove a pre-existing, linked, or replaced entry.
        """
        import stat
        candidate = bundle if isinstance(bundle, str) else (
            bundle.get('file') if isinstance(bundle, dict) else None)
        if not isinstance(candidate, str) or os.path.islink(candidate):
            return True  # no safely identified owned file to reclaim
        path = os.path.realpath(candidate)
        root = os.path.realpath('/mnt/upan/dump/mf1')
        if (os.path.dirname(path) != root or not path.lower().endswith('.bin')
                or path in existing_meta):
            return True
        try:
            current = self._auto_file_snapshot('/mnt/upan/dump/mf1')
            if path not in current:
                return True
            st = os.lstat(path)
            if not stat.S_ISREG(st.st_mode):
                return True
            record = (path, st.st_dev, st.st_ino)
            if record not in self.auto_created_files:
                self.auto_created_files.append(record)
            # A failed/partial read can still create a same-stem JSON.
            # Only reclaim it when it is new in this attempt.
            status = self._auto_track_mf1_sidecar(path, existing_meta, current)
            if status != 'ok':
                return False
            outcome = self._auto_cleanup_captures(only_path=path)
            return outcome.get('status') == 'ok'
        except (OSError, ValueError) as exc:
            return False

    def _auto_discard_rejected_dump(self, path):
        """Remove only this rejected session-owned file, never a prior dump."""
        return self._auto_cleanup_captures(only_path=path)

    def auto_cancel(self):
        """Request cancellation of active RF and clean session-owned files."""
        with self._auto_io_lock:
            busy = self._auto_busy
        if busy:
            self._auto_signal_cancel()
            # Worker performs cleanup when it safely regains ownership.
            return {'status': 'cancelled'}
        result = self._auto_cleanup_captures()
        if result['status'] != 'ok':
            self.auto_error = 'Temp cleanup failed'
            return {'status': 'error'}
        return {'status': 'cancelled'}

    def _auto_schedule_result_return(self, state_id):
        """Return to scan-count selection after 5s, only if still on this screen."""
        if getattr(self, '_notice_total', 1)>1:
            return
        canvas = self.host.getCanvas()
        if canvas is None or not hasattr(canvas, 'after'):
            return
        def finish():
            if getattr(self.host, '_current_state_id', None) == state_id:
                self.host._set_state('auto_options')
        canvas.after(5000, finish)

    def draw_auto_unsupported(self):
        self._auto_clear_ui(except_tag='_dd2_auto_unsupported')
        self._dd_notice('_dd2_auto_unsupported', ['Identified:',
            self.auto_unsupported_reason or 'Unknown tag', 'MIFARE Classic only'],
            ['#64748B', '#1647D6', '#B91C1C'])
        self._auto_schedule_result_return('auto_unsupported')

    def clear_auto_unsupported(self):
        self.host.getCanvas().delete('_dd2_auto_unsupported')

    def _auto_cleanup_captures(self, only_path=None):
        """Delete only session-created MF1 dumps except the final capture.

        Never remove pre-existing files, symlinks, or replaced inodes.
        Keep failed deletions tracked so a later attempt is possible.
        """
        import stat
        tracked = list(self.auto_created_files)
        if not tracked:
            return {'status': 'ok', 'deleted': 0}
        root = os.path.realpath('/mnt/upan/dump/mf1')
        keep = getattr(self, 'auto_last_capture_path', None)
        remaining = []
        deleted = 0
        def same_dump(path, bin_path):
            return (bin_path is not None and
                    os.path.splitext(path)[0] == os.path.splitext(bin_path)[0] and
                    os.path.splitext(path)[1].lower() in ('.bin', '.json'))
        for path, device, inode in tracked:
            if only_path is not None and not same_dump(path, only_path):
                remaining.append((path, device, inode))
                continue
            if same_dump(path, keep):
                remaining.append((path, device, inode))
                continue
            try:
                if (os.path.dirname(path) != root or
                        os.path.realpath(path) != path or
                        not path.lower().endswith(('.bin', '.json'))):
                    raise ValueError('Unsafe dump path')
                st = os.lstat(path)
                if (not stat.S_ISREG(st.st_mode) or
                        st.st_dev != device or st.st_ino != inode):
                    raise ValueError('Dump changed since capture')
                os.unlink(path)
                deleted += 1
            except FileNotFoundError:
                pass
            except (OSError, ValueError) as exc:
                remaining.append((path, device, inode))
        self.auto_created_files = remaining
        failed = sum(1 for item in remaining if
                     not same_dump(item[0], keep) and
                     (only_path is None or same_dump(item[0], only_path)))
        return {'status': 'error' if failed else 'ok',
                'deleted': deleted, 'failed': failed, 'kept': keep}

    # Keep the path injectable only for isolated tests. The production default
    # remains the standard iCopy-X/XS dump directory.
    AUTO_REPORT_DIR = '/mnt/upan/dump/auto_scan'

    def auto_report_save_with_delay(self):
        """Show Saving... for at least 3 seconds before displaying the result.

        Called by the busy state's run: handler (worker context), not the UI
        thread. Preserve the original save/error handling and return value.
        """
        import time
        started = time.monotonic()
        try:
            return self.auto_report_save()
        finally:
            remaining = 3.0 - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)

    def auto_report_save(self):
        """Write exactly one report; cleanup retry must not duplicate it."""
        from datetime import datetime
        self.auto_report_last_action = 'save'
        if self.auto_report_path and os.path.isfile(self.auto_report_path):
            cleanup = self._auto_cleanup_captures()
            self.auto_report_error = '' if cleanup.get('status') == 'ok' else 'Dump cleanup failed'
            return {'status': 'ok' if not self.auto_report_error else 'error', 'already_saved': True}
        try:
            folder = self.AUTO_REPORT_DIR
            os.makedirs(folder, exist_ok=True)
            if not self.auto_report_path or not os.path.isfile(self.auto_report_path):
                # Counter is persisted separately: deleted numbers are never reused.
                import re as _re
                counter_path = os.path.join(folder, '.report_next')
                try:
                    with open(counter_path, 'r', encoding='ascii') as counter_file:
                        next_number = max(1, int(counter_file.read().strip()))
                except (OSError, ValueError):
                    next_number = 1
                existing_numbers = [int(m.group(1)) for name in os.listdir(folder)
                                    for m in [_re.match(r'^Report (\d+) ', name)] if m]
                next_number = max([next_number] + [n+1 for n in existing_numbers])
                now = datetime.now()
                self.auto_log_created = now.strftime('%Y.%m.%d %H:%M')
                while True:
                    # 20 chars max for generated visible name.
                    base = 'Report {} {}'.format(next_number, now.strftime('%d.%m.%Y'))
                    # Display width is handled by the notice pager, not the filename counter.
                    path = os.path.join(folder, base + '.log')
                    if not os.path.exists(path):
                        break
                    next_number += 1
                import tempfile
                fd, temporary = tempfile.mkstemp(prefix='.dd2-', suffix='.tmp', dir=folder)
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        f.write(self._auto_report_text())
                        f.write('\n' + self._auto_log_snapshot_line() + '\n')
                        f.flush()
                        os.fsync(f.fileno())
                    if os.path.exists(path):
                        raise FileExistsError('Report filename already exists')
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
                self.auto_report_path = path
                with open(counter_path + '.tmp', 'w', encoding='ascii') as counter_file:
                    counter_file.write(str(next_number + 1))
                os.replace(counter_path + '.tmp', counter_path)
            self.auto_report_error = ''
            cleanup = self._auto_cleanup_captures()
            if cleanup['status'] != 'ok':
                self.auto_report_error = 'Dump cleanup failed'
                return {'status': 'error'}
            return {'status': 'ok'}
        except Exception as exc:
            self.auto_report_error = str(exc)
            return {'status': 'error'}

    def auto_report_discard(self):
        self.auto_report_last_action = 'delete'
        self.auto_report_error = ''
        cleanup = self._auto_cleanup_captures()
        if cleanup['status'] != 'ok':
            self.auto_report_error = 'Dump cleanup failed'
            return {'status': 'error'}
        return {'status': 'ok'}

    def auto_report_retry_action(self):
        """Worker-thread file action; retry whichever action failed."""
        if self.auto_report_last_action == 'save':
            return self.auto_report_save()
        if self.auto_report_last_action == 'delete':
            return self.auto_report_discard()
        self.auto_report_error = 'Nothing to retry'
        return {'status': 'error'}

    def draw_auto_report_retry(self):
        self._catalog_notice('auto_report_retry',
            title='Report save failed' if self.auto_report_last_action == 'save' else 'Cleanup failed',
            error=self.auto_report_error or 'Unknown error')

    def clear_auto_report_retry(self):
        self.host.getCanvas().delete('_dd2_auto_report_retry')

    def draw_auto_report_prompt(self):
        self._catalog_notice('auto_report_prompt')

    def clear_auto_report_prompt(self):
        self.host.getCanvas().delete('_dd2_auto_report_prompt')

    def draw_auto_report_done(self):
        tag = '_dd2_auto_report_done'
        if self.auto_report_error:
            self._catalog_notice('auto_report_done_error', tag, error=self.auto_report_error)
        elif self.auto_report_path:
            self._catalog_notice('auto_report_saved', tag, filename=os.path.basename(self.auto_report_path))
        else:
            self._catalog_notice('auto_report_discarded', tag)

    def clear_auto_report_done(self):
        self.host.getCanvas().delete('_dd2_auto_report_done')

    def draw_auto_unavailable(self):
        self._catalog_notice('auto_unavailable', total=self.auto_scan_count)

    def clear_auto_unavailable(self):
        self.host.getCanvas().delete('_dd2_auto_unavailable')

    def _refresh_catalog(self):
        catalog = {}
        accepted = rejected = 0
        logged_rejections = set()
        for name in self.TYPE_NAMES:
            category = 'MIFARE Classic' if name in self.MF1_VARIANTS else ('iCLASS' if name.startswith('iCLASS ') else name)
            found = []
            try:
                candidates = discover(DUMP_ROOT, category)
            except (OSError, ValueError, TypeError) as exc:
                candidates = []
            for path in candidates:
                try:
                    # Bound memory consumption BEFORE parsing arbitrary JSON or BIN.
                    size = os.path.getsize(path)
                    if not 0 < size <= 1024 * 1024:
                        raise ValueError('file size outside safe range (1..1048576)')
                    raw = load(path, category)
                    if name in self.MF1_VARIANTS and len(raw) != self.MF1_VARIANTS[name]:
                        continue  # Valid dump, but belongs to another MF1 size.
                    if category == 'iCLASS' and len(raw) < 16:
                        raise ValueError('iCLASS record too short')
                    if name.startswith('iCLASS ') and self._dump_subtype(path, category) != name:
                        continue
                    if category == 'T5577' and len(raw) != 48:
                        raise ValueError('T5577 native iCopy dump requires 12 blocks (48 bytes)')
                    if category in ('Paxton Net2', 'Paxton Switch2'):
                        from _dump_diff_2_lib.universal_screen import paxton_detail_blocks
                        if len(paxton_detail_blocks(path, category)) != 8:
                            raise ValueError('Paxton blocks B0..B7 incomplete')
                    found.append(path)
                    accepted += 1
                except (OSError, ValueError, TypeError, KeyError, IndexError, UnicodeError, OverflowError) as exc:
                    if path not in logged_rejections:
                        rejected += 1
                        logged_rejections.add(path)
            if found:
                catalog[name] = found
        self._catalog = catalog
        self._visible_types = [name for name in self.TYPE_NAMES if catalog.get(name)]
        self.type_cursor = min(self.type_cursor, max(0, len(self._visible_types) - 1))


    def _draw(self, tag, lines):
        """Maximum eight 26-column rows; wrap rather than silently truncate."""
        c = _LocalizedCanvas(self.host.getCanvas())
        c.delete(tag)
        rows = [(str(line)[:26], color) for line, color in lines]
        for i, (line, color) in enumerate(rows[:8]):
            c.create_text(19, 42 + i * 17, text=line, anchor='nw',
                          fill=color, font=('Courier New', 9), tags=tag)

    # Custom four-row type picker: avoids firmware list overflowing into footer.
    TYPE_NAMES = ('Paxton Net2', 'Paxton Switch2', 'T5577',
                  'MIFARE Classic Mini', 'MIFARE Classic 1K',
                  'MIFARE Classic 2K', 'MIFARE Classic 4K',
                  'Ultralight / NTAG', 'iCLASS Elite', 'iCLASS Legacy')
    MF1_VARIANTS = {
        'MIFARE Classic Mini': 320,
        'MIFARE Classic 1K': 1024,
        'MIFARE Classic 2K': 2048,
        'MIFARE Classic 4K': 4096,
    }

    def draw_types(self):
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_types'
        c.delete(tag)
        c.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        names = getattr(self, '_visible_types', [])
        # The label says Page x/y with four menu entries per page.
        # Sliding the viewport by one entry mislabeled the visible page.
        top = (self.type_cursor // 4) * 4 if names else 0
        for slot, index in enumerate(range(top, min(top + 4, len(names)))):
            y = 57 + slot * 30
            if index == self.type_cursor:
                c.create_rectangle(12, y-3, 235, y+19, fill='#EAEAEA', outline='', tags=tag)
            c.create_text(27, y, text=names[index], anchor='nw',
                          font=('Courier New', 14), fill='#222222', tags=tag)
        if top:
            c.create_text(3, 44, text='▲', anchor='nw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)
        if top + 4 < len(names):
            c.create_text(3, 198, text='▼', anchor='sw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)
        if not names:
            c.create_text(120, 100, text='No valid dumps found', anchor='center', fill='#AA0000', font=('Courier New', 9), tags=tag)
        c.create_text(120, 190, text='Page {}/{}'.format(self.type_cursor // 4 + 1,
                      max(1, (len(names) + 3) // 4)), anchor='center',
                      fill='#1647D6', font=('Courier New', 9), tags=tag)

    def type_up(self):
        self.type_cursor = max(0, self.type_cursor - 1)
        self.draw_types()

    def type_down(self):
        self.type_cursor = min(len(getattr(self, '_visible_types', [])) - 1, self.type_cursor + 1) if getattr(self, '_visible_types', []) else 0
        self.draw_types()

    def choose_current_type(self):
        names = getattr(self, '_visible_types', [])
        return self.choose_type(names[self.type_cursor]) if names else {'status': 'empty'}

    def clear_types(self):
        self.host.getCanvas().delete('_dd2_types')

    def choose_type(self, name):
        # The four MIFARE Classic variants are independent menu entries, but
        # they all use the same original mf1 folder and the same parser.
        # Never classify by filename: decode the actual memory first.
        # Revalidate when opening a category; files may have changed on SD.
        self._refresh_catalog()
        if name not in self._catalog:
            return {'status': 'empty'}
        variant_size = self.MF1_VARIANTS.get(name)
        category = 'MIFARE Classic' if variant_size is not None else ('iCLASS' if name.startswith('iCLASS ') else name)
        self.category = category
        self.files = list(self._catalog[name])
        if category in ('Ultralight / NTAG', 'iCLASS'):
            self.files.sort(key=lambda path: (self._dump_group(path, category), os.path.basename(path).lower()))
        self.selected = []
        self.cursor = 0
        self.name_scroll = 0
        self.host.set_var('category', name)
        self.host.set_var('picker_title', name)
        self.picker_top = 0
        return {'status': 'ok'}

    def _choose(self, name):
        return self.choose_type(name)

    def type_paxton_net2(self): return self._choose('Paxton Net2')
    def type_paxton_switch2(self): return self._choose('Paxton Switch2')
    def type_t5577(self): return self._choose('T5577')
    def type_mfc(self): return self._choose('MIFARE Classic 1K')
    def type_mfu(self): return self._choose('Ultralight / NTAG')
    def type_iclass(self): return self._choose('iCLASS Elite')

    def _footer_hint(self, label, y=174, tag='_dd2_hint'):
        """Show ALL/SRW action inside content, never on the button bar."""
        c = _LocalizedCanvas(self.host.getCanvas())
        c.delete(tag)
        if label:
            c.create_text(120, y, text='SRW - ' + label.title(), anchor='center',
                          fill='#1647D6', font=('Arial', 10 if tag == '_dd2_picker_hint' else 9), tags=tag)

    def _picker_footer(self):
        self._footer_hint('Info', y=181, tag='_dd2_picker_hint')

    def draw_picker(self):
        self.host.set_var('selected_count', str(len(self.selected)))
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_picker'
        c.delete(tag)
        c.delete('_dd2_validation')
        c.delete('_dd2_picker_hint')
        # Clear stale list rows left by firmware before painting our five-row viewport.
        c.create_rectangle(0, 49, 239, 200, fill='#FFFFFF', outline='', tags=tag)
        # Title comes from the screen definition, not an overlapping canvas label.
        c.create_text(26, 43, text='{}: {}/2'.format(_dd_translate('Sel.'), len(self.selected)),
                      anchor='nw', fill='#222222', font=('Courier New', 11), tags=tag)
        c.create_text(228, 43, text='Dump: {}/{}'.format(self.cursor + 1 if self.files else 0, len(self.files)),
                      anchor='ne', fill='#222222', font=('Courier New', 11), tags=tag)
        if not self.files:
            c.create_text(19, 83, text='No dumps found', anchor='nw',
                          fill='#AA0000', font=('Courier New', 9), tags=tag)
        if self.cursor < self.picker_top:
            self.picker_top = self.cursor
        if self.cursor >= self.picker_top + 5:
            self.picker_top = self.cursor - 4
        self.picker_top = max(0, min(self.picker_top, max(0, len(self.files) - 5)))
        top = self.picker_top
        for slot, idx in enumerate(range(top, min(len(self.files), top + 5))):
            name = os.path.basename(self.files[idx])
            selected = idx in self.selected
            active = idx == self.cursor
            # Reserve the rightmost columns for the scroll arrow, never text.
            window = 18
            # One trailing blank is part of the scrollable view so the final
            # position displays the complete .bin suffix followed by space.
            scroll_text = name + ' '
            max_offset = max(0, len(scroll_text) - window)
            offset = min(self.name_scroll if active else 0, max_offset)
            visible = scroll_text[offset:offset + window]
            y = 64 + slot * 21
            if active:
                c.create_rectangle(1, y - 3, 239, y + 18, fill='#EAEAEA',
                                   outline='', tags=tag)
            c.create_text(26, y, text=('[x] ' if selected else '[ ] ') + visible,
                          anchor='nw', fill='#222222', font=('Courier New', 11), tags=tag)
            if active and max_offset > 0:
                # Only show an arrow for a direction that can still be scrolled.
                if offset < max_offset:
                    c.create_text(5, y + 1, text='▶', anchor='nw',
                                  fill='#00BFFF', font=('Arial', 9), tags=tag)
                if offset > 0:
                    c.create_text(235, y + 1, text='◀', anchor='ne',
                                  fill='#00BFFF', font=('Arial', 9), tags=tag)
        # Vertical indicators at the extreme left, outside file text rows.
        if top > 0:
            c.create_text(3, 44, text='▲', anchor='nw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)
        if top + 5 < len(self.files):
            c.create_text(3, 198, text='▼', anchor='sw',
                          fill='#1647D6', font=('Arial', 9), tags=tag)
        c.create_text(120, 193, text='OK - Select/Deselect', anchor='center',
                      fill='#1647D6', font=('Arial', 10), tags=tag)
        self._picker_footer()

    def picker_up(self):
        if self.files: self.cursor = max(0, self.cursor - 1)
        self.name_scroll = 0
        self.draw_picker()

    def picker_down(self):
        if self.files: self.cursor = min(len(self.files) - 1, self.cursor + 1)
        self.name_scroll = 0
        self.draw_picker()

    def picker_left(self):
        self.name_scroll = max(0, self.name_scroll - 3)
        self.draw_picker()

    def picker_right(self):
        if self.files:
            name = os.path.basename(self.files[self.cursor])
            self.name_scroll = min(max(0, len(name)+1-18), self.name_scroll+3)
        self.draw_picker()

    @staticmethod
    def _abc_mfc_uid(raw):
        """Extract the MIFARE Classic UID from the first manufacturer block."""
        if not raw or len(raw) < 16:
            return None
        # Manufacturer block: 7-byte UID uses SAK at byte 7, while
        # 4-byte UID has its BCC at byte 4. 4-byte is the conservative
        # fallback; 7-byte identification is also checked against log UID.
        return (raw[:4].hex().upper(), raw[:7].hex().upper())

    def _abc_log_evidence(self, raw):
        """Read existing Auto Scan results for this UID; never rerun analysis."""
        if self.category != 'MIFARE Classic':
            return []
        candidates = self._abc_mfc_uid(raw)
        if not candidates:
            return []
        import glob
        import re
        evidence = []
        paths = sorted(glob.glob(os.path.join(self.AUTO_REPORT_DIR, '*.log')))
        for path in paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    snapshot = self._auto_log_decode_snapshot(f.read(1048577).splitlines()) if os.path.getsize(path)<=1048576 else None
                if not snapshot:
                    continue
                uid = re.sub(r'[^0-9A-F]', '', str(snapshot['result'].get('uid') or '').upper())
                if uid not in candidates:
                    continue
                evidence.append({'path': path, 'snapshot': snapshot,
                                 'counters': snapshot['result'].get('possible_counters') or [],
                                 'changed': snapshot['result'].get('changed_bytes') or []})
            except (OSError, ValueError, TypeError, KeyError) as exc:
                continue
        return evidence


    @staticmethod
    def _group_sequential_evidence(records):
        """Group the same saved sequence, retaining each interpretation's sources."""
        reports = []
        groups = {}
        for path, uid, scans, candidate in records:
            values = tuple(candidate.get('values') or [])
            steps = tuple(candidate.get('steps') or [b-a for a,b in zip(values,values[1:])])
            rollback = bool(candidate.get('counter_rollback', False))
            key = (uid or path, scans, candidate['block'], candidate['offset'], values, steps, rollback)
            if path not in reports:
                reports.append(path)
            source = reports.index(path) + 1
            if key not in groups:
                groups[key] = {'uid': uid, 'scans': scans, 'block': candidate['block'],
                               'offset': candidate['offset'], 'values': values, 'steps': steps,
                               'counter_rollback': rollback, 'variants': {}}
            variants = groups[key]['variants']
            sources = variants.setdefault((candidate['width'], candidate['endian']), [])
            if source not in sources:
                sources.append(source)
        return list(groups.values()), reports

    def _abc_sections(self, raws):
        """MFC Compare Anti-Clone findings; 2 dumps do not prove a sequence."""
        if self.category != 'MIFARE Classic':
            return {'A': [], 'B': [], 'C': True}
        anti = ['Anti-Clone Analysis']
        for index, raw in enumerate(raws):
            prefix = 'A' if len(raws) == 2 and index == 0 else 'B'
            result = self._pm3_result(raw)
            anti.append('Dump {}: {}'.format(prefix, result.get('status', 'NOT TESTED')))
            for kind, key in (('Match', 'matches'), ('Exp', 'experimental')):
                for entry in result.get(key) or []:
                    name = entry.get('name', entry.get('family', 'Unknown')) if isinstance(entry, dict) else str(entry)
                    anti.append('{} {}: {}'.format(prefix, kind, name))
            for note in result.get('diagnostics') or []:
                anti.append('{} Diag: {}'.format(prefix, note))
        if len(raws) == 2:
            comparison = analyze_anticopy(raws[0], raws[1], [self._pm3_result(x) for x in raws])
            anti.append('Same UID: {}'.format('YES' if comparison.get('same_uid') else 'NO'))
            if comparison.get('comparison_valid'):
                for key, label in (('data_blocks_changed','Data blocks'),
                                   ('trailer_blocks_changed','Trailers'),
                                   ('manufacturer_blocks_changed','Manufacturer')):
                    anti.append('{}: {}'.format(label, len(comparison.get(key) or [])))
                anti.append('Dynamic: {}'.format('POSSIBLE' if comparison.get('dynamic_candidate') else 'NO'))
        anti.append('Heuristic: NOT PROOF')
        # No Sequential page for two dumps; Auto Scan results are handled by Details.
        return {'A': anti, 'B': [], 'C': True}

    @staticmethod
    def _abc_pad_section(lines, section):
        """Append complete optional sections at page boundaries (8, then 7 rows)."""
        if not section:
            return
        if lines:
            while len(lines) < 8 or (len(lines) - 8) % 7:
                lines.append('')
        lines.extend(section)
        while len(lines) < 8 or (len(lines) - 8) % 7:
            lines.append('')

    def _load_json_sidecar(self, path, any_category=False):
        """Parse the same-stem Proxmark3 JSON sidecar; None when absent.

        Single read/parse point for the whole Details path. MFC and iCLASS
        Details used to open and json.load() this same file a second time
        (once here-equivalent, once more via the old _json_metadata) on
        every render; they now call this once and reuse the parsed object.
        Also now rejects a non-dict JSON root the same way for every
        caller (ValueError), instead of MFC/iCLASS each risking an
        uncaught AttributeError/TypeError from calling .get() on it.
        """
        if not any_category and self.category in ('Paxton Net2', 'Paxton Switch2'):
            return None
        sidecar = path if path.lower().endswith('.json') else os.path.splitext(path)[0] + '.json'
        if not os.path.isfile(sidecar):
            return None
        with open(sidecar, 'r', encoding='utf-8') as stream:
            obj = json.load(stream)
        if not isinstance(obj, dict):
            raise ValueError('Invalid JSON root')
        return obj

    @staticmethod
    def _json_metadata_from_obj(obj):
        """Flatten an already-parsed JSON sidecar into scalar (label, value) items.

        Preserve JSON key spelling/order. Do not present memory block dictionaries
        as scalar metadata; those are rendered separately as memory pages.
        """
        if not obj:
            return []
        items = []
        def collect(mapping):
            for key, value in mapping.items():
                # Original iCLASS metadata bookkeeping is not a Details field.
                if key == 'Created' and value == 'proxmark3':
                    continue
                # FileType is visible under the display label Type.
                if isinstance(value, dict):
                    if key == 'Card':
                        collect(value)
                    continue
                if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    rendered = str(value).strip()
                    if rendered:
                        items.append(('Type' if str(key) == 'FileType' else str(key), rendered))
                elif isinstance(value, (list, tuple)) and value:
                    # Preserve informational arrays without confusing them with memory blocks.
                    if all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in value):
                        items.append(('Type' if str(key) == 'FileType' else str(key), ', '.join(map(str, value))))
        collect(obj)
        return items

    def _json_metadata(self, path):
        """Optional same-stem Proxmark3 metadata; Paxton TXT never probes JSON.

        Unchanged public entry point for the single-read call sites
        (T5577, Ultralight, the generic fallback list). MFC and iCLASS
        call _load_json_sidecar + _json_metadata_from_obj directly so
        they only touch the file once.
        """
        return self._json_metadata_from_obj(self._load_json_sidecar(path))

    def show_details(self):
        """Synchronous entry for local tools; device uses prepare/finish_details."""
        result = self._prepare_details_model()
        if self._details_notice:
            self.host.show_toast(self._details_notice[0], timeout=self._details_notice[1])
        return {'status': self._details_position()} if result['status'] == 'model_ready' else result

    def _prepare_details_model(self):
        self._details_notice = None
        self._universal_details_pages = None
        if not self.files or not self.selected:
            self._details_notice = (_dd_translate('No dump selected'), 1500)
            return {'status': 'invalid'}
        path = self.files[self.selected[-1]]
        name = os.path.basename(path)
        title = self._dump_subtype(path, self.category)
        lines = [title]
        lines.extend(_dd_filename_lines('Dump: ' + name, 26))
        lines.extend(([] if self.category in ('Paxton Net2', 'Paxton Switch2', 'MIFARE Classic', 'iCLASS', 'T5577') else ['Type: ' + self.category]) + [
                      'Size: {} bytes'.format(os.path.getsize(path)),
                      'Date: ' + time.strftime('%Y.%m.%d %H:%M',
                                    time.localtime(os.path.getmtime(path)))])
        data = b''
        try:
            data = load(path, self.category)
            if self.category not in ('T5577', 'Paxton Net2', 'Paxton Switch2'):
                ident = identity(path, self.category, data)
                if ident:
                    lines.append('{}: {}'.format(*ident))
            info = json_info_lines(path, self.category)
            if info is not None:
                boundary = next((i for i, v in enumerate(info)
                                 if re.match(r'^\s*B\d+:', str(v))), len(info))
                lines = ([title] + _dd_filename_lines('Dump: ' + name, 26) +
                         ['Size: {} bytes'.format(os.path.getsize(path)),
                          'Date: ' + time.strftime('%d/%m/%Y %H:%M',
                                      time.localtime(os.path.getmtime(path)))] +
                         [v for v in info[:boundary]
                          if not str(v).startswith(('Filename:', 'Dump:', 'File:',
                                                     'FileType:', 'Type:', 'Size:',
                                                     'Modified:', 'Date:'))
                          and str(v) != name])
            # Generic formats: preserve root/Card scalar labels from same-stem JSON.
            # Dedicated iCLASS/MFC/UL/T5577 screens paginate these separately.
            if self.category not in ('Paxton Net2', 'Paxton Switch2',
                                     'iCLASS', 'MIFARE Classic',
                                     'Ultralight / NTAG', 'T5577'):
                existing = {str(v).split(':', 1)[0].strip().upper() for v in lines}
                for key, value in self._json_metadata(path):
                    if key.upper() not in existing:
                        lines.append('{}: {}'.format(key, value))
                        existing.add(key.upper())
            # Render MIFARE Classic from 16-byte blocks directly. Every 32-HEX
            # block becomes EXACTLY two 16-HEX rows, aligned at the same X.
            # This bypasses any legacy 8-HEX-per-row formatter or JSON wrapping.
            if self.category == 'MIFARE Classic':
                for offset in range(0, len(data), 16):
                    value = data[offset:offset + 16].hex().upper()
                    block_no = offset // 16
                    lines.append('B{}: {}'.format(block_no, value[:16]))
                    if len(value) > 16:
                        lines.append('      ' + value[16:32])
            elif self.category in ('Paxton Net2', 'Paxton Switch2'):
                from _dump_diff_2_lib.universal_screen import paxton_detail_blocks
                blocks = paxton_detail_blocks(path, self.category)
                lines.append('UID (B0): ' + blocks[0][2].hex().upper())
                lines.append('Blocks: 8')
                lines.extend('{}: {}'.format(('Password B1' if n == 1 else 'Key/Pwd B2' if n == 2 else 'Config B3' if n == 3 else 'User B{}'.format(n)), value.hex().upper()) for n, _, value in blocks[1:])
            else:
                if self.category == 'T5577':
                    for i in range(0, len(data), 4):
                        page, block = (0, i//4) if i < 32 else (1, (i-32)//4)
                        lines.append('P{}/B{}: {}'.format(page, block, data[i:i+4].hex().upper()))
                else:
                    lines.extend(detail_block_lines(path, self.category, data))
        except (ValueError, IOError, OSError) as exc:
            lines.append('Parse: ' + str(exc))
        if self.category == 'Ultralight / NTAG':
            # Native MFU dump parser removes its 56-byte metadata header.
            # Memory pages are 4 bytes each; never display header as pages.
            try:
                memory = load(path, self.category)
                if not memory or len(memory) % 4:
                    raise ValueError('Invalid Ultralight memory')
                uid_info = identity(path, self.category, memory)
                uid = uid_info[1] if uid_info and uid_info[0] == 'UID' else None
                # Native MFU JSON metadata is distinct from memory blocks.
                # Display every card field except creator/file-type bookkeeping.
                metadata = dict(self._json_metadata(path))
                sections = []
                # Every scalar JSON field gets its own label/value; 3 fields
                # per page = 6 rows, 19px pitch, safely above the footer.
                pairs = [(k, v) for k, v in metadata.items() if k.upper() != 'UID']
                page, count = [], 0
                for key, val in pairs:
                    needed = 1 + max(1, (len(str(val)) + 21)//22)
                    if page and count + needed > 6:
                        sections.append(('json_fields', page)); page, count = [], 0
                    if needed > 6:
                        # A long scalar is split into continuation pages.
                        chunks = [str(val)[j:j+110] for j in range(0, len(str(val)), 110)]
                        for j, chunk in enumerate(chunks):
                            if page:
                                sections.append(('json_fields', page)); page, count = [], 0
                            sections.append(('json_fields', [(key if j == 0 else key+' (cont.)', chunk)]))
                        continue
                    page.append((key, val)); count += needed
                if page: sections.append(('json_fields', page))
                block_rows = [(i // 4, memory[i:i+4].hex().upper())
                              for i in range(0, len(memory), 4)]
                block_capacity = max(1, (177 - 55) // 16)
                sections.extend(('blocks', block_rows[i:i+block_capacity])
                                for i in range(0, len(block_rows), block_capacity))
                self._ul_details = {
                    'type': title, 'name': name,
                    'date': time.strftime('%d/%m/%Y %H:%M',
                                          time.localtime(os.path.getmtime(path))),
                    'uid': uid, 'sections': sections,
                    'pages': 1 + len(sections),
                }
                self.details_lines = ['ULTRALIGHT DETAILS'] * self._ul_details['pages']
                self.details_page = 0
                return {'status': 'model_ready'}
            except (ValueError, OSError, IOError) as exc:
                self._details_notice = ('Ultralight: ' + str(exc), 2500)
                return {'status': 'invalid'}
        # MIFARE Classic: read-only Details with full 16-byte blocks.
        # Do not infer live SAK/ATQA from a raw memory-only BIN.
        self._mfc_details = None
        if self.category == 'MIFARE Classic' and data and len(data) % 16 == 0:
            card = {}
            sidecar_obj = None
            try:
                sidecar_obj = self._load_json_sidecar(path)
                if sidecar_obj and isinstance(sidecar_obj.get('Card'), dict):
                    card = sidecar_obj['Card']
            except (ValueError, IOError, OSError, TypeError):
                card, sidecar_obj = {}, None
            uid = str(card.get('UID') or data[:4].hex().upper()).upper()
            atqa = str(card.get('ATQA') or '').upper()
            sak = str(card.get('SAK') or '').upper()
            metadata = [('UID:', uid)]
            if atqa: metadata.append(('ATQA:', atqa))
            if sak: metadata.append(('SAK:', sak))
            for key, value in self._json_metadata_from_obj(sidecar_obj):
                if key.upper() not in ('UID', 'ATQA', 'SAK'):
                    metadata.append((key + ':', value))
            evidence = self._abc_log_evidence(data)
            report_name = os.path.basename(evidence[-1]['path']) if evidence else ''
            changed = []
            if evidence:
                saved = evidence[-1]['snapshot']['result']
                ac = self._pm3_result(data)
                findings = [str(x.get('name') or x.get('family') or 'Unknown')
                            if isinstance(x, dict) else str(x)
                            for x in (ac.get('matches') or [])] + [
                            (str(x.get('name') or x.get('family') or 'Unknown')
                             if isinstance(x, dict) else str(x)) + ' (EXP)'
                            for x in (ac.get('experimental') or [])]
                # An Auto Scan log without an Anti-Clone verdict is not a reason
                # to skip Anti-Clone: analyse the selected MIFARE dump locally.
                if str(ac.get('status', '')).upper() in ('', 'NOT TESTED', 'NOT FOUND', 'NOT IMPLEMENTED', 'NO MATCH'):
                    ac = self._pm3_result(data)
                    findings = [str(x.get('name') or x.get('family') or 'Unknown')
                                if isinstance(x, dict) else str(x)
                                for x in (ac.get('matches') or [])] + [
                                (str(x.get('name') or x.get('family') or 'Unknown')
                                 if isinstance(x, dict) else str(x)) + ' (EXP)'
                                for x in (ac.get('experimental') or [])]
                findings = ['Status: ' + str(ac.get('status', 'NO MATCH'))] + (['Reason: '+str(ac['reason'])] if ac.get('reason') else []) + findings + ['Diag: ' + str(x) for x in (ac.get('diagnostics') or [])]
                changed = [int(x) for x in (saved.get('changed_bytes') or [])
                           if str(x).isdigit()]
                counters = saved.get('possible_counters') or []
                scans = len(evidence[-1]['snapshot']['captures'])
                # Use saved analysis only; Details must not rerun Sequential.
                valid_counters = [(candidate, candidate.get('values') or [])
                                  for candidate in (saved.get('sequential_candidates') or [])
                                  if isinstance(candidate,dict) and candidate.get('status')=='ON']
                sequential_rows = ['Sequential: {}'.format('ON' if valid_counters else 'OFF'),
                                   'Source: Auto Scan log', 'Scan: {}'.format(scans)]
                counter_groups, _ = self._group_sequential_evidence([
                    (evidence[-1]['path'], uid, scans, candidate) for candidate, _ in valid_counters])
                for candidate in counter_groups:
                    values = candidate['values']
                    sequential_rows.extend([
                        'Block: {}'.format(candidate['block']),
                        'Counter: {}'.format(' '.join('{:02X}'.format(v) for v in values)),
                        'Steps: {}'.format(' '.join('{:+d}'.format(values[i+1]-values[i])
                                                      for i in range(len(values)-1))),
                        'Offset: {}'.format(candidate['offset'])])
                    for width, endian in candidate['variants']:
                        sequential_rows.append('Width/endian: {}/{}'.format(width, endian))
                    sequential_rows.append('Rollback: {}'.format('ON' if candidate.get('counter_rollback') else 'OFF'))
            else:
                protection = self._pm3_result(data)
                findings = [str(x.get('name') or x.get('family') or 'Unknown')
                            if isinstance(x, dict) else str(x)
                            for x in (protection.get('matches') or [])] + [
                            (str(x.get('name') or x.get('family') or 'Unknown')
                             if isinstance(x, dict) else str(x)) + ' (EXP)'
                            for x in (protection.get('experimental') or [])]
                findings = ['Status: ' + str(protection.get('status', 'NOT TESTED'))] + (['Reason: '+str(protection['reason'])] if protection.get('reason') else []) + findings + ['Diag: ' + str(x) for x in (protection.get('diagnostics') or [])]
                sequential_rows = ['Min. 3 scans required', 'Sequential: OFF']
            findings = [_dd_translate(row) for row in findings]
            # MFC Details only: 22-column, six-row pagination; no dropped diagnostics.
            def wrap_words(text, width=22):
                raw = str(text).strip()
                if len(raw) <= width:
                    return [raw]
                if ':' in raw:
                    label, value = raw.split(':', 1)
                    if len(label) + 1 <= width:
                        label = label + ':'
                        value = value.strip()
                        if value:
                            return [label] + wrap_words(value, width)
                words = raw.split()
                result, line = [], ''
                for word in words:
                    if len(word) > width:
                        if line:
                            result.append(line)
                            line = ''
                        result.extend(word[i:i+width] for i in range(0,len(word),width))
                    elif len(line + (' ' if line else '') + word) > width:
                        result.append(line)
                        line = word
                    else:
                        line += (' ' if line else '') + word
                if line:
                    result.append(line)
                return result or ['']

            sections = []
            def paginate_rows(title, rows):
                sections.append((title,[(str(raw),[_dd_translate(str(raw))]) for raw in rows]))

            anti_findings = findings or (['NOT TESTED'] if len(data) not in (1024,4096) else ['NO MATCH'])
            # Explain the limits of detection immediately before Anti-Clone results.
            sections.append(('Analysis Notice', [
                ('Detection is not', ['Detection is not']),
                ('proof of protection.', ['proof of protection.']),
                ('No match does not', ['No match does not']),
                ('prove its absence.', ['prove its absence.']),
            ]))
            paginate_rows('Anti-Clone Analysis', anti_findings)
            paginate_rows('Sequential Analysis', sequential_rows)
            structure = analyze_mfc_structure(data)
            if structure.get('supported'):
                structure_rows = [
                    'Sectors: {}'.format(structure['sectors']),
                    'Trailers: {}'.format(len(structure['trailers'])),
                    'Access bits: {}'.format('VALID' if not structure['access_invalid'] else 'INVALID / UNKNOWN'),
                    'Invalid trailers: {}'.format(len(structure['access_invalid'])),
                    'Value blocks: {}'.format(len(structure['value_blocks'])),
                    'UID BCC: {}'.format('VALID' if structure['bcc0'] else 'INVALID')]
                structure_rows.extend('Invalid trailer B{}'.format(n) for n in structure['access_invalid'])
                structure_rows.extend('Value block B{}'.format(n) for n in structure['value_blocks'])
                structure_rows.append('Structure, not authenticity')
                paginate_rows('Classic Structure:', structure_rows)

            # Fixed-width Courier New 12 layout. Pagination is determined
            # by predefined 8-byte HEX rows, never by runtime font metrics.
            def metadata_row_count(label, value):
                raw = str(value).upper()
                if re.fullmatch(r'[0-9A-F]+', raw) and len(raw) % 2 == 0:
                    lines = (len(raw) // 2 + 7) // 8
                    return 1 if lines <= 1 else 1 + lines
                return 1 + max(1, (len(str(value))+21)//22) if len(str(label))+len(str(value))+1 > 22 else 1
            card_page, used_rows = [], 0
            for item in metadata:
                needed = metadata_row_count(*item)
                if card_page and used_rows + needed > 5:
                    sections.append(('Card:', card_page))
                    card_page, used_rows = [], 0
                card_page.append(item)
                used_rows += needed
            if card_page:
                sections.append(('Card:', card_page))
            blocks = [(i // 16, data[i:i+16].hex().upper())
                      for i in range(0, len(data), 16)]
            # Two complete 16-byte blocks per page, no page split.
            sections.extend(('blocks', blocks[i:i+2]) for i in range(0, len(blocks), 2))
            self._mfc_details = {
                'type': title, 'name': name,
                'date': time.strftime('%d/%m/%Y %H:%M', time.localtime(os.path.getmtime(path))),
                'findings': findings, 'sections': sections,
                'anti_clone_result': ac if evidence else protection,
                'card_type': str(card.get('Type') or card.get('type') or ''),
                'sequential_status': 'ON' if evidence and valid_counters else 'OFF',
                'changed_bytes': set(changed),
                'report_name': report_name,
                'pages': 1 + len(sections),
            }
            self.details_lines = ['MFC DETAILS'] * self._mfc_details['pages']
            self.details_page = 0
            return {'status': 'model_ready'}
        self._ul_details = None
        self._iclass_details = None
        if self.category == 'iCLASS':
            try:
                card = {}
                blocks = []
                sidecar_obj = self._load_json_sidecar(path)
                if sidecar_obj is not None:
                    card = sidecar_obj.get('Card') or {}
                    if not isinstance(card, dict):
                        raise ValueError('Invalid iCLASS Card object')
                    raw_blocks = sidecar_obj.get('blocks') or {}
                    if not isinstance(raw_blocks, dict):
                        raise ValueError('Invalid iCLASS blocks')
                    for key in sorted(raw_blocks, key=lambda n: int(n)):
                        value = str(raw_blocks[key]).upper()
                        if len(value) != 16 or not re.match(r'^[0-9A-F]{16}$', value):
                            raise ValueError('Invalid iCLASS Block {}'.format(key))
                        blocks.append((int(key), value))
                else:
                    raw = load(path, self.category)
                    if not raw or len(raw) % 8:
                        raise ValueError('Invalid iCLASS memory')
                    blocks = [(i//8, raw[i:i+8].hex().upper()) for i in range(0, len(raw), 8)]
                entries = []
                for key, value in self._json_metadata_from_obj(sidecar_obj):
                    entries.append((key, value, bool(re.fullmatch(r'[0-9A-Fa-f]{16}', value))))
                # First page: type/name/date and CSN (when present).
                csn = next((value for label, value, ishex in entries if label.upper() == 'CSN'), '')
                entries = [item for item in entries if item[0].upper() != 'CSN']
                entries.extend(('Block {}'.format(n), v, True) for n, v in blocks)
                # Two rows per item; 3 entries per page without empty lines.
                # Six content rows; reserve one for label and as many as
                # necessary for the value. 8-byte HEX always takes one row.
                groups, group, used = [], [], 0
                for label, value, ishex in entries:
                    if ishex:
                        rows = 1 if len(value) <= 16 else (len(value)+15)//16
                    else:
                        rows = max(1, (len(str(value))+21)//22)
                    if group and used + 1 + rows > 6:
                        groups.append(group); group, used = [], 0
                    # Preserve complete metadata; universal Details paginates it.
                    group.append((label, value, ishex))
                    used += 1 + rows
                if group: groups.append(group)
                self._iclass_details = {
                    'type': title, 'name': name,
                    'date': time.strftime('%d/%m/%Y %H:%M', time.localtime(os.path.getmtime(path))),
                    'csn': csn, 'groups': groups, 'pages': 1 + len(groups),
                }
                self.details_lines = ['ICLASS DETAILS'] * self._iclass_details['pages']
                self.details_page = 0
                return {'status': 'model_ready'}
            except (ValueError, OSError, IOError, TypeError, KeyError) as exc:
                self._details_notice = ('iCLASS: ' + str(exc), 2500)
                return {'status': 'invalid'}
        if self.category in ('Paxton Net2', 'Paxton Switch2'):
            # Two fixed pages. Rendering reads these fields, not legacy wrapped lines.
            from _dump_diff_2_lib.universal_screen import paxton_detail_blocks
            blocks = paxton_detail_blocks(path, self.category)
            self._paxton_details = {
                'type': title, 'name': name,
                'size': os.path.getsize(path),
                'date': time.strftime('%d/%m/%Y %H:%M',
                                      time.localtime(os.path.getmtime(path))),
                'blocks': [item[2].hex().upper() for item in blocks],
            }
            self.details_lines = ['PAXTON DETAILS'] * 3
            self.details_page = 0
            return {'status': 'model_ready'}
        self._paxton_details = None
        self._t5577_details = None
        if self.category == 'T5577':
            # No factory UID for T5577. Display all captured Page 0 / Page 1
            # blocks; never invent a credential or silently omit trailing data.
            try:
                memory = load(path, self.category)
                if not memory or len(memory) % 4:
                    raise ValueError('Invalid T5577 block data')
                # Native iCopy-X T5577: Page 0 = 8 blocks, Page 1 = 4.
                if len(memory) != 48:
                    raise ValueError('T5577 native dump requires 48 bytes')
                blocks = [memory[i:i+4].hex().upper() for i in range(0, 48, 4)]
                self._t5577_details = {
                    'name': name,
                    'date': time.strftime('%d/%m/%Y %H:%M',
                                          time.localtime(os.path.getmtime(path))),
                    'blocks': blocks,
                    'pages': 4,
                    'json_fields': self._json_metadata(path),
                }
                # Additional JSON pages must not disturb the four approved block pages.
                fields = self._t5577_details['json_fields']
                json_pages, page, used = [], [], 0
                for key, val in fields:
                    parts = [str(val)[j:j+22] for j in range(0, len(str(val)), 22)]
                    for j in range(0, len(parts), 5):
                        chunk = parts[j:j+5]
                        needed = 1 + len(chunk)
                        if page and used + needed > 6:
                            json_pages.append(page); page, used = [], 0
                        page.append((key if j == 0 else key+' (cont.)', '\n'.join(chunk)))
                        used += needed
                if page: json_pages.append(page)
                self._t5577_details['json_pages'] = json_pages
                self._t5577_details['pages'] += len(self._t5577_details['json_pages'])
                self.details_lines = ['T5577 DETAILS'] * self._t5577_details['pages']
                self.details_page = 0
                return {'status': 'model_ready'}
            except (ValueError, OSError, IOError) as exc:
                self._details_notice = ('T5577: ' + str(exc), 2500)
                return {'status': 'invalid'}
        # Optional A and B are shared with Compare; C is the complete details
        # already assembled above. A/B are omitted entirely when not supported.
        if self.category == 'MIFARE Classic':
            sections = self._abc_sections([data])
            prefix = []
            self._abc_pad_section(prefix, sections['A'])
            self._abc_pad_section(prefix, sections['B'])
            lines = prefix + lines
        result = []
        for line in lines:
            line = str(line)
            # Keep HH:MM together: never allow spaces after the colon.
            if line.startswith('Date: '):
                line = re.sub(r'(\\d{1,2}):\\s+(\\d{2})\\b', r'\\1:\\2', line)
                result.append(line)
                continue
            if self.category == 'iCLASS' and re.match(r'^(?:Config|Configuration):\s*[0-9A-Fa-f]+$', line):
                result.extend(_dd_hex_label_rows(re.sub(r'^Configuration:', 'Config:', line)))
            elif self.category == 'MIFARE Classic' and (
                    re.match(r'^B\d+: [0-9A-F]{1,16}$', line) or
                    re.match(r'^ {6}[0-9A-F]{1,16}$', line)):
                result.append(line)
            else:
                result.extend(_dd_hex_label_rows(line))
        self._details_filename_rows = set()
        for idx, item in enumerate(result):
            if item.startswith('Dump: '):
                self._details_filename_rows.add(idx)
                j = idx + 1
                while j < len(result) and not result[j].startswith(('Type:', 'Size:', 'Date:', 'UID:', 'B0:', 'B1:', 'FileType:', 'Taille:', 'Date:')) and not re.match(r'^B\d+:', result[j]):
                    if result[j].startswith((' ', 'A.bin', 'B.bin')) or result[j].endswith(('.bin', '.json', '.txt', '.eml')):
                        self._details_filename_rows.add(j)
                    else:
                        break
                    j += 1
        # Keep multi-line memory blocks together. Do not split the first
        # and second half of a 16-byte Classic block across screen boundaries.
        if self.category in ('MIFARE Classic', 'T5577'):
            grouped = []
            i = 0
            while i < len(result):
                row = result[i]
                if (self.category == 'MIFARE Classic' and
                        re.match(r'^B\d+: [0-9A-F]{16}$', row) and
                        i + 1 < len(result) and
                        re.match(r'^ {6}[0-9A-F]{16}$', result[i+1])):
                    grouped.append([row, result[i+1]])
                    i += 2
                else:
                    grouped.append([row]); i += 1
            packed = []
            for group in grouped:
                capacity = 8 if len(packed) < 8 else 7
                if len(packed) >= 8:
                    capacity = 7
                    used = (len(packed)-8) % 7
                else:
                    used = len(packed)
                remaining = capacity - used
                if len(group) > remaining:
                    packed.extend([''] * remaining)
                packed.extend(group)
            result = packed
        self.details_lines = result
        self.details_page = 0
        return {'status': 'model_ready'}

    def _stop_details_filename_scroll(self):
        """Cancel the active Canvas timer when leaving or redrawing Details."""
        timer = getattr(self, '_details_name_timer', None)
        self._details_name_timer = None
        if timer is not None:
            try:
                self.host.getCanvas().after_cancel(timer)
            except (AttributeError, ValueError, RuntimeError):
                pass
        self._details_name_generation = getattr(
            self, '_details_name_generation', 0) + 1

    def _draw_details_filename(self, c, tag, name, y, face):
        from tkinter import font as tkfont
        self._stop_details_filename_scroll()
        measure=tkfont.Font(family=face[0],size=face[1]).measure
        label=_dd_translate('Name:')
        x=9;name_x=x+measure(label+' ');width=231-name_x
        c.create_text(x,y,text=label,anchor='nw',fill='#64748B',font=face,tags=tag)
        def visible(value):
            end=0
            while end<len(value) and measure(value[:end+1])<=width:end+=1
            return value[:end]
        name=str(name)
        text_id=c.create_text(name_x,y,text=visible(name),anchor='nw',fill='#1647D6',font=face,tags=tag)
        if measure(name)<=width:return
        cycle=' '+name+' '
        generation=self._details_name_generation;offset=0
        filename_page=self.details_page
        def tick():
            nonlocal offset
            if (generation!=self._details_name_generation or self.details_page!=filename_page or
                    getattr(self.host,'_current_state_id',None) not in ('details_first','details_middle','details_last','details_single')):
                return
            offset=(offset+1)%len(cycle)
            c.itemconfigure(text_id,text=visible(cycle[offset:]+cycle[:offset]))
            self._details_name_timer=c.after(240,tick)
        self._details_name_timer=c.after(600,tick)

    @staticmethod
    def _translate(text):
        return _dd_translate(text)

    def _localized_canvas(self):
        return _LocalizedCanvas(self.host.getCanvas())

    def draw_details(self):
        """Single Details renderer for all supported dump categories."""
        from _dump_diff_2_lib.universal_screen import render_details
        if self._universal_details_pages is None:
            self._ensure_universal_details()
        self._stop_details_filename_scroll()
        if not render_details(self):
            raise ValueError('No Details pages for {}'.format(self.category))

    def _details_page_count(self):
        if self._universal_details_pages is None:
            self._ensure_universal_details()
        return len(self._universal_details_pages)

    def _ensure_universal_details(self):
        """Build once per dump; no legacy rendering fallback."""
        if self._universal_details_pages is None:
            from _dump_diff_2_lib.universal_screen import build
            pages = build(self)
            if not pages:
                raise ValueError('Cannot build Details for {}'.format(self.category))
            self._universal_details_pages = pages
            try:
                from _dump_diff_2_lib.universal_screen import validate_pages
                validate_pages(self.category, pages)
            except Exception:
                pass  # Diagnostics must not interrupt Details.

    def _details_position(self):
        pages = self._details_page_count()
        if pages == 1:
            return 'single'
        if self.details_page == 0:
            return 'first'
        if self.details_page >= pages - 1:
            return 'last'
        return 'middle'

    def next_details(self):
        self.details_page = min(self.details_page + 1,
                                self._details_page_count() - 1)
        return {'status': self._details_position()}

    def prev_details(self):
        self.details_page = max(0, self.details_page - 1)
        return {'status': self._details_position()}

    def back_or_prev_details(self):
        if self.details_page > 0:
            self.prev_details()
            return {'status': 'prev'}
        return {'status': 'back'}

    def clear_details(self):
        self._stop_details_filename_scroll()
        self.host.getCanvas().delete('_dd2_details')
        self.host.getCanvas().delete('_dd2_details_hint')
        self.host.getCanvas().delete('_dd2_footer')

    def picker_toggle(self):
        if not self.files: return
        if self.cursor in self.selected: self.selected.remove(self.cursor)
        elif len(self.selected) < 2:
            if self.selected and self.category in ('MIFARE Classic', 'Ultralight / NTAG', 'iCLASS'):
                first = self.files[self.selected[0]]
                second = self.files[self.cursor]
                if self._dump_group(first, self.category) != self._dump_group(second, self.category):
                    try:
                        self.host.show_toast(_dd_translate('Incompatible dump types'), timeout=1800)
                    except (AttributeError, TypeError):
                        pass
                    self.draw_picker()
                    return
            self.selected.append(self.cursor)
        else:
            try:
                self.host.show_toast(_dd_translate('Maximum 2 dumps'), timeout=1500)
            except (AttributeError, TypeError):
                pass
        self.draw_picker()

    def picker_clear(self):
        self.host.getCanvas().delete('_dd2_picker')
        self.host.getCanvas().delete('_dd2_validation')
        self.host.getCanvas().delete('_dd2_footer')

    def picker_m2(self):
        """Worker: Classic goes directly to results after selection validation."""
        if len(self.selected) != 2:
            return {'status': 'need_two'}
        if self.category == 'MIFARE Classic':
            return self.confirm_compare_mode()
        self.compare_mode_top = 0
        return {'status': 'mode'}


    def _compare_mode_lines(self):
        if self.category == 'MIFARE Classic':
            return [('Anti-Clone:', 'Heuristic'), ('Sequential:', 'From report'),
                    ('', 'Results on next pages')]
        return [('Anti-Clone:', 'N/A'), ('Sequential:', 'N/A'),
                ('', 'Only MIFARE Classic')]

    def draw_compare_mode(self):
        """Compare INFO before Result, shared with Paxton."""
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_compare_mode'
        c.delete(tag)
        from tkinter import font as tkfont
        face = ('Courier New', 12)
        native_measure = tkfont.Font(family='Courier New', size=12).measure
        measure = lambda text: native_measure(_dd_translate(text))
        # 19px row pitch; leave a full blank row before the availability note.
        # Anchor 'nw' means y is the glyph TOP, not its centre.
        lines = self._compare_mode_lines()
        na_column = None
        if self.category != 'MIFARE Classic':
            pairs = [(_dd_translate(label).rstrip(' :') + ': ',
                      _dd_translate(value)) for label, value in lines if label]
            label_width = max((native_measure(label) for label, _ in pairs), default=0)
            value_width = max((native_measure(value) for _, value in pairs), default=0)
            na_column = (240 - label_width - value_width) / 2 + label_width
        for i, (label, value) in enumerate(lines):
            y = (70, 89, 127, 146)[i]
            if not label:
                c.create_text(120, y, text=value, anchor='center',
                              fill='#1647D6', font=face, tags=tag)
                continue
            display_label = _dd_translate(label)
            display_value = _dd_translate(value)
            from _dump_diff_2_lib.screen_catalog import draw_pair
            x = (na_column - native_measure(display_label.rstrip(' :') + ': ')
                 if na_column is not None else measure(' '))
            draw_pair(c,x,y,display_label,display_value,'#64748B' if value=='N/A' else '#1647D6',face,tag,measure)

    def clear_compare_mode(self):
        self.host.getCanvas().delete('_dd2_compare_mode')

    def confirm_compare_mode(self):
        # Compare directly: do not briefly display the obsolete Comparing...
        # intermediate state before the Result compare screen.
        self.sequential_enabled = False  # Pair alone is not an Auto-Scan sequence
        ready = self.begin_compare()
        if ready.get('status') == 'invalid':
            return {'status': 'error'}
        return self.do_compare()

    def _comparison_type_label(self):
        """Display-only identification. Never changes the comparison bytes."""
        category = self.category or 'Dump'
        if len(self.selected) != 2:
            return category
        paths = [self.files[i] for i in self.selected]
        prepared = self._comparison_data_for_display()
        types = prepared['types']
        return types[0] if types[0] == types[1] else category

    @staticmethod
    def _dump_subtype(path, category):
        """Recognize supported full-size dumps, then explicit file labels."""
        try:
            size = os.path.getsize(path)
        except OSError:
            return category
        name = os.path.basename(path).upper()
        if category == 'MIFARE Classic':
            # Use decoded memory, not the physical file size: a native
            # JSON dump and a verified BIN dump must report the same variant.
            try:
                size = len(load(path, category))
            except (OSError, ValueError, TypeError, KeyError):
                return category
            return {320: 'MIFARE Classic Mini',
                    1024: 'MIFARE Classic 1K',
                    2048: 'MIFARE Classic 2K',
                    4096: 'MIFARE Classic 4K'}.get(size, category)
        if category == 'iCLASS':
            # Filename prefixes produced by iCopy-X (including Iclass-Elite_).
            if re.search(r'(^|[^A-Z])ELITE([^A-Z]|$)', name):
                return 'iCLASS Elite'
            if re.search(r'(^|[^A-Z])LEGACY([^A-Z]|$)', name):
                return 'iCLASS Legacy'
            # Renamed dumps may still retain explicit subtype in companion JSON.
            meta = os.path.splitext(path)[0] + '.json'
            try:
                with open(meta, 'r') as stream:
                    info = json.load(stream)
                if isinstance(info, dict):
                    labels = []
                    for key in ('Type', 'type', 'CardType', 'card_type', 'TagType', 'tag_type'):
                        value = info.get(key)
                        if isinstance(value, str):
                            labels.append(value)
                    card = info.get('Card')
                    if isinstance(card, dict):
                        for key in ('Type', 'type', 'CardType', 'card_type'):
                            value = card.get(key)
                            if isinstance(value, str):
                                labels.append(value)
                    for value in labels:
                        if re.search(r'\bELITE\b', value, re.I):
                            return 'iCLASS Elite'
                        if re.search(r'\bLEGACY\b', value, re.I):
                            return 'iCLASS Legacy'
            except (OSError, ValueError, TypeError):
                pass
            return category
        if category == 'Ultralight / NTAG':
            # Proxmark3 mfu_dump_t: 56-byte header + 4 bytes per page.
            # A complete dump has a canonical page count. The header
            # records page count minus one at offset 11.
            try:
                with open(path, 'rb') as f:
                    header = f.read(56)
                if len(header) == 56 and size >= 64:
                    pages = header[11] + 1
                    if size == 56 + pages * 4:
                        canonical = {16: 'MIFARE Ultralight',
                                     20: 'Ultralight EV1',
                                     41: 'Ultralight EV1',
                                     45: 'NTAG213',
                                     48: 'Ultralight C',
                                     135: 'NTAG215',
                                     231: 'NTAG216'}
                        if pages in canonical:
                            return canonical[pages]
            except (OSError, ValueError, IndexError):
                pass
            # Explicit iCopy naming is useful for partial dumps,
            # but never guess from a partial file's byte length.
            prefixes = (('M0-UL-C_', 'Ultralight C'),
                        ('M0-UL-EV1_', 'Ultralight EV1'),
                        ('M0-UL_', 'MIFARE Ultralight'),
                        ('NTAG213_', 'NTAG213'),
                        ('NTAG215_', 'NTAG215'),
                        ('NTAG216_', 'NTAG216'))
            for prefix, label in prefixes:
                if name.startswith(prefix):
                    return label
        return category

    @classmethod
    def _dump_group(cls, path, category):
        """Conservative compatibility key for the existing picker.

        A label alone cannot prove chip identity. Unknown types are grouped by
        loaded memory length; known variants also require equal memory length.
        No changes to T5577 or Paxton comparison behavior.
        """
        if category not in ('MIFARE Classic', 'Ultralight / NTAG', 'iCLASS'):
            return category
        try:
            data = load(path, category)
            size = len(data)
        except (OSError, ValueError, TypeError, KeyError):
            return ('INVALID', os.path.basename(path))
        if category == 'MIFARE Classic':
            return (category, {320: 'Mini', 1024: '1K', 2048: '2K',
                               4096: '4K'}.get(size, 'UNKNOWN'), size)
        subtype = cls._dump_subtype(path, category)
        # Unknown model: same length alone is insufficient for an assured
        # match, but remains comparable as an explicitly unknown variant.
        return (category, subtype, size)

    def _identical_notice(self):
        # Known and experimental signatures show WARNING; heuristic only.
        ac = (self.result or {}).get('anticopy') or {}
        recognized = any(
            (ac.get(side) or {}).get('matches') or (ac.get(side) or {}).get('experimental')
            for side in ('a', 'b')
        )
        return ('WARNING - Press INFO', '#D00000') if recognized else ('Press INFO', '#1647D6')

    def draw_identical(self):
        """Centered comparison summary, blue success line, firmware-owned footer."""
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_identical'
        c.delete(tag)
        subtype = self._comparison_type_label()
        c.create_text(120, 72, text=subtype[:28],
                      anchor='center', fill='#1647D6',
                      font=('Courier New', 11 if len(subtype) > 18 else 13, 'bold'), tags=tag)
        c.create_text(120, 98, text='Dump A vs Dump B',
                      anchor='center', fill='#222222',
                      font=('Courier New', 13), tags=tag)
        c.create_text(120, 134, text='Dumps are identical',
                      anchor='center', fill='#1555C0',
                      font=('Courier New', 13, 'bold'), tags=tag)
        if self.category in ('MIFARE Classic','Paxton Net2','Paxton Switch2','T5577','iCLASS','Ultralight / NTAG'):
            notice, color = self._identical_notice()
            c.create_text(120, 177, text=notice,
                          anchor='center', fill=color,
                          font=('Courier New', 9, 'bold'), tags=tag)

    def draw_different(self):
        """Comparison summary before INFO; same navigation as identical dumps."""
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_different'
        c.delete(tag)
        subtype = self._comparison_type_label()
        c.create_text(120, 72, text=subtype[:28],
                      anchor='center', fill='#1647D6',
                      font=('Courier New', 11 if len(subtype) > 18 else 13, 'bold'), tags=tag)
        c.create_text(120, 98, text='Dump A vs Dump B',
                      anchor='center', fill='#222222',
                      font=('Courier New', 13), tags=tag)
        c.create_text(120, 134, text='Dumps are different',
                      anchor='center', fill='#B00020',
                      font=('Courier New', 9, 'bold'), tags=tag)
        if self.category in ('MIFARE Classic', 'Paxton Net2', 'Paxton Switch2','T5577','iCLASS','Ultralight / NTAG'):
            notice, color = (('WARNING - Press INFO', '#D00000') if self.category in ('Paxton Net2','Paxton Switch2','T5577') else self._identical_notice())
            c.create_text(120, 177, text=notice,
                          anchor='center', fill=color,
                          font=('Courier New', 9, 'bold'), tags=tag)

    def clear_different(self):
        self.host.getCanvas().delete('_dd2_different')

    def clear_identical(self):
        self.host.getCanvas().delete('_dd2_identical')

    def draw_need_two(self):
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_need_two'
        c.delete(tag)
        c.create_text(120, 116, text='Select 2 dumps',
                      anchor='center', fill='#B00020',
                      font=('Courier New', 14, 'bold'), tags=tag)
        c.create_text(120, 143, text='to compare',
                      anchor='center', fill='#B00020',
                      font=('Courier New', 14, 'bold'), tags=tag)

    def show_need_two_timed(self):
        """Show error and return automatically after 2000 ms on the UI thread."""
        self.draw_need_two()
        canvas = self.host.getCanvas()
        def return_to_picker():
            # Ignore stale callbacks if the user or firmware changed screens.
            if getattr(self.host, '_current_state_id', None) == 'need_two':
                self.clear_need_two()
                self.host._set_state('picker')
        canvas.after(2000, return_to_picker)

    def clear_need_two(self):
        self.host.getCanvas().delete('_dd2_need_two')

    def _checking_status(self):
        """Display the actual enabled/disabled state of sequential analysis."""
        return 'ready_simple' if self.category in ('Paxton Net2', 'Paxton Switch2', 'T5577', 'iCLASS') else ('ready_enabled' if self.sequential_enabled else 'ready_disabled')

    def begin_compare(self):
        if len(self.selected) != 2:
            self._dd_set_error('Select exactly two dumps')
            return {'status': 'invalid'}
        return {'status': self._checking_status()}

    def do_compare(self):
        if len(self.selected) != 2:
            self._dd_set_error('Select exactly two dumps')
            return {'status': 'error'}
        self._comparison_data = None
        self._comparison_page_cache = None
        a, b = [self.files[i] for i in self.selected]
        start = time.monotonic()
        try:
            if self.category in ('MIFARE Classic', 'Ultralight / NTAG', 'iCLASS') and \
                    self._dump_group(a, self.category) != self._dump_group(b, self.category):
                raise ValueError('Incompatible dump types')
            self.result = compare(a, b, self.category)
            # Paxton exception: B0/UID is display-only; compare B1..B7.
            # Other formats compare their complete decoded memory.
            self.result['same'] = load(a, self.category) == load(b, self.category)
            self.result['names'] = [os.path.basename(a), os.path.basename(b)]
            changes = self.result.get('changes', [])
            self.result['anticopy'] = None
            self.result['security'] = None
            if self.category == 'MIFARE Classic':
                for source in (a, b):
                    self._prepare_pm3(load(source, self.category))
            self.result['abc'] = self._abc_sections([load(a, self.category), load(b, self.category)])
            if self.category == 'MIFARE Classic':
                raw_a, raw_b = load(a, self.category), load(b, self.category)
                self.result['anticopy'] = analyze_anticopy(raw_a, raw_b, [self._pm3_result(raw_a), self._pm3_result(raw_b)])
                ac = self.result['anticopy']
                self.result['security'] = None  # B requires a validated 3/6/10-scan log
                sec = self.result['security'] or {}
            self.change_page = 0
            def short_name(value):
                return value if len(value) <= 28 else value[:25] + '...'
            self.host.set_var('dump_a', short_name(self.result['names'][0]))
            self.host.set_var('dump_b', short_name(self.result['names'][1]))
            self.host.set_var('diff_count', str(sum(x[4] for x in self._all_compare_blocks())))
            # Compare the complete set of memory blocks. Paxton B0 is
            # deliberately excluded from equality, but remains visible in INFO.
            blocks = self._all_compare_blocks()
            if self.category in ('Paxton Net2', 'Paxton Switch2'):
                memory = [entry for entry in blocks if entry[0] in range(1, 8)]
                if len(blocks) != 8 or len(memory) != 7:
                    raise ValueError('Incomplete Paxton comparison B1..B7')
                self.result['same'] = all(entry[2] == entry[3] for entry in memory)
            else:
                self.result['same'] = bool(blocks) and all(entry[2] == entry[3] for entry in blocks)
            self._prepare_comparison_data(blocks)
            return {'status': 'identical' if self.result['same'] else 'different'}
        except Exception as exc:
            # Preserve the existing error screen.
            try:
                self._dd_set_error(str(exc)[:100])
            except Exception:
                pass
            return {'status': 'error'}

    def _comparison_signature(self):
        return (self.category, tuple(self.files[i] for i in self.selected))

    def _comparison_data_for_display(self):
        prepared = getattr(self, '_comparison_data', None)
        if (prepared is None or prepared['result'] is not self.result or
                prepared['signature'] != self._comparison_signature()):
            raise ValueError('Comparison data not prepared')
        return prepared

    def _prepare_comparison_data(self, blocks=None):
        """Worker-only input snapshot. Tk pagination never opens dump/report files."""
        paths = [self.files[i] for i in self.selected]
        prepared = {'signature': self._comparison_signature(), 'result': self.result,
                    'blocks': self._all_compare_blocks() if blocks is None else blocks,
                    'types': [self._dump_subtype(path, self.category) for path in paths]}
        if self.category == 'MIFARE Classic':
            prepared['raw'] = [load(path, self.category) for path in paths]
            prepared['metadata'] = [dict(self._json_metadata(path)) for path in paths]
            prepared['evidence'] = [self._abc_log_evidence(raw) for raw in prepared['raw']]
        elif self.category in ('iCLASS', 'Ultralight / NTAG'):
            objects = []
            for path in paths:
                candidate = path if path.lower().endswith('.json') else os.path.splitext(path)[0] + '.json'
                if os.path.isfile(candidate):
                    with open(candidate, encoding='utf-8') as handle:
                        obj = json.load(handle)
                    objects.append(obj if isinstance(obj, dict) else {})
                else:
                    objects.append({})
            prepared['objects'] = objects
        self._comparison_data = prepared

    def _all_compare_blocks(self):
        """Full BIN contents; never infer UID or identity from filenames."""
        if len(self.selected) != 2:
            return []
        prepared = getattr(self, '_comparison_data', None)
        if (prepared is not None and prepared['result'] is self.result and
                prepared['signature'] == self._comparison_signature()):
            return prepared['blocks']
        # Paxton TXT: line 1 stores B1..B7; line 2 stores UID (B0).
        # Use the same authoritative decoder as Dump Details, not raw 28-byte
        # slices incorrectly numbered B0..B6. UID is shown but not counted.
        if self.category in ('Paxton Net2', 'Paxton Switch2'):
            from _dump_diff_2_lib.universal_screen import paxton_detail_blocks
            blocks_a = paxton_detail_blocks(self.files[self.selected[0]], self.category)
            blocks_b = paxton_detail_blocks(self.files[self.selected[1]], self.category)
            if len(blocks_a) != 8 or len(blocks_b) != 8:
                raise ValueError('Incomplete Paxton blocks B0..B7')
            labels = ('UID (B0)', 'Password B1', 'Key/Pwd B2', 'Config B3',
                      'User B4', 'User B5', 'User B6', 'User B7')
            return [(i, labels[i], blocks_a[i][2].hex().upper(),
                     blocks_b[i][2].hex().upper(),
                     i != 0 and blocks_a[i][2] != blocks_b[i][2])
                    for i in range(8)]
        raw_a = load(self.files[self.selected[0]], self.category)
        raw_b = load(self.files[self.selected[1]], self.category)
        width = {'iCLASS': 8, 'MIFARE Classic': 16,
                 'Ultralight / NTAG': 4, 'T5577': 4,
                 'Paxton Net2': 4, 'Paxton Switch2': 4}.get(self.category, 4)
        count = (max(len(raw_a), len(raw_b)) + width - 1) // width
        result = []
        for i in range(count):
            aa = raw_a[i*width:(i+1)*width]
            bb = raw_b[i*width:(i+1)*width]
            if self.category == 'iCLASS':
                labels = ('CSN', 'Config', 'e-Purse', 'Kd', 'Kc', 'AIA')
                label = labels[i] if i < len(labels) else 'Block {}'.format(i)
            elif self.category.startswith('Paxton '):
                labels = ('UID', 'Password', 'Key/Pwd', 'Config')
                label = labels[i] if i < 4 else 'User B{}'.format(i)
            elif self.category == 'Ultralight / NTAG':
                label = 'Page {}'.format(i)
            else:
                label = 'Block {}'.format(i)
            result.append((i, label, aa.hex().upper(), bb.hex().upper(), aa != bb))
        return result

    def _full_block_pages(self):
        """All memory blocks, one complete block per screen, no filtering."""
        blocks = self._all_compare_blocks()
        return [[block] for block in blocks] or [[]]



    def _show_full_block_compare(self, page_override=None, total_override=None, show_intro=True):
        """240x240 firmware Canvas: subtype and filenames only on page one.

        Each page shows one entire block (including identical ones). The
        header/footer bars are drawn by firmware, never duplicated here.
        """
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_changes'
        c.delete(tag)
        c.delete('_dd2_changes_hint')
        pages = self._full_block_pages()
        page = self.change_page if page_override is None else page_override
        page = max(0, min(page, len(pages) - 1))
        first = page == 0 and show_intro
        # The first screen has room for filename and count; later screens
        # intentionally repeat neither type, filenames nor status.
        if first:
            # Stage 1: approved Paxton Result Compare page 1. All other
            # categories and later pages remain untouched until approval.
            if self.category in ('Paxton Net2', 'Paxton Switch2'):
                self._draw_paxton_compare_page_one(c, tag, pages[page])
            else:
                self._draw_compare_page_v317(c, tag, pages[page], first=True)
        else:
            if self.category in ('Paxton Net2', 'Paxton Switch2'):
                self._draw_compare_page_v317(c, tag, pages[page], first=False)
            else:
                self._draw_compare_page_v317(c, tag, pages[page], first=False)
        self._footer_hint('Back', y=177, tag='_dd2_changes_hint')
        total = len(pages) if total_override is None else total_override
        display_page = page + 1 if total_override is None else self.change_page + 1
        c.create_text(120, 190, text='Page {}/{}'.format(display_page, total),
                      anchor='center', fill='#1647D6',
                      font=('Courier New', 10), tags=tag)
        if self.change_page > 0:
            c.create_text(9, 43, text='▲', anchor='nw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)
        if self.change_page + 1 < total:
            c.create_text(9, 198, text='▼', anchor='sw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)

    def _draw_compare_page_v317(self, c, tag, blocks, first):
        """Compare groups: label above A/B; 8 spaced bytes/row, 5px margins.

        Paxton B0/UID is display-only and never highlighted or counted.
        """
        if first:
            c.create_text(120, 43, text=self._comparison_type_label()[:24],
                          anchor='n', fill='#1647D6',
                          font=('Courier New', 10, 'bold'), tags=tag)
            names = (self.result or {}).get('names') or []
            if len(names) != 2 and len(self.selected) == 2:
                names = [os.path.basename(self.files[i]) for i in self.selected]
            for n, name in enumerate(names[:2]):
                c.create_text(120, 58 + 14*n,
                              text=('A: ' if n == 0 else 'B: ') + name[:21],
                              anchor='n', fill='#222222',
                              font=('Courier New', 9), tags=tag)
            count = sum(bool(item[4]) for item in self._all_compare_blocks())
            c.create_text(120, 87,
                          text='Different blocks: {}'.format(count) if count else 'Identical',
                          anchor='n', fill='#D00000' if count else '#1647D6',
                          font=('Courier New', 9), tags=tag)
        if not blocks:
            return
        index, label, av, bv, different = blocks[0]
        ignore_uid = self.category in ('Paxton Net2', 'Paxton Switch2') and index == 0
        if ignore_uid:
            label = 'UID (B0)'
        y = 102 if first else 62
        c.create_text(120, y, text=label.rstrip(':') + ':', anchor='n',
                      fill='#D00000' if different and not ignore_uid else '#555555',
                      font=('Courier New', 10), tags=tag)
        y += 17
        for prefix, value, other in (('A:', av, bv), ('B:', bv, av)):
            cells = [value[i:i+2] for i in range(0, len(value), 2)]
            refs = [other[i:i+2] for i in range(0, len(other), 2)]
            for start in range(0, max(1, len(cells)), 8):
                part = cells[start:start+8]
                if not part:
                    continue
                self._draw_compare_spaced_row(c, tag, y, prefix if start == 0 else '  ',
                                              part, refs[start:start+8], ignore_uid)
                y += 13

    @staticmethod
    def _draw_compare_spaced_row(c, tag, y, prefix, cells, refs, ignore_diff=False):
        """Pixel-measured 8-byte row, at least 5 px margins, no ellipses."""
        try:
            import tkinter.font as tkfont
            face = tkfont.Font(family='Courier New', size=10)
            measure = face.measure
        except (ImportError, RuntimeError, ValueError, AttributeError):
            measure = lambda value: len(value) * 6
        font = ('Courier New', 10)
        text = prefix + ' ' + ' '.join(cells)
        width = measure(text)
        # The normal eight-byte row fits a 240px screen at 10pt. 5px safe area.
        x = max(5, (240 - width) / 2)
        c.create_text(x, y, text=prefix + ' ', anchor='nw', fill='#555555',
                      font=font, tags=tag)
        pos = prefix + ' '
        for i, pair in enumerate(cells):
            ref = refs[i] if i < len(refs) else None
            c.create_text(x + measure(pos), y, text=pair, anchor='nw',
                          fill='#D00000' if not ignore_diff and pair != ref else '#1647D6',
                          font=font, tags=tag)
            pos += pair
            if i + 1 < len(cells):
                pos += ' '


    def _draw_paxton_compare_page_one(self, c, tag, blocks):
        """Paxton B0: both filenames and a byte-colored UID comparison."""
        c.create_text(120, 42, text=self._comparison_type_label(),
                      anchor='n', fill='#1647D6', font=('Courier New', 10, 'bold'), tags=tag)
        names = (self.result or {}).get('names') or []
        if len(names) != 2 and len(self.selected) == 2:
            names = [os.path.basename(self.files[i]) for i in self.selected]
        for i in range(2):
            name = str(names[i]) if i < len(names) else ''
            y = 58 + i * 28
            c.create_text(120, y, text=('A: ' if i == 0 else 'B: ') + name[:20],
                          anchor='n', fill='#222222', font=('Courier New', 9), tags=tag)
            if len(name) > 20:
                c.create_text(120, y + 13, text=name[20:], anchor='n',
                              fill='#222222', font=('Courier New', 8 if len(name) > 47 else 9), tags=tag)
        count = sum(bool(row[4]) for row in self._all_compare_blocks())
        c.create_text(120, 116,
                      text='Different blocks: {}'.format(count) if count else 'Identical',
                      anchor='n', fill='#D00000' if count else '#1647D6',
                      font=('Courier New', 10), tags=tag)
        if blocks:
            index, label, av, bv, different = blocks[0]
            c.create_text(120, 135, text='UID (B0)' if index == 0 else label,
                          anchor='n', fill='#222222', font=('Courier New', 10), tags=tag)
            self._draw_paxton_ab_line(c, tag, 153, av, av if index == 0 else bv, display_b=bv)

    def _draw_paxton_ab_line(self, c, tag, y, av, bv, display_b=None):
        """Center A/B values; color only different bytes red."""
        a, b = (av or '').upper(), (display_b if display_b is not None else bv or '').upper()
        compare_b = (bv or '').upper()
        line = 'A: {} B: {}'.format(a, b)
        try:
            import tkinter.font as tkfont
            cw = tkfont.Font(family='Courier New', size=10).measure('0')
        except (ImportError, RuntimeError, ValueError, AttributeError):
            cw = 6
        x = 120 - len(line) * cw / 2
        c.create_text(x, y, text='A: ', anchor='nw', fill='#1647D6',
                      font=('Courier New', 10), tags=tag)
        for start, val, other in ((3, a, compare_b), (3 + len(a) + 4, b, a)):
            for pos in range(0, len(val), 2):
                pair = val[pos:pos+2]
                c.create_text(x + (start + pos) * cw, y, text=pair, anchor='nw',
                              fill='#D00000' if pair != other[pos:pos+2] else '#1647D6',
                              font=('Courier New', 10), tags=tag)
        c.create_text(x + (3 + len(a)) * cw, y, text=' B: ', anchor='nw',
                      fill='#1647D6', font=('Courier New', 10), tags=tag)


    def _draw_compare_hex(self, canvas, tag, y, prefix, value, other, xcenter=120):
        """Byte-wise color, stable monospaced positions, centered group."""
        length = max(len(value), len(other))
        n = (length + 1) // 2
        cells = [value[i*2:i*2+2] or '--' for i in range(n)]
        reference = [other[i*2:i*2+2] or '--' for i in range(n)]
        try:
            import tkinter.font as tkfont
            cw = tkfont.Font(family='Courier New', size=10).measure('0')
        except (ImportError, RuntimeError, ValueError, AttributeError):
            cw = 6
        # For a 4-byte page, 12 characters per half fit on the 240px LCD.
        left = xcenter - (len(prefix) + 1 + len(cells)*2)*cw/2
        canvas.create_text(left, y, text=prefix + ' ', anchor='nw',
                           fill='#222222', font=('Courier New', 10), tags=tag)
        for i, pair in enumerate(cells):
            canvas.create_text(left + (len(prefix) + 1 + i*2)*cw, y,
                               text=pair,
                               fill='#D00000' if pair != reference[i] else '#1647D6',
                               anchor='nw', font=('Courier New', 10), tags=tag)

    def _abc_compare_pages(self):
        sections = (self.result or {}).get('abc') or {}
        if self.category == 'MIFARE Classic':
            lines = list(sections.get('A') or [])
            # 22 characters per line; heading only on the first page.
            groups = []
            for line in lines:
                line = str(line)
                if line == 'Anti-Clone Analysis':
                    groups.append([line])
                    continue
                if len(line) <= 22:
                    groups.append([line])
                elif ':' in line:
                    label, value = line.split(':', 1)
                    if len(label) < 22:
                        groups.append([label + ':'] + self._dd2_wrap_22(value.strip()))
                    else:
                        groups.append(self._dd2_wrap_22(line))
                else:
                    groups.append(self._dd2_wrap_22(line))
            pages, page = [], []
            for group in groups:
                for row in group:
                    if len(page) >= 6:
                        pages.append(page)
                        page = []
                    page.append(row)
            if page:
                pages.append(page)
            blocks = self._all_compare_blocks()
            summary = [self._comparison_type_label(), 'Tag Info + Blocks',
                       'Blocks: {}'.format(len(blocks)),
                       'Different: {}'.format(sum(bool(x[4]) for x in blocks))]
            pages.append(summary)
            return pages
        pages = []
        for key in ('A', 'B'):
            rows = sections.get(key) or []
            for i in range(0, len(rows), 7):
                pages.append(rows[i:i+7])
        return pages

    @staticmethod
    def _dd2_wrap_22(value):
        words = str(value).split()
        out, line = [], ''
        for word in words:
            if len(word) > 22:
                if line:
                    out.append(line)
                    line = ''
                out.extend(word[i:i+22] for i in range(0, len(word), 22))
            elif len(line) + len(word) + (1 if line else 0) > 22:
                out.append(line)
                line = word
            else:
                line += (' ' if line else '') + word
        if line:
            out.append(line)
        return out or ['']

    def _abc_draw_compare_intro(self, rows, total):
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_changes'
        c.delete(tag)
        c.delete('_dd2_changes_hint')
        if self.category == 'MIFARE Classic':
            face = ('Courier New', 12)
            start_y = 47 + (38 if len(rows) in (2,3) and 'Anti-Clone Analysis' not in rows else 0)
            for i, line in enumerate(rows):
                heading = line in ('Anti-Clone Analysis', 'Tag Info + Blocks')
                from _dump_diff_2_lib.universal_screen import anti_clone_color
                finding = line.startswith(('Dump A:', 'Dump B:', 'A Match:', 'B Match:',
                                           'A Exp:', 'B Exp:', 'A Diag:', 'B Diag:'))
                line_color = '#1647D6' if heading else anti_clone_color(line) if finding else '#64748B'
                c.create_text(120, start_y + i*19, text=line,
                              anchor='n', fill=line_color,
                              font=face, tags=tag)
        else:
            for i, line in enumerate(rows):
                color = ('#1647D6' if line in ('Anti-Clone Analysis', 'Sequential Analysis', 'Tag Info + Blocks')
                         else '#C62828' if line.startswith(('Possible ', 'A: Possible', 'B: Possible'))
                         else '#222222')
                c.create_text(120 if color == '#1647D6' else 17, 53+i*17,
                              text=line[:28], anchor='n' if color == '#1647D6' else 'nw',
                              fill=color, font=('Courier New', 9), tags=tag)
        self._footer_hint('Back', y=177, tag='_dd2_changes_hint')
        c.create_text(120, 190, text='Page {}/{}'.format(self.change_page+1, total),
                      anchor='center', fill='#1647D6', font=('Courier New', 9), tags=tag)
        if self.change_page:
            c.create_text(9, 43, text='▲', anchor='nw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)
        if self.change_page + 1 < total:
            c.create_text(9, 198, text='▼', anchor='sw', fill='#1647D6',
                          font=('Arial', 9), tags=tag)

    def _paxton_compare_pages(self):
        return self._cached_comparison_pages('_paxton_compare_pages')

    def _build_paxton_compare_pages(self):
        """Paxton comparison: summary + Details-style B1..B7 (UID excluded)."""
        blocks = self._all_compare_blocks()
        if len(blocks) != 8 or [x[0] for x in blocks] != list(range(8)):
            raise ValueError('Paxton Compare requires B0..B7')
        memory = blocks[1:]
        changed = sum(bool(x[4]) for x in memory)
        if not changed:
            # Exactly the same B1-B3 / B4-B7 split as Paxton Details.
            return [('summary', None), ('identical', memory[:3]),
                    ('identical', memory[3:])]
        # 3 physical lines per block (centered label + two A/B rows).
        # Maximum six lines per page; never split a block.
        return [('summary', None)] + [('different', memory[i:i+2])
                                     for i in range(0, len(memory), 2)]

    def _paxton_compare_draw(self):
        """Native Canvas, 12pt/19px, Details coordinates and fixed footer."""
        from tkinter import font as tkfont
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_changes'
        c.delete(tag)
        c.delete('_dd2_changes_hint')
        pages = self._paxton_compare_pages()
        self.change_page = max(0, min(self.change_page, len(pages)-1))
        mode, rows = pages[self.change_page]
        face = ('Courier New', 12)
        native_measure = tkfont.Font(family='Courier New', size=12).measure
        measure = lambda text: native_measure(_dd_translate(text))
        gray, blue, red = '#64748B', '#1647D6', '#D62636'

        def centered_pair(y, label, value, value_color):
            left = label + ' '
            full_width = measure(left + value)
            x = (240 - full_width)/2
            c.create_text(x, y, text=left, anchor='nw', fill=gray,
                          font=face, tags=tag)
            c.create_text(x+measure(left), y, text=value, anchor='nw',
                          fill=value_color, font=face, tags=tag)

        if mode == 'summary':
            changed = sum(bool(x[4]) for x in self._all_compare_blocks()[1:])
            c.create_text(120, 43, text=self.category, anchor='n',
                          fill=blue, font=face, tags=tag)
            # IDENTICAL: two empty lines after type; DIFFERENT: one.
            y = 100 if not changed else 81
            centered_pair(y, 'Compare:', 'DIFFERENT' if changed else 'IDENTICAL',
                          red if changed else blue)
            centered_pair(y+19, 'UID:', 'Difference ignored', blue)
            if changed:
                centered_pair(y+38, 'Changed blocks:', str(changed), red)
        elif mode == 'identical':
            # Exactly Details pair rows: x=9, label gray, spaced HEX blue.
            y = 85 if len(rows) <= 3 else 64
            for index, label, av, bv, different in rows:
                prefix = label.split(' B')[0] if index in (1,2,3) else label
                prefix = prefix.rstrip(':') + ': '
                value = ' '.join(av[i:i+2] for i in range(0, len(av), 2))
                if measure(prefix + value) > 222:
                    raise ValueError('Paxton Details row too wide')
                c.create_text(9, y, text=prefix, anchor='nw', fill=gray,
                              font=face, tags=tag)
                c.create_text(9+measure(prefix), y, text=value, anchor='nw',
                              fill=blue, font=face, tags=tag)
                y += 19
        else:
            # Center only the field name. A/B rows start at the Details x=9.
            shared = {index for index, _, av, bv, _ in rows
                      if self.category == 'Paxton Switch2' and index in (1, 2) and av == bv}
            line_count = sum(2 if row[0] in shared else 3 for row in rows)
            y = 85 if line_count <= 3 else 62 if line_count == 4 else 43
            for index, label, av, bv, different in rows:
                field = label.split(' B')[0] if index in (1,2,3) else label
                c.create_text(120, y, text=field.rstrip(':')+':', anchor='n',
                              fill=gray, font=face, tags=tag)
                y += 19
                values = (('A/B:', av),) if index in shared else (('Dump A:', av), ('Dump B:', bv))
                for side, value in values:
                    prefix = ' ' + side + ' '
                    pairs = [value[i:i+2] for i in range(0,len(value),2)]
                    refs = [av[i:i+2] for i in range(0,len(av),2)]
                    text_width = measure(prefix + ' '.join(pairs))
                    if text_width > 235:
                        raise ValueError('Paxton Compare A/B row too wide')
                    # One leading space, exactly as approved for Compare.
                    x = 5
                    c.create_text(x,y,text=prefix,anchor='nw',fill=gray,
                                  font=face,tags=tag)
                    x += measure(prefix)
                    for j, pair in enumerate(pairs):
                        c.create_text(x,y,text=pair,anchor='nw',
                                      fill=red if side=='Dump B:' and pair!=refs[j] else blue,
                                      font=face,tags=tag)
                        x += measure(pair)
                        if j < len(pairs)-1:
                            x += measure(' ')
                    y += 19
        self._footer_hint('Back', y=177, tag='_dd2_changes_hint')
        c.create_text(120,190,text='Page {}/{}'.format(self.change_page+1,len(pages)),
                      anchor='center',fill=blue,font=('Courier New',10),tags=tag)
        if self.change_page:
            c.create_text(235,43,text='▲',anchor='ne',fill=blue,
                          font=('Arial',9),tags=tag)
        if self.change_page+1<len(pages):
            c.create_text(235,198,text='▼',anchor='se',fill=blue,
                          font=('Arial',9),tags=tag)

    def _t5577_compare_pages(self):
        return self._cached_comparison_pages('_t5577_compare_pages')

    def _build_t5577_compare_pages(self):
        """Native 48-byte T5577: P0 B0..B7 and P1 B0..B3, no UID."""
        blocks = self._all_compare_blocks()
        if len(blocks) != 12 or [b[0] for b in blocks] != list(range(12)) or any(len(b[2]) != 8 or len(b[3]) != 8 for b in blocks):
            raise ValueError('T5577 Compare requires 12 complete 4-byte blocks')
        # Show EVERY block as Dump A / Dump B, whether identical or different.
        # Keep the existing summary and byte-level difference highlighting.
        return [('summary', None)] + [('mixed', blocks[i:i+2]) for i in range(0,12,2)]

    def _t5577_compare_draw(self):
        """T5577 Compare: Courier New 12, 19px pitch, original footer."""
        from tkinter import font as tkfont
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_changes'
        c.delete(tag)
        c.delete('_dd2_changes_hint')
        pages = self._t5577_compare_pages()
        self.change_page = max(0, min(self.change_page, len(pages)-1))
        mode, rows = pages[self.change_page]
        face = ('Courier New', 12)
        native_measure = tkfont.Font(family='Courier New', size=12).measure
        measure = lambda text: native_measure(_dd_translate(text))
        gray, blue, red = '#64748B', '#1647D6', '#D62636'

        def pair(y,label,value,color):
            from _dump_diff_2_lib.screen_catalog import draw_pair
            draw_pair(c,measure(' '),y,label,value,color,face,tag,measure)

        def block_name(index):
            return ('Config ' if index == 0 else '') + 'P{} B{}:'.format(0 if index < 8 else 1, index if index < 8 else index-8)

        if mode == 'summary':
            changed = sum(bool(x[4]) for x in self._all_compare_blocks())
            c.create_text(120, 43, text='T5577', anchor='n', fill=blue, font=face, tags=tag)
            y = 100 if not changed else 81
            pair(y, 'Compare:', 'DIFFERENT' if changed else 'IDENTICAL', red if changed else blue)
            if changed:
                pair(y+19, 'Changed blocks:', str(changed), red)
        elif mode == 'identical':
            # Details-style left aligned label, space, four HEX bytes.
            y = 43
            for index, _, av, _, _ in rows:
                prefix = ' ' + block_name(index) + ' '
                value = ' '.join(av[i:i+2] for i in range(0,8,2))
                if measure(prefix+value) > 230:
                    raise ValueError('T5577 identical line exceeds display width')
                c.create_text(5,y,text=prefix,anchor='nw',fill=gray,font=face,tags=tag)
                c.create_text(5+measure(prefix),y,text=value,anchor='nw',fill=blue,font=face,tags=tag)
                y += 19
        else:
            y = 43 if len(rows) == 2 else 85
            for index, _, av, bv, _ in rows:
                c.create_text(120,y,text=block_name(index),anchor='n',fill=gray,font=face,tags=tag)
                y += 19
                reference = [av[i:i+2] for i in range(0,8,2)]
                for side, value in ((('A/B:',av),) if av == bv else (('Dump A:',av),('Dump B:',bv))):
                    prefix = ' ' + side + ' '
                    pairs = [value[i:i+2] for i in range(0,8,2)]
                    if measure(prefix+' '.join(pairs)) > 230:
                        raise ValueError('T5577 A/B line exceeds display width')
                    x = 5
                    c.create_text(x,y,text=prefix,anchor='nw',fill=gray,font=face,tags=tag)
                    x += measure(prefix)
                    for j, byte in enumerate(pairs):
                        c.create_text(x,y,text=byte,anchor='nw',fill=red if side=='Dump B:' and byte != reference[j] else blue,font=face,tags=tag)
                        x += measure(byte)
                        if j < 3: x += measure(' ')
                    y += 19
        self._footer_hint('Back', y=177, tag='_dd2_changes_hint')
        c.create_text(120,190,text='Page {}/{}'.format(self.change_page+1,len(pages)),anchor='center',fill=blue,font=('Courier New',10),tags=tag)
        if self.change_page:
            c.create_text(235,43,text='▲',anchor='ne',fill=blue,font=('Arial',9),tags=tag)
        if self.change_page+1<len(pages):
            c.create_text(235,198,text='▼',anchor='se',fill=blue,font=('Arial',9),tags=tag)

    def _iclass_result_pages(self):
        return self._cached_comparison_pages('_iclass_result_pages')

    def _build_iclass_result_pages(self):
        """iCLASS-only Compare: summary followed by JSON Details-style fields.

        Eight-byte values have a centered label with colon above centered HEX.
        Identical values appear once (A/B); differences show A and B with
        changed B bytes red. A field is never split between pages.
        """
        import json
        import os
        import re
        blocks = self._all_compare_blocks()
        changed = sum(bool(row[4]) for row in blocks)
        if not blocks:
            raise ValueError('No iCLASS blocks to compare')
        paths = [self.files[i] for i in self.selected]
        card_a, card_b = [obj.get('Card', {}) if isinstance(obj.get('Card', {}), dict) else {}
                          for obj in self._comparison_data_for_display()['objects']]
        fields = []
        # Card fields preserve their JSON order. Blocks follow in numeric order,
        # as on the iCLASS Details pages. Never infer values from filenames.
        for key in dict.fromkeys(list(card_a) + list(card_b)):
            if key.lower() in ('created', 'filetype', 'type'):
                continue
            va = str(card_a.get(key, '')).replace(' ', '').upper()
            vb = str(card_b.get(key, '')).replace(' ', '').upper()
            if va and vb and re.fullmatch('[0-9A-F]+', va) and re.fullmatch('[0-9A-F]+', vb) and len(va) % 2 == 0 and len(vb) % 2 == 0:
                fields.append(('Signature 32B' if key == 'Signature' else key, va, vb))
        for index, label, va, vb, _ in blocks:
            fields.append(('Block {}'.format(index), va, vb))
        pages = [('summary', changed)]
        pending = []
        for label, va, vb in fields:
            equal = va == vb
            # 8 bytes per HEX line; labels are separate centered rows.
            arows = [' '.join(va[j:j+2] for j in range(i, min(i+16,len(va)), 2)) for i in range(0,len(va),16)] or ['']
            brows = [' '.join(vb[j:j+2] for j in range(i, min(i+16,len(vb)), 2)) for i in range(0,len(vb),16)] or ['']
            lines = 1 + len(arows) if equal else 2 + len(arows) + len(brows)
            if lines > 6:
                raise ValueError('iCLASS Compare field too long: {}'.format(label))
            field = (label, va, vb, equal, lines)
            if pending and sum(f[4] for f in pending) + lines > 6:
                pages.append(('fields', pending)); pending=[]
            pending.append(field)
        if pending:
            pages.append(('fields', pending))
        return pages

    def _iclass_result_draw(self):
        """Draw only iCLASS Compare; never touch Details or other categories."""
        from tkinter import font as tkfont
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_changes'
        c.delete(tag)
        c.delete('_dd2_changes_hint')
        pages = self._iclass_result_pages()
        self.change_page = max(0, min(self.change_page, len(pages)-1))
        mode, payload = pages[self.change_page]
        face = ('Courier New', 12)
        native_measure = tkfont.Font(family='Courier New', size=12).measure
        measure = lambda text: native_measure(_dd_translate(text))
        gray, blue, red = '#64748B', '#1647D6', '#D62636'
        def pair(y,label,value,color):
            from _dump_diff_2_lib.screen_catalog import draw_pair
            draw_pair(c,measure(' '),y,label,value,color,face,tag,measure)
        def hex_row(y, value, reference=None):
            parts = [value[i:i+2] for i in range(0,len(value),2)]
            refs = [reference[i:i+2] for i in range(0,len(reference),2)] if reference is not None else []
            # Center each complete eight-byte line as in Details.
            for offset in range(0,len(parts),8):
                chunk=parts[offset:offset+8]
                row=' '.join(chunk)
                x=(240-measure(row))/2
                for j,byte in enumerate(chunk):
                    pos=offset+j
                    c.create_text(x,y,text=byte,anchor='nw',font=face,
                                  fill=red if reference is not None and (pos>=len(refs) or byte!=refs[pos]) else blue,tags=tag)
                    x += measure(byte)
                    if j+1<len(chunk): x += measure(' ')
                y += 19
            return y
        if mode == 'summary':
            c.create_text(120,43,text=self._comparison_data_for_display()['types'][0],
                          anchor='n',fill=blue,font=face,tags=tag)
            # FileType comes from the original iCLASS JSON, not the filename.
            type_value = next((obj['FileType'].strip()
                               for obj in self._comparison_data_for_display()['objects']
                               if isinstance(obj.get('FileType'), str) and obj['FileType'].strip()), None)
            y = 100 if payload == 0 else 81
            pair(y,'Compare:','IDENTICAL' if payload == 0 else 'DIFFERENT',blue if payload == 0 else red)
            if payload:
                pair(y+19,'Changed blocks:',str(payload),red)
            if type_value is not None:
                pair(y+38 if payload else y+19, 'Type:', type_value, blue)
        else:
            count=sum(field[4] for field in payload)
            y=81 if count<=3 else 62 if count==4 else 43
            for label,va,vb,equal,_ in payload:
                c.create_text(120,y,text=label+(' A/B:' if equal else ' A:'),
                              anchor='n',fill=gray,font=face,tags=tag)
                y=hex_row(y+19,va)
                if not equal:
                    c.create_text(120,y,text=label+' B:',anchor='n',fill=gray,font=face,tags=tag)
                    y=hex_row(y+19,vb,va)
        self._footer_hint('Back',y=177,tag='_dd2_changes_hint')
        c.create_text(120,190,text='Page {}/{}'.format(self.change_page+1,len(pages)),
                      anchor='center',fill=blue,font=('Courier New',10),tags=tag)
        if self.change_page:
            c.create_text(235,43,text='▲',anchor='ne',fill=blue,font=('Arial',9),tags=tag)
        if self.change_page+1<len(pages):
            c.create_text(235,198,text='▼',anchor='se',fill=blue,font=('Arial',9),tags=tag)

    def _ultralight_compare_pages(self):
        return self._cached_comparison_pages('_ultralight_compare_pages')

    def _ultralight_layout_rows(self, fields):
        """Expand atomic fields once for both measured pagination and drawing."""
        rows=[]
        for label,va,vb,equal,short,height in fields:
            for side,value,reference in ([('A/B',va,None)] if equal else [('A',va,None),('B',vb,va)]):
                name=label+' '+side+':'
                if short:
                    rows.append(('pair',name,value,reference))
                else:
                    rows.append(('label',name,'',None))
                    for start in range(0,len(value),16):
                        rows.append(('hex','',value[start:start+16],reference[start:start+16] if reference is not None else None))
        return rows

    def _ultralight_row_positions(self, rows):
        from _dump_diff_2_lib.screen_catalog import row_positions
        geometry=[]
        for kind,label,value,reference in rows:
            spaced=' '.join(value[i:i+2] for i in range(0,len(value),2))
            geometry.append(('pair',_dd_translate(label),spaced) if kind=='pair' else
                            ('label',_dd_translate(label) if kind=='label' else spaced,''))
        return row_positions(geometry,True)

    def _build_ultralight_compare_pages(self):
        """Ultralight Compare: JSON Card metadata, then complete 4-byte pages.

        One field stays on one screen; identical data is marked A/B, while
        changed bytes are marked red in B. Do not affect Details or iCLASS.
        """
        import json
        import re
        from tkinter import font as tkfont
        content_font=tkfont.Font(family='Courier New',size=12)
        paths = [self.files[i] for i in self.selected]
        (a, ta), (b, tb) = [(obj.get('Card', {}) or {}, obj.get('FileType'))
                            for obj in self._comparison_data_for_display()['objects']]
        fields = []
        for key in dict.fromkeys(list(a) + list(b)):
            va, vb = str(a.get(key, '')).replace(' ', '').upper(), str(b.get(key, '')).replace(' ', '').upper()
            if va and vb and re.fullmatch('[0-9A-F]+', va) and re.fullmatch('[0-9A-F]+', vb) and len(va)%2==0 and len(vb)%2==0:
                fields.append(('Signature 32B' if key == 'Signature' else key, va, vb))
        blocks = self._all_compare_blocks()
        for index, _, va, vb, _ in blocks:
            fields.append(('Block {}'.format(index), va, vb))
        pages = [('summary', (sum(bool(x[4]) for x in blocks), ta or tb))]
        pending, used = [], 0
        for label, va, vb in fields:
            equal = va == vb
            # 4-byte values fit beside short labels; larger values are centered
            # beneath a centered label, in groups of at most eight bytes.
            # Measure the complete rendered row, including leading space, label,
            # A/B or A/B-specific suffix, colon, spaces between HEX bytes.
            # Each side must independently fit when values differ.
            def fits_row(suffix, value):
                data = ' '.join(value[i:i+2] for i in range(0, len(value), 2))
                return content_font.measure(_dd_translate(label+suffix)+' '+data) <= 222
            short = (fits_row(' A/B:', va) if equal else
                     fits_row(' A:', va) and fits_row(' B:', vb))
            rows_a = (len(va)+15)//16
            rows_b = (len(vb)+15)//16
            height = (1 if short else 1+rows_a) if equal else (2 if short else 2+rows_a+rows_b)
            if height > 6:
                if pending:
                    pages.append(('fields',pending));pending=[];used=0
                for side, value, reference in (('A',va,None),('B',vb,va)):
                    pages.append(('signature', (label+' '+side+':', value, reference)))
                continue
            entry=(label,va,vb,equal,short,height)
            trial=self._ultralight_layout_rows(pending+[entry])
            if pending and (len(trial)>6 or self._ultralight_row_positions(trial)[-1]+content_font.metrics('linespace')>171):
                pages.append(('fields',pending));pending=[];used=0
            pending.append(entry);used+=height
        if pending: pages.append(('fields',pending))
        # Keep a short final field from becoming an otherwise empty page,
        # including the page immediately before an atomic signature.
        for index in range(2,len(pages)):
            mode,current=pages[index]
            previous_mode,previous=pages[index-1]
            if (mode=='fields' and previous_mode=='fields' and len(current)==1
                    and current[0][5]<=2 and len(previous)>1
                    and sum(field[5] for field in previous[:-1])>=2):
                trial=self._ultralight_layout_rows([previous[-1]]+current)
                if len(trial)<=6 and self._ultralight_row_positions(trial)[-1]+content_font.metrics('linespace')<=171:
                    current.insert(0,previous.pop())
        return pages

    def _ultralight_compare_draw(self):
        """Use firmware-owned bars, native Canvas and iCLASS footer positions."""
        from tkinter import font as tkfont
        c = _LocalizedCanvas(self.host.getCanvas())
        tag = '_dd2_changes'
        c.delete(tag)
        c.delete('_dd2_changes_hint')
        pages = self._ultralight_compare_pages()
        self.change_page = max(0,min(self.change_page,len(pages)-1))
        mode, payload = pages[self.change_page]
        face = ('Courier New',12)
        measure = tkfont.Font(family='Courier New',size=12).measure
        gray, blue, red = '#64748B','#1647D6','#D62636'
        def pair(y,label,value,color):
            from _dump_diff_2_lib.screen_catalog import draw_pair
            draw_pair(c,measure(' '),y,label,value,color,face,tag,measure)
        def hex_rows(y,value,reference=None):
            bytes_=[value[i:i+2] for i in range(0,len(value),2)]
            refs=[reference[i:i+2] for i in range(0,len(reference),2)] if reference is not None else []
            for offset in range(0,len(bytes_),8):
                part=bytes_[offset:offset+8]
                x=(240-measure(' '.join(part)))/2
                for j,byte in enumerate(part):
                    index=offset+j
                    color=red if reference is not None and (index>=len(refs) or byte!=refs[index]) else blue
                    c.create_text(x,y,text=byte,anchor='nw',fill=color,font=face,tags=tag)
                    x+=measure(byte)+measure(' ')
                y+=19
            return y
        def short_row(y,label,value,reference=None):
            label=_dd_translate(label)
            prefix=label+' '
            data=' '.join(value[i:i+2] for i in range(0,len(value),2))
            if measure(prefix+data)>230:
                raise ValueError('Ultralight Compare line exceeds 230px: '+label)
            from _dump_diff_2_lib.screen_catalog import draw_pair
            draw_pair(c,measure(' '),y,label,'',blue,face,tag,measure)
            x=measure(' ')+measure(prefix)
            refs=[reference[i:i+2] for i in range(0,len(reference),2)] if reference is not None else []
            for j in range(0,len(value),2):
                byte=value[j:j+2]
                color=red if reference is not None and (j//2>=len(refs) or byte!=refs[j//2]) else blue
                c.create_text(x,y,text=byte,anchor='nw',fill=color,font=face,tags=tag)
                x+=measure(byte)+measure(' ')
        if mode=='summary':
            changed,filetype=payload
            c.create_text(120,43,text=self._comparison_type_label(),anchor='n',fill=blue,font=face,tags=tag)
            y=81 if changed else 100
            pair(y,'Compare:','DIFFERENT' if changed else 'IDENTICAL',red if changed else blue)
            if changed: pair(y+19,'Changed blocks:',str(changed),red)
            if filetype: pair(y+38 if changed else y+19,'Type:',str(filetype),blue)
        elif mode=='signature':
            label,value,reference=payload
            rows=[('label',label,'',None)]+[('hex','',value[i:i+16],reference[i:i+16] if reference is not None else None) for i in range(0,len(value),16)]
            for row,y in zip(rows,self._ultralight_row_positions(rows)):
                if row[0]=='label':c.create_text(120,y,text=row[1],anchor='n',fill=gray,font=face,tags=tag)
                else:hex_rows(y,row[2],row[3])
        else:
            rows=self._ultralight_layout_rows(payload)
            for (kind,label,value,reference),y in zip(rows,self._ultralight_row_positions(rows)):
                if kind=='pair':short_row(y,label,value,reference)
                elif kind=='label':c.create_text(120,y,text=label,anchor='n',fill=gray,font=face,tags=tag)
                else:hex_rows(y,value,reference)
        self._footer_hint('Back',y=177,tag='_dd2_changes_hint')
        c.create_text(120,190,text='Page {}/{}'.format(self.change_page+1,len(pages)),anchor='center',fill=blue,font=('Courier New',10),tags=tag)
        if self.change_page:
            c.create_text(235,43,text='▲',anchor='ne',fill=blue,font=('Arial',9),tags=tag)
        if self.change_page+1<len(pages):
            c.create_text(235,198,text='▼',anchor='se',fill=blue,font=('Arial',9),tags=tag)

    def _cached_comparison_pages(self, name):
        """A comparison is a fixed result until its inputs/result change."""
        signature=(name,self.category,tuple(self.files[i] for i in self.selected),
                   _dd_language(),self.host.getCanvas().tk.call('tk','scaling'))
        cached=getattr(self,'_comparison_page_cache',None)
        if cached is not None and cached[0] is self.result and cached[1]==signature:
            return cached[2]
        pages=getattr(self,'_build'+name)()
        self._comparison_page_cache=(self.result,signature,pages)
        return pages

    def _mfc_compare_pages(self):
        return self._cached_comparison_pages('_mfc_compare_pages')

    def _build_mfc_compare_pages(self):
        """MIFARE Classic compare: report findings, then JSON, then memory."""
        import re
        paths = [self.files[i] for i in self.selected]
        prepared = self._comparison_data_for_display()
        raw = prepared['raw']
        metadata = prepared['metadata']
        anti = (self.result or {}).get('anticopy') or {}
        scans = [anti.get('a') or {}, anti.get('b') or {}]
        blocks = self._all_compare_blocks()
        changed = sum(bool(x[4]) for x in blocks)
        from _dump_diff_2_lib.screen_catalog import field_pages, pm3_display_fields, text_rows
        from tkinter import font as tkfont
        measure = tkfont.Font(family='Courier New',size=12).measure
        variants=[{320:'Mini',1024:'1K',2048:'2K',4096:'4K'}.get(len(d),'?') for d in raw]
        card=[]
        for label,values in [('Type:',['mfc-'+v.lower() for v in variants]),
                             ('Size:',[str(len(d))+' bytes' for d in raw]),
                             ('Blocks:',[str(len(d)//16) for d in raw])]:
            if values[0]==values[1]:card.append((label,values[0]))
            else:
                for side,value in zip(('A','B'),values):card.append((label.rstrip(':')+' '+side+':',value))
        card.append(('Dumps:','2'))
        pages=[('notice',None)]
        title='MIFARE Classic '+(variants[0] if variants[0]==variants[1] else variants[0]+'/'+variants[1])
        pages.extend(('fields',rows) for rows in field_pages([(title,card)],_dd_translate))
        sections=[]
        groups = []
        def wrap_words(value):
            return text_rows(value, measure, 222) or ['N/A']
        def field(label, value, side=None, reference=None):
            value='N/A' if value is None or value=='' else _dd_translate(str(value))
            label=_dd_translate(str(label))
            prefix=str(label).replace('_',' ')+(' '+side if side else '')+':'
            h=re.sub(r'\s+','',value)
            ishex=bool(re.fullmatch(r'[0-9A-Fa-f]+',h)) and len(h)%2==0
            display=' '.join(h[i:i+2] for i in range(0,len(h),2)).upper() if ishex else value
            if measure(prefix+' '+display)<=222:
                return [('pair',(prefix,display,h.upper() if ishex else None,reference,
                                 '#D62636' if reference is not None and not ishex else None))]
            result=[('label',prefix)]
            if ishex:
                for i in range(0,len(h),16):
                    result.append(('hex',(h[i:i+16].upper(),reference,i)))
            else:
                result.extend(('changed_value' if reference is not None else 'value',part)
                              for part in wrap_words(display))
            return result
        def add(label,va,vb):
            va='N/A' if va is None or va=='' else str(va)
            vb='N/A' if vb is None or vb=='' else str(vb)
            rows=(field(label,va,'A/B') if va==vb else
                  field(label,va,'A')+field(label,vb,'B',va))
            groups.append(rows)
        def single(label,value,severity=None):
            color='#E58A19' if severity=='orange' else severity or '#1647D6'
            sections[-1][1].append((label+':',str(value),color))
        # Three analysis sections. A/B notation is reserved for JSON and blocks.
        # Reuse the same validated UID/report.log reader as MFC Details.
        from _dump_diff_2_lib.dump_security import analyze_mfc_structure
        sections.append(('Anti-Clone Analysis',[]))
        findings = {}
        for side, scan in zip(('A','B'), scans):
            for row in pm3_display_fields(scan):
                findings.setdefault(tuple(row), set()).add(side)
        for row, sides in findings.items():
            label = row[0] if len(sides)==2 else row[0].rstrip(':')+' '+next(iter(sides))+':'
            sections[-1][1].append((label,)+row[1:])
        # Compare both selected UID candidates against saved native Auto Scan logs.
        # A two-dump comparison alone never enables Sequential.
        evidence=[]
        for records in prepared['evidence']:
            evidence.extend(records)
        valid=[]; seen=set()
        for item in evidence:
            path=item['path']
            if path in seen:continue
            seen.add(path)
            snapshot=item['snapshot']
            captures=snapshot['captures']
            if len(captures)<3:continue
            # Auto Scan stores validated results when writing the report.
            # Compare must consume them rather than rerunning Sequential.
            saved=snapshot['result'].get('sequential_candidates') or []
            for candidate in saved:
                if isinstance(candidate,dict) and candidate.get('status')=='ON':
                    valid.append((path, str(snapshot['result'].get('uid') or '').upper(), len(captures), candidate))
        # Do not show an empty Sequential page when neither UID is in the log.
        if not evidence:
            sections.append(('Sequential Analysis',[]))
            single('Sequential','OFF')
            single('Required','3 or more dumps')
        if evidence:
            sections.append(('Sequential Analysis',[]))
            single('Source', 'Auto Scan log')
            if not valid:
                single('Sequential','OFF')
            counter_groups, _ = self._group_sequential_evidence(valid)
            multiple_uids = len({group['uid'] for group in counter_groups}) > 1
            for candidate_index, candidate in enumerate(counter_groups):
                if candidate_index:
                    sections.append(('Sequential Analysis',[]))
                # Display the confirmed counter block on the Sequential row.
                # No redundant separate Block line or ON label.
                single('Sequential','Block {}'.format(candidate['block']),'#D62636')
                if multiple_uids:
                    single('UID', candidate['uid'])
                single('Rollback','ON' if candidate.get('counter_rollback', False) else 'OFF', 'orange' if candidate.get('counter_rollback', False) else None)
                single('Scans',str(candidate['scans']))
                single('Offset',str(candidate['offset']),'#D62636')
                single('Counter',' '.join(str(x) for x in candidate['values']),'#D62636')
                single('Steps',' '.join('{:+d}'.format(x) for x in candidate['steps']),'#D62636')
                variants = candidate['variants']
                for (width, endian), refs in variants.items():
                    single('Width/endian', '{}/{}'.format(width, endian), '#D62636')
        # Keep comparison diagnostics within Sequential, without an extra intro screen.
        single('Compare','DIFFERENT' if changed else 'IDENTICAL','#C62828' if changed else None)
        for key, label in (('uid_checked','UID checked'), ('same_uid','Same UID'),
                           ('comparison_valid','Comparison valid'), ('dynamic_candidate','Dynamic candidate')):
            single(label, 'ON' if anti.get(key) else 'OFF', 'orange' if key=='dynamic_candidate' and anti.get(key) else None)
        for key, label in (('data_blocks_changed','Data blocks'),
                           ('trailer_blocks_changed','Trailers'),
                           ('manufacturer_blocks_changed','Manufacturer')):
            values = anti.get(key) or []
            single(label, ', '.join(map(str,values)) if values else 'None')
        sections.append(('Classic Structure',[]))
        structures=[analyze_mfc_structure(dump) for dump in raw]
        structure_findings=[]; structure_seen=set()
        for structure in structures:
            if not structure.get('supported'):
                item=('Structure','N/A',None)
                if item not in structure_seen:structure_seen.add(item);structure_findings.append(item)
                continue
            invalid=structure.get('access_invalid') or []
            item=('Access','INVALID' if invalid else 'VALID','orange' if invalid else None)
            if item not in structure_seen:structure_seen.add(item);structure_findings.append(item)
            if invalid:
                item=('Invalid',', '.join(str(x) for x in invalid),'orange')
                if item not in structure_seen:structure_seen.add(item);structure_findings.append(item)
            values=structure.get('value_blocks') or []
            if values:
                item=('Value blocks',', '.join(str(x) for x in values),None)
                if item not in structure_seen:structure_seen.add(item);structure_findings.append(item)
            item=('UID BCC','VALID' if structure.get('bcc0') else 'INVALID',None)
            if item not in structure_seen:structure_seen.add(item);structure_findings.append(item)
        for label,value,severity in structure_findings:single(label,value,severity)
        pages.extend(('fields',rows) for rows in field_pages(sections,_dd_translate))
        # JSON metadata has no invented section heading.
        for key in dict.fromkeys(list(metadata[0])+list(metadata[1])):
            if key in ('Created','Type'): continue
            add(key,metadata[0].get(key),metadata[1].get(key))
        # Memory blocks follow immediately; keep each complete 16-byte field atomic.
        for index,_,va,vb,_ in blocks:
            add('Block {}'.format(index),va,vb)
        pending=[]
        capacity=6  # y=43..138, 19px pitch; two 3-row blocks fit.
        for group in groups:
            if group and group[0][0]=='heading' and pending:
                pages.append(('rows',pending));pending=[]
            if len(group)>capacity:
                if pending:pages.append(('rows',pending));pending=[]
                while len(group)>capacity:
                    take=capacity
                    # Do not orphan a label from its following value.
                    if group[take-1][0]=='label':take-=1
                    pages.append(('rows',group[:take]));group=group[take:]
            if pending and len(pending)+len(group)>capacity:
                pages.append(('rows',pending));pending=[]
            pending.extend(group)
        if pending:pages.append(('rows',pending))
        return pages

    def _mfc_compare_draw(self):
        """Native Canvas; 19px pitch, labels left, long labels centered."""
        from tkinter import font as tkfont
        import re
        c=_LocalizedCanvas(self.host.getCanvas())
        tag='_dd2_changes'
        c.delete(tag);c.delete('_dd2_changes_hint')
        pages=self._mfc_compare_pages()
        self.change_page=max(0,min(self.change_page,len(pages)-1))
        mode,payload=pages[self.change_page]
        if mode=='fields':
            from _dump_diff_2_lib.screen_catalog import draw_field_page
            draw_field_page(self.host.getCanvas(),payload,self.change_page,len(pages),tag,'Back',_dd_translate)
            return
        face=('Courier New',12)
        native_measure=tkfont.Font(family='Courier New',size=12).measure
        measure=lambda text: native_measure(_dd_translate(text))
        blue,gray,red,orange='#1647D6','#64748B','#D62636','#D97706'
        def line(y,txt,color=gray,center=False):
            if measure(txt)>230:
                raise ValueError('MFC row exceeds width: '+txt)
            if center:
                c.create_text(120,y,text=txt,anchor='n',fill=color,font=face,tags=tag)
            else:
                c.create_text(measure(' '),y,text=txt,anchor='nw',fill=color,font=face,tags=tag)
        def pair(y,label,value,hexstr=None,reference=None,color=None):
            full=' '+label+' '+value
            if measure(full)>224:
                raise ValueError('MFC pair exceeds width: '+full)
            x=measure(' ')
            name=label.rstrip(' :')
            c.create_text(x,y,text=name,anchor='nw',fill=gray,font=face,tags=tag)
            c.create_text(x+measure(name),y,text=':',anchor='nw',fill='#222222',font=face,tags=tag)
            x+=measure(name+': ')
            if hexstr is not None:
                ref=re.sub(r'\s+','',reference or '').upper()
                for i in range(0,len(hexstr),2):
                    byte=hexstr[i:i+2]
                    c.create_text(x,y,text=byte,anchor='nw',font=face,
                        fill=red if reference is not None and byte!=ref[i:i+2] else (color or blue),tags=tag)
                    x+=measure(byte+' ')
            else:
                c.create_text(x,y,text=value,anchor='nw',fill=color or blue,font=face,tags=tag)
        if mode=='summary':
            line(43,self._comparison_type_label(),blue,True)
            count,filetype=payload
            pair(81,'Compare:', 'DIFFERENT' if count else 'IDENTICAL',color=red if count else blue)
            if count:pair(100,'Changed blocks:',str(count),color=red)
            if filetype:pair(119 if count else 100,'Type:',str(filetype))
        elif mode=='notice':
            from _dump_diff_2_lib.screen_catalog import analysis_notice_lines
            line(43,'Analysis Notice',red,True)
            for i,txt in enumerate(analysis_notice_lines(_dd_translate)):
                line(81+i*19,txt,gray,True)
        else:
            has_heading=bool(payload and payload[0][0]=='heading')
            # Three/four visible lines including title: one blank line after title.
            # Five/six lines: no blank line. Footer/navigation is not counted.
            y=43 if len(payload)>=5 or has_heading else 62
            if len(payload)==1 and not has_heading:
                y=(40+200-tkfont.Font(family='Courier New',size=12).metrics('linespace'))/2
            insert_gap=has_heading and 2 <= len(payload)-1 <= 4
            for row_index,row in enumerate(payload):
                if insert_gap and row_index==1:
                    y+=19
                kind,value=row[:2]
                if kind=='pair':pair(y,*value)
                elif kind=='alert_pair':pair(y,*value[:4],color=row[2])
                elif kind in ('hex','alert_hex'):
                    hexstr,reference,offset=value
                    ref=re.sub(r'\s+','',reference or '').upper()
                    vals=[hexstr[i:i+2] for i in range(0,len(hexstr),2)]
                    display=' '.join(vals)
                    x=(240-measure(display))/2
                    for i,byte in enumerate(vals):
                        c.create_text(x,y,text=byte,anchor='nw',font=face,
                            fill=row[2] if kind=='alert_hex' else red if reference is not None and byte!=ref[offset+i*2:offset+i*2+2] else blue,tags=tag)
                        x+=measure(byte+' ')
                elif kind=='heading':line(y,value,blue,True)
                elif kind=='label':line(y,value,gray,True)
                else:line(y,value,row[2] if kind=='alert_value' else
                          red if kind=='changed_value' else blue,False)
                y+=19
        self._footer_hint('Back',y=177,tag='_dd2_changes_hint')
        c.create_text(120,190,text='Page {}/{}'.format(self.change_page+1,len(pages)),
                      anchor='center',fill=blue,font=('Courier New',10),tags=tag)
        if self.change_page:c.create_text(235,43,text='▲',anchor='ne',fill=blue,font=('Arial',9),tags=tag)
        if self.change_page+1<len(pages):c.create_text(235,198,text='▼',anchor='se',fill=blue,font=('Arial',9),tags=tag)

    def show_changes(self):
        if not self.result:
            return
        if self.category == 'iCLASS':
            return self._iclass_result_draw()
        if self.category == 'Ultralight / NTAG':
            return self._ultralight_compare_draw()
        if self.category == 'MIFARE Classic':
            return self._mfc_compare_draw()
        if self.category in ('Paxton Net2', 'Paxton Switch2'):
            return self._paxton_compare_draw()
        if self.category == 'T5577':
            return self._t5577_compare_draw()
        extras = self._abc_compare_pages()
        total = len(extras) + len(self._full_block_pages())
        self.change_page = max(0, min(self.change_page, total-1))
        if self.change_page < len(extras):
            return self._abc_draw_compare_intro(extras[self.change_page], total)
        return self._show_full_block_compare(
            page_override=self.change_page-len(extras), total_override=total,
            show_intro=(len(extras) == 0))

    def _anticopy_lines(self):
        """Build every Anti-Copy row; never discard diagnostics."""
        report = self.result.get('anticopy') or {}
        a, b = report.get('a', {}), report.get('b', {})
        lines = [('Anti-Copy comparison', '#1647D6')]
        for prefix, obj in (('A:', a), ('B:', b)):
            labels = obj.get('matches', []) + obj.get('experimental', [])
            color = '#D00000' if labels else '#222222'
            status = obj.get('status', '?')
            if labels:
                # Keep the Urmet Captiv marker readable on the 240px display.
                first_label = str(labels[0])
                if first_label == 'Urmet Captiv marker':
                    lines.append(('{} Urmet Captiv'.format(prefix), color))
                else:
                    lines.append(('{} Found {}'.format(prefix, first_label), color))
                for label in labels[1:]:
                    lines.append(('  ' + str(label), color))
            else:
                lines.append(('{} {}'.format(prefix, status), color))
        if report.get('comparison_valid'):
            data_count = len(report.get('data_blocks_changed', []))
            trailer_count = len(report.get('trailer_blocks_changed', []))
            lines.append(('Data changed: {}'.format(data_count), '#222222'))
            manufacturer_count = len(report.get('manufacturer_blocks_changed', []))
            lines.append(('Manufacturer changed: {}'.format('Y' if manufacturer_count else 'N'), '#222222'))
            lines.append(('Trailers: {}'.format(trailer_count), '#222222'))
            if report.get('uid_checked') and not report.get('same_uid'):
                lines.append(('Different UID', '#222222'))
        if self.result.get('security') is not None:
            # Keep Security analysis together with its values on page 2.
            if len(lines) == 6:
                lines.append(('', '#222222'))
            for line in security_info_lines(self.result['security'], self.sequential_enabled):
                line = re.sub(r'\bcand\.', 'candidate', line)
                finding = re.match(r'^(Counter|Mirror):\s*(\d+)\s+candidate(?:s)?\b', line)
                color = '#1647D6' if line == 'Security analysis' else ('#B36B00' if finding and int(finding.group(2)) > 0 else '#222222')
                lines.append((line, color))
        else:
            lines.append(('HEURISTIC - NOT PROOF', '#222222'))
        return lines

    def _anticopy_pages(self):
        lines = list(self._anticopy_lines())
        # Do not create a page containing only the heuristic disclaimer.
        lines = [line for line in lines if line[0] != 'HEURISTIC - NOT PROOF'] + [
            line for line in lines if line[0] == 'HEURISTIC - NOT PROOF']
        pages = [lines[i:i+7] for i in range(0, len(lines), 7)] or [[]]
        if len(pages) > 1 and len(pages[-1]) == 1 and pages[-1][0][0] == 'HEURISTIC - NOT PROOF':
            # Replace a redundant blank on previous page, or keep a two-line final page.
            if any(not line[0] for line in pages[-2]):
                pages[-2] = [line for line in pages[-2] if line[0]] + pages[-1]
                pages.pop()
            else:
                pages[-1].insert(0, pages[-2].pop())
        return pages




    def next_changes(self):
        if self.category == 'Ultralight / NTAG':
            self.change_page = min(self.change_page + 1, len(self._ultralight_compare_pages()) - 1)
            return self.show_changes_safe()
        if self.category == 'MIFARE Classic':
            self.change_page = min(self.change_page + 1, len(self._mfc_compare_pages()) - 1)
            return self.show_changes_safe()
        if self.category == 'iCLASS':
            self.change_page = min(self.change_page + 1, len(self._iclass_result_pages()) - 1)
            return self.show_changes_safe()
        if self.category in ('Paxton Net2', 'Paxton Switch2'):
            self.change_page = min(self.change_page + 1, len(self._paxton_compare_pages()) - 1)
            return self.show_changes_safe()
        if self.category == 'T5577':
            self.change_page = min(self.change_page + 1, len(self._t5577_compare_pages()) - 1)
            return self.show_changes_safe()
        extra = len(self._abc_compare_pages())
        if self.change_page + 1 < extra + len(self._full_block_pages()):
            self.change_page += 1
        self.show_changes_safe()

    def prev_changes(self):
        self.change_page = max(0, self.change_page - 1)
        self.show_changes_safe()

    def show_changes_safe(self):
        try:
            return self.show_changes()
        except (ValueError, TypeError, KeyError, IndexError, OSError) as exc:
            self._dd_set_error(str(exc))
            self.host._set_state('error')

    def clear_changes(self):
        self.host.getCanvas().delete('_dd2_changes')
        self.host.getCanvas().delete('_dd2_changes_hint')
