# Write scenario: write_ultralight_c_success
SCENARIO_RESPONSES = {
    'hf mfu restore': (0, '''[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[=] Restoring to card...
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    'hf mfu info': (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight C (MF0ULC)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
'''),
    'hf mfu dump': (0, '''[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] MFU dump completed
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 3
