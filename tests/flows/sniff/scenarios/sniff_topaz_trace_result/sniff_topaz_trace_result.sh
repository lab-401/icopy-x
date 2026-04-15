#!/bin/bash
# Scenario: Topaz Sniff with trace data — happy path
# Flow: GOTO:4 → DOWN×3 → OK → M1 start → M2 finish → result → save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_topaz_trace_result"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=3 (Topaz is fourth item), min_unique=3
run_sniff_scenario 3 6 "toast:Sniffing in progress" "M2:Save" "save"
