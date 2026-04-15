#!/bin/bash
# Auto-Copy scenario: autocopy_ul_partial_read
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_ul_partial_read"
BOOT_TIMEOUT=600
AUTOCOPY_TRIGGER_WAIT=240
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/auto-copy/includes/auto_copy_common.sh"
# UL partial dump (hf mfu dump returns -1 with "Partial dump created") is treated as
# Read Failed by the .so — the write phase is never reached. Test as early_exit.
run_auto_copy_scenario 3 "toast:Read Failed" "early_exit"
