# Write scenario: write_lf_io_success
# IO ProxII (type 12) write to T55XX via direct block writes (same as AWID)
#
# Ground truth: docs/Real_Hardware_Intel/awid_write_trace_20260328.txt (same pattern)
# IO Prox uses FSK2a RF/64 (Block0=00147060), raw 24 hex = 3 data blocks.

SCENARIO_RESPONSES = {
    # === Password detect (MUST be before generic detect for substring priority) ===
    'lf t55xx detect p 20206666': (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : FSK2a
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00147070
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
[=]      Bit Rate       : 5 - RF/64
[=]      Inverted       : No
[=]      Offset         : 33
[=]      Seq. Term.     : No
[=]      Block0         : 0x00147060
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
    ],
    # === Write commands ===
    'lf t55xx write b 7': (0, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (0, '''[=] Writing page 0  block: 00  data: 0x00147060
'''),
    'lf t55xx write b 1': (0, '''[=] Writing page 0  block: 01  data: 0x007E0180
'''),
    'lf t55xx write b 2': (0, '''[=] Writing page 0  block: 02  data: 0xA5000000
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
    # === Scan/read — IO Prox raw must be 24+ hex digits for 3 data blocks ===
    'lf io read': (0, '''[+] IO Prox - XSF(01)01:12345, Raw: 007E0180A500000000000000
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
[+] IO Prox - XSF(00)00:00273, Raw: 0078402010188ff7 (ok)

[+] Valid IO Prox ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 12
