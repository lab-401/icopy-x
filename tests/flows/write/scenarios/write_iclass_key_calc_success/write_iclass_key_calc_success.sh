#!/bin/bash
# Write scenario: write_iclass_key_calc_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_iclass_key_calc_success"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=80
WRITE_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
# iCLASS key calc + write: calcnewkey → wrbl block 3 with XOR key.
# Verify skipped: mock returns same rdbl data for all blocks.
run_write_scenario 4 "toast:Write successful" "no_verify" "toast:Write successful"
