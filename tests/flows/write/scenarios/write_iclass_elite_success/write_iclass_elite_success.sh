#!/bin/bash
# Write scenario: write_iclass_elite_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_iclass_elite_success"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=80
WRITE_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
# iCLASS write: wrbl returns "successful" for all blocks.
# Verify skipped: mock returns same rdbl data for all blocks, can't match per-block
# dump file contents. Write success confirmed by wrbl "successful" keyword.
run_write_scenario 4 "toast:Write successful" "no_verify" "toast:Write successful"
