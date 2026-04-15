# Write scenario: write_iso15693_restore_fail
# hf15write.so flow (verified via QEMU trace):
#   1. hf 15 restore f {path}.bin — restore fails with "restore failed"
#      hasKeyword("restore failed") triggers write failure — never reaches csetuid
#   No csetuid, no verify phase
SCENARIO_RESPONSES = {
    'hf 15 csetuid': (0, '''[usb] pm3 --> hf 15 csetuid E004010012345678

[+] setting new UID (ok)
'''),
    'hf 15 restore': (0, '''[usb] pm3 --> hf 15 restore f /tmp/dump.bin

[-] restore failed
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
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 19
