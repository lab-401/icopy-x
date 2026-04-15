# iCLASS: key found but dump fails → "Read Failed!"
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
'''),
    'lf sea': (0, '''[usb] pm3 --> lf search
[!] No data found!
[-] No known 125/134 kHz tags found!
'''),
    'hf sea': (0, '''[usb] pm3 --> hf search

[+] Valid iCLASS tag / PicoPass tag found
'''),
    'hf iclass rdbl b 01 k AFA785A7DAB33378': (0, '''[usb] pm3 --> hf iclass rdbl b 01 k AFA785A7DAB33378

Block 01 : 12 FF FF FF 7F 1F FF 3C
'''),
    'hf iclass rdbl': (0, '''[usb] pm3 --> hf iclass rdbl

[-] Error reading block
'''),
    'hf iclass info': (0, '''[usb] pm3 --> hf iclass info

[=] CSN: 00 0B 0F FF F7 FF 12 E0
[=] CC:  D5 F8 FF FF FF FF FF FE
'''),
    'hf iclass chk': (0, '''[usb] pm3 --> hf iclass chk

[+] Found valid key ae a6 84 a6 da b2 12 32
'''),
    'hf iclass dump': (-1, ''''''),
}
DEFAULT_RETURN = -1
TAG_TYPE = 17
