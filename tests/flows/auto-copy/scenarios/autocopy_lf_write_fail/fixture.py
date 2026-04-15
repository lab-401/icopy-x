# Auto-Copy scenario: autocopy_lf_write_fail
# LF EM410x: scan + read OK, but clone command times out, toast: Write failed
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Write Failures)
#
# PM3 command sequence:
#   hf 14a info (passthrough)
#   hf sea (passthrough)
#   lf sea (Valid EM410x)
#   lf em 410x_read
#   lf t55xx wipe p 20206666
#   lf t55xx detect
#   lf em 410x_write (timeout)

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

[+] EM410x pattern found

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
HoneyWell IdentKey {{
DEZ 8          : 06903435
DEZ 10         : 0867656267
}}
Other          : 22155_003_06903435
Pattern Paxton : 1642715 [0x190F8B]

[+] Valid EM410x ID found!
'''),
    'lf em 410x_read': (1, '''[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
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
    'lf t55xx detect': (1, '''[=]      Chip Type      : T55x7
[=]      Modulation     : ASK
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : Yes
[=]      Block0         : 0x000880E0
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
    'lf em 410x_write': (-1, '''
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
