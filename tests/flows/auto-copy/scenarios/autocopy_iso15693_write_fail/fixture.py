# Auto-Copy scenario: autocopy_iso15693_write_fail
# ISO15693: dump read succeeds, hf 15 restore returns "restore failed"
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.8 + hf15write_strings.txt ("restore failed")
#
# PM3 command sequence:
#   hf 14a info (no HF14A tag)
#   hf sea (Valid ISO15693)
#   hf 15 dump (success)
#   hf 15 restore (restore failed)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'lf sea': (1, '''[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (1, '''
[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
'''),
    'hf 15 dump': (1, '''[+] Block  0: E0 04 01 00 12 34 56 78
[+] Block  1: 00 00 00 00 00 00 00 00
[+] saved 112 bytes to binary file /mnt/upan/dump/icode/ICODE_E004010012345678_1.bin
'''),
    'hf 15 restore': (1, '''[-] restore failed
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 19
