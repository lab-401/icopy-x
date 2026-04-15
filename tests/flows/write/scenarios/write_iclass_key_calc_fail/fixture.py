# Write scenario: write_iclass_key_calc_fail
SCENARIO_RESPONSES = {
    'hf iclass rdbl b 01 k AFA785A7DAB33378': (0, '''[usb] pm3 --> hf iclass rdbl b 01 k AFA785A7DAB33378

Block 01 : 12 FF FF FF 7F 1F FF 3C
'''),
    'hf iclass calcnewkey': (-1, ''''''),
    # Generic rdbl — matches write/verify phase readTagBlock calls (block 6+)
    # Returns all-zero data so getNeedWriteBlock detects mismatch with dump file
    'hf iclass rdbl': (0, '''Block 06 : 00 00 00 00 00 00 00 00
'''),
    'hf iclass info': (0, '''[usb] pm3 --> hf iclass info

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
'''),
    'hf iclass dump': (0, '''[usb] pm3 --> hf iclass dump k aea684a6dab21232

[+] saving dump file - 19 blocks read
'''),
    'hf iclass chk': (0, '''[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
'''),
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid iCLASS tag / PicoPass tag found
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 17
