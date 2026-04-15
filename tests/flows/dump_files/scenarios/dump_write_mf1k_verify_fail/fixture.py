# Write MF1K success, verify failure — write completes OK, then verify detects card removed.
# Seed file: M1-1K-4B_DAEFB416_1.bin
# Ground truth: working write flow fixture (write_mf1k_standard_verify_fail)
#   Write phase: hf 14a info returns matching UID DA EF B4 16 (write succeeds)
#   Verify phase: hf 14a info returns (-1, '') — card removed → "Verification failed"
SCENARIO_RESPONSES = {
    'hf 14a info': [
        # Write phase: exactly 3 calls (initial + 2 post-write verifies)
        (1, '\n\n[+]  UID: DA EF B4 16 \n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n'),
        (1, '\n\n[+]  UID: DA EF B4 16 \n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n'),
        (1, '\n\n[+]  UID: DA EF B4 16 \n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n'),
        # 4th call: M1=Verify phase — card removed → "Verification failed!"
        (-1, ''),
    ],
    'hf mf cgetblk 0': (1, '\n--block number: 0 \n[#] wupC1 error\n[!!] Can\'t read block. error=-1\n'),
    'hf mf fchk': (1, '[+] Loaded 108 keys from /tmp/.keys/mf_tmp_keys\n[=] Running strategy 1\n[=] Chunk: 0.4s | found 32/32 keys (85)\n[=] time in checkkeys (fast) 0.4s\n\n\n[+] found keys:\n[+] |-----|----------------|---|----------------|---|\n[+] | Sec | key A          |res| key B          |res|\n[+] |-----|----------------|---|----------------|---|\n[+] | 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 001 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 002 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 003 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 004 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 005 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 006 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 007 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 008 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 009 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 010 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 011 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 012 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 013 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 014 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 015 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] |-----|----------------|---|----------------|---|\n[+] ( 0:Failed / 1:Success)\n\n'),
    'hf mf wrbl': (1, '--block no 0, key A - FF FF FF FF FF FF \n--data: DA EF B4 16 C1 08 04 00 00 00 00 00 00 00 00 00 \nisOk:01\n'),
    'hf mf rdsc': (-1, ''),
    'hf mf rdbl': (1, '--data: FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF\nisOk:01\n'),
    'hf 14a reader': (1, '[+]  UID: DA EF B4 16\n'),
}
DEFAULT_RETURN = 1
