# Auto-Copy scenario: autocopy_mf1k_gen1a
# MF Classic 1K Gen1a: magic card detected via cgetblk, csave read, cload write
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.1 (Gen1a)
#
# Gen1a is detected by scan.so via cgetblk success (Block 0 readable via magic command).
# The read path uses csave (magic dump) instead of fchk+rdsc.
# The write path uses cload (magic load) instead of wrbl.
#
# PM3 command sequence:
#   hf 14a info
#   hf mf cgetblk 0 (success = Gen1a)
#   hf mf csave (dump via magic backdoor)
#   hf mf cload b (write via magic backdoor)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: 11 22 33 44
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (1, '''--block number: 0
Block 0: 11223344080400626364656667686970
'''),
    'hf mf csave': (1, '''[+] saved 1024 bytes to binary file /mnt/upan/dump/mf1/M1-1K-4B_11223344_1.bin
'''),
    'hf mf cload': (1, '''[+] Card loaded 64 blocks from file
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
