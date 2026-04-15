# ISO14443-B tag
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info
[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid ISO14443-B tag found
[+] UID: AA BB CC DD
[+] ATQB: 50 00 00 00
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 22
