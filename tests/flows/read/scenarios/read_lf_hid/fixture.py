# HID Prox: read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=] 
[=] Checking for known tags...
[=] 
[+] HID Prox - 2006222332 (4505) - len: 26 bit - OEM: 000 FC: 17 Card: 4505

[+] Valid HID Prox ID found!

Couldn't identify a chipset
'''),
    'lf hid read': (0, '''[usb] pm3 --> lf hid read

[+] Valid HID Prox ID found!
[+] HID Prox - 200068012345
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 9
