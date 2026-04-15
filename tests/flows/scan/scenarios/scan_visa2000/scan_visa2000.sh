#!/bin/bash
# Scan scenario: visa2000
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_visa2000"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
