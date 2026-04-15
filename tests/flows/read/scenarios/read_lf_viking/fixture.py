# viking read success
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
[+] Viking - Card 99BBB000, Raw: F2000099BBB000C8

[+] Valid Viking ID found!

Couldn't identify a chipset
'''),
    'lf viking read': (0, '''[usb] pm3 --> lf viking read

[+] Viking - Card 12345678, Raw: 1234567800112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 15
