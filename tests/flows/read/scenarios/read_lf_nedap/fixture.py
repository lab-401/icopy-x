# nedap read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid NEDAP ID
[+] Card ID: 12345678
'''),
    'lf nedap read': (0, '''[usb] pm3 --> lf nedap read

[+] NEDAP - Card: 12345678, Raw: 1234567800112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 32
