# MIFARE Mini (SAK 09)
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: DE AD BE EF
[+] ATQA: 00 04
[+]  SAK: 09 [2]
[+] Possible types:
[+]    MIFARE Mini
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 25
