# Topaz Sniff — empty trace (no tag communication captured)
# PM3 commands (verified by QEMU .so behavior):
#   1. hf topaz sniff  — start sniff (fired by M1=Start)
#   2. hf list topaz   — parse trace (fired by M2=Finish → showResult())
# Both return successfully but trace is empty (len = 0)
SCENARIO_RESPONSES = {
    'hf topaz sniff': (0, '''[usb] pm3 --> hf topaz sniff
#db# Starting to sniff
trace len = 0
'''),
    'hf list topaz': (0, '''[usb] pm3 --> hf list topaz

Recorded activity (trace len = 0 bytes)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
'''),
}
DEFAULT_RETURN = 1
