# Simulate scenario: sim_fdxb_data_validation_fail
# FDX-B Data (type 28): overflow NC beyond 38-bit max (274877906943)
# ISO 11784: NC is 38-bit national ID, max 274877906943
# Validation should fire before PM3 command is sent — no PM3 response needed.

SCENARIO_RESPONSES = {}
DEFAULT_RETURN = 1
SIM_INDEX = 15
