# nexwatch read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid NexWatch ID
[+] Raw: AABBCCDD00112233
'''),
    'lf nexwatch read': (0, '''[usb] pm3 --> lf nexwatch read

[+] NexWatch, Quadrakey
[+] ID: AABBCCDD00112233
[+] Raw: AABBCCDD0011223344556677
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 45
