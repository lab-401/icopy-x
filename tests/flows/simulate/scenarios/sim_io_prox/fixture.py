# Simulate scenario: sim_io_prox
# LF IO Prox (type 12): sim with default-edited Version/FC/CN
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf io sim {version} {fc} {cn}
#
# Defaults: Version=0x01, FC=1, CN=1

SCENARIO_RESPONSES = {
    'lf io sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 12
SIM_INDEX = 8
