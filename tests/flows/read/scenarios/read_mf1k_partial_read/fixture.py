# MF Classic 1K: all keys found, but card partially readable (sectors 8-15 fail during rdsc)
# This tests the "partial data saved" (read_ok_2) path where some sectors read OK but others fail.
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
[+] ( 0:Failed / 1:Success)
'''),
    # Sectors 0-7 read OK, sectors 8-15 fail (card partially readable)
    # Sequential responses: first 8 succeed, then fail.
    # After the last entry, subsequent calls stay at the last entry,
    # so the 9th+ rdsc calls (sectors 8+) all return the Auth error.
    'hf mf rdsc': [
        (0, '''--sector no 0, key B - FF FF FF FF FF FF

isOk:01
  0 | 2C AD C2 72 9C 4C 45 45 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 1, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 2, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 3, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 4, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 5, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 6, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        (0, '''--sector no 7, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  1 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  2 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
  3 | FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
'''),
        # Sectors 8-15: Auth error (card partially readable)
        # Return code 0 (PM3 completed, not a transport error) with isOk:00 content.
        # The .so checks isOk to detect per-sector failure and skips.
        # Return -1 would abort the entire read.
        (0, '''--sector no 8, key B - FF FF FF FF FF FF

isOk:00
[-] Authentication error
'''),
    ],
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
