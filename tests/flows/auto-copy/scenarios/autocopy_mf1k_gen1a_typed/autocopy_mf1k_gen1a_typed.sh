#!/bin/bash
# Auto-Copy scenario: autocopy_mf1k_gen1a_typed
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_mf1k_gen1a_typed"
BOOT_TIMEOUT=600
AUTOCOPY_TRIGGER_WAIT=240
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/auto-copy/includes/auto_copy_common.sh"
run_auto_copy_scenario 5 "toast:Write successful" "no_verify"
