# T5577 Sniff — password 20206666 found in write commands
# Ground truth: sniff_strings.txt line 869-871 — T5577 parser regexes:
#   "Leading [0-9a-zA-Z]* pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\|"
#   "Default pwd write\s+\|\s+([A-Fa-f0-9]{8})\s\|"
# The pipe-delimited table format is what the .so parsers match against.
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
[+] Default pwd write | 20206666 | 00148040 |  1  |  0   |  Y  |  N  | 0000000000
[+] Default pwd write | 20206666 | FE80A6C0 |  2  |  0   |  Y  |  N  | 0000000000
[+] Default pwd write | 20206666 | 00000000 |  3  |  0   |  Y  |  N  | 0000000000
[+] Default pwd write | 20206666 | 00107060 |  0  |  0   |  Y  |  N  | 0000000000
125k_sniff_finished
'''),
}
DEFAULT_RETURN = 1
