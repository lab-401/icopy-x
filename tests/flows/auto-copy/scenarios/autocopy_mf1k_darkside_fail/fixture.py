# Auto-Copy scenario: autocopy_mf1k_darkside_fail
# MF Classic 1K: static nonce card, darkside attack fails, toast: No valid key
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 5 (Key Recovery - static nonce)
#
# PM3 command sequence:
#   hf 14a info (Static nonce: yes)
#   hf mf cgetblk 0
#   hf mf fchk 1 keys (no keys)
#   hf mf darkside (fails)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: AA BB CC DD
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Static nonce: yes
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mf fchk': (1, '''[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys
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
    'hf mf darkside': (1, '''[-] This card is not vulnerable to Darkside attack
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
