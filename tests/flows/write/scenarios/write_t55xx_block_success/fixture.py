# Write scenario: write_t55xx_block_success
# T55XX block-by-block write flow:
#   READ: detect(original) x2 → read blocks → dump
#   WRITE: wipe → detect(wiped) x2 → write blocks → detect(restored) → read blocks (verify)
#
# lf t55xx detect uses SEQUENTIAL responses:
#   calls 1-2: original config (READ phase)
#   calls 3-4: wiped config (after wipe)
#   calls 5+:  restored config (after block writes, for verify)

_DETECT_ORIGINAL = (0, '''[usb] pm3 --> lf t55xx detect

[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
''')

_DETECT_WIPED = (0, '''[usb] pm3 --> lf t55xx detect

[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
''')

SCENARIO_RESPONSES = {
    'lf t55xx read b 0': (0, '''[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
'''),
    'lf t55xx read b': (0, '''[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
'''),
    'hf felica reader': (0, '''[usb] pm3 --> hf felica reader
'''),
    'lf t55xx detect': [
        _DETECT_ORIGINAL,  # READ phase call 1
        _DETECT_ORIGINAL,  # READ phase call 2
        _DETECT_WIPED,     # after wipe call 1
        _DETECT_WIPED,     # after wipe call 2
        _DETECT_ORIGINAL,  # after block writes (verify)
    ],
    'lf t55xx write': (0, '''[=] Writing page 0  block: 00  data: 0x00148040
'''),
    'lf t55xx dump': (0, '''[usb] pm3 --> lf t55xx dump

[+] saved 12 blocks
'''),
    'lf t55xx wipe': (0, '''[usb] pm3 --> lf t55xx wipe p 20206666

[=] Begin wiping T55x7 tag

[=] Default configation block 000880E0
[=] Writing page 0  block: 00  data: 0x000880E0 pwd: 0x20206666
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
'''),
    'hf 14a info': (1, '''
'''),
    'data save': (0, '''[+] saved 40000 bytes to /tmp/lf_trace_tmp
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
}
DEFAULT_RETURN = 1
TAG_TYPE = 23
