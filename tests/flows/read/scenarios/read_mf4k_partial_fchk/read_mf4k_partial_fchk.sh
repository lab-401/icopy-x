#!/bin/bash
# Read scenario: mf4k_partial_fchk
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_partial_fchk"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:File saved"
