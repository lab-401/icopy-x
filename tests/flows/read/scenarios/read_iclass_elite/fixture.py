# iCLASS Elite: elite key found via 'e' flag, 19 blocks dumped
# Ground truth: trace_iclass_elite_read_20260401.txt
# Flow: hf sea → rdbl key attempts (fail) → rdbl with 'e' flag (elite, SUCCESS)
#       → hf iclass info → hf iclass dump → File saved
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
    # Elite rdbl with 'e' flag succeeds — MUST match before generic 'hf iclass rdbl'
    # Ground truth: trace line "hf iclass rdbl b 01 k 2020666666668888 e"
    # Response: "[+] Using elite algo" + block 01 data
    'hf iclass rdbl b 01 k 2020666666668888 e': (0, '''[+] Using elite algo

[+]  block 01 : 12 FF FF FF 7F 1F FF 3C

'''),
    # All other rdbl attempts (legacy keys, without 'e') return empty
    # Ground truth: trace shows ret=1 with empty response for non-elite keys
    'hf iclass rdbl': (0, '''
'''),
    'hf iclass info': (0, '''[usb] pm3 --> hf iclass info

[=] --- Tag Information --------------------------
[=] -------------------------------------------------------------
[+]     CSN: 4A 67 8E 15 FE FF 12 E0   (uid)
[+]  Config: 12 FF FF FF 7F 1F FF 3C   (Card configuration)
[+] E-purse: FF FF FF FF F9 FF FF FF   (Card challenge, CC)
[+]      Kd: 00 00 00 00 00 00 00 00   (Debit key, hidden)
[+]      Kc: 00 00 00 00 00 00 00 00   (Credit key, hidden)
'''),
    # Dump with elite flag succeeds
    # Ground truth: trace line "hf iclass dump k 2020666666668888 f ... e"
    'hf iclass dump': (0, '''[usb] pm3 --> hf iclass dump k 2020666666668888 e

[+] Using elite algo
[=] Card has atleast 2 application areas. AA1 limit 18 (0x12) AA2 limit 31 (0x1F)

[+] saving dump file - 19 blocks read
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 18
