#!/bin/bash
# Simulate scenario: sim_pyramid
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_pyramid"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 11 3 "lf_sim" "M2:Start"
