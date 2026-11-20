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

"""T5577 Multiwriter plugin for iCopy-XS
Copyright (c) 2026: jareckib

Port of lf_t55xx_multiwriter.lua.

Stores 1, 2 or 3 EM4102 UIDs on a single T5577 tag.
Supports:
  - Manual HEX input: exactly 10 hexadecimal characters (40-bit UID)
  - Manual DEC input: 1 to 13 decimal digits (engraved ID)
  - DEC range validation: 0 to 1099511627775 (0xFFFFFFFFFF)
    (all-zero IDs are rejected during input validation)
  - Reading EM4102 IDs from an original fob via PM3
  - Encoding and writing multiple UIDs to T5577

Each explicit user read/write attempt renews the executor recovery budget
when supported. Failed reads request one managed reader restart; retry is
offered only after confirmed recovery. Block writes and automatic
verification do not renew the budget, and writes are never replayed
automatically.
"""

import re
from lib.input_dec import FreeDecInput
from lib.input_hex import FreeHexInput
from lib._constants import SCREEN_W, BTN_BAR_Y0, NORMAL_TEXT_COLOR
from lib import resources

TIMEOUT_READ  = 10000
TIMEOUT_WRITE = 8000
TIMEOUT_PRECHECK = 5000
TIMEOUT_DET   = 15000   # 15 s maximum for dedicated T55xx detect

BLOCK0 = {1: '00148040', 2: '00148080', 3: '001480C0'}


# ---------------------------------------------------------------------------
# EM4102 encoding
# ---------------------------------------------------------------------------

def _hex_to_bin40(hex_value):
    """Convert exactly 10-hex EM4102 UID into its raw 40-bit binary representation.

    Accept only 10 hex characters (40 bits). Return None on invalid input.
    """
    if not isinstance(hex_value, str) or not re.fullmatch(r'[0-9A-Fa-f]{10}', hex_value):
        return None
    val_clean = hex_value.upper()
    dec = int(val_clean, 16)
    return '{:040b}'.format(dec)


def _even_parity(bits):
    return '0' if bits.count('1') % 2 == 0 else '1'


def encode_uid(uid_hex):
    """Encode EM4102 UID into T5577 format (two 8-hex blocks).

    uid_hex must be a 10-hex string (40 bits). Returns (block_a, block_b) or None.
    """
    uid_bin = _hex_to_bin40(uid_hex)
    if uid_bin is None:
        return None

    # 9 start bits (1 + 8x1)
    start_bits = '1' + '1' * 8

    # 40 data bits + parity bit every 4 bits
    data_with_parity = ''
    for i in range(0, 40, 4):
        nibble = uid_bin[i:i+4]
        data_with_parity += nibble + _even_parity(nibble)

    # 4 column parity bits
    col_parity = ''
    for col in range(4):
        col_bits = data_with_parity[col::5]
        col_parity += _even_parity(col_bits)

    # Stop bit
    full_bin = start_bits + data_with_parity + col_parity + '0'

    # Convert to hex (64 bits = 16 hex characters = 2 blocks of 8)
    full_hex = '{:016X}'.format(int(full_bin, 2))
    return full_hex[:8], full_hex[8:]


def dec_to_hex_uid(dec_str):
    """Convert a 1..13-digit decimal ID within the EM4102 40-bit range."""
    if not isinstance(dec_str, str) or not re.fullmatch(r'[0-9]{1,13}', dec_str):
        return None
    value = int(dec_str)
    if value > 0xFFFFFFFFFF:
        return None
    return '{:010X}'.format(value)


# ---------------------------------------------------------------------------
# PM3 output parsers
# ---------------------------------------------------------------------------

def _parse_em410x_id(output):
    """Accept only a complete 40-bit EM4102 ID, never XL or a partial match."""
    if not output:
        return None
    if isinstance(output, bytes):
        output = output.decode('utf-8', 'replace')
    for line in str(output).splitlines():
        # Match the entire ID field; do not take ten characters from a longer
        # UID, a malformed suffix, or an EM410x XL response.
        m = re.fullmatch(
            r'\s*(?:\[\+\]\s*)?EM\s*410x\s+ID\s*:?\s*([0-9A-Fa-f]{10})\s*',
            line, re.IGNORECASE,
        )
        if m:
            return m.group(1).upper()
    return None


def _parse_block(output, block_num):
    """Parse a Page 0 block from T55xx dump or single-block read output.

    Ignore ANSI terminal formatting and never accidentally use Page 1 blocks.
    """
    if not output:
        return None
    if isinstance(output, bytes):
        output = output.decode('utf-8', 'replace')
    output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(output))
    output = output.replace('\r', '\n')
    page = 0
    for line in output.splitlines():
        heading = re.search(r'\bPage\s+([01])\b', line, re.IGNORECASE)
        if heading:
            page = int(heading.group(1))
            continue
        if page != 0:
            continue
        match = re.search(
            r'^\s*(?:\[\+\]\s*)?0?([0-7])\s*\|\s*([0-9A-Fa-f]{8})(?=\s*\|)',
            line,
        )
        if match and int(match.group(1)) == block_num:
            return match.group(2).upper()
    return None


# ---------------------------------------------------------------------------
# Plugin Class Implementation
# ---------------------------------------------------------------------------

class T55xxMultiwriterPlugin(object):

    def __init__(self, host=None):
        self.host = host
        self._dec = None
        self._hex = None
        self._recovery_status = None
        self._blink_active = False
        self._blink_generation = 0
        self._blink_after_id = None


    # -- helpers ----------------------------------------------------------

    def _close_inputs(self):
        """Release native input widgets on the UI thread."""
        for name in ('_dec', '_hex'):
            widget = getattr(self, name)
            if widget is not None:
                widget.hide()
                setattr(self, name, None)

    def on_destroy(self):
        self._stop_detect_wait_blink()
        self._close_inputs()

    def _begin_user_operation(self):
        """Worker-only fresh recovery budget for an explicit user attempt."""
        try:
            import executor
        except ImportError:
            return  # Older hosts may expose PM3 only through the plugin API.
        reset = getattr(executor, 'resetReworkCount', None)
        if callable(reset):
            reset()

    def _pm3(self, cmd, timeout=TIMEOUT_WRITE):
        """Execute one PM3 command; leave transport recovery to the executor."""
        return self.host.pm3_command(cmd, timeout=timeout)

    def _get_uid_list(self):
        """Load the UID list from state variables."""
        uids = []
        for i in range(1, 4):
            uid = self.host.get_var('uid{}'.format(i), '')
            if uid:
                uids.append(uid)
        return uids

    def _read_transport_error(self, recovered_status):
        """Keep the error and UID list; request recovery without replaying RF."""
        self._recovery_status = recovered_status
        return {'status': 'recover_reader'}

    def start_reader_recovery(self):
        """Center the recovery notice on UI before starting the worker."""
        self._stop_detect_wait_blink()
        canvas = self.host.getCanvas()
        for item in canvas.find_withtag('_jr_content'):
            if canvas.type(item) == 'text':
                canvas.coords(item, SCREEN_W // 2, 120)
                canvas.itemconfigure(item, anchor='center',
                                     font=resources.get_font(16), width=222,
                                     justify='center')
        self.host._execute_action('run:do_recover_reader')

    def do_recover_reader(self):
        """Worker-only managed restart, once per failed read operation."""
        status = self._recovery_status
        self._recovery_status = None
        try:
            import executor
            recovered = status is not None and executor.reworkPM3All() is True
        except Exception:
            recovered = False
        if recovered:
            return {'status': status}
        self.host.set_var('error_msg', self.host.tr('PM3 restart failed.\nRestart device.'))
        return {'status': 'recovery_failed'}

    def _set_uid(self, index, uid):
        self.host.set_var('uid{}'.format(index), uid)

    def _clear_uids(self):
        for i in range(1, 4):
            self.host.set_var('uid{}'.format(i), '')
        self.host.set_var('uid_count', '0')

    def _update_uid_count(self):
        count = len(self._get_uid_list())
        self.host.set_var('uid_count', str(count))
        if count == 1:
            self.host.set_var('uid_count_label', self.host.tr('{} UID stored').format(count))
        else:
            self.host.set_var('uid_count_label', self.host.tr('{} UIDs stored').format(count))
        # Summary
        lines = []
        for i, uid in enumerate(self._get_uid_list(), 1):
            lines.append(self.host.tr('UID{}: {}').format(i, uid))
        self.host.set_var('uid_summary', '\n'.join(lines) if lines else self.host.tr('No UIDs yet'))
        self.host.set_var('block0_label', self.host.tr('Block 0: {}').format(BLOCK0[count]) if count in BLOCK0 else self.host.tr('Block 0: --------'))
        return count

    # -- Initialization ----------------------------------------------------

    def do_init(self):
        self._clear_uids()
        self.host.set_var('error_msg', '')
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
        self.host.set_var('last_uid', '')
        self.host.set_var('written_count', '0')
        self.host.set_var('block0_label', self.host.tr('Block 0: --------'))
        self.host.set_var('uid_summary', self.host.tr('No UIDs yet'))
        self.host.set_var('uid_count_label', self.host.tr('0 UIDs stored'))
        self.host.set_var('input_mode', '')
        self._dec = None
        self._hex = None
        return {'status': 'ok'}

    def _input_validation_error(self, first, second=''):
        """Show two separately centered validation lines, as in EM from dec."""
        self.host.set_var('error_line1', first)
        self.host.set_var('error_line2', second)
        self.host.set_var('error_msg', first + ('\n' + second if second else ''))
        return {'status': 'error'}

    # -- DEC input --------------------------------------------------------

    def draw_menu_footer(self):
        """Draw normal-weight, translated main-menu hints above the button bar."""
        self._draw_bottom_hints(self.host.tr('OK - Read original fob'), self.host.tr('SRW - Exit'))

    def draw_add_uid_footer(self):
        self._draw_bottom_hints(self.host.tr('OK  - Read EM'))

    def draw_uid_added_footer(self):
        self._draw_bottom_hints(self.host.tr('OK - Write to T5577'))
        self.host.getCanvas().create_text(
            SCREEN_W // 2, BTN_BAR_Y0 - 24,
            text=self.host.tr('SRW - Clear UIDs'), font=resources.get_font(10),
            fill=NORMAL_TEXT_COLOR, anchor='s', tags='_jr_content',
        )

    def draw_verify_fail_footer(self):
        self.draw_error()
        self._draw_bottom_hints(self.host.tr('OK - Retry write'))

    def draw_input_method_error_footer(self):
        self.draw_error()
        self._draw_bottom_hints(self.host.tr('OK - back to options'))  # Translated, centered error-screen hint

    def draw_place_tag_footer(self):
        self._draw_bottom_hints(self.host.tr('Press OK to write'))

    def draw_success_footer(self):
        self._draw_bottom_hints(self.host.tr('OK - Write again'))

    def draw_lf_check_error_footer(self):
        self.draw_error()
        self._draw_bottom_hints(self.host.tr('OK - Retry'))

    def draw_write_error_footer(self):
        self.draw_error()
        self._draw_bottom_hints(self.host.tr('OK - retry write'))

    def draw_error(self):
        self._draw_fitted_message('#D62636', bottom=174)

    def draw_information(self):
        self._draw_fitted_message(NORMAL_TEXT_COLOR, bottom=195)

    def _draw_fitted_message(self, color, bottom):
        """Enlarge translated native content without touching bars or keys.

        Use the button-bar font size where it fits; measure both dimensions
        before falling back for longer messages. Called only on the UI thread.
        """
        import tkinter.font as tkfont
        canvas = self.host.getCanvas()
        texts = [canvas.itemcget(item, 'text')
                 for item in canvas.find_withtag('_jr_content')
                 if canvas.type(item) == 'text' and
                 canvas.itemcget(item, 'text').strip()]
        if not texts:
            return
        for size in (16, 14, 13, 12, 10):
            face = resources.get_font(size)
            font = tkfont.Font(font=face)
            rows = []
            for text in texts:
                for paragraph in text.splitlines():
                    line = ''
                    for word in paragraph.split():
                        if line and font.measure(line + ' ' + word) > 222:
                            rows.append(line)
                            line = ''
                        while font.measure(word) > 222:
                            stop = 1
                            while stop < len(word) and font.measure(word[:stop + 1]) <= 222:
                                stop += 1
                            rows.append(word[:stop])
                            word = word[stop:]
                        line += (' ' if line else '') + word
                    if line:
                        rows.append(line)
            height = font.metrics('linespace')
            step = max(19, height + 1)
            y = (120 - height / 2) if len(rows) == 1 else 81 if len(rows) <= 3 else 62 if len(rows) == 4 else 43
            if y + (len(rows) - 1) * step + height <= bottom:
                break
        canvas.delete('_jr_content')
        for row in rows:
            canvas.create_text(SCREEN_W // 2, y, text=row, anchor='n',
                               font=face, fill=color, tags='_jr_content')
            y += step

    def draw_colored_uid_values(self):
        """Color values on every UID line, including multiline summaries.

        Keep labels dark. Rebuild from the current rendered text each time the
        screen is entered, so Back/Remove/New do not leave stale colored text.
        """
        import tkinter.font as tkfont
        canvas = self.host.getCanvas()
        for item in tuple(canvas.find_withtag('_jr_content')):
            if canvas.type(item) != 'text':
                continue
            raw = canvas.itemcget(item, 'text')
            lines = raw.split('\n')
            if not any(re.fullmatch(
                    r'(?:UID[0-9]*|HEX|DEC|Block 0|Bloc 0)\s*:\s*[0-9A-Fa-f]+', x.strip())
                    for x in lines):
                continue
            font_spec = canvas.itemcget(item, 'font')
            font = tkfont.Font(font=font_spec)
            line_height = font.metrics('linespace')
            bbox = canvas.bbox(item)
            if not bbox:
                continue
            original_tags = tuple(canvas.gettags(item))
            original_color = canvas.itemcget(item, 'fill')
            canvas.delete(item)
            for index, line in enumerate(lines):
                y = bbox[1] + index * line_height
                m = re.fullmatch(
                    r'(UID[0-9]*|HEX|DEC|Block 0|Bloc 0)(\s*:\s*)([0-9A-Fa-f]+)',
                    line.strip())
                if not m:
                    canvas.create_text(SCREEN_W // 2, y, text=line,
                                       font=font_spec, fill=original_color,
                                       anchor='n', tags=original_tags)
                    continue
                prefix = m.group(1) + m.group(2)
                value = m.group(3)
                x = (SCREEN_W - font.measure(prefix + value)) // 2
                canvas.create_text(x, y, text=prefix, font=font_spec,
                                   fill=NORMAL_TEXT_COLOR, anchor='nw',
                                   tags=original_tags)
                canvas.create_text(x + font.measure(prefix), y, text=value,
                                   font=font_spec, fill='#0000FF', anchor='nw',
                                   tags=original_tags)

    def _draw_bottom_hints(self, *labels):
        self.draw_colored_uid_values()
        canvas = self.host.getCanvas()
        canvas.delete('_multiwriter_menu_footer')
        font = resources.get_font(12)
        bottom = BTN_BAR_Y0 - 5
        for i, label in enumerate(reversed(labels)):
            canvas.create_text(
                SCREEN_W // 2, bottom - i * 19,
                text=label, font=font,
                fill=NORMAL_TEXT_COLOR, anchor='s',
                tags=('_jr_content', '_multiwriter_menu_footer'),
            )

    def show_dec_input(self):
        self._close_inputs()
        canvas = self.host.getCanvas()
        self._dec = FreeDecInput(
            canvas, label=self.host.tr('DEC: '),
            hint=self.host.tr('\nUp/Down - digit\nLeft/Right - move'),
            hint_font_size=12,
            max_length=13,
        )
        self._dec.show()

    def dec_roll_up(self):
        if self._dec is not None:
            self._dec.rollUp()

    def dec_roll_down(self):
        if self._dec is not None:
            self._dec.rollDown()

    def dec_move_left(self):
        if self._dec is not None:
            self._dec.moveLeft()

    def dec_move_right(self):
        if self._dec is not None:
            self._dec.moveRight()

    def do_capture_dec(self):
        """Get UID from the dec input (up to 13 decimal digits = engraved ID)."""
        self.host.set_var('error_msg', '')
        dec = self._dec.getValue() if self._dec is not None else ''
        if self._dec is not None:
            self._dec.hide()
            self._dec = None

        if not dec:
            return self._input_validation_error(self.host.tr('Enter a digit.'))

        if re.fullmatch(r'0+', dec):
            return self._input_validation_error(self.host.tr('ID cannot be'), self.host.tr('all zeros.'))

        uid = dec_to_hex_uid(dec)
        if uid is None:
            return self._input_validation_error(self.host.tr('Invalid DEC'), self.host.tr('(max 40-bit).'))

        return self._store_uid(uid)

    # -- HEX input (fixed 10 hex) ----------------------------------------

    def show_hex_input(self):
        self._close_inputs()
        canvas = self.host.getCanvas()
        # Force exactly 10 hex characters for EM4102
        self._hex = FreeHexInput(
            canvas, label=self.host.tr('INPUT HEX:'),
            hint=self.host.tr('\nUp/Down - digit\nLeft/Right - move'),
            max_length=10,
            per_line=10,
            hint_font_size=12,
        )
        self._hex.show()

    def hex_roll_up(self):
        if self._hex is not None:
            self._hex.rollUp()

    def hex_roll_down(self):
        if self._hex is not None:
            self._hex.rollDown()

    def hex_move_left(self):
        if self._hex is not None:
            self._hex.moveLeft()

    def hex_move_right(self):
        if self._hex is not None:
            self._hex.moveRight()

    def do_capture_hex(self):
        """Get UID from the hex input widget. Only exactly 10 hex chars accepted."""
        self.host.set_var('error_msg', '')
        val = self._hex.getValue() if self._hex is not None else ''
        if self._hex is not None:
            self._hex.hide()
            self._hex = None
        if not val:
            return self._input_validation_error(self.host.tr('Enter HEX'), self.host.tr('characters.'))

        uid = val.upper()
        # Enforce exact 10-hex length for EM4102
        if not re.fullmatch(r'[0-9A-F]{10}', uid):
            return self._input_validation_error(self.host.tr('Invalid HEX length'), self.host.tr('Exactly 10 HEX required.'))

        if int(uid, 16) == 0:
            return self._input_validation_error(self.host.tr('UID cannot be'), self.host.tr('all zeros.'))

        return self._store_uid(uid)

    def _back_from_input(self, widget_name):
        """Hide the editor on the UI thread; preserve already stored UIDs."""
        widget = getattr(self, widget_name)
        if widget is not None:
            widget.hide()
            setattr(self, widget_name, None)
        count = self._update_uid_count()
        if count >= 3:
            return {'status': 'stored_full'}
        if count > 0:
            return {'status': 'stored_more'}
        return {'status': 'empty'}

    def retry_dec_input(self):
        """Re-enter the DEC editor after a validation error."""
        self._dec = None
        self.host.set_var('error_msg', '')
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
        return {'status': 'retry'}

    def retry_hex_input(self):
        """Re-enter the HEX editor after a validation error."""
        self._hex = None
        self.host.set_var('error_msg', '')
        self.host.set_var('error_line1', '')
        self.host.set_var('error_line2', '')
        return {'status': 'retry'}

    def dec_back_cleanse(self):
        return self._back_from_input('_dec')

    def hex_back_cleanse(self):
        return self._back_from_input('_hex')

    def do_return_to_uid_list(self):
        """Return to the UID summary without discarding stored entries."""
        count = self._update_uid_count()
        if count >= 3:
            return {'status': 'stored_full'}
        if count > 0:
            return {'status': 'stored_more'}
        return {'status': 'empty'}

    def do_clear_uid_list(self):
        """Clear only the in-memory session after explicit UI confirmation."""
        self._clear_uids()
        self.host.set_var('last_uid', '')
        return self.do_cancel_write()

    # -- Read original fob ------------------------------------------------

    def do_read_fob(self):
        """Read UID from the original fob via PM3."""
        self.host.set_var('error_msg', '')
        if len(self._get_uid_list()) >= 3:
            return {'status': 'full'}
        try:
            self._begin_user_operation()
            ok, out = self._pm3('lf em 410x reader', TIMEOUT_READ)
        except Exception:
            ok, out = False, ''
        # A failed PM3 command must never contribute a UID, even when its
        # output contains a plausible-looking ID (e.g. stale/partial output).
        if not ok:
            self.host.set_var('error_msg', self.host.tr('No EM410x tag detected.\nAdjust position and retry.'))
            return self._read_transport_error('read_recovered')
        uid = _parse_em410x_id(out) if out else None

        if not uid:
            self.host.set_var('error_msg', self.host.tr('No EM410x tag detected.\nAdjust position and retry.'))
            return {'status': 'error'}

        if not re.fullmatch(r'[0-9A-F]{10}', uid):
            self.host.set_var('error_msg', self.host.tr('Read UID has unsupported length or format.\nExpected exactly 10 hex (EM4102).'))
            return {'status': 'error'}

        return self._store_uid(uid)

    def _store_uid(self, uid):
        """Save the UID into the next available slot."""
        uids = self._get_uid_list()
        if len(uids) >= 3:
            self.host.set_var('error_msg', self.host.tr('Maximum 3 UIDs reached.'))
            return {'status': 'full'}

        if not isinstance(uid, str) or not re.fullmatch(r'[0-9A-Fa-f]{10}', uid) or int(uid, 16) == 0:
            self.host.set_var('error_msg', self.host.tr('Invalid UID: {}').format(uid))
            return {'status': 'error'}
        # Encode and verify
        result = encode_uid(uid)
        if result is None:
            self.host.set_var('error_msg', self.host.tr('Encoding failed for:\n{}').format(uid))
            return {'status': 'error'}

        # Store in the first empty slot. This also keeps the slot index correct
        # if the state was left partially populated after navigating Back.
        idx = None
        for slot in range(1, 4):
            if not self.host.get_var('uid{}'.format(slot), ''):
                idx = slot
                break

        if idx is None:
            self.host.set_var('error_msg', self.host.tr('Maximum 3 UIDs reached.'))
            return {'status': 'full'}

        self._set_uid(idx, uid)
        count = self._update_uid_count()
        self.host.set_var('last_uid', uid)

        if count < 3:
            return {'status': 'stored_more'}
        else:
            return {'status': 'stored_full'}

    def do_precheck(self):
        """Fast LF protocol check; never start detect if the transport timed out.

        A positive LF decode is evidence of a readable tag, not proof of T5577.
        Blank/unconfigured/password-protected T5577 may fail this precheck.
        """
        self.host.set_var('error_msg', '')
        if not self._get_uid_list():
            self.host.set_var('error_msg', self.host.tr('No UIDs to write.'))
            return {'status': 'error'}
        try:
            self._begin_user_operation()
            ok, out = self._pm3('lf search', TIMEOUT_PRECHECK)
        except Exception:
            self.host.set_var('error_msg', self.host.tr('LF check: communication error.'))
            return self._read_transport_error('write_recovered')
        if not ok:
            self.host.set_var('error_msg', self.host.tr('LF check failed or timed out.'))
            return self._read_transport_error('write_recovered')
        # 'lf search' cannot reliably identify a blank/unconfigured T5577.
        # A successful transport response is sufficient to attempt dedicated detect.
        return {'status': 'ok'}

    def _run_progress(self, handler):
        """Run the real operation without an artificial display delay."""
        try:
            return handler()
        finally:
            # Worker only changes flags; UI owns the scheduled Tk callback.
            self._blink_active = False
            self._blink_generation += 1

    def do_precheck_visible(self):
        return self._run_progress(self.do_precheck)

    def start_precheck(self):
        self._start_progress('run:do_precheck_visible')

    def start_write(self):
        self._start_progress('run:do_write_visible')

    def start_verify(self):
        self._start_progress('run:do_verify_visible')

    def _stop_detect_wait_blink(self):
        """Cancel the scheduled animation on the UI thread."""
        self._blink_active = False
        self._blink_generation += 1
        if self._blink_after_id is not None:
            self.host.getCanvas().after_cancel(self._blink_after_id)
            self._blink_after_id = None

    def start_detect(self):
        self._start_progress('run:do_detect_visible')

    def _start_progress(self, action):
        """One stable native layout for every stage; RF stays in run:."""
        self._stop_detect_wait_blink()
        canvas = self.host.getCanvas()
        items = [item for item in canvas.find_withtag('_jr_content')
                 if canvas.type(item) == 'text' and
                 canvas.itemcget(item, 'text').strip()]
        for item, y in zip(items, (70, 120, 162)):
            canvas.coords(item, SCREEN_W // 2, y)
            canvas.itemconfigure(item, anchor='center')
            if y != 120:
                # Two lines at most, measured with the device's actual font.
                # Keep clear of both the centered Wait and native bars.
                for size in (16, 15, 14, 13, 12):
                    canvas.itemconfigure(item, font=resources.get_font(size),
                                         width=222, justify='center')
                    box = canvas.bbox(item)
                    if box and box[3] - box[1] <= 52 and box[0] >= 0 and box[2] <= SCREEN_W:
                        break
        self._blink_active = True
        generation = self._blink_generation
        wait_texts = ('Wait...', self.host.tr('Wait...'))
        matches = [item for item in canvas.find_withtag('_jr_content')
                   if canvas.type(item) == 'text' and
                   canvas.itemcget(item, 'text') in wait_texts]
        if matches:
            item = matches[-1]
            canvas.coords(item, SCREEN_W // 2, 120)
            canvas.itemconfigure(item, anchor='center', font=resources.get_font(16))
            def tick(visible):
                self._blink_after_id = None
                if not self._blink_active or generation != self._blink_generation:
                    return
                if canvas.type(item) != 'text':
                    return
                canvas.itemconfigure(item, state='normal' if visible else 'hidden')
                self._blink_after_id = canvas.after(1000, tick, not visible)
            self._blink_after_id = canvas.after(1000, tick, False)
        self.host._execute_action(action)

    def do_detect_visible(self):
        return self._run_progress(self.do_detect)

    def do_write_visible(self):
        return self._run_progress(self.do_write)

    def do_verify_visible(self):
        return self._run_progress(self.do_verify)

    # -- Write to T5577 ---------------------------------------------------

    def do_detect(self):
        """Detect tag only after successful LF precheck."""
        self.host.set_var('error_msg', '')
        if not self._get_uid_list():
            self.host.set_var('error_msg', self.host.tr('No UIDs to write.'))
            return {'status': 'error'}
        try:
            ok, detect_output = self._pm3('lf t55xx detect', TIMEOUT_DET)
        except Exception:
            self.host.set_var('error_msg', self.host.tr('T5577 detection: communication error.'))
            return self._read_transport_error('write_recovered')
        if not ok:
            self.host.set_var('error_msg', self.host.tr('T5577 detection: communication error.'))
            return self._read_transport_error('write_recovered')
        if not re.search(r'Chip type\s*\.{0,12}\s*[:=]?\s*T55x7\b', detect_output or '', re.IGNORECASE):
            self.host.set_var('error_msg', self.host.tr('T5577 detection failed.\nCheck tag and position.'))
            return {'status': 'error'}
        return {'status': 'ok'}

    def do_write(self):
        """Write data only after precheck and detect have succeeded."""
        self.host.set_var('error_msg', '')
        uids = self._get_uid_list()
        if not 1 <= len(uids) <= 3:
            self.host.set_var('error_msg', self.host.tr('Invalid UID count.'))
            return {'status': 'error'}
        all_blocks = []
        for uid in uids:
            result = encode_uid(uid)
            if result is None or int(uid, 16) == 0:
                self.host.set_var('error_msg', self.host.tr('Invalid UID: {}').format(uid))
                return {'status': 'error'}
            all_blocks.extend(result)
        block0 = BLOCK0[len(uids)]
        self.host.set_var('block0_label', self.host.tr('Block 0: {}').format(block0))
        # A new attempt invalidates the previous verification snapshot.
        self.host.set_var('written_count', '0')
        self.host.set_var('written_block0', '')
        for i in range(1, 7):
            self.host.set_var('written_block{}'.format(i), '')
        for i, blk in [(0, block0)] + list(enumerate(all_blocks, 1)):
            try:
                ok, _ = self._pm3('lf t55xx write -b {} -d {}'.format(i, blk), TIMEOUT_WRITE)
            except Exception:
                self.host.set_var('error_msg', self.host.tr('Communication error on block {}.').format(i))
                return {'status': 'error'}
            if not ok:
                self.host.set_var('error_msg', self.host.tr('Write failed on block {}.\nCheck tag position.').format(i))
                return {'status': 'error'}
        self.host.set_var('written_block0', block0)
        for i, blk in enumerate(all_blocks, 1):
            self.host.set_var('written_block{}'.format(i), blk)
        self.host.set_var('written_count', str(len(all_blocks)))
        return {'status': 'done'}

    def do_verify(self):
        """Verify written Page 0 blocks in RAM, without creating dump files.

        Read all blocks, then retry only failed blocks once.
        The tag must remain in place until the last block is verified.
        """
        self.host.set_var('error_msg', '')
        block0 = self.host.get_var('written_block0', '')
        try:
            n = int(self.host.get_var('written_count', '0'))
        except (TypeError, ValueError):
            n = 0
        if not block0 or not 1 <= n <= 6:
            self.host.set_var('error_msg', self.host.tr('No write data to verify.'))
            return {'status': 'error'}

        expected = {
            i: (block0 if i == 0 else self.host.get_var(
                'written_block{}'.format(i), ''))
            for i in range(n + 1)
        }
        if any(not re.fullmatch(r'[0-9A-Fa-f]{8}', value or '')
               for value in expected.values()):
            self.host.set_var('error_msg', self.host.tr('No write data to verify.'))
            return {'status': 'error'}

        # Always perform the fast LF search before dedicated detect, also
        # when verifying after a write. Do not enter detect on transport failure.
        try:
            search_ok, search_output = self._pm3('lf search', TIMEOUT_PRECHECK)
        except Exception:
            search_ok, search_output = False, ''
        if not search_ok:
            self.host.set_var('error_msg', self.host.tr(
                'LF check failed or timed out.'))
            return self._read_transport_error('lf_check_failed')

        # Block 0 was written first; re-detect to configure subsequent reads.
        try:
            detected, detect_output = self._pm3('lf t55xx detect', TIMEOUT_DET)
        except Exception:
            detected, detect_output = False, ''
        if not detected:
            self.host.set_var('error_msg', self.host.tr('T5577 detection: communication error.'))
            return self._read_transport_error('verify_recovered')
        if not re.search(
                r'Chip type\s*\.{0,12}\s*[:=]?\s*T55x7\b',
                detect_output or '', re.IGNORECASE):
            self.host.set_var('error_msg', self.host.tr(
                'T5577 not detected\nafter writing.'))
            return {'status': 'failed'}

        # Collect data mismatches, but stop immediately on transport failure.
        failed = []
        for i in range(n + 1):
            try:
                read_ok, output = self._pm3(
                    'lf t55xx read -b {}'.format(i), TIMEOUT_READ)
            except Exception:
                read_ok, output = False, ''
            if not read_ok:
                self.host.set_var('error_msg', self.host.tr('Cannot read block {}').format(i))
                return self._read_transport_error('verify_recovered')
            found = _parse_block(output, i) if read_ok else None
            if found is None or found.upper() != expected[i].upper():
                failed.append(i)

        # Second pass: retry ONLY the blocks that failed in pass one.
        still_failed = []
        for i in failed:
            try:
                read_ok, output = self._pm3(
                    'lf t55xx read -b {}'.format(i), TIMEOUT_READ)
            except Exception:
                read_ok, output = False, ''
            if not read_ok:
                self.host.set_var('error_msg', self.host.tr('Cannot read block {}').format(i))
                return self._read_transport_error('verify_recovered')
            found = _parse_block(output, i) if read_ok else None
            if found is None or found.upper() != expected[i].upper():
                still_failed.append(i)

        if still_failed:
            i = still_failed[0]
            self.host.set_var('error_msg', self.host.tr(
                'Block {} mismatch').format(i))
            return {'status': 'failed'}

        return {'status': 'ok'}

    def do_write_again(self):
        """Start a new write with the existing UID list intact."""
        return {'status': 'ok'}

    def do_cancel_write(self):
        """Cancel the current write attempt without deleting the UID list."""
        self.host.set_var('error_msg', '')
        # Invalidate verification data from the failed/abandoned attempt.
        self.host.set_var('written_count', '0')
        self.host.set_var('written_block0', '')
        for i in range(1, 7):
            self.host.set_var('written_block{}'.format(i), '')
        count = self._update_uid_count()
        if count >= 3:
            return {'status': 'stored_full'}
        if count > 0:
            return {'status': 'stored_more'}
        return {'status': 'empty'}

    def do_remove_last(self):
        """Remove the last UID and return the state matching the remaining list."""
        self.host.set_var('error_msg', '')
        uids = self._get_uid_list()
        if not uids:
            self.host.set_var('error_msg', self.host.tr('No UIDs to remove.'))
            self._update_uid_count()
            return {'status': 'empty'}

        # UIDs are stored sequentially, so removing the last item leaves no gaps.
        self.host.set_var('uid{}'.format(len(uids)), '')
        count = self._update_uid_count()

        # A previous write/verification no longer represents the current UID list.
        self.host.set_var('written_count', '0')
        self.host.set_var('written_block0', '')
        for i in range(1, 7):
            self.host.set_var('written_block{}'.format(i), '')

        if count == 0:
            self.host.set_var('last_uid', '')
            return {'status': 'empty'}
        if count >= 3:
            return {'status': 'stored_full'}
        return {'status': 'stored_more'}

