# Auto-Copy scenario: autocopy_iclass_legacy
# iCLASS Legacy: key check with standard key, dump blocks, calcnewkey + wrbl write
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.7 (iCLASS)
#
# PM3 command sequence:
#   hf 14a info (no tag)
#   hf sea (Valid iCLASS tag)
#   hf iclass info
#   hf iclass rdbl b 01 k AFA785A7DAB33378
#   hf iclass chk
#   hf iclass dump
#   hf iclass calcnewkey
#   hf iclass wrbl

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'lf sea': (1, '''[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (1, '''
[+] Valid iCLASS tag / PicoPass tag found
'''),
    'hf iclass info': (1, '''
[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
'''),
    # Scan phase: standard key rdbl succeeds -> ICLASS_LEGACY (type 17)
    'hf iclass rdbl b 01 k AFA785A7DAB33378': (1, '''
Block 01 : 12 FF FF FF 7F 1F FF 3C
'''),
    'hf iclass chk': (1, '''
[+] Found valid key afa785a7dab33378
'''),
    'hf iclass dump': (1, '''[+] saving dump file - 19 blocks read
'''),
    # Write phase: calcnewkey + wrbl
    'hf iclass calcnewkey': (1, '''[+] Xor div key : A1 B2 C3 D4 E5 F6 A7 B8
'''),
    'hf iclass wrbl': (1, '''[+] Write block 6 successful
'''),
    # Verify phase: readBlockHex reads blocks back to confirm write
    # Block 03 = password block (must match calcnewkey result)
    'hf iclass rdbl b 03': (1, '''Block 03 : A1 B2 C3 D4 E5 F6 A7 B8
'''),
    # Per-block rdbl for verify phase — must match generate_write_dump.py iclass_dump() data
    # blocks[i] = bytes([i, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
    'hf iclass rdbl b 06': (1, 'Block 06 : 06 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 07': (1, 'Block 07 : 07 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 08': (1, 'Block 08 : 08 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 09': (1, 'Block 09 : 09 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0a': (1, 'Block 0a : 0A 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0b': (1, 'Block 0b : 0B 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0c': (1, 'Block 0c : 0C 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0d': (1, 'Block 0d : 0D 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0e': (1, 'Block 0e : 0E 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 0f': (1, 'Block 0f : 0F 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 10': (1, 'Block 10 : 10 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 11': (1, 'Block 11 : 11 01 02 03 04 05 06 07\n'),
    'hf iclass rdbl b 12': (1, 'Block 12 : 12 01 02 03 04 05 06 07\n'),
    # Generic rdbl fallback for any other block
    'hf iclass rdbl': (1, 'Block 06 : 06 01 02 03 04 05 06 07\n'),
}
DEFAULT_RETURN = 1
TAG_TYPE = 17
