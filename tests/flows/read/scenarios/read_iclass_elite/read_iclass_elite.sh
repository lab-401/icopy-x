#!/bin/bash
# Read scenario: read_iclass_elite
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_iclass_elite"
BOOT_TIMEOUT=180  # iClass HF search takes longer to reach scan result under QEMU
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
