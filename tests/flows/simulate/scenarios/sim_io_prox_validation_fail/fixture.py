# Simulate scenario: sim_io_prox_validation_fail
# Validation failure: field value exceeds max → toast "Input invalid:..."
# Ground truth: V1090_SIMULATION_FLOW_COMPLETE.md §16 (Validation Constraints)
# QEMU-verified: OK-enter-edit changes field, M2 triggers validation
#
# No PM3 commands sent — validation fails before startSim()

SCENARIO_RESPONSES = {}
DEFAULT_RETURN = 1
SIM_INDEX = 8
