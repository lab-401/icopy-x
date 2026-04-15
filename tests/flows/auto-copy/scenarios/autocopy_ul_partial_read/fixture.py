# Auto-Copy scenario: autocopy_ul_partial_read
# MIFARE Ultralight: hf mfu dump returns "Partial dump created", partial data still written
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 4.2 + hfmfuread_strings.txt ("Partial dump created")
#
# PM3 command sequence:
#   hf 14a info
#   hf mfu info
#   hf mfu dump (Partial dump created — returns -1 with keyword)
#   hf mfu restore (write succeeds with partial data)
#
# NOTE: hf mfu dump returns -1 for partial dump. hfmfuread.so checks
# hasKeyword("Partial dump created") to distinguish partial from total failure.
# With ret=1 the module treats it as full success then rejects the file.

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
[=]       TYPE: Ultralight (MF0ICU1)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
'''),
    # ret=-1 signals non-clean completion; hasKeyword("Partial dump created")
    # distinguishes partial success from total failure in hfmfuread.so
    'hf mfu dump': (-1, '''[+] Partial dump created: /mnt/upan/dump/mfu/MFU_04A1B2C3D4E5F6_1.bin
[!] Partial dump created
'''),
    'hf mfu restore': (1, '''[+] Wrote 16 pages
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 2
