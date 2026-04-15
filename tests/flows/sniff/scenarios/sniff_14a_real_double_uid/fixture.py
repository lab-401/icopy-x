# 14A Sniff — real double-length UID trace (cascade select)
# Real trace data from user
# PM3 commands: hf 14a sniff + hf list mf
# UID bytes 04 53 5d + 42 a7 49 80 (cascade), trace_len=2298
SCENARIO_RESPONSES = {
    'hf 14a sniff': (1, '\n'),
    'hf list mf': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 2298 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] ISO14443A - all times are in carrier periods (1/13.56MHz)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
  188213078 | 188215446 | Tag |44  00                                                                   |     |
  188224958 | 188235486 | Rdr |93  70  88  04  53  5d  82  17  d3                                       | ok  | SELECT_UID
  188236978 | 188240498 | Tag |04  da  17                                                               |     |
  188243234 | 188245698 | Rdr |95  20                                                                   |     | ANTICOLL-2
  188247382 | 188253270 | Tag |42  a7  49  80  2c                                                       |     |
  188257314 | 188267842 | Rdr |95  70  42  a7  49  80  2c  2d  5e                                       | ok  | ANTICOLL-2
  188269398 | 188272918 | Tag |08  b6  dd                                                               |     |
  188503146 | 188507914 | Rdr |61  00  2d  62                                                           | ok  | AUTH-B(0)
  188512414 | 188517150 | Tag |01  02  03  04                                                           |     |
  188521244 | 188530620 | Rdr |95  84  ec  75                                                           |!crc | ANTICOLL-2
  188539152 | 188543824 | Tag |e7  86  42  2d                                                           |     |
  188614336 | 188619104 | Rdr |30  de  37  97                                                           |!crc | READBLOCK(222)
  188622644 | 188623284 | Tag |07                                                                       |     |
'''),
}
DEFAULT_RETURN = 1
