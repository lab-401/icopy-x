#!/bin/bash
# Console test: RIGHT during READ_IN_PROGRESS — MF Classic 1K (all default keys)
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_console_during_read"
BOOT_TIMEOUT=300
TRIGGER_WAIT=180
source "${PROJECT}/tests/flows/read/includes/read_console_common.sh"
run_read_console_during_read_scenario 3 "toast:File saved"
