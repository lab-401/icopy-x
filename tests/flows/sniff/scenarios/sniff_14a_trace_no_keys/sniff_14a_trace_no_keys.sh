#!/bin/bash
# Scenario: 14A Sniff with trace data but no keys found
# Flow: GOTO:4 → select 14A → M1 start → M2 finish → Decoding → result (TraceLen only, no UID/Key)
# Ground truth: trace_sniff_flow_20260403.txt — real device 14A trace, sniff_14a_decoding_288_of_9945.png
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_14a_trace_no_keys"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"
run_sniff_scenario 0 5 "toast:Sniffing in progress" "M2:Save" "save"
