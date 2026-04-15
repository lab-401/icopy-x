# Diagnosis — User diagnosis: ALL 5 PM3 tests pass
# HF antenna: high mV, LF antenna: high mV, HF reader: tag found,
# LF reader: tag found, Flash: load+wipe success
SCENARIO_RESPONSES = {
    'hf tune': (1, '''
[=] Measuring HF antenna, click pm3 button or press Enter to exit
[|] 37662 mV / 37 V[/] 37636 mV / 37 V[-] 37623 mV / 37 V
[=] Done.
'''),
    'lf tune': (1, '''
[=] Measuring LF antenna at 125.00 kHz, click pm3 button or press Enter to exit
[-] 43063 mV /  43 V[\\] 43097 mV /  43 V[|] 43089 mV /  43 V
[=] Done.
'''),
    'hf 14a reader': (1, '''
[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K
'''),
    'lf sea': (1, '''
[=] NOTE: some demods output possible binary
[=] Checking for known tags...
[+] EM410x pattern found
EM TAG ID      : 0F0368568B
[+] Valid EM410x ID found!
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
