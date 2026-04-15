# 14B Sniff — real REQB data
# PM3 commands: hf 14b sniff + hf list 14b
# Real trace with REQB/ATTRIB/WUPB exchange
SCENARIO_RESPONSES = {
    'hf 14b sniff': (1, '\n'),
    'hf list 14b': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 876 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] ISO14443B - all times are in carrier periods (1/13.56MHz)

 Start | End | Src | Data                                                   | CRC | Annotation
-------+-----+-----+--------------------------------------------------------+-----+-----------
     0 |   0 | Rdr | 05 00 00 71 ff                                         | ok  | REQB
     0 |   0 | Tag | 50 82 0d e1 74 20 38 19 22 00 21 85 5e d7              | ok  |
     0 |   0 | Rdr | 05 00 00 71 ff                                         | ok  | REQB
     0 |   0 | Tag | 50 82 0d e1 74 20 38 19 22 00 21 85 5e d7              | ok  |
     0 |   0 | Rdr | 1d 82 0d e1 74 00 08 01 05 0f 9b                       | ok  | ATTRIB
     0 |   0 | Rdr | 05 00 08 39 73                                         | ok  | WUPB
     0 |   0 | Tag | 50 11 aa 33 bb 20 38 19 22 00 21 85 7e 59              | ok  |
     0 |   0 | Rdr | 05 00 08 39 73                                         | ok  | WUPB
     0 |   0 | Tag | 50 11 aa 33 bb 20 38 19 22 00 21 85 7e 59              | ok  |
'''),
}
DEFAULT_RETURN = 1
