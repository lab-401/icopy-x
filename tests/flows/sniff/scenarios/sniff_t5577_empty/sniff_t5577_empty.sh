#!/bin/bash
# Scenario: T5577 Sniff with no data captured — empty result
# Flow: GOTO:4 → DOWN×4 → OK → M1 start → M2 finish → empty result → save
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_t5577_empty"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=4 (T5577 is fifth/last item), min_unique=3
# Ground truth: FB state_059 — Save dimmed for empty trace, no save attempted
run_sniff_scenario 4 5 "toast:Sniffing in progress" "M2:Save" "no_save"
