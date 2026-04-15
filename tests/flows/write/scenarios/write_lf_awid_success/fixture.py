# Write scenario: write_lf_awid_success
# AWID (type 11) write to T55XX via direct block writes (NOT lf awid clone)
#
# Ground truth: docs/Real_Hardware_Intel/awid_write_trace_20260328.txt
# Write sequence:
#   1. lf t55xx wipe p 20206666
#   2. lf t55xx detect             (wiped ASK config)
#   3. lf t55xx write b 1 d XXXX   (raw data block 1)
#   4. lf t55xx write b 2 d XXXX   (raw data block 2)
#   5. lf t55xx write b 3 d XXXX   (raw data block 3)
#   6. lf t55xx write b 0 d 00107060  (AWID FSK2a config)
#   7. lf t55xx detect             (verify FSK2a config)
#   8. lf t55xx write b 7 d 20206666  (DRM password)
#   9. lf t55xx write b 0 d 00107070  (config + password bit)
#  10. lf t55xx detect p 20206666  (verify with password)
#  11. lf sea + lf awid read       (verify tag identity, done twice)
#
# Raw data from lf awid read is 24 hex = 12 bytes = 3 data blocks.

SCENARIO_RESPONSES = {
    # === Password detect (MUST be before generic detect for substring priority) ===
    'lf t55xx detect p 20206666': (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : FSK2a
[=]      Bit Rate       : 4 - RF/50
[=]      Inverted       : Yes
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00107070
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : Yes
'''),
    # === Sequential detect: [0]=after wipe, [1]=after block writes ===
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
[=]      Modulation     : FSK2a
[=]      Bit Rate       : 4 - RF/50
[=]      Inverted       : Yes
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00107060
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
    ],
    # === Write commands — block writes return simple ack ===
    'lf t55xx write b 7': (0, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (0, '''[=] Writing page 0  block: 00  data: 0x00107060
'''),
    'lf t55xx write b 1': (0, '''[=] Writing page 0  block: 01  data: 0x01200480
'''),
    'lf t55xx write b 2': (0, '''[=] Writing page 0  block: 02  data: 0x00000000
'''),
    'lf t55xx write b 3': (0, '''[=] Writing page 0  block: 03  data: 0x00000000
'''),
    'lf t55xx wipe': (0, '''
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
    # === Scan/read phase — AWID raw must be 24 hex digits (12 bytes = 3 data blocks) ===
    'lf awid read': (0, '''[+] AWID - len: 26, FC: 123, CN: 4567 - Wiegand: 200068012345, Raw: 012004800000000000000000
'''),
    'hf 14a info': (1, '''
'''),
    # === Verify: lf sea must find AWID — use "Valid AWID ID" keyword (scan parser checks this) ===
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
}
DEFAULT_RETURN = 1
TAG_TYPE = 11
