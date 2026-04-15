# 14A Sniff — PWR abort during active sniffing
# PM3 commands (verified by QEMU .so behavior):
#   1. hf 14a sniff  — start sniff (fired by M1=Start)
#   PWR pressed during sniffing — aborts before M2=Finish, no parse command issued
SCENARIO_RESPONSES = {
    'hf 14a sniff': (0, '''[usb] pm3 --> hf 14a sniff
#db# Starting to sniff
trace len = 0
'''),
}
DEFAULT_RETURN = 1
