# Write scenario: write_iclass_legacy_fail
# iCLASS Legacy (type 17): read succeeds, write fails (wrbl returns -1)
# The "Write failed!" toast appears because startPM3Task returns -1.
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
    # --- Write phase: wrbl FAILS ---
    'hf iclass wrbl': (-1, ''),
    # --- Write/Verify phase: readTagBlock reads blocks back ---
    # Block 03 (password block) — for writePassword readback
    'hf iclass rdbl b 03': (0, '''Block 03 : AE A6 84 A6 DA B2 12 32
'''),
    # Generic rdbl — matches write/verify calls (block 6+)
    # Returns block data so getNeedWriteBlock finds blocks to write
    'hf iclass rdbl': (0, '''Block 06 : 00 00 00 00 00 00 00 00
'''),
    # --- Scan phase: 14a/LF must fail ---
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 17
