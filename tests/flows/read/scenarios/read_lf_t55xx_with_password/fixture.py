# T55XX: password found via chk → detect+dump with password
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
    'lf t55xx detect': (0, '''[usb] pm3 --> lf t55xx detect p 51243648

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Bit Rate       : 2 - RF/32
[=] Inverted       : No
[=] Offset         : 33
[=] Seq. Terminator: Yes
[=] Block0         : 0x00148040
[=] Downlink Mode  : default/fixed bit length
[=] Password Set   : Yes
[=] Password       : 51243648
'''),
    'lf t55xx chk': (0, '''[usb] pm3 --> lf t55xx chk f key3

[+] Found valid password: 51243648
'''),
    'lf t55xx dump': (0, '''[usb] pm3 --> lf t55xx dump p 51243648

[+] saved 12 blocks
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 23
