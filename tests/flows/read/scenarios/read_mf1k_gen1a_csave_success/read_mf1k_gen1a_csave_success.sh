#!/bin/bash
# Read scenario: mf1k_gen1a_csave_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_gen1a_csave_success"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# Gen1a csave: 64 block dump via backdoor — needs extended timeout
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:File saved"
