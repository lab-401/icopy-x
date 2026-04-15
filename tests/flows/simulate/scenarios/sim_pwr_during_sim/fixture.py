# Simulate scenario: sim_pwr_during_sim
# PWR key during active simulation — tests stopSim() + exit behavior
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §8 (Key Events - During Simulation)
#
# PM3 command: lf em 410x_sim (simulation starts then PWR stops+exits)

SCENARIO_RESPONSES = {
    'lf em 410x_sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
TAG_TYPE = 8
SIM_INDEX = 5
