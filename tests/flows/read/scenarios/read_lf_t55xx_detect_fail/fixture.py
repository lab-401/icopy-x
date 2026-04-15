# T55XX: no password, detect fails → "Read Failed!"
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[-] No known 125/134 kHz tags found!
'''),
    'data save': (0, '''[+] saved 40000 bytes to /tmp/lf_trace_tmp
'''),
    'hf felica reader': (0, '''[usb] pm3 --> hf felica reader
'''),
    'lf t55xx detect': (-1, ''''''),
    'lf t55xx chk': (0, '''[usb] pm3 --> lf t55xx chk f key3

[-] No valid password found
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 23
