# Auto-Copy scenario: autocopy_iclass_write_fail
# iCLASS Legacy: read succeeds, wrbl returns error (no success keyword)
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.7 + iclasswrite_strings.txt
#
# PM3 command sequence:
#   hf 14a info (no HF14A tag)
#   hf sea (Valid iCLASS tag)
#   hf iclass info
#   hf iclass rdbl b 01 k AFA785A7DAB33378
#   hf iclass chk (key found)
#   hf iclass dump (success)
#   hf iclass calcnewkey
#   hf iclass wrbl (error)

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
    # Write phase: calcnewkey succeeds, wrbl FAILS
    'hf iclass calcnewkey': (1, '''[+] Xor div key : A1 B2 C3 D4 E5 F6 A7 B8
'''),
    'hf iclass wrbl': (1, '''[-] Write failed
'''),
    # Generic rdbl fallback: returns data (needed for read/verify phases)
    'hf iclass rdbl': (1, '''Block 06 : 06 01 02 03 04 05 06 07
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 17
