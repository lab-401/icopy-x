# Erase T5577 DRM-locked tag — success
# Source: trace_erase_flow_20260330.txt lines 707-713
# T5577 with DRM password 20206666; wipe with password succeeds,
# post-verify detect shows Chip Type T55x7 (no password needed after wipe)
SCENARIO_RESPONSES = {
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
[=]      Block0         : 0x000880E0 (auto detect)
[=]      Downlink Mode  : default/fixed bit length
[=]      Password Set   : No
'''),
}
DEFAULT_RETURN = 1
