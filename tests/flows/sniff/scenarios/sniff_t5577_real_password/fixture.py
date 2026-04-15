# T5577 Sniff — real password found
# PM3 commands: lf config a 0 t 20 s 10000 + lf t55xx sniff
# Real trace with password FF000000 visible in Default write/pwd read lines
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
[#] Done, saved 38500 out of 0 seen samples at 8 bits/sample
[=] Reading 38499 bytes from device memory
[+] Data fetched
[=] Samples @ 8 bits/smpl, decimation 1:1

[=] T55xx command detection
[+] Downlink mode           |  password  |   Data   | blk | page |  0  |  1  | raw
[+] ------------------------+------------+----------+-----+------+-----+-----+-----
[+] Default write/pwd read  | FF000000   | FF000000 |  6  |   0  |  16 |  45 | 10111111111011
[+] Default write/pwd read  | FF000000   | FF000000 |  6  |   0  |  17 |  46 | 10111111111011
125k_sniff_finished
'''),
}
DEFAULT_RETURN = 1
