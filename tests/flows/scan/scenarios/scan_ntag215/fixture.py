# NTAG215 (504 bytes)
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG215
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    'hf mfu info': (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: NTAG 215 504bytes (NT2H1511G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 6
