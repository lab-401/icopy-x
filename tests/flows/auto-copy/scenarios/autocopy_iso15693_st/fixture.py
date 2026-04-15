# Auto-Copy scenario: autocopy_iso15693_st
# ISO15693 ST Microelectronics: dump + restore + csetuid
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.8 (ISO15693 ST)
#
# PM3 command sequence:
#   hf 14a info (no tag)
#   hf sea (Valid ISO15693 + ST)
#   hf 15 dump
#   hf 15 restore
#   hf 15 csetuid

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'lf sea': (1, '''[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (1, '''
[+] Valid ISO15693 tag found
[+] UID: E0 02 08 01 12 34 56 78
[+] ST Microelectronics SA France
'''),
    'hf 15 dump': (1, '''[+] Block  0: E0 02 08 01 12 34 56 78
[+] Block  1: 00 00 00 00 00 00 00 00
[+] saved 112 bytes to binary file /mnt/upan/dump/icode/ICODE_E002080112345678_1.bin
'''),
    'hf 15 restore': (1, '''[+] Block  0 - Write OK
[+] Block  1 - Write OK
[+] Block  2 - Write OK
[+] Block  3 - Write OK
[+] Block  4 - Write OK
[+] Block  5 - Write OK
[+] Block  6 - Write OK
[+] Block  7 - Write OK
[+] Block  8 - Write OK
[+] Block  9 - Write OK
[+] Block 10 - Write OK
[+] Block 11 - Write OK
[+] Block 12 - Write OK
[+] Block 13 - Write OK
[+] Wrote 14 blocks (112 bytes) to card
[+] done
'''),
    'hf 15 csetuid': (1, '''[+] setting new UID (ok)
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 46
