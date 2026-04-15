#!/bin/bash
# Scenario: T5577 Sniff — real block data (C02A4E07, E0152703), no password
# Flow: GOTO:4 → DOWN×4 → OK → M1 start → [auto-finish] → result → save
# Real trace data from user. T5577 always auto-finishes (timeout=-1).
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="sniff_t5577_real_block_data"
source "${PROJECT}/tests/flows/sniff/includes/sniff_common.sh"

# down_count=4, min_unique=5, auto_finish (T5577 — no M2 press to stop)
run_sniff_scenario 4 5 "toast:Sniffing in progress" "M2:Save" "save" "" "auto_finish"
