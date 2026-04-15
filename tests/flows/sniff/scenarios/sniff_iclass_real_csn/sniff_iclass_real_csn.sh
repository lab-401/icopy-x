#!/bin/bash
# Scenario: iCLASS Sniff with real CSN data
# Flow: GOTO:4 -> DOWN x2 -> OK -> M1 start -> M2 finish -> result -> save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_iclass_real_csn"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=2 (iCLASS is third item), min_unique=6
run_sniff_scenario 2 6 "toast:Sniffing in progress" "M2:Save" "save" "decoding"
