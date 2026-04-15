# Write scenario: write_ntag216_success
SCENARIO_RESPONSES = {
    'hf mfu restore': (0, '''[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[=] Restoring to card...
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG216
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    'hf mfu info': (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: NTAG 216 888bytes (NT2H1611G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
'''),
    'hf mfu dump': (0, '''[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] NTAG dump completed
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 7
