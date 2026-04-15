# Auto-Copy scenario: autocopy_ultralight_ev1_happy
# MIFARE Ultralight EV1: mfu dump read + mfu restore write success
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 (Ultralight/NTAG)
#
# PM3 command sequence:
#   hf 14a info
#   hf mfu info
#   hf mfu dump
#   hf mfu restore

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    'hf mfu info': (1, '''
[=] --- Tag Information ---------
[=]       TYPE: Ultralight EV1 (MF0UL1101)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
'''),
    'hf mfu dump': (1, '''[+] Dump file created: /mnt/upan/dump/mfu/MFU_EV1_04A1B2C3D4E5F6_1.bin
'''),
    'hf mfu restore': (1, '''[+] Wrote 41 pages
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 4
