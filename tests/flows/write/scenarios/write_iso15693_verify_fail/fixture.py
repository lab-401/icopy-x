# Write scenario: write_iso15693_verify_fail
# hf15write.so flow (verified via QEMU trace):
#   1. hf 15 restore f {path}.bin — succeeds with "Write OK" + "done"
#   2. hf 15 csetuid {uid} — succeeds
#   3. hf sea — verify re-scan → tag NOT found → verify fails
# NOTE: restore is called FIRST, then csetuid. Response must contain both "Write OK" AND "done".
#
# 'hf sea' is sequential: [0]=scan phase (tag found), [1]=verify phase (no tag)
SCENARIO_RESPONSES = {
    'hf 15 csetuid': (0, '''[usb] pm3 --> hf 15 csetuid E004010012345678

[+] setting new UID (ok)
'''),
    'hf 15 restore': (0, '''[usb] pm3 --> hf 15 restore f /mnt/upan/dump/icode/ICODE_E004010012345678_1.bin

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

[+] Block  0: E0 04 01 00 12 34 56 78
[+] Block  1: 00 00 00 00 00 00 00 00
[+] saved 112 bytes to binary file
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    # Sequential: [0]=scan phase, [1]=write internal verify (must pass), [2]=separate M1 verify (fails)
    'hf sea': [
        (0, '''[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
'''),
        (0, '''[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
'''),
        (0, '''[usb] pm3 --> hf search

[!] No known/supported 13.56 MHz tags found
'''),
    ],
}
DEFAULT_RETURN = 1
TAG_TYPE = 19
