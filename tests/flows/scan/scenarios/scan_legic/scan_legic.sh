#!/bin/bash
# Scan scenario: legic
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_legic"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
