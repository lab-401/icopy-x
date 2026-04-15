# MIFARE DESFire — scan_hfsea→isMifare→scan_14a→DESFire
SCENARIO_RESPONSES = {
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] MIFARE DESFire card found
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 C1 D2 E3 F4 A5 B6
[+] ATQA: 03 44
[+]  SAK: 20 [2]
[+] Possible types:
[+]    MIFARE DESFire MF3ICD40
[+] ATS: 06 75 77 81 02 80
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 39
