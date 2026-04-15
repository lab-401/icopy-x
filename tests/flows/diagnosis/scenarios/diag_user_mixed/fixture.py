# Diagnosis — User diagnosis: mixed results (matches real device trace)
# Source: Real device trace Session 2
# HF antenna: 37662 mV PASS, LF antenna: 43063 mV PASS,
# HF reader: card select failed FAIL, LF reader: noise FAIL,
# Flash: load+wipe success PASS
SCENARIO_RESPONSES = {
    'hf tune': (1, '''
[=] Measuring HF antenna, click pm3 button or press Enter to exit
[|] 37662 mV / 37 V[/] 37636 mV / 37 V[-] 37623 mV / 37 V[\\] 37632 mV / 37 V[|] 37632 mV / 37 V[/] 37619 mV / 37 V
[=] Done.
'''),
    'lf tune': (1, '''
[=] Measuring LF antenna at 125.00 kHz, click pm3 button or press Enter to exit
[-] 43063 mV /  43 V[\\] 43097 mV /  43 V[|] 43089 mV /  43 V[/] 43063 mV /  43 V[-] 43080 mV /  43 V[\\] 43097 mV /  43 V[=] Done.
'''),
    'hf 14a reader': (1, '''
[!] iso14443a card select failed
'''),
    'lf sea': (1, '''

[=] NOTE: some demods output possible binary
[=] if it finds something that looks like a tag
[=] False Positives ARE possible
[=]
[=] Checking for known tags...
[=]
[|]Searching for MOTOROLA tag...
[-] No data found!
[=] Signal looks like noise. Maybe not an LF tag?

'''),
    'mem spiffs load': (1, '''
[+] loaded 2 bytes from binary file /tmp/test_pm3_mem.nikola
[+] Wrote 2 bytes to file test_pm3_mem.nikola
'''),
    'mem spiffs wipe': (1, '''
[=] Wiping all files from SPIFFS FileSystem
[#] removed test_pm3_mem.nikola
[=] Done!
'''),
}
DEFAULT_RETURN = 1
