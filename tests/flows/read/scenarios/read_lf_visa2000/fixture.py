# visa2000 read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid Visa2000 ID
[+] Card ID: 12345678
'''),
    'lf visa2000 read': (0, '''[usb] pm3 --> lf visa2000 read

[+] Visa2000 - Card 12345678, Raw: 1234567800112233
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 37
