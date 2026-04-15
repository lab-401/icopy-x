# pyramid read success
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
[+] Pyramid - len: 26, FC: 240 Card: 61456 - Wiegand: 1e1e021, Raw: 00010101010101010101015e0e804346

[+] Valid Pyramid ID found!

Couldn't identify a chipset
'''),
    'lf pyramid read': (0, '''[usb] pm3 --> lf pyramid read

[+] Valid Pyramid ID
[+] FC: 123, CN: 4567
[+] Raw: 0000000000001E39
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 16
