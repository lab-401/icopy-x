# MF Classic 1K Gen1a: cgetblk succeeds → csave dumps all 64 blocks
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 11 22 33 44
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf 14a reader': (0, '''[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
'''),
    'hf mf cgetblk': (0, '''[usb] pm3 --> hf mf cgetblk 0

[+] Block 0: 11 22 33 44 9C 4C 45 45 00 00 00 00 00 00 00 00
[+] isOk:01
'''),
    'hf mf csave': (0, '''[usb] pm3 --> hf mf csave 1 o /tmp/dump.bin

[+] saved 1024 bytes to binary file /tmp/dump.bin
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
