# gprox read success
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[+] Valid Guardall G-Prox II ID
[+] FC: 123, CN: 4567
'''),
    'lf gproxii read': (0, '''[usb] pm3 --> lf gproxii read

[+] Valid Guardall G-Prox II ID
[+] FC: 123, CN: 4567
[+] Raw: 0880088008800880
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 13
