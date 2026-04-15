# Write MF1K to Gen1a magic card — hf mf cload path.
# PM3 commands from canonical trace lines 226-265:
#   hf 14a info → detects "Magic capabilities : Gen 1a"
#   hf mf cload b <path>.bin → bulk load 64 blocks
#   hf 14a raw -p -a -b 7 40 → BCC fix wake
#   hf 14a raw -p -a 43 → BCC fix auth
#   hf 14a raw -c -p -a e000 → read block 0
#   hf 14a raw -c -p -a e100 → write block 0
#   hf 14a raw -c -p -a 8500... → BCC data
#   hf 14a raw -c -a 5000 → halt
#   hf 14a info → verify UID
# Ground truth: docs/Real_Hardware_Intel/trace_dump_files_20260403.txt
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '\n\n[+]  UID: DA EF B4 16 \n[+] ATQA: 00 04\n[+]  SAK: 08 [2]\n[+] Possible types:\n[+]    MIFARE Classic 1K / Classic 1K CL2\n[=] proprietary non iso14443-4 card found, RATS not supported\n[+] Magic capabilities : Gen 1a\n[+] Prng detection: weak\n'),
    'hf mf cgetblk 0': (1, '\n--block number:0 \n--data: DA EF B4 16 C1 08 04 00 62 63 64 65 66 67 68 69\n'),
    'hf mf cload': (1, '[+] loaded 1024 bytes from binary file /mnt/upan/dump/mf1/M1-1K-4B_DAEFB416_1.bin\n[=] Copying to magic card\n................................................................\n\n[+] Card loaded 64 blocks from file\n'),
    'hf 14a raw': (1, 'received 1 bytes\n0A \n'),
    'hf mf fchk': (1, '[+] found keys:\n[+] | 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |\n'),
    'hf mf wrbl': (1, '[+] isOk:01\n'),
}
DEFAULT_RETURN = 1
