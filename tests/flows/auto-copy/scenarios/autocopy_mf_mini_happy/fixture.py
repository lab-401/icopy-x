# Auto-Copy scenario: autocopy_mf_mini_happy
# MIFARE Mini (type 25): 5 sectors, all default keys, read + write success
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 (MIFARE Classic variants)
#
# PM3 command sequence:
#   hf 14a info (SAK 09)
#   hf mf cgetblk 0
#   hf mf fchk 0 keys
#   hf mf rdsc 0-4
#   hf mf wrbl 0-19

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: DE AD BE EF
[+] ATQA: 00 04
[+]  SAK: 09 [2]
[+] Possible types:
[+]    MIFARE Mini
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mf fchk': (1, '''[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys
[=] Running strategy 1
[=] Chunk: 1.1s | found 10/10 keys (85)
[=] time in checkkeys (fast) 1.1s


[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 001 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 002 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 003 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 004 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
'''),
    'hf mf rdsc': (1, '''\n--sector no 0, key B - FF FF FF FF FF FF  \n\nisOk:01\n  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF \n
'''),
    'hf mf rdbl': (1, '''--block no 19, key A - FF FF FF FF FF FF
--data: FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
isOk:01
'''),
    'hf mf wrbl': (1, '''--block no 0, key A - FF FF FF FF FF FF
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
isOk:01
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 25
