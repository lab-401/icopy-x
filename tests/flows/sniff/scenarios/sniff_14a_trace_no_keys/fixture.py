# 14A Sniff — trace captured but no keys/UID extractable
# Ground truth: real device trace_sniff_flow_20260403.txt format
# hf 14a sniff returns empty (real device: ret=1 \n)
# hf list mf returns trace table with WUPA/ANTICOLL but NO key annotations
# Parsers: parserKeyForM1 finds no "key" lines, parserUidForData finds no SELECT_UID
SCENARIO_RESPONSES = {
    'hf 14a sniff': (1, '\n'),
    'hf list mf': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 2048 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] ISO14443A - all times are in carrier periods (1/13.56MHz)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
          0 |        992 | Rdr |52(7)                                                                    |     | WUPA
       2228 |       4596 | Tag |04  00                                                                   |     |
       7232 |      16544 | Rdr |93  20                                                                   |     | ANTICOLL
      17956 |      36164 | Tag |88  04  aa  55  c3                                                       |     |
      39232 |      67264 | Rdr |93  70  88  04  aa  55  c3  96  aa                                       |  ok | SELECT_UID
      68516 |      77540 | Tag |24  d8  36                                                               |     |
      80000 |      81000 | Rdr |52(7)                                                                    |     | WUPA
     100000 |     101000 | Rdr |52(7)                                                                    |     | WUPA
'''),
}
DEFAULT_RETURN = 1
