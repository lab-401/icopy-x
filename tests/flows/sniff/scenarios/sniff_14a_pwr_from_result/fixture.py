# 14A Sniff — PWR from result state back to type list
# PM3 commands (verified by QEMU .so behavior):
#   1. hf 14a sniff  — start sniff (fired by M1=Start)
#   2. hf list mf    — parse trace (fired by M2=Finish → showResult())
# Note: .so issues "hf list mf" NOT "hf 14a list" for 14A sniff type
SCENARIO_RESPONSES = {
    'hf 14a sniff': (0, '''[usb] pm3 --> hf 14a sniff
#db# Starting to sniff
trace len = 1234
'''),
    'hf list mf': (0, '''[usb] pm3 --> hf list mf

Recorded activity (trace len = 1234 bytes)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
          0 |        992 | Rdr |26                                                                       |     | REQA
       2228 |       4596 | Tag |04  00                                                                   |     |
       7232 |      16544 | Rdr |93  20                                                                   |     | ANTICOLL
      17956 |      36164 | Tag |2c  ad  c2  72  11                                                       |     |
      39232 |      67264 | Rdr |93  70  2c  ad  c2  72  11  01  e5                                       |  ok | SELECT_UID
      68516 |      77540 | Tag |08  b6  dd                                                               |     |
      80480 |     110848 | Rdr |60  03  44  92  f8  5a                                                   |  ok | AUTH-A(3)
     114944 |     119520 | Tag |ab  cd  12  34                                                           |     |
     122880 |     144640 | Rdr |a1  b2  c3  d4  e5  f6  a7  b8                                           |     |
     145920 |     155200 | Tag |11  22  33  44                                                           |     |
            |            |  *  |                                                key FFFFFFFFFFFF prng WEAK |     |
     160000 |     187520 | Rdr |55  66  77  88  99  aa  bb  cc  dd  ee  ff  00  11  22  33  44  55  66    |  ok | READBLOCK(3)
     188800 |     210560 | Tag |00  00  00  00  00  00  ff  07  80  69  ff  ff  ff  ff  ff  ff  33  77    |  ok |
'''),
}
DEFAULT_RETURN = 1
