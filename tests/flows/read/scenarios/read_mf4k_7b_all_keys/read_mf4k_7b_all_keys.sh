#!/bin/bash
# Read scenario: read_mf4k_7b_all_keys
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_7b_all_keys"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
# 4K = 40 sectors under QEMU — needs extended timeout
BOOT_TIMEOUT=600
TRIGGER_WAIT=360
run_read_scenario 3 "toast:File saved"
