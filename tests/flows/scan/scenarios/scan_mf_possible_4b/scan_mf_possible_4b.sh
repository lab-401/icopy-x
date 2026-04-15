#!/bin/bash
# Scan scenario: mf_possible_4b
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_mf_possible_4b"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
