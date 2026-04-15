# LEGIC: failed to identify tag type
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid LEGIC Prime tag found
[+] MCD: 3C
[+] MSN: 01 02 03
'''),
    'hf legic dump': (0, '''[usb] pm3 --> hf legic dump

[-] Failed to identify tagtype
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 20
