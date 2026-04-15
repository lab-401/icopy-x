# iCLASS Legacy tag
# Ground truth: trace_iclass_scan_20260331.txt lines 4-22 (scan 1, type=17)
# Flow: hf 14a info (empty) -> lf sea (nothing) -> hf sea (truncated) ->
#       hf iclass rdbl b 01 k AFA785A7DAB33378 (fail x2) ->
#       hf iclass rdbl b 01 k 2020666666668888 (success, block data) ->
#       hf iclass info (CSN + Config + E-purse)
SCENARIO_RESPONSES = {
    # Line 7: ret=1 \n
    'hf 14a info': (1, '\n'),
    # Line 9: ret=1, no LF tag
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[|]Searching for MOTOROLA tag...
[-] No data found!
[=] Signal looks like noise. Maybe not an LF tag?

'''),
    # Line 11: ret=1, hf search — truncated at 300 chars in trace but full response
    # contains "Valid iCLASS tag" which hfsearch.so detects via hasKeyword.
    # Ground truth: hfsearch_strings.txt: "Valid iCLASS tag"
    # Ground truth: cmdhf.c line 136: "Valid iCLASS tag / PicoPass tag found"
    'hf sea': (1, '''
[-] Searching for ThinFilm tag...
[-] Searching for LTO-CM tag...
[-] Searching for ISO14443-A tag...
[+] Valid iCLASS tag / PicoPass tag found

    CSN: 75 D0 E0 13 FE FF 12 E0
 Config: 12 FF FF FF 7F 1F FF 3C
'''),
    # Lines 12-17: key attempts fail (ret=1, empty response)
    # Line 18: success with key 2020666666668888
    'hf iclass rdbl': (1, '\n[+]  block 01 : 12 FF FF FF 7F 1F FF 3C \n\n'),
    # Line 19-20: hf iclass info returns CSN + Config
    'hf iclass info': (1, '''
[=] --- Tag Information --------------------------
[=] -------------------------------------------------------------
[+]     CSN: 75 D0 E0 13 FE FF 12 E0   (uid)
[+]  Config: 12 FF FF FF 7F 1F FF 3C   (Card configuration)
[+] E-purse: FA FF FF FF FF FF FF FF   (Card challenge, CC)
[+]      Kd: 00 00 00 00 00 00 00 00
[+]      Kc: 00 00 00 00 00 00 00 00
[+]    AA1:
[+]         block  6: 03 03 03 03 00 03 E0 17
[+]         block  7: 01 01 01 01 01 01 01 01
[+]         block  8: 00 01 02 03 04 05 06 07
[+]         block  9: 08 09 0A 0B 0C 0D 0E 0F
[+]         block 10: 10 11 12 13 14 15 16 17
[+]         block 11: 18 19 1A 1B 1C 1D 1E 1F
[+]         block 12: FF FF FF FF FF FF FF FF
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 17
