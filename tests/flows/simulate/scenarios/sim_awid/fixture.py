# Simulate scenario: sim_awid
# LF AWID (type 11): sim with valid FC/CN/Format after editing
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf awid sim {fc} {cn} {format}
#
# Defaults: FC=222222, CN=444444, Format=26
# After valid editing: FC=2, CN=5, Format=27

SCENARIO_RESPONSES = {
    'lf awid sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 11
SIM_INDEX = 7
