# HID Prox — lf sea → "Valid HID Prox ID" → type 9
# Ground truth: trace_lf_scans_20260406.txt session 7
# Regex: HID Prox - ([xX0-9a-fA-F]+)
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
[+] HID Prox - 2006222332 (4505) - len: 26 bit - OEM: 000 FC: 17 Card: 4505

[+] Valid HID Prox ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
