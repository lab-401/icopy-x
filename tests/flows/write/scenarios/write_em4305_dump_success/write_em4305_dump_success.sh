#!/bin/bash
# Write scenario: write_em4305_dump_success
# EM4305 dump write: 16 lf em 4x05_write commands + verify via lf em 4x05_read.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_em4305_dump_success"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=90
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 4 "toast:Write successful" "no_verify" "toast:Write successful"
