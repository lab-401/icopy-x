# Paradox — lf sea → "Valid Paradox ID" → type 35
# Ground truth: trace_lf_scans_20260406.txt session 16
# Note: Paradox line uses [=] not [+] prefix
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
[=] Paradox - ID: 00c2cc000 FC: 236 Card: 49152, Checksum: 00, Raw: 0f56999a9a5a555555555555

[+] Valid Paradox ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
