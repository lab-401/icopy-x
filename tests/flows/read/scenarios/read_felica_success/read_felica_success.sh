#!/bin/bash
# Read scenario: felica_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_felica_success"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
