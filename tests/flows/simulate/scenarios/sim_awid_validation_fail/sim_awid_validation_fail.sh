#!/bin/bash
# Simulate scenario: sim_awid_validation_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_awid_validation_fail"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 7 3 "lf_sim" "M2:Start"
