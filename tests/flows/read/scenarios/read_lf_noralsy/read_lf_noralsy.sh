#!/bin/bash
# Read scenario: lf_noralsy
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_lf_noralsy"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:File saved"
