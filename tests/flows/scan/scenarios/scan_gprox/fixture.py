# Valid Guardall G-Prox II ID
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info
[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid Guardall G-Prox II ID
[+] FC: 123, CN: 4567
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 13
