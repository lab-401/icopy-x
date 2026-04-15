# MF Classic 4K: partial fchk, nested recovers rest
SCENARIO_RESPONSES = {
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: AA BB CC DD
[+] ATQA: 00 02
[+]  SAK: 18 [2]
[+] Possible types:
[+]    MIFARE Classic 4K / Classic 4K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
    'hf mf fchk': (0, '''[usb] pm3 --> hf mf fchk 4
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
[+] | 008 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 009 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 010 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 011 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 012 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 013 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 014 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 015 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 016 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 017 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 018 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 019 | ffffffffffff   | 1 | ------------   | 0 |
[+] | 020 | ------------   | 0 | ------------   | 0 |
[+] | 021 | ------------   | 0 | ------------   | 0 |
[+] | 022 | ------------   | 0 | ------------   | 0 |
[+] | 023 | ------------   | 0 | ------------   | 0 |
[+] | 024 | ------------   | 0 | ------------   | 0 |
[+] | 025 | ------------   | 0 | ------------   | 0 |
[+] | 026 | ------------   | 0 | ------------   | 0 |
[+] | 027 | ------------   | 0 | ------------   | 0 |
[+] | 028 | ------------   | 0 | ------------   | 0 |
[+] | 029 | ------------   | 0 | ------------   | 0 |
[+] | 030 | ------------   | 0 | ------------   | 0 |
[+] | 031 | ------------   | 0 | ------------   | 0 |
[+] | 032 | ------------   | 0 | ------------   | 0 |
[+] | 033 | ------------   | 0 | ------------   | 0 |
[+] | 034 | ------------   | 0 | ------------   | 0 |
[+] | 035 | ------------   | 0 | ------------   | 0 |
[+] | 036 | ------------   | 0 | ------------   | 0 |
[+] | 037 | ------------   | 0 | ------------   | 0 |
[+] | 038 | ------------   | 0 | ------------   | 0 |
[+] | 039 | ------------   | 0 | ------------   | 0 |
[+] |-----|----------------|---|----------------|---|
'''),
    'hf mf nested': (0, '''[usb] pm3 --> hf mf nested 2 0 A ffffffffffff

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
[+] | 016 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 017 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 018 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 019 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 020 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 021 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 022 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 023 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 024 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 025 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 026 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 027 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 028 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 029 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 030 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 031 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 032 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 033 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 034 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 035 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 036 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 037 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 038 | ffffffffffff   | 1 | ffffffffffff   | 1 |
[+] | 039 | ffffffffffff   | 1 | ffffffffffff   | 1 |
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
TAG_TYPE = 0
