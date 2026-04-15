#!/bin/bash
# Read scenario: lf_visa2000
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_lf_visa2000"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
