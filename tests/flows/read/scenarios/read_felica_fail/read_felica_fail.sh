#!/bin/bash
# Read scenario: felica_fail
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_felica_fail"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
