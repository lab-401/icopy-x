#!/bin/bash
# Write scenario: write_ntag215_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_ntag215_success"
BOOT_TIMEOUT=120
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=90
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification successful" "" "toast:Write successful!"
