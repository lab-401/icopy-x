#!/bin/bash
# Auto-Copy scenario: autocopy_lf_awid
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_lf_awid"
BOOT_TIMEOUT=600
AUTOCOPY_TRIGGER_WAIT=240
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/auto-copy/includes/auto_copy_common.sh"
run_auto_copy_scenario 6 "toast:Verification successful" "" "toast:Write successful!"
