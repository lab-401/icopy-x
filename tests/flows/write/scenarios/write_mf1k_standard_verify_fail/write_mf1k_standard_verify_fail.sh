#!/bin/bash
# Write scenario: write_mf1k_standard_verify_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_mf1k_standard_verify_fail"
BOOT_TIMEOUT=600
READ_TRIGGER_WAIT=200
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=120
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification failed" "" "toast:Write successful!"
