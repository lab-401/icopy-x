# Securakey — lf sea → "Valid Securakey ID" → type 14
# Ground truth: trace_lf_scans_20260406.txt session 18
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
[+] Securakey - len: 32 FC: 0x2AAA Card: 52428, Raw: 7FCC0002A955329860000000
[+] Wiegand: 55559998 parity (ok)

[=] How the FC translates to printed FC is unknown

[=] How the checksum is calculated is unknown
[=] Help the community identify this format further
[=]  by sharing your tag on the pm3 forum or with forum members


[+] Valid Securakey ID found!

Couldn't identify a chipset
'''),
}
DEFAULT_RETURN = 1
