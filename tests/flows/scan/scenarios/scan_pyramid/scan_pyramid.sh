#!/bin/bash
# Scan scenario: pyramid
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_pyramid"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
