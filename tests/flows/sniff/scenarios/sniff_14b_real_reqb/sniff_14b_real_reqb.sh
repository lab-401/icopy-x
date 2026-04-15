#!/bin/bash
# Scenario: 14B Sniff with real REQB data
# Flow: GOTO:4 -> DOWN x1 -> OK -> M1 start -> M2 finish -> result -> save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_14b_real_reqb"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=1 (14B is second item), min_unique=6
run_sniff_scenario 1 6 "toast:Sniffing in progress" "M2:Save" "save"
