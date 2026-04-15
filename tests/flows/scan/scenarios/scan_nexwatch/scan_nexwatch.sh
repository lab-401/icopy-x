#!/bin/bash
# Scan scenario: nexwatch
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_nexwatch"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
