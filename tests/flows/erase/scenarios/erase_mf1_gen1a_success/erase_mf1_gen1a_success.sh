#!/bin/bash
# Erase MF1 Gen1a magic card — cwipe success
# Trace source: trace_erase_flow_20260330.txt lines 6-15
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="erase_mf1_gen1a_success"
source "${PROJECT}/tests/flows/erase/includes/erase_common.sh"
run_erase_scenario 0 3 "toast:Erase successful"
