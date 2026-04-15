# FeliCa Lite
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info
[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf felica reader': (0, '''[usb] pm3 --> hf felica reader

[+] FeliCa tag info
[+] IDm: 01 FE 01 02 03 04 05 06
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 21
