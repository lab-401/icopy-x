# Auto-Copy scenario: autocopy_mf1k_fchk_timeout
# MF Classic 1K: hf mf fchk returns -1 (timeout), toast: "Time out"
# Ground truth: V1090_AUTOCOPY_FLOW_COMPLETE.md Section 3 (keys_check_failed) + hfmfkeys_strings.txt
#
# PM3 command sequence:
#   hf 14a info
#   hf mf cgetblk 0 (not Gen1a)
#   hf mf fchk (returns -1 = timeout)

SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: B7 78 5E 50
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+]    MIFARE Plus 2K / Plus EV1 2K
[+]    MIFARE Plus CL2 2K / Plus CL2 EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mf fchk': (-1, '''[!] command execution time out
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
