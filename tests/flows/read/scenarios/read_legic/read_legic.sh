#!/bin/bash
# Read scenario: legic
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_legic"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
