#!/usr/bin/env python3

##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Seed dump files for QEMU Write/DumpFiles walker testing.

Creates minimal valid dump files in /mnt/upan/dump/* directories
so CardWalletActivity can list and operate on them.

Filenames match REAL DEVICE format (from trace_dump_files_20260403.txt
and 160 files pulled from real hardware):
  MF1:    M1-1K-4B_{UID}_{INDEX}.bin      (1024 bytes for 1K)
  MF4K:   M1-4K-4B_{UID}_{INDEX}.bin      (4096 bytes)
  Mini:   M1-Mini-4B_{UID}_{INDEX}.bin     (320 bytes)
  MFU:    M0-UL_{UID}_{INDEX}.bin          (120 bytes)
  iClass: Iclass-Elite_{UID}_{INDEX}.bin   (152 bytes)
  T55xx:  T55xx_{B0}_{B1}_{B2}_{INDEX}.bin (48 bytes)
  EM410x: EM410x-ID_{ID}_{INDEX}.txt       (text)
  FDX:    FDX-ID_{CC-NC}_{INDEX}.txt       (text)
  AWID:   AWID-ID_{FC,CN}_{INDEX}.txt      (text)
  etc.

Usage:
    python3 tools/seed_dump_files.py              # seed all types
    python3 tools/seed_dump_files.py --type mf1    # seed one type
    python3 tools/seed_dump_files.py --clean       # remove all test dumps
"""
import os, argparse
from pathlib import Path

BASE = Path("/mnt/upan/dump")

# Type -> (directory, [(filename, content), ...])
# Filenames match real device format. Content is minimal valid data.
DUMP_TYPES = {
    # === HF types ===
    'mf1': {
        'path': 'mf1',
        'files': [
            # M1-{size}-{uidLen}B_{UID}_{index}.{ext}
            ('M1-1K-4B_DAEFB416_1.bin', b'\xDA\xEF\xB4\x16' + b'\x00' * 1020),  # 1024 bytes
        ],
    },
    'mf1_4k': {
        'path': 'mf1',
        'files': [
            ('M1-4K-4B_E93C5221_1.bin', b'\xE9\x3C\x52\x21' + b'\x00' * 4092),  # 4096 bytes
        ],
    },
    'mf1_mini': {
        'path': 'mf1',
        'files': [
            ('M1-Mini-4B_8800E177_1.bin', b'\x88\x00\xE1\x77' + b'\x00' * 316),  # 320 bytes
        ],
    },
    'mfu': {
        'path': 'mfu',
        'files': [
            # M0-UL_{UID}_{index}.bin — 120 bytes (real device size)
            ('M0-UL_04DDEEFF001122_1.bin', b'\x04\xDD\xEE\xFF\x00\x11\x22' + b'\x00' * 113),
        ],
    },
    'iclass': {
        'path': 'iclass',
        'files': [
            # Iclass-Elite_{UID}_{index}.bin — 152 bytes (real device size)
            ('Iclass-Elite_4A678E15FEFF12E0_1.bin', b'\x4A\x67\x8E\x15\xFE\xFF\x12\xE0' + b'\x00' * 144),
        ],
    },
    'icode': {
        'path': 'icode',
        'files': [
            ('ICODE_E004010012345678_1.bin', b'\xE0\x04\x01\x00\x12\x34\x56\x78' + b'\x00' * 120),
        ],
    },
    'legic': {
        'path': 'legic',
        'files': [
            ('Legic_AABBCCDD_1.bin', b'\xAA\xBB\xCC\xDD' + b'\x00' * 252),
        ],
    },
    'felica': {
        'path': 'felica',
        'files': [
            # FeliCa_{UID}_{index}.txt — real device format
            ('FeliCa_010108018D162D1A_1.txt', b'FeliCa IDm: 010108018D162D1A\n'),
        ],
    },
    # === LF ID types — text format ===
    'em410x': {
        'path': 'em410x',
        'files': [
            # EM410x-ID_{ID}_{index}.txt
            ('EM410x-ID_0F0368568B_1.txt', b'EM410x ID: 0F0368568B\nRaw: 0FFE8C6A00\n'),
        ],
    },
    'hid': {
        'path': 'hid',
        'files': [
            ('HID-ID_200068012345_1.txt', b'HID Prox ID\nRaw: 200068012345\nFC: 123, CN: 4567\n'),
        ],
    },
    'indala': {
        'path': 'indala',
        'files': [
            ('Indala-ID_A000000000123456_1.txt', b'Indala ID\nRaw: A0 00 00 00 00 12 34 56\n'),
        ],
    },
    'awid': {
        'path': 'awid',
        'files': [
            # AWID-ID_{spec}_{index}.txt — real device format
            ('AWID-ID_FC123-CN4567_1.txt', b'AWID ID\nFC: 123, CN: 4567\nRaw: 2004800000\n'),
        ],
    },
    'ioprox': {
        'path': 'ioprox',
        'files': [
            ('IOProx-ID_007E0180A5_1.txt', b'IO Prox ID\nXSF(01)01:12345\nRaw: 007E0180A5\n'),
        ],
    },
    'gproxii': {
        'path': 'gproxii',
        'files': [
            ('GProxII-ID_1234567800_1.txt', b'G-Prox II ID\nFC: 123, CN: 4567\nRaw: 1234567800\n'),
        ],
    },
    'securakey': {
        'path': 'securakey',
        'files': [
            ('Securakey-ID_AABBCCDD00112233_1.txt', b'Securakey ID\nRaw: AABBCCDD00112233\n'),
        ],
    },
    'viking': {
        'path': 'viking',
        'files': [
            ('Viking-ID_12345678_1.txt', b'Viking ID\nCard: 12345678\nRaw: 1234567800112233\n'),
        ],
    },
    'pyramid': {
        'path': 'pyramid',
        'files': [
            ('Pyramid-ID_0001E2403B_1.txt', b'Pyramid ID\nFC: 123, CN: 4567\nRaw: 0001E2403B\n'),
        ],
    },
    'fdx': {
        'path': 'fdx',
        'files': [
            # FDX-ID_{CC-NC}_{index}.txt — real device format
            ('FDX-ID_0060-030207938416_1.txt', b'FDX-B ID\nAnimal ID: 0060-030207938416\nRaw: 0103E820C0\n'),
        ],
    },
    'gallagher': {
        'path': 'gallagher',
        'files': [
            ('Gallagher-ID_AABBCCDDEE001122_1.txt', b'Gallagher ID\nRaw: AABBCCDDEE001122\n'),
        ],
    },
    'jablotron': {
        'path': 'jablotron',
        'files': [
            ('Jablotron-ID_FF010201234568_1.txt', b'Jablotron ID\nCard: FF010201234568\nRaw: 1234567800112233\n'),
        ],
    },
    'keri': {
        'path': 'keri',
        'files': [
            ('Keri-ID_12345678_1.txt', b'KERI ID\nInternal ID: 12345678\nRaw: 1234567800112233\n'),
        ],
    },
    'nedap': {
        'path': 'nedap',
        'files': [
            ('Nedap-ID_12345678_1.txt', b'NEDAP ID\nCard: 12345678\nRaw: 1234567800112233\n'),
        ],
    },
    'noralsy': {
        'path': 'noralsy',
        'files': [
            ('Noralsy-ID_12345678_1.txt', b'Noralsy ID\nCard: 12345678\nRaw: 1234567800112233\n'),
        ],
    },
    'pac': {
        'path': 'pac',
        'files': [
            ('PAC-ID_FF01020304050607_1.txt', b'PAC/Stanley ID\nCard: FF01020304050607\nRaw: AABBCCDD00112233\n'),
        ],
    },
    'paradox': {
        'path': 'paradox',
        'files': [
            ('Paradox-ID_AABBCCDD00112233_1.txt', b'Paradox ID\nFC: 123, CN: 4567\nRaw: AABBCCDD00112233\n'),
        ],
    },
    'presco': {
        'path': 'presco',
        'files': [
            ('Presco-ID_12345678_1.txt', b'Presco ID\nCard: 12345678\nRaw: 123456780011223344556677\n'),
        ],
    },
    'visa2000': {
        'path': 'visa2000',
        'files': [
            ('Visa2000-ID_12345678_1.txt', b'Visa2000 ID\nCard: 12345678\nRaw: 1234567800112233\n'),
        ],
    },
    'nexwatch': {
        'path': 'nexwatch',
        'files': [
            ('NexWatch-ID_AABBCCDD00112233_1.txt', b'NexWatch ID\nID: AABBCCDD00112233\nRaw: AABBCCDD0011223344556677\n'),
        ],
    },
    # === Special formats ===
    't55xx': {
        'path': 't55xx',
        'files': [
            # T55xx_{B0}_{B1}_{B2}_{index}.bin — 48 bytes (real device size)
            # Block 0 = 00148040 matches real device file from trace_dump_files_em410x_t55xx_write_20260405.txt
            ('T55xx_00148040_00000000_00000000_1.bin', b'\x00\x14\x80\x40' + b'\x00' * 44),
        ],
    },
    'em4x05': {
        'path': 'em4x05',
        'files': [
            ('EM4x05_00148040_1.bin', b'\x00\x14\x80\x40' + b'\x00' * 60),  # 64 bytes
        ],
    },
    'hf14a': {
        'path': 'hf14a',
        'files': [
            ('HF14A_04AABBCCDDEE_1.bin', b'\x04\xAA\xBB\xCC\xDD\xEE' + b'\x00' * 58),
        ],
    },
}


def seed(type_filter=None):
    """Create dump files for all (or filtered) types."""
    count = 0
    for type_key, cfg in DUMP_TYPES.items():
        if type_filter and type_key != type_filter:
            continue
        dump_dir = BASE / cfg['path']
        dump_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in cfg['files']:
            fpath = dump_dir / fname
            fpath.write_bytes(content)
            count += 1
            print(f'  [SEED] {fpath} ({len(content)} bytes)')
    print(f'\nSeeded {count} dump files across {len(DUMP_TYPES)} types')
    # Also create keys directory
    keys_dir = Path("/mnt/upan/keys/mf1")
    keys_dir.mkdir(parents=True, exist_ok=True)


def clean():
    """Remove all test dump files."""
    count = 0
    for type_key, cfg in DUMP_TYPES.items():
        dump_dir = BASE / cfg['path']
        if dump_dir.exists():
            for fname, _ in cfg['files']:
                fpath = dump_dir / fname
                if fpath.exists():
                    fpath.unlink()
                    count += 1
    print(f'Cleaned {count} test dump files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', help='Seed only this type')
    parser.add_argument('--clean', action='store_true', help='Remove test dumps')
    args = parser.parse_args()

    if args.clean:
        clean()
    else:
        seed(args.type)
