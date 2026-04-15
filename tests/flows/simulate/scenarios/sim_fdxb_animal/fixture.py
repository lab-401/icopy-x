# Simulate scenario: sim_fdxb_animal
# LF FDX-B Animal (type 28): sim with default-edited Country/ID/AnimalBit
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf FDX sim c {country} n {id} s
#
# Note: trailing 's' flag = animal/short mode
# Defaults: Country=0001, ID=0000000001

SCENARIO_RESPONSES = {
    'lf FDX sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 28
SIM_INDEX = 14
