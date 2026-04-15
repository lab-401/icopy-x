#!/bin/bash
# Simulate scenario: sim_fdxb_animal
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_fdxb_animal"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 14 3 "lf_sim" "M2:Start"
