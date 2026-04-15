#!/bin/bash
# Read scenario: iclass_legacy
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_iclass_legacy"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
