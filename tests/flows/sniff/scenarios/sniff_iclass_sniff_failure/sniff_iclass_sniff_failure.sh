#!/bin/bash
# Scenario: iClass Sniff — sniff command fails (ret=-1), empty result
# Flow: GOTO:4 → DOWN×2 → OK → M1 start → M2 finish → empty result (Save dimmed)
# Ground truth: trace_sniff_flow_20260403.txt — real device iClass returned ret=-1
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_iclass_sniff_failure"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"
# Ground truth: sniff failure (ret=-1) → empty trace → Save dimmed, no save attempted
run_sniff_scenario 2 5 "toast:Sniffing in progress" "M2:Save" "no_save"
