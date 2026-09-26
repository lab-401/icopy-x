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

"""Save a Chameleon emulator slot as an iCopy-X dump.

Used by the Chameleon Dump plugin's read flow (both the Ultra and Tiny
backends).  Produces files that match the iCopy-X filename convention
(``src/middleware/appfiles.py``) so the built-in Dump Files browser, the
write flow and card_notes all recognise them:

    mf1     M1-<1K|4K|Plus-2K|Mini>-<4B|7B>_<uid>_<n>.bin  (+ .json)
    mfu     NTAG213|NTAG215|NTAG216_<uid>_<n>.bin           (+ .json)
    em410x  EM410x-ID_<id>_<n>.txt

The ``_n`` index auto-increments, so an existing dump is never overwritten.
Every file is written atomically (temp file + ``os.replace``) so a crash
mid-write cannot leave a half-written dump behind.
"""

import json
import os
import tempfile

DUMP_ROOT = '/mnt/upan/dump'

# iCopy-X dump sub-directories (lowercase; see appfiles.DIR_NAME_*).
FAMILY_SUBDIR = {
    'mf1': 'mf1',
    'mfu': 'mfu',
    'em410x': 'em410x',
}

# MIFARE Classic block count -> filename size token (appfiles/hfmfread).
MFC_SIZE_TOKEN = {
    20: 'Mini',
    64: '1K',
    128: 'Plus-2K',
    256: '4K',
}

MAX_INDEX = 999

# PM3 mfu .bin layout understood by the middleware and the writer plugins:
# version(8) | 4 | signature(32) | counters(12) | pages(N*4).
_MFU_GAP = b'\x00' * 4
_MFU_COUNTERS = b'\x00' * 12


class DumpError(Exception):
    """Raised when a slot cannot be turned into a valid dump."""


def default_dir(family):
    """Canonical directory for a dump family."""
    try:
        sub = FAMILY_SUBDIR[family]
    except KeyError:
        raise DumpError('unknown dump family: %s' % family)
    return '%s/%s' % (DUMP_ROOT, sub)


def _check_uid(uid):
    text = str(uid).strip().upper()
    if not text or not all(c in '0123456789ABCDEF' for c in text):
        raise DumpError('bad UID for filename: %r' % (uid,))
    return text


def next_path(directory, prefix, uid, ext):
    """Next free ``<prefix>_<uid>_<n><ext>`` path (creates *directory*)."""
    uid = _check_uid(uid)
    os.makedirs(directory, exist_ok=True)
    path = None
    for n in range(1, MAX_INDEX + 1):
        path = os.path.join(directory, '%s_%s_%d%s' % (prefix, uid, n, ext))
        if not os.path.exists(path):
            return path
    raise DumpError('no free %s_%s_* index in %s' % (prefix, uid, directory))


def _write_atomic(path, data):
    directory = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.dump-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_text(path, text):
    _write_atomic(path, text.encode('utf-8'))


def mfc_size_token(blocks):
    """Filename size token for a MIFARE Classic block count."""
    try:
        return MFC_SIZE_TOKEN[int(blocks)]
    except (KeyError, TypeError, ValueError):
        raise DumpError('unsupported MIFARE Classic size: %r blocks' % (blocks,))


def mf1_prefix(blocks, uid_len):
    """``M1-<size>-<4B|7B>`` prefix for a MIFARE Classic dump."""
    return 'M1-%s-%dB' % (mfc_size_token(blocks), int(uid_len))


def mfu_uid(pages):
    """7-byte UID from an MF0/NTAG page image (page 0 + page 1)."""
    if len(pages) < 8:
        raise DumpError('MF0 page image too short for a UID')
    return pages[0:3] + pages[4:8]


def encode_mfu_bin(pages, version=None, signature=None):
    """PM3-compatible mfu ``.bin`` image: version + signature + pages."""
    version = (version or b'')[:8].ljust(8, b'\x00')
    signature = (signature or b'')[:32].ljust(32, b'\x00')
    return version + _MFU_GAP + signature + _MFU_COUNTERS + bytes(pages)


def _mf1_json(uid, data, atqa=None, sak=None):
    blocks = {}
    for i in range(len(data) // 16):
        blocks[str(i)] = data[i * 16:(i + 1) * 16].hex().upper()
    card = {'UID': uid}
    if atqa:
        card['ATQA'] = atqa
    if sak:
        card['SAK'] = sak
    return json.dumps({
        'Created': 'proxmark3',
        'FileType': 'mfc v2',
        'Card': card,
        'blocks': blocks,
    }, indent=2)


def _mfu_json(uid, pages, version=None, signature=None):
    blocks = {}
    for i in range(len(pages) // 4):
        blocks[str(i)] = pages[i * 4:(i + 1) * 4].hex().upper()
    card = {'UID': uid}
    if version:
        card['Version'] = version.hex().upper()
    if signature:
        card['Signature'] = signature.hex().upper()
    return json.dumps({'Card': card, 'blocks': blocks})


def save_mf1(directory, blocks, uid_len, uid, data, atqa=None, sak=None):
    """Write a MIFARE Classic dump (``.bin`` + ``.json``); return the path."""
    data = bytes(data)
    if len(data) != int(blocks) * 16:
        raise DumpError('%d bytes for a %d-block MIFARE Classic dump' % (
            len(data), blocks))
    path = next_path(directory, mf1_prefix(blocks, uid_len), uid, '.bin')
    _write_atomic(path, data)
    _write_text(os.path.splitext(path)[0] + '.json',
                _mf1_json(_check_uid(uid), data, atqa=atqa, sak=sak))
    return path


def save_mfu(directory, prefix, uid, pages, version=None, signature=None):
    """Write an MF0/NTAG dump (``.bin`` + ``.json``); return the path."""
    pages = bytes(pages)
    if len(pages) < 8:
        raise DumpError('MF0 page image too short')
    uid = _check_uid(uid)
    path = next_path(directory, prefix, uid, '.bin')
    _write_atomic(path, encode_mfu_bin(pages, version, signature))
    _write_text(os.path.splitext(path)[0] + '.json',
                _mfu_json(uid, pages, version=version, signature=signature))
    return path


def save_em410x(directory, uid):
    """Write an EM410x LF dump (``.txt``); return the path."""
    uid = _check_uid(uid)
    path = next_path(directory, 'EM410x-ID', uid, '.txt')
    _write_text(path, '%s\n%s\n' % (uid, uid))
    return path
