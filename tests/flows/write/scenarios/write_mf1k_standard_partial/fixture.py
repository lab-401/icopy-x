# Write scenario: write_mf1k_standard_partial
SCENARIO_RESPONSES = {
    'hf 14a reader': (0, '''[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
'''),
    'hf mf cgetblk': (0, '''--block number: 0
[#] wupC1 error
[-] Can't set magic card block
[-] isOk:00
'''),
    'hf mf rdsc 0 ': (0, '''--sector no 0, key B - FF FF FF FF FF FF

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
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf fchk': (0, '''[usb] pm3 --> hf mf fchk 1
[+] No key specified, trying default keys
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
    'hf mf rdsc': (0, '''--sector no 0, key B - FF FF FF FF FF FF

isOk:01
  0 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
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
    'hf 14a raw': (0, '''[usb] pm3 --> hf 14a raw -p -a 43
[-] isOk:00
'''),
    'hf mf rdbl': (0, '''[usb] pm3 --> hf mf rdbl 63 A ffffffffffff
--block no 63, key A - FF FF FF FF FF FF
--data: FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
isOk:01
'''),
    # Sequential: first 10 writes succeed, then all fail → partial success
    # The .so tracks write_success_list; non-empty = "Write successful!"
    'hf mf wrbl': [
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[+] isOk:01\n'),
        (0, '[-] isOk:00\n'),  # 11th+ calls fail (stays on last entry)
    ],
}
DEFAULT_RETURN = 1
TAG_TYPE = 1
