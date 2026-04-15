#!/bin/bash
# Scenario: 14A Sniff with trace data — happy path
# Flow: GOTO:4 → select "1. 14A Sniff" (default) → M2 start → M2 finish → result → save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_14a_trace_result"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=0 (14A is default selection), min_unique=3
run_sniff_scenario 0 6 "toast:Sniffing in progress" "M2:Save" "save" "decoding"
