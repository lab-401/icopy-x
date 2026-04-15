#!/bin/bash
# Write scenario: write_iclass_key_calc_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_iclass_key_calc_fail"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=80
WRITE_TRIGGER_WAIT=40
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 4 "toast:Write failed" "no_verify" "toast:Write failed"
