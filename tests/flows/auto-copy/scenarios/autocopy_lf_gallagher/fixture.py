# Auto-Copy scenario: autocopy_lf_gallagher
# LF GALLAGHER (type 29): full auto-copy pipeline with T55XX DRM + verify
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6 + awid_write_trace_20260328.txt + fdxb_t55_write_trace_20260328.txt
#
# PM3 command sequence:
#   hf 14a info (passthrough)
#   hf sea (passthrough)
#   lf sea (Valid GALLAGHER ID)
#   lf gallagher read x2
#   lf t55xx wipe p 20206666
#   lf t55xx detect (after wipe)
#   lf gallagher clone
#   lf t55xx detect (after clone)
#   lf t55xx write b 7 d 20206666 (DRM)
#   lf t55xx write b 0 (config+pw bit)
#   lf t55xx detect p 20206666 (verify config)
#   lf sea (verify identity)

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
0 -9 -18 -27 -36 -45 -54 -63 -
[=]  Before:  7F D5 8C 3B 8D 8D 8D C3 
[=]  After :  0A CD 60 65 3F 3F 3F 56 
[+] GALLAGHER - Region: 2 FC: 64725 CN: 719622 Issue Level: 6
[+]    Printed: B64725
[+]    Raw: 7FEAA30768D46A35868C35CF
[+]    CRC: 8C - F8 (fail)

[+] Valid GALLAGHER ID found!

Couldn't identify a chipset
'''),
    'lf gallagher read': (1, '''[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
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
    'lf gallagher clone': (1, '''[+] Preparing to clone Gallagher to T55x7
'''),
    'lf t55xx write b 7': (1, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (1, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 29
