# paradox read success
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
[=] Paradox - ID: 00c2cc000 FC: 236 Card: 49152, Checksum: 00, Raw: 0f56999a9a5a555555555555

[+] Valid Paradox ID found!

Couldn't identify a chipset
'''),
    'lf paradox read': (0, '''[usb] pm3 --> lf paradox read

[+] Valid Paradox ID found!
[+] FC: 123, CN: 4567
[+] Raw: AABBCCDD00112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 35
