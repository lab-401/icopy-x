#!/bin/bash
# Simulate scenario: sim_gprox_ii
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_gprox_ii"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 9 3 "lf_sim" "M2:Start"
