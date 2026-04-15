# Simulate scenario: sim_nedap
# LF Nedap (type 32): sim with default-edited Subtype/CN/ID
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf nedap sim s {subtype} c {cn} i {id}
#
# Defaults: Subtype=0x01, CN=00001, ID=00001

SCENARIO_RESPONSES = {
    'lf nedap sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 32
SIM_INDEX = 13
