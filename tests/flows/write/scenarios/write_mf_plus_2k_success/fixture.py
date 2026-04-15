# Write scenario: write_mf_plus_2k_success
# MIFARE Plus 2K (SAK 08, SL1 mode) — PM3 reports both Classic and Plus possibilities
# Source: real device trace full_read_write_trace_20260327.txt line 43 + autocopy fixtures
SCENARIO_RESPONSES = {
    'hf 14a reader': (0, '''[usb] pm3 --> hf 14a reader

[+]  UID: 2C AD C2 72
'''),
    'hf mf cgetblk': (0, '''[-] Can't set magic card block
[-] isOk:00
'''),
    'hf 14a info': (0, '''[usb] pm3 --> hf 14a info

[+]  UID: 2C AD C2 72
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K / Classic 1K CL2
[+]    MIFARE Plus 2K / Plus EV1 2K
[+]    MIFARE Plus CL2 2K / Plus CL2 EV1 2K
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf fchk': (0, '''[usb] pm3 --> hf mf fchk 2
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
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
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
    'hf 14a raw': (0, '''[usb] pm3 --> hf 14a raw -p -a 43
[-] isOk:00
'''),
    'hf mf rdbl': (0, '''[usb] pm3 --> hf mf rdbl 127 A ffffffffffff
--block no 127, key A - FF FF FF FF FF FF
--data: FF FF FF FF FF FF FF 07 80 69 FF FF FF FF FF FF
isOk:01
'''),
    'hf mf wrbl': (0, '''[usb] pm3 --> hf mf wrbl 1 A ffffffffffff 00000000000000000000000000000000
[+] isOk:01
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 26
