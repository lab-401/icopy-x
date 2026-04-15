# ISO15693 ICODE
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info
[!] Card doesn't support standard iso14443-3 anticollision
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
DEFAULT_RETURN = -1
TAG_TYPE = 19
