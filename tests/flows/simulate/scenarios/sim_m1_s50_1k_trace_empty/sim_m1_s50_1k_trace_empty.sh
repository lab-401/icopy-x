#!/bin/bash
# Simulate scenario: sim_m1_s50_1k_trace_empty
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_m1_s50_1k_trace_empty"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 0 3 "trace_empty" "content:TraceLen"
