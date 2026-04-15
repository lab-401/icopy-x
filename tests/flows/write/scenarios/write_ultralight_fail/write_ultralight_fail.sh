#!/bin/bash
# Write scenario: write_ultralight_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_ultralight_fail"
BOOT_TIMEOUT=120
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=30
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 4 "toast:Write failed" "no_verify" "toast:Write failed"
