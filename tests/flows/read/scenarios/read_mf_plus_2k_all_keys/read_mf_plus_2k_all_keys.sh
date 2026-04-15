#!/bin/bash
# Read scenario: read_mf_plus_2k_all_keys
# KNOWN ISSUE: fixture detects type 1 (MF Classic 1K) instead of type 26 (MF Plus 2K).
# Needs better hf 14a info fixture to distinguish Plus 2K from Classic 1K.
# Skip validation until fixture is corrected.
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf_plus_2k_all_keys"
SKIP_VALIDATION=1
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# Plus 2K = 32 sectors — needs extended timeout under QEMU
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:File saved"
