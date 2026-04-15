# Write scenario: write_lf_jablotron_success
SCENARIO_RESPONSES = {
    # === Data block writes (B0_WRITE_MAP: raw T55XX block writes) ===
    'lf t55xx write b 1': (0, '''[=] Writing page 0  block: 01  data: 0x00000001
'''),
    'lf t55xx write b 2': (0, '''[=] Writing page 0  block: 02  data: 0x00000002
'''),
    'lf t55xx write b 7': (0, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (0, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
    'lf jablotron read': (0, '''[usb] pm3 --> lf jablotron read

[+] Jablotron - Card: FF010201234568, Raw: 1234567800112233
'''),
    # === Password detect (MUST be before generic detect for substring priority) ===
    'lf t55xx detect p 20206666': (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00098090
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
[=]      Modulation     : BIPHASEa - (CDP)
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : Yes
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00098080
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
[+] Jablotron - Card: 7270a18, Raw: FFFF011999900079
[+] Printed: 1410-01-1999-9000

[+] Valid Jablotron ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 30
