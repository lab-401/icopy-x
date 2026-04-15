#!/bin/bash
# Scenario: Topaz Sniff with NDEF tag data captured
# Flow: GOTO:4 → DOWN×3 → OK → M1 start → M2 finish → result → save
# Ground truth: PM3 hf topaz sniff + hf list topaz format
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_topaz_trace_ndef"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"
run_sniff_scenario 3 5 "toast:Sniffing in progress" "M2:Save" "save"
