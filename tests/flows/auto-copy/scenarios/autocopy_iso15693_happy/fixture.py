# Auto-Copy scenario: autocopy_iso15693_happy
# ISO15693 ICODE: hf 15 dump read + hf 15 restore write success
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.8 (ISO15693)
#
# PM3 command sequence:
#   hf 14a info (no tag)
#   hf sea (Valid ISO15693)
#   hf 15 dump
#   hf 15 restore

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
    # Step 2 of hf15write: set UID after restore — ground truth: V1090_WRITE_FLOW_COMPLETE.md section 8
    'hf 15 csetuid': (1, '''[+] setting new UID (ok)
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
}
DEFAULT_RETURN = 1
TAG_TYPE = 19
