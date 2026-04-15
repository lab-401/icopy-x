# Write scenario: write_lf_gallagher_success
SCENARIO_RESPONSES = {
    'lf gallagher clone': (0, '''[+] Preparing to clone Gallagher to T55x7
'''),
    'lf t55xx write b 7': (0, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (0, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
    'lf gallagher read': (0, '''[usb] pm3 --> lf gallagher read

[+] Valid GALLAGHER ID found!
[+] Raw: AABBCCDDEE001122
'''),
    # === Password detect (MUST be before generic detect for substring priority) ===
    'lf t55xx detect p 20206666': (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00088058
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : Yes
'''),
    # === Sequential detect: [0]=after wipe, [1]=after clone ===
    'lf t55xx detect': [
        (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
        (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x00088048
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
    ],
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
}
DEFAULT_RETURN = 1
TAG_TYPE = 29
