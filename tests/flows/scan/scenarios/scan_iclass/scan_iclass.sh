#!/bin/bash
# Scan scenario: iclass
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_iclass"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
