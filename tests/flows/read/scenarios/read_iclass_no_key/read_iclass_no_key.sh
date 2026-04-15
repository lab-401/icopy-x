#!/bin/bash
# Read scenario: iclass_no_key
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_iclass_no_key"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
