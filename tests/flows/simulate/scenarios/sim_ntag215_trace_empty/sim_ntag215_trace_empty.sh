#!/bin/bash
# Simulate scenario: sim_ntag215_trace_empty
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_ntag215_trace_empty"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 3 3 "trace_empty" "content:TraceLen"
