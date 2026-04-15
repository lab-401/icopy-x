# Pyramid — lf sea → "Valid Pyramid ID" → type 16
# Ground truth: trace_lf_scans_20260406.txt session 17
# Regex: FC:*\s+([xX0-9a-fA-F]+) extracts FC
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
[+] Pyramid - len: 26, FC: 240 Card: 61456 - Wiegand: 1e1e021, Raw: 00010101010101010101015e0e804346

[+] Valid Pyramid ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
