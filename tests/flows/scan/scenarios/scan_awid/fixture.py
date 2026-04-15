# AWID — lf sea → "Valid AWID ID" → type 11
# Ground truth: trace_lf_scans_20260406.txt session 1
# Regex: the .so uses getContentFromRegexG to extract fields from the AWID line
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
[+] AWID - len: 222 -unknown- (28635) - Wiegand: 7ad377b79fa2dfb6, Raw: 01deb4ddede7e8b7edbdb7e1

[+] Valid AWID ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
