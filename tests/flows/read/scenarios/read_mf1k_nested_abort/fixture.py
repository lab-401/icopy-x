# MF Classic 1K: nested → user presses button → abort
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf 14a reader': (0, '''[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
    'hf mf fchk': (0, '''[usb] pm3 --> hf mf fchk 1
[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 001 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 002 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 003 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 004 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 005 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 006 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 007 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 008 | ------------   | 0 | ------------   | 0 |
[+] | 009 | ------------   | 0 | ------------   | 0 |
[+] | 010 | ------------   | 0 | ------------   | 0 |
[+] | 011 | ------------   | 0 | ------------   | 0 |
[+] | 012 | ------------   | 0 | ------------   | 0 |
[+] | 013 | ------------   | 0 | ------------   | 0 |
[+] | 014 | ------------   | 0 | ------------   | 0 |
[+] | 015 | ------------   | 0 | ------------   | 0 |
[+] |-----|----------------|---|----------------|---|
'''),
    'hf mf nested': (0, '''[usb] pm3 --> hf mf nested 1 0 A ffffffffffff

[-] button pressed. Aborted.
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
