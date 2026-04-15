#!/bin/bash
# Scan scenario: no_tag
PROJECT="${PROJECT:-/home/qx/icopy-x-reimpl}"
SCENARIO="scan_no_tag"
source "${PROJECT}/tests/flows/scan/includes/scan_common.sh"
run_scan_scenario 3
