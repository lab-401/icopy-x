#!/bin/bash
# Auto-Copy scenario: autocopy_mf4k_happy
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_mf4k_happy"
# MF4K has ~216 writable blocks at ~3s each = ~650s. Need 900s timeout.
BOOT_TIMEOUT=1200
AUTOCOPY_TRIGGER_WAIT=240
WRITE_TRIGGER_WAIT=900
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/auto-copy/includes/auto_copy_common.sh"
run_auto_copy_scenario 5 "toast:Write successful" "no_verify"
