# Auto-Copy scenario: autocopy_mf4k_happy
# MF Classic 4K: all default keys found, read 40 sectors, write all blocks
# Ground truth: mf4k_read_trace_20260328.txt + V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1
#
# PM3 command sequence:
#   hf 14a info (SAK 18)
#   hf mf cgetblk 0
#   hf mf fchk 4 keys
#   hf mf rdsc 0-39
#   hf mf wrbl 0-255

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: AA BB CC DD
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mf fchk': (1, '''[+] Loaded 106 keys from /tmp/.keys/mf_tmp_keys
[=] Running strategy 1
[=] Chunk: 1.1s | found 80/80 keys (85)
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
    # 16 blocks per sector — large sectors (32-39) need 16 blocks.
    # Small sectors (0-31) also get 16 blocks; .so uses the correct count
    # based on sector number.
    'hf mf rdsc': (1, '''\n--sector no 0, key B - FF FF FF FF FF FF  \n\nisOk:01\n  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF \n  4 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  5 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  6 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  7 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  8 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n  9 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n 10 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n 11 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n 12 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n 13 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n 14 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 \n 15 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF \n
'''),
    'hw ver': (1, '''
 [ Proxmark3 RFID instrument ]
   firmware............... PM3OTHER
'''),
    'hf mf rdbl': (1, '''--block no 255, key A - FF FF FF FF FF FF
--data: FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
isOk:01
'''),
    'hf mf wrbl': (1, '''--block no 0, key A - FF FF FF FF FF FF
--data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
isOk:01
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 0
