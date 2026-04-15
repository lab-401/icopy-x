# Erase MF Classic 1K — keys found but wrbl fails (access bits prevent writes)
# Source: trace_erase_flow_20260330.txt lines 688-706
# SAK 08 = 1K, not Gen1a (wupC1 error), fchk finds 32/32 keys (484558414354),
# wrbl returns isOk:00 with "Write block error" — erase fails
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: 0A D0 7A B8
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+]    MIFARE Plus 2K / Plus EV1 2K
[+]    MIFARE Plus CL2 2K / Plus CL2 EV1 2K
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mf fchk': (1, '''[+] Loaded 108 keys from /tmp/.keys/mf_tmp_keys
[=] Running strategy 1
[=] Chunk: 1.9s | found 32/32 keys (85)
[=] time in checkkeys (fast) 1.9s


[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 001 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 002 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 003 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 004 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 005 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 006 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 007 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 008 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 009 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 010 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 011 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 012 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 013 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 014 | 484558414354   | 1 | 484558414354   | 1 |
[+] | 015 | 484558414354   | 1 | 484558414354   | 1 |
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
'''),
    'hf mf wrbl': (1, '''--block no 60, key A - 48 45 58 41 43 54
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
[#] Cmd Error: 04
[#] Write block error
isOk:00
'''),
}
DEFAULT_RETURN = 1
