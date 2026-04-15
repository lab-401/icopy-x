# Hitag — lf sea → "Valid Hitag" → type 38
# Ground truth: trace_lf_scans_20260406.txt session 14
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
[+]  UID: ffffffff

[+] Valid Hitag found!
'''),
}
DEFAULT_RETURN = 1
