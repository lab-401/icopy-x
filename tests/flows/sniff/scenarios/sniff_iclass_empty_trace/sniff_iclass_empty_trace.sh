#!/bin/bash
# Scenario: iCLASS Sniff with empty trace — no tag communication captured
# Flow: GOTO:4 → DOWN×2 → OK → M1 start → M2 finish → empty result (Save dimmed)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_iclass_empty_trace"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=2 (iCLASS is third item), min_unique=3
# Ground truth: FB state_059 — Save dimmed for empty trace, no save attempted
run_sniff_scenario 2 5 "toast:Sniffing in progress" "M2:Save" "no_save"
