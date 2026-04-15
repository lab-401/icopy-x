# Auto-Copy scenario: autocopy_mf1k_partial_keys
# MF Classic 1K: fchk finds partial keys, nested does not complete, toast: Missing keys
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5 (Key Recovery - partial)
#
# PM3 command sequence:
#   hf 14a info
#   hf mf cgetblk 0
#   hf mf fchk 1 keys (8/32)
#   hf mf nested o (timeout)

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
[=] Chunk: 1.1s | found 8/32 keys (85)
[=] time in checkkeys (fast) 1.1s


[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 001 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 002 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 003 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 004 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 005 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 006 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 007 | ffffffffffff   | 1 | ------------   | 0 |
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
    # nested returns -1: card lost / timeout during nested attack.
    # .so sees nested failure → can't recover remaining keys → "Missing keys" toast.
    # Non-empty content ensures CACHE is updated for hasKeyword checks.
    'hf mf nested': (-1, '''[-] Can't select card (ALL)
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
