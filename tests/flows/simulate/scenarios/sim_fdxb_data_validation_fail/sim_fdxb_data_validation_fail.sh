#!/bin/bash
# Simulate scenario: sim_fdxb_data_validation_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_fdxb_data_validation_fail"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 15 3 "validation_fail" "toast:Input invalid"
