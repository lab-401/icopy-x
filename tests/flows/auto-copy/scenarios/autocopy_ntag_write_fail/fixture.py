# Auto-Copy scenario: autocopy_ntag_write_fail
# NTAG215: dump read success, restore fails with block write error
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 (restore failure)
#
# PM3 command sequence:
#   hf 14a info
#   hf mfu info
#   hf mfu dump
#   hf mfu restore (failed to write block)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG215
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    'hf mfu info': (1, '''
[=] --- Tag Information ---------
[=]       TYPE: NTAG 215 504bytes (NT2H1511G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
'''),
    'hf mfu dump': (1, '''[+] Dump file created: /mnt/upan/dump/mfu/NTAG215_04B1C2D3E4F5A6_1.bin
'''),
    'hf mfu restore': (1, '''[!] failed to write block 4
[!] Restoring page 4 failed
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 6
