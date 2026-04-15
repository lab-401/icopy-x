# awid read success
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
[+] AWID - len: 222 -unknown- (28635) - Wiegand: 7ad377b79fa2dfb6, Raw: 01deb4ddede7e8b7edbdb7e1

[+] Valid AWID ID found!

Couldn't identify a chipset
'''),
    'lf awid read': (0, '''[usb] pm3 --> lf awid read

[+] Valid AWID ID
[+] FC: 123, CN: 4567
[+] Raw: 2004800000
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 11
