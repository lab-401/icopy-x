# MIFARE Classic 1K, 4-byte UID (SAK 08)
# Negative test: RIGHT pressed during scan flow (should have no effect)
# Fixture data identical to scan_mf_classic_1k_4b
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf 14a reader': (0, '''[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 1
