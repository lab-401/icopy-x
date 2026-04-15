#!/bin/bash
# Write scenario: write_mf4k_standard_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_mf4k_standard_success"
BOOT_TIMEOUT=900
READ_TRIGGER_WAIT=200
WRITE_TRIGGER_WAIT=640
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification successful" "" "toast:Write successful!"
