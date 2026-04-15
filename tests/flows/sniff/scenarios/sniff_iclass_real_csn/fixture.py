# iClass Sniff — real CSN data
# PM3 commands: hf iclass sniff + hf list iclass
# Real trace with CSN exchange visible in SELECT/READCHECK sequence
SCENARIO_RESPONSES = {
    'hf iclass sniff': (1, '\n'),
    'hf list iclass': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 640 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] iClass - all times are in carrier periods (1/13.56MHz)

 Start |  End  | Src | Data                                       | CRC | Annotation
-------+-------+-----+--------------------------------------------+-----+-------------------
     0 |     0 | Rdr | 0a                                         |     | ACTALL
     0 |     0 | Rdr | 0a                                         |     | ACTALL
   720 |   720 | Tag | 0f                                         |     |
   720 |   720 | Rdr | 0c                                         |     | IDENTIFY
  1440 |  1440 | Tag | 0f                                         |     |
  1440 |  1440 | Rdr | 0c                                         |     | IDENTIFY
  4496 |  4496 | Tag | 08 24 8e 00 01 40 02 5c 52 de              | ok  | CSN
  4496 |  4496 | Rdr | 81 08 24 8e 00 01 40 02 5c                 |     | SELECT
  7552 |  7552 | Tag | 42 20 71 04 08 00 12 e0 5f 37              | ok  |
  7552 |  7552 | Rdr | 88 02                                      |     | READCHECK[Kd](2)
 10096 | 10096 | Tag | 50 52 4f 58 4a 43 4d 30                    | ok  |
 10096 | 10096 | Rdr | 0c 01 fa 22                                | ok  | READ(1)
 13152 | 13152 | Tag | ff ff ff fe 7f 1f 7f 2c bb b2              | ok  |
 13152 | 13152 | Rdr | 0c 05 de 64                                | ok  | READ(5)
 16208 | 16208 | Tag | ff ff ff ff ff ff ff ff ea f5              | ok  |
'''),
}
DEFAULT_RETURN = 1
