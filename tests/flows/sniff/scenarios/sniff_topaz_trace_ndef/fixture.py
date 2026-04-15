# Topaz Sniff — NDEF tag data captured
# Ground truth: PM3 hf list topaz output format (Topaz/Jewel protocol)
# No real device trace available — synthetic fixture matching PM3 output format
SCENARIO_RESPONSES = {
    'hf topaz sniff': (1, '''
#db# Starting Topaz sniff
trace len = 320
'''),
    'hf list topaz': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 320 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] Topaz - all times are in carrier periods (1/13.56MHz)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
          0 |        992 | Rdr |26                                                                       |     | REQA
       2228 |       4596 | Tag |0c  00                                                                   |     | ATQA
       7232 |      16544 | Rdr |06  00                                                                   |     | RID
      17956 |      52164 | Tag |12  49  06  c2  70  b0  d2                                               |     |
      55232 |      83264 | Rdr |00  00  00  00  00  00  d2                                               |  ok | RALL
      84516 |     130540 | Tag |12  49  06  c2  70  b0  d2  31  57  03  11  d1  01  0d  55  01  65  78  61  6d  70  6c  65  2e  63  6f  6d  fe  00  00  00  00 |     | NDEF
'''),
}
DEFAULT_RETURN = 1
