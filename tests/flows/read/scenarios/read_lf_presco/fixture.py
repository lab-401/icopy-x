# presco read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid Presco ID
[+] Card ID: 12345678
'''),
    'lf presco read': (0, '''[usb] pm3 --> lf presco read

[+] Presco - Card: 12345678, Raw: 123456780011223344556677
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 36
