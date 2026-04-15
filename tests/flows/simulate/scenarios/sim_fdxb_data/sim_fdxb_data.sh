#!/bin/bash
# Simulate scenario: sim_fdxb_data
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_fdxb_data"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 15 3 "lf_sim" "M2:Start"
