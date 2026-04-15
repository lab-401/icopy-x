# IO Prox — lf sea → "Valid IO Prox ID" → type 12
# Ground truth: trace_lf_scans_20260406.txt session 10
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
[+] IO Prox - XSF(00)00:00273, Raw: 0078402010188ff7 (ok)

[+] Valid IO Prox ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
