#!/bin/bash
# Scan scenario: ntag215
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_ntag215"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
