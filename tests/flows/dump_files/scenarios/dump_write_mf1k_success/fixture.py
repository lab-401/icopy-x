# Write MF1K from dump file — standard (non-Gen1a) success path.
# PM3 commands from canonical trace lines 12-147:
#   hf 14a info → hf mf cgetblk 0 (wupC1 error) → hf mf fchk → hf mf wrbl ×64
# Seed file: M1-1K-4B_DAEFB416_1.bin
# Ground truth: docs/Real_Hardware_Intel/trace_dump_files_20260403.txt
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '\n\n[+]  UID: DA EF B4 16 \n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Prng detection: weak\n'),
    'hf mf cgetblk 0': (1, '\n--block number: 0 \n[#] wupC1 error\n[!!] Can\'t read block. error=-1\n'),
    'hf mf fchk': (1, '[+] Loaded 108 keys from /tmp/.keys/mf_tmp_keys\n[=] Running strategy 1\n[=] Chunk: 0.4s | found 32/32 keys (85)\n[=] time in checkkeys (fast) 0.4s\n\n\n[+] found keys:\n[+] |-----|----------------|---|----------------|---|\n[+] | Sec | key A          |res| key B          |res|\n[+] |-----|----------------|---|----------------|---|\n[+] | 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 001 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 002 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 003 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 004 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 005 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 006 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 007 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 008 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 009 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 010 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 011 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 012 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 013 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 014 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] | 015 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n[+] |-----|----------------|---|----------------|---|\n[+] ( 0:Failed / 1:Success)\n\n'),
    'hf mf wrbl': (1, '--block no 0, key A - FF FF FF FF FF FF \n--data: DA EF B4 16 C1 08 04 00 00 00 00 00 00 00 00 00 \nisOk:01\n'),
    'hf mf rdbl': (1, '--data: DA EF B4 16 C1 08 04 00 00 00 00 00 00 00 00 00\nisOk:01\n'),
    'hf 14a reader': (1, '[+]  UID: DA EF B4 16\n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n'),
}
DEFAULT_RETURN = 1
