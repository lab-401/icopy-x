# BCC0 incorrect — UID error detection
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[!] BCC0 incorrect, expected 0x2C != 0xFF
'''),
}
DEFAULT_RETURN = -1
TAG_TYPE = -1
