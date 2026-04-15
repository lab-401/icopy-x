# 14A Sniff — real key found trace (UID 8d 2d 6f 67, key FFFFFFFFFFFF, prng WEAK)
# Real trace data from user
# PM3 commands: hf 14a sniff + hf list mf
# trace_len=2298, key FFFFFFFFFFFF found, prng WEAK
SCENARIO_RESPONSES = {
    'hf 14a sniff': (1, '\n'),
    'hf list mf': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 2298 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] ISO14443A - all times are in carrier periods (1/13.56MHz)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
     142336 |     143328 | Rdr |52(7)                                                                    |     | WUPA
     144452 |     146820 | Tag |04  00                                                                   |     |
     149376 |     151840 | Rdr |93  20                                                                   |     | ANTICOLL
     152900 |     158788 | Tag |8d  2d  6f  67  a8                                                       |     |
     161408 |     171872 | Rdr |93  70  8d  2d  6f  67  a8  f4  65                                       | ok  | SELECT_UID
     172996 |     176516 | Tag |08  b6  dd                                                               |     |
     178688 |     183456 | Rdr |60  08  bd  f7                                                           | ok  | AUTH-A(8)
     185284 |     190020 | Tag |01  20  01  45                                                           |     |
     199296 |     208672 | Rdr |dd  47  17  32  9a  87  fc  ec                                           |     |
     209732 |     214404 | Tag |7f  54  ae  24                                                           |     |
     222848 |     227616 | Rdr |16  0c  09  26                                                           |     |
            |            |  *  |                                                key FFFFFFFFFFFF prng WEAK |     |
            |            |  *  |60  00  F5  7B                                                            | ok  | AUTH-A(0)
     229444 |     234180 | Tag |b5  36  13  e4                                                           |     |
'''),
}
DEFAULT_RETURN = 1
