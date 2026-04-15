#!/bin/bash
# Write scenario: write_mf1k_7b_standard_success
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="write_mf1k_7b_standard_success"
source "${PROJECT}/tests/flows/write/includes/write_common.sh"
run_write_scenario 5 "toast:Verification successful" "" "toast:Write successful!"
