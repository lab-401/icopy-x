# Auto-Copy scenario: autocopy_mf1k_happy
# MF Classic 1K: all default keys found via fchk, read all sectors, write all blocks
# Ground truth: trace_autocopy_mf1k_standard.txt + full_read_write_trace_20260327.txt
#
# PM3 command sequence:
#   hf 14a info
#   hf mf cgetblk 0
#   hf mf fchk 1 keys
#   hf mf rdsc 0-15
#   hf mf wrbl 0-63
#   hf 14a info (verify)
#   hf mf cgetblk 0 (verify)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: B7 78 5E 50
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+]    MIFARE Plus 2K / Plus EV1 2K
[+]    MIFARE Plus CL2 2K / Plus CL2 EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mf fchk': (1, '''[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys
[=] Running strategy 1
[=] Chunk: 1.1s | found 32/32 keys (85)
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
[+] | 005 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 006 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 007 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 008 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 009 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 010 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 011 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 012 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 013 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 014 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 015 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
'''),
    'hf mf rdsc': (1, '''\n--sector no 0, key B - FF FF FF FF FF FF  \n\nisOk:01\n  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF \n
'''),
    'hf mf rdbl': (1, '''--block no 63, key A - FF FF FF FF FF FF
--data: FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
isOk:01
'''),
    'hf mf wrbl': (1, '''--block no 0, key A - FF FF FF FF FF FF
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
isOk:01
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
