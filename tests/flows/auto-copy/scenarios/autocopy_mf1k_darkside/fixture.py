# Auto-Copy scenario: autocopy_mf1k_darkside
# MF Classic 1K: no default keys, darkside + nested recovery, then read + write
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5 (Key Recovery)
#
# PM3 command sequence:
#   hf 14a info
#   hf mf cgetblk 0
#   hf mf fchk 1 keys (no keys)
#   hf mf darkside (found key)
#   hf mf nested o (all keys)
#   hf mf rdsc 0-15
#   hf mf wrbl 0-63

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
    # Sequential fchk: call 1 = scan phase (no keys on source), call 2 = write phase (target has default keys)
    # Ground truth: full_read_write_trace_20260327.txt lines 47+57 — fchk called TWICE
    'hf mf fchk': [
        (1, '''[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys
[=] Running strategy 1
[=] Chunk: 1.1s | found 0/32 keys (85)
[=] time in checkkeys (fast) 1.1s


[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | ------------   | 0 | ------------   | 0 |
[+] | 001 | ------------   | 0 | ------------   | 0 |
[+] | 002 | ------------   | 0 | ------------   | 0 |
[+] | 003 | ------------   | 0 | ------------   | 0 |
[+] | 004 | ------------   | 0 | ------------   | 0 |
[+] | 005 | ------------   | 0 | ------------   | 0 |
[+] | 006 | ------------   | 0 | ------------   | 0 |
[+] | 007 | ------------   | 0 | ------------   | 0 |
[+] | 008 | ------------   | 0 | ------------   | 0 |
[+] | 009 | ------------   | 0 | ------------   | 0 |
[+] | 010 | ------------   | 0 | ------------   | 0 |
[+] | 011 | ------------   | 0 | ------------   | 0 |
[+] | 012 | ------------   | 0 | ------------   | 0 |
[+] | 013 | ------------   | 0 | ------------   | 0 |
[+] | 014 | ------------   | 0 | ------------   | 0 |
[+] | 015 | ------------   | 0 | ------------   | 0 |
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
'''),
        (1, '''[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys
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
    ],
    'hf mf darkside': (1, '''[+] found valid key: a0a1a2a3a4a5
'''),
    'hf mf nested': (1, '''[+] Testing known keys. Sector count 16
[+] Time to go: 0
[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 001 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 002 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 003 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 004 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 005 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 006 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 007 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 008 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 009 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 010 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 011 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 012 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 013 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 014 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
[+] | 015 | a0a1a2a3a4a5   | 1 | b0b1b2b3b4b5   | 1 |
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
DEFAULT_RETURN = 1
TAG_TYPE = 1
