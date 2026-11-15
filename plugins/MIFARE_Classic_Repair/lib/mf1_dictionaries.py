# Copyright (c) 2026 jareckib
"""Read and safely learn MIFARE Classic keys on iCopy-X USB partition.

Only verified 6-byte MIFARE Classic keys are accepted for saving. The module
never touches system files, T55xx dictionaries or card memory.
"""
from __future__ import absolute_import

import os
import re
import tempfile
import fcntl
from contextlib import contextmanager

MF1_DIR = '/mnt/upan/keys/mf1'
LEARNED_FILE = 'mfc_users_keys.dic'  # Same destination as hfmfkeys.saveLearnedKeys()
KEY_RE = re.compile(r'^[0-9A-Fa-f]{12}$')
PREFERRED = ('mf_user_key.dic', 'mfc_default_keys.dic', 'mfc_users_keys.dic')
FCHK_SECTOR_0 = re.compile(
    r'^\s*(?:\[\+\]\s*)?0{1,3}\s*\|\s*0*3\s*\|\s*'
    r'([0-9a-fA-F]{12}|-{12})\s*\|\s*([01])\s*\|\s*'
    r'([0-9a-fA-F]{12}|-{12})\s*\|\s*([01])(?:\s*\||\s*$)')


def dictionary_paths(directory=MF1_DIR):
    """Paths on the same /mnt/upan partition as dump; never bundle dictionaries."""
    try:
        names = [n for n in os.listdir(directory)
                 if n.lower().endswith('.dic') and os.path.isfile(os.path.join(directory, n))]
    except OSError:
        return []
    names.sort(key=lambda n: (PREFERRED.index(n) if n in PREFERRED else len(PREFERRED), n.lower()))
    return [os.path.join(directory, n) for n in names]


def dictionary_keys(paths, limit=None, seen=None):
    """Return ordered unique keys, ignoring comments and malformed entries."""
    seen = set(seen or ())
    result = []
    for path in paths:
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='replace') as fh:
                for line in fh:
                    key = line.split('#', 1)[0].strip().upper()
                    if KEY_RE.fullmatch(key) and key not in seen:
                        seen.add(key)
                        result.append(key)
                        if limit is not None and len(result) >= limit:
                            return result
        except (OSError, UnicodeError):
            continue
    return result


def alternating_keys(keys):
    """Reorder unique candidates: first, last, second, penultimate, ...

    Callers pass keys *after* priority candidates have been removed.
    Original user dictionary files remain unchanged.
    """
    left, right = 0, len(keys) - 1
    while left <= right:
        yield keys[left]
        left += 1
        if left <= right:
            yield keys[right]
            right -= 1


def key_batches(keys, size=128):
    """Split an ordered key iterator into bounded fchk batches.

    Between batches the plugin can service cancellation without waiting for
    a single bulk scan of several thousand keys to complete.
    """
    if size <= 0:
        raise ValueError('Batch size must be positive')
    batch = []
    for key in keys:
        batch.append(key)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


@contextmanager
def temporary_dictionary(keys):
    """Create one short-lived fchk dictionary under /tmp, never on USB.

    The helper controls creation, close and deletion; an exception or user
    cancellation must not leave a reordered copy beside the originals.
    """
    fd, path = tempfile.mkstemp(prefix='mfc_repair_', suffix='.dic')
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            for key in keys:
                if not KEY_RE.fullmatch(key):
                    raise ValueError('Invalid MIFARE Classic key in temporary batch')
                stream.write(key.upper() + '\n')
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def found_sector0_keys(fchk_output):
    """Parse only validated sector 0 key table results from `hf mf fchk --1k`."""
    for raw in (fchk_output or '').splitlines():
        line = re.sub(r'\x1b\[[0-9;]*m', '', raw)
        match = FCHK_SECTOR_0.match(line)
        if not match:
            continue
        a, a_ok, b, b_ok = match.groups()
        found = []
        # Prefer B when available: the current Noralsy test tag reads with B.
        if b_ok == '1' and KEY_RE.fullmatch(b):
            found.append(('b', b.upper()))
        if a_ok == '1' and KEY_RE.fullmatch(a):
            found.append(('a', a.upper()))
        return found
    return []


def append_verified_key(key, directory=MF1_DIR):
    """Append a *previously verified* key to the normal iCopy-X user dictionary.

    Caller MUST prove authentication with a real block read first. This
    helper does no RF. The result is one of 'saved', 'exists', 'invalid',
    'unavailable', 'error'. Never creates /mnt/upan or its keys/mf1 directory;
    never overwrites a dictionary or dumps. Existing keys in *any* .dic
    count as known, so rescans don't create redundant entries.
    """
    if not isinstance(key, str) or KEY_RE.fullmatch(key) is None:
        return 'invalid'
    key = key.upper()
    if not os.path.isdir(directory):
        return 'unavailable'
    target = os.path.join(directory, LEARNED_FILE)
    if os.path.islink(target):
        return 'error'  # Refuse symlinks to paths outside the key directory.
    if key in set(dictionary_keys(dictionary_paths(directory))):
        return 'exists'
    try:
        # POSIX advisory lock prevents this plugin's concurrent writes.
        # Open a+ instead of w to guarantee no truncation of existing keys.
        with open(target, 'a+', encoding='utf-8') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                stream.seek(0)
                existing_text = stream.read()
                present = {
                    line.split('#', 1)[0].strip().upper()
                    for line in existing_text.splitlines()
                }
                if key in present:
                    return 'exists'
                stream.seek(0, os.SEEK_END)
                if existing_text and not existing_text.endswith(('\n', '\r')):
                    stream.write('\n')
                stream.write(key + '\n')
                stream.flush()
                os.fsync(stream.fileno())
                return 'saved'
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except (OSError, UnicodeError, ValueError):
        return 'error'
