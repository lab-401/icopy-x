# Write scenario: write_iclass_key_calc_success
# iCLASS Legacy (type 17): standard key succeeds, calcNewKey + wrbl succeeds
# The writePassword flow: calcnewkey → wrbl with calculated key
#
# Dict order matters — mock matches FIRST substring hit.
# More specific patterns MUST come before less specific ones.
SCENARIO_RESPONSES = {
    # --- Scan phase: type detection ---
    # Standard key rdbl succeeds → type ICLASS_LEGACY (17)
    'hf iclass rdbl b 01 k AFA785A7DAB33378': (0, '''[usb] pm3 --> hf iclass rdbl b 01 k AFA785A7DAB33378

Block 01 : 12 FF FF FF 7F 1F FF 3C
'''),
    'hf iclass info': (0, '''[usb] pm3 --> hf iclass info

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid iCLASS tag / PicoPass tag found
'''),
    # --- Read phase ---
    'hf iclass dump': (0, '''[usb] pm3 --> hf iclass dump k AFA785A7DAB33378

[+] saving dump file - 19 blocks read
'''),
    # --- Read phase: key check ---
    'hf iclass chk': (0, '''[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
'''),
    # --- Write phase: key calculation ---
    'hf iclass calcnewkey': (0, '''[usb] pm3 --> hf iclass calcnewkey o aea684a6dab21232 n 0102030405060708

[+] Xor div key : AB CD EF 01 23 45 67 89
'''),
    # --- Write phase: block write ---
    'hf iclass wrbl': (0, '''[+] Write block 3 successful
'''),
    # --- Write/Verify phase: readTagBlock reads blocks back ---
    # Block 03 (password block) — must match calcnewkey result for writePassword verify
    'hf iclass rdbl b 03': (0, '''Block 03 : AB CD EF 01 23 45 67 89
'''),
    # Verify reads block 01 with the chk key after password write
    'hf iclass rdbl b 01 k aea684a6dab21232': (0, 'Block 01 : 12 FF FF FF 7F 1F FF 3C\n'),
    # Per-block rdbl for blocks 6-18: data matches generate_write_dump.py output
    # PM3 uses HEX block numbers: block 10 = b 0a, block 18 = b 12
    'hf iclass rdbl b 06': (0, 'Block 06 : 06 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 07': (0, 'Block 07 : 07 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 08': (0, 'Block 08 : 08 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 09': (0, 'Block 09 : 09 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0a': (0, 'Block 0a : 0A 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0b': (0, 'Block 0b : 0B 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0c': (0, 'Block 0c : 0C 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0d': (0, 'Block 0d : 0D 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0e': (0, 'Block 0e : 0E 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0f': (0, 'Block 0f : 0F 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 10': (0, 'Block 10 : 10 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 11': (0, 'Block 11 : 11 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 12': (0, 'Block 12 : 12 01 02 03 04 05 06 07\n'),
    # --- Scan phase: 14a/LF must fail ---
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 17
