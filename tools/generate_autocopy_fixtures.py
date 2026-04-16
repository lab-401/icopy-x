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

"""Generate fixture.py + .sh files for ALL ~45 Auto-Copy flow test scenarios.

  1.
  2. docs/traces/trace_autocopy_mf1k_standard.txt
  3. docs/Real_Hardware_Intel/full_read_write_trace_20260327.txt
  4. docs/Real_Hardware_Intel/awid_write_trace_20260328.txt
  5. docs/Real_Hardware_Intel/fdxb_t55_write_trace_20260328.txt
  6. docs/Real_Hardware_Intel/t55_to_t55_write_trace_20260328.txt
  7. docs/Real_Hardware_Intel/mf4k_read_trace_20260328.txt
  8. docs/Real_Hardware_Intel/mf4k_nonmagic_app_trace_20260328.txt
  9. docs/v1090_strings/ (keyword verification)

CRITICAL:
  - Every PM3 command, response string, keyword, and return code comes from
    the above ground-truth sources. Nothing is copy-pasted from existing
    read/write test fixtures. Existing fixture.py files are referenced for
    STRUCTURAL FORMAT ONLY (dict layout, sequential response syntax).
  - startPM3Task returns 1=success, -1=timeout. Mock returns 1 for matched commands.
  - For LF tag scan: HF stages must PASS THROUGH (return 1 with no-match text, NOT -1).
  - All LF clones include T55XX DRM sequence (pw 20206666 to block 7).
  - LF verify: lfverify.verify_t55xx() re-scans via lf sea. Fixture must have
    lf sea response containing the correct tag keyword.
"""

import os
import stat
import textwrap

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS_DIR = os.path.join(PROJECT, 'tests', 'flows', 'auto-copy', 'scenarios')

# ============================================================================
# Ground-truth PM3 response constants
# Derived from V1090_AUTOCOPY_FLOW_COMPLETE.md + real device traces
# ============================================================================

# --- HF passthrough responses (scan pipeline must continue for LF tags) ---
# Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6
# hf 14a info with no tag must return ret=1 with no-match content (not -1)
HF14A_NO_TAG = """\
[!] Card doesn't support standard iso14443-3 anticollision
"""

HFSEA_NO_TAG = """\
[!] No known/supported 13.56 MHz tags found
"""

LFSEA_NO_TAG = """\
[!] No data found!
[-] No known 125/134 kHz tags found!
"""

# --- LF write common responses ---
# Source: awid_write_trace_20260328.txt, fdxb_t55_write_trace_20260328.txt
LF_WIPE_RESP = """\

[=] Begin wiping T55x7 tag

[=] Default configation block 000880E0
[=] Writing page 0  block: 00  data: 0x000880E0 pwd: 0x20206666
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
"""

# Source: awid_write_trace_20260328.txt line 18
LF_DETECT_AFTER_WIPE = """\
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
"""

# Source: awid_write_trace_20260328.txt line 29-31
LF_WRITE_B7_RESP = """[=] Writing page 0  block: 07  data: 0x20206666
"""

LF_WRITE_B0_DRM_RESP = """[=] Writing page 0  block: 00  data: 0x00098090
"""

LF_DETECT_WITH_PW = """\
[=]      Chip Type      : T55x7
[=]      Modulation     : FSK2a
[=]      Bit Rate       : 4 - RF/50
[=]      Inverted       : Yes
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00107070
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : Yes
"""

# --- MF Classic: fchk response builder ---
# Source: trace_autocopy_mf1k_standard.txt line 19-21
# fchk returns found keys in table format
def _fchk_all_found(num_sectors, size_flag):
    """Build fchk response showing all keys found with default key."""
    lines = []
    lines.append('[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys\n')
    lines.append('[=] Running strategy 1\n')
    total = num_sectors * 2
    lines.append(f'[=] Chunk: 1.1s | found {total}/{total} keys (85)\n')
    lines.append(f'[=] time in checkkeys (fast) 1.1s\n\n\n')
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(num_sectors):
        lines.append(f'[+] | {s:03d} | ffffffffffff   | 1 | ffffffffffff   | 1 |\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] ( 0:Failed / 1:Success)\n')
    return ''.join(lines)

def _fchk_no_keys(num_sectors, size_flag):
    """Build fchk response showing no keys found."""
    lines = []
    lines.append('[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys\n')
    lines.append('[=] Running strategy 1\n')
    total = num_sectors * 2
    lines.append(f'[=] Chunk: 1.1s | found 0/{total} keys (85)\n')
    lines.append(f'[=] time in checkkeys (fast) 1.1s\n\n\n')
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(num_sectors):
        lines.append(f'[+] | {s:03d} | ------------   | 0 | ------------   | 0 |\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] ( 0:Failed / 1:Success)\n')
    return ''.join(lines)

def _fchk_partial_keys(num_sectors, found_a=8, found_b=0):
    """Build fchk response showing partial keys found."""
    lines = []
    lines.append('[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys\n')
    lines.append('[=] Running strategy 1\n')
    total_found = found_a + found_b
    total = num_sectors * 2
    lines.append(f'[=] Chunk: 1.1s | found {total_found}/{total} keys (85)\n')
    lines.append(f'[=] time in checkkeys (fast) 1.1s\n\n\n')
    lines.append('[+] found keys:\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] | Sec | key A          |res| key B          |res|\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    for s in range(num_sectors):
        ka = 'ffffffffffff   | 1' if s < found_a else '------------   | 0'
        kb = 'ffffffffffff   | 1' if s < found_b else '------------   | 0'
        lines.append(f'[+] | {s:03d} | {ka} | {kb} |\n')
    lines.append('[+] |-----|----------------|---|----------------|---|\n')
    lines.append('[+] ( 0:Failed / 1:Success)\n')
    return ''.join(lines)

# --- MF Classic: rdsc response ---
# Source: trace_autocopy_mf1k_standard.txt line 26-28
def _rdsc_response():
    return """\
\\n--sector no 0, key B - FF FF FF FF FF FF  \\n\\nisOk:01\\n  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \\n  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \\n  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \\n  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF \\n"""

# --- HF14A info for MF Classic ---
# Source: full_read_write_trace_20260327.txt line 12
MF1K_HF14A_INFO = """\

[+]  UID: B7 78 5E 50
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+]    MIFARE Plus 2K / Plus EV1 2K
[+]    MIFARE Plus CL2 2K / Plus CL2 EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""

# Source: mf4k_read_trace_20260328.txt (SAK 18 = 4K)
MF4K_HF14A_INFO = """\

[+]  UID: AA BB CC DD
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""

# Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 (Gen1a cgetblk success)
CGETBLK_NOT_GEN1A = """\
--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
"""

CGETBLK_GEN1A = """\
--block number: 0
Block 0: 11223344080400626364656667686970
"""

# Source: full_read_write_trace_20260327.txt wrbl responses
WRBL_SUCCESS = """\
--block no 0, key A - FF FF FF FF FF FF
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
isOk:01
"""

WRBL_FAIL = """\
--block no 0, key A - FF FF FF FF FF FF
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
isOk:00
"""

# ============================================================================
# LF TAG DEFINITIONS — from V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6
# ============================================================================
LF_TAG_DEFS = {
    # (tag_name, type_code, lf_sea_keyword, read_cmd, read_response, clone_cmd, clone_response, lf_sea_verify)
    'em410x': {
        'type_code': 8,
        'lf_sea_keyword': 'Valid EM410x ID found',
        'lf_sea_response': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]

[+] EM410x pattern found

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
HoneyWell IdentKey {{
DEZ 8          : 06903435
DEZ 10         : 0867656267
}}
Other          : 22155_003_06903435
Pattern Paxton : 1642715 [0x190F8B]

[+] Valid EM410x ID found!
""",
        'read_cmd': 'lf em 410x_read',
        'read_response': """\
[+] EM410x - Tag ID: 0F0368568B
""",
        # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3
        'clone_cmd': 'lf em 410x_write',
        'clone_response': """\
[+] Writing T55x7 tag with UID 0x0F0368568B
[+] Blk | Data
[+] ----+------------
[+]  00 | 00148040
""",
        'lf_sea_verify': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] EM410x pattern found

EM TAG ID      : 0F0368568B
[+] Valid EM410x ID found!
""",
    },
    'hid': {
        'type_code': 9,
        'lf_sea_keyword': 'Valid HID Prox ID found',
        'lf_sea_response': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
""",
        'read_cmd': 'lf hid read',
        'read_response': """\
[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
[+] Raw: 200068012345
""",
        'clone_cmd': 'lf hid clone',
        'clone_response': """\
[+] Preparing to clone HID to T55x7
""",
        'lf_sea_verify': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
""",
    },
    'indala': {
        'type_code': 10,
        'lf_sea_keyword': 'Valid Indala ID found',
        'lf_sea_response': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] Valid Indala ID found!
[+] Raw: A0000000001234560000000000000000
""",
        'read_cmd': 'lf indala read',
        'read_response': """\
[+] Valid Indala ID found!
[+] Raw: A0000000001234560000000000000000
""",
        'clone_cmd': 'lf indala clone',
        'clone_response': """\
[+] Preparing to clone Indala to T55x7
""",
        'lf_sea_verify': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] Valid Indala ID found!
[+] Raw: A0000000001234560000000000000000
""",
    },
    'awid': {
        'type_code': 11,
        # Source: awid_write_trace_20260328.txt
        'lf_sea_keyword': 'AWID',
        'lf_sea_response': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] AWID - len: 222 -unknown- (63198) - Wiegand: b4ddede7e8b7edbd, Raw: 01deb4ddede7e8b7edbdb7e1
""",
        'read_cmd': 'lf awid read',
        # Source: awid_write_trace_20260328.txt line 7
        'read_response': """\
[+] AWID - len: 222 -unknown- (63198) - Wiegand: b4ddede7e8b7edbd, Raw: 01deb4ddede7e8b7edbdb7e1
""",
        'clone_cmd': 'lf t55xx write b 1',
        'clone_response': """\
[=] Writing page 0  block: 01  data: 0x01DEB4DD
""",
        'lf_sea_verify': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] AWID - len: 222 -unknown- (32395) - Wiegand: 203bd69bbdbcfd16, Raw: 01deb4ddede7e8b7edbdb7e1
""",
    },
    'io_prox': {
        'type_code': 12,
        'lf_sea_keyword': 'Valid IO Prox ID',
        'lf_sea_response': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] Valid IO Prox ID found!
[+] XSF(01)01:12345
""",
        'read_cmd': 'lf io read',
        'read_response': """\
[+] Valid IO Prox ID found!
[+] XSF(01)01:12345
[+] FC: 01, CN: 12345
[+] Raw: 007E0180A5
""",
        'clone_cmd': 'lf io clone',
        'clone_response': """\
[+] Preparing to clone IO Prox to T55x7
""",
        'lf_sea_verify': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] Valid IO Prox ID found!
[+] XSF(01)01:12345
""",
    },
    'gprox': {
        'type_code': 13,
        'lf_sea_keyword': 'Valid Guardall G-Prox II',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Guardall G-Prox II ID found!
[+] FC: 123, CN: 4567
[+] Raw: 0880088008800880
""",
        'read_cmd': 'lf gproxii read',
        'read_response': """\
[+] Valid Guardall G-Prox II ID found!
[+] FC: 123, CN: 4567
[+] Raw: 0880088008800880
""",
        'clone_cmd': 'lf gproxii clone',
        'clone_response': """\
[+] Preparing to clone G-Prox II to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Guardall G-Prox II ID found!
[+] FC: 123, CN: 4567
[+] Raw: 0880088008800880
""",
    },
    'securakey': {
        'type_code': 14,
        'lf_sea_keyword': 'Valid Securakey ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Securakey ID found!
[+] Raw: AABBCCDD00112233
""",
        'read_cmd': 'lf securakey read',
        'read_response': """\
[+] Valid Securakey ID found!
[+] Raw: AABBCCDD00112233
""",
        'clone_cmd': 'lf securakey clone',
        'clone_response': """\
[+] Preparing to clone Securakey to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Securakey ID found!
[+] Raw: AABBCCDD00112233
""",
    },
    'viking': {
        'type_code': 15,
        'lf_sea_keyword': 'Valid Viking ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Viking ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf viking read',
        'read_response': """\
[+] Viking - Card 12345678, Raw: 1234567800112233
""",
        'clone_cmd': 'lf viking clone',
        'clone_response': """\
[+] Preparing to clone Viking to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Viking ID found!
[+] Card ID: 12345678
""",
    },
    'pyramid': {
        'type_code': 16,
        'lf_sea_keyword': 'Valid Pyramid ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Pyramid ID found!
[+] FC: 123, CN: 4567
""",
        'read_cmd': 'lf pyramid read',
        'read_response': """\
[+] Valid Pyramid ID found!
[+] FC: 123, CN: 4567
[+] Raw: 0000000000001E39
""",
        'clone_cmd': 'lf pyramid clone',
        'clone_response': """\
[+] Preparing to clone Pyramid to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Pyramid ID found!
[+] FC: 123, CN: 4567
""",
    },
    'paradox': {
        'type_code': 35,
        'lf_sea_keyword': 'Valid Paradox ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Paradox ID found!
[+] FC: 123, CN: 4567
[+] Raw: AABBCCDD00112233
""",
        'read_cmd': 'lf paradox read',
        'read_response': """\
[+] Valid Paradox ID found!
[+] FC: 123, CN: 4567
[+] Raw: AABBCCDD00112233
""",
        'clone_cmd': 'lf paradox clone',
        'clone_response': """\
[+] Preparing to clone Paradox to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Paradox ID found!
[+] FC: 123, CN: 4567
""",
    },
    'fdxb': {
        'type_code': 28,
        # Source: fdxb_t55_write_trace_20260328.txt
        'lf_sea_keyword': 'FDX-B',
        'lf_sea_response': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          0060-030207938416
[+] National Code      030207938416 (0x708888F70)
[+] Country Code       0060
""",
        'read_cmd': 'lf fdx read',
        # Source: fdxb_t55_write_trace_20260328.txt line 7
        'read_response': """\
[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          0060-030207938416
[+] National Code      030207938416 (0x708888F70)
[+] Country Code       0060
[+] Reserved/RFU       14339 (0x3803)
[+]   Animal bit set?  True
[+]       Data block?  True  [value 0x800000]
[+] CRC-16             0xCE2B (ok)
""",
        # Source: fdxb_t55_write_trace_20260328.txt line 35
        'clone_cmd': 'lf fdx clone',
        'clone_response': """\
[=]       Country code 60
[=]      National code 30207938416
[=]     Set animal bit N
[=] Set data block bit N
[=]      Extended data 0x0
[=]                RFU 0
[=] Preparing to clone FDX-B to T55x7 with animal ID: 0060-30207938416
[+] Blk | Data
[+] ----+------------
[+]  00 | 00098080
""",
        # Source: fdxb_t55_write_trace_20260328.txt line 46
        'lf_sea_verify': """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          0060-030207938416
[+] National Code      030207938416 (0x708888F70)
[+] Country Code       0060
""",
    },
    'gallagher': {
        'type_code': 29,
        'lf_sea_keyword': 'Valid GALLAGHER ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
""",
        'read_cmd': 'lf gallagher read',
        'read_response': """\
[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
""",
        'clone_cmd': 'lf gallagher clone',
        'clone_response': """\
[+] Preparing to clone Gallagher to T55x7
""",
        'lf_sea_verify': """\
[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
""",
    },
    'jablotron': {
        'type_code': 30,
        'lf_sea_keyword': 'Valid Jablotron ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Jablotron ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf jablotron read',
        'read_response': """\
[+] Jablotron - Card: FF010201234568, Raw: 1234567800112233
""",
        'clone_cmd': 'lf jablotron clone',
        'clone_response': """\
[+] Preparing to clone Jablotron to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Jablotron ID found!
[+] Card ID: 12345678
""",
    },
    'keri': {
        'type_code': 31,
        'lf_sea_keyword': 'Valid KERI ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid KERI ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf keri read',
        'read_response': """\
[+] Valid KERI ID found!
[+] KERI - Internal ID: 12345678, Raw: 1234567800112233
""",
        'clone_cmd': 'lf keri clone',
        'clone_response': """\
[+] Preparing to clone KERI to T55x7
""",
        'lf_sea_verify': """\
[+] Valid KERI ID found!
[+] Card ID: 12345678
""",
    },
    'nedap': {
        'type_code': 32,
        'lf_sea_keyword': 'Valid NEDAP ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid NEDAP ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf nedap read',
        'read_response': """\
[+] NEDAP - Card: 12345678, Raw: 1234567800112233
""",
        'clone_cmd': 'lf nedap clone',
        'clone_response': """\
[+] Preparing to clone NEDAP to T55x7
""",
        'lf_sea_verify': """\
[+] Valid NEDAP ID found!
[+] Card ID: 12345678
""",
    },
    'noralsy': {
        'type_code': 33,
        'lf_sea_keyword': 'Valid Noralsy ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Noralsy ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf noralsy read',
        'read_response': """\
[+] Noralsy - Card: 12345678, Raw: 1234567800112233
""",
        'clone_cmd': 'lf noralsy clone',
        'clone_response': """\
[+] Preparing to clone Noralsy to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Noralsy ID found!
[+] Card ID: 12345678
""",
    },
    'pac': {
        'type_code': 34,
        'lf_sea_keyword': 'Valid PAC/Stanley ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid PAC/Stanley ID found!
[+] Raw: AABBCCDD00112233
""",
        'read_cmd': 'lf pac read',
        'read_response': """\
[+] PAC/Stanley - Card: FF01020304050607, Raw: AABBCCDD00112233
""",
        'clone_cmd': 'lf pac clone',
        'clone_response': """\
[+] Preparing to clone PAC/Stanley to T55x7
""",
        'lf_sea_verify': """\
[+] Valid PAC/Stanley ID found!
[+] Raw: AABBCCDD00112233
""",
    },
    'presco': {
        'type_code': 36,
        'lf_sea_keyword': 'Valid Presco ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Presco ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf presco read',
        'read_response': """\
[+] Presco - Card: 12345678, Raw: 123456780011223344556677
""",
        'clone_cmd': 'lf presco clone',
        'clone_response': """\
[+] Preparing to clone Presco to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Presco ID found!
[+] Card ID: 12345678
""",
    },
    'visa2000': {
        'type_code': 37,
        'lf_sea_keyword': 'Valid Visa2000 ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid Visa2000 ID found!
[+] Card ID: 12345678
""",
        'read_cmd': 'lf visa2000 read',
        'read_response': """\
[+] Visa2000 - Card 12345678, Raw: 1234567800112233
""",
        'clone_cmd': 'lf visa2000 clone',
        'clone_response': """\
[+] Preparing to clone Visa2000 to T55x7
""",
        'lf_sea_verify': """\
[+] Valid Visa2000 ID found!
[+] Card ID: 12345678
""",
    },
    'nexwatch': {
        'type_code': 45,
        'lf_sea_keyword': 'Valid NexWatch ID',
        'lf_sea_response': """\

[=] Checking for known tags...
[=]
[+] Valid NexWatch ID found!
[+] Raw: AABBCCDD00112233
""",
        'read_cmd': 'lf nexwatch read',
        'read_response': """\
[+] NexWatch, Quadrakey
[+] ID: AABBCCDD00112233
[+] Raw: AABBCCDD0011223344556677
""",
        'clone_cmd': 'lf nexwatch clone',
        'clone_response': """\
[+] Preparing to clone NexWatch to T55x7
""",
        'lf_sea_verify': """\
[+] Valid NexWatch ID found!
[+] Raw: AABBCCDD00112233
""",
    },
}


# ============================================================================
# SCENARIO GENERATORS
# ============================================================================

def escape_for_fixture(text):
    """Escape text for embedding in a Python triple-quoted string."""
    # Replace actual backslash-n sequences from raw traces
    return text


def make_fixture_header(scenario_name, description, ground_truth, pm3_commands):
    """Build the header comment block for a fixture.py."""
    lines = [
        f"# Auto-Copy scenario: {scenario_name}",
        f"# {description}",
        f"#",
        "# PM3 command sequence:",
    ]
    for cmd in pm3_commands:
        lines.append(f"#   {cmd}")
    lines.append("")
    return '\n'.join(lines) + '\n'


def format_response(ret, text):
    """Format a single (return_code, text) tuple as Python source."""
    # Use triple-quoted string with proper indentation
    escaped = text.rstrip('\n')
    return f"({ret}, '''{escaped}\n''')"


def format_list_response(pairs):
    """Format a list of (return_code, text) tuples as Python source."""
    items = []
    for ret, text in pairs:
        escaped = text.rstrip('\n')
        items.append(f"        ({ret}, '''{escaped}\n''')")
    return '[\n' + ',\n'.join(items) + ',\n    ]'


def write_fixture_py(path, header, responses, default_return, tag_type):
    """Write a fixture.py file."""
    lines = [header]
    lines.append("SCENARIO_RESPONSES = {\n")
    for key, val in responses.items():
        if isinstance(val, list):
            lines.append(f"    '{key}': {format_list_response(val)},\n")
        else:
            ret, text = val
            lines.append(f"    '{key}': {format_response(ret, text)},\n")
    lines.append("}\n")
    lines.append(f"DEFAULT_RETURN = {default_return}\n")
    lines.append(f"TAG_TYPE = {tag_type}\n")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(''.join(lines))


def write_scenario_sh(path, scenario_name, min_unique, trigger, mode,
                      boot_timeout=600, autocopy_wait=240, write_wait=300,
                      verify_wait=60):
    """Write a <name>.sh runner script."""
    content = f'''#!/bin/bash
# Auto-Copy scenario: {scenario_name}
PROJECT="${{PROJECT:-/home/qx/icopy-x-reimpl}}"
SCENARIO="{scenario_name}"
BOOT_TIMEOUT={boot_timeout}
AUTOCOPY_TRIGGER_WAIT={autocopy_wait}
WRITE_TRIGGER_WAIT={write_wait}
VERIFY_TRIGGER_WAIT={verify_wait}
source "${{PROJECT}}/tests/flows/auto-copy/includes/auto_copy_common.sh"
run_auto_copy_scenario {min_unique} "{trigger}" "{mode}"
'''
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ============================================================================
# CATEGORY 1: SCAN PHASE EXITS (3 scenarios)
# ============================================================================

def gen_autocopy_scan_no_tag():
    """No tag on reader - all PM3 commands timeout."""
    name = 'autocopy_scan_no_tag'
    header = make_fixture_header(
        name,
        'No tag found - all scan phases timeout, toast: No tag found',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Scan Failures)',
        ['hf 14a info -> timeout', 'hf sea -> timeout', 'lf sea -> timeout']
    )
    # All commands timeout = DEFAULT_RETURN = -1, no entries
    responses = {}
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=-1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=3, trigger='toast:No tag found', mode='early_exit',
        autocopy_wait=120
    )
    return name


def gen_autocopy_scan_multi_tag():
    """Multiple tags detected during hf 14a info."""
    name = 'autocopy_scan_multi_tag'
    header = make_fixture_header(
        name,
        'Multiple tags detected - hf 14a info returns collision, toast: Multiple tags detected',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Scan Failures)',
        ['hf 14a info -> Multiple tags detected']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 - tag_multi
    responses = {
        'hf 14a info': (1, """\

[!] Multiple tags detected. Collision after bit 32
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=-1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=3, trigger='toast:Multiple tags', mode='early_exit',
        autocopy_wait=120
    )
    return name


def gen_autocopy_scan_wrong_type():
    """Unsupported tag type found during scan."""
    name = 'autocopy_scan_wrong_type'
    header = make_fixture_header(
        name,
        'Wrong/unsupported tag type found, toast: No tag found Or Wrong type found',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Scan Failures)',
        ['hf 14a info -> no tag', 'hf sea -> no known', 'lf sea -> no known',
         'hf felica reader -> no tag', 'lf t55xx detect -> fail']
    )
    # All stages return no match, including T55XX detect fail = unsupported
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'hf sea': (1, HFSEA_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'data save': (1, '[+] saved 40000 bytes to /tmp/lf_trace_tmp\n'),
        'hf felica reader': (1, '[!] card timeout\n'),
        'lf t55xx detect': (1, """\
[!] Could not detect modulation automatically. Try setting it manually with 'lf t55xx config'
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=-1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=3, trigger='toast:No tag found', mode='early_exit',
        autocopy_wait=120
    )
    return name


# ============================================================================
# CATEGORY 2: MF CLASSIC VARIANTS (9 scenarios)
# ============================================================================

def gen_autocopy_mf1k_happy():
    """MF1K happy path: fchk all keys -> rdsc -> wrbl success."""
    name = 'autocopy_mf1k_happy'
    header = make_fixture_header(
        name,
        'MF Classic 1K: all default keys found via fchk, read all sectors, write all blocks',
        'trace_autocopy_mf1k_standard.txt + full_read_write_trace_20260327.txt',
        ['hf 14a info', 'hf mf cgetblk 0', 'hf mf fchk 1 keys', 'hf mf rdsc 0-15',
         'hf mf wrbl 0-63', 'hf 14a info (verify)', 'hf mf cgetblk 0 (verify)']
    )
    # Source: trace_autocopy_mf1k_standard.txt line 9-21 (scan+read)
    # Source: full_read_write_trace_20260327.txt line 59-186 (write)
    responses = {
        'hf 14a info': (1, MF1K_HF14A_INFO),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_all_found(16, 1)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_SUCCESS),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_mf1k_darkside():
    """MF1K with darkside+nested key recovery."""
    name = 'autocopy_mf1k_darkside'
    header = make_fixture_header(
        name,
        'MF Classic 1K: no default keys, darkside + nested recovery, then read + write',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5 (Key Recovery)',
        ['hf 14a info', 'hf mf cgetblk 0', 'hf mf fchk 1 keys (no keys)',
         'hf mf darkside (found key)', 'hf mf nested o (all keys)',
         'hf mf rdsc 0-15', 'hf mf wrbl 0-63']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5
    # darkside succeeds because PRNG is weak (no "Static nonce" in hf 14a info)
    responses = {
        'hf 14a info': (1, MF1K_HF14A_INFO),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_no_keys(16, 1)),
        'hf mf darkside': (1, """\
[+] found valid key: a0a1a2a3a4a5
"""),
        'hf mf nested': (1, """\
[+] Testing known keys. Sector count 16
[+] found valid key: b0b1b2b3b4b5
"""),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_SUCCESS),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_mf1k_darkside_fail():
    """MF1K with static nonce - darkside fails."""
    name = 'autocopy_mf1k_darkside_fail'
    header = make_fixture_header(
        name,
        'MF Classic 1K: static nonce card, darkside attack fails, toast: No valid key',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5 (Key Recovery - static nonce)',
        ['hf 14a info (Static nonce: yes)', 'hf mf cgetblk 0',
         'hf mf fchk 1 keys (no keys)', 'hf mf darkside (fails)']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5
    # Static nonce: yes -> darkside vulnerable returns False
    responses = {
        'hf 14a info': (1, """\

[+]  UID: AA BB CC DD
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Static nonce: yes
"""),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_no_keys(16, 1)),
        'hf mf darkside': (1, """\
[-] This card is not vulnerable to Darkside attack
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=3, trigger='toast:No valid key', mode='early_exit'
    )
    return name


def gen_autocopy_mf1k_gen1a():
    """MF1K Gen1a magic card: csave -> cload write."""
    name = 'autocopy_mf1k_gen1a'
    header = make_fixture_header(
        name,
        'MF Classic 1K Gen1a: magic card detected via cgetblk, csave read, cload write',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 (Gen1a)',
        ['hf 14a info', 'hf mf cgetblk 0 (success = Gen1a)',
         'hf mf fchk 1 keys', 'hf mf rdsc 0-15',
         'hf mf csetuid', 'hf mf cload b']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 Gen1a path
    responses = {
        'hf 14a info': (1, """\

[+]  UID: 11 22 33 44
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
        'hf mf cgetblk': (1, CGETBLK_GEN1A),
        'hf mf fchk': (1, _fchk_all_found(16, 1)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf cload': (1, """\
[+] Card loaded 64 blocks from file
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_mf4k_happy():
    """MF4K happy path: fchk all 40 sectors -> rdsc -> wrbl."""
    name = 'autocopy_mf4k_happy'
    header = make_fixture_header(
        name,
        'MF Classic 4K: all default keys found, read 40 sectors, write all blocks',
        'mf4k_read_trace_20260328.txt + V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1',
        ['hf 14a info (SAK 18)', 'hf mf cgetblk 0', 'hf mf fchk 4 keys',
         'hf mf rdsc 0-39', 'hf mf wrbl 0-255']
    )
    # Source: mf4k_read_trace_20260328.txt
    responses = {
        'hf 14a info': (1, MF4K_HF14A_INFO),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_all_found(40, 4)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_SUCCESS),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=0
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_mf1k_write_fail():
    """MF1K write failure: wrbl isOk:00."""
    name = 'autocopy_mf1k_write_fail'
    header = make_fixture_header(
        name,
        'MF Classic 1K: read success but wrbl returns isOk:00, toast: Write failed',
        'full_read_write_trace_20260327.txt (wrbl response format) + V1090_AUTOCOPY_FLOW_COMPLETE.md',
        ['hf 14a info', 'hf mf cgetblk 0', 'hf mf fchk 1 keys',
         'hf mf rdsc 0-15', 'hf mf wrbl (isOk:00)']
    )
    responses = {
        'hf 14a info': (1, MF1K_HF14A_INFO),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_all_found(16, 1)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_FAIL),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=4, trigger='toast:Write failed', mode='no_verify'
    )
    return name


def gen_autocopy_mf1k_partial_keys():
    """MF1K partial keys: fchk partial -> nested incomplete."""
    name = 'autocopy_mf1k_partial_keys'
    header = make_fixture_header(
        name,
        'MF Classic 1K: fchk finds partial keys, nested does not complete, toast: Missing keys',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5 (Key Recovery - partial)',
        ['hf 14a info', 'hf mf cgetblk 0', 'hf mf fchk 1 keys (8/32)',
         'hf mf nested o (timeout)']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5
    responses = {
        'hf 14a info': (1, MF1K_HF14A_INFO),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_partial_keys(16, found_a=8, found_b=0)),
        'hf mf nested': (-1, ''),  # timeout = no more keys recovered
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=3, trigger='toast:Missing keys', mode='early_exit'
    )
    return name


def gen_autocopy_mf_mini_happy():
    """MIFARE Mini (type 25): 5 sectors, fchk all -> rdsc -> wrbl."""
    name = 'autocopy_mf_mini_happy'
    header = make_fixture_header(
        name,
        'MIFARE Mini (type 25): 5 sectors, all default keys, read + write success',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 (MIFARE Classic variants)',
        ['hf 14a info (SAK 09)', 'hf mf cgetblk 0', 'hf mf fchk 0 keys',
         'hf mf rdsc 0-4', 'hf mf wrbl 0-19']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md reader table: M1_MINI type 25, SAK 09
    responses = {
        'hf 14a info': (1, """\

[+]  UID: DE AD BE EF
[+] ATQA: 00 04
[+]  SAK: 09 [2]
[+] Possible types:
[+]    MIFARE Mini
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_all_found(5, 0)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_SUCCESS),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=25
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_mf1k_7b_happy():
    """MF1K 7-byte UID (type 42): fchk all -> rdsc -> wrbl."""
    name = 'autocopy_mf1k_7b_happy'
    header = make_fixture_header(
        name,
        'MF Classic 1K 7-byte UID (type 42): all default keys, read + write success',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 (7B UID)',
        ['hf 14a info (7-byte UID)', 'hf mf cgetblk 0', 'hf mf fchk 1 keys',
         'hf mf rdsc 0-15', 'hf mf wrbl 0-63']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md reader table: M1_S50_1K_7B type 42
    responses = {
        'hf 14a info': (1, """\

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
"""),
        'hf mf cgetblk': (1, CGETBLK_NOT_GEN1A),
        'hf mf fchk': (1, _fchk_all_found(16, 1)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_SUCCESS),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=42
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


# ============================================================================
# CATEGORY 3: UL/NTAG (4 scenarios)
# ============================================================================

def gen_autocopy_ultralight_happy():
    """MIFARE Ultralight: dump -> restore success."""
    name = 'autocopy_ultralight_happy'
    header = make_fixture_header(
        name,
        'MIFARE Ultralight: mfu dump read + mfu restore write success',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 (Ultralight/NTAG)',
        ['hf 14a info', 'hf mfu info', 'hf mfu dump', 'hf mfu restore']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2
    responses = {
        'hf 14a info': (1, """\

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
        'hf mfu info': (1, """\

[=] --- Tag Information ---------
[=]       TYPE: Ultralight (MF0ICU1)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
"""),
        'hf mfu dump': (1, """\
[+] Dump file created: /mnt/upan/dump/mfu/MFU_04A1B2C3D4E5F6_1.bin
"""),
        'hf mfu restore': (1, """\
[+] Wrote 20 pages
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=2
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_ntag215_happy():
    """NTAG215: dump -> restore success."""
    name = 'autocopy_ntag215_happy'
    header = make_fixture_header(
        name,
        'NTAG215: mfu dump read + mfu restore write success',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 (Ultralight/NTAG)',
        ['hf 14a info', 'hf mfu info', 'hf mfu dump', 'hf mfu restore']
    )
    responses = {
        'hf 14a info': (1, """\

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG215
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
        'hf mfu info': (1, """\

[=] --- Tag Information ---------
[=]       TYPE: NTAG 215 504bytes (NT2H1511G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
"""),
        'hf mfu dump': (1, """\
[+] Dump file created: /mnt/upan/dump/mfu/NTAG215_04B1C2D3E4F5A6_1.bin
"""),
        'hf mfu restore': (1, """\
[+] Wrote 135 pages
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=6
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_ntag_write_fail():
    """NTAG write failure: restore reports block write error."""
    name = 'autocopy_ntag_write_fail'
    header = make_fixture_header(
        name,
        'NTAG215: dump read success, restore fails with block write error',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 (restore failure)',
        ['hf 14a info', 'hf mfu info', 'hf mfu dump',
         'hf mfu restore (failed to write block)']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 parse
    responses = {
        'hf 14a info': (1, """\

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG215
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
        'hf mfu info': (1, """\

[=] --- Tag Information ---------
[=]       TYPE: NTAG 215 504bytes (NT2H1511G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
"""),
        'hf mfu dump': (1, """\
[+] Dump file created: /mnt/upan/dump/mfu/NTAG215_04B1C2D3E4F5A6_1.bin
"""),
        'hf mfu restore': (1, """\
[!] failed to write block 4
[!] Restoring page 4 failed
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=6
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=4, trigger='toast:Write failed', mode='no_verify'
    )
    return name


def gen_autocopy_ultralight_ev1_happy():
    """MIFARE Ultralight EV1: dump -> restore success."""
    name = 'autocopy_ultralight_ev1_happy'
    header = make_fixture_header(
        name,
        'MIFARE Ultralight EV1: mfu dump read + mfu restore write success',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 (Ultralight/NTAG)',
        ['hf 14a info', 'hf mfu info', 'hf mfu dump', 'hf mfu restore']
    )
    responses = {
        'hf 14a info': (1, """\

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
"""),
        'hf mfu info': (1, """\

[=] --- Tag Information ---------
[=]       TYPE: Ultralight EV1 (MF0UL1101)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
"""),
        'hf mfu dump': (1, """\
[+] Dump file created: /mnt/upan/dump/mfu/MFU_EV1_04A1B2C3D4E5F6_1.bin
"""),
        'hf mfu restore': (1, """\
[+] Wrote 41 pages
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=4
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


# ============================================================================
# CATEGORY 4: LF TAGS (20 scenarios)
# All use full pipeline: scan -> read -> write -> DRM -> verify
# Toast: Verification successful
# ============================================================================

def gen_autocopy_lf_tag(tag_key):
    """Generate an auto-copy fixture for a single LF tag type."""
    tdef = LF_TAG_DEFS[tag_key]
    name = f'autocopy_lf_{tag_key}'
    type_code = tdef['type_code']

    # For AWID, the write uses direct t55xx block writes + DRM (from real trace)
    # For most others: clone command + DRM + verify
    # Source: awid_write_trace_20260328.txt, V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.6
    if tag_key == 'awid':
        write_cmds = [
            'lf t55xx wipe p 20206666',
            'lf t55xx detect (after wipe)',
            'lf t55xx write b 1-3 (data blocks)',
            'lf t55xx write b 0 (config)',
            'lf t55xx detect (after write)',
            'lf t55xx write b 7 d 20206666 (DRM)',
            'lf t55xx write b 0 (config+pw bit)',
            'lf t55xx detect p 20206666 (verify config)',
            'lf sea + lf awid read (verify identity)',
        ]
    else:
        write_cmds = [
            'lf t55xx wipe p 20206666',
            'lf t55xx detect (after wipe)',
            f'{tdef["clone_cmd"]}',
            'lf t55xx detect (after clone)',
            'lf t55xx write b 7 d 20206666 (DRM)',
            'lf t55xx write b 0 (config+pw bit)',
            'lf t55xx detect p 20206666 (verify config)',
            'lf sea (verify identity)',
        ]

    header = make_fixture_header(
        name,
        f'LF {tag_key.upper()} (type {type_code}): full auto-copy pipeline with T55XX DRM + verify',
        f'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6 + awid_write_trace_20260328.txt + fdxb_t55_write_trace_20260328.txt',
        ['hf 14a info (passthrough)', 'hf sea (passthrough)', f'lf sea ({tdef["lf_sea_keyword"]})',
         f'{tdef["read_cmd"]} x2'] + write_cmds
    )

    # Build responses dict
    # Scan phase: HF stages must pass through with no-match content, ret=1
    responses = {}

    # Scan phase passthrough for HF
    responses['hf 14a info'] = (1, HF14A_NO_TAG)
    responses['hf sea'] = (1, HFSEA_NO_TAG)

    # LF scan: lf sea finds the tag
    responses['lf sea'] = (1, tdef['lf_sea_response'])

    # LF read: specialized read command (called twice in AutoCopy per trace)
    responses[tdef['read_cmd']] = (1, tdef['read_response'])

    # Write phase
    responses['lf t55xx wipe'] = (1, LF_WIPE_RESP)

    # Sequential detect: after wipe (ASK), after clone (tag modulation)
    # Source: awid_write_trace_20260328.txt lines 17-18, 27-28
    responses['lf t55xx detect p 20206666'] = (1, LF_DETECT_WITH_PW)
    responses['lf t55xx detect'] = [
        (1, LF_DETECT_AFTER_WIPE),
        (1, LF_DETECT_AFTER_WIPE),
    ]

    # Clone command (for non-AWID)
    if tag_key != 'awid':
        responses[tdef['clone_cmd']] = (1, tdef['clone_response'])

    # T55XX write commands for block writes
    responses['lf t55xx write b 7'] = (1, LF_WRITE_B7_RESP)
    responses['lf t55xx write b 0'] = (1, LF_WRITE_B0_DRM_RESP)

    # For AWID specifically, add data block write commands
    if tag_key == 'awid':
        responses['lf t55xx write b 1'] = (1, """\
[=] Writing page 0  block: 01  data: 0x01DEB4DD
""")
        responses['lf t55xx write b 2'] = (1, """\
[=] Writing page 0  block: 02  data: 0xEDE7E8B7
""")
        responses['lf t55xx write b 3'] = (1, """\
[=] Writing page 0  block: 03  data: 0xEDBDB7E1
""")

    # Verify phase: lfverify.verify_t55xx() runs lf sea + specific read
    # The lf sea from scan phase is re-used for verify (same dict key = same response).
    # We override with the verify-specific response to ensure keyword matches.
    # Actually, lf sea key is already set above. For verify, the same response works
    # since it contains the tag keyword.
    # Override lf sea with verify response (contains keyword for lfverify parser)
    responses['lf sea'] = (1, tdef['lf_sea_verify'])

    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=1, tag_type=type_code
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=6, trigger='toast:Verification successful', mode=''
    )
    return name


# ============================================================================
# CATEGORY 5: T55XX / EM4305 (2 scenarios)
# ============================================================================

def gen_autocopy_t55xx_happy():
    """T55XX: detect -> dump -> restore -> verify."""
    name = 'autocopy_t55xx_happy'
    header = make_fixture_header(
        name,
        'T55XX direct: detect card, dump blocks, wipe + restore, verify by block read-back',
        't55_to_t55_write_trace_20260328.txt + V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.5',
        ['hf 14a info (no tag)', 'lf sea (no known tag)', 'data save',
         'hf sea (no tag)', 'hf felica reader (no tag)',
         'lf t55xx detect (success)', 'lf t55xx read b 0-7',
         'lf t55xx dump', 'lf t55xx wipe p 20206666',
         'lf t55xx detect (after wipe)', 'lf t55xx restore',
         'lf t55xx detect (after restore)', 'lf t55xx read b 0-7 (verify)']
    )
    # Source: t55_to_t55_write_trace_20260328.txt
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'data save': (1, '[+] saved 40000 bytes to /tmp/lf_trace_tmp\n'),
        'hf sea': (1, HFSEA_NO_TAG),
        'hf felica reader': (1, '[!] card timeout\n'),
        # Sequential detect: first call = original card, after wipe = ASK default, after restore = original
        # Source: t55_to_t55_write_trace_20260328.txt lines 6-34
        'lf t55xx detect': [
            (1, """\
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
"""),
            (1, """\
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
"""),
            (1, LF_DETECT_AFTER_WIPE),
            (1, LF_DETECT_AFTER_WIPE),
            (1, """\
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
"""),
        ],
        # Source: t55_to_t55_write_trace_20260328.txt lines 11-12
        'lf t55xx read b 0': (1, """\
[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
"""),
        'lf t55xx read b': (1, """\
[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
"""),
        # Source: t55_to_t55_write_trace_20260328.txt line 17
        'lf t55xx dump': (1, """\
[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
[+]  02 | 00000000 | 00000000000000000000000000000000 | ....
[+]  03 | 00000000 | 00000000000000000000000000000000 | ....
[+]  04 | 00000000 | 00000000000000000000000000000000 | ....
[+]  05 | 00000000 | 00000000000000000000000000000000 | ....
[+]  06 | 00000000 | 00000000000000000000000000000000 | ....
[+]  07 | 00000000 | 00000000000000000000000000000000 | ....
"""),
        'lf t55xx wipe': (1, LF_WIPE_RESP),
        # Source: t55_to_t55_write_trace_20260328.txt line 31
        'lf t55xx restore': (1, """\
[+] loaded 48 bytes from binary file /mnt/upan/dump/t55xx/T55xx_00148040_00000000_00000000_2.bin
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=1, tag_type=23
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=6, trigger='toast:Verification successful', mode=''
    )
    return name


def gen_autocopy_em4305_happy():
    """EM4305: 4x05_info -> dump -> write -> verify."""
    name = 'autocopy_em4305_happy'
    header = make_fixture_header(
        name,
        'EM4305: detect via 4x05_info, dump words, write words, verify',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.5 (EM4305)',
        ['hf 14a info (no tag)', 'lf sea (no known)',
         'data save', 'hf sea (no tag)', 'hf felica reader',
         'lf t55xx detect (fail)', 'lf em 4x05_info',
         'lf em 4x05_dump', 'lf em 4x05_write (per word)', 'lf em 4x05_dump (verify)']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.5 EM4305
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'data save': (1, '[+] saved 40000 bytes to /tmp/lf_trace_tmp\n'),
        'hf sea': (1, HFSEA_NO_TAG),
        'hf felica reader': (1, '[!] card timeout\n'),
        'lf t55xx detect': (1, """\
[!] Could not detect modulation automatically. Try setting it manually with 'lf t55xx config'
"""),
        'lf em 4x05_info': (1, """\
[+] --- Tag Information ---
[+] Chip Type   : EM4205/EM4305
[+] UID         : 600071E2
"""),
        'lf em 4x05_dump': (1, """\
[+] | 00 | 600071E2 - EM4x05 / EM4305
[+] | 01 | 00000000 -
[+] | 02 | 00000000 -
[+] | 03 | 00000000 -
[+] | 04 | 00148040 -
"""),
        'lf em 4x05_write': (1, """\
[+] Success writing to tag
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=1, tag_type=24
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=6, trigger='toast:Verification successful', mode=''
    )
    return name


# ============================================================================
# CATEGORY 6: iCLASS (2 scenarios)
# ============================================================================

def gen_autocopy_iclass_legacy():
    """iCLASS Legacy: chk -> dump -> calcnewkey -> wrbl."""
    name = 'autocopy_iclass_legacy'
    header = make_fixture_header(
        name,
        'iCLASS Legacy: key check with standard key, dump blocks, calcnewkey + wrbl write',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.7 (iCLASS)',
        ['hf 14a info (no tag)', 'hf sea (Valid iCLASS tag)',
         'hf iclass info', 'hf iclass rdbl b 01 k AFA785A7DAB33378',
         'hf iclass chk', 'hf iclass dump',
         'hf iclass calcnewkey', 'hf iclass wrbl']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.7
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'hf sea': (1, """\

[+] Valid iCLASS tag / PicoPass tag found
"""),
        'hf iclass info': (1, """\

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
"""),
        # Standard key succeeds on block 01
        'hf iclass rdbl b 01 k AFA785A7DAB33378': (1, """\

Block 01 : 12 FF FF FF 7F 1F FF 3C
"""),
        'hf iclass rdbl': (1, """\
[-] Error reading block
"""),
        'hf iclass chk': (1, """\

[+] Found valid key afa785a7dab33378
"""),
        'hf iclass dump': (1, """\
[+] saving dump file - 19 blocks read
"""),
        'hf iclass calcnewkey': (1, """\
[+] Xor div key : A1 B2 C3 D4 E5 F6 A7 B8
"""),
        'hf iclass wrbl': (1, """\
[+] Write block 6 successful
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=17
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_iclass_elite():
    """iCLASS Elite: Elite key -> dump -> write."""
    name = 'autocopy_iclass_elite'
    header = make_fixture_header(
        name,
        'iCLASS Elite: standard keys fail, elite key found via chk, dump + write',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.7 (iCLASS Elite)',
        ['hf 14a info (no tag)', 'hf sea (Valid iCLASS tag)',
         'hf iclass info', 'hf iclass rdbl (all fail)',
         'hf iclass chk (elite key found)', 'hf iclass dump',
         'hf iclass calcnewkey', 'hf iclass wrbl']
    )
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'hf sea': (1, """\

[+] Valid iCLASS tag / PicoPass tag found
"""),
        'hf iclass info': (1, """\

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
"""),
        # All legacy rdbl fail
        'hf iclass rdbl': (1, """\
[-] Error reading block
"""),
        # chk finds elite key
        'hf iclass chk': (1, """\

[+] Found valid key ae a6 84 a6 da b2 12 32
"""),
        'hf iclass dump': (1, """\
[+] saving dump file - 19 blocks read
"""),
        'hf iclass calcnewkey': (1, """\
[+] Xor div key : A1 B2 C3 D4 E5 F6 A7 B8
"""),
        'hf iclass wrbl': (1, """\
[+] Write block 6 successful
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=18
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


# ============================================================================
# CATEGORY 7: ISO15693 (2 scenarios)
# ============================================================================

def gen_autocopy_iso15693_happy():
    """ISO15693 ICODE: dump -> restore success."""
    name = 'autocopy_iso15693_happy'
    header = make_fixture_header(
        name,
        'ISO15693 ICODE: hf 15 dump read + hf 15 restore write success',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.8 (ISO15693)',
        ['hf 14a info (no tag)', 'hf sea (Valid ISO15693)',
         'hf 15 dump', 'hf 15 restore']
    )
    # Source: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.8
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'hf sea': (1, """\

[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
"""),
        'hf 15 dump': (1, """\
[+] ISO15693 tag dump saved to file
"""),
        'hf 15 restore': (1, """\
[+] Write OK
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=19
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


def gen_autocopy_iso15693_st():
    """ISO15693 ST variant: dump -> restore success."""
    name = 'autocopy_iso15693_st'
    header = make_fixture_header(
        name,
        'ISO15693 ST Microelectronics: dump + restore + csetuid',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.8 (ISO15693 ST)',
        ['hf 14a info (no tag)', 'hf sea (Valid ISO15693 + ST)',
         'hf 15 dump', 'hf 15 restore', 'hf 15 csetuid']
    )
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'lf sea': (1, LFSEA_NO_TAG),
        'hf sea': (1, """\

[+] Valid ISO15693 tag found
[+] UID: E0 02 08 01 12 34 56 78
[+] ST Microelectronics SA France
"""),
        'hf 15 dump': (1, """\
[+] ISO15693 tag dump saved to file
"""),
        'hf 15 restore': (1, """\
[+] Write OK
"""),
        'hf 15 csetuid': (1, """\
[+] setting new UID (ok)
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=46
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Write successful', mode='no_verify'
    )
    return name


# ============================================================================
# CATEGORY 8: CROSS-TYPE FAILURES (3 scenarios)
# ============================================================================

def gen_autocopy_lf_write_fail():
    """LF clone fails - timeout on clone command."""
    name = 'autocopy_lf_write_fail'
    header = make_fixture_header(
        name,
        'LF EM410x: scan + read OK, but clone command times out, toast: Write failed',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Write Failures)',
        ['hf 14a info (passthrough)', 'hf sea (passthrough)',
         'lf sea (Valid EM410x)', 'lf em 410x_read',
         'lf t55xx wipe p 20206666', 'lf t55xx detect',
         'lf em 410x_write (timeout)']
    )
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'hf sea': (1, HFSEA_NO_TAG),
        'lf sea': (1, LF_TAG_DEFS['em410x']['lf_sea_response']),
        'lf em 410x_read': (1, LF_TAG_DEFS['em410x']['read_response']),
        'lf t55xx wipe': (1, LF_WIPE_RESP),
        'lf t55xx detect': (1, LF_DETECT_AFTER_WIPE),
        'lf em 410x_write': (-1, ''),  # timeout = write fails
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=8
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=4, trigger='toast:Write failed', mode='no_verify'
    )
    return name


def gen_autocopy_lf_verify_fail():
    """LF write OK but verify mismatch - different ID on readback."""
    name = 'autocopy_lf_verify_fail'
    header = make_fixture_header(
        name,
        'LF EM410x: write succeeds, but verify re-scan shows different ID = mismatch',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Verify Failures)',
        ['hf 14a info (passthrough)', 'hf sea (passthrough)',
         'lf sea (Valid EM410x)', 'lf em 410x_read',
         'lf t55xx wipe p 20206666', 'lf t55xx detect',
         'lf em 410x_write (OK)', 'lf t55xx write b 7 (DRM)',
         'lf t55xx write b 0 (config+pw)',
         'lf t55xx detect p 20206666', 'lf sea (different ID = mismatch)']
    )
    responses = {
        'hf 14a info': (1, HF14A_NO_TAG),
        'hf sea': (1, HFSEA_NO_TAG),
        # Read scan finds EM410x with ID 0F0368568B
        'lf em 410x_read': (1, LF_TAG_DEFS['em410x']['read_response']),
        'lf t55xx wipe': (1, LF_WIPE_RESP),
        'lf t55xx detect p 20206666': (1, LF_DETECT_WITH_PW),
        'lf t55xx detect': [
            (1, LF_DETECT_AFTER_WIPE),
            (1, LF_DETECT_AFTER_WIPE),
        ],
        'lf em 410x_write': (1, """\
[+] Writing T55x7 tag with UID 0x0F0368568B
[+] Blk | Data
[+] ----+------------
[+]  00 | 00148040
"""),
        'lf t55xx write b 7': (1, LF_WRITE_B7_RESP),
        'lf t55xx write b 0': (1, LF_WRITE_B0_DRM_RESP),
        # Verify: lf sea returns a DIFFERENT EM TAG ID -> mismatch
        'lf sea': (1, """\

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] EM410x pattern found

EM TAG ID      : 0011223344

[+] Valid EM410x ID found!
"""),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=1, tag_type=8
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=5, trigger='toast:Verification failed', mode=''
    )
    return name


def gen_autocopy_mf1k_verify_fail():
    """MF1K write OK but readback shows mismatch."""
    name = 'autocopy_mf1k_verify_fail'
    header = make_fixture_header(
        name,
        'MF Classic 1K: write succeeds (isOk:01), but post-write cgetblk returns error = verify mismatch',
        'V1090_AUTOCOPY_FLOW_COMPLETE.md Section 14 (HF Verification)',
        ['hf 14a info', 'hf mf cgetblk 0', 'hf mf fchk 1 keys',
         'hf mf rdsc 0-15', 'hf mf wrbl 0-63 (isOk:01)',
         'hf 14a info (verify)', 'hf mf cgetblk 0 (verify = error)']
    )
    # Post-write verification: hf 14a info + cgetblk. cgetblk returning error
    # after wrbl success means verification detected a mismatch.
    # Source: full_read_write_trace_20260327.txt lines 187-194 (post-write verify pattern)
    responses = {
        'hf 14a info': (1, MF1K_HF14A_INFO),
        'hf mf cgetblk': (-1, ''),  # post-write cgetblk timeout = can't verify
        'hf mf fchk': (1, _fchk_all_found(16, 1)),
        'hf mf rdsc': (1, _rdsc_response()),
        'hf mf wrbl': (1, WRBL_SUCCESS),
    }
    write_fixture_py(
        os.path.join(SCENARIOS_DIR, name, 'fixture.py'),
        header, responses, default_return=-1, tag_type=1
    )
    write_scenario_sh(
        os.path.join(SCENARIOS_DIR, name, f'{name}.sh'),
        name, min_unique=4, trigger='toast:Verification failed', mode='no_verify'
    )
    return name


# ============================================================================
# MAIN: Generate all scenarios and register in pm3_fixtures.py
# ============================================================================

def main():
    all_scenarios = []

    print("=== Generating Auto-Copy fixture files ===\n")

    # Category 1: Scan Phase Exits
    print("Category 1: Scan Phase Exits")
    all_scenarios.append(gen_autocopy_scan_no_tag())
    all_scenarios.append(gen_autocopy_scan_multi_tag())
    all_scenarios.append(gen_autocopy_scan_wrong_type())
    print(f"  Generated {3} scenarios\n")

    # Category 2: MF Classic Variants
    print("Category 2: MF Classic Variants")
    all_scenarios.append(gen_autocopy_mf1k_happy())
    all_scenarios.append(gen_autocopy_mf1k_darkside())
    all_scenarios.append(gen_autocopy_mf1k_darkside_fail())
    all_scenarios.append(gen_autocopy_mf1k_gen1a())
    all_scenarios.append(gen_autocopy_mf4k_happy())
    all_scenarios.append(gen_autocopy_mf1k_write_fail())
    all_scenarios.append(gen_autocopy_mf1k_partial_keys())
    all_scenarios.append(gen_autocopy_mf_mini_happy())
    all_scenarios.append(gen_autocopy_mf1k_7b_happy())
    print(f"  Generated {9} scenarios\n")

    # Category 3: UL/NTAG
    print("Category 3: UL/NTAG")
    all_scenarios.append(gen_autocopy_ultralight_happy())
    all_scenarios.append(gen_autocopy_ntag215_happy())
    all_scenarios.append(gen_autocopy_ntag_write_fail())
    all_scenarios.append(gen_autocopy_ultralight_ev1_happy())
    print(f"  Generated {4} scenarios\n")

    # Category 4: LF Tags
    print("Category 4: LF Tags")
    lf_tags = [
        'em410x', 'hid', 'indala', 'awid', 'io_prox', 'gprox',
        'securakey', 'viking', 'pyramid', 'paradox', 'fdxb',
        'gallagher', 'jablotron', 'keri', 'nedap', 'noralsy',
        'pac', 'presco', 'visa2000', 'nexwatch',
    ]
    for tag_key in lf_tags:
        all_scenarios.append(gen_autocopy_lf_tag(tag_key))
    print(f"  Generated {len(lf_tags)} scenarios\n")

    # Category 5: T55XX/EM4305
    print("Category 5: T55XX/EM4305")
    all_scenarios.append(gen_autocopy_t55xx_happy())
    all_scenarios.append(gen_autocopy_em4305_happy())
    print(f"  Generated {2} scenarios\n")

    # Category 6: iCLASS
    print("Category 6: iCLASS")
    all_scenarios.append(gen_autocopy_iclass_legacy())
    all_scenarios.append(gen_autocopy_iclass_elite())
    print(f"  Generated {2} scenarios\n")

    # Category 7: ISO15693
    print("Category 7: ISO15693")
    all_scenarios.append(gen_autocopy_iso15693_happy())
    all_scenarios.append(gen_autocopy_iso15693_st())
    print(f"  Generated {2} scenarios\n")

    # Category 8: Cross-type Failures
    print("Category 8: Cross-type Failures")
    all_scenarios.append(gen_autocopy_lf_write_fail())
    all_scenarios.append(gen_autocopy_lf_verify_fail())
    all_scenarios.append(gen_autocopy_mf1k_verify_fail())
    print(f"  Generated {3} scenarios\n")

    # Summary
    print(f"=== TOTAL: {len(all_scenarios)} scenarios generated ===")
    for s in all_scenarios:
        fixture_path = os.path.join(SCENARIOS_DIR, s, 'fixture.py')
        sh_path = os.path.join(SCENARIOS_DIR, s, f'{s}.sh')
        assert os.path.exists(fixture_path), f"Missing: {fixture_path}"
        assert os.path.exists(sh_path), f"Missing: {sh_path}"
        print(f"  {s}/")
        print(f"    fixture.py  OK")
        print(f"    {s}.sh  OK")

    # Generate pm3_fixtures.py registration snippet
    print("\n=== ALL_AUTOCOPY_SCENARIOS dict for tools/pm3_fixtures.py ===")
    print("ALL_AUTOCOPY_SCENARIOS = {")
    for s in all_scenarios:
        print(f"    '{s}': '{s}',")
    print("}")
    print(f"\n# Total: {len(all_scenarios)} autocopy scenarios")

    return all_scenarios


if __name__ == '__main__':
    main()
