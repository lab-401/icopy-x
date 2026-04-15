# Write scenario: write_lf_fdxb_success
# FDX-B (type 28) clone to T55XX with DRM + verify
#
# Real device trace: docs/Real_Hardware_Intel/fdxb_t55_write_trace_20260328.txt
# Write sequence: wipe → detect(wiped) → clone → detect(cloned) → DRM writes →
#                 detect+password → lf sea → lf fdx read → success
#
# Key: 'lf t55xx detect' is sequential — returns different data after wipe vs clone.
#      'lf t55xx detect p 20206666' is a separate pattern (must appear FIRST for priority).

SCENARIO_RESPONSES = {
    # === Password detect (MUST be before generic detect for substring priority) ===
    'lf t55xx detect p 20206666': (0, '''
[=]      Chip Type      : T55x7
[=]      Modulation     : BIPHASEa - (CDP)
[=]      Bit Rate       : 2 - RF/32
[=]      Inverted       : Yes
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
    # === Write commands ===
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
    'lf t55xx write b 7': (0, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (0, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
    'lf fdx clone': (0, '''[=]       Country code 999
[=]      National code 12345678
[=]     Set animal bit N
[=] Set data block bit N
[=]      Extended data 0x0
[=]                RFU 0
[=] Preparing to clone FDX-B to T55x7 with animal ID: 999-12345678
[+] Blk | Data
[+] ----+------------
[+]  00 | 00098080
[+]  01 | 01A00038
[+]  02 | 0011E780
[+]  03 | 80000000
'''),
    # === Scan/read phase responses ===
    'hf 14a info': (1, '''
'''),
    'lf fdx read': (0, '''[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          999-000012345678
[+] National Code      12345678 (0xBC614E)
[+] Country Code       999
[+] Reserved/RFU       0 (0x0000)
[+]   Animal bit set?  False
[+]       Data block?  False  [value 0x0]
[+] CRC-16             0x74AC (ok)
[+] Raw                0103E820C00103E820C0
'''),
    # === Verify: lf sea must find FDX-B with matching animal ID ===
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=] 
[=] Checking for known tags...
[=] 
[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          0060-030207938416
[+] National Code      030207938416 (0x708888F70)
[+] Country Code       0060
[+] Reserved/RFU       14339 (0x3803)
[+]   Animal bit set?  True
[+]       Data block?  True  [value 0x800000]
[+] CRC-16             0xCE2B (ok)
[+] Raw                0E F1 11 10 E0 F0 E0 0F 

[+] Valid FDX-B ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 28
