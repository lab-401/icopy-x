# Erase MF Classic 4K — standard erase with all default keys, success
# Source: trace_erase_flow_20260330.txt lines 16-538
# SAK 18 = 4K, not Gen1a (wupC1 error), fchk 4 finds 80/80 keys, wrbl isOk:01
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: 00 00 00 00
[+] ATQA: 00 02
[+]  SAK: 18 [2]
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
[=] Chunk: 0.6s | found 80/80 keys (85)
[=] time in checkkeys (fast) 0.6s


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
[+] | 016 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 017 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 018 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 019 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 020 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 021 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 022 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 023 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 024 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 025 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 026 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 027 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 028 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 029 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 030 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 031 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 032 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 033 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 034 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 035 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 036 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 037 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 038 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 039 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
'''),
    'hf mf wrbl': (1, '''--block no 240, key A - FF FF FF FF FF FF
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
isOk:01
'''),
}
DEFAULT_RETURN = 1
