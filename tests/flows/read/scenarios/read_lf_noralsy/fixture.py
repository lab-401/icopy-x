# noralsy read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid Noralsy ID
[+] Card ID: 12345678
'''),
    'lf noralsy read': (0, '''[usb] pm3 --> lf noralsy read

[+] Noralsy - Card: 12345678, Raw: 1234567800112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 33
