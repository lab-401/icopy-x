##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
# Copyright (c) 2026: Vost02
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Card Notes -- browse cards and attach a note to each, keyed by UID.

The iCopy-X stores dumps keyed by the card number (UID) and the built-in
Dump Files browser can only show that number, so a wallet with many cards
is hard to read.  This plugin browses ``/mnt/upan/dump/`` and lets you
attach a note per card.  The notes live in a sidecar store shared with
other plugins (see :mod:`lib.card_notes`), so the Ultra/Tiny writers can
show the note next to the matching dump.  A card is identified by its UID,
read from the filename or, for a renamed dump, from the dump files
themselves, so renaming a dump does not lose its note.

Notes are written either on the device -- the edit screen is a normal
``ui.json`` ``input_text`` field (UP/DOWN change the character under the
cursor, LEFT/RIGHT move, M1 deletes a cell, M2 cycles the character set,
OK saves) -- or on a PC by editing ``/mnt/upan/card_notes.json`` while the
iCopy-X exports its user partition as a USB mass-storage drive.  The
device keyboard is ASCII only; Chinese notes written on a PC display fine
on the device.
"""

import os

from lib import card_notes as store

DEFAULT_DUMP_ROOT = '/mnt/upan/dump'


def _scan_dumps(root):
    """Map ``family:identity`` -> {family, uid, path, mtime} for every dump."""
    cards = {}
    if not os.path.isdir(root):
        return cards
    try:
        families = sorted(os.listdir(root))
    except OSError:
        return cards
    for family in families:
        directory = os.path.join(root, family)
        if not os.path.isdir(directory) or family.startswith('.'):
            continue
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            uid = store.uid_from_dump(path, family)
            if not uid:
                continue
            key = store.key(family, uid)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = 0.0
            previous = cards.get(key)
            if previous is None or mtime >= previous['mtime']:
                cards[key] = {'family': family, 'uid': uid,
                              'path': path, 'mtime': mtime}
    return cards


class CardNotesPlugin(object):
    """Entry class for Card Notes (a ui.json plugin).

    The screens live in ui.json; these methods only touch data.  The note
    editor is the framework's ``input_text`` field, so this plugin is an
    ordinary ui.json plugin like every other bundled one.
    """

    def __init__(self, host=None):
        self.host = host
        self._cards = {}
        self._keys = []
        self._notes = {}
        self._notes_path = store.NOTES_PATH
        self._dump_root = DEFAULT_DUMP_ROOT
        self._edit_key = None

    # -- host helpers --------------------------------------------------

    def _set(self, key, value):
        if self.host is not None:
            self.host.set_var(key, value)

    def _set_list_items(self, state_id, items):
        screens = getattr(self.host, '_screens', None)
        if not screens or state_id not in screens:
            return False
        state_def = screens[state_id]
        screen = state_def.get('screen', state_def)
        content = screen.setdefault('content', {})
        content['type'] = 'list'
        content['items'] = items
        return True

    def _selected(self):
        list_state = getattr(self.host, '_list_state', None) or {}
        entry = list_state.get('list') or {}
        try:
            return int(entry.get('selected', 0))
        except (TypeError, ValueError):
            return 0

    def _toast(self, text, error=False):
        if self.host is not None:
            self.host.show_toast(text, timeout=0 if error else 1200,
                                 icon='error' if error else None)

    # -- data ----------------------------------------------------------

    def _reload(self):
        self._notes_path = store.notes_path()
        self._dump_root = os.environ.get('CARD_NOTES_DUMP_DIR', DEFAULT_DUMP_ROOT)
        self._cards = _scan_dumps(self._dump_root)
        self._notes = store.load(self._notes_path)
        self._keys = sorted(self._cards, key=self._sort_key)

    def _sort_key(self, key):
        note = store.note_text(self._notes.get(key))
        uid = self._cards[key]['uid']
        return (0 if note else 1, (note or uid).lower(), uid)

    def _label(self, key):
        note = store.note_text(self._notes.get(key))
        uid = self._cards[key]['uid']
        if note:
            text = '%s  %s' % (note, uid)
        elif self.host is not None:
            text = '%s  %s' % (self.host.tr("(no note)"), uid)
        else:
            text = '%s  %s' % ("(no note)", uid)
        return text[:34]

    @staticmethod
    def _split(key):
        family, _, uid = key.partition(':')
        return family, uid

    # -- actions -------------------------------------------------------

    def load(self):
        """on_enter for the list screen: rescan and fill the list."""
        try:
            self._reload()
        except Exception as exc:
            if self.host is not None:
                self.host.set_var('error_msg',
                                  self.host.tr('%s: %s') % (type(exc).__name__, exc))
            return {'status': 'error'}
        if self._keys:
            items = [{'label': self._label(key)} for key in self._keys]
        elif self.host is not None:
            items = [{'label': self.host.tr("No cards found")}]
        else:
            items = [{'label': "No cards found"}]
        self._set_list_items('list', items)
        return {'status': 'loaded'}

    def edit(self):
        idx = self._selected()
        if not (0 <= idx < len(self._keys)):
            return {'status': 'loaded'}
        self._edit_key = self._keys[idx]
        self._set('edit_note', store.note_text(self._notes.get(self._edit_key)))
        return {'status': 'edit'}

    def save(self):
        if self._edit_key is None:
            return {'status': 'saved'}
        text = ''
        if self.host is not None:
            text = (self.host.get_input() or '').strip()
        notes = store.load(self._notes_path)
        family, uid = self._split(self._edit_key)
        store.set_note(notes, family, uid, text)
        try:
            store.save(notes, self._notes_path)
            self._toast(self.host.tr("Saved") if self.host is not None else "Saved")
        except OSError as exc:
            self._toast('%s: %s' % (self.host.tr("Save failed") if self.host
                                    else "Save failed", exc), error=True)
        return {'status': 'saved'}

    def clear(self):
        idx = self._selected()
        if 0 <= idx < len(self._keys):
            key = self._keys[idx]
            notes = store.load(self._notes_path)
            family, uid = self._split(key)
            store.clear_note(notes, family, uid)
            try:
                store.save(notes, self._notes_path)
                self._toast(self.host.tr("Cleared") if self.host is not None
                            else "Cleared")
            except OSError as exc:
                self._toast('%s: %s' % (self.host.tr("Save failed") if self.host
                                        else "Save failed", exc), error=True)
        return {'status': 'cleared'}
