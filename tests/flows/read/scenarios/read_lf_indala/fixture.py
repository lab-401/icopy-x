# Indala read success
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
[+] Indala - len 1888, Raw: a0000000ef00000000000000c0e0f0e620000000ff00000000000000

[+] Valid Indala ID found!

Couldn't identify a chipset
'''),
    'lf indala read': (0, '''[usb] pm3 --> lf indala read

[+] Valid Indala ID
[+] Raw: A0 00 00 00 00 12 34 56
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 10
