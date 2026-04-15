#!/bin/bash
# Console test: RIGHT on READ_SUCCESS result screen — Ultralight
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_ultralight_console_on_success"
BOOT_TIMEOUT=300
TRIGGER_WAIT=180
source "${PROJECT}/tests/flows/read/includes/read_console_common.sh"
run_read_console_on_result_scenario 3 "toast:File saved"
