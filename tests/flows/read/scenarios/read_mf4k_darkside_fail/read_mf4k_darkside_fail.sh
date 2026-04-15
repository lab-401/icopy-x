#!/bin/bash
# Read scenario: mf4k_darkside_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf4k_darkside_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "M1:Sniff"
