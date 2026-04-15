#!/bin/bash
# Read scenario: wrong tag type detected — user selected M1 1K but EM410x found
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_wrong_type"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Wrong type"
