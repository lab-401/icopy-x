#!/bin/bash
# Scenario: 14A Sniff with empty trace — no tag communication captured
# Flow: GOTO:4 → select 14A → M1 start → M2 finish → empty result (Save dimmed)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_14a_empty_trace"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=0 (14A is default), min_unique=3
# Ground truth: FB state_059 — Save dimmed for TraceLen: 0, no save attempted
run_sniff_scenario 0 5 "toast:Sniffing in progress" "M2:Save" "no_save"
