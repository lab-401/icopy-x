# Jablotron — lf sea → "Valid Jablotron ID" → type 30
# Ground truth: trace_lf_scans_20260406.txt session 11
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
[+] Jablotron - Card: 7270a18, Raw: FFFF011999900079
[+] Printed: 1410-01-1999-9000

[+] Valid Jablotron ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
