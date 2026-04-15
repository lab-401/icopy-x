#!/bin/bash
# Auto-Copy scenario: autocopy_t55xx_happy
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="autocopy_t55xx_happy"
BOOT_TIMEOUT=600
AUTOCOPY_TRIGGER_WAIT=240
WRITE_TRIGGER_WAIT=300
VERIFY_TRIGGER_WAIT=60
source "${PROJECT}/tests/flows/auto-copy/includes/auto_copy_common.sh"
# T55XX direct write succeeds but internal lfverify needs block-specific read responses
# not provided in this fixture. Test write success only, skip explicit verify.
run_auto_copy_scenario 5 "toast:Write successful!" "no_verify"
