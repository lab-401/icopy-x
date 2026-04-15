# MF Classic 4K Gen1a: csave 4 dumps all 256 blocks (4096 bytes)
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: E9 78 4E 21
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[+] Magic capabilities : Gen 1a
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (0, '''[usb] pm3 --> hf mf cgetblk 0

data: E9 78 4E 21 FE 98 02 00 62 63 64 65 66 67 68 69
'''),
    'hf mf csave': (0, '''[usb] pm3 --> hf mf csave 4 o /tmp/dump.bin

[+] Saving magic MIFARE 4K
[+] saved 4096 bytes to binary file /tmp/dump.bin
[+] saved 256 blocks to text file /tmp/dump.eml
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 0
