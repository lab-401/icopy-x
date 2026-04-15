# Auto-Copy scenario: autocopy_lf_awid
# LF AWID (type 11): full auto-copy pipeline with T55XX DRM + verify
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6 + awid_write_trace_20260328.txt + fdxb_t55_write_trace_20260328.txt
#
# PM3 command sequence:
#   hf 14a info (passthrough)
#   hf sea (passthrough)
#   lf sea (AWID)
#   lf awid read x2
#   lf t55xx wipe p 20206666
#   lf t55xx detect (after wipe)
#   lf t55xx write b 1-3 (data blocks)
#   lf t55xx write b 0 (config)
#   lf t55xx detect (after write)
#   lf t55xx write b 7 d 20206666 (DRM)
#   lf t55xx write b 0 (config+pw bit)
#   lf t55xx detect p 20206666 (verify config)
#   lf sea + lf awid read (verify identity)

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
[+] AWID - len: 222 -unknown- (28635) - Wiegand: 7ad377b79fa2dfb6, Raw: 01deb4ddede7e8b7edbdb7e1

[+] Valid AWID ID found!

Couldn't identify a chipset
'''),
    'lf awid read': (1, '''[+] AWID - len: 222 -unknown- (63198) - Wiegand: b4ddede7e8b7edbd, Raw: 01deb4ddede7e8b7edbdb7e1
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
    'lf t55xx detect p 20206666': (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : FSK2a
[=]      Bit Rate       : 4 - RF/50
[=]      Inverted       : Yes
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00107070
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : Yes
'''),
    'lf t55xx detect': [
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
    ],
    'lf t55xx write b 7': (1, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (1, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
    'lf t55xx write b 1': (1, '''[=] Writing page 0  block: 01  data: 0x01DEB4DD
'''),
    'lf t55xx write b 2': (1, '''[=] Writing page 0  block: 02  data: 0xEDE7E8B7
'''),
    'lf t55xx write b 3': (1, '''[=] Writing page 0  block: 03  data: 0xEDBDB7E1
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 11
