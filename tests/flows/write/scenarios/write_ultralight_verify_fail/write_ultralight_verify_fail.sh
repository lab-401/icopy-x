#!/bin/bash
# Write scenario: write_ultralight_verify_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_ultralight_verify_fail"
BOOT_TIMEOUT=120
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=90
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification failed" "" "toast:Write successful!"
