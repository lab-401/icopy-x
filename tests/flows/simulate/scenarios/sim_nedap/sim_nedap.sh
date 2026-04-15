#!/bin/bash
# Simulate scenario: sim_nedap
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_nedap"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 13 3 "lf_sim" "M2:Start"
