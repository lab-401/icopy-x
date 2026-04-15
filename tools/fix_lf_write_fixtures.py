#!/usr/bin/env python3

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

"""Fix all LF write fixtures to use sequential detect responses.

The .so reads Block0 from `lf t55xx detect` after clone and uses it to compute
the DRM password config. The detect after clone must return the cloned config
(not the wiped default). The password detect must show Password Set: Yes.

Block0 values per type from PM3 clone responses and standard T55XX configs:
- EM410x:  00148040 (ASK/Manchester, RF/64)
- HID:     00107060 (FSK2a, RF/50)
- FDX-B:   00098080 (BIPHASEa, RF/32, Inv)
- Others:  00148040 (generic ASK — .so doesn't check modulation string)
"""

import os, re, sys

# Block0 configs per type. For unknown types, use 00148040 (ASK default).
# The .so reads Block0 from detect to compute password bit, but doesn't validate modulation.
BLOCK0_MAP = {
    8:  '00148040',  # EM410x (from clone response)
    9:  '00107060',  # HID (from clone response)
    10: '00082040',  # Indala (PSK1)
    11: '00107060',  # AWID (FSK2a, same as HID)
    12: '00147060',  # IO ProxII (FSK2a, RF/64)
    13: '00107060',  # GProx (FSK2a)
    14: '00107060',  # Securakey (FSK2)
    15: '00088048',  # Viking (ASK/Manchester)
    16: '00107080',  # Pyramid (FSK2a, 4 blocks)
    28: '00098080',  # FDX-B (BIPHASEa)
    29: '00088048',  # Gallagher (ASK/Manchester)
    30: '00098080',  # Jablotron (BIPHASEa, like FDX-B)
    31: '00040040',  # Keri (PSK)
    32: '00107060',  # Nedap (FSK2)
    33: '00088080',  # Noralsy (ASK)
    34: '00088080',  # PAC (ASK)
    35: '00107060',  # Paradox (FSK2a)
    36: '00088040',  # Presco (ASK/Manchester)
    37: '00088040',  # Visa2000 (ASK/Manchester)
    45: '00107060',  # NexWatch (FSK2)
}

# Modulation parameters from Block0 config
MODULATION_MAP = {
    '00148040': ('ASK', '5 - RF/64', 'No', 'No'),
    '00107060': ('FSK2a', '4 - RF/50', 'No', 'No'),
    '00107080': ('FSK2a', '4 - RF/50', 'No', 'No'),
    '00082040': ('PSK1', '2 - RF/32', 'No', 'No'),
    '00098080': ('BIPHASEa - (CDP)', '2 - RF/32', 'Yes', 'No'),
    '00088048': ('ASK', '2 - RF/32', 'No', 'Yes'),
    '00088080': ('ASK', '2 - RF/32', 'No', 'No'),
    '00088040': ('ASK', '2 - RF/32', 'No', 'No'),
    '00040040': ('PSK1', '2 - RF/32', 'No', 'No'),
    '00147060': ('FSK2a', '5 - RF/64', 'No', 'No'),
}

def detect_response(block0_hex, password_set=False):
    """Generate a detect response string for given Block0."""
    mod, br, inv, st = MODULATION_MAP.get(block0_hex, ('ASK', '2 - RF/32', 'No', 'No'))
    pwd = 'Yes' if password_set else 'No'
    return f'''
[=]      Chip Type      : T55x7
[=]      Modulation     : {mod}
[=]      Bit Rate       : {br}
[=]      Inverted       : {inv}
[=]      Offset         : 33
[=]      Seq. Term.     : {st}
[=]      Block0         : 0x{block0_hex.upper()}
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : {pwd}
'''


def fix_fixture(fixture_path):
    """Fix a single LF write fixture with sequential detect responses."""
    with open(fixture_path) as f:
        content = f.read()

    # Extract TAG_TYPE
    m = re.search(r'TAG_TYPE\s*=\s*(\d+)', content)
    if not m:
        print(f'  SKIP {fixture_path}: no TAG_TYPE')
        return False
    tag_type = int(m.group(1))

    # Skip if already has sequential detect (list format)
    if re.search(r"'lf t55xx detect'\s*:\s*\[", content):
        print(f'  SKIP {fixture_path}: already sequential (type {tag_type})')
        return False

    block0 = BLOCK0_MAP.get(tag_type, '00148040')
    block0_pwd = f'{int(block0, 16) | 0x10:08X}'

    detect_wiped = detect_response('000880E0', password_set=False)
    detect_cloned = detect_response(block0, password_set=False)
    detect_pwd = detect_response(block0_pwd, password_set=True)

    # Build new SCENARIO_RESPONSES dict by parsing the old one
    # Strategy: read the file, find detect entries, replace with sequential
    lines = content.split('\n')
    new_lines = []
    i = 0
    inserted_pwd_detect = False
    inserted_seq_detect = False

    while i < len(lines):
        line = lines[i]

        # Replace 'lf t55xx detect p' entry (password detect) — or skip if exists
        if "'lf t55xx detect p" in line and not inserted_pwd_detect:
            # Skip old password detect entry (may span multiple lines until next entry)
            while i < len(lines) and not (i > 0 and re.match(r"\s+'[^']+'\s*:", lines[i]) and "'lf t55xx detect p" not in lines[i]):
                i += 1
                if i < len(lines) and ("')," in lines[i-1] or "''')," in lines[i-1]):
                    break
            # Will insert new one with the sequential detect
            continue

        # Replace 'lf t55xx detect' entry
        if re.search(r"'lf t55xx detect'\s*:", line) and not inserted_seq_detect:
            # Find the end of this dict entry (next key or closing brace)
            indent = '    '

            # Insert password detect FIRST (for substring priority)
            new_lines.append(f"{indent}# === Password detect (MUST be before generic detect for substring priority) ===")
            new_lines.append(f"{indent}'lf t55xx detect p 20206666': (0, '''{detect_pwd}'''),")
            inserted_pwd_detect = True

            # Insert sequential detect
            new_lines.append(f"{indent}# === Sequential detect: [0]=after wipe, [1]=after clone ===")
            new_lines.append(f"{indent}'lf t55xx detect': [")
            new_lines.append(f"{indent}    (0, '''{detect_wiped}'''),")
            new_lines.append(f"{indent}    (0, '''{detect_cloned}'''),")
            new_lines.append(f"{indent}],")
            inserted_seq_detect = True

            # Skip old detect entry
            while i < len(lines):
                i += 1
                if i >= len(lines):
                    break
                if "')," in lines[i-1] or "''')," in lines[i-1]:
                    break
            continue

        new_lines.append(line)
        i += 1

    new_content = '\n'.join(new_lines)
    with open(fixture_path, 'w') as f:
        f.write(new_content)

    print(f'  FIXED {os.path.basename(os.path.dirname(fixture_path))} (type {tag_type}, Block0={block0})')
    return True


def main():
    scenarios_dir = os.path.join(os.path.dirname(__file__), '..', 'tests', 'flows', 'write', 'scenarios')
    scenarios_dir = os.path.abspath(scenarios_dir)

    fixed = 0
    for name in sorted(os.listdir(scenarios_dir)):
        if not name.startswith('write_lf_') or not name.endswith('_success'):
            continue
        # Skip FDXB — already fixed manually
        if name == 'write_lf_fdxb_success':
            continue
        fixture_path = os.path.join(scenarios_dir, name, 'fixture.py')
        if os.path.exists(fixture_path):
            if fix_fixture(fixture_path):
                fixed += 1

    print(f'\nFixed {fixed} fixtures')


if __name__ == '__main__':
    main()
