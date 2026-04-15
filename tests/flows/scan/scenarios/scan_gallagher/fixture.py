# GALLAGHER — lf sea → "Valid GALLAGHER ID" → type 29
# Ground truth: trace_lf_scans_20260406.txt session 5
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=] 
[=] Checking for known tags...
[=] 
0 -9 -18 -27 -36 -45 -54 -63 -
[=]  Before:  7F D5 8C 3B 8D 8D 8D C3 
[=]  After :  0A CD 60 65 3F 3F 3F 56 
[+] GALLAGHER - Region: 2 FC: 64725 CN: 719622 Issue Level: 6
[+]    Printed: B64725
[+]    Raw: 7FEAA30768D46A35868C35CF
[+]    CRC: 8C - F8 (fail)

[+] Valid GALLAGHER ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
