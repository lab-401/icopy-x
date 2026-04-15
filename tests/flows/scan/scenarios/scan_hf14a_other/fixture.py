# Unknown HF 14443-A tag — scan_hfsea→isMifare→scan_14a→no match→type 40
SCENARIO_RESPONSES = {
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] MIFARE card found
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: FF EE DD CC
[+] ATQA: 00 04
[+]  SAK: 28 [2]
[=] proprietary non iso14443-4 card found, RATS not supported
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 40
