#!/bin/bash
# Read scenario: mf1k_partial_nested_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_partial_nested_success"
TRIGGER_WAIT=108  # Partial nested key operations need extra time under QEMU
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
