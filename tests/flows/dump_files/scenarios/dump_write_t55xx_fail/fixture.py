# Write T55xx raw dump via write_lf_dump — fail path (restore command fails).
# Ground truth: write_t55xx_restore_fail pattern from write flow tests
# The lf t55xx restore command returns -1 → "Write failed!"
SCENARIO_RESPONSES = {
    'lf t55xx wipe': (1, '\n\n[=] Begin wiping T55x7 tag\n\n[=] Default configation block 000880E0\n[=] Writing page 0  block: 00  data: 0x000880E0 pwd: 0x20206666\n[=] Writing page 0  block: 01  data: 0x00000000 \n[=] Writing page 0  block: 02  data: 0x00000000 \n[=] Writing page 0  block: 03  data: 0x00000000 \n[=] Writing page 0  block: 04  data: 0x00000000 \n[=] Writing page 0  block: 05  data: 0x00000000 \n[=] Writing page 0  block: 06  data: 0x00000000 \n[=] Writing page 0  block: 07  data: 0x00000000 \n'),
    'lf t55xx detect': [
        # 1st: post-wipe — ASK/RF32, Block0=000880E0
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 2 - RF/32\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x000880E0\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
        # 2nd: second detect before restore — same as 1st
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 2 - RF/32\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x000880E0\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
        # 3rd: post-restore verify — ASK/RF64, Block0=00148040
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 5 - RF/64\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x00148040\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
        # 4th+: extra detect calls (stay at last entry)
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 5 - RF/64\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x00148040\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
        # 5th: extra (stays at last)
        (1, '\n[=]      Chip Type      : T55x7\n[=]      Modulation     : ASK\n[=]      Bit Rate       : 5 - RF/64\n[=]      Inverted       : No\n[=]      Offset         : 33\n[=]      Seq. Term.     : Yes\n[=]      Block0         : 0x00148040\n[=]      Downlink Mode  : default/fixed bit length\n[=]      Password Set   : No\n\n'),
    ],
    'lf t55xx restore': (-1, ''),
    # Page 0 block reads — block 0 returns config, blocks 1-7 return 00000000
    'lf t55xx read b 0 1': (1, '\n[+] Reading Page 1:\n[+] blk | hex data | binary                           | ascii\n[+] ----+----------+----------------------------------+-------\n[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@\n'),
    'lf t55xx read b 1 1': (1, '\n[+] Reading Page 1:\n[+] blk | hex data | binary                           | ascii\n[+] ----+----------+----------------------------------+-------\n[+]  01 | E0150A0C | 11100000000101010000101000001100 | ...\n'),
    'lf t55xx read b 2 1': (1, '\n[+] Reading Page 1:\n[+] blk | hex data | binary                           | ascii\n[+] ----+----------+----------------------------------+-------\n[+]  02 | 9C43AF65 | 10011100010000111010111101100101 | Ce\n'),
    'lf t55xx read b 3 1': (1, '\n[+] Reading Page 1:\n[+] blk | hex data | binary                           | ascii\n[+] ----+----------+----------------------------------+-------\n[+]  03 | 00000000 | 00000000000000000000000000000000 | ....\n'),
    'lf t55xx read b 0': (1, '\n[+] Reading Page 0:\n[+] blk | hex data | binary                           | ascii\n[+] ----+----------+----------------------------------+-------\n[+]  00 | 00148040 | 00000000000101001000000001000000 | ..@\n'),
    'lf t55xx read b': (1, '\n[+] Reading Page 0:\n[+] blk | hex data | binary                           | ascii\n[+] ----+----------+----------------------------------+-------\n[+]  01 | 00000000 | 00000000000000000000000000000000 | ....\n'),
}
DEFAULT_RETURN = 1
