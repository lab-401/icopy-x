#!/bin/bash
# Console test: RIGHT on READ_FAILED result screen — MF Classic 1K (all sectors fail)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_console_on_failure"
BOOT_TIMEOUT=300
TRIGGER_WAIT=180
source "${PROJECT}/tests/flows/read/includes/read_console_common.sh"
run_read_console_on_result_scenario 3 "toast:Read Failed"
