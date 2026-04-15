# Erase MF1 — NTAG/non-MFC card, fchk finds 0 keys
# Source: trace_erase_flow_20260330.txt lines 678-687
# SAK 00 = NTAG 216, not Gen1a (wupC1 error), hf mfu info confirms NTAG,
# fchk 0 (Mini format, 5 sectors) finds 0/10 keys — erase impossible
SCENARIO_RESPONSES = {
    'hf 14a info': (1, '''
[+]  UID: 11 22 33 55 66 77 88
[+] ATQA: 00 44
[+]  SAK: 00 [2]
[+] MANUFACTURER:    Emosyn-EM Microelectronics USA
[+]     NTAG21x Modifiable
[+] TYPE: NTAG 216 888bytes (NT2H1611G0DU)
[+]    MIFARE Ultralight Compatible
[=] proprietary non iso14443-4 card found, RATS not supported
[+] Prng detection: weak
'''),
    'hf mf cgetblk': (1, '''--block number: 0
[#] wupC1 error
[!!] Can't read block. error=-1
'''),
    'hf mfu info': (1, '''
[=] --- Tag Information --------------------------
[=] -------------------------------------------------------------
[+]       TYPE: NTAG 216 888bytes (NT2H1611G0DU)
[+]        UID: 11 22 33 55 66 77 88
[+]     UID[0]: 11, Emosyn-EM Microelectronics USA
[+]       BCC0: 00 (ok)
[+]       BCC1: 00 (ok)
[+]   Internal: 48 (default)
[+]       Lock: 00 00
[+] OneTimePad: 00 00 00 00
'''),
    'hf mf fchk': (1, '''[+] Loaded 108 keys from /tmp/.keys/mf_tmp_keys
[=] Running strategy 1
[=] Chunk: 1.8s | found 0/10 keys (85)
[=] Chunk: 0.6s | found 0/10 keys (23)
[=] Running strategy 2
....[=] Chunk: 8.4s | found 0/10 keys (108)
[=] time in checkkeys (fast) 10.8s


[+] found keys:
[+] |-----|----------------|---|----------------|---|
[+] | Sec | key A          |res| key B          |res|
[+] |-----|----------------|---|----------------|---|
[+] | 000 | -------------- | 0 | -------------- | 0 |
[+] | 001 | -------------- | 0 | -------------- | 0 |
[+] | 002 | -------------- | 0 | -------------- | 0 |
[+] | 003 | -------------- | 0 | -------------- | 0 |
[+] | 004 | -------------- | 0 | -------------- | 0 |
[+] |-----|----------------|---|----------------|---|
[+] ( 0:Failed / 1:Success)
'''),
}
DEFAULT_RETURN = 1
