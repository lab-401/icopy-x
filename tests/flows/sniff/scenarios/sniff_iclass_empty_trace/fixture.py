# iCLASS Sniff — empty trace (no tag communication captured)
# PM3 commands (verified by QEMU .so behavior):
#   1. hf iclass sniff  — start sniff (fired by M1=Start)
#   2. hf list iclass   — parse trace (fired by M2=Finish → showResult())
# Both return successfully but trace is empty (len = 0)
SCENARIO_RESPONSES = {
    'hf iclass sniff': (0, '''[usb] pm3 --> hf iclass sniff
#db# Starting to sniff
trace len = 0
'''),
    'hf list iclass': (0, '''[usb] pm3 --> hf list iclass

Recorded activity (trace len = 0 bytes)

      Start |        End | Src | Data (! denotes parity error)                                           | CRC | Annotation
------------+------------+-----+-------------------------------------------------------------------------+-----+--------------------
'''),
}
DEFAULT_RETURN = 1
