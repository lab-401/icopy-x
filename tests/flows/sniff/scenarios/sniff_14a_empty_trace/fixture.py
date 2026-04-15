# 14A Sniff — empty trace (no tag communication captured)
# PM3 commands (verified by QEMU .so behavior):
#   1. hf 14a sniff  — start sniff (fired by M1=Start)
#   2. hf list mf    — parse trace (fired by M2=Finish → showResult())
# Both return successfully but trace is empty (len = 0)
SCENARIO_RESPONSES = {
    'hf 14a sniff': (0, '''[usb] pm3 --> hf 14a sniff
#db# Starting to sniff
trace len = 0
'''),
    'hf list mf': (0, '''[usb] pm3 --> hf list mf

Recorded activity (trace len = 0 bytes)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
'''),
}
DEFAULT_RETURN = 1
