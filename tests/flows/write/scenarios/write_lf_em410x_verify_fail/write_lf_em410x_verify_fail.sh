#!/bin/bash
# Write scenario: write_lf_em410x_verify_fail
# write.write.run() calls lfwrite.write() (clone+DRM) then lfverify.verify() (inline verify).
# If inline verify succeeds → "Write successful!" toast.
# Then explicit verify via M1 press calls lfverify.verify() again.
# This scenario: inline verify matches (write succeeds), explicit verify gets
# a DIFFERENT UID → "Verification failed!" toast from the explicit verify phase.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_lf_em410x_verify_fail"
BOOT_TIMEOUT=150
READ_TRIGGER_WAIT=60
WRITE_TRIGGER_WAIT=90
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification failed" "" "toast:Write successful!"
