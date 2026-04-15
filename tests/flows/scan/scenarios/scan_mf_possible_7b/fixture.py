# MIFARE POSSIBLE 7B (type 44)
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic
[+]    MIFARE Plus 2K / Plus EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Static nonce: yes
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 44
