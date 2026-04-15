# Auto-Copy scenario: autocopy_t55xx_happy
# T55XX direct: detect card, dump blocks, wipe + restore, verify by block read-back
# Ground truth: t55_to_t55_write_trace_20260328.txt + V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.5
#
# PM3 command sequence:
#   hf 14a info (no tag)
#   lf sea (no known tag)
#   data save
#   hf sea (no tag)
#   hf felica reader (no tag)
#   lf t55xx detect (success)
#   lf t55xx read b 0-7
#   lf t55xx dump
#   lf t55xx wipe p 20206666
#   lf t55xx detect (after wipe)
#   lf t55xx restore
#   lf t55xx detect (after restore)
#   lf t55xx read b 0-7 (verify)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''[!] Card doesn't support standard iso14443-3 anticollision
'''),
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[-] No known 125/134 kHz tags found!
'''),
    'data save': (1, '''[+] saved 40000 bytes to /tmp/lf_trace_tmp
'''),
    'hf felica reader': (1, '''[!] card timeout
'''),
    'lf t55xx detect': [
        (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
        (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
        (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
        (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
        (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00148040
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
    ],
    'lf t55xx read b 0': (1, '''[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
'''),
    'lf t55xx read b': (1, '''[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
'''),
    # dump response MUST include "saved 12 blocks" — ground truth: lft55xx_strings.txt hasKeyword check
    'lf t55xx dump': (1, '''[+] Reading Page 0:
[+] blk | hex data | binary                           | ascii
[+] ----+----------+----------------------------------+-------
[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@
[+]  01 | 00000000 | 00000000000000000000000000000000 | ....
[+]  02 | 00000000 | 00000000000000000000000000000000 | ....
[+]  03 | 00000000 | 00000000000000000000000000000000 | ....
[+]  04 | 00000000 | 00000000000000000000000000000000 | ....
[+]  05 | 00000000 | 00000000000000000000000000000000 | ....
[+]  06 | 00000000 | 00000000000000000000000000000000 | ....
[+]  07 | 00000000 | 00000000000000000000000000000000 | ....

[+] saved 12 blocks
'''),
    'lf t55xx wipe': (1, '''
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
    'lf t55xx restore': (1, '''[+] loaded 48 bytes from binary file /mnt/upan/dump/t55xx/T55xx_00148040_00000000_00000000_2.bin
[=] Writing page 0  block: 01  data: 0x00000000
[=] Writing page 0  block: 02  data: 0x00000000
[=] Writing page 0  block: 03  data: 0x00000000
[=] Writing page 0  block: 04  data: 0x00000000
[=] Writing page 0  block: 05  data: 0x00000000
[=] Writing page 0  block: 06  data: 0x00000000
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 23
