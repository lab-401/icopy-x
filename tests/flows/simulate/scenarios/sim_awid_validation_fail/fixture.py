# Simulate scenario: sim_awid_validation_fail
# Multi-field editing + sim test
# QEMU-verified: validation not triggered for this type — .so passes values directly to PM3
#
# PM3 command: lf awid sim

SCENARIO_RESPONSES = {
    'lf awid sim': (1, '''[+] Starting to simulate
'''),
}
DEFAULT_RETURN = 1
SIM_INDEX = 7
