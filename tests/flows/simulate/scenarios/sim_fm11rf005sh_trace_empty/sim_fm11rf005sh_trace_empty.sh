#!/bin/bash
# Simulate scenario: sim_fm11rf005sh_trace_empty
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_fm11rf005sh_trace_empty"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 4 3 "trace_empty" "content:TraceLen"
