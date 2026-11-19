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

##########################################################################
# EMERGENCY BACKUP - MAIN PLUGIN (iCopy-X / iCopy-XS)
##########################################################################
# Purpose:
#   - Provides Delete Backup and Full SD Image UI flows.
#   - Shows paginated information, confirmation, progress, ETA and errors.
#   - Checks available UDUMP space before backup and during writing;
#     estimates compressed size and reserves 256 MiB as a safety margin.
#   - Reads the physical SD layout and copies the pre-UDUMP sectors,
#     including MBR/bootloader, p1 Boot, p2 RootFS and p3 Userdata.
#   - Rebuilds p4 UDUMP as a virtual FAT32 filesystem, excluding /backups,
#     so the output never contains its own in-progress backup.
#   - Streams one gzip RAW card image into FAT32-safe 2 GiB parts without
#     creating a second full-size image on the device.
#   - Stores each backup in a separate dated folder: DD.MM.YYYY HHhMMm;
#     includes README and Windows join scripts alongside the parts.
#   - Lists only recognized dated backup folders; after confirmation,
#     deletes the entire selected folder, not individual files.
#   - Handles cancellation and cleans up incomplete backup output.
# Dependencies: gzip_fast.py, fat32_virtual.py, UI/translation JSON files.
# Lab401 integration: expensive work uses run: callbacks; UI uses call:.
# System firmware files are not modified.
##########################################################################

# @copyright (2026) jareckib
import gzip
from gzip_fast import FastGzip
import zlib
from fat32_virtual import VirtualFAT32
import errno
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import stat
import struct
import tarfile
import textwrap
import threading
import time

UPAN_ROOT = '/mnt/upan'
BACKUP_ROOT = '/mnt/upan/backups/emergency_backup'
DISK = '/dev/mmcblk0'
PARTITIONS = (
    ('boot', '/dev/mmcblk0p1'),
    ('rootfs', '/dev/mmcblk0p2'),
    ('userdata', '/dev/mmcblk0p3'),
)
BLKGETSIZE64 = 0x80081272
CHUNK_SIZE = 1024 * 1024
MIN_FREE_MARGIN = 256 * 1024 * 1024
MAX_FAT_FILE = (4 * 1024 * 1024 * 1024) - 1
SPLIT_SIZE = 2 * 1024 * 1024 * 1024
MERGE_TOOLS = ('Combine_Backup.bat', 'Combine_Backup.ps1', 'README.txt')
PROGRESS_INTERVAL_SEC = 0.7
# Previous measured backup: 21m06s, plus 5s safety allowance.
ESTIMATED_BACKUP_SECONDS = 21 * 60 + 11


class BackupCancelled(Exception):
    pass


class IncompatibleSDCard(OSError):
    """Unsupported SD layout or FAT32 metadata; no image may be started."""


def _text(path, limit=65536):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(limit)
    except Exception:
        return ''


def _bytes(n):
    n = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return ('%d' if unit == 'B' else '%.1f') % n + unit
        n /= 1024


def _device_size(path):
    with open(path, 'rb', buffering=0) as f:
        try:
            result = fcntl.ioctl(f.fileno(), BLKGETSIZE64, b'\0' * 8)
            return struct.unpack('Q', result)[0]
        except OSError:
            pass
    value = _text('/sys/class/block/%s/size' % os.path.basename(path)).strip()
    if value.isdigit():
        return int(value) * 512
    size = os.stat(path).st_size
    if size > 0:
        return size
    raise OSError('Unknown device size: %s' % path)


def _partition_info(label, path):
    name = os.path.basename(path)
    start = _text('/sys/class/block/%s/start' % name).strip()
    size = _device_size(path)
    if not start.isdigit() or not size or size % 512:
        raise OSError('Cannot determine partition geometry: %s' % name)
    return {'label': label, 'device': path, 'start_sector': int(start),
            'size_bytes': size, 'size_sectors': size // 512}


def _add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = int(time.time())
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


class SplitImageWriter(object):
    """Gzip output sink split into <=2 GiB parts on FAT32.

    Each part is a .part file until the entire gzip stream was closed and
    fsynced successfully. A failed/cancelled run removes every partial part.
    """
    def __init__(self, filename, checkpoint):
        self.filename = filename
        self.checkpoint = checkpoint
        self.parts = []
        self.current = None
        self.current_size = 0
        self.total = 0
        self._open_next()

    def _open_next(self):
        if len(self.parts) >= 999:
            raise IOError('Too many backup parts')
        name = '%s.%03d' % (self.filename, len(self.parts) + 1)
        partial = name + '.part'
        if os.path.exists(name) or os.path.exists(partial):
            raise IOError('Backup part exists: %s' % name)
        self.current = open(partial, 'xb')
        self.current_size = 0
        self.parts.append((partial, name))

    def write(self, data):
        mv = memoryview(data)
        while len(mv):
            self.checkpoint()
            remaining = SPLIT_SIZE - self.current_size
            if remaining == 0:
                self._close_current()
                self._open_next()
                remaining = SPLIT_SIZE
            take = min(len(mv), remaining)
            self.current.write(mv[:take])
            self.current_size += take
            self.total += take
            mv = mv[take:]
            if self.total % (16*1024*1024) < take:
                self.checkpoint()
        return len(data)

    def flush(self):
        if self.current is not None:
            self.current.flush()

    def _close_current(self):
        if self.current is not None:
            self.current.flush()
            os.fsync(self.current.fileno())
            self.current.close()
            self.current = None

    def close(self):
        self._close_current()

    def commit(self):
        self.close()
        renamed = []
        try:
            for partial, name in self.parts:
                os.rename(partial, name)
                renamed.append(name)
        except Exception:
            for name in renamed:
                try: os.remove(name)
                except OSError: pass
            raise
        return [name for _, name in self.parts]

    def discard(self):
        if self.current is not None:
            try: self.current.close()
            except OSError: pass
            self.current = None
        for partial, name in self.parts:
            for path in (partial, name):
                try: os.remove(path)
                except OSError: pass


class _ProgressReader(object):
    def __init__(self, src, size, progress, digest):
        self.src = src
        self.remaining = size
        self.progress = progress
        self.digest = digest

    def read(self, requested=-1):
        if self.remaining == 0:
            return b''
        amount = min(CHUNK_SIZE, self.remaining)
        if requested >= 0:
            amount = min(amount, requested)
        data = self.src.read(amount)
        if not data:
            raise IOError('Unexpected end of source data')
        self.remaining -= len(data)
        self.digest.update(data)
        self.progress(len(data))
        return data


class RootFSBackupPlugin(object):
    """Preserves original class and framework entry point."""
    def __init__(self, host=None):
        self.host = host
        self._cancel = threading.Event()
        self._done = 0
        self._total = 1
        self._last_update = 0
        self._phase = ''
        self._output = None
        self._mount = None
        self._partial_file = None
        self._next_capacity_check = 64 * 1024 * 1024
        self._original_key_handler = None
        self._cancel_active = False
        self._wait_visible = True
        self._progress_percent = 0
        self._progress_info = 'Preparing...'
        self._pending_preflight = None
        self._writer = None
        self._last_capacity_bytes = 0
        self._eta_start = None
        self._backup_menu_selected = 0
        self._backup_items = []
        self._backup_selected = 0
        self._backup_to_delete = None

    # Dump Diff 2-style info pages: draw only within the content canvas area.
    # No RF or backup I/O is performed by these synchronous call: methods.
    _INFO_PAGES = (
        ('Back up the SD card.', 'Save all partitions.', 'Protect system files.', 'For 16 GB SD cards.'),
        ('SD cards may fail.', 'Bad edits harm SD.', 'Restore your iCopy.'),
        ('BOOT TIMEOUT error.', 'Use your own image.', 'Write to a spare SD.'),
        ('Full SD image.', 'All four partitions.', 'Ready for USBImager.'),
        ('P1: Boot (RAW).', 'P2: RootFS (RAW).', 'P3: Userdata (RAW).'),
        ('P4: UDUMP (FAT32).', 'Files copied first.', 'Backups are excluded.'),
        ('MBR and bootloader.', 'Sector layout saved.', 'Original disk size.'),
        ('2 GB .img.gz parts.', 'Saved on UDUMP.', 'Get files in PC mode.'),
        ('Copy all image parts.', 'Copy BAT and PS1 too.', 'Use one PC folder.'),
        ('Run Combine_Backup.', 'Double-click the BAT.', 'No 7-Zip needed.'),
        ('Check the final IMG.', 'Then use USBImager.', 'Use a spare microSD.'),
        ('Backup takes ~21 min.', 'Keep USB power on.', 'Do not turn off.'),
        ('Parts fit FAT32.', 'Check free space.'),
    )

    def _translate(self, value):
        """Use the firmware plugin localisation service (any installed language)."""
        if not isinstance(value, str) or not value:
            return value
        try:
            import resources
            language = str(resources.getLanguage()).lower().replace('_', '-').split('-', 1)[0]
            if not re.fullmatch(r'[a-z]{2,8}', language):
                return value
            if not hasattr(self, '_language_cache'):
                self._language_cache = {}
            if language not in self._language_cache:
                path = os.path.join(os.path.dirname(__file__), 'lang', language + '.json')
                try:
                    with open(path, 'r', encoding='utf-8') as stream:
                        pack = json.load(stream)
                    if not isinstance(pack, dict):
                        pack = {}
                except (OSError, ValueError, TypeError):
                    pack = {}
                self._language_cache[language] = pack
            pack = self._language_cache[language]
            # iCopy-X resolves plugin pack -> core pack -> English.
            def tr(text):
                return resources.tr_plugin(text, {language: pack})
            translated = tr(value)
            if translated != value:
                return translated
            # Dynamic diagnostics: translate known labels only; preserve values.
            for key in sorted(pack, key=len, reverse=True):
                if key.endswith(':') and value.startswith(key + ' '):
                    return tr(key) + ' ' + value[len(key) + 1:]
            return value
        except (ImportError, AttributeError, OSError, ValueError, TypeError):
            return value

    def _ui_later(self, cb, milliseconds=0):
        try:
            from lib import actstack
            root = actstack._root
            if root is not None:
                root.after(milliseconds, cb)
        except Exception:
            pass

    def _cancel_key_hook(self):
        # Plugin-local key interception: the framework suppresses normal keys
        # in busy run: states. No system firmware files are modified.
        if self._original_key_handler is not None or self.host is None:
            return
        from lib._constants import KEY_M1
        original = self.host.onKeyEvent
        self._original_key_handler = original
        def handler(key):
            if key == KEY_M1 and self._cancel_active:
                self._cancel.set()
                self._progress_info = 'Cancelling...'
                self._ui_later(self._draw_progress)
                return
            return original(key)
        self.host.onKeyEvent = handler

    def _restore_cancel_hook(self):
        if self._original_key_handler is not None and self.host is not None:
            self.host.onKeyEvent = self._original_key_handler
        self._original_key_handler = None

    def _draw_progress(self):
        if (self.host is None or
                getattr(self.host, '_current_state_id', '') != 'running'):
            return
        canvas = self.host.getCanvas()
        if canvas is None:
            return
        tag = '_emergency_progress'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        if self._wait_visible:
            canvas.create_text(134, 58, text=self._translate('WAIT...'), anchor='n',
                               fill='#1647D6', font=('Courier New',12,'bold'), tags=tag)
        # Separate the operation and the actual SD area/partition on two lines.
        # Keep WAIT, the fonts, the percentage and the green progress bar as before.
        phase = self._progress_info
        if phase.startswith(('p1 ', 'p2 ', 'p3 ')):
            operation, detail = 'Copying system', phase
        elif phase == 'p4 UDUMP':
            operation, detail = 'Building UDUMP', phase
        elif phase == 'MBR / Bootloader':
            operation, detail = 'Copying SD start', 'MBR + SD boot code'
        elif phase == 'SD system space':
            operation, detail = 'Copying system', 'Between partitions'
        elif phase == 'Padding image':
            operation, detail = 'Building SD image', phase
        elif phase in ('Closing gzip', 'Saving parts', 'Backup ready'):
            operation, detail = 'Finalizing backup', phase
        else:
            operation, detail = 'Creating SD image', phase
        canvas.create_text(120, 80, text=self._translate(operation)[:21],
                           anchor='n', fill='#777777', font=('Courier New',12), tags=tag)
        canvas.create_text(120, 103, text=self._translate(detail)[:21],
                           anchor='n', fill='#777777', font=('Courier New',12), tags=tag)
        canvas.create_text(120, 131, text='%d%%' % self._progress_percent,
                           anchor='n', fill='#1647D6', font=('Courier New',12,'bold'), tags=tag)
        canvas.create_rectangle(15, 156, 225, 168, fill='#dddddd', outline='#777777', tags=tag)
        width = int(208 * max(0,min(100,self._progress_percent))/100.0)
        if width:
            canvas.create_rectangle(16,157,16+width,167,fill='#20A750',outline='',tags=tag)
        # The countdown and bar use the same time-based estimate.
        elapsed = max(0, time.monotonic() - self._eta_start) if self._eta_start is not None else 0
        seconds_left = max(0, ESTIMATED_BACKUP_SECONDS - int(elapsed))
        left_text = '%s %02d:%02d' % (self._translate('Est. left:'),
                                       seconds_left // 60, seconds_left % 60)
        canvas.create_text(120, 179, text=left_text, anchor='n',
                           fill='#777777', font=('Courier New', 12), tags=tag)

    def draw_backup_done(self):
        """Large readable completion text without altering firmware UI widgets."""
        if self.host is None:
            return
        canvas = self.host.getCanvas()
        if canvas is None:
            return
        tag = '_emergency_done'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        # Result layout fits four 12px Courier lines within the content area.
        lines = [
            self._translate('Backup completed!'),
            self._translate('Saved parts:') + ' %d' % getattr(self, '_saved_parts', 0),
            self._translate('Total:') + ' ' + _bytes(getattr(self, '_saved_bytes', 0)),
            self._translate('Copy parts to PC'),
            self._translate('Run Combine_Backup.bat'),
            self._translate('Write with USBImager'),
        ]
        for i, line in enumerate(lines):
            canvas.create_text(8, 56 + i*23, text=line,
                               anchor='nw', fill='#1647D6' if i == 0 else '#777777',
                               font=('Courier New', 12, 'bold') if i == 0 else ('Courier New', 12),
                               tags=tag)

    def draw_backup_cancelled(self):
        """Show cancellation and cleanup messages in readable 12px text.

        The framework screen contains no small default text; this overlay
        draws the translated result below the unchanged title bar.
        """
        if self.host is None:
            return
        canvas = self.host.getCanvas()
        if canvas is None:
            return
        tag = '_emergency_cancelled'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        messages = (self._translate('Backup cancelled.'),
                    self._translate('Incomplete parts removed.'))
        lines = []
        for message in messages:
            lines.extend(textwrap.wrap(message, width=20,
                                       break_long_words=True,
                                       break_on_hyphens=False) or [''])
        first_y = 109 - ((len(lines) - 1) * 23 // 2)
        for i, line in enumerate(lines):
            canvas.create_text(120, first_y + i * 23, text=line,
                               anchor='n', fill='#C00000',
                               font=('Courier New', 12), tags=tag)

    def clear_backup_cancelled(self):
        if self.host is not None:
            canvas = self.host.getCanvas()
            if canvas is not None:
                canvas.delete('_emergency_cancelled')

    def clear_backup_done(self):
        if self.host is not None:
            canvas = self.host.getCanvas()
            if canvas is not None:
                canvas.delete('_emergency_done')

    def _update_timed_percent(self):
        """Estimate progress by elapsed time; reserve 99/100 for finalization.

        The estimate can reach 98% before I/O completes. It must never
        imply that a backup succeeded until writer.commit() finishes.
        """
        if self._eta_start is None or self._progress_percent >= 99:
            return
        elapsed = max(0.0, time.monotonic() - self._eta_start)
        self._progress_percent = min(98, int(98 * elapsed / ESTIMATED_BACKUP_SECONDS))

    def _blink_progress(self):
        if self.host is None or not self._cancel_active:
            return
        if getattr(self.host, '_current_state_id', '') != 'running':
            return
        self._wait_visible = not self._wait_visible
        self._update_timed_percent()
        self._draw_progress()
        self._ui_later(self._blink_progress, 600)

    def _preflight_estimate(self, p4_start, fat):
        """Conservative estimate; UDUMP is ONLY occupied file contents.

        Sample raw boot/system bytes for a gzip compression estimate. Assume
        UDUMP files are incompressible (upper-bound), plus FAT/gzip overhead.
        This is an estimate; streaming guard remains mandatory.
        """
        sample_bytes = 0
        compressed = 0
        block = 256 * 1024
        step = 32 * 1024 * 1024
        with open(DISK, 'rb', buffering=0) as src:
            for offset in range(0, p4_start, step):
                self._check_cancel()
                src.seek(offset)
                data = src.read(min(block, p4_start-offset))
                if not data:
                    raise IOError('Cannot sample raw SD sectors')
                sample_bytes += len(data)
                compressed += len(zlib.compress(data, 1))
        # margin for samples missing less-compressible sections
        raw_est = int((compressed / float(max(sample_bytes,1))) * p4_start * 1.35)
        occupied = sum(node.size for node in fat.nodes if not node.directory)
        # Compression of zero-filled free FAT32 space is negligible; reserve
        # extra space for FAT metadata, compressed stream and unusual files.
        return raw_est + occupied + (128*1024*1024), occupied

    def do_preflight(self):
        """Runs through run:, never from synchronous UI action."""
        self._ui_later(lambda: self._draw_scanning('preflight'))
        try:
            mount = self._mounted_udump()
            if mount['fstype'].lower() not in ('vfat','fat32','fat','msdos'):
                raise IncompatibleSDCard('UDUMP must be FAT32')
            layout, _head = self._disk_layout(mount)
            p4 = layout['partitions'][3]
            with open(p4['device'],'rb',buffering=0) as fd:
                boot_sector = fd.read(512)
            self._validate_udump_fat32(boot_sector, p4)
            fat = VirtualFAT32(UPAN_ROOT,os.path.join(UPAN_ROOT,'backups'),
                               boot_sector,p4['size_sectors'],p4['start_sector'])
            est, occupied = self._preflight_estimate(p4['start_sector']*512,fat)
            free = shutil.disk_usage(UPAN_ROOT).free
            # never allocate a second full final file: .part is renamed
            allowed = max(0,free-MIN_FREE_MARGIN)
            self._space_text = ('%s %s\n%s %s\n%s %s\n%s' %
                                (self._translate('UDUMP used:'), _bytes(occupied),
                                 self._translate('IMG est:'), _bytes(est),
                                 self._translate('Free:'), _bytes(free),
                                 self._translate('Parts: 2 GB each')))
            self.host.set_var('space_text', self._space_text)
            if est > allowed:
                self._last_space_error = ('%s\n%s %s\n%s %s' %
                    (self._translate('Not enough space'),
                     self._translate('Estimated:'), _bytes(est),
                     self._translate('Available:'), _bytes(allowed)))
                self.host.set_var('space_error', self._last_space_error)
                return {'status':'no_space'}
            return {'status':'ok'}
        except IncompatibleSDCard as exc:
            self._last_space_error = str(exc)
            self.host.set_var('space_error', str(exc))
            return {'status': 'incompatible'}
        except Exception as exc:
            self._last_space_error = str(exc)
            self.host.set_var('space_error', str(exc))
            return {'status': 'no_space'}

    def _draw_error_large(self, message):
        canvas = self.host.getCanvas() if self.host is not None else None
        if canvas is None:
            return
        tag = '_emergency_error_large'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        lines = []
        for paragraph in [self._translate(part) for part in message.split('\n')]:
            lines.extend(textwrap.wrap(paragraph, width=20,
                                       break_long_words=True,
                                       break_on_hyphens=False) or [''])
        for i, line in enumerate(lines[:7]):
            canvas.create_text(9, 60 + i*19, text=line, anchor='nw',
                               fill='#D52C2C', font=('Courier New', 12, 'bold'),
                               tags=tag)

    def draw_backup_error_large(self):
        self._draw_error_large(getattr(self, '_last_error_msg', 'Backup error'))
        self._ui_later(lambda: self._draw_error_large(
            getattr(self, '_last_error_msg', 'Backup error')), 160)

    def draw_space_error_large(self):
        self._draw_error_large(getattr(self, '_last_space_error', 'Not enough space'))
        self._ui_later(lambda: self._draw_error_large(
            getattr(self, '_last_space_error', 'Not enough space')), 160)

    def draw_no_backups_large(self):
        # Center the empty-list message in the available body canvas.
        self._draw_center_status('No backups found', '#D52C2C')
        self._ui_later(lambda: self._draw_center_status('No backups found', '#D52C2C'), 160)

    def _draw_center_status(self, message, color='#777777', tag='_emergency_error_large'):
        canvas = self.host.getCanvas() if self.host is not None else None
        if canvas is None:
            return
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        canvas.create_text(120, 124, text=self._translate(message), anchor='center',
                           fill=color, font=('Courier New', 12, 'bold'), tags=tag)

    def _draw_scanning(self, state_id):
        # Avoid delayed UI work painting over the next screen.
        if getattr(self.host, '_current_state_id', None) != state_id:
            return
        self._draw_center_status('Scanning...', '#1647D6', '_emergency_scanning')

    def _draw_space_summary(self):
        canvas = self.host.getCanvas() if self.host is not None else None
        if canvas is None:
            return
        tag = '_emergency_space_summary'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        value = getattr(self, '_space_text', '')
        for i, line in enumerate(value.splitlines()[:5]):
            canvas.create_text(9, 88 + 19*i, text=self._translate(line), anchor='nw',
                               fill='#777777', font=('Courier New', 12), tags=tag)

    def draw_space_summary(self):
        self._draw_space_summary()
        self._ui_later(self._draw_space_summary, 160)

    def clear_space_summary(self):
        if self.host is not None:
            canvas = self.host.getCanvas()
            if canvas is not None:
                canvas.delete('_emergency_space_summary')

    def clear_error_large(self):
        if self.host is not None:
            canvas = self.host.getCanvas()
            if canvas is not None:
                canvas.delete('_emergency_error_large')

    def _draw_menu(self, selected):
        canvas = self.host.getCanvas()
        if canvas is None:
            return
        tag = '_emergency_menu'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        for i, title in enumerate(('Delete Backup', 'Full SD Image')):
            y = 76 + i * 42
            if i == selected:
                canvas.create_rectangle(9, y-5, 231, y+25, fill='#20A750',
                                        outline='', tags=tag)
            canvas.create_text(18, y, text=self._translate(title), anchor='nw',
                               fill='white' if i == selected else '#1647D6',
                               font=('Courier New', 14), tags=tag)
        # Two text-only instructions above the firmware footer (10 px).
        # The menu retains UP/DOWN navigation; no arrow glyphs are used here.
        canvas.create_text(120, 175, text=self._translate('Up/Down - Select'),
                           anchor='center', fill='#1647D6',
                           font=('Courier New', 10), tags=tag)
        canvas.create_text(120, 190, text=self._translate('OK - Confirm'),
                           anchor='center', fill='#1647D6',
                           font=('Courier New', 10), tags=tag)

    def draw_menu_delete(self):
        self._cancel_key_hook()
        self._backup_menu_selected = 0
        self._draw_menu(0)
        self._ui_later(lambda: self._draw_menu(0), 160)

    def draw_menu_backup(self):
        self._cancel_key_hook()
        self._backup_menu_selected = 1
        self._draw_menu(1)
        self._ui_later(lambda: self._draw_menu(1), 160)

    def clear_menu(self):
        canvas = self.host.getCanvas()
        if canvas is not None:
            canvas.delete('_emergency_menu')

    _BACKUP_PART_RE = re.compile(r'^(icopyx-emergency-\d{8}_\d{6}\.img\.gz)\.(\d{3})$')

    _BACKUP_FOLDER_RE = re.compile(r'^\d{2}\.\d{2}\.\d{4} \d{2}h\d{2}m(?:-\d{2})?$')

    def _list_backup_groups(self):
        """List completed dated backup folders only; ignore old flat backups."""
        if not os.path.isdir(BACKUP_ROOT):
            return []
        items = []
        with os.scandir(BACKUP_ROOT) as entries:
            for ent in entries:
                if (ent.is_symlink() or not ent.is_dir(follow_symlinks=False)
                        or not self._BACKUP_FOLDER_RE.fullmatch(ent.name)):
                    continue
                parts = []
                with os.scandir(ent.path) as contents:
                    for child in contents:
                        match = self._BACKUP_PART_RE.fullmatch(child.name)
                        if (match and child.is_file(follow_symlinks=False)
                                and not child.is_symlink()):
                            parts.append((int(match.group(2)), child.name,
                                          child.stat(follow_symlinks=False).st_size,
                                          match.group(1)))
                parts.sort()
                if (parts and [x[0] for x in parts] == list(range(1, len(parts)+1))
                        and len({x[3] for x in parts}) == 1):
                    items.append({'stem': ent.name, 'folder': ent.name,
                                  'parts': [x[1] for x in parts],
                                  'size': sum(x[2] for x in parts)})
        return sorted(items, key=lambda item:
                      item['stem'][6:10]+item['stem'][3:5]+item['stem'][:2]
                      +item['stem'][11:13]+item['stem'][14:16], reverse=True)

    def _display_backup_date(self, item):
        return item['folder']

    def scan_backups(self):
        self._ui_later(lambda: self._draw_scanning('delete_scan'))
        try:
            self._mounted_udump()
            self._backup_items = self._list_backup_groups()
            self._backup_selected = 0
            return {'status': 'found' if self._backup_items else 'empty'}
        except Exception as exc:
            self._last_error_msg = str(exc)
            self.host.set_var('error_msg', str(exc))
            return {'status': 'error'}

    def _draw_delete_list(self):
        canvas = self.host.getCanvas()
        if canvas is None:
            return
        tag = '_emergency_delete_list'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        items = self._backup_items
        if not items:
            return
        per_page = 3
        page = self._backup_selected // per_page
        first = page * per_page
        for local_idx, item in enumerate(items[first:first+per_page]):
            y = 59 + local_idx * 38
            selected = first + local_idx == self._backup_selected
            if selected:
                canvas.create_rectangle(5, y-2, 234, y+34,
                                        fill='#20A750', outline='', tags=tag)
            label = self._display_backup_date(item)
            color = 'white' if selected else '#777777'
            canvas.create_text(10, y, text=label, anchor='nw', fill=color,
                               font=('Courier New', 12), tags=tag)
            detail = '%s  %d %s' % (_bytes(item['size']), len(item['parts']),
                                    self._translate('part(s)'))
            canvas.create_text(10, y+18, text=detail[:23], anchor='nw', fill=color,
                               font=('Courier New', 12), tags=tag)
        if page > 0:
            canvas.create_text(233, 52, text='▲', anchor='ne', fill='#1647D6',
                               font=('Arial', 9), tags=tag)
        if (page + 1) * per_page < len(items):
            canvas.create_text(233, 179, text='▼', anchor='se', fill='#1647D6',
                               font=('Arial', 9), tags=tag)
        total_pages = (len(items)+per_page-1)//per_page
        canvas.create_text(120, 191, text=self._translate('Page') + ' %d/%d' %
                           (page+1, total_pages), anchor='center', fill='#1647D6',
                           font=('Courier New', 10), tags=tag)

    def draw_delete_list(self):
        self._draw_delete_list()
        self._ui_later(self._draw_delete_list, 160)

    def delete_up(self):
        self._backup_selected = max(0, self._backup_selected-1)
        self._draw_delete_list()

    def delete_down(self):
        self._backup_selected = min(len(self._backup_items)-1,
                                    self._backup_selected+1)
        self._draw_delete_list()

    def clear_delete_list(self):
        canvas = self.host.getCanvas()
        if canvas is not None:
            canvas.delete('_emergency_delete_list')

    def draw_delete_confirm(self):
        if not self._backup_items:
            return
        item = self._backup_items[self._backup_selected]
        canvas = self.host.getCanvas()
        self._backup_to_delete = {'stem': item['stem'],
                                  'folder': item['folder'],
                                  'parts': list(item['parts']),
                                  'size': item['size']}
        if canvas is None:
            return
        tag = '_emergency_delete_confirm'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        date_label = self._display_backup_date(item)
        date, clock = date_label.split(' ', 1)
        lines = [self._translate('Delete this backup?'),
                 date, clock,
                 '%s: %s' % (self._translate('Size'), _bytes(item['size'])),
                 self._translate('Cannot be undone!')]
        for i, line in enumerate(lines):
            canvas.create_text(10, 63+i*24, text=line[:22], anchor='nw',
                               fill='#D52C2C' if i in (0,4) else '#777777',
                               font=('Courier New', 12), tags=tag)

    def clear_delete_confirm(self):
        canvas = self.host.getCanvas()
        if canvas is not None:
            canvas.delete('_emergency_delete_confirm')

    def _draw_deleting_status(self):
        # Progress indicator for folder deletion, using the standard 12px font.
        if getattr(self.host, '_current_state_id', None) != 'deleting':
            return
        self._draw_center_status('Deleting...', '#1647D6', '_emergency_deleting')

    def draw_delete_done(self):
        """Draw successful deletion in Courier New 12px, not firmware default."""
        canvas = self.host.getCanvas() if self.host is not None else None
        if canvas is None:
            return
        tag = '_emergency_delete_done'
        canvas.delete(tag)
        canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
        message = getattr(self, '_delete_result_text', self._translate('Backup deleted'))
        for i, line in enumerate(message.splitlines()[:5]):
            canvas.create_text(120, 104 + i * 23, text=line, anchor='center',
                               fill='#1647D6' if i == 0 else '#777777',
                               font=('Courier New', 12), tags=tag)

    def clear_delete_done(self):
        canvas = self.host.getCanvas() if self.host is not None else None
        if canvas is not None:
            canvas.delete('_emergency_delete_done')

    def do_delete_backup(self):
        # run: only; delete only the folder selected and verified beforehand.
        self._ui_later(self._draw_deleting_status)
        try:
            self._mounted_udump()
            selected = self._backup_to_delete
            if not selected:
                raise OSError('No backup selected')
            available = {(item['stem'], item['folder']): item
                         for item in self._list_backup_groups()}
            actual = available.get((selected['stem'], selected['folder']))
            if actual is None or actual['parts'] != selected['parts']:
                raise OSError('Backup changed; select it again')
            folder = selected['folder']
            if not folder or not self._BACKUP_FOLDER_RE.fullmatch(folder):
                raise OSError('Invalid backup folder')
            path = os.path.join(BACKUP_ROOT, folder)
            if os.path.islink(path) or not os.path.isdir(path):
                raise OSError('Invalid backup directory')
            # Delete the complete dated folder. Never enter subfolders in the UI.
            # shutil.rmtree does not follow directory symlinks.
            shutil.rmtree(path)
            self._delete_result_text = '%s\n%s' % (
                self._translate('Backup deleted'), _bytes(selected['size']))
            self.host.set_var('delete_result', self._delete_result_text)
            return {'status': 'done'}
        except Exception as exc:
            self._last_error_msg = str(exc)
            self.host.set_var('error_msg', str(exc))
            return {'status': 'error'}

    def _draw_info_page(self, index):
        """Match Dump Diff 2 paging coordinates, typography and arrow placement."""
        canvas = self.host.getCanvas()
        if canvas is None:
            return
        tag = '_full_sd_info'
        canvas.delete(tag)
        # The firmware owns the title bar (y<49) and hardware-button footer.
        canvas.create_rectangle(0, 49, 239, 200, fill='white',
                                outline='', tags=tag)
        # 23 physical character cells: one left margin, up to 21
        # content characters, and at least one right margin.
        # Keep WAIT/progress screens unchanged; page indicator uses 10px.
        lines = []
        for original in self._INFO_PAGES[index]:
            translated = self._translate(original).strip()
            if not translated:
                lines.append(' ')
                continue
            for segment in textwrap.wrap(translated, width=21,
                                         break_long_words=True,
                                         break_on_hyphens=False):
                lines.append(' ' + segment)
        blue = '#1647D6'
        gray = '#777777'
        face = ('Courier New', 12)
        y = 82 if len(lines) <= 3 else 65
        for line in lines:
            canvas.create_text(8, y, text=line, anchor='nw',
                               fill=gray, font=face, tags=tag)
            y += 19
        if index > 0:
            canvas.create_text(235, 43, text='▲', anchor='ne',
                               fill=blue, font=('Arial', 9), tags=tag)
        if index + 1 < len(self._INFO_PAGES):
            canvas.create_text(235, 198, text='▼', anchor='se',
                               fill=blue, font=('Arial', 9), tags=tag)
        # Hardware OK hint is separate from content and sits above Page N/N.
        # All informational lines use <=21 content characters + left margin.
        canvas.create_text(120, 171,
                           text=self._translate('OK - Start backup'),
                           anchor='center', fill=blue,
                           font=('Courier New', 10), tags=tag)
        canvas.create_text(120, 190,
                           text=self._translate('Page') + ' {}/{}'.format(index + 1, len(self._INFO_PAGES)),
                           anchor='center', fill=blue,
                           font=('Courier New', 10), tags=tag)

    def clear_info_screen(self):
        canvas = self.host.getCanvas()
        if canvas is not None:
            canvas.delete('_full_sd_info')

    def draw_info_1(self):
        self._draw_info_page(0)

    def draw_info_2(self):
        self._draw_info_page(1)

    def draw_info_3(self):
        self._draw_info_page(2)

    def draw_info_4(self):
        self._draw_info_page(3)

    def draw_info_5(self):
        self._draw_info_page(4)

    def draw_info_6(self):
        self._draw_info_page(5)

    def draw_info_7(self):
        self._draw_info_page(6)

    def draw_info_8(self):
        self._draw_info_page(7)

    def draw_info_9(self):
        self._draw_info_page(8)

    def draw_info_10(self):
        self._draw_info_page(9)

    def draw_info_11(self):
        self._draw_info_page(10)

    def draw_info_12(self):
        self._draw_info_page(11)

    def draw_info_13(self):
        self._draw_info_page(12)

    def on_destroy(self):
        self._cancel.set()
        self._cancel_active = False
        self._restore_cancel_hook()

    def request_cancel(self):
        self._cancel.set()

    def _check_cancel(self):
        if self._cancel.is_set():
            raise BackupCancelled()

    def _progress(self, count):
        self._done += count
        if self._writer and self._writer.total >= self._last_capacity_bytes + 16 * 1024 * 1024:
            self._ensure_capacity(self._writer, self._mount)
            self._last_capacity_bytes = self._writer.total
        now = time.time()
        if now - self._last_update > PROGRESS_INTERVAL_SEC or self._done >= self._total:
            self._last_update = now
            self._update_timed_percent()
            self._progress_info = self._phase
            self._ui_later(self._draw_progress)
        self._check_cancel()

    def _scan_udump(self):
        """Snapshot file listing; NEVER include /mnt/upan/backups (no recursion)."""
        entries = []
        total = 0
        for base, dirs, files in os.walk(UPAN_ROOT, topdown=True, followlinks=False):
            self._check_cancel()
            dirs[:] = sorted(d for d in dirs
                             if not (base == UPAN_ROOT and d == 'backups')
                             and not os.path.islink(os.path.join(base, d)))
            relbase = os.path.relpath(base, UPAN_ROOT)
            if relbase != '.':
                entries.append((base, True))
            for filename in sorted(files):
                full = os.path.join(base, filename)
                try:
                    st = os.lstat(full)
                except OSError:
                    raise IOError('Cannot inspect UDUMP file: %s' % full)
                if stat.S_ISREG(st.st_mode):
                    entries.append((full, False))
                    total += st.st_size
                elif stat.S_ISLNK(st.st_mode):
                    raise IOError('UDUMP symlinks unsupported: %s' % full)
        return entries, total

    def _mounted_udump(self):
        # Require the destination to be an actual mount, not a folder on rootfs.
        if not os.path.ismount(UPAN_ROOT):
            raise OSError('/mnt/upan is not mounted: refusing backup')
        for line in _text('/proc/mounts').splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == UPAN_ROOT:
                return {'device': parts[0], 'fstype': parts[2]}
        return {'device': '?', 'fstype': '?'}

    def _validate_udump_fat32(self, boot_sector, p4):
        """Check source FAT32 BPB before constructing a virtual UDUMP image.

        This inspects only the source boot sector and never modifies the SD.
        The virtual FAT32 generator has its own capacity/file checks.
        """
        if len(boot_sector) != 512 or boot_sector[510:512] != b'\x55\xaa':
            raise IncompatibleSDCard('Invalid UDUMP FAT32 boot sector')
        bytes_per_sector = struct.unpack_from('<H', boot_sector, 11)[0]
        sectors_per_cluster = boot_sector[13]
        reserved = struct.unpack_from('<H', boot_sector, 14)[0]
        fat_count = boot_sector[16]
        root_entries = struct.unpack_from('<H', boot_sector, 17)[0]
        sectors_per_fat = struct.unpack_from('<I', boot_sector, 36)[0]
        fat16_sectors = struct.unpack_from('<H', boot_sector, 22)[0]
        root_cluster = struct.unpack_from('<I', boot_sector, 44)[0]
        if (bytes_per_sector != 512 or sectors_per_cluster == 0 or
                sectors_per_cluster & (sectors_per_cluster - 1) or
                sectors_per_cluster > 128 or reserved == 0 or
                fat_count not in (1, 2) or root_entries != 0 or
                fat16_sectors != 0 or sectors_per_fat == 0 or
                root_cluster < 2):
            raise IncompatibleSDCard('Unsupported UDUMP FAT32 format')
        total16 = struct.unpack_from('<H', boot_sector, 19)[0]
        total32 = struct.unpack_from('<I', boot_sector, 32)[0]
        total = total16 or total32
        if (total == 0 or total > p4['size_sectors'] or
                reserved + fat_count * sectors_per_fat >= total):
            raise IncompatibleSDCard('Invalid UDUMP FAT32 size')

    def _validate_partition_table(self, header, partitions, disk_size):
        """Verify the on-card MBR geometry matches Linux block geometry.

        Do not enforce one manufacturer's fixed offsets or partition sizes.
        """
        if len(header) < 512 or header[510:512] != b'\x55\xaa':
            raise IncompatibleSDCard('Invalid SD partition table')
        if disk_size <= 0 or disk_size % 512:
            raise IncompatibleSDCard('Invalid SD capacity')
        # This image writer supports four primary MBR entries, not GPT/extended.
        for i, part in enumerate(partitions):
            entry = header[446 + 16*i:446 + 16*(i+1)]
            kind = entry[4]
            start, size = struct.unpack_from('<II', entry, 8)
            if (kind in (0, 0x05, 0x0f, 0x85, 0xee) or
                    start != part['start_sector'] or
                    size != part['size_sectors']):
                raise IncompatibleSDCard('Unsupported partition P%d' % (i + 1))
        ordered = sorted(partitions, key=lambda part: part['start_sector'])
        previous_end = 1
        for part in ordered:
            start = part['start_sector']
            end = start + part['size_sectors']
            if start < previous_end or end > disk_size // 512 or end <= start:
                raise IncompatibleSDCard('Invalid SD partition geometry')
            previous_end = end
        # The image generator streams all bytes before P4 as raw sectors.
        if ordered[-1]['label'] != 'udump':
            raise IncompatibleSDCard('Unsupported UDUMP placement')
        # Detect additional partitions not represented in the image.
        extra = [name for name in os.listdir('/sys/class/block')
                 if re.fullmatch(r'mmcblk0p[5-9][0-9]*', name)]
        if extra:
            raise IncompatibleSDCard('Extra SD partitions found')

    def _disk_layout(self, mount):
        if not os.path.exists(DISK):
            raise OSError('Missing disk %s' % DISK)
        disk_size = _device_size(DISK)
        infos = [_partition_info(label, path) for label, path in PARTITIONS]
        p4 = _partition_info('udump', '/dev/mmcblk0p4')
        if mount['device'] not in ('/dev/mmcblk0p4', '/dev/root') and not mount['device'].endswith('/mmcblk0p4'):
            raise OSError('UDUMP mount is not mmcblk0p4: %s' % mount['device'])
        infos.append(p4)
        first_sector = min(p['start_sector'] for p in infos)
        head_size = min(1024 * 1024, first_sector * 512)
        if head_size < 512:
            raise OSError('No space to capture disk partition table')
        if max(p['start_sector'] + p['size_sectors'] for p in infos) * 512 > disk_size:
            raise OSError('Partition extends beyond disk')
        with open(DISK, 'rb', buffering=0) as disk:
            head = disk.read(head_size)
        if len(head) != head_size:
            raise IOError('Cannot read disk header')
        self._validate_partition_table(head, infos, disk_size)
        layout = {'format': 'icopy-full-sd-v1', 'disk': DISK, 'disk_size_bytes': disk_size,
                  'sector_size': 512, 'partitions': infos, 'udump_mount': mount,
                  'disk_header_bytes': len(head), 'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                  'udump_excluded': ['/backups'], 'warning': 'Not a sector-exact snapshot of p4.'}
        return layout, head

    def _ensure_capacity(self, writer, mount):
        free = shutil.disk_usage(UPAN_ROOT).free
        if free < MIN_FREE_MARGIN:
            raise OSError('UDUMP space low; stopped safely')
        if writer.current_size > SPLIT_SIZE:
            raise OSError('Internal error: backup part exceeds 2 GiB')

    def _check_write_capacity(self):
        self._check_cancel()
        writer = self._writer
        if writer and writer.total >= self._last_capacity_bytes + 16*1024*1024:
            self._ensure_capacity(writer, self._mount)
            self._last_capacity_bytes = writer.total

    def _install_merge_tools(self, target_dir):
        # The tools remain alongside the backups and can be copied in PC Mode.
        for name in MERGE_TOOLS:
            source = os.path.join(os.path.dirname(__file__), name)
            destination = os.path.join(target_dir, name)
            with open(source, 'rb') as f:
                data = f.read()
            with open(destination + '.tmp', 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.rename(destination + '.tmp', destination)

    def do_backup(self):
        """Create bootable full-card gzip split into 2-GiB FAT32-safe parts.

        Copy all numbered parts plus BAT and PS1 from the UDUMP backup folder
        to one Windows folder, run BAT, then flash merged IMG.GZ on a spare SD.
        """
        self._cancel.clear()
        self._cancel_active = True
        self._wait_visible = True
        self._progress_percent = 0
        self._progress_info = 'Preparing...'
        self._eta_start = time.monotonic()
        self._ui_later(self._blink_progress, 150)
        self.host.set_var('error_msg', '')
        self.host.set_var('result_text', '')
        self.host.set_progress(0, 'Preparing image...')
        writer = None
        completed = False
        backup_dir = None
        self._phase = 'Preparing image'
        try:
            os.makedirs(BACKUP_ROOT, exist_ok=True)
            stamp = time.strftime('%Y%m%d_%H%M%S')
            folder_stamp = time.strftime('%d.%m.%Y %Hh%Mm')
            mount = self._mounted_udump()
            if mount['fstype'].lower() not in ('vfat', 'fat32', 'fat', 'msdos'):
                raise IncompatibleSDCard('UDUMP must be FAT32')
            layout, _ = self._disk_layout(mount)
            disk_bytes = layout['disk_size_bytes']
            p4 = layout['partitions'][3]
            p4_start = p4['start_sector'] * 512
            p4_bytes = p4['size_bytes']
            if p4_start + p4_bytes > disk_bytes:
                raise OSError('UDUMP is beyond disk end')
            if shutil.disk_usage(UPAN_ROOT).free < MIN_FREE_MARGIN:
                raise OSError('Not enough space on UDUMP')
            with open(p4['device'], 'rb', buffering=0) as src:
                boot_sector = src.read(512)
            self._phase = 'Indexing UDUMP'
            self._progress_info = self._phase
            self._ui_later(self._draw_progress)
            self._validate_udump_fat32(boot_sector, p4)
            fat = VirtualFAT32(UPAN_ROOT, os.path.join(UPAN_ROOT, 'backups'),
                               boot_sector, p4['size_sectors'], p4['start_sector'])
            self._done, self._total, self._last_update = 0, disk_bytes, 0
            self._last_capacity_bytes = 0
            self._phase = 'MBR / Bootloader'
            backup_dir = os.path.join(BACKUP_ROOT, folder_stamp)
            # If two backups begin in the same minute, do not mix their files.
            if os.path.exists(backup_dir):
                backup_dir = os.path.join(BACKUP_ROOT, folder_stamp + '-%02d' % int(stamp[-2:]))
            os.mkdir(backup_dir)
            self._install_merge_tools(backup_dir)
            filename = os.path.join(backup_dir, 'icopyx-emergency-%s.img.gz' % stamp)
            writer = SplitImageWriter(filename, self._check_write_capacity)
            self._writer, self._mount = writer, mount
            try:
                os.sync()
            except Exception:
                pass
            with FastGzip(writer, level=1) as gz:
                # Use the actual partition geometry. Gaps between partitions
                # are part of the full disk image too (including the MBR and
                # bootloader before p1). Do not modify the progress screen UI.
                regions = []
                for idx, part in enumerate(layout['partitions'][:3], 1):
                    start = part['start_sector'] * 512
                    end = start + part['size_bytes']
                    regions.append((start, end, 'p%d %s' % (
                        idx, {'boot': 'Boot', 'rootfs': 'RootFS',
                              'userdata': 'Userdata'}.get(part['label'].lower(),
                                                          part['label']))))
                with open(DISK, 'rb', buffering=0) as disk:
                    offset = 0
                    remaining = p4_start
                    while remaining:
                        self._check_cancel()
                        phase = 'MBR / Bootloader' if offset < regions[0][0] else 'SD system space'
                        for start, end, name in regions:
                            if start <= offset < end:
                                phase = name
                                break
                        if phase != self._phase:
                            self._phase = phase
                            self._progress_info = phase
                            self._ui_later(self._draw_progress)
                        block = disk.read(min(CHUNK_SIZE, remaining))
                        if not block:
                            raise IOError('Premature disk read: %s' % DISK)
                        gz.write(block)
                        offset += len(block)
                        remaining -= len(block)
                        self._progress(len(block))
                self._phase = 'p4 UDUMP'
                self._progress_info = self._phase
                self._ui_later(self._draw_progress)
                for block, length in fat.stream_regions(CHUNK_SIZE):
                    self._check_cancel()
                    if block is None:
                        gz.write_zeros(length, self._progress)
                    else:
                        gz.write(block)
                        self._progress(length)
                remaining = disk_bytes - p4_start - p4_bytes
                self._phase = 'Padding image'
                if remaining:
                    gz.write_zeros(remaining, self._progress)
                self._phase = 'Closing gzip'
                self._progress_percent = 99
                self._progress_info = 'Closing gzip'
                self._ui_later(self._draw_progress)
            self._check_cancel()
            self._phase = 'Saving parts'
            self._progress_info = 'Saving parts'
            self._ui_later(self._draw_progress)
            writer.close()  # fsync the last part before marking anything ready
            self._check_cancel()
            filenames = writer.commit()
            completed = True
            self._phase = 'Backup ready'
            self._progress_percent = 100
            self._progress_info = 'Backup ready'
            self._ui_later(self._draw_progress)
            self._saved_parts = len(filenames)
            self._saved_bytes = writer.total
            self.host.set_var('result_text', '%s %d %s\n%s %s\n%s\n%s' % (
                self._translate('Saved'), len(filenames), self._translate('part(s)'),
                _bytes(writer.total), self._translate('total'),
                self._translate('Copy BAT + PS1 + parts'),
                self._translate('Use USBImager after join')))
            return {'status': 'done'}
        except BackupCancelled:
            self.host.set_var('result_text', self._translate('Backup cancelled.') + '\n' +
                              self._translate('Incomplete parts removed.'))
            return {'status': 'cancelled'}
        except Exception as exc:
            self._last_error_msg = str(exc)
            self.host.set_var('error_msg', str(exc))
            return {'status': 'error'}
        finally:
            self._cancel_active = False
            self._writer = None
            self._mount = None
            if writer is not None and not completed:
                writer.discard()
            if backup_dir and not completed:
                # Clean only this run's newly created directory.
                try:
                    shutil.rmtree(backup_dir)
                except OSError:
                    pass
