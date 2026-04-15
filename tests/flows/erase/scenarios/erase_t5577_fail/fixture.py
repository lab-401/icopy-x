# Erase T5577 — all strategies fail
# Source: trace_erase_flow_20260330.txt lines 714-722
# Wipe command itself returns OK, but post-verify detect fails ("Could not detect modulation"),
# detect with password also fails, chk finds no valid password — erase failed
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
    'lf t55xx detect': (1, '''[!] Could not detect modulation automatically. Try setting it manually with 'lf t55xx config'
'''),
    'lf t55xx chk': (1, '''[+] loaded 107 keys from dictionary file /tmp/.keys/t5577_tmp_keys.dic
[=] Testing 51243648
[=] Testing 000D8787
[=] Testing 19920427
[=] Testing 65857569
[=] Testing 05D73B9F
[=] Testing 89A69E60
[=] Testing 314159265
[=] Testing FFFFFFFF
[=] Testing 00000000
[=] Testing 11111111
[=] Testing 22222222
[=] Testing 33333333
[=] Testing 44444444
[=] Testing 55555555
[=] Testing 66666666
[=] Testing 77777777
[=] Testing 88888888
[=] Testing 99999999
[=] Testing AAAAAAAAA
[=] Testing BBBBBBBBB
[=] Testing CCCCCCCCC
[=] Testing DDDDDDDDD
[=] Testing EEEEEEEEE
[!] No valid password found
'''),
}
DEFAULT_RETURN = 1
