# iClass Sniff — sniff command returns failure (ret=-1)
# Ground truth: trace_sniff_flow_20260403.txt — real device returned ret=-1 for hf iclass sniff
# hf list iclass returns empty trace (0 bytes)
SCENARIO_RESPONSES = {
    'hf iclass sniff': (-1, '\n'),
    'hf list iclass': (1, '''[=] downloading tracelog data from device
[+] Recorded activity (trace len = 0 bytes)
[=] start = start of start frame end = end of frame. src = source of transfer
[=] iClass - all times are in carrier periods (1/13.56MHz)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
'''),
}
DEFAULT_RETURN = 1
