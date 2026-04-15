# Write scenario: write_lf_em410x_success
SCENARIO_RESPONSES = {
    'lf t55xx write b 7': (0, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (0, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
    'lf em 410x_write': (0, '''[usb] pm3 --> lf em 410x_write 0F0368568B 1

[+] Writing T55x7 tag with UID 0x0F0368568B
[+] Blk | Data
[+] ----+------------
[+]  00 | 00148040
[+]  01 | FF8C6584
[+]  02 | 00680D1A
'''),
    # === Password detect (MUST be before generic detect for substring priority) ===
    'lf t55xx detect p 20206666': (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00148050
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
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00148040
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
    'lf em 410x': (0, '''[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
'''),
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=] 
[=] Checking for known tags...
[=] 
[+] EM410x pattern found

EM TAG ID      : 1111000000

Possible de-scramble patterns

Unique TAG ID  : 8888000000
HoneyWell IdentKey {
DEZ 8          : 00000000
DEZ 10         : 0285212672
DEZ 5.5        : 04352.00000
DEZ 3.5A       : 017.00000
DEZ 3.5B       : 017.00000
DEZ 3.5C       : 000.00000
DEZ 14/IK2     : 00073299656704
DEZ 15/IK3     : 000586397253632
DEZ 20/ZK      : 08080808000000000000
}
Other          : 00000_000_00000000
Pattern Paxton : 286539264 [0x11143E00]
Pattern 1      : 0 [0x0]
Pattern Sebury : 0 0 0  [0x0 0x0 0x0]

[+] Valid EM410x ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
