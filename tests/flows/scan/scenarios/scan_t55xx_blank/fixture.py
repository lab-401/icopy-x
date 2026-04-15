# T55XX blank card (LF signal but no known modulation)
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info
[!] Card doesn't support standard iso14443-3 anticollision
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
    'hf sea': (0, '''[usb] pm3 --> hf search
[!] No known/supported 13.56 MHz tags found
'''),
    'hf felica reader': (0, '''[usb] pm3 --> hf felica reader
'''),
    'lf t55xx detect': (0, '''[usb] pm3 --> lf t55xx detect

[=] Chip Type      : T55x7
[=] Modulation     : ASK
[=] Bit Rate       : 2 - RF/32
[=] Inverted       : No
[=] Offset         : 32
[=] Seq. Terminator: Yes
[=] Block0         : 0x00148040
[=] Downlink Mode  : default/fixed bit length
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 23
