#!/bin/bash
# Simulate scenario: sim_m1_s70_4k_trace_empty
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_m1_s70_4k_trace_empty"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 1 3 "trace_empty" "content:TraceLen"
