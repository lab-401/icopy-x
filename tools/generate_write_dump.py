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

"""Generate valid dump files for write flow testing.

Called by write_common.sh after the read phase to fix the dump file
created by the mock (which has duplicated sector data).

Usage:
    python3 tools/generate_write_dump.py <fixture_path>

Reads TAG_TYPE and SCENARIO_RESPONSES from fixture.py, determines the
correct dump format, finds the most recent dump file, and overwrites
it with structurally valid data. Also ensures the key file exists.
"""

import os
import sys
import struct
import glob
import re

# UID extraction regex from hf 14a info response
UID_4B_RE = re.compile(r'UID:\s*([0-9A-Fa-f ]{11})')  # "2C AD C2 72"
UID_7B_RE = re.compile(r'UID:\s*([0-9A-Fa-f ]{20})')  # "04 A1 B2 C3 D4 E5 F6"

# --- MFC dump generation ---

def mfc_1k_dump(uid_bytes, sak=0x08):
    """Generate a valid MFC 1K binary dump (1024 bytes = 64 blocks)."""
    dump = bytearray(1024)
    # Block 0: UID + BCC + SAK + ATQA + manufacturer
    bcc = 0
    for b in uid_bytes:
        bcc ^= b
    block0 = bytearray(16)
    block0[0:len(uid_bytes)] = uid_bytes
    block0[len(uid_bytes)] = bcc
    block0[len(uid_bytes)+1] = sak
    block0[len(uid_bytes)+2] = 0x04  # ATQA low
    block0[len(uid_bytes)+3] = 0x00  # ATQA high
    # Fill rest with manufacturer data
    for i in range(len(uid_bytes)+4, 16):
        block0[i] = 0x62 + (i - len(uid_bytes) - 4)  # b, c, d, e, ...
    dump[0:16] = block0

    # Sector trailers at blocks 3, 7, 11, ..., 63
    trailer = bytes.fromhex('FFFFFFFFFFFF') + bytes.fromhex('FF078069') + bytes.fromhex('FFFFFFFFFFFF')
    for sector in range(16):
        trailer_block = sector * 4 + 3
        offset = trailer_block * 16
        dump[offset:offset+16] = trailer

    return bytes(dump)


def mfc_2k_dump(uid_bytes, sak=0x08):
    """Generate a valid MFC Plus 2K binary dump (2048 bytes = 128 blocks = 32 sectors)."""
    dump = bytearray(2048)
    # Block 0: UID + BCC + SAK + ATQA
    bcc = 0
    for b in uid_bytes:
        bcc ^= b
    block0 = bytearray(16)
    block0[0:len(uid_bytes)] = uid_bytes
    block0[len(uid_bytes)] = bcc
    block0[len(uid_bytes)+1] = sak
    block0[len(uid_bytes)+2] = 0x04  # ATQA low
    block0[len(uid_bytes)+3] = 0x00
    for i in range(len(uid_bytes)+4, 16):
        block0[i] = 0x62 + (i - len(uid_bytes) - 4)
    dump[0:16] = block0

    # Sector trailers at blocks 3, 7, 11, ..., 127 (32 sectors × 4 blocks each)
    trailer = bytes.fromhex('FFFFFFFFFFFF') + bytes.fromhex('FF078069') + bytes.fromhex('FFFFFFFFFFFF')
    for sector in range(32):
        trailer_block = sector * 4 + 3
        offset = trailer_block * 16
        dump[offset:offset+16] = trailer

    return bytes(dump)


def mfc_4k_dump(uid_bytes, sak=0x18):
    """Generate a valid MFC 4K binary dump (4096 bytes = 256 blocks)."""
    dump = bytearray(4096)
    # Block 0
    bcc = 0
    for b in uid_bytes:
        bcc ^= b
    block0 = bytearray(16)
    block0[0:len(uid_bytes)] = uid_bytes
    block0[len(uid_bytes)] = bcc
    block0[len(uid_bytes)+1] = sak
    block0[len(uid_bytes)+2] = 0x02  # ATQA low for 4K
    block0[len(uid_bytes)+3] = 0x00
    for i in range(len(uid_bytes)+4, 16):
        block0[i] = 0x62 + (i - len(uid_bytes) - 4)
    dump[0:16] = block0

    trailer = bytes.fromhex('FFFFFFFFFFFF') + bytes.fromhex('FF078069') + bytes.fromhex('FFFFFFFFFFFF')
    # Small sectors (0-31): 4 blocks each, trailer at block 3
    for sector in range(32):
        trailer_block = sector * 4 + 3
        offset = trailer_block * 16
        dump[offset:offset+16] = trailer
    # Large sectors (32-39): 16 blocks each, trailer at last block
    for sector in range(32, 40):
        first_block = 128 + (sector - 32) * 16
        trailer_block = first_block + 15
        offset = trailer_block * 16
        dump[offset:offset+16] = trailer

    return bytes(dump)


def mfc_mini_dump(uid_bytes, sak=0x09):
    """Generate a valid MFC Mini binary dump (320 bytes = 20 blocks = 5 sectors)."""
    dump = bytearray(320)
    bcc = 0
    for b in uid_bytes:
        bcc ^= b
    block0 = bytearray(16)
    block0[0:len(uid_bytes)] = uid_bytes
    block0[len(uid_bytes)] = bcc
    block0[len(uid_bytes)+1] = sak
    block0[len(uid_bytes)+2] = 0x04
    block0[len(uid_bytes)+3] = 0x00
    dump[0:16] = block0

    trailer = bytes.fromhex('FFFFFFFFFFFF') + bytes.fromhex('FF078069') + bytes.fromhex('FFFFFFFFFFFF')
    for sector in range(5):
        trailer_block = sector * 4 + 3
        offset = trailer_block * 16
        dump[offset:offset+16] = trailer

    return bytes(dump)


def iclass_dump(csn_bytes, key_bytes=None):
    """Generate a valid iCLASS binary dump (19 blocks × 8 bytes = 152 bytes).

    Block layout:
      0: CSN (Card Serial Number)
      1: Configuration
      2: ePurse
      3: Kd (debit key)
      4: Kc (credit key)
      5: Application Issuer Area
      6-18: Application data
    """
    blocks = [b'\x00' * 8] * 19
    blocks[0] = csn_bytes[:8].ljust(8, b'\x00')
    blocks[1] = bytes.fromhex('12FFFFFF7F1FFF3C')  # Config
    blocks[2] = bytes.fromhex('FEFFFFFFFFFFFFFF')  # ePurse
    if key_bytes:
        blocks[3] = key_bytes[:8].ljust(8, b'\x00')
        blocks[4] = key_bytes[:8].ljust(8, b'\x00')
    else:
        blocks[3] = bytes.fromhex('AEA684A6DAB21232')
        blocks[4] = bytes.fromhex('AEA684A6DAB21232')
    blocks[5] = bytes.fromhex('FFFFFFFFFFFFF3FF')
    # Application data blocks 6-18: fill with distinct non-zero data
    # so iclasswrite's getNeedWriteBlock detects differences from tag
    for i in range(6, 19):
        blocks[i] = bytes([i, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
    return b''.join(blocks)


def ul_dump(uid_bytes, page_count=20):
    """Generate a valid Ultralight/NTAG binary dump."""
    dump = bytearray(page_count * 4)
    # Page 0-1: UID (7 bytes split across pages)
    if len(uid_bytes) >= 7:
        dump[0:3] = uid_bytes[0:3]
        dump[3] = uid_bytes[0] ^ uid_bytes[1] ^ uid_bytes[2] ^ 0x88  # BCC0
        dump[4:8] = uid_bytes[3:7]
    # Page 2: BCC1 + internal
    if len(uid_bytes) >= 7:
        dump[8] = uid_bytes[3] ^ uid_bytes[4] ^ uid_bytes[5] ^ uid_bytes[6]  # BCC1
    # Page 3: OTP (all zeros for blank)
    # Pages 4+: user data (zeros)
    return bytes(dump)


# --- Key file generation ---

def generate_key_file(path, num_keys=104):
    """Generate a PM3 key dictionary file (6 bytes per key)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = bytes.fromhex('FFFFFFFFFFFF')
    with open(path, 'wb') as f:
        for _ in range(num_keys):
            f.write(key)


# --- EML file generation ---

def dump_to_eml(dump_bytes, block_size=16):
    """Convert binary dump to .eml text format (hex per line)."""
    lines = []
    for i in range(0, len(dump_bytes), block_size):
        block = dump_bytes[i:i+block_size]
        lines.append(block.hex().upper())
    return '\n'.join(lines) + '\n'


# --- Main ---

# Type → dump directory mapping
TYPE_TO_DIR = {
    0: 'mf1', 1: 'mf1', 25: 'mf1', 41: 'mf1', 42: 'mf1', 43: 'mf1', 44: 'mf1',
    2: 'mfu', 3: 'mfu', 4: 'mfu', 5: 'mfu', 6: 'mfu', 7: 'mfu',
    17: 'iclass', 18: 'iclass',
    19: 'icode',
    8: 'em410x', 9: 'hid', 10: 'indala', 11: 'awid', 12: 'ioprox',
    13: 'em4x05', 23: 't55xx', 24: 'em4x05',
    14: 'securakey', 15: 'viking', 16: 'pyramid',
    28: 'fdx', 29: 'gallagher', 30: 'jablotron', 31: 'keri',
    32: 'nedap', 33: 'noralsy', 34: 'pac', 35: 'paradox',
    36: 'presco', 37: 'visa2000', 45: 'nexwatch',
}

# UL/NTAG page counts
UL_PAGE_COUNTS = {2: 16, 3: 48, 4: 44, 5: 45, 6: 135, 7: 231}


SERIAL_RE = re.compile(r'Serial\s*:\s*([0-9A-Fa-f]+)')
CSN_RE = re.compile(r'CSN:\s*([0-9A-Fa-f ]+)')


def extract_csn(fixture_responses):
    """Extract CSN bytes from hf iclass info response."""
    for key in ['hf iclass info']:
        if key in fixture_responses:
            val = fixture_responses[key]
            if isinstance(val, tuple):
                resp = val[1]
            elif isinstance(val, list):
                resp = val[0][1] if val and isinstance(val[0], tuple) else ''
            else:
                resp = str(val)
            m = CSN_RE.search(resp)
            if m:
                return bytes.fromhex(m.group(1).replace(' ', ''))
    return None


def extract_uid(fixture_responses):
    """Extract UID bytes from hf 14a info response, or serial from EM4305 info."""
    # Try HF 14A first
    info_resp = ''
    for key in ['hf 14a info', 'hf 14a reader']:
        if key in fixture_responses:
            val = fixture_responses[key]
            if isinstance(val, tuple):
                info_resp = val[1]
            elif isinstance(val, list):
                info_resp = val[0][1] if val and isinstance(val[0], tuple) else ''
            else:
                info_resp = str(val)
            break

    # Try 7-byte UID first, then 4-byte
    m = UID_7B_RE.search(info_resp)
    if m:
        return bytes.fromhex(m.group(1).replace(' ', ''))
    m = UID_4B_RE.search(info_resp)
    if m:
        return bytes.fromhex(m.group(1).replace(' ', ''))

    # Try ISO15693/iCLASS UID from hf sea response
    for key in ['hf sea']:
        if key in fixture_responses:
            val = fixture_responses[key]
            if isinstance(val, tuple):
                resp = val[1]
            elif isinstance(val, list):
                resp = val[0][1] if val and isinstance(val[0], tuple) else ''
            else:
                resp = str(val)
            # ISO15693 UID: "UID: E0 04 01 00 12 34 56 78" (8 bytes)
            m = re.search(r'UID:\s*([0-9A-Fa-f ]{23})', resp)
            if m:
                return bytes.fromhex(m.group(1).replace(' ', ''))
            # Shorter UID formats
            m = re.search(r'UID:\s*([0-9A-Fa-f ]{11,})', resp)
            if m:
                return bytes.fromhex(m.group(1).strip().replace(' ', ''))

    # Try EM4305 serial from lf em 4x05_info
    for key in ['lf em 4x05_info']:
        if key in fixture_responses:
            val = fixture_responses[key]
            if isinstance(val, tuple):
                resp = val[1]
            elif isinstance(val, list):
                resp = val[0][1] if val and isinstance(val[0], tuple) else ''
            else:
                resp = str(val)
            m = SERIAL_RE.search(resp)
            if m:
                return bytes.fromhex(m.group(1))

    return bytes.fromhex('2CADC272')  # fallback


def find_most_recent_dump(dump_dir, pattern):
    """Find the highest-numbered dump file matching pattern.

    Files are named <prefix>_<N>.bin where N auto-increments.
    We want the highest N (most recently created by the read phase).
    """
    files = glob.glob(os.path.join(dump_dir, pattern))
    if not files:
        return None
    # Extract the numeric suffix and pick the highest
    numbered = []
    for f in files:
        m = re.search(r'_(\d+)\.bin$', f)
        if m:
            numbered.append((int(m.group(1)), f))
    if numbered:
        return max(numbered)[1]
    # Fallback to mtime
    return max(files, key=os.path.getmtime)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_write_dump.py <fixture_path>", file=sys.stderr)
        sys.exit(1)

    fixture_path = sys.argv[1]

    # Load fixture
    ns = {}
    with open(fixture_path) as f:
        exec(f.read(), ns)
    tag_type = ns.get('TAG_TYPE', 1)
    responses = ns.get('SCENARIO_RESPONSES', {})

    uid_bytes = extract_uid(responses)
    uid_hex = uid_bytes.hex().upper()
    csn_bytes = extract_csn(responses)

    dump_subdir = TYPE_TO_DIR.get(tag_type, 'mf1')
    dump_dir = f'/mnt/upan/dump/{dump_subdir}'

    # Ensure key file exists (needed for MFC types)
    if tag_type in (0, 1, 25, 41, 42, 43, 44):
        generate_key_file('/tmp/.keys/mf_tmp_keys')

    # For iCLASS types, find ALL dump files in the iclass directory
    # The filenames are created by hficlass.so as Iclass-{subtype}_{CSN}_N.bin
    if tag_type in (17, 18) and csn_bytes:
        csn_hex = csn_bytes.hex().upper()
        all_dumps = glob.glob(os.path.join(dump_dir, f'*{csn_hex}*.bin'))
        if not all_dumps:
            # Also try with partial CSN match (truncated in filenames)
            all_dumps = glob.glob(os.path.join(dump_dir, f'Iclass-*_{csn_hex[:16]}*.bin'))
        if not all_dumps:
            # Fallback: create with correct name pattern
            subtype = 'Elite' if tag_type == 18 else 'Legacy'
            all_dumps = [os.path.join(dump_dir, f'Iclass-{subtype}_{csn_hex}_1.bin')]
    else:
        # Overwrite ALL dump files matching this UID — we don't know which one
        # the .so will pass to WriteActivity as the bundle path.
        all_dumps = glob.glob(os.path.join(dump_dir, f'*_{uid_hex}_*.bin'))
        # Also try wildcard match (EM4305 uses Serial not UID in filename)
        if not all_dumps:
            all_dumps = glob.glob(os.path.join(dump_dir, f'*{uid_hex}*.bin'))
        if not all_dumps:
            # Read phase might not have created a file yet — create one with appropriate name
            if tag_type == 24:  # EM4305
                all_dumps = [os.path.join(dump_dir, f'EM4305_{uid_hex}_1.bin')]
            elif tag_type == 23:  # T55XX
                all_dumps = [os.path.join(dump_dir, f'T55xx_{uid_hex}_00000000_1.bin')]
            elif tag_type in (2, 3, 4, 5, 6, 7):  # UL/NTAG
                prefix = {2: 'M0-UL', 3: 'M0-ULC', 4: 'M0-ULEV1', 5: 'NTAG213', 6: 'NTAG215', 7: 'NTAG216'}.get(tag_type, 'M0-UL')
                all_dumps = [os.path.join(dump_dir, f'{prefix}_{uid_hex}_1.bin')]
            elif tag_type in (19, 46):  # ISO15693
                all_dumps = [os.path.join(dump_dir, f'ICODE_{uid_hex}_1.bin')]
            else:
                all_dumps = [os.path.join(dump_dir, f'M1-1K-4B_{uid_hex}_1.bin')]

    # Generate correct dump data based on type
    if tag_type in (1, 42, 43, 44):  # MFC 1K variants
        dump_data = mfc_1k_dump(uid_bytes)
    elif tag_type == 26:  # MFC Plus 2K (32 sectors × 4 blocks = 128 blocks × 16 = 2048 bytes)
        dump_data = mfc_2k_dump(uid_bytes)
    elif tag_type in (0, 41):  # MFC 4K
        dump_data = mfc_4k_dump(uid_bytes)
    elif tag_type == 25:  # MFC Mini
        dump_data = mfc_mini_dump(uid_bytes)
    elif tag_type in (2, 3, 4, 5, 6, 7):  # UL/NTAG
        pages = UL_PAGE_COUNTS.get(tag_type, 20)
        dump_data = ul_dump(uid_bytes, pages)
    elif tag_type in (17, 18):  # iCLASS Legacy/Elite
        dump_csn = csn_bytes if csn_bytes else bytes.fromhex('000B0FFFF7FF12E0')
        dump_data = iclass_dump(dump_csn)
    elif tag_type in (19, 46):  # ISO15693
        # ISO15693 dump: 14 blocks × 8 bytes = 112 bytes
        # Block 0 contains UID (8 bytes)
        dump_data = uid_bytes[:8].ljust(8, b'\x00') + b'\x00' * 104
    else:
        # LF/other — create minimal dump
        dump_data = uid_bytes + b'\x00' * max(0, 64 - len(uid_bytes))

    # Overwrite ALL matching dump .bin files
    for dump_file in all_dumps:
        os.makedirs(os.path.dirname(dump_file), exist_ok=True)
        with open(dump_file, 'wb') as f:
            f.write(dump_data)

        # Also create/overwrite .eml
        eml_file = dump_file.replace('.bin', '.eml')
        if tag_type in (17, 18):
            block_size = 8  # iCLASS: 8 bytes per block
        elif tag_type in (2, 3, 4, 5, 6, 7):
            block_size = 4  # UL/NTAG: 4 bytes per page
        else:
            block_size = 16  # MFC/other: 16 bytes per block
        with open(eml_file, 'w') as f:
            f.write(dump_to_eml(dump_data, block_size))

    print(f'[DUMP] Type {tag_type}, UID {uid_hex}, {len(dump_data)} bytes → {len(all_dumps)} files fixed')


if __name__ == '__main__':
    main()
