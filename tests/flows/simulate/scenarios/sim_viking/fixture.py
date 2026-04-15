# Simulate scenario: sim_viking
# LF Viking (type 15): sim with default-edited UID
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf Viking sim {edited_uid}
#
# Note: case-sensitive "Viking" in PM3 command

SCENARIO_RESPONSES = {
    'lf Viking sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 15
SIM_INDEX = 10
