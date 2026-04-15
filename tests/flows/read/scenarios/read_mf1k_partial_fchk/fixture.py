# MF Classic 1K: partial fchk (8/16 keyA), nested recovers rest
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

[+] found valid key: a0a1a2a3a4a5
[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 001 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 002 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 003 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 004 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 005 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 006 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 007 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 008 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 009 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 010 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 011 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 012 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 013 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 014 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 015 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] |-----|----------------|---|----------------|---|
'''),
    'hf mf rdsc': (0, '''--sector no 0, key B - FF FF FF FF FF FF

isOk:01
  0 | 2C AD C2 72 9C 4C 45 45 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  4 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  5 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  6 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  7 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  8 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  9 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  10 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  11 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  12 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  13 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  14 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  15 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
