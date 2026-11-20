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

"""MIFARE Classic Fix plugin for iCopy-X/XS.
Copyright (c) 2026: jareckib

Detect and repair writable-UID MIFARE Classic Magic cards.
Find and verify sector keys using dictionaries and supported PM3 attacks.
Automatically save discovered keys to the user dictionary.
Wipe card data after confirmation when all sector keys are known.
"""

import os
import re
import sys
import time
import threading
import weakref

# Keep helper inside this plugin; do not modify system firmware /lib.
_LOCAL_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
if _LOCAL_LIB not in sys.path:
    sys.path.insert(0, _LOCAL_LIB)
from key_finding import (parse_fchk_keys, parse_attack_key, is_finished_fchk,
                         fmt_duration, progress_metrics)
from mf1_dictionaries import (dictionary_paths, dictionary_keys, found_sector0_keys,
                              alternating_keys, key_batches, temporary_dictionary,
                              append_verified_key, LEARNED_FILE)
from mifare_repair import (MODES, MENU_ITEMS, new_uid, repair_commands,
                           help_capabilities, extract_uid, command_failed,
                           RECOVERY_KEYS, extract_block_bytes, recovery_config,
                           parse_magic_identity, has_magic_evidence, is_standard_only,
                           block0)

PM3_TIMEOUT_MS = 12000
CAP_TIMEOUT_MS = 6000
MF1_FCHK_BATCH_SIZE = 128  # Small batches for alternating order + M1 cancellation.
MF1_FCHK_TIMEOUT_MS = 90000  # Per batch, not per entire multi-thousand-key dictionary.


class MifareClassicRepairPlugin(object):
    def __init__(self, host=None):
        self.host = host
        self.index = 0
        self.mode = None
        self.uid = ''
        self.capabilities = {'gen1a': False, 'gen2': False, 'config': False}
        self._last_message = ''
        self._auth = None
        self._rescue_family = None
        self._rescue_uid_length = None
        self._mf1_dictionary_paths = []
        self._mf1_priority_keys = []
        self._dictionary_blink_event = None
        self._dictionary_blink_thread = None
        self._scan_cancelled = threading.Event()
        self._auto_scan_active = False
        self._cancel_key_original = None
        self._keyfind_mode = 'dictionary'
        self._keyfind_found = {}
        self._keyfind_started = 0.0
        self._keyfind_running = False
        self._keyfind_selected = 0
        self._keyfind_uid = ''
        self._keyfind_indicator_label = 'checking dictionary...'

    def _var(self, key, value):
        self.host.set_var(key, self._tr(str(value)))

    def _error(self, msg, status='error'):
        self._last_message = msg
        pass
        self._var('error_msg', msg)
        return {'status': status}

    def _pm3(self, cmd, timeout=PM3_TIMEOUT_MS):
        # No logger: preserve the exact command/reply interface.
        return self.host.pm3_command(cmd, timeout=timeout)

    def do_init(self):
        pass
        self.index = 0
        self.mode = None
        self.uid = ''
        self._auth = None
        self._scan_cancelled.clear()
        self._auto_scan_active = False
        self._mf1_dictionary_paths = dictionary_paths()
        self._mf1_priority_keys = dictionary_keys(self._mf1_dictionary_paths, limit=4,
                                                  seen=RECOVERY_KEYS)
        pass
        self._rescue_family = None
        self._rescue_uid_length = None
        self._var('error_msg', '')
        self._var('mode_label', '')
        self._var('new_uid', '')
        self._var('result_uid', '')
        self._var('detect_message', '')
        self._var('dictionary_message', '')
        self._var('dictionary_progress', '')
        for _name in ('keys_elapsed', 'keys_rate', 'keys_eta', 'keys_found',
                      'keys_result', 'keys_key', 'keys_method'):
            self._var(_name, '')
        self._var('wipe_option', '')
        self._keyfind_found = {}
        self._keyfind_mode = 'dictionary'
        self._keyfind_started = 0.0
        self._keyfind_running = False
        self._keyfind_selected = 0
        self._keyfind_uid = ''
        self._keyfind_indicator_label = 'checking dictionary...'
        return {'status': 'ok'}

    def do_check_firmware(self):
        # Read-only help calls; capability check never modifies PM3 or tag state.
        responses = []
        for cmd in ('hf 14a config -h', 'hf mf wrbl -h', 'hf mf csetuid -h'):
            try:
                ok, out = self._pm3(cmd, CAP_TIMEOUT_MS)
                # CLI -h may return a nonzero exit code while still printing help.
                responses.append(out or '')
            except Exception:
                responses.append('')
        self.capabilities = help_capabilities(*responses[:3])
        pass
        # Key finding requires no Magic UID write feature and also runs on
        # firmware where write-based repair is unavailable.
        self.capabilities['key_finding'] = True
        self._var('firmware_status', 'Supported')
        return {'status': 'ok'}

    def _tr(self, text):
        """Translate custom Canvas labels via firmware PluginActivity.tr()."""
        fn = getattr(self.host, 'tr', None)
        return fn(text) if callable(fn) else text

    def _canvas(self):
        return self.host.getCanvas()

    def draw_modes(self):
        """Green selection, 4 items/page, visible page counter and arrows."""
        self._install_cancel_key_handler()
        c = self._canvas()
        tag = '_mfc_modes'
        c.delete(tag)
        c.create_rectangle(0, 49, 239, 198, fill='white', outline='', tags=(tag, '_jr_content'))
        count = len(MENU_ITEMS)
        visible = 4
        page = self.index // visible
        pages = (count + visible - 1) // visible
        top = page * visible
        c.create_text(120, 60, text=self._tr('Select repair mode'), anchor='center',
                      font=('Courier New', 12), fill='#1647D6', tags=(tag, '_jr_content'))
        for row, idx in enumerate(range(top, min(top + visible, count))):
            entry = MENU_ITEMS[idx]
            enabled = ((self.capabilities.get('gen1a') or self.capabilities.get('gen2')) if idx == 0 else
                       True if idx == 1 else
                       self.capabilities.get(entry[2], False))
            y = 83 + row * 22
            if idx == self.index:
                c.create_rectangle(6, y-10, 234, y+11, fill='#38A757',
                                   outline='', tags=(tag, '_jr_content'))
            c.create_text(15, y, anchor='w', text=self._tr(entry[1]),
                          font=('Courier New', 12),
                          fill=('#FFFFFF' if idx == self.index and enabled
                                else '#E0E0E0' if idx == self.index
                                else '#555555' if enabled else '#AAAAAA'), tags=(tag, '_jr_content'))
        if page > 0:
            c.create_text(222, 66, anchor='center', text='▲',
                          font=('Courier New', 11), fill='#1647D6', tags=(tag, '_jr_content'))
        if page + 1 < pages:
            c.create_text(222, 169, anchor='center', text='▼',
                          font=('Courier New', 11), fill='#1647D6', tags=(tag, '_jr_content'))
        c.create_text(120, 185, anchor='center',
                      text=self._tr('Page {}/{}').format(page + 1, pages),
                      font=('Courier New', 10), fill='#1647D6', tags=(tag, '_jr_content'))

    def clear_modes(self):
        self._canvas().delete('_mfc_modes')

    def mode_up(self):
        self.index = (self.index - 1) % len(MENU_ITEMS)
        self.draw_modes()

    def mode_down(self):
        self.index = (self.index + 1) % len(MENU_ITEMS)
        self.draw_modes()

    def choose_mode(self):
        pass
        if self.index == 0:
            if not (self.capabilities.get('gen1a') or self.capabilities.get('gen2')):
                return self._error('Auto Repair unavailable.', 'unsupported')
            self.mode = None
            self.uid = ''
            self._scan_cancelled.clear()
            self._auto_scan_active = True
            return {'status': 'auto'}
        if self.index == 1:
            self._scan_cancelled.clear()
            self._auto_scan_active = False
            return {'status': 'keys_only'}
        self.mode = MENU_ITEMS[self.index]
        if self._rescue_family is not None and (self.mode[2] != self._rescue_family or
             self.mode[4] != self._rescue_uid_length):
            self._auth = None
        if not self.capabilities.get(self.mode[2], False):
            return self._error('Firmware lacks this\nrepair method.', 'unsupported')
        self.uid = new_uid(self.mode[4])
        self._var('mode_label', self.mode[1])
        self._var('new_uid', self.uid)
        return {'status': 'ok'}

    def _install_cancel_key_handler(self):
        """Allow M1 to cancel a read-only scan while PluginActivity is busy.

        Firmware PluginActivity.onKeyEvent() normally discards M1 during a
        run: operation. Install a reversible, instance-local dispatch hook
        on the UI thread; never change a firmware/system source file.
        All other keys (especially PWR) retain their original handling.
        """
        if self._cancel_key_original is not None:
            return
        host = self.host
        original = getattr(host, 'onKeyEvent', None)
        if not callable(original):
            pass
            return
        plugin_ref = weakref.ref(self)

        def dispatch(key):
            plugin = plugin_ref()
            if key == 'M1' and plugin is not None and plugin._auto_scan_active:
                plugin.cancel_dictionary_scan()
                return
            return original(key)

        try:
            host.onKeyEvent = dispatch
            self._cancel_key_original = original
            pass
        except (AttributeError, TypeError):
            pass

    def cancel_dictionary_scan(self):
        """UI-thread callback: request cancellation, never perform RF work.

        stopPM3Task(wait=False) is the executor's nonblocking cancellation
        API. It does not call reworkPM3All from the UI thread. The RF worker
        owns cleanup and final hf 14a config --std before changing screens.
        """
        if not self._auto_scan_active or self._scan_cancelled.is_set():
            return {'status': 'noop'}
        self._scan_cancelled.set()
        pass
        self._var('dictionary_message', 'Cancelling...')
        refresh = getattr(self.host, 'update_screen', None)
        if callable(refresh):
            refresh()
        try:
            import executor
            stop = getattr(executor, 'stopPM3Task', None)
            if callable(stop):
                stop(wait=False)
                pass
            else:
                # Older executor: stop between commands only; never wait on UI.
                pass
        except Exception as exc:
            pass
        return {'status': 'noop'}

    def retry_auto_scan(self):
        """UI-only retry: reset cancellation before the run: worker starts."""
        self._scan_cancelled.clear()
        self._auto_scan_active = True
        self._var('dictionary_message', '')
        self._var('dictionary_progress', '')
        return {'status': 'retry'}

    # Two independent UI choices. Darkside mode includes Nested recovery.
    # Neither key-search mode writes to physical MIFARE cards.
    _KEYFIND_MODES = ('dictionary', 'darkside_nested')
    _KEYFIND_LABELS = ('Dict. Key search', 'Darkside key search')

    def reset_keys_choice(self):
        """UI-only: initialise submenu without starting RF."""
        self._keyfind_selected = 0
        self._render_keys_choice()

    def _render_keys_choice(self):
        """Green UP/DOWN selection, drawn on UI thread like the main menu."""
        c = self._canvas()
        c.delete('_mfc_keys_choice')
        tag = '_mfc_keys_choice'
        c.create_rectangle(0, 65, 239, 192, fill='white', outline='',
                           tags=(tag, '_jr_content'))
        c.create_text(120, 74, text=self._tr('No writes to card'),
                      font=('Courier New', 12), fill='#1647D6',
                      tags=(tag, '_jr_content'))
        for i, label in enumerate(self._KEYFIND_LABELS):
            y = 109 + i * 29
            if i == self._keyfind_selected:
                c.create_rectangle(6, y - 12, 234, y + 12,
                                   fill='#38A757', outline='',
                                   tags=(tag, '_jr_content'))
            c.create_text(120, y, text=self._tr(label),
                          font=('Courier New', 12),
                          fill='white' if i == self._keyfind_selected else '#555555',
                          tags=(tag, '_jr_content'))
        c.create_text(120, 181, text=self._tr('UP/DOWN select'),
                      font=('Courier New', 10), fill='#1647D6',
                      tags=(tag, '_jr_content'))

    def clear_keys_choice(self):
        self._canvas().delete('_mfc_keys_choice')

    def keys_choice_up(self):
        self._keyfind_selected = (self._keyfind_selected - 1) % len(self._KEYFIND_MODES)
        self._render_keys_choice()

    def keys_choice_down(self):
        self._keyfind_selected = (self._keyfind_selected + 1) % len(self._KEYFIND_MODES)
        self._render_keys_choice()

    def start_keys_selected(self):
        """UI only. Dictionary search is distinct from Darkside + Nested."""
        self._keyfind_mode = self._KEYFIND_MODES[self._keyfind_selected]
        return self._prepare_keys_run()

    def start_keys_dictionary(self):
        self._keyfind_mode = 'dictionary'
        return self._prepare_keys_run()

    def start_keys_darkside(self):
        """UI-only shortcut for the combined Darkside + Nested search."""
        self._keyfind_mode = 'darkside_nested'
        return self._prepare_keys_run()

    def _prepare_keys_run(self):
        self._scan_cancelled.clear()
        self._auto_scan_active = True
        self._keyfind_found = {}
        self._var('wipe_option', '')
        for key in ('keys_elapsed','keys_rate','keys_eta','keys_found',
                    'keys_result','keys_key','keys_method','dictionary_progress',
                    'dictionary_message'):
            self._var(key, '')
        self._var('keys_mode_label', self._tr(self._KEYFIND_LABELS[self._keyfind_selected]))
        pass
        return {'status': 'scan'}

    def _keyfind_progress(self, checked, total, phase='Dictionary'):
        elapsed = max(0.0, time.monotonic() - self._keyfind_started)
        rate, eta = progress_metrics(checked, total, elapsed)
        self._var('dictionary_progress', (self._tr('Keys: {}/{}').format(checked, total)
                                        if phase == 'Dictionary' else self._tr('Slots: {}/32').format(len(self._keyfind_found))))
        self._var('keys_elapsed', self._tr('Time: {}').format(fmt_duration(elapsed)))
        self._var('keys_rate', self._tr('Rate: {:.1f} keys/s').format(rate)
                  if phase == 'Dictionary' and rate else 'Rate: --')
        self._var('keys_eta', self._tr('ETA: {}').format(fmt_duration(eta)) if phase == 'Dictionary' else 'ETA: unknown')
        self._var('keys_found', self._tr('Found: {}/32').format(len(self._keyfind_found)))
        self._var('keys_method', phase)
        self.host.update_screen()
        return rate, eta

    def _keyfind_verify(self, sector, which, key, attempts=2, method='dictionary'):
        """Only an authenticated RF block read counts as a verified key."""
        if not re.fullmatch(r'[0-9a-fA-F]{12}', key or ''):
            return False
        slot = (sector, which)
        if slot in self._keyfind_found:
            return True
        for attempt in range(attempts):
            if self._scan_should_stop():
                return False
            cmd = 'hf mf rdbl --blk {} -{} -k {}'.format(sector * 4, which, key)
            try:
                ok, reply = self._pm3(cmd, PM3_TIMEOUT_MS)
                block = (extract_block_bytes(reply) if ok and
                         not command_failed(ok, reply) else None)
            except Exception as exc:
                pass
                block = None
            if self._scan_should_stop():
                return False
            if block:
                self._keyfind_found[slot] = key.upper()
                pass
                self._learn_verified_key(which, key.upper(), sector * 4)
                return True
        return False

    def _keyfind_accept_table(self, reply, method):
        """Only report keys proven with a valid read; never trust a table alone."""
        newly = 0
        for (sector, which), key in sorted(parse_fchk_keys(reply).items()):
            if self._scan_should_stop():
                break
            if (sector, which) not in self._keyfind_found and self._keyfind_verify(
                    sector, which, key, method=method):
                newly += 1
        return newly

    def _keyfind_run_dictionary(self):
        """Priority then 1,last,2,penultimate…; no writes to user dictionaries."""
        self._mf1_dictionary_paths = dictionary_paths()
        all_keys = dictionary_keys(self._mf1_dictionary_paths)
        priority = []
        seen = set()
        for key in list(self._mf1_priority_keys) + list(RECOVERY_KEYS):
            key = key.upper()
            if key not in seen:
                priority.append(key)
                seen.add(key)
        rest = [k for k in all_keys if k not in seen]
        total = len(priority) + len(rest)
        batches = ([priority] if priority else []) + list(key_batches(
            alternating_keys(rest), MF1_FCHK_BATCH_SIZE))
        checked = 0
        pass
        self._start_dictionary_blink()
        try:
            self._keyfind_progress(0, total)
            for index,batch in enumerate(batches,1):
                if self._scan_should_stop():
                    return 'cancelled'
                pass
                self._var('dictionary_progress', self._tr('Keys: {}-{}/{}').format(
                    checked+1, checked+len(batch), total))
                self.host.update_screen()
                try:
                    with temporary_dictionary(batch) as name:
                        if self._scan_should_stop():
                            return 'cancelled'
                        ok, reply = self._pm3('hf mf fchk --1k -f {}'.format(name),
                                              MF1_FCHK_TIMEOUT_MS)
                except Exception as exc:
                    pass
                    return 'incomplete'
                if self._scan_should_stop():
                    return 'cancelled'
                if not is_finished_fchk(ok, reply):
                    pass
                    return 'incomplete'
                checked += len(batch)
                newly = self._keyfind_accept_table(reply, 'dictionary')
                if self._scan_should_stop():
                    return 'cancelled'
                rate, eta = self._keyfind_progress(checked, total)
                pass
                if len(self._keyfind_found) == 32:
                    return 'complete'
            return 'complete'  # Complete dictionary coverage, keys can be partial.
        finally:
            self._stop_dictionary_blink()

    def _keyfind_propagate(self, key, method):
        if self._scan_should_stop():
            return False
        try:
            ok, reply = self._pm3('hf mf fchk --1k -k {}'.format(key),
                                  MF1_FCHK_TIMEOUT_MS)
        except Exception:
            return False
        if self._scan_should_stop() or not is_finished_fchk(ok, reply):
            return False
        return self._keyfind_accept_table(reply, method) > 0

    def _keyfind_run_darkside(self):
        """Darkside ONLY. No dictionary scan or Nested fallback.

        A successful Darkside result is verified on sector 0 key A before
        learning. Reusing the same proven key across sectors with `fchk -k`
        is not a dictionary search.
        """
        self._var('keys_method', 'Darkside')
        self._var('keys_eta', 'ETA: unknown')
        self._var('keys_rate', 'Rate: --')
        self._start_dictionary_blink('checking Darkside...')
        try:
            self.host.update_screen()
            pass
            try:
                ok, out = self._pm3('hf mf darkside', 120000)
            except Exception as exc:
                pass
                return 'incomplete'
            if self._scan_should_stop():
                return 'cancelled'
            key = parse_attack_key(out) if ok else None
            if key and self._keyfind_verify(0, 'a', key, attempts=3, method='darkside'):
                pass
                self._keyfind_propagate(key, 'darkside')
                return 'complete' if len(self._keyfind_found) == 32 else 'partial'
            pass
            return 'not_vulnerable'
        finally:
            self._stop_dictionary_blink()

    def _keyfind_seed_nested(self):
        """Probe a SMALL known-key set; do not scan all external dictionaries.

        Previously learned keys are preferred as Nested authentication seeds.
        No Darkside action is attempted when a seed is unavailable.
        """
        keys = []
        seen = set()
        try:
            learned = os.path.join('/mnt/upan/keys/mf1', LEARNED_FILE)
            recent = dictionary_keys([learned])[-32:]
        except Exception:
            recent = []
        for value in (list(reversed(recent)) + list(RECOVERY_KEYS)
                      + list(self._mf1_priority_keys)):
            value = value.upper()
            if value not in seen:
                seen.add(value)
                keys.append(value)
        if not keys:
            return False
        self._var('keys_method', 'Nested seed')
        pass
        try:
            with temporary_dictionary(keys) as path:
                ok, out = self._pm3('hf mf fchk --1k -f {}'.format(path),
                                    MF1_FCHK_TIMEOUT_MS)
        except Exception as exc:
            pass
            return False
        if self._scan_should_stop():
            return False
        if not is_finished_fchk(ok, out):
            pass
            return False
        self._keyfind_accept_table(out, 'seed')
        pass
        return bool(self._keyfind_found)

    def _keyfind_run_nested(self, seed_already_verified=False):
        """Nested with an existing recovered key, or a small known-key seed.

        Cap the scan to avoid hours of retries on unsupported cards. M1 can
        cancel between commands or request a nonblocking PM3 stop.
        """
        self._var('keys_eta', 'ETA: unknown')
        self._var('keys_rate', 'Rate: --')
        self._start_dictionary_blink('running Nested...')
        try:
            # A verified Darkside key is already a valid Nested seed.
            # Otherwise try a small learned/built-in candidate set only.
            if seed_already_verified:
                if not self._keyfind_found:
                    return 'no_seed'
            elif not self._keyfind_seed_nested():
                return 'cancelled' if self._scan_should_stop() else 'no_seed'
            if self._scan_should_stop():
                return 'cancelled'
            started = time.monotonic()
            budget_seconds = 300
            for sector in range(16):
                for which in ('a', 'b'):
                    if self._scan_should_stop():
                        return 'cancelled'
                    if time.monotonic() - started >= budget_seconds:
                        pass
                        return 'incomplete'
                    if (sector, which) in self._keyfind_found:
                        continue
                    known_slot, known_key = next(iter(sorted(self._keyfind_found.items())))
                    src_sector, src_type = known_slot
                    cmd = ('hf mf nested --1k --blk {} -{} -k {} --tblk {} --t{}'
                           .format(src_sector*4, src_type, known_key, sector*4, which))
                    self._var('keys_method', 'Nested S{} {}'.format(sector, which.upper()))
                    self.host.update_screen()
                    pass
                    try:
                        ok, reply = self._pm3(cmd, 45000)
                    except Exception as exc:
                        pass
                        continue
                    if self._scan_should_stop():
                        return 'cancelled'
                    key = parse_attack_key(reply) if ok else None
                    if key and self._keyfind_verify(sector, which, key,
                                                     attempts=3, method='nested'):
                        pass
                        self._keyfind_propagate(key, 'nested')
                    else:
                        pass
                    self._keyfind_progress(0, 0, 'Nested')
                    if len(self._keyfind_found) == 32:
                        return 'complete'
            return 'partial'
        finally:
            self._stop_dictionary_blink()

    def _keyfind_run_darkside_nested(self):
        """Run Darkside and then Nested without scanning the complete .dic.

        Darkside is attempted first (the user explicitly selected that mode).
        If it yields a verified Key A, re-use it for targeted Nested probes.
        Otherwise try a small known-key seed set so Nested can still work
        on cards where Darkside is unsupported. At no point is the full
        Dictionary search invoked. No physical card writes occur.
        """
        pass
        darkside_result = self._keyfind_run_darkside()
        if self._scan_should_stop() or darkside_result == 'cancelled':
            return 'cancelled'
        if len(self._keyfind_found) == 32:
            pass
            return 'complete'
        # If Darkside recovered a key, Nested does not need any fchk seed
        # discovery. If not, Nested only probes a small established seed set.
        seed_found = bool(self._keyfind_found)
        pass
        nested_result = self._keyfind_run_nested(seed_already_verified=seed_found)
        if self._scan_should_stop() or nested_result == 'cancelled':
            return 'cancelled'
        if len(self._keyfind_found) == 32:
            final_status = 'complete'
        elif nested_result == 'incomplete' or darkside_result == 'incomplete':
            # A command failed or was not completed; don't claim exhaustive
            # search even if some other key slots were verified.
            final_status = 'incomplete'
        elif self._keyfind_found:
            final_status = 'partial'
        else:
            final_status = 'no_recovery'
        pass
        return final_status

    def do_find_keys(self):
        """Standalone, read-only key finding: bypass healthy-card repair gate."""
        self._auto_scan_active = True
        self._keyfind_found = {}
        self._keyfind_uid = ''
        self._keyfind_started = time.monotonic()
        self._keyfind_running = True
        status = 'incomplete'
        pass
        try:
            # Only MIFARE Classic 1K, not a destructive Magic repair.
            self._var('keys_method','Detecting card')
            self.host.update_screen()
            try:
                ok,reader = self._pm3('hf 14a reader', CAP_TIMEOUT_MS)
            except Exception:
                ok,reader = False,''
            if self._scan_should_stop():
                status = 'cancelled'
            elif not ok or not extract_uid(reader):
                status = 'no_card'
            else:
                self._keyfind_uid = extract_uid(reader)
                self._var('keys_key', 'UID: ' + self._keyfind_uid)
                if self._keyfind_mode == 'dictionary':
                    status = self._keyfind_run_dictionary()
                elif self._keyfind_mode == 'darkside_nested':
                    status = self._keyfind_run_darkside_nested()
                else:
                    status = 'incomplete'
                if status == 'complete' and len(self._keyfind_found) < 32:
                    status = 'partial'
        except Exception as exc:
            pass
            status = 'incomplete'
        finally:
            self._auto_scan_active = False
            self._keyfind_running = False
            self._stop_dictionary_blink()
            # At this point no card-write has occurred in this workflow.
            # If cancellation stopped a command, executor owns its safe cleanup.
            reset_ok = self._reset_rf_standard()
            if self._scan_cancelled.is_set():
                status = 'cancelled'
            elapsed = time.monotonic()-self._keyfind_started
            self._var('keys_elapsed', self._tr('Time: {}').format(fmt_duration(elapsed)))
            count = len(self._keyfind_found)
            self._var('keys_found',self._tr('Found: {}/32').format(count))
            self._var('wipe_option', 'SRW - Wipe' if count > 0 else '')
            # A representative recovered key, not a false claim of all keys.
            if self._keyfind_found:
                (sec,typ),key = next(iter(sorted(self._keyfind_found.items())))
                self._var('keys_key','S{} {}: {}'.format(sec,typ.upper(),key))
            self._var('keys_result', (
                {
                    'complete':'All keys verified', 'partial':'Some keys missing',
                    'incomplete':'Scan incomplete', 'no_card':'No card detected',
                    'cancelled':'Cancelled', 'not_vulnerable':'Darkside unsupported',
                    'no_seed':'No known Nested key', 'no_recovery':'No key recovered'
                }.get(status, 'Scan incomplete') if reset_ok else 'PM3 RF reset failed'
            ))
            if not reset_ok:
                status = 'incomplete'
            pass
        return {'status': status}

    def prepare_wipe(self):
        """UI only. No write unless 32 authenticated slots have been found."""
        if len(self._keyfind_found) != 32 or not self._keyfind_uid:
            self._var('wipe_message', 'All 32 keys required')
            return {'status': 'blocked'}
        self._var('wipe_message', 'UID: ' + self._keyfind_uid)
        return {'status': 'confirm'}

    def _reset_rf_standard(self):
        """Restore normal ISO14443-A settings and verify PM3 response.

        Intended for RF worker methods; do not restart the reader here.
        """
        try:
            ok, out = self._pm3('hf 14a config --std', CAP_TIMEOUT_MS)
            return not command_failed(ok, out)
        except Exception:
            return False

    def do_wipe_verified(self):
        """Wipe and restore RF configuration on success or failure."""
        try:
            result = self._do_wipe_verified_core()
        finally:
            reset_ok = self._reset_rf_standard()
        if not reset_ok:
            self._var('wipe_message', 'PM3 RF reset failed')
            return {'status': 'error'}
        return result

    def _do_wipe_verified_core(self):
        """Destructive operation with an explicit confirmation screen.

        Read the card again and require the original UID and the same live keys.
        Do not use --gen2: manufacturer block 0 is preserved.
        """
        import tempfile
        if len(self._keyfind_found) != 32 or not self._keyfind_uid:
            return self._wipe_fail('All 32 keys required')
        try:
            ok, out = self._pm3('hf 14a reader', CAP_TIMEOUT_MS)
            if not ok or extract_uid(out) != self._keyfind_uid:
                return self._wipe_fail('Card changed / missing')
            # Check a representative known key before attempting any write.
            key = self._keyfind_found.get((0, 'a'))
            ok, out = self._pm3('hf mf rdbl --blk 0 -a -k ' + key, PM3_TIMEOUT_MS)
            if command_failed(ok, out) or not extract_block_bytes(out):
                return self._wipe_fail('Key check failed')
            keydata = b''.join(bytes.fromhex(self._keyfind_found[(sec, typ)])
                               for typ in ('a', 'b') for sec in range(16))
            fd, path = tempfile.mkstemp(prefix='mfc_wipe_', suffix='.bin')
            try:
                with os.fdopen(fd, 'wb') as fp:
                    fp.write(keydata)
                # Explicit key file: do not depend on an autopwn output directory.
                ok, out = self._pm3('hf mf wipe -f ' + path, 150000)
                if command_failed(ok, out):
                    return self._wipe_fail('Wipe failed / check card')
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            self._var('wipe_message', 'Wipe complete')
            return {'status': 'ok'}
        except Exception:
            return self._wipe_fail('Wipe failed / check card')

    def _wipe_fail(self, message):
        self._var('wipe_message', message)
        return {'status': 'error'}

    def _scan_should_stop(self):
        return self._auto_scan_active and self._scan_cancelled.is_set()

    def _standard_detect(self):
        """Check ordinary selection first, without relying on Magic markers."""
        for cmd in ('hf 14a reader', 'hf 14a info'):
            try:
                ok, out = self._pm3(cmd, CAP_TIMEOUT_MS)
            except Exception as exc:
                pass
                continue
            found = extract_uid(out)
            pass
            if ok and found:
                return found
        return None

    def _gen1_rescue_read(self):
        """Magic backdoor reads work even when ISO14443A selection fails."""
        if not self.capabilities.get('gen1a'):
            return None
        for suffix in ('', ' --gdm'):
            cmd = 'hf mf cgetblk --blk 0' + suffix
            try:
                ok, out = self._pm3(cmd, PM3_TIMEOUT_MS)
                data = extract_block_bytes(out) if ok and not command_failed(ok, out) else None
            except Exception:
                data = None
            pass
            if data:
                return {'family':'gen1a', 'uid_length':4,
                        'key':None, 'key_type':None, 'gdm':bool(suffix),
                        'block0':data}
        return None

    def _start_dictionary_blink(self, label='checking dictionary...'):
        """Flash the blue screen label while probing the external .dic keys.

        Only the firmware's thread-safe set_var/update_screen APIs are used;
        no Canvas or Tk widget access is made from the RF worker or blinker.
        """
        if self._dictionary_blink_event is not None:
            return
        stopped = threading.Event()
        self._dictionary_blink_event = stopped
        self._keyfind_indicator_label = label

        def animate():
            visible = True
            while not stopped.is_set():
                self._var('dictionary_message', ('Cancelling...' if self._scan_should_stop()
                         else self._keyfind_indicator_label if visible else ''))
                if self._keyfind_running and self._keyfind_started:
                    self._var('keys_elapsed', self._tr('Time: {}').format(fmt_duration(
                        time.monotonic() - self._keyfind_started)))
                refresh = getattr(self.host, 'update_screen', None)
                if callable(refresh):
                    try:
                        refresh()  # UI-thread dispatch is owned by PluginActivity
                    except Exception:
                        pass
                visible = not visible
                stopped.wait(0.45)

        self._dictionary_blink_thread = threading.Thread(
            target=animate, name='MFC-dictionary-indicator', daemon=True)
        self._dictionary_blink_thread.start()

    def _stop_dictionary_blink(self):
        stopped = self._dictionary_blink_event
        self._dictionary_blink_event = None
        if stopped is not None:
            stopped.set()
        thread = self._dictionary_blink_thread
        self._dictionary_blink_thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._var('dictionary_message', '')
        self._var('dictionary_progress', '')
        refresh = getattr(self.host, 'update_screen', None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    def _learn_verified_key(self, which, key, block):
        """Persist only proven credentials; RF verification occurs at caller.

        Store them beside the external dictionaries using iCopy-X's standard
        learned-key filename. Not used for user-entered, unverified values.
        """
        if not self._mf1_dictionary_paths:
            return
        directory = os.path.dirname(self._mf1_dictionary_paths[0])
        try:
            outcome = append_verified_key(key, directory=directory)
        except Exception as exc:
            outcome = 'error'
            pass
        pass
        if outcome == 'saved':
            # Newly learned keys are now available to later fchk runs and
            # to system hfmfkeys; no existing dictionaries are reordered.
            refresh = getattr(self.host, 'show_toast', None)
            if callable(refresh):
                refresh('Key saved to dictionary', timeout=2200)

    def _gen2_rescue_read(self, uid_length, block=0, keys=None):
        """Read-only rescue. Fast known keys, then external .dic via PM3 fchk.

        `hf mf fchk` is a single bulk dictionary operation; this avoids
        thousands of individual sector-authentication PM3 commands. It never
        fills emulator memory or writes the physical fob.
        """
        if not self.capabilities.get('gen2') or not self.capabilities.get('config'):
            return None
        if self._scan_should_stop():
            return None
        automatic = (keys is None)
        blink = bool(automatic and self._mf1_dictionary_paths)
        if blink:
            self._start_dictionary_blink()
        if automatic:
            # Fast-path the first external keys, then original v10 defaults.
            # The complete dictionaries are checked in bulk below if needed.
            priority = self._mf1_priority_keys + list(RECOVERY_KEYS)
            keys = [(which, key) for key in priority for which in ('b', 'a')]
        try:
            if self._scan_should_stop():
                return None
            ok, out = self._pm3(recovery_config(uid_length), CAP_TIMEOUT_MS)
            if self._scan_should_stop():
                return None
            if command_failed(ok, out):
                pass
                return None

            def read_with_credentials(which, key, retries=1):
                cmd = 'hf mf rdbl --blk {} -{} -k {}'.format(block, which, key)
                for attempt in range(retries):
                    if self._scan_should_stop():
                        return None
                    try:
                        valid, reply = self._pm3(cmd, PM3_TIMEOUT_MS)
                        data = (extract_block_bytes(reply) if valid and
                                not command_failed(valid, reply) else None)
                    except Exception:
                        data = None
                    if self._scan_should_stop():
                        return None
                    pass
                    if data:
                        # A real authenticated 16-byte block read is the
                        # minimum evidence required for key learning. fchk
                        # output alone is never persisted.
                        self._learn_verified_key(which, key, block)
                        return {'family':'gen2', 'uid_length':uid_length,
                                'key':key, 'key_type':which, 'block0':data}
                return None

            tried = set()
            for which, key in keys:
                if self._scan_should_stop():
                    return None
                if (which, key) in tried:
                    continue
                tried.add((which, key))
                result = read_with_credentials(which, key)
                if result:
                    return result

            # Bulk search is only appropriate for a 1K-compatible sector 0
            # when credentials were not supplied by the caller.
            if automatic and block == 0 and self._mf1_dictionary_paths:
                # Priority credentials were tested individually above. Read
                # all remaining unique external keys without changing .dic
                # files, then interleave: first, last, second, penultimate...
                priority_keys = set(self._mf1_priority_keys) | set(RECOVERY_KEYS)
                remaining = dictionary_keys(self._mf1_dictionary_paths,
                                            seen=priority_keys)
                total_keys = len(remaining)
                total_batches = ((total_keys + MF1_FCHK_BATCH_SIZE - 1) //
                                 MF1_FCHK_BATCH_SIZE)
                pass
                for batch_num, batch in enumerate(
                        key_batches(alternating_keys(remaining),
                                    MF1_FCHK_BATCH_SIZE), 1):
                    if self._scan_should_stop():
                        return None
                    pass
                    start = (batch_num - 1) * MF1_FCHK_BATCH_SIZE + 1
                    end = min(start + len(batch) - 1, total_keys)
                    # This range is being tested; do not mark it as complete
                    # before the RF command returns successfully.
                    self._var('dictionary_progress',
                              self._tr('Keys {}-{}/{}').format(start, end, total_keys))
                    self.host.update_screen()
                    try:
                        # A throwaway file is needed for PM3's bulk fchk.
                        # It is removed even when M1 interrupts the command.
                        with temporary_dictionary(batch) as temp_path:
                            if self._scan_should_stop():
                                return None
                            cmd = 'hf mf fchk --1k -f {}'.format(temp_path)
                            valid, reply = self._pm3(cmd, MF1_FCHK_TIMEOUT_MS)
                    except Exception as exc:
                        pass
                        if self._scan_should_stop():
                            return None
                        # Uncertain PM3/file state: do not claim all keys
                        # were tested and do not start another RF operation.
                        return None
                    if self._scan_should_stop():
                        return None
                    if not valid:
                        pass
                        # Timeout/transport failure: don't silently skip
                        # a batch and report its keys as checked.
                        return None
                    self._var('dictionary_progress',
                              self._tr('Keys {}/{}').format(end, total_keys))
                    self.host.update_screen()
                    found = found_sector0_keys(reply)
                    for which, key in found:
                        if self._scan_should_stop():
                            return None
                        # A successful fchk is insufficient; verify a real
                        # 16-byte B0 read before accepting authentication.
                        result = read_with_credentials(which, key, retries=3)
                        if result:
                            pass
                            return result
            return None
        finally:
            # Return reader to standard before any other rescue or write.
            try:
                self._pm3('hf 14a config --std', CAP_TIMEOUT_MS)
            except Exception:
                pass
            finally:
                if blink:
                    self._stop_dictionary_blink()

    def _auto_probe(self):
        """Standard detect -> read-only rescue -> select supported repair mode."""
        self.mode = None
        self.uid = ''
        self._auth = None
        self._rescue_family = None
        self._rescue_uid_length = None
        self._var('detect_message', 'No rescue response.\nSelect manual mode.')
        if self._scan_should_stop():
            return {'status': 'cancelled'}
        if self._standard_detect():
            self._var('detect_message', 'Card detected.\nRepair not needed.')
            pass
            return {'status': 'healthy'}

        # Read-only rescue methods: Gen1a backdoor followed by Gen2 forced
        # anticollision 4b then 7b. A valid 16-byte block is mandatory.
        if self._scan_should_stop():
            return {'status': 'cancelled'}
        matched = self._gen1_rescue_read()
        if self._scan_should_stop():
            return {'status': 'cancelled'}
        if matched is None:
            for uid_length in (4, 7):
                if self._scan_should_stop():
                    return {'status': 'cancelled'}
                matched = self._gen2_rescue_read(uid_length)
                if matched is not None:
                    break
        if matched is None:
            pass
            return {'status': 'manual'}

        family = matched['family']
        length = matched['uid_length']
        self._rescue_family = family
        self._rescue_uid_length = length
        if matched['key']:
            self._auth = (matched['key_type'], matched['key'])
        pass
        # A 4K read of block 128 is affirmative evidence of 4K capacity.
        # A failure is NOT proof of 1K: keys may differ between sectors.
        is_4k = False
        if family == 'gen1a':
            suffix = ' --gdm' if matched.get('gdm') else ''
            try:
                ok, out = self._pm3('hf mf cgetblk --blk 128' + suffix, CAP_TIMEOUT_MS)
                is_4k = bool(ok and not command_failed(ok, out) and extract_block_bytes(out))
            except Exception:
                pass
        else:
            is_4k = bool(self._gen2_rescue_read(length, block=128,
                         keys=[self._auth] if self._auth else None))
        if is_4k:
            for mode in MODES:
                if (mode[2], mode[3], mode[4]) == (family, '4K', length):
                    self.mode = mode
                    self.uid = new_uid(length)
                    self._var('mode_label', mode[1])
                    self._var('new_uid', self.uid)
                    self._var('detect_message', 'Detected: ' + mode[1])
                    return {'status': 'ok'}
        self._var('detect_message', 'Rescue read: ' + family + '\nSelect 1K or 4K.')
        return {'status':'manual'}

    def do_auto_detect(self):
        """Read-only probe, cooperatively cancellable via M1, then RF reset."""
        self._auto_scan_active = True
        pass
        result = {'status': 'manual'}
        reset_ok = False
        try:
            try:
                if self._scan_should_stop():
                    result = {'status': 'cancelled'}
                else:
                    result = self._auto_probe()
            finally:
                # Cancel is disabled before restoring standard RF configuration:
                # an M1 press here must not interrupt the cleanup command.
                self._auto_scan_active = False
                # The RF worker owns cleanup even after stopPM3Task(wait=False).
                try:
                    ok, out = self._pm3('hf 14a config --std', CAP_TIMEOUT_MS)
                    reset_ok = not command_failed(ok, out)
                except Exception as exc:
                    pass
                    reset_ok = False
            if not reset_ok:
                self._var('error_msg', 'PM3 reset failed.\nRestart reader.')
                self.mode = None
                self.uid = ''
                result = {'status': 'unsafe'}
            elif self._scan_cancelled.is_set():
                self.mode = None
                self.uid = ''
                self._var('detect_message', 'Dictionary scan cancelled.')
                result = {'status': 'cancelled'}
            pass
            return result
        finally:
            self._auto_scan_active = False

    def open_manual_menu(self):
        # UI-only action; manual choice does not guess a damaged tag's type.
        self.index = next((i for i, item in enumerate(MENU_ITEMS) if i > 1 and
                           self._rescue_family == item[2] and
                           self._rescue_uid_length == item[4]), 2)
        return {'status': 'ok'}

    def draw_repair_hint(self):
        c = self._canvas()
        c.delete('_mfc_repair_hint')
        c.create_text(120, 183, text=self._tr('OK - Repair'),
                      font=('Courier New', 12), fill='#1647D6',
                      anchor='center', tags=('_mfc_repair_hint', '_jr_content'))

    def clear_repair_hint(self):
        self._canvas().delete('_mfc_repair_hint')

    def _restart_reader(self):
        """Reuse the iCopy-X executor's existing full PM3 restart/reconnect.

        This is the firmware-owned reworkPM3All() path; it restarts the PM3
        and reconnects without reissuing an uncertain card write.  Must be
        called from a ``run:`` RF worker, never a UI ``call:`` handler.
        """
        pass
        started = time.monotonic()
        try:
            import executor
            fn = getattr(executor, 'reworkPM3All', None)
            result = bool(fn()) if callable(fn) else False
            pass
            return result
        except Exception as exc:
            pass
            return False

    def _read_repaired_uid(self):
        """Read only: determine whether the generated UID is selectable."""
        uid_seen = None
        for cmd in ('hf 14a reader', 'hf 14a info'):
            try:
                ok, out = self._pm3(cmd, CAP_TIMEOUT_MS)
                if not ok:
                    continue
                value = extract_uid(out)
                if value:
                    uid_seen = value
                    if value == self.uid:
                        return True, uid_seen
            except Exception:
                continue
        return False, uid_seen

    def _write_gen2_force(self):
        """Force only the manufacturer-block warning, NOT MIFARE authentication.

        Try ordinary known A/B credentials. Repeat only after a definitive
        authentication rejection, which precedes any card write. An ambiguous
        reply, timeout or connection failure NEVER triggers another write.
        """
        candidates = []
        if self._auth and self._auth[0] in ('a', 'b'):
            candidates.append(self._auth)
        for key in RECOVERY_KEYS:
            for which in ('a', 'b'):
                candidate = (which, key)
                if candidate not in candidates:
                    candidates.append(candidate)
        for index, (which, key) in enumerate(candidates, 1):
            _, write = repair_commands(self.mode, self.uid, key=key, key_type=which)
            pass
            try:
                ok, out = self._pm3(write, PM3_TIMEOUT_MS)
            except Exception as exc:
                pass
                return 'Write result unknown.\nCheck before retry.'
            if not ok:
                # The executor may have lost the reply AFTER writing the card.
                pass
                return 'Write result unknown.\nCheck before retry.'
            if re.search(r'(?i)\bwrite\s*\(\s*ok\s*\)', out or ''):
                pass
                self._auth = (which, key)
                return None
            # Auth rejection is definitive: MIFARE did not allow a block write.
            if re.search(r'(?i)\b(?:auth\s+error|authentication\s+(?:failed|error)|auth\s+failed)\b', out or ''):
                pass
                continue
            # Can't select card, write fail, missing success marker, timeout:
            # no key guessing/replay after an uncertain mutation.
            pass
            if command_failed(ok, out):
                return 'Block 0 write failed.\nCheck card and mode.'
            return 'Write unconfirmed.\nCheck before retry.'
        return 'No known key works.\nCheck card or key.'

    def _write_gen1_force(self):
        """Gen1a has NO --force flag and uses Magic backdoor commands."""
        _, write = repair_commands(self.mode, self.uid)
        for index, cmd in enumerate((write, write + ' --gdm'), 1):
            pass
            try:
                ok, out = self._pm3(cmd, PM3_TIMEOUT_MS)
            except Exception as exc:
                pass
                return 'Write result unknown.\nCheck before retry.'
            if not ok:
                return 'Write result unknown.\nCheck before retry.'
            # Iceman csetuid reports "New UID ... ( verified )" on success.
            if re.search(r'(?i)\bnew\s+uid\b', out or '') and \
                    re.search(r'(?i)\bverified\b', out or '') and \
                    not command_failed(ok, out):
                pass
                return None
            if index == 1 and re.search(r'(?i)\bwupC1\s+error\b', out or ''):
                # Alternative GDM wakeup, but only after a failed wakeup.
                continue
            pass
            if command_failed(ok, out):
                return 'Gen1a write failed.\nCheck card or mode.'
            return 'Write unconfirmed.\nCheck before retry.'
        return 'Gen1a write failed.\nCheck card or mode.'

    def do_repair(self):
        pass
        # Only the explicit confirmation screen permits any block-0 write.
        if not self.uid or self.mode not in MODES:
            return self._error('No repair target.')
        family = self.mode[2]
        if not self.capabilities.get(family, False):
            return self._error('Firmware unsupported.', 'unsupported')
        self._var('result_uid', self.uid)
        self._var('error_msg', '')
        repair_error = None
        reset_error = False
        try:
            # Do not trust leftover forced anti-collision from a prior scan.
            ok, out = self._pm3('hf 14a config --std', CAP_TIMEOUT_MS)
            if command_failed(ok, out):
                repair_error = 'RF setup failed.'
            elif self._standard_detect():
                # A normal selectable card is not a soft-brick. Protect it.
                repair_error = 'Card reads normally.\nRepair not needed.'
            elif family == 'gen2':
                if self._auth is None:
                    found = self._gen2_rescue_read(self.mode[4], block=0)
                    if found:
                        self._auth = (found['key_type'], found['key'])
                config = recovery_config(self.mode[4])
                ok, out = self._pm3(config, CAP_TIMEOUT_MS)
                if command_failed(ok, out):
                    repair_error = 'RF setup failed.'
                else:
                    repair_error = self._write_gen2_force()
            else:
                # csetuid can wake a Gen1a even if standard reader and
                # cgetblk both fail. Do NOT gate on a rescue-read success.
                repair_error = self._write_gen1_force()
        except Exception as exc:
            pass
            repair_error = 'PM3 connection or\ncommand failed.'
        finally:
            try:
                ok, out = self._pm3('hf 14a config --std', CAP_TIMEOUT_MS)
                reset_error = command_failed(ok, out)
            except Exception as exc:
                pass
                reset_error = True

        # Never restart/replay a write against a healthy card.
        if repair_error == 'Card reads normally.\nRepair not needed.':
            return self._error(repair_error)
        if not reset_error:
            verified, uid_seen = self._read_repaired_uid()
            if verified:
                pass
                return {'status': 'ok'}
        else:
            uid_seen = None

        # The only recovery action is the existing host reader restart.
        # NEVER resend a block-0 write here: the outcome may be uncertain.
        if not self._restart_reader():
            if reset_error:
                return self._error('PM3 reset unverified.\nPM3 restart failed.')
            if repair_error:
                return self._error(repair_error)
            return self._error('Card not verified.\nPM3 restart failed.')
        try:
            ok, out = self._pm3('hf 14a config --std', CAP_TIMEOUT_MS)
            if command_failed(ok, out):
                return self._error('PM3 reset failed\nafter reader restart.')
        except Exception:
            return self._error('PM3 reset failed\nafter reader restart.')
        verified, new_seen = self._read_repaired_uid()
        if verified:
            pass
            return {'status': 'ok'}
        if repair_error:
            return self._error(repair_error)
        if new_seen or uid_seen:
            return self._error('UID mismatch.\nCard not verified.')
        return self._error('Card not detected.\nRepair not verified.')
