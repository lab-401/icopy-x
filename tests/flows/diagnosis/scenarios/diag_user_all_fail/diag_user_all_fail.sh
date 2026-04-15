#!/bin/bash
# Diagnosis — User diagnosis: ALL 5 PM3 tests fail
# Zero voltage, no cards/tags, flash load error
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="diag_user_all_fail"
BOOT_TIMEOUT=300
DIAG_TRIGGER_WAIT=120
source "${PROJECT}/tests/flows/diagnosis/includes/diagnosis_common.sh"
run_diagnosis_scenario 3 "content:Memory:"
