# Write scenario: write_mf1k_gen1a_success
SCENARIO_RESPONSES = {
    'hf 14a reader': (0, '''[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
'''),
    'hf mf cgetblk': (0, '''[usb] pm3 --> hf mf cgetblk 0
[+] Block 0: 2CADC2729C4C4545000000000000000
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf csave': (0, '''[usb] pm3 --> hf mf csave 1 o /tmp/dump.bin

[+] saved 1024 bytes to binary file /tmp/dump.bin
'''),
    'hf mf cload': (0, '''[usb] pm3 --> hf mf cload b /tmp/dump.bin
[+] Card loaded 64 blocks from file
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
