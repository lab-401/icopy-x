#!/bin/bash
# Read scenario: mf1k_no_keys
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="read_mf1k_no_keys"
source "${PROJECT}/tests/flows/read/includes/read_common.sh"
run_read_scenario 3 "toast:Read Failed"
