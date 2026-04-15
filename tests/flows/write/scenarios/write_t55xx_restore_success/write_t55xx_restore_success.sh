#!/bin/bash
# Write scenario: write_t55xx_restore_success
# NOTE: T55XX write includes internal verify (Verifying... shown during write phase).
# write.so passes raw=None to lfverify.verify() because T55XX stores the dump path
# in the 'file' field, not 'raw'. The separate M1 verify button always fails (-10).
# This is a real device limitation — verified via debug tracing.
# We test the write+internal-verify path, which shows "Write successful!" on success.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_t55xx_restore_success"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=90
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Write successful" "no_verify" "toast:Write successful"
