#!/bin/bash
# Read scenario: iso15693
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_iso15693"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
