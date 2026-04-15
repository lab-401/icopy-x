#!/bin/bash
# Scan scenario: awid
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_awid"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
