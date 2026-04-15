#!/bin/bash
# Simulate scenario: sim_nedap_validation_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_nedap_validation_fail"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 13 3 "validation_fail" "toast:Input invalid"
