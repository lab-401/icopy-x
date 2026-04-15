#!/bin/bash
# Read scenario: lf_em4305_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_lf_em4305_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Wrong type"
