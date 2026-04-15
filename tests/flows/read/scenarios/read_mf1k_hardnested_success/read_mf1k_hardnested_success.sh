#!/bin/bash
# Read scenario: mf1k_hardnested_success
# ACTUAL BEHAVIOR: .so never sends hf mf hardnested automatically.
# After nested "not vulnerable" → goes to Missing Keys / Sniff warning screen.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_hardnested_success"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "M1:Sniff"
