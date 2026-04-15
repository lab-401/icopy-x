# Write scenario: write_iso15693_st_success
# hf15write.so flow (ISO15693_ICODE type 19):
#   1. hf 15 restore f {path}.bin — restore data blocks (checked: Write OK + done)
#   2. hf 15 csetuid {uid} — set UID on target (checked: setting new UID (ok))
#   3. hf sea — verify re-scan (checked: Valid ISO15693)
# NOTE: restore is called FIRST, then csetuid. Response must contain both "Write OK" AND "done".
# NOTE: ISO15693_ST_SA (type 46) is NOT writable. This uses type 19 (ICODE) with same write path.
SCENARIO_RESPONSES = {
    'hf 15 csetuid': (0, '''[usb] pm3 --> hf 15 csetuid E002080112345678

[+] setting new UID (ok)
'''),
    'hf 15 restore': (0, '''[usb] pm3 --> hf 15 restore f /mnt/upan/dump/icode/ICODE_E002080112345678_1.bin

[+] Block  0 - Write OK
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
    'hf 14a info': (1, '''
'''),
    'hf 15 dump': (0, '''[usb] pm3 --> hf 15 dump

[+] Block  0: E0 02 08 01 12 34 56 78
[+] Block  1: 00 00 00 00 00 00 00 00
[+] saved 112 bytes to binary file
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 02 08 01 12 34 56 78
[+] NXP Semiconductors Germany
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 19  # ISO15693_ICODE (type 19) is writable; ISO15693_ST_SA (46) is NOT — both use hf15write.so
