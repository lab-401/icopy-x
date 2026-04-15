# ISO15693 ST Microelectronics SA
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
[+] UID: E0 02 08 01 12 34 56 78
[+] ST Microelectronics SA France
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 46
