# Write scenario: write_ultralight_verify_fail
# Write succeeds but verify detects wrong tag (different UID on re-scan).
# Sequential responses: read phase gets valid UL, verify phase gets different UID.
SCENARIO_RESPONSES = {
    'hf mfu restore': (0, '''[usb] pm3 --> hf mfu restore s e f /tmp/dump.bin

[=] Restoring to card...
'''),
    # Sequential: [0]=read scan, [1]=post-write auto-check, [2+]=verify — different UID
    'hf 14a info': [
        (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
        (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 A1 B2 C3 D4 E5 F6
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
        (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 04 FF FF FF FF FF FF
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] Possible types:
[+]    MIFARE Ultralight
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
    ],
    # Sequential: first calls return correct UID, verify calls return different UID
    'hf mfu info': [
        (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight (MF0ICU1)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
'''),
        (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight (MF0ICU1)
[=]        UID: 04 A1 B2 C3 D4 E5 F6
[=]    UID LEN: 7
'''),
        (0, '''[usb] pm3 --> hf mfu info

[=] --- Tag Information ---------
[=]       TYPE: Ultralight (MF0ICU1)
[=]        UID: 04 FF FF FF FF FF FF
[=]    UID LEN: 7
'''),
    ],
    'hf mfu dump': (0, '''[usb] pm3 --> hf mfu dump f /tmp/dump.bin

[=] MFU dump completed
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 2
