#!/bin/bash
# Simulate scenario: sim_hid_prox
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_hid_prox"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 6 3 "lf_sim" "M2:Start"
