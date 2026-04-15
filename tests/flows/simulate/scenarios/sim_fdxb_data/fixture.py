# Simulate scenario: sim_fdxb_data
# LF FDX-B Data (type 28): sim with default-edited Country/ID/Ext
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §4
#
# PM3 command sequence:
#   lf FDX sim c {country} n {id} e {ext}
#
# Note: 'e {ext}' flag = extended/data mode (no trailing 's')
# Defaults: Country=0001, ID=0000000001, Ext=001

SCENARIO_RESPONSES = {
    'lf FDX sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 28
SIM_INDEX = 15
