#!/bin/bash
# Simulate scenario: sim_viking
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_viking"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 10 3 "lf_sim" "M2:Start"
