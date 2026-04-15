#!/bin/bash
# Auto-Copy scenario: autocopy_scan_multi_tag
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_scan_multi_tag"
BOOT_TIMEOUT=600
AUTOCOPY_TRIGGER_WAIT=120
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/auto-copy/includes/auto_copy_common.sh"
run_auto_copy_scenario 3 "toast:Multiple tags" "early_exit"
