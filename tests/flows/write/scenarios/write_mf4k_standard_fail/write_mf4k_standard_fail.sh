#!/bin/bash
# Write scenario: write_mf4k_standard_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_mf4k_standard_fail"
BOOT_TIMEOUT=900
READ_TRIGGER_WAIT=200
WRITE_TRIGGER_WAIT=640
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 4 "toast:Write failed" "no_verify" "toast:Write failed"
