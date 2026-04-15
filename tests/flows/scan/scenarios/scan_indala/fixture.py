# Indala — lf sea → "Valid Indala ID" → type 10
# Ground truth: trace_lf_scans_20260406.txt session 9
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
[+] Indala - len 1888, Raw: a0000000ef00000000000000c0e0f0e620000000ff00000000000000

[+] Valid Indala ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
