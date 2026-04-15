#!/bin/bash
# Simulate scenario: sim_pwr_during_sim
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_pwr_during_sim"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 5 3 "pwr_during_sim" ""
