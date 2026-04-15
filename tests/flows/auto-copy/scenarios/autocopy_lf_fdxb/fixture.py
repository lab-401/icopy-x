# Auto-Copy scenario: autocopy_lf_fdxb
# LF FDXB (type 28): full auto-copy pipeline with T55XX DRM + verify
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6 + awid_write_trace_20260328.txt + fdxb_t55_write_trace_20260328.txt
#
# PM3 command sequence:
#   hf 14a info (passthrough)
#   hf sea (passthrough)
#   lf sea (FDX-B)
#   lf fdx read x2
#   lf t55xx wipe p 20206666
#   lf t55xx detect (after wipe)
#   lf fdx clone
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
    'lf fdx read': (1, '''[+] FDX-B / ISO 11784/5 Animal
[+] Animal ID          0060-030207938416
[+] National Code      030207938416 (0x708888F70)
[+] Country Code       0060
[+] Reserved/RFU       14339 (0x3803)
[+]   Animal bit set?  True
[+]       Data block?  True  [value 0x800000]
[+] CRC-16             0xCE2B (ok)
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
    'lf fdx clone': (1, '''[=]       Country code 60
[=]      National code 30207938416
[=]     Set animal bit N
[=] Set data block bit N
[=]      Extended data 0x0
[=]                RFU 0
[=] Preparing to clone FDX-B to T55x7 with animal ID: 0060-30207938416
[+] Blk | Data
[+] ----+------------
[+]  00 | 00098080
'''),
    'lf t55xx write b 7': (1, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (1, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 28
