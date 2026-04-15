# T5577 Sniff — empty (no LF data captured)
# PM3 commands (verified by QEMU .so behavior):
#   1. lf config a 0 t 20 s 10000  — configure LF sampling
#   2. lf t55xx sniff               — start LF sniff (fired by M1=Start)
#   No parse command — T5577 data would be in sniff output, but none captured
SCENARIO_RESPONSES = {
    'lf config a 0 t 20 s 10000': (0, '''[usb] pm3 --> lf config a 0 t 20 s 10000

LF Sampling config
  [a]  decimation..: 0
  [b]  bits per sample...: 8
  [d]  divisor......: 95  ( 125.00 kHz )
  [t]  threshold....: 20
  [s]  samples to skip..: 10000
'''),
    'lf t55xx sniff': (0, '''[usb] pm3 --> lf t55xx sniff
#db# Starting LF sniff
'''),
}
DEFAULT_RETURN = 1
