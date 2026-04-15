#!/bin/bash
# Simulate scenario: sim_jablotron
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_jablotron"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 12 3 "lf_sim" "M2:Start"
