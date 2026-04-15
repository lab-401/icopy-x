#!/bin/bash
# Read scenario: ultralight_empty
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_ultralight_empty"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:Read Failed"
