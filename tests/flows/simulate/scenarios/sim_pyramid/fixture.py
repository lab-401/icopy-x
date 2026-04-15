# Simulate scenario: sim_pyramid
# LF Pyramid (type 16): sim with default-edited FC/CN
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf Pyramid sim {fc} {cn}
#
# Note: case-sensitive "Pyramid" in PM3 command
# Defaults: FC=001, CN=00001

SCENARIO_RESPONSES = {
    'lf Pyramid sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 16
SIM_INDEX = 11
