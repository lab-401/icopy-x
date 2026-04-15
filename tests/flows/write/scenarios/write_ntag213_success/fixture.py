# Write scenario: write_ntag213_success
SCENARIO_RESPONSES = {
    'hf mfu restore': (0, '''[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[=] Restoring to card...
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 B1 C2 D3 E4 F5 A6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    NTAG213
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    'hf mfu info': (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: NTAG 213 144bytes (NT2H1311G0DU)
[=]        UID: 04 B1 C2 D3 E4 F5 A6
[=]    UID LEN: 7
'''),
    'hf mfu dump': (0, '''[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] NTAG dump completed
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 5
