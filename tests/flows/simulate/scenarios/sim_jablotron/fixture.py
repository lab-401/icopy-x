# Simulate scenario: sim_jablotron
# LF Jablotron (type 30): sim with default-edited UID
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf Jablotron sim {edited_uid}
#
# Note: case-sensitive "Jablotron" in PM3 command

SCENARIO_RESPONSES = {
    'lf Jablotron sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 30
SIM_INDEX = 12
