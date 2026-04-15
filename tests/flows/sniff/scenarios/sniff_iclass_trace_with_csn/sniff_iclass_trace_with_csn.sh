#!/bin/bash
# Scenario: iClass Sniff with CSN captured in trace
# Flow: GOTO:4 → DOWN×2 → OK → M1 start → M2 finish → result with CSN → save
# Ground truth: sniff_iclass_trace_result fixture format + iClass protocol
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_iclass_trace_with_csn"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"
run_sniff_scenario 2 5 "toast:Sniffing in progress" "M2:Save" "save"
