#!/bin/bash
# Simulate scenario: sim_awid
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_awid"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 7 3 "lf_sim" "M2:Start"
