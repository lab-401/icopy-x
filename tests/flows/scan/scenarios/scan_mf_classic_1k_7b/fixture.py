# MIFARE Classic 1K, 7-byte UID (SAK 08)
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 42
