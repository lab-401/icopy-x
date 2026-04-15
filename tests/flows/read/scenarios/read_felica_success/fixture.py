# FeliCa Lite: litedump success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
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
    'hf felica litedump': (0, '''[usb] pm3 --> hf felica litedump

[+] FeliCa Lite dump
[+] State: 0
[+] Polling disabled: No
[+] Authenticated: No
[+] Block  0: 01 FE 01 02 03 04 05 06
[+] Block  1: 00 00 00 00 00 00 00 00
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 21
