# Auto-Copy scenario: autocopy_lf_io_prox
# LF IO_PROX (type 12): full auto-copy pipeline with T55XX DRM + verify
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.3-4.6 + awid_write_trace_20260328.txt + fdxb_t55_write_trace_20260328.txt
#
# PM3 command sequence:
#   hf 14a info (passthrough)
#   hf sea (passthrough)
#   lf sea (Valid IO Prox ID)
#   lf io read x2
#   lf t55xx wipe p 20206666
#   lf t55xx detect (after wipe)
#   lf hid clone (IO Prox routed through write_hid)
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
[+] IO Prox - XSF(00)00:00273, Raw: 0078402010188ff7 (ok)

[+] Valid IO Prox ID found!

Couldn't identify a chipset
'''),
    'lf io read': (1, '''[+] Valid IO Prox ID found!
[+] XSF(01)01:12345
[+] FC: 01, CN: 12345
[+] Raw: 007E018012345000
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
    'lf hid clone': (1, '''[+] Preparing to clone HID to T55x7
[+] Success writing to tag
'''),
    'lf t55xx write b 7': (1, '''[=] Writing page 0  block: 07  data: 0x20206666
'''),
    'lf t55xx write b 0': (1, '''[=] Writing page 0  block: 00  data: 0x00098090
'''),
    'lf t55xx write b': (1, '''[=] Writing page 0  block: 01  data: 0x007E0180
[+] Success writing to tag
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 12
