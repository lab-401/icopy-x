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

"""Manage Dictionaries plugin.

Two features, chosen from the main menu:

1. Load Dictionaries
   Copies the bundled default dictionaries from the plugins directory to
   their live locations on the SD card, creating the destination
   directories if they do not exist.  This overwrites the live copy, so
   any keys added manually afterwards are lost if it is run again -- the
   UI warns about this before running.

       mf1  : /mnt/upan/plugins/dictionaries/mf1/mfc_default_keys.dic
              -> /mnt/upan/keys/mf1/mfc_default_keys.dic
       t55xx: /mnt/upan/plugins/dictionaries/t55xx/t55xx_default_pwds.dic
              -> /mnt/upan/keys/t55xx/t55xx_default_pwds.dic

2. Add to Dictionary
   A picker cycles between "MF1", "MF1 User" and "T55xx"; the chosen type
   routes to a hex input screen (12 hex chars for MFC / user keys, 8 hex
   chars for T55xx passwords).  The entered value is appended to the live
   dictionary:
     - strict length + hex validation
     - duplicate keys are skipped (case-insensitive)
     - a single "# iCopy-XS Added Key" header is written above the block
       of added keys, kept at the end of the file
     - the file/dir is created if absent and the write is flushed+fsynced

3. Backup Dictionaries
   Copies the current live SD dictionaries into a numbered subdirectory
   under /mnt/upan/backup_dictionaries so users can snapshot their keys
   before/after manual edits.  Each backup is its own numbered folder
   holding both dics.  Backup #1 is always the newest: on every backup the
   existing folders are shifted up (highest first, so they never collide)
   and the fresh copy becomes folder 1.  Only live files that exist are
   copied; if neither exists nothing is written.

       /mnt/upan/keys/mf1/mfc_default_keys.dic
       /mnt/upan/keys/mf1/mfc_users_keys.dic
       /mnt/upan/keys/t55xx/t55xx_default_pwds.dic
           -> /mnt/upan/backup_dictionaries/1/<same names>

4. Clear User Keys
   Deletes the learned-keys dictionary (mfc_users_keys.dic) after showing an
   information screen with the current key count.  Only the user dic is
   removed; the default MF1 dic, the T55xx dic and any backups are untouched.

File paths and names are fixed and must not change -- they mirror the
locations the rest of the firmware reads from (hfmfkeys._SD_DIC and the
T55xx recovery plugin's _DIC_SRC).

Method names here are referenced verbatim from ui.json run: actions.

Python 3.8 compatible.
"""

import os
import re
import shutil

# ----------------------------------------------------------------------
# Dictionary locations -- names are exact and must not be changed
#
# Sources are bundled INSIDE this plugin directory so they travel with the
# plugin when the app is installed/flashed -- nothing needs to be
# pre-seeded on the SD card.  _PLUGIN_DIR resolves to this plugin's own
# folder at runtime (plugin.py is imported from its real file path, so
# __file__ points here).  Destinations are the live SD locations the rest
# of the firmware reads from (hfmfkeys._SD_DIC and the T55xx recovery
# plugin's dic path).
# ----------------------------------------------------------------------

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_DIR = os.path.join(_PLUGIN_DIR, 'dictionaries')

_MFC_SRC = os.path.join(_BUNDLED_DIR, 'mf1', 'mfc_default_keys.dic')
_MFC_DST = '/mnt/upan/keys/mf1/mfc_default_keys.dic'
_MFC_LEN = 12  # MFC key = 6 bytes = 12 hex chars

_T55_SRC = os.path.join(_BUNDLED_DIR, 't55xx', 't55xx_default_pwds.dic')
_T55_DST = '/mnt/upan/keys/t55xx/t55xx_default_pwds.dic'
_T55_LEN = 8   # T55xx password = 4 bytes = 8 hex chars

# Learned-keys dic: auto-populated by hfmfkeys.saveLearnedKeys(), and manually
# appendable here.  Same 12-hex format as the MF1 default dic.
_USER_DST = '/mnt/upan/keys/mf1/mfc_users_keys.dic'
_USER_LEN = 12

# iCLASS Legacy keys dictionary (for iCLASS SE/SEOS card cloning)
_ICLASS_SRC = os.path.join(_BUNDLED_DIR, 'iclass', 'iclass_default_keys.dic')
_ICLASS_DST = '/mnt/upan/keys/iclass/iclass_default_keys.dic'
_ICLASS_LEN = 16  # iCLASS key = 8 bytes = 16 hex chars

# Comment written once above the block of user-added keys
_HEADER = '# iCopy-XS Added Key'

_HEX_RE = re.compile(r'^[0-9A-Fa-f]+$')

# Backup destination base dir on the SD card.  Each backup is a numbered
# subdirectory (1, 2, 3, ...) with #1 always the most recent.
_BACKUP_DIR = '/mnt/upan/backup_dictionaries'
_MFC_NAME = os.path.basename(_MFC_DST)  # mfc_default_keys.dic
_T55_NAME = os.path.basename(_T55_DST)  # t55xx_default_pwds.dic
_USER_NAME = os.path.basename(_USER_DST)  # mfc_users_keys.dic
_ICLASS_NAME = os.path.basename(_ICLASS_DST)  # iclass_default_keys.dic


class ManageDictionariesPlugin(object):
    """Entry class for the Manage Dictionaries plugin."""

    def __init__(self, host=None):
        self.host = host

    # ------------------------------------------------------------------
    # Add-type picker (on_enter of add_picker)
    # ------------------------------------------------------------------

    def do_init_add(self):
        """Default the picker to MF1 each time the picker is entered."""
        self.host.set_var('dic_type', 'MF1')
        return None

    def do_cycle_type(self):
        """Cycle the displayed dictionary type: MF1 -> MF1 User -> T55xx -> ICLASS."""
        current = self.host.get_var('dic_type', 'MF1')
        if current == 'MF1':
            nxt = 'MF1 User'
        elif current == 'MF1 User':
            nxt = 'T55xx'
        elif current == 'T55xx':
            nxt = 'ICLASS'
        else:
            nxt = 'MF1'
        self.host.set_var('dic_type', nxt)
        self.host.update_screen()
        return None

    def do_confirm_type(self):
        """Route to the correct input screen based on the selected type.

        MF1 and MF1 User are both 12-hex keys, so both route to input_mfc;
        do_capture_mfc picks the destination dic from dic_type.
        """
        if self.host.get_var('dic_type', 'MF1') == 'T55xx':
            return {'status': 't55xx'}
        if self.host.get_var('dic_type', 'MF1') == 'ICLASS':
            return {'status': 'iclass'}
        return {'status': 'mfc'}

    # ------------------------------------------------------------------
    # Key capture -- read the input widget while it is still alive
    # ------------------------------------------------------------------

    def do_capture_mfc(self):
        """Capture and append a 12-hex key to the selected MF1 dic."""
        if self.host.get_var('dic_type', 'MF1') == 'MF1 User':
            return self._capture(_USER_DST, _USER_LEN, 'MF1 User')
        return self._capture(_MFC_DST, _MFC_LEN, 'MF1')

    def do_capture_t55xx(self):
        """Capture and append a T55xx password (8 hex chars)."""
        return self._capture(_T55_DST, _T55_LEN, 'T55xx')

    def do_capture_iclass(self):
        """Capture and append an iCLASS key (16 hex chars)."""
        return self._capture(_ICLASS_DST, _ICLASS_LEN, 'iCLASS')

    def _capture(self, path, keylen, label):
        """Validate the hex input then append it to the given dictionary.

        Returns a status dict for the state machine:
            added     -- key validated and appended
            duplicate -- key already present, skipped
            invalid   -- wrong length or non-hex
            error     -- file write failed
        """
        value = self.host.get_input().strip().upper()

        # Strict length + hex validation
        if len(value) != keylen or _HEX_RE.match(value) is None:
            return {'status': 'invalid'}

        try:
            existing = self._read_file(path)
        except Exception:
            existing = ''

        # Duplicate check -- case-insensitive over valid key lines only
        if value in self._existing_keys(existing, keylen):
            self.host.set_var('added_key', value)
            return {'status': 'duplicate'}

        try:
            self._append_key(path, existing, value, keylen)
        except Exception:
            return {'status': 'error'}

        self.host.set_var('added_key', value)
        return {'status': 'added'}

    # ------------------------------------------------------------------
    # Load dictionaries (on_enter of loading)
    # ------------------------------------------------------------------

    def do_load(self):
        """Copy both bundled dictionaries to their live SD locations.

        Creates destination directories if missing and overwrites any
        existing live copy.  Reports per-file status so the result screen
        can show exactly what happened.

        Returns:
            {'status': 'done'}  if BOTH files copied
            {'status': 'error'} if either file failed
        """
        mf_ok = self._copy_one(_MFC_SRC, _MFC_DST)
        t55_ok = self._copy_one(_T55_SRC, _T55_DST)
        iclass_ok = self._copy_one(_ICLASS_SRC, _ICLASS_DST)

        self.host.set_var('load_mf', 'OK' if mf_ok else 'FAILED')
        self.host.set_var('load_t55', 'OK' if t55_ok else 'FAILED')
        self.host.set_var('load_iclass', 'OK' if iclass_ok else 'FAILED')

        if mf_ok and t55_ok and iclass_ok:
            return {'status': 'done'}
        return {'status': 'error'}

    def _copy_one(self, src, dst):
        """Copy src -> dst, creating dst's directory. Returns True on success."""
        try:
            if not os.path.isfile(src):
                return False
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Backup dictionaries (on_enter of backing_up)
    # ------------------------------------------------------------------

    def do_backup(self):
        """Snapshot the live SD dictionaries into backup_dictionaries/1.

        Only live files that exist are copied.  Existing numbered backups
        are shifted up first so the new snapshot always lands in folder 1
        (the most recent).

        Returns:
            {'status': 'done'}  at least one live dic backed up to #1
            {'status': 'empty'} neither live dic exists -- nothing written
            {'status': 'error'} shift/copy failed
        """
        self.host.set_var('backup_mf', '--')
        self.host.set_var('backup_user', '--')
        self.host.set_var('backup_t55', '--')
        self.host.set_var('backup_iclass', '--')

        present = [
            (_MFC_DST, _MFC_NAME, 'mf'),
            (_USER_DST, _USER_NAME, 'user'),
            (_T55_DST, _T55_NAME, 't55'),
            (_ICLASS_DST, _ICLASS_NAME, 'iclass'),
        ]
        present = [(s, n, tag) for (s, n, tag) in present if os.path.isfile(s)]

        # Nothing on the SD to snapshot -- do not create an empty backup
        if not present:
            return {'status': 'empty'}

        try:
            os.makedirs(_BACKUP_DIR, exist_ok=True)
            # Push existing backups up so #1 is free for the newest snapshot
            self._shift_backups_up()
            dest = os.path.join(_BACKUP_DIR, '1')
            os.makedirs(dest, exist_ok=True)
            for (src, name, tag) in present:
                shutil.copy(src, os.path.join(dest, name))
                self.host.set_var('backup_%s' % tag, 'OK')
        except Exception:
            return {'status': 'error'}

        return {'status': 'done'}

    def _shift_backups_up(self):
        """Rename every numbered backup dir N -> N+1, highest first.

        Renaming from the highest number down means the target N+1 is
        always free when we rename N, so backups never collide.  Only
        positive integer directory names are touched; any other entry
        (stray files, non-numeric dirs) is left untouched.
        """
        nums = []
        for name in os.listdir(_BACKUP_DIR):
            full = os.path.join(_BACKUP_DIR, name)
            if os.path.isdir(full) and name.isdigit() and int(name) >= 1:
                nums.append(int(name))

        for n in sorted(nums, reverse=True):
            src = os.path.join(_BACKUP_DIR, str(n))
            dst = os.path.join(_BACKUP_DIR, str(n + 1))
            os.rename(src, dst)

    # ------------------------------------------------------------------
    # Clear user keys (on_enter of clear_info / clearing)
    # ------------------------------------------------------------------

    def do_clear_info(self):
        """Count learned keys so the info screen shows what will be cleared."""
        n = 0
        try:
            if os.path.isfile(_USER_DST):
                with open(_USER_DST, 'r') as f:
                    for line in f:
                        t = line.strip()
                        if len(t) == _USER_LEN and _HEX_RE.match(t) is not None:
                            n += 1
        except Exception:
            n = 0
        self.host.set_var('clear_count', str(n))
        return None

    def do_clear(self):
        """Delete the learned-keys dic (mfc_users_keys.dic).

        Only the user/learned dictionary is removed -- the default MF1 dic,
        the T55xx dic and any saved backups are never touched.

        Returns:
            {'status': 'done'}  the user dic was removed
            {'status': 'empty'} no user dic present -- nothing to clear
            {'status': 'error'} the file could not be removed
        """
        if not os.path.isfile(_USER_DST):
            return {'status': 'empty'}
        try:
            os.remove(_USER_DST)
        except Exception:
            return {'status': 'error'}
        return {'status': 'done'}

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def _read_file(self, path):
        """Return the file's text, or '' if it does not exist / cannot read."""
        try:
            with open(path, 'r') as f:
                return f.read()
        except (OSError, IOError):
            return ''

    def _is_key(self, line, keylen):
        """True if a stripped line is a valid key of the expected length."""
        s = line.strip()
        return len(s) == keylen and _HEX_RE.match(s) is not None

    def _existing_keys(self, text, keylen):
        """Set of upper-cased valid keys already present in the text."""
        keys = set()
        for line in text.splitlines():
            if self._is_key(line, keylen):
                keys.add(line.strip().upper())
        return keys

    def _needs_header(self, lines, keylen):
        """Whether a fresh header must precede the key we are about to add.

        Walks from the end of the file over trailing blank lines and the
        trailing run of valid keys.  If the line immediately above that
        run is exactly our header, the block already has one and we do not
        add another.  Otherwise (different content, or no header found) we
        add the header so every added-key block is labelled.
        """
        i = len(lines) - 1
        while i >= 0 and lines[i].strip() == '':
            i -= 1
        while i >= 0 and self._is_key(lines[i], keylen):
            i -= 1
        if i >= 0 and lines[i].strip() == _HEADER:
            return False
        return True

    def _append_key(self, path, existing, key, keylen):
        """Append key (with header if needed) and fsync.

        Creates the parent directory and file if absent.  Guarantees the
        new content starts on its own line even if the existing file did
        not end with a newline.
        """
        lines = existing.splitlines()
        need_header = self._needs_header(lines, keylen)

        block = ''
        # Separate from prior content that lacks a trailing newline
        if existing and not existing.endswith('\n'):
            block += '\n'
        if need_header:
            block += _HEADER + '\n'
        block += key + '\n'

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a') as f:
            f.write(block)
            f.flush()
            os.fsync(f.fileno())
