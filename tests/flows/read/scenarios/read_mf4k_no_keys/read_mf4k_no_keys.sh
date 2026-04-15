#!/bin/bash
# Read scenario: mf4k_no_keys
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_no_keys"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# 4K no_keys: darkside → nested → 40 individual nested → 40 rdsc = 85 PM3 commands
BOOT_TIMEOUT=600
TRIGGER_WAIT=480
run_read_scenario 3 "toast:Read Failed"
