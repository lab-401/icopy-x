#!/bin/bash
# Read scenario: mf1k_nested_retry
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_nested_retry"
TRIGGER_WAIT=108  # Nested retry needs extra time under QEMU
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
