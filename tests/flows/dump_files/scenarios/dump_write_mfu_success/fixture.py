# Write MFU (Ultralight) from dump file — success path.
# PM3 commands from canonical trace lines 201-209:
#   hf mfu restore s e f /mnt/upan/dump/mfu/M0-UL_04DDEEFF001122_1.bin
#   hf 14a info
#   hf mf cgetblk 0
#   hf mfu info
# Ground truth: docs/Real_Hardware_Intel/trace_dump_files_20260403.txt
# Ground truth: working write flow fixture (write_ultralight_success)
SCENARIO_RESPONSES = {
    'hf mfu restore': (0, '[=] Restoring to card...\n[+] loaded 120 bytes from binary file /mnt/upan/dump/mfu/M0-UL_04DDEEFF001122_1.bin\n'),
    'hf 14a info': (0, '\n\n[+]  UID: 04 DD EE FF 00 11 22 \n[+] ATQA: 00 44\n[+]  SAK: 00 [2]\n[+] MANUFACTURER:    NXP Semiconductors Germany\nTYPE: MIFARE Ultralight\n[+]    MIFARE Ultralight/C/NTAG Compatible\n'),
    'hf mf cgetblk 0': (0, '\n--block number: 0 \n[#] wupC1 error\n[!!] Can\'t read block. error=-1\n'),
    'hf mfu info': (0, '\n\n[=] --- Tag Information --------------------------\n[=] -------------------------------------------------------------\n      TYPE: Ultralight (MF0ICU1)\n[+]        UID: 04 DD EE FF 00 11 22 \n[+]     UID[0]: 04, NXP Semiconductors Germany\n      BCC0: 88, crc ok\n[+]       BCC1: 00 (ok)\n[+]   Internal: 48 (default)\n[+]       Lock: 00 00  - 00\n[+] OneTimePad: 00 00 00 00  - 0000\n\n'),
    'hf mfu dump': (0, '[=] MFU dump completed\n[+] saved 120 bytes to binary file\n'),
}
DEFAULT_RETURN = 1
