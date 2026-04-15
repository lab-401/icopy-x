# Simulate scenario: sim_em410x
# LF EM410x (type 8): sim with default-edited UID
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf em 410x_sim {edited_uid}

SCENARIO_RESPONSES = {
    'lf em 410x_sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
SIM_INDEX = 5
