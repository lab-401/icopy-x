# Auto-Copy scenario: autocopy_lf_verify_fail
# LF EM410x: write succeeds, but verify re-scan shows different ID = mismatch
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (Verify Failures)
#
# PM3 command sequence:
#   hf 14a info (passthrough)
#   hf sea (passthrough)
#   lf sea (Valid EM410x — scan)
#   lf em 410x_read (scan)
#   lf t55xx wipe p 20206666
#   lf t55xx detect (after wipe)
#   lf em 410x_write (OK)
#   lf t55xx detect (after clone)
#   lf t55xx write b 7 (DRM)
#   lf t55xx write b 0 (config+pw)
#   lf t55xx detect p 20206666 (DRM verify)
#   lf sea (DRM verify — same ID = write OK)
#   lf em 410x_read (DRM verify — same)
#   === Phase 5: M1 verify ===
#   lf sea (re-verify — different ID = mismatch!)
#   lf em 410x_read (re-verify — different ID)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''[!] Card doesn't support standard iso14443-3 anticollision
'''),
    # Sequential: scan, DRM verify (same ID = write success), Phase 5 verify (different ID = mismatch)
    'lf sea': [
        (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] EM410x pattern found

EM TAG ID      : 0F0368568B

[+] Valid EM410x ID found!
'''),
        (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] EM410x pattern found

EM TAG ID      : 0F0368568B

[+] Valid EM410x ID found!
'''),
        (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[+] EM410x pattern found

EM TAG ID      : 0011223344

[+] Valid EM410x ID found!
'''),
    ],
    # Sequential: read, DRM verify (same), Phase 5 verify (different)
    'lf em 410x_read': [
        (1, '''[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
'''),
        (1, '''[+] EM 410x ID 0F0368568B

EM TAG ID      : 0F0368568B

Possible de-scramble patterns

Unique TAG ID  : F0C016A5D1
'''),
        (1, '''[+] EM 410x ID 0011223344

EM TAG ID      : 0011223344

Possible de-scramble patterns

Unique TAG ID  : 0088CC44AA
'''),
    ],
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
    'lf em 410x_write': (1, '''[+] Writing T55x7 tag with UID 0x0F0368568B
[+] Blk | Data
[+] ----+------------
[+]  00 | 00148040
'''),
    'lf t55xx write b 7': (1, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (1, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
