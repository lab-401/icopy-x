# Write scenario: write_lf_em410x_verify_fail
# Clone + DRM protection succeeds, inline verify during write succeeds,
# but EXPLICIT verify (M1 press) reads a DIFFERENT UID → "Verification failed!"
#
# PM3 command sequence (from real test logs):
#   Read phase:
#     lf em 410x_read        [0] scan
#     lf em 410x_read        [1] read
#   Write phase (lfwrite.write + inline lfverify.verify):
#     lf t55xx wipe           wipe with password
#     lf t55xx detect         [0] after wipe
#     lf em 410x_write        clone
#     lf t55xx detect         [1] after clone
#     lf t55xx write b 7      DRM password block
#     lf t55xx write b 0      DRM config block
#     lf t55xx detect p       verify DRM
#     lf sea                  [0] inline verify scan → must match
#     lf em 410x_read         [2] inline verify read → must match
#   Explicit verify phase (lfverify.verify via M1 press):
#     lf sea                  [1] explicit verify scan → tag found (mismatch OK)
#     lf em 410x_read         [3] explicit verify read → DIFFERENT UID
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
    # Sequential lf em 410x_read:
    #   [0]=scan, [1]=read, [2]=inline verify (match), [3]=explicit verify (MISMATCH)
    'lf em 410x': [
        (0, '''[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
'''),
        (0, '''[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
'''),
        (0, '''[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
'''),
        (0, '''[usb] pm3 --> lf em 410x_read

[+] EM 410x ID 0011223344

EM TAG ID      : 0011223344

Possible de-scramble patterns

Unique TAG ID  : 0088CC44AA
'''),
    ],
    # Sequential lf sea:
    #   [0]=inline verify during write (match), [1]=explicit verify (different ID, still tag found)
    'lf sea': [
        (0, '''[usb] pm3 --> lf search

[+] Valid EM410x ID found!
[+] EM410x - Tag ID: 0F0368568B
'''),
        (0, '''[usb] pm3 --> lf search

[+] Valid EM410x ID found!
[+] EM410x - Tag ID: 0011223344
'''),
    ],
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
