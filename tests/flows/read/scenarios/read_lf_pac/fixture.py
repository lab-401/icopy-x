# pac read success
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
[+] PAC/Stanley - Card: 9AAAAAA0, Raw: FF2049906D3B41D0741D0741D0706D23

[+] Valid PAC/Stanley ID found!

Couldn't identify a chipset
'''),
    'lf pac read': (0, '''[usb] pm3 --> lf pac read

[+] PAC/Stanley - Card: FF01020304050607, Raw: AABBCCDD00112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 34
