# Diagnosis — User diagnosis: ALL 5 PM3 tests fail
# HF antenna: 0 mV, LF antenna: 0 mV, HF reader: no card,
# LF reader: no tag / noise, Flash: load error
SCENARIO_RESPONSES = {
    'hf tune': (1, '''
[=] Measuring HF antenna, click pm3 button or press Enter to exit
[|] 0 mV / 0 V[/] 0 mV / 0 V[-] 0 mV / 0 V
[=] Done.
'''),
    'lf tune': (1, '''
[=] Measuring LF antenna at 125.00 kHz, click pm3 button or press Enter to exit
[-] 0 mV /  0 V[\\] 0 mV /  0 V[|] 0 mV /  0 V
[=] Done.
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
[=] Signal looks like noise. Maybe not an LF tag?
'''),
    'mem spiffs load': (1, '''
[!!] Could not find file test_pm3_mem.nikola
'''),
    'mem spiffs wipe': (1, '''
[=] Wiping all files from SPIFFS FileSystem
[=] Done!
'''),
}
DEFAULT_RETURN = 1
