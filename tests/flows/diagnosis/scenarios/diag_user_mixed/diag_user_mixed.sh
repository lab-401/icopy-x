#!/bin/bash
# Diagnosis — User diagnosis: mixed results (matches real device trace)
# Antenna voltages pass, readers fail (no tag present), flash pass
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="diag_user_mixed"
BOOT_TIMEOUT=300
DIAG_TRIGGER_WAIT=120
source "${PROJECT}/tests/flows/diagnosis/includes/diagnosis_common.sh"
run_diagnosis_scenario 3 "content:Memory:"
