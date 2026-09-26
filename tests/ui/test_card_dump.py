"""Chameleon Dump plugin: iCopy-X dump naming and writers (dump_writer)."""

import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dump_writer():
    path = os.path.join(REPO, 'plugins', 'chameleon_dump', 'dump_writer.py')
    spec = importlib.util.spec_from_file_location('dump_writer_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


card_dump = _load_dump_writer()


def _uid_pages(uid_hex):
    """Build a 2-page NTAG image whose UID is *uid_hex* (14 hex)."""
    raw = bytes.fromhex(uid_hex)
    return raw[0:3] + b'\x88' + raw[3:7]


# ----------------------------------------------------------------------
# Naming
# ----------------------------------------------------------------------

def test_mfc_size_token_and_prefix():
    assert card_dump.mfc_size_token(64) == '1K'
    assert card_dump.mfc_size_token(256) == '4K'
    assert card_dump.mfc_size_token(128) == 'Plus-2K'
    assert card_dump.mfc_size_token(20) == 'Mini'
    assert card_dump.mf1_prefix(64, 4) == 'M1-1K-4B'
    assert card_dump.mf1_prefix(64, 7) == 'M1-1K-7B'
    with pytest.raises(card_dump.DumpError):
        card_dump.mfc_size_token(32)


def test_default_dir():
    assert card_dump.default_dir('mf1') == '/mnt/upan/dump/mf1'
    assert card_dump.default_dir('mfu') == '/mnt/upan/dump/mfu'
    assert card_dump.default_dir('em410x') == '/mnt/upan/dump/em410x'
    with pytest.raises(card_dump.DumpError):
        card_dump.default_dir('t55xx')


def test_next_path_increments(tmp_path):
    d = str(tmp_path)
    p1 = card_dump.next_path(d, 'M1-1K-4B', 'DAEFB416', '.bin')
    assert os.path.basename(p1) == 'M1-1K-4B_DAEFB416_1.bin'
    open(p1, 'wb').close()
    p2 = card_dump.next_path(d, 'M1-1K-4B', 'DAEFB416', '.bin')
    assert os.path.basename(p2) == 'M1-1K-4B_DAEFB416_2.bin'


def test_next_path_rejects_bad_uid(tmp_path):
    with pytest.raises(card_dump.DumpError):
        card_dump.next_path(str(tmp_path), 'M1-1K-4B', '../evil', '.bin')


# ----------------------------------------------------------------------
# MIFARE Classic
# ----------------------------------------------------------------------

def test_save_mf1_bin_and_json(tmp_path):
    data = bytes(range(256)) * 4  # 1024 bytes = 64 blocks
    path = card_dump.save_mf1(str(tmp_path), 64, 4, 'daefb416', data,
                              atqa='0400', sak='08')
    assert os.path.basename(path) == 'M1-1K-4B_DAEFB416_1.bin'
    assert open(path, 'rb').read() == data

    doc = json.load(open(os.path.splitext(path)[0] + '.json'))
    assert doc['Card']['UID'] == 'DAEFB416'
    assert doc['Card']['ATQA'] == '0400'
    assert doc['Card']['SAK'] == '08'
    assert len(doc['blocks']) == 64
    assert doc['blocks']['0'] == data[:16].hex().upper()
    assert doc['blocks']['63'] == data[63 * 16:64 * 16].hex().upper()


def test_save_mf1_rejects_wrong_size(tmp_path):
    with pytest.raises(card_dump.DumpError):
        card_dump.save_mf1(str(tmp_path), 64, 4, 'DAEFB416', b'\x00' * 16)


# ----------------------------------------------------------------------
# NTAG / MF0
# ----------------------------------------------------------------------

def test_encode_mfu_bin_layout():
    pages = b'\x01\x02\x03\x04' * 4
    version = bytes.fromhex('0004040201000F03')
    signature = bytes.fromhex('AA' * 32)
    blob = card_dump.encode_mfu_bin(pages, version, signature)
    assert len(blob) == 56 + len(pages)
    assert blob[0:8] == version
    assert blob[12:44] == signature
    assert blob[56:] == pages


def test_mfu_uid_skips_bcc():
    pages = bytes.fromhex('1D3232950E950000')  # uid 1D32320E950000
    assert card_dump.mfu_uid(pages).hex().upper() == '1D32320E950000'


def test_save_mfu_bin_and_json(tmp_path):
    pages = bytes(range(180))
    version = bytes.fromhex('0004040201000F03')
    signature = bytes.fromhex('BB' * 32)
    path = card_dump.save_mfu(str(tmp_path), 'NTAG213', '1d32320e950000',
                              pages, version=version, signature=signature)
    assert os.path.basename(path) == 'NTAG213_1D32320E950000_1.bin'
    blob = open(path, 'rb').read()
    assert len(blob) == 236
    assert blob[56:] == pages

    doc = json.load(open(os.path.splitext(path)[0] + '.json'))
    assert doc['Card']['UID'] == '1D32320E950000'
    assert doc['Card']['Version'] == version.hex().upper()
    assert doc['Card']['Signature'] == signature.hex().upper()
    assert doc['blocks']['0'] == pages[:4].hex().upper()
    assert doc['blocks']['44'] == pages[44 * 4:45 * 4].hex().upper()


def test_save_mfu_defaults_missing_metadata(tmp_path):
    pages = bytes(180)
    path = card_dump.save_mfu(str(tmp_path), 'NTAG213', '00112233445566', pages)
    blob = open(path, 'rb').read()
    assert blob[0:8] == b'\x00' * 8
    assert blob[12:44] == b'\x00' * 32


# ----------------------------------------------------------------------
# EM410x
# ----------------------------------------------------------------------

def test_save_em410x(tmp_path):
    path = card_dump.save_em410x(str(tmp_path), '0000bc614e')
    assert os.path.basename(path) == 'EM410x-ID_0000BC614E_1.txt'
    assert open(path).read() == '0000BC614E\n0000BC614E\n'


def test_writes_leave_no_temp_files(tmp_path):
    card_dump.save_mf1(str(tmp_path), 64, 4, 'DAEFB416', bytes(1024))
    card_dump.save_mfu(str(tmp_path), 'NTAG213', '00112233445566', bytes(180))
    card_dump.save_em410x(str(tmp_path), '0000BC614E')
    leftovers = [n for n in os.listdir(str(tmp_path)) if n.startswith('.dump-')]
    assert leftovers == []
