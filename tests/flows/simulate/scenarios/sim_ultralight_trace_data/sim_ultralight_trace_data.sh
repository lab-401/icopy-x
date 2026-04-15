#!/bin/bash
# Simulate scenario: sim_ultralight_trace_data
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sim_ultralight_trace_data"
source "${PROJECT}/tests/flows/simulate/includes/sim_common.sh"
run_sim_scenario 2 3 "trace_data" "content:TraceLen"
