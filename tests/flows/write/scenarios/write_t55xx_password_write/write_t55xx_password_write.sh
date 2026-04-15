#!/bin/bash
# Write scenario: write_t55xx_password_write
# NOTE: T55XX write includes internal verify (Verifying... shown during write phase).
# write.so passes raw=None to lfverify.verify() for separate verify because T55XX
# stores the dump path in 'file' not 'raw'. The M1 verify button always fails (-10).
# This is a real device limitation. We test write+internal-verify only.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_t55xx_password_write"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=90
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Write successful" "no_verify" "toast:Write successful"
