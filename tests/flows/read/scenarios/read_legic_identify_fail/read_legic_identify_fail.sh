#!/bin/bash
# Read scenario: legic_identify_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_legic_identify_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
