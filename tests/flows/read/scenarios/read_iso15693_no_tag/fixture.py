# ISO15693: no tag found during dump (period required — hf15read.so hasKeyword check)
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid ISO15693 tag found
[+] UID: E0 04 01 00 12 34 56 78
'''),
    'hf 15 dump': (0, '''[usb] pm3 --> hf 15 dump

[-] No tag found.
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 19
