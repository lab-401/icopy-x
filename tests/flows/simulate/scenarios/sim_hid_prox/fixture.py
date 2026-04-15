# Simulate scenario: sim_hid_prox
# LF HID Prox (type 9): sim with default-edited raw ID
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf hid sim {edited_raw}

SCENARIO_RESPONSES = {
    'lf hid sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 9
SIM_INDEX = 6
