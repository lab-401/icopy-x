# T5577 Sniff — auto-finish via 125k_sniff_finished marker
# PM3 commands (verified by trace_sniff_flow_20260403.txt + trace_sniff_t5577_enhanced_20260404.txt):
#   1. lf config a 0 t 20 s 10000  — configure LF sampling
#   2. lf t55xx sniff               — start LF sniff
#   Response contains 125k_sniff_finished marker → onData() auto-stops
# Ground truth: real device response contains:
#   "[=] Reading N bytes from device memory" — parsed by parserLfTraceLen()
#   "[+] Default pwd write | XXXXXXXX |" — parsed by parserT5577WriteKeyForLine regex
SCENARIO_RESPONSES = {
    'lf config a 0 t 20 s 10000': (1, '''
LF Sampling config
  [a]  decimation..: 0
  [b]  bits per sample...: 8
  [d]  divisor......: 95  ( 125.00 kHz )
  [t]  threshold....: 20
  [s]  samples to skip..: 10000
'''),
    'lf t55xx sniff': (1, '''[#] LF Sampling config
[#]   [q] divisor.............95 ( 125.00 kHz )
[#]   [b] bits per sample.....8
[#]   [d] decimation..........1
[#]   [a] averaging...........No
[#]   [t] trigger threshold...20
[#]   [s] samples to skip.....10000
[#] LF Sampling Stack
[#]   Max stack usage.........4472 / 8480 bytes
[#] Done, saved 42260 out of 0 seen samples at 8 bits/sample
[=] Reading 42259 bytes from device memory
[+] Data fetched
[=] Samples @ 8 bits/smpl, decimation 1:1

[=] T55xx command detection
[+] Downlink mode         | password |   Data   | blk | page |  0  |  1  | raw
[+] ----------------------+----------+----------+-----+------+-----+-----+-------
[+] Default pwd write | 00000000 | 00148040 |  1  |  0   |  Y  |  N  | 0000000000
[+] Default pwd write | 00000000 | FE80A6C0 |  2  |  0   |  Y  |  N  | 0000000000
[+] Default pwd write | 00000000 | 00000000 |  3  |  0   |  Y  |  N  | 0000000000
[+] Default pwd write | 00000000 | 00107060 |  0  |  0   |  Y  |  N  | 0000000000
125k_sniff_finished
'''),
}
DEFAULT_RETURN = 1
