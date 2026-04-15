# Viking — lf sea → "Valid Viking ID" → type 15
# Ground truth: trace_lf_scans_20260406.txt session 19
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
[+] Viking - Card 99BBB000, Raw: F2000099BBB000C8

[+] Valid Viking ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
