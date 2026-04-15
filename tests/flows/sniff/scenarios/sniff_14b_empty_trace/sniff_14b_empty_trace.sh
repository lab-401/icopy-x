#!/bin/bash
# Scenario: 14B Sniff with empty trace — no tag communication captured
# Flow: GOTO:4 → DOWN×1 → OK → M1 start → M2 finish → empty result (Save dimmed)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_14b_empty_trace"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=1 (14B is second item), min_unique=3
# Ground truth: FB state_059 — Save dimmed for empty trace, no save attempted
run_sniff_scenario 1 5 "toast:Sniffing in progress" "M2:Save" "no_save"
