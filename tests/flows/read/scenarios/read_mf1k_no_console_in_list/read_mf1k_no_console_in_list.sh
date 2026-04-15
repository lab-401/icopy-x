#!/bin/bash
# Negative test: RIGHT in ReadListActivity should NOT open console
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_no_console_in_list"
source "${PROJECT}/tests/flows/read/includes/read_console_common.sh"
run_read_no_console_scenario "No console in ReadListActivity" "read_list"
