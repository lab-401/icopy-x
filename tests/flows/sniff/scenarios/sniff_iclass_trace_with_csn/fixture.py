# iClass Sniff — CSN captured from IDENTIFY response
# Ground truth: PM3 hf iclass sniff + hf list iclass output format
# CSN appears in IDENTIFY response as 8-byte hex
SCENARIO_RESPONSES = {
    'hf iclass sniff': (1, '''
#db# Starting iClass sniff
trace len = 480
'''),
    'hf list iclass': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 480 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] iClass - all times are in carrier periods (1/13.56MHz)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
          0 |        992 | Rdr |06                                                                       |     | ACTALL
       2228 |       4596 | Tag |0f                                                                       |     |
       7232 |      16544 | Rdr |0c                                                                       |     | IDENTIFY
      17956 |      52164 | Tag |2a  d7  88  10  06  0f  33  d8                                           |     | CSN
      55232 |      83264 | Rdr |81  2a  d7  88  10  06  0f  33  d8                                       |  ok | SELECT
      84516 |     118540 | Tag |a8  00  00  00  f0  ff  ff  ff                                           |     | CC
     120000 |     148000 | Rdr |88  02                                                                   |  ok | READCHECK(2)
     149000 |     181000 | Tag |ab  cd  ef  01  23  45  67  89                                           |     | MAC
'''),
}
DEFAULT_RETURN = 1
