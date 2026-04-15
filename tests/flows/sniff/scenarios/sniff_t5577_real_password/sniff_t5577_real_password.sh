#!/bin/bash
# Scenario: T5577 Sniff — real password FF000000 found in write/pwd read commands
# Flow: GOTO:4 → DOWN×4 → OK → M1 start → [auto-finish] → result → save
# Real trace data from user. T5577 always auto-finishes (timeout=-1).
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_t5577_real_password"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=4, min_unique=5, auto_finish (T5577 — no M2 press to stop)
run_sniff_scenario 4 5 "toast:Sniffing in progress" "M2:Save" "save" "" "auto_finish"
