#!/bin/bash
# Scenario: iCLASS Sniff with trace data — happy path
# Flow: GOTO:4 → DOWN×2 → OK → M1 start → M2 finish → result → save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_iclass_trace_result"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=2 (iCLASS is third item), min_unique=3
run_sniff_scenario 2 6 "toast:Sniffing in progress" "M2:Save" "save"
