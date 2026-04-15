#!/bin/bash
# Read scenario: mf1k_partial_fchk
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_partial_fchk"
TRIGGER_WAIT=108  # Partial fchk key checking needs extra time under QEMU
BOOT_TIMEOUT=180
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
