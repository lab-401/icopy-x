#!/bin/bash
# Simulate scenario: sim_em410x
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_em410x"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 5 3 "lf_sim" "M2:Start"
