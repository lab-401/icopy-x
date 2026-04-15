# Simulate scenario: sim_gprox_ii
# LF G-Prox II (type 13): sim with default-edited FC/CN/Format
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf gproxii sim {fc} {cn} {format}
#
# Defaults: FC=001, CN=00001, Format=026

SCENARIO_RESPONSES = {
    'lf gproxii sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 13
SIM_INDEX = 9
