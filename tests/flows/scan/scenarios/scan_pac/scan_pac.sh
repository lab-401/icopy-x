#!/bin/bash
# Scan scenario: pac
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_pac"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
